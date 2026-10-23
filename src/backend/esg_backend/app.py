"""Local hackathon API. Simulated roles are not production authentication."""
from contextlib import asynccontextmanager
from secrets import compare_digest
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from .config import Settings
from .db import build_engine, make_session_factory
from .models import ActivityEvent, ApprovedSnapshot
from .schemas import ActivitiesInput, ApprovalInput, DeclarationInput, HandoffInput, QuestionnaireInput, RecalculateInput, ReviewInput, Period, DocumentUpdateInput, DocumentVersionInput
from .service import MAX_FILE, Workspace, row
from .storage import StorageError, SupabaseStorage


def create_app(*, settings=None, session_factory=None, storage=None):
    settings = settings or Settings.from_env()
    settings.validate_demo_access()
    configuration_error = None
    engine = None
    if session_factory is None:
        try:
            settings.validate()
            engine = build_engine(settings.database_url)
            session_factory = make_session_factory(engine)
        except ValueError as error:
            configuration_error = str(error)
    owned_storage = storage is None
    if storage is None and not configuration_error:
        storage = SupabaseStorage(settings.supabase_url, settings.supabase_server_key, settings.storage_bucket)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if engine:
            engine.dispose()
        if owned_storage and storage is not None:
            storage.client.close()

    api = FastAPI(title='ESG Passport API', version='1.0.0', lifespan=lifespan)
    api.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin],
                       allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type', 'X-Demo-Role'])
    api.state.settings = settings

    @api.middleware('http')
    async def demo_access(request, call_next):
        if settings.demo_access_enabled and not (request.method == 'GET' and request.url.path == '/health'):
            supplied = request.headers.get('x-demo-backend-key', '')
            if not compare_digest(supplied.encode('utf-8'), settings.backend_shared_key.encode('utf-8')):
                return JSONResponse(status_code=401, content={'detail': 'Demo access required.'},
                                    headers={'Cache-Control': 'no-store'})
        response = await call_next(request)
        if settings.demo_access_enabled:
            response.headers['Cache-Control'] = 'private, no-store'
        return response

    def session():
        if configuration_error or session_factory is None:
            raise HTTPException(503, configuration_error or 'Backend storage is not configured.')
        with session_factory() as db:
            try:
                yield db
            finally:
                db.rollback()

    def role(x_demo_role: str | None = Header(default=None)):
        if x_demo_role is None:
            raise HTTPException(401, 'Select a simulated Owner or Admin clerk role.')
        if x_demo_role not in ('owner', 'clerk'):
            raise HTTPException(403, 'This action requires the Owner or Admin clerk role.')
        return x_demo_role

    def workspace(db=Depends(session), actor_role=Depends(role)):
        return Workspace(db, storage, settings, actor_role)

    def customer_workspace(db=Depends(session)):
        return Workspace(db, storage, settings, 'customer')

    @api.exception_handler(SQLAlchemyError)
    def database_error(request, error):
        return JSONResponse(status_code=503, content={'detail': 'Database unavailable. Check the backend connection and run its migrations.'})

    @api.exception_handler(StorageError)
    def storage_error(request, error):
        return JSONResponse(status_code=503, content={'detail': 'Evidence storage unavailable. Check the private bucket and backend Supabase settings.'})

    @api.get('/health')
    def health():
        if configuration_error:
            detail = 'Backend configuration unavailable.' if settings.demo_access_enabled else configuration_error
            return JSONResponse(status_code=503, content={'status': 'not_configured', 'detail': detail})
        try:
            with session_factory() as db:
                db.execute(text('SELECT 1'))
            return {'status': 'ok', 'synthetic_only': True, 'ai_enabled': True,
                    'ai_mode': 'offline_deterministic', 'ocr_enabled': True}
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={'status': 'unavailable', 'detail': 'Cannot connect to Supabase Postgres.'})

    @api.get('/profile')
    def profile(period: Period = '2026-09', work=Depends(workspace)):
        return work.profile(period)

    @api.post('/profile/recalculate')
    def recalculate(body: RecalculateInput, work=Depends(workspace)):
        work.company(lock=True)
        work.period(body.period)
        result = work.profile(body.period)
        work.log('profile_calculated', body.period, 'Calculated from confirmed records and versioned factors.', body.period)
        work.db.commit()
        return result

    @api.get('/documents')
    def documents(period: Period = '2026-09', archived: bool = False, work=Depends(workspace)):
        work.company()
        return work.documents(period, archived=archived)

    @api.post('/documents', status_code=201)
    def upload(file: UploadFile = File(), type: str = Form(), period: Period = Form('2026-09'), work=Depends(workspace)):
        content = file.file.read(MAX_FILE + 1)
        precomputed = None
        if settings.sandbox_instance:
            from .public_sandbox import validate_synthetic_upload, fixture_extraction
            validate_synthetic_upload(content, type, period)
            precomputed = fixture_extraction(content)
        return work.upload(file.filename, type, content, file.content_type, period,
                           precomputed_extraction=precomputed)

    @api.get('/documents/{document_id}')
    def document(document_id: str, work=Depends(workspace)):
        return work.serialize_document(work.document(document_id))

    def file_response(result):
        content, mime, name = result
        return Response(content=content, media_type=mime, headers={
            'Content-Disposition': f"inline; filename*=UTF-8''{quote(name, safe='')}",
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})

    @api.post('/documents/{document_id}/ocr/retry')
    def retry_document_ocr(document_id: str, body: DocumentVersionInput, work=Depends(workspace)):
        return work.retry_ocr(document_id, body)

    @api.get('/documents/{document_id}/file')
    def document_file(document_id: str, work=Depends(workspace)):
        return file_response(work.file(document_id))

    @api.put('/documents/{document_id}')
    def update_document(document_id: str, body: DocumentUpdateInput, work=Depends(workspace)):
        return work.update_document(document_id, body)

    @api.delete('/documents/{document_id}')
    def delete_document(document_id: str, body: DocumentVersionInput, work=Depends(workspace)):
        return work.delete_document(document_id, body)

    @api.post('/documents/{document_id}/archive')
    def archive_document(document_id: str, body: DocumentVersionInput, work=Depends(workspace)):
        return work.archive_document(document_id, body)

    @api.post('/documents/{document_id}/restore')
    def restore_document(document_id: str, body: DocumentVersionInput, work=Depends(workspace)):
        return work.archive_document(document_id, body, restore=True)

    @api.put('/documents/{document_id}/activities')
    def activities(document_id: str, body: ActivitiesInput, work=Depends(workspace)):
        return work.save_activities(document_id, body)

    @api.get('/declarations')
    def declarations(period: Period = '2026-09', work=Depends(workspace)):
        return work.declarations(period)

    @api.put('/declarations/{code}')
    def declaration(code: str, body: DeclarationInput, work=Depends(workspace)):
        return work.save_declaration(code, body)

    @api.get('/questionnaires')
    def requests(period: Period = '2026-09', work=Depends(workspace)):
        return work.requests(period)

    @api.post('/questionnaires', status_code=201)
    def create_request(body: QuestionnaireInput, work=Depends(workspace)):
        return work.create_request(body)

    @api.get('/questionnaires/{identifier}')
    def request(identifier: str, work=Depends(workspace)):
        return work.serialize_request(work.questionnaire(identifier))

    @api.post('/questionnaires/{identifier}/map')
    def map_request(identifier: str, work=Depends(workspace)):
        return work.map_request(identifier)

    @api.put('/questions/{identifier}/review')
    def review(identifier: str, body: ReviewInput, work=Depends(workspace)):
        return work.review_question(identifier, body)

    @api.put('/questionnaires/{identifier}')
    def handoff(identifier: str, body: HandoffInput, work=Depends(workspace)):
        return work.handoff(identifier)

    @api.post('/questionnaires/{identifier}/approve-share')
    def approve(identifier: str, body: ApprovalInput, work=Depends(workspace)):
        return work.approve(identifier, body)

    @api.get('/shares')
    def shares(period: Period = '2026-09', work=Depends(workspace)):
        work.require_owner()
        return [work.serialize_pack(pack) for pack in work.db.scalars(select(ApprovedSnapshot).where(
            ApprovedSnapshot.company_id == settings.company_id).order_by(ApprovedSnapshot.created_at.desc()))
            if pack.snapshot.get('period') == period]

    @api.get('/shares/{token}')
    def share(token: str, work=Depends(customer_workspace)):
        return work.get_pack(token)

    @api.get('/shares/{token}/evidence/{document_id}')
    def shared_file(token: str, document_id: str, work=Depends(customer_workspace)):
        return file_response(work.file(document_id, token))

    @api.get('/activity-log')
    def activity_log(work=Depends(workspace)):
        return [row(event) for event in work.db.scalars(select(ActivityEvent).where(
            ActivityEvent.company_id == settings.company_id).order_by(ActivityEvent.time.desc()))]

    @api.post('/demo/reset')
    def reset(work=Depends(workspace)):
        return work.reset()

    if settings.public_workspace_enabled:
        # No anonymous request reaches real Supabase storage or sessions.
        from .public_sandbox import make_public_app
        api.mount('/sandbox',make_public_app(settings),name='public-synthetic-sandbox')

    return api


app = create_app()
