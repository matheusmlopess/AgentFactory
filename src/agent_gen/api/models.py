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
