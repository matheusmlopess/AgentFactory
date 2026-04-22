"""
POST /v1/validate — server-side license key validation.
Called by .ai/scripts/skill-completeness-check.py require_plan().
"""
from fastapi import APIRouter

from ..models import ValidateRequest, ValidateResponse

router = APIRouter(prefix="/v1", tags=["license"])

_PLAN_RANK = {"free": 0, "pro": 1, "team": 2, "enterprise": 3}


@router.post("/validate", response_model=ValidateResponse)
def validate_license(req: ValidateRequest) -> ValidateResponse:
    """
    Validate a license key against a minimum plan tier.

    Keys are formatted as: <plan>_<random>
    Example: pro_abc123...

    In production, replace this with a real key lookup in the users table
    or a dedicated license_keys table with hashed keys.
    """
    # Extract plan from key prefix (format: plan_<token>)
    parts = req.key.split("_", 1)
    if len(parts) != 2 or parts[0] not in _PLAN_RANK:
        return ValidateResponse(valid=False)

    key_plan = parts[0]
    required_rank = _PLAN_RANK.get(req.tier, 999)
    if _PLAN_RANK[key_plan] >= required_rank:
        return ValidateResponse(valid=True, tier=key_plan)
    return ValidateResponse(valid=False)
