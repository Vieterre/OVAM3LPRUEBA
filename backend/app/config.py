import os
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Settings:
    app_env: str
    auth_mode: str
    enable_test_auth: bool
    dev_test_secret: str
    database_url: str
    cors_origins: List[str]
    rag_enabled: bool = True
    rag_source_paths: List[str] = field(default_factory=lambda: ["rag_sources"])
    rag_chunk_chars: int = 1200
    rag_chunk_overlap: int = 180
    rag_embedding_dimensions: int = 256
    rag_top_k: int = 4
    rag_max_question_chars: int = 500

    @classmethod
    def from_environment(cls):
        cors_origins = [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "").split(",")
            if origin.strip()
        ]
        return cls(
            app_env=os.getenv("APP_ENV", "development").strip().lower(),
            auth_mode=os.getenv("AUTH_MODE", "mock").strip().lower(),
            enable_test_auth=os.getenv("ENABLE_TEST_AUTH", "false").strip().lower()
            in {"1", "true", "yes"},
            dev_test_secret=os.getenv("DEV_TEST_SECRET", ""),
            database_url=os.getenv(
                "DATABASE_URL", "sqlite:///./ova-dev.db"
            ).strip(),
            cors_origins=cors_origins,
            rag_enabled=os.getenv("RAG_ENABLED", "true").strip().lower()
            in {"1", "true", "yes"},
            rag_source_paths=[
                path.strip()
                for path in os.getenv("RAG_SOURCE_PATHS", "rag_sources").split(",")
                if path.strip()
            ],
            rag_chunk_chars=int(os.getenv("RAG_CHUNK_CHARS", "1200")),
            rag_chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "180")),
            rag_embedding_dimensions=int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "256")),
            rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
            rag_max_question_chars=int(os.getenv("RAG_MAX_QUESTION_CHARS", "500")),
        )

    def validate(self):
        if self.app_env not in {"development", "test", "production"}:
            raise RuntimeError("APP_ENV debe ser development, test o production")
        if self.auth_mode not in {"mock", "institutional"}:
            raise RuntimeError("AUTH_MODE debe ser mock o institutional")
        if self.app_env == "production" and self.auth_mode == "mock":
            raise RuntimeError("El modo de autenticación ficticia no se permite en producción")
        if self.auth_mode == "institutional":
            raise RuntimeError(
                "La autenticación institucional aún no está implementada; requiere especificaciones de TIC"
            )
        if self.enable_test_auth and self.app_env != "development":
            raise RuntimeError("ENABLE_TEST_AUTH solo se permite en desarrollo")
        if self.enable_test_auth and len(self.dev_test_secret) < 32:
            raise RuntimeError("DEV_TEST_SECRET debe tener al menos 32 caracteres")
        if not 400 <= self.rag_chunk_chars <= 4000:
            raise RuntimeError("RAG_CHUNK_CHARS debe estar entre 400 y 4000")
        if not 0 <= self.rag_chunk_overlap < self.rag_chunk_chars:
            raise RuntimeError("RAG_CHUNK_OVERLAP debe ser menor que RAG_CHUNK_CHARS")
        if not 64 <= self.rag_embedding_dimensions <= 2048:
            raise RuntimeError("RAG_EMBEDDING_DIMENSIONS debe estar entre 64 y 2048")
        if not 1 <= self.rag_top_k <= 8:
            raise RuntimeError("RAG_TOP_K debe estar entre 1 y 8")
        if not 100 <= self.rag_max_question_chars <= 1200:
            raise RuntimeError("RAG_MAX_QUESTION_CHARS debe estar entre 100 y 1200")

