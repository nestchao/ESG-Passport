"""Relational records for evidence provenance, declarations and approved snapshots."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uuidstr() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = 'companies'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    name: Mapped[str] = mapped_column(String(255), default='')
    location: Mapped[str] = mapped_column(String(255), default='')
    sector: Mapped[str] = mapped_column(String(255), default='')
    period: Mapped[str] = mapped_column(String(64), default='')
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Document(Base):
    __tablename__ = 'documents'
    __table_args__ = (UniqueConstraint('company_id', 'file_hash', name='uq_document_company_hash'),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(255), default='')
    type: Mapped[str] = mapped_column(String(64), default='other')
    period: Mapped[str] = mapped_column(String(64), default='')
    mime_type: Mapped[str] = mapped_column(String(128), default='application/octet-stream')
    file_hash: Mapped[str] = mapped_column(String(64))
    object_path: Mapped[str] = mapped_column(Text, unique=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    activity_revision: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    original_extraction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String(255), default='')
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Activity(Base):
    __tablename__ = 'activities'
    __table_args__ = (
        UniqueConstraint('document_id', 'revision', 'category', name='uq_activity_document_revision_category'),
        CheckConstraint('quantity >= 0', name='ck_activity_quantity_nonnegative'),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id', ondelete='CASCADE'), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(64), default='')
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 12), default=Decimal('0'))
    unit: Mapped[str] = mapped_column(String(64), default='')
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    allocated_period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assumptions: Mapped[str] = mapped_column(Text, default='')
    source_reference: Mapped[str] = mapped_column(Text, default='')
    confirmed_by: Mapped[str] = mapped_column(String(255), default='')
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Declaration(Base):
    __tablename__ = 'declarations'
    __table_args__ = (UniqueConstraint('company_id', 'code', 'period', 'version', name='uq_declaration_version'),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    code: Mapped[str] = mapped_column(String(32), default='')
    period: Mapped[str] = mapped_column(String(64), default='')
    version: Mapped[int] = mapped_column(Integer, default=1)
    answer: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    declared_by: Mapped[str] = mapped_column(String(255), default='')
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FactorVersion(Base):
    __tablename__ = 'factor_versions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    key: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), default='')
    value: Mapped[Decimal] = mapped_column(Numeric(30, 15), default=Decimal('0'))
    unit: Mapped[str] = mapped_column(String(128), default='')
    year: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(64), default='1')
    source: Mapped[str] = mapped_column(Text, default='')
    assumptions: Mapped[str] = mapped_column(Text, default='')
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)


class Questionnaire(Base):
    __tablename__ = 'questionnaires'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    customer: Mapped[str] = mapped_column(String(255), default='')
    period: Mapped[str] = mapped_column(String(64), default='')
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='draft')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Question(Base):
    __tablename__ = 'questions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    questionnaire_id: Mapped[str] = mapped_column(ForeignKey('questionnaires.id', ondelete='CASCADE'), index=True)
    text: Mapped[str] = mapped_column(Text, default='')
    codes: Mapped[list] = mapped_column(JSON, default=list)
    proposed_codes: Mapped[list] = mapped_column(JSON, default=list)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_declaration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(255), default='')
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default='')
    uncertainty: Mapped[str] = mapped_column(Text, default='')
    confidence: Mapped[str] = mapped_column(String(32), default='Medium')
    version: Mapped[int] = mapped_column(Integer, default=1)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ApprovedSnapshot(Base):
    __tablename__ = 'approved_snapshots'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    questionnaire_id: Mapped[str] = mapped_column(ForeignKey('questionnaires.id', ondelete='CASCADE'), index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True)
    recipient: Mapped[str] = mapped_column(String(255), default='')
    approved_by: Mapped[str] = mapped_column(String(255), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class ActivityEvent(Base):
    __tablename__ = 'activity_events'
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuidstr)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id', ondelete='CASCADE'), index=True)
    actor: Mapped[str] = mapped_column(String(255), default='')
    role: Mapped[str] = mapped_column(String(64), default='')
    action: Mapped[str] = mapped_column(String(128), default='')
    target: Mapped[str] = mapped_column(String(255), default='')
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    summary: Mapped[str] = mapped_column(Text, default='')
