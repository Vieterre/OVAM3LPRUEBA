import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class LearnerProgress(Base):
    __tablename__ = "learner_progress"
    __table_args__ = (
        UniqueConstraint("subject_id", "course_id", "course_version", name="uq_learner_course_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    course_id: Mapped[str] = mapped_column(String(64), nullable=False)
    course_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    first_entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    modules: Mapped[list["ModuleProgress"]] = relationship(
        back_populates="learner_progress", cascade="all, delete-orphan"
    )


class ModuleProgress(Base):
    __tablename__ = "module_progress"
    __table_args__ = (
        UniqueConstraint("learner_progress_id", "module_id", name="uq_progress_module"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    learner_progress_id: Mapped[str] = mapped_column(
        ForeignKey("learner_progress.id", ondelete="CASCADE"), index=True, nullable=False
    )
    module_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    required_resources_opened: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resource_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    learner_progress: Mapped[LearnerProgress] = relationship(back_populates="modules")


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_key: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    source_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    chunks: Mapped[list["RagChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class RagChunk(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_rag_document_chunk"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        ForeignKey("rag_documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    locator: Mapped[str] = mapped_column(String(128), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    document: Mapped[RagDocument] = relationship(back_populates="chunks")


class RagChatEvent(Base):
    __tablename__ = "rag_chat_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    question: Mapped[str] = mapped_column(String(1200), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
