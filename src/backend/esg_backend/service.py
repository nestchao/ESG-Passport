"""Transactional workspace operations and API representations."""
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from io import BytesIO
from pathlib import PurePosixPath
import re
import secrets
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import delete, select, tuple_

from .models import (Activity, ActivityEvent, ApprovedSnapshot, Company, Declaration,
                     Document, FactorVersion, Question, Questionnaire, utcnow)
from .rules import calculate_profile, answer_question, suggest_codes, validate_declaration, TITLES

MAX_FILE = 10 * 1024 * 1024
ACTORS = {'owner': 'Mr Lim', 'clerk': 'Aina Tan', 'customer': 'Customer'}
UNITS = {'electricity': {'kWh'}, 'diesel': {'L'}, 'petrol': {'L'}, 'water': {'m3', 'L'},
         'waste_generated': {'kg', 't'}, 'waste_diverted': {'kg', 't'}, 'waste_disposed': {'kg', 't'}}


def safe(value):
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    return value


def row(model, *exclude):
    return safe({column.key: getattr(model, column.key) for column in model.__table__.columns
                 if column.key not in exclude})


def invalid(field, message):
    raise HTTPException(422, detail=[{'loc': ['body', field], 'msg': message, 'type': 'value_error'}])


def validate_file(content, supplied_type):
    if not content or len(content) > MAX_FILE:
        invalid('file', 'Choose a document up to 10 MB.')
    try:
        if supplied_type == 'application/pdf':
            if not content.startswith(b'%PDF-'):
                raise ValueError('Invalid PDF.')
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise ValueError('Password-protected PDFs are not supported.')
            if len(reader.pages) != 1:
                raise ValueError('Upload one PDF page at a time.')
            return 'application/pdf', 'pdf'
        if supplied_type not in ('image/png', 'image/jpeg'):
            raise ValueError('Choose JPEG, PNG or a single-page PDF.')
        with Image.open(BytesIO(content)) as image:
            if image.format not in ('JPEG', 'PNG') or image.width * image.height > 40_000_000:
                raise ValueError('Choose a JPEG or PNG image below 40 megapixels.')
            actual = 'image/png' if image.format == 'PNG' else 'image/jpeg'
            image.verify()
        if actual != supplied_type:
            raise ValueError('The file content does not match its supplied type.')
        return actual, 'png' if actual == 'image/png' else 'jpg'
    except HTTPException:
        raise
    except Exception:
        invalid('file', 'The document is unreadable, unsupported, encrypted or has multiple pages. Upload one readable page.')


