"""Transactional workspace operations and API representations."""
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
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
        if not re.fullmatch(r'(?!0000)[0-9]{4}-(0[1-9]|1[0-2])', period):
            invalid('period', 'Choose a valid reporting month (YYYY-MM).')
        return period

    def log(self, action, target, summary, period=None):
        self.db.add(ActivityEvent(company_id=self.settings.company_id, actor=self.actor, role=self.role,
                                  action=action, target=target, summary=summary, period=period))

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
            output['archived'] = doc.archived_at is not None
            history = grouped[doc.id]
            output['activities'] = [activity for activity in history if activity['revision'] == doc.activity_revision]
            if include_history:
                output['history'] = history
            results.append(output)
        return results

    def serialize_document(self, doc, include_path=False):
        result = self.serialize_documents([doc], include_path=include_path)[0]
        extraction = result.get('extraction') or {}
        # An earlier OCR parser could have failed even when OCR recognised the
        # bill. Re-evaluate the original only when opening an unconfirmed,
        # activity-free record with a failed extraction. This is a read-only
        # candidate: do not mutate the original record, upload, or confirmation.
        if (not doc.confirmed and not result.get('activities') and not doc.archived_at
                and extraction.get('ocr_status') in ('manual_entry_required', 'unavailable')):
            try:
                from .bill_ocr import extract_upload
                content = self.storage.download(doc.object_path)
                recovered = extract_upload(content, doc.mime_type, doc.type, doc.period)
                if recovered.get('activities') or recovered.get('waste_transfer_candidate'):
                    recovered['uncertainty_notes'].append(
                        'OCR retried for an existing record. Correct and confirm the values; the original extraction is retained.')
                    result['extraction'] = recovered
            except Exception:
                # Recovery must never prevent viewing the uploaded source.
                pass
        return result

    def documents(self, period='2026-09', *, archived=False, include_history=True):
        self.period(period)
        documents = self.db.scalars(select(Document).where(
            Document.company_id == self.settings.company_id, Document.period == period,
            Document.archived_at.is_not(None) if archived else Document.archived_at.is_(None)).order_by(Document.uploaded_at, Document.id))
        return self.serialize_documents(documents, include_history=include_history)

    def declarations(self, period='2026-09'):
        self.period(period)
        records = self.db.scalars(select(Declaration).where(Declaration.company_id == self.settings.company_id,
            Declaration.period == period).order_by(Declaration.code, Declaration.version.desc()))
        latest = {}
        for declaration in records:
            latest.setdefault(declaration.code, row(declaration))
        evidence_ids = {identifier for declaration in latest.values() for identifier in declaration['evidence_ids']}
        available = set(self.db.scalars(select(Document.id).where(Document.company_id == self.settings.company_id,
            Document.archived_at.is_(None), Document.id.in_(evidence_ids)))) if evidence_ids else set()
        for declaration in latest.values():
            if any(identifier not in available for identifier in declaration['evidence_ids']):
                declaration['complete'] = False
        return list(latest.values())

    def profile(self, period='2026-09'):
        self.period(period)
        company = self.company()
        factors = [row(f) for f in self.db.scalars(select(FactorVersion).order_by(FactorVersion.year, FactorVersion.id))]
        result = calculate_profile(row(company), self.documents(period, include_history=False), self.declarations(period), factors, period)
        result['version'] = company.version
        return safe(result)

    def invalidate(self, periods, document_id=None):
        company = self.company()
        company.version += 1
        periods = set(periods)
        if document_id:
            for declaration in self.db.scalars(select(Declaration).where(Declaration.company_id == company.id)):
                if document_id in declaration.evidence_ids:
                    periods.add(declaration.period)
        requests = list(self.db.scalars(select(Questionnaire).where(
            Questionnaire.company_id == company.id, Questionnaire.period.in_(periods))))
        ids = [request.id for request in requests]
        for request in requests:
            request.version += 1
            request.status = 'draft'
        if ids:
            for question in self.db.scalars(select(Question).where(Question.questionnaire_id.in_(ids))):
                question.reviewed = False
                question.version += 1

    def ensure_editable(self, doc, expected_version=None):
        if doc.archived_at:
            raise HTTPException(409, 'Restore this archived document before editing it.')
        self.check_version(doc, expected_version)

    @staticmethod
    def check_version(doc, expected_version):
        if expected_version is not None and doc.version != expected_version:
            raise HTTPException(409, 'This document changed. Refresh before saving.')

    def update_document(self, document_id, body):
        self.company(lock=True)
        doc = self.document(document_id)
        self.ensure_editable(doc, body.expected_version)
        self.period(body.period)
        old_period = doc.period
        doc.name, doc.period = body.name, body.period
        if body.type is not None and body.type != doc.type:
            old_type = doc.type
            doc.type = body.type
            self.log('document_reclassified', doc.id,
                     f'Document category corrected from {old_type} to {doc.type}; reconfirmation required.', doc.period)
        return self.save_activities(document_id, body, confirmed=False, old_period=old_period)

    def archive_document(self, document_id, body, *, restore=False):
        self.company(lock=True)
        doc = self.document(document_id)
        self.check_version(doc, body.expected_version)
        if bool(doc.archived_at) == (not restore):
            raise HTTPException(409, 'Document is already in the requested state.')
        doc.archived_at = None if restore else utcnow()
        doc.archived_by = None if restore else self.actor
        doc.confirmed = False
        doc.version += 1
        self.invalidate([doc.period], doc.id)
        self.log('document_restored' if restore else 'document_archived', doc.id,
                 'Restored for review.' if restore else 'Archived from active reporting.', doc.period)
        self.db.flush()
        result = self.serialize_document(doc)
        self.db.commit()
        return result

    def delete_document(self, document_id, body):
        """Owner-only permanent delete of evidence without approved references.

        The original is temporarily buffered so a DB commit failure can
        restore the immutable Storage object; audit events stay in the DB.
        No approved pack or historical declaration may lose its evidence.
        """
        self.require_owner()
        self.company(lock=True)
        doc = self.db.scalar(select(Document).where(
            Document.id == document_id, Document.company_id == self.settings.company_id
        ).with_for_update())
        if doc is None:
            raise HTTPException(404, 'Document not found.')
        self.check_version(doc, body.expected_version)
        for pack in self.db.scalars(select(ApprovedSnapshot).where(
                ApprovedSnapshot.company_id == self.settings.company_id)):
            snapshot = pack.snapshot or {}
            if (document_id in snapshot.get('selected_evidence_ids', []) or
                    any(item.get('id') == document_id for item in snapshot.get('evidence', []))):
                raise HTTPException(409, 'This record belongs to an approved customer Passport. Archive it instead; approved evidence cannot be deleted.')
        for declaration in self.db.scalars(select(Declaration).where(
                Declaration.company_id == self.settings.company_id)):
            if document_id in (declaration.evidence_ids or []):
                raise HTTPException(409, 'An owner declaration references this record. Remove that reference before deleting, or archive the record.')
        period, path, mime, name = doc.period, doc.object_path, doc.mime_type, doc.name
        original = self.storage.download(path)
        # Explicitly remove revisions; SQLite tests may not enable FK cascades,
        # while Postgres enforces them. Invalidate current drafts before delete.
        self.invalidate([period], document_id)
        self.db.execute(delete(Activity).where(Activity.company_id == self.settings.company_id,
                                               Activity.document_id == document_id))
        self.db.delete(doc)
        self.log('document_deleted', document_id,
                 f'Permanently deleted an eligible {doc.type} record, its activity revisions and source file.', period)
        self.db.flush()
        try:
            # Do not commit a DB deletion when object removal itself fails.
            self.storage.delete([path])
        except Exception:
            self.db.rollback()
            # A storage service may have deleted the file before reporting an
            # error. Check the original and attempt compensation if missing.
            try:
                self.storage.download(path)
            except Exception:
                try:
                    self.storage.upload(path, original, mime)
                except Exception:
                    import logging
                    logging.getLogger(__name__).error('CRITICAL: uncertain Storage deletion left source evidence unavailable.')
            raise
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            try:
                self.storage.upload(path, original, mime)
            except Exception:
                import logging
                logging.getLogger(__name__).error('CRITICAL: failed to restore source evidence after document deletion commit failure.')
            raise
        return {'deleted': True, 'id': document_id, 'period': period}

    def upload(self, filename, category, content, mime_type, period='2026-09', *, precomputed_extraction=None):
        self.period(period)
        company = self.company(lock=True)
        if category not in ('electricity', 'diesel', 'petrol', 'water', 'waste'):
            invalid('type', 'Select electricity, diesel, petrol, water or waste.')
        mime, extension = validate_file(content, mime_type)
        digest = hashlib.sha256(content).hexdigest()
        existing = self.db.scalar(select(Document).where(Document.company_id == company.id, Document.file_hash == digest))
        if existing:
            raise HTTPException(409, {'message': 'This file has already been uploaded. Open its existing record.',
                'document_id': existing.id, 'period': existing.period, 'archived': existing.archived_at is not None})
        document_id = str(uuid4())
        name = PurePosixPath((filename or 'record').replace('\\', '/')).name[:240]
        path = f'{company.id}/uploads/{document_id}/{digest}.{extension}'
        doc = Document(id=document_id, company_id=company.id, name=name, type=category, period=period,
                       mime_type=mime, file_hash=digest, object_path=path, uploaded_by=self.actor)
        try:
            self.storage.upload(path, content, mime)
            # The existing /documents upload now pre-fills the existing editor.
            # OCR is never considered confirmed evidence or a calculation input.
            from copy import deepcopy
            if precomputed_extraction is None:
                from .bill_ocr import extract_upload
                extracted = extract_upload(content, mime, category, period)
            else:
                # Public synthetic fixtures use precomputed values to avoid
                # loading ONNX OCR models on Render's small free instance.
                extracted = deepcopy(precomputed_extraction)
            doc.extraction = extracted
            doc.original_extraction = deepcopy(extracted)
            self.db.add(doc)
            self.db.flush()
            self.invalidate([period])
            self.log('document_uploaded', doc.id, f'Added {name}; quantities await review.', period)
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

    def retry_ocr(self, document_id, body):
        """Re-read an immutable source without changing reviewed activities.

        The first extraction is kept as provenance, and existing activity
        revisions stay untouched until a clerk explicitly reviews the new
        candidates and saves them. Public visitors never run expensive OCR.
        """
        if self.settings.sandbox_instance:
            raise HTTPException(403, 'Live OCR is available in the protected staff workspace only.')
        self.company(lock=True)
        doc = self.document(document_id)
        self.ensure_editable(doc, body.expected_version)
        if doc.confirmed:
            raise HTTPException(409, 'Save this confirmed record as an unconfirmed draft before re-running OCR.')
        from .bill_ocr import extract_upload
        source = self.storage.download(doc.object_path)
        doc.extraction = extract_upload(source, doc.mime_type, doc.type, doc.period)
        doc.version += 1
        self.log('ocr_retried', doc.id,
                 'Original document reprocessed; suggestions still require manual review.', doc.period)
        self.db.flush()
        # Use the persisted candidate rather than the GET read-only recovery path.
        result = self.serialize_documents([doc])[0]
        self.db.commit()
        return result

    def save_activities(self, document_id, body, *, confirmed=None, old_period=None):
        self.company(lock=True)
        doc = self.document(document_id)
        self.ensure_editable(doc, body.expected_version)
        confirmed = body.confirmed if confirmed is None else confirmed
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
            start, end = f'{item.period_start.year:04d}-{item.period_start.month:02d}', f'{item.period_end.year:04d}-{item.period_end.month:02d}'
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
        doc.confirmed = confirmed
        for item in body.activities:
            values = item.model_dump(exclude={'id', 'revision', 'confirmed_by', 'confirmed_at'})
            self.db.add(Activity(company_id=doc.company_id, document_id=doc.id, revision=doc.activity_revision,
                **values, confirmed_by=self.actor if confirmed else '', confirmed_at=utcnow() if confirmed else None))
        self.invalidate([doc.period, old_period or doc.period], doc.id)
        self.log('activity_confirmed' if confirmed else 'activity_draft_saved', doc.id,
                 f'Revision {doc.activity_revision}: {len(body.activities)} quantities; confirmed={confirmed}.', doc.period)
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
            if self.document(identifier).archived_at:
                raise HTTPException(409, 'Archived documents cannot be used as new declaration evidence.')
        previous = self.db.scalar(select(Declaration).where(Declaration.company_id == self.settings.company_id,
            Declaration.code == code, Declaration.period == body.period).order_by(Declaration.version.desc()))
        declaration = Declaration(company_id=self.settings.company_id, code=code, period=body.period,
            version=(previous.version if previous else 0) + 1, answer=body.answer, evidence_ids=evidence,
            complete=complete, declared_by=self.actor)
        self.db.add(declaration)
        self.invalidate([body.period])
        self.log('declaration_saved', code, f'Owner declaration version {declaration.version}; complete={complete}.', body.period)
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
            profile = self.profile(request.period)
        if questions is None:
            questions = self.db.scalars(select(Question).where(
                Question.questionnaire_id == request.id).order_by(Question.position))
        question_rows = [row(q) for q in questions]
        # Integrate offline evidence-readiness checks into the EXISTING question
        # response. Do not persist warnings or change calculated answers/reviews.
        needs_evidence = any(q['reviewed'] and not q.get('manual_answer') and
                             set(q.get('codes') or ()).intersection(
                                 {'E1.1', 'E1.2', 'E2.1', 'E3.1', 'E4.1'}) for q in question_rows)
        observations = []
        if needs_evidence:
            from .ai_evidence import normalize_confirmed_activities
            documents = self.documents(request.period, include_history=False)
            document_ids = [d['id'] for d in documents]
            if document_ids:
                hashes = dict(self.db.execute(select(Document.id, Document.file_hash).where(
                    Document.company_id == self.settings.company_id,
                    Document.id.in_(document_ids))).all())
                for doc in documents:
                    doc['file_hash'] = hashes.get(doc['id'], '')
            observations = normalize_confirmed_activities(documents, self.settings.company_id)
        results = []
        for question in question_rows:
            answer = answer_question(question, profile)
            if needs_evidence:
                from .ai_evidence import existing_question_coverage
                advisory = existing_question_coverage(
                    question, observations, self.settings.company_id, request.period)
                if advisory:
                    answer['uncertainty'] = ((answer.get('uncertainty') or '').strip() + ' ' + advisory).strip()
            if question['reviewed'] and not question.get('manual_answer'):
                from .ai_calculation import existing_calculation_provenance
                factor_advisory = existing_calculation_provenance(profile, question.get('codes'))
                if factor_advisory:
                    answer['uncertainty'] = ((answer.get('uncertainty') or '').strip() + ' ' + factor_advisory).strip()
            results.append(safe(answer))
        return {**row(request), 'questions': results}

    def requests(self, period='2026-09'):
        self.period(period)
        requests = list(self.db.scalars(select(Questionnaire).where(
            Questionnaire.company_id == self.settings.company_id, Questionnaire.period == period).order_by(Questionnaire.created_at)))
        if not requests:
            return []
        profile = self.profile(period)
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
        self.log('questionnaire_created', request.id, f'{body.customer}: {len(body.questions)} questions.', request.period)
        self.db.flush()
        result = self.serialize_request(request)
        self.db.commit()
        return result

    def map_request(self, identifier):
        self.company(lock=True)
        request = self.questionnaire(identifier)
        for question in self.db.scalars(select(Question).where(Question.questionnaire_id == request.id)):
            from .ai_mapping import suggest_reviewed_codes
            mapping = suggest_reviewed_codes(question.id, question.text)
            proposed = mapping['codes']
            question.proposed_codes = proposed
            question.codes = []
            question.reviewed = False
            question.confidence = mapping['confidence']
            question.rationale = mapping['rationale']
            question.uncertainty = mapping['uncertainty']
            question.version += 1
        request.status = 'draft'
        request.version += 1
        self.log('mapping_proposed', request.id, 'Offline EN/BM SEDG rules and legacy Social/Governance suggestions prepared; human review required.', request.period)
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
            'period': self.questionnaire(question.questionnaire_id).period} if body.manual_answer else None)
        question.reviewed_by = self.actor if body.reviewed else ''
        question.reviewed_at = utcnow() if body.reviewed else None
        question.version += 1
        request = self.questionnaire(question.questionnaire_id)
        request.version += 1
        request.status = 'draft'
        self.log('mapping_reviewed', identifier, f'Version {question.version}: {old_codes} → {question.codes}; reviewed={body.reviewed}.', request.period)
        self.db.flush()
        result = safe(answer_question(row(question), self.profile(request.period)))
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
        self.log('ready_for_owner', identifier, 'Prepared answers sent to owner; nothing was shared externally.', request.period)
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
        selected_docs = [self.document(identifier) for identifier in selected]
        if any(doc.archived_at for doc in selected_docs):
            raise HTTPException(409, 'Archived documents cannot be selected for a new approval.')
        evidence = self.serialize_documents(selected_docs, include_path=True)
        # Existing Approve & Share now requires explicit PR #9 gap decisions.
        # No additional endpoint: first POST returns a deterministic review
        # challenge, the owner confirms each gap, and retries this same POST.
        from .ai_evidence import (normalize_confirmed_activities,
            prepare_pr9_at_owner_approval, pr9_acknowledgement_items)
        from ai.workflow.forms import fingerprint
        from ai.workflow.outcome import approve_outcome, export_preparation
        selected_observations = normalize_confirmed_activities(evidence, self.settings.company_id)
        preparation_reviews = []
        prepared_at = safe(utcnow())
        for question in prepared['questions']:
            review = prepare_pr9_at_owner_approval(
                question, selected_observations, self.settings.company_id,
                request.period, self.actor, prepared_at)
            if review is not None:
                preparation_reviews.append(review)
        question_text_by_id = {q['id']: q['text'] for q in prepared['questions']}
        required_issues = [
            {**item, 'question_text': question_text_by_id.get(item['question_id'], '')}
            for item in pr9_acknowledgement_items(preparation_reviews)]
        challenge = fingerprint({'request_id': request.id, 'version': request.version,
            'period': request.period, 'recipient': body.recipient,
            'selected_evidence_ids': sorted(selected),
            'evidence_versions': sorted((d.id, d.version, d.file_hash,
                                         d.activity_revision) for d in selected_docs),
            'question_reviews': [
                (q['id'], q.get('version'), q.get('reviewed_at'), q.get('codes'))
                for q in prepared['questions']],
            'required_issues': required_issues})
        supplied = body.acknowledged_issues
        required_ids = {item['id'] for item in required_issues}
        if required_ids and (
                body.pr9_review_hash != challenge or
                set(supplied) != required_ids or len(supplied) != len(required_ids) or
                len(body.pr9_review_reason.strip()) < 10):
            raise HTTPException(409, {
                'message': 'Review and acknowledge every outstanding PR #9 issue before sharing.',
                'pr9_review': {'hash': challenge, 'items': required_issues}})
        if not required_ids and (supplied or body.pr9_review_hash):
            raise HTTPException(409, 'Review details have changed; refresh the request.')
        # Stage 4 acceptance always uses the genuine owner's decision, never
        # fabricated consent. Acknowledgements are bound to selected evidence.
        private_exports = []
        for review in preparation_reviews:
            outcome = review.pop('_outcome', None)
            if outcome is None:
                continue  # Unsupported/mismatched form remains manual review.
            accepted_requirements = sorted({req['requirement_id'] for req in review['requirements']
                                            if req['issues']})
            completed = approve_outcome(outcome, reviewer=self.actor,
                reason=body.pr9_review_reason.strip() or 'No unresolved gaps in approved preparation',
                at=prepared_at, acknowledged_requirements=accepted_requirements)
            validated_export = export_preparation(completed)
            private_exports.append({'question_id': review['question_id'],
                                    'approved_preparation': json.loads(validated_export)})
            review['status'] = 'preparation_approved_with_gaps' if accepted_requirements else 'preparation_approved'
            review['acknowledged_requirement_ids'] = accepted_requirements
        owner_review = {'reviewer': self.actor, 'at': prepared_at,
            'reason': body.pr9_review_reason.strip(),
            'challenge_hash': challenge, 'acknowledged_issues': sorted(required_ids)}
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
        # Keep statuses/gaps only. Missing PR #9 consent never becomes approved.
        if preparation_reviews:
            snapshot['pr9_preparation_review'] = preparation_reviews
            snapshot['pr9_owner_review'] = owner_review
            # Full PR #9 audit/exports stay private in the immutable DB
            # snapshot, NOT exposed through customer share-token responses.
            snapshot['pr9_private_preparations'] = private_exports
        # PR #9 snapshot fingerprint protects preparation state against subsequent
        # accidental changes. It is an integrity check, not a digital signature.
        from ai.workflow.forms import fingerprint
        snapshot = safe(snapshot)
        snapshot['preparation_snapshot_sha256'] = fingerprint(snapshot)
        pack = ApprovedSnapshot(company_id=self.settings.company_id, questionnaire_id=request.id,
            token=secrets.token_urlsafe(32), recipient=body.recipient, approved_by=self.actor,
            created_at=created, snapshot=safe(snapshot))
        self.db.add(pack)
        request.status = 'shared'
        request.version += 1
        self.log('pack_approved', identifier, f'Immutable snapshot approved for {body.recipient}; {len(selected)} attachments.', request.period)
        self.db.flush()
        result = self.serialize_pack(pack)
        self.db.commit()
        return result

    @staticmethod
    def serialize_pack(pack):
        output = row(pack)
        # Older packs have no digest; keep them readable without falsely claiming
        # they received the new protection.
        saved = output['snapshot']
        digest = saved.get('preparation_snapshot_sha256')
        if digest:
            from ai.workflow.forms import fingerprint
            body = {key: value for key, value in saved.items()
                    if key != 'preparation_snapshot_sha256'}
            if fingerprint(body) != digest:
                raise HTTPException(409, 'Approved snapshot integrity check failed.')
        # Never expose private object paths or hashes; customer evidence goes through token routes.
        output['snapshot'].pop('pr9_private_preparations', None)
        output['snapshot'].pop('pr9_owner_review', None)
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
        # Guard the existing evidence-download route too.
        saved = pack.snapshot
        digest = saved.get('preparation_snapshot_sha256')
        if digest:
            from ai.workflow.forms import fingerprint
            if fingerprint({key: value for key, value in saved.items()
                            if key != 'preparation_snapshot_sha256'}) != digest:
                raise HTTPException(409, 'Approved snapshot integrity check failed.')
        return pack

    def get_pack(self, token):
        pack = self.pack(token)
        result = self.serialize_pack(pack)
        self.log('customer_pack_viewed', pack.id, 'Approved pack opened using its share token.', pack.snapshot.get('period'))
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
