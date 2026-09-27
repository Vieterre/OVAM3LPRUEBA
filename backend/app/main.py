import hmac
from contextlib import asynccontextmanager
from datetime import timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from .auth import TEST_USERS, AuthenticatedUser, build_auth_dependency, issue_token
from .config import Settings
from .database import Base, build_engine, build_session_factory
from .models import LearnerProgress, ModuleProgress, utc_now
from .schemas import DevSessionRequest, DevSessionResponse, EntryRequest, ProgressResponse, ProgressUpdate


def _iso(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def create_app(settings=None, engine=None):
    settings = settings or Settings.from_environment()
    settings.validate()
    engine = engine or build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app):
        Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(
        title="Backend piloto de seguimiento OVA",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "PUT", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def get_db():
        with session_factory() as db:
            yield db

    current_user = build_auth_dependency(settings)

    @app.get("/healthz", tags=["health"])
    def healthz(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            raise HTTPException(status_code=503, detail="Base de datos no disponible")
        return {"status": "ok"}

    @app.post("/v1/dev/session", response_model=DevSessionResponse, tags=["development"])
    def create_dev_session(
        request: DevSessionRequest,
        x_dev_test_secret: str | None = Header(default=None),
    ):
        if not settings.enable_test_auth or settings.app_env != "development" or settings.auth_mode != "mock":
            raise HTTPException(status_code=404, detail="No encontrado")
        if not x_dev_test_secret or not hmac.compare_digest(
            x_dev_test_secret, settings.dev_test_secret
        ):
            raise HTTPException(status_code=401, detail="Credencial de prueba inválida")
        return DevSessionResponse(
            user_id=request.user_id,
            display_name=TEST_USERS[request.user_id],
            access_token=issue_token(request.user_id, settings.dev_test_secret),
            expires_in_seconds=8 * 60 * 60,
        )

    @app.post("/v1/me/entry", response_model=ProgressResponse, tags=["progress"])
    def record_entry(
        request: EntryRequest,
        user: AuthenticatedUser = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        now = utc_now()
        progress = db.scalar(
            select(LearnerProgress)
            .options(selectinload(LearnerProgress.modules))
            .where(
                LearnerProgress.subject_id == user.subject_id,
                LearnerProgress.course_id == request.course_id,
                LearnerProgress.course_version == request.course_version,
            )
        )
        if progress is None:
            progress = LearnerProgress(
                subject_id=user.subject_id,
                course_id=request.course_id,
                course_version=request.course_version,
                status="in_progress",
                first_entry_at=now,
                last_activity_at=now,
            )
            db.add(progress)
        else:
            progress.last_activity_at = now
        db.commit()
        db.refresh(progress)
        return _to_response(progress)

    @app.get("/v1/me/progress", response_model=ProgressResponse, tags=["progress"])
    def get_my_progress(
        course_id: str = Query(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
        course_version: str = Query(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9._-]+$"),
        user: AuthenticatedUser = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        progress = db.scalar(
            select(LearnerProgress)
            .options(selectinload(LearnerProgress.modules))
            .where(
                LearnerProgress.subject_id == user.subject_id,
                LearnerProgress.course_id == course_id,
                LearnerProgress.course_version == course_version,
            )
        )
        if progress is None:
            raise HTTPException(status_code=404, detail="Aún no hay avance guardado")
        return _to_response(progress)

    @app.put("/v1/me/progress", response_model=ProgressResponse, tags=["progress"])
    def save_my_progress(
        request: ProgressUpdate,
        user: AuthenticatedUser = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        now = utc_now()
        progress = db.scalar(
            select(LearnerProgress)
            .options(selectinload(LearnerProgress.modules))
            .where(
                LearnerProgress.subject_id == user.subject_id,
                LearnerProgress.course_id == request.course_id,
                LearnerProgress.course_version == request.course_version,
            )
        )
        if progress is None:
            progress = LearnerProgress(
                subject_id=user.subject_id,
                course_id=request.course_id,
                course_version=request.course_version,
                first_entry_at=now,
            )
            db.add(progress)
            db.flush()

        progress.status = request.status
        progress.last_activity_at = now
        progress.completed_at = now if request.status == "completed" else None
        modules_by_id = {module.module_id: module for module in progress.modules}
        for update in request.modules:
            module = modules_by_id.get(update.module_id)
            if module is None:
                module = ModuleProgress(module_id=update.module_id)
                progress.modules.append(module)
            module.status = update.status
            module.score = update.score
            module.attempts = update.attempts
            module.required_resources_opened = update.required_resources_opened
            module.resource_types = update.resource_types
            module.updated_at = now

        db.commit()
        db.refresh(progress)
        return _to_response(progress)

    return app


def _to_response(progress):
    return ProgressResponse(
        course_id=progress.course_id,
        course_version=progress.course_version,
        status=progress.status,
        first_entry_at=_iso(progress.first_entry_at),
        last_activity_at=_iso(progress.last_activity_at),
        completed_at=_iso(progress.completed_at),
        modules=[
            {
                "module_id": module.module_id,
                "status": module.status,
                "score": module.score,
                "attempts": module.attempts,
                "required_resources_opened": module.required_resources_opened,
                "resource_types": module.resource_types or [],
                "updated_at": _iso(module.updated_at),
            }
            for module in sorted(progress.modules, key=lambda item: item.module_id)
        ],
    )


app = create_app()