class Workspace:
    def __init__(self, session, storage, settings, role='owner'):
        self.db, self.storage, self.settings, self.role = session, storage, settings, role
        self.actor = ACTORS[role]
        self._company = None

    def company(self, lock=False):
        if not lock and self._company is not None:
            return self._company
        query = select(Company).where(Company.id == self.settings.company_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        company = self.db.scalar(query)
        if not company:
            raise HTTPException(409, 'Workspace not initialized. Run migrations and the explicit seed command.')
        self._company = company
        return company

    def require_owner(self):
        if self.role != 'owner':
            raise HTTPException(403, 'Only the Owner can perform this action.')

    def period(self, period):
        if period != self.company().period:
            invalid('period', 'This hackathon workspace supports September 2026 only.')

    def log(self, action, target, summary):
        self.db.add(ActivityEvent(company_id=self.settings.company_id, actor=self.actor, role=self.role,
                                  action=action, target=target, summary=summary))

    def document(self, document_id):
        doc = self.db.scalar(select(Document).where(Document.id == document_id,
                                                    Document.company_id == self.settings.company_id))
        if not doc:
            raise HTTPException(404, 'Document not found.')
        return doc

    def serialize_documents(self, documents, *, include_path=False, include_history=True):
        documents = list(documents)
        if not documents:
            return []
        grouped = {doc.id: [] for doc in documents}
        query = select(Activity).join(Document, Activity.document_id == Document.id).where(
            Document.company_id == self.settings.company_id,
            Activity.document_id.in_(grouped))
        if not include_history:
            query = query.where(tuple_(Activity.document_id, Activity.revision).in_(
                [(doc.id, doc.activity_revision) for doc in documents]))
        for activity in self.db.scalars(query.order_by(Activity.revision, Activity.category)):
            grouped[activity.document_id].append(row(activity, 'company_id', 'document_id'))
        results = []
        for doc in documents:
            output = row(doc, *([] if include_path else ['object_path', 'file_hash']))
            history = grouped[doc.id]
            output['activities'] = [activity for activity in history if activity['revision'] == doc.activity_revision]
            if include_history:
                output['history'] = history
            results.append(output)
        return results

    def serialize_document(self, doc, include_path=False):
        return self.serialize_documents([doc], include_path=include_path)[0]

    def documents(self, *, include_history=True):
        documents = self.db.scalars(select(Document).where(
            Document.company_id == self.settings.company_id).order_by(Document.uploaded_at, Document.id))
        return self.serialize_documents(documents, include_history=include_history)

    def declarations(self):
        records = self.db.scalars(select(Declaration).where(Declaration.company_id == self.settings.company_id,
            Declaration.period == self.company().period).order_by(Declaration.code, Declaration.version.desc()))
        latest = {}
        for declaration in records:
            latest.setdefault(declaration.code, row(declaration))
        return list(latest.values())

    def profile(self):
        company = self.company()
        factors = [row(f) for f in self.db.scalars(select(FactorVersion).order_by(FactorVersion.year, FactorVersion.id))]
        result = calculate_profile(row(company), self.documents(include_history=False), self.declarations(), factors, company.period)
        result['version'] = company.version
        return safe(result)

    def invalidate(self):
        company = self.company()
        company.version += 1
        for request in self.db.scalars(select(Questionnaire).where(Questionnaire.company_id == company.id)):
            request.version += 1
            request.status = 'draft'
            for question in self.db.scalars(select(Question).where(Question.questionnaire_id == request.id)):
                question.reviewed = False
                question.version += 1

    def upload(self, filename, category, content, mime_type):
        company = self.company(lock=True)
        if category not in ('electricity', 'diesel', 'petrol', 'water', 'waste'):
            invalid('type', 'Select electricity, diesel, petrol, water or waste.')
        mime, extension = validate_file(content, mime_type)
        digest = hashlib.sha256(content).hexdigest()
        if self.db.scalar(select(Document).where(Document.company_id == company.id, Document.file_hash == digest)):
            raise HTTPException(409, 'This file has already been uploaded. Open its existing record.')
        document_id = str(uuid4())
        name = PurePosixPath((filename or 'record').replace('\\', '/')).name[:240]
        path = f'{company.id}/uploads/{document_id}/{digest}.{extension}'
        doc = Document(id=document_id, company_id=company.id, name=name, type=category, period=company.period,
                       mime_type=mime, file_hash=digest, object_path=path, uploaded_by=self.actor)
        try:
            self.storage.upload(path, content, mime)
            self.db.add(doc)
            self.db.flush()
            self.invalidate()
            self.log('document_uploaded', doc.id, f'Added {name}; quantities await review.')
            result = self.serialize_document(doc)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            try:
                self.storage.delete([path])
            except Exception:
                import logging
                logging.getLogger(__name__).error('Could not clean up an uploaded object after a database failure.')
            raise

    def save_activities(self, document_id, body):
        self.company(lock=True)
        doc = self.document(document_id)
        seen = set()
        for index, item in enumerate(body.activities):
            field = f'activities.{index}'
            allowed = item.category.startswith('waste_') if doc.type == 'waste' else item.category == doc.type
            if not allowed:
                invalid(field + '.category', 'The activity category must match this document type.')
            if item.category in seen:
                invalid(field + '.category', 'Use one total per category per document.')
            seen.add(item.category)
            if item.unit not in UNITS[item.category]:
                invalid(field + '.unit', 'Choose a supported unit for this category.')
            if item.period_start > item.period_end:
                invalid(field + '.period_end', 'End date must follow the start date.')
            start, end = item.period_start.strftime('%Y-%m'), item.period_end.strftime('%Y-%m')
            if start != end:
                if not item.estimated or not item.assumptions or item.allocated_period != doc.period:
                    invalid(field, 'Cross-month records require an estimated allocation to the reporting month and its method.')
                if not start <= item.allocated_period <= end:
                    invalid(field + '.allocated_period', 'Allocation must fall within the source period.')
            elif start != doc.period or item.allocated_period not in (None, doc.period):
                invalid(field + '.period_start', 'Dates must belong to the selected reporting month.')
            if item.estimated and not item.assumptions:
                invalid(field + '.assumptions', 'Describe the estimation method.')
        doc.activity_revision += 1
        doc.version += 1
        doc.confirmed = body.confirmed
        for item in body.activities:
            values = item.model_dump(exclude={'id', 'revision', 'confirmed_by', 'confirmed_at'})
            self.db.add(Activity(company_id=doc.company_id, document_id=doc.id, revision=doc.activity_revision,
                **values, confirmed_by=self.actor if body.confirmed else '', confirmed_at=utcnow() if body.confirmed else None))
        self.invalidate()
        self.log('activity_confirmed' if body.confirmed else 'activity_draft_saved', doc.id,
                 f'Revision {doc.activity_revision}: {len(body.activities)} quantities; confirmed={body.confirmed}.')
        self.db.flush()
        result = self.serialize_document(doc)
        self.db.commit()
        return result

    def save_declaration(self, code, body):
        self.require_owner()
        self.company(lock=True)
        self.period(body.period)
        if code not in TITLES or code.startswith('E'):
            invalid('code', 'Choose a supported social or governance disclosure.')
        try:
            complete = validate_declaration(code, body.answer)
        except ValueError as error:
            invalid('answer', str(error))
        evidence = list(dict.fromkeys(body.evidence_ids))
        for identifier in evidence:
            self.document(identifier)
        previous = self.db.scalar(select(Declaration).where(Declaration.company_id == self.settings.company_id,
            Declaration.code == code, Declaration.period == body.period).order_by(Declaration.version.desc()))
        declaration = Declaration(company_id=self.settings.company_id, code=code, period=body.period,
            version=(previous.version if previous else 0) + 1, answer=body.answer, evidence_ids=evidence,
            complete=complete, declared_by=self.actor)
        self.db.add(declaration)
        self.invalidate()
        self.log('declaration_saved', code, f'Owner declaration version {declaration.version}; complete={complete}.')
        self.db.flush()
        result = row(declaration)
        self.db.commit()
        return result

    def questionnaire(self, identifier):
        result = self.db.scalar(select(Questionnaire).where(Questionnaire.id == identifier,
                                      Questionnaire.company_id == self.settings.company_id))
        if not result:
            raise HTTPException(404, 'Questionnaire not found.')
        return result

    def serialize_request(self, request, *, profile=None, questions=None):
        if profile is None:
            profile = self.profile()
        if questions is None:
            questions = self.db.scalars(select(Question).where(
                Question.questionnaire_id == request.id).order_by(Question.position))
        return {**row(request), 'questions': [safe(answer_question(row(q), profile)) for q in questions]}

    def requests(self):
        requests = list(self.db.scalars(select(Questionnaire).where(
            Questionnaire.company_id == self.settings.company_id).order_by(Questionnaire.created_at)))
        if not requests:
            return []
        profile = self.profile()
        grouped = {request.id: [] for request in requests}
        for question in self.db.scalars(select(Question).where(
                Question.questionnaire_id.in_(grouped)).order_by(Question.position)):
            grouped[question.questionnaire_id].append(question)
        return [self.serialize_request(request, profile=profile, questions=grouped[request.id])
                for request in requests]

    def create_request(self, body):
        self.company(lock=True)
        self.period(body.period)
        request = Questionnaire(company_id=self.settings.company_id, customer=body.customer, period=body.period,
                                due_date=body.due_date)
        self.db.add(request)
        self.db.flush()
        for position, text in enumerate(body.questions):
            self.db.add(Question(questionnaire_id=request.id, text=text, position=position,
                                 rationale='Awaiting matching and human review.', confidence='Low'))
        self.log('questionnaire_created', request.id, f'{body.customer}: {len(body.questions)} questions.')
        self.db.flush()
        result = self.serialize_request(request)
        self.db.commit()
        return result

    def map_request(self, identifier):
        self.company(lock=True)
        request = self.questionnaire(identifier)
        for question in self.db.scalars(select(Question).where(Question.questionnaire_id == request.id)):
            proposed = suggest_codes(question.text)
            question.proposed_codes = proposed
            question.codes = []
            question.reviewed = False
            question.confidence = 'Medium' if proposed else 'Low'
            question.rationale = 'Suggested from question wording; confirm or correct the disclosure.'
            question.uncertainty = 'Wording-based suggestion, not AI. Human confirmation required.'
            if re.search(r'scope\s*3', question.text, re.I):
                question.uncertainty += ' Scope 3 is unsupported; address that part in an owner response.'
            question.version += 1
        request.status = 'draft'
        request.version += 1
        self.log('mapping_proposed', request.id, 'Wording-based suggestions prepared; all mappings require confirmation.')
        self.db.flush()
        result = self.serialize_request(request)
        self.db.commit()
        return result

    def review_question(self, identifier, body):
        self.company(lock=True)
        question = self.db.scalar(select(Question).join(Questionnaire).where(Question.id == identifier,
                                                 Questionnaire.company_id == self.settings.company_id))
        if not question:
            raise HTTPException(404, 'Question not found.')
        if body.manual_answer:
            self.require_owner()
        old_codes = list(question.codes)
        question.codes = list(dict.fromkeys(body.codes))
        question.reviewed = body.reviewed
        question.manual_answer = body.manual_answer or None
        question.manual_declaration = ({'declared_by': self.actor, 'declared_at': safe(utcnow()),
            'period': self.company().period} if body.manual_answer else None)
        question.reviewed_by = self.actor if body.reviewed else ''
        question.reviewed_at = utcnow() if body.reviewed else None
        question.version += 1
        request = self.questionnaire(question.questionnaire_id)
        request.version += 1
        request.status = 'draft'
        self.log('mapping_reviewed', identifier, f'Version {question.version}: {old_codes} → {question.codes}; reviewed={body.reviewed}.')
        self.db.flush()
        result = safe(answer_question(row(question), self.profile()))
        self.db.commit()
        return result

    def handoff(self, identifier):
        self.company(lock=True)
        request = self.questionnaire(identifier)
        questions = list(self.db.scalars(select(Question).where(Question.questionnaire_id == request.id)))
        if not questions or any(not q.reviewed for q in questions):
            raise HTTPException(409, 'Review every question before sending it to the owner.')
        request.status = 'ready_for_owner'
        request.version += 1
        self.log('ready_for_owner', identifier, 'Prepared answers sent to owner; nothing was shared externally.')
        self.db.flush()
        result = self.serialize_request(request)
        self.db.commit()
        return result

    def approve(self, identifier, body):
        self.require_owner()
        self.company(lock=True)
        request = self.questionnaire(identifier)
        if request.version != body.version:
            raise HTTPException(409, 'This draft changed. Refresh and review it before approving.')
        prepared = self.serialize_request(request)
        if not prepared['questions'] or any(not q['reviewed'] for q in prepared['questions']):
            raise HTTPException(409, 'Review every question before approving.')
        selected = list(dict.fromkeys(body.selected_evidence_ids))
        evidence = [self.serialize_document(self.document(identifier), include_path=True) for identifier in selected]
        included = set(selected)
        for question in prepared['questions']:
            question['evidence_ids'] = [identifier for identifier in question.get('evidence_ids', []) if identifier in included]
            for metric in question.get('metrics', []):
                metric['evidence_ids'] = [identifier for identifier in metric.get('evidence_ids', []) if identifier in included]
                metric['confirmation_history'] = [entry for entry in metric.get('confirmation_history', [])
                                                  if not entry.get('evidence_id') or entry['evidence_id'] in included]
                for component in metric.get('components', []):
                    component['evidence_ids'] = [identifier for identifier in component.get('evidence_ids', []) if identifier in included]
        created = utcnow()
        snapshot = {'company': row(self.company()), 'period': request.period, 'recipient': body.recipient,
            'approved_by': self.actor, 'approved_at': safe(created), 'questions': prepared['questions'],
            'questionnaire_version': request.version, 'calculation_version': 'rules-v1',
            'selected_evidence_ids': selected, 'evidence': evidence}
        pack = ApprovedSnapshot(company_id=self.settings.company_id, questionnaire_id=request.id,
            token=secrets.token_urlsafe(32), recipient=body.recipient, approved_by=self.actor,
            created_at=created, snapshot=safe(snapshot))
        self.db.add(pack)
        request.status = 'shared'
        request.version += 1
        self.log('pack_approved', identifier, f'Immutable snapshot approved for {body.recipient}; {len(selected)} attachments.')
        self.db.flush()
        result = self.serialize_pack(pack)
        self.db.commit()
        return result

    @staticmethod
    def serialize_pack(pack):
        output = row(pack)
        # Never expose private object paths or hashes; customer evidence goes through token routes.
        for document in output['snapshot'].get('evidence', []):
            document.pop('object_path', None)
            document.pop('file_hash', None)
            document.pop('history', None)
        return output

    def pack(self, token):
        pack = self.db.scalar(select(ApprovedSnapshot).where(ApprovedSnapshot.token == token,
                                  ApprovedSnapshot.company_id == self.settings.company_id))
        if not pack:
            raise HTTPException(404, 'Approved pack not found.')
        return pack

    def get_pack(self, token):
        pack = self.pack(token)
        result = self.serialize_pack(pack)
        self.log('customer_pack_viewed', pack.id, 'Approved pack opened using its share token.')
        self.db.commit()
        return result

    def file(self, identifier, token=None):
        if token:
            pack = self.pack(token)
            evidence = next((d for d in pack.snapshot.get('evidence', []) if d['id'] == identifier), None)
            if not evidence or identifier not in pack.snapshot.get('selected_evidence_ids', []):
                raise HTTPException(404, 'This evidence was not included in the approved pack.')
            path, mime, name = evidence['object_path'], evidence['mime_type'], evidence['name']
        else:
            document = self.document(identifier)
            path, mime, name = document.object_path, document.mime_type, document.name
        return self.storage.download(path), mime, name

    def reset(self):
        self.require_owner()
        company = self.company(lock=True)
        if not self.settings.allow_sample_reset or company.id != 'lim-carton' or not company.synthetic:
            raise HTTPException(403, 'Sample reset is disabled for this workspace.')
        paths = list(self.db.scalars(select(Document.object_path).where(Document.company_id == company.id)))
        # Delete database-owned rows explicitly, also preserving correctness in test databases.
        request_ids = select(Questionnaire.id).where(Questionnaire.company_id == company.id)
        self.db.execute(delete(Question).where(Question.questionnaire_id.in_(request_ids)))
        for model in (ApprovedSnapshot, Activity, Declaration, Document, Questionnaire, ActivityEvent):
            self.db.execute(delete(model).where(model.company_id == company.id))
        self.db.execute(delete(Company).where(Company.id == company.id))
        self.db.flush()
        from .seed import seed_workspace
        # Only paths created by this reset are eligible for compensation on failure.
        self.db.info.pop('seed_uploaded_paths', None)
        try:
            seed_workspace(self.db, self.storage, self.settings)
            self.log('sample_reset', self.settings.company_id, 'Only this synthetic workspace was restored.')
            self.db.commit()
        except Exception:
            self.db.rollback()
            new_paths = self.db.info.pop('seed_uploaded_paths', [])
            if new_paths:
                try:
                    self.storage.delete(new_paths)
                except Exception:
                    import logging
                    logging.getLogger(__name__).error('Could not clean up sample objects after a reset failure.')
            raise
        # Originals for all prior packs in this workspace become unreachable after the explicit reset.
        try:
            self.storage.delete(paths)
        except Exception:
            import logging
            logging.getLogger(__name__).error('Some obsolete sample objects could not be removed after reset.')
        return {'reset': True, 'version': 1}
