from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DevSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(pattern=r"^test-agent-(?:00[1-9]|01[0-9]|020)$")


class DevSessionResponse(BaseModel):
    user_id: str
    display_name: str
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class EntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    course_version: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9._-]+$")


class ModuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    status: Literal["not_started", "in_progress", "completed"]
    score: int | None = Field(default=None, ge=0, le=100)
    attempts: int = Field(default=0, ge=0, le=10000)
    required_resources_opened: bool = False
    resource_types: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("resource_types")
    @classmethod
    def validate_resource_types(cls, values):
        cleaned = [value.strip()[:40] for value in values if value.strip()]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("resource_types no puede contener duplicados")
        return cleaned


class ProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    course_version: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9._-]+$")
    status: Literal["in_progress", "completed"]
    modules: list[ModuleUpdate] = Field(default_factory=list, max_length=20)

    @field_validator("modules")
    @classmethod
    def validate_unique_modules(cls, modules):
        module_ids = [module.module_id for module in modules]
        if len(module_ids) != len(set(module_ids)):
            raise ValueError("modules no puede contener module_id duplicados")
        return modules


class ModuleProgressResponse(ModuleUpdate):
    updated_at: str


class ProgressResponse(BaseModel):
    course_id: str
    course_version: str
    status: str
    first_entry_at: str
    last_activity_at: str
    completed_at: str | None
    modules: list[ModuleProgressResponse]
