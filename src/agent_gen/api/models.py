"""Pydantic models for the AgentFactory API."""
from __future__ import annotations

from pydantic import BaseModel


class User(BaseModel):
    id: str
    github_id: int
    github_handle: str
    email: str
    avatar_url: str
    plan: str  # free | pro | team | enterprise


class ValidateRequest(BaseModel):
    key: str
    tier: str


class ValidateResponse(BaseModel):
    valid: bool
    tier: str | None = None


class RegistrySummary(BaseModel):
    name: str
    description: str
    tags: list[str] = []
    latest_version: str | None = None
    updated_at: str


class RegistryEntry(BaseModel):
    name: str
    description: str
    tags: list[str] = []
    owner: str
    version: str
    versions: list[str]
    sha256: str
    size_bytes: int
    published_at: str
    zip_url: str


class DeviceCodeResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: float


class DevicePollRequest(BaseModel):
    device_code: str


class DevicePollResponse(BaseModel):
    status: str  # pending | authorized | expired
    token: str | None = None
    user: User | None = None


class DeviceApproveRequest(BaseModel):
    user_code: str
