"""
POST /v1/validate — server-side license key validation.
Called by .ai/scripts/skill-completeness-check.py require_plan().

Keys are random strings issued with `agentfactory-api keys add --plan <plan>`; only their
sha256 hash is stored (license_keys table). The key text itself carries no plan.
"""
from fastapi import APIRouter

from ..db import PLAN_RANK, license_plan
from ..models import ValidateRequest, ValidateResponse

router = APIRouter(prefix="/v1", tags=["license"])


@router.post("/validate", response_model=ValidateResponse)
def validate_license(req: ValidateRequest) -> ValidateResponse:
    """Valid when the key is active and its plan is at least the requested tier."""
    required_rank = PLAN_RANK.get(req.tier)
    if required_rank is None or not req.key:
        return ValidateResponse(valid=False)
    plan = license_plan(req.key)
    if plan is not None and PLAN_RANK.get(plan, -1) >= required_rank:
        return ValidateResponse(valid=True, tier=plan)
    return ValidateResponse(valid=False)
