import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Settings:
    app_env: str
    auth_mode: str
    enable_test_auth: bool
    dev_test_secret: str
    database_url: str
    cors_origins: List[str]

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

