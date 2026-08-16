from fastapi import APIRouter, Depends

from api.dependencies.auth_dependency import get_current_user, require_role
from api.dependencies.service_dependencies import get_policy_service, get_retention_service
from database.models.policy_model import PolicyPublic, PolicyUpdate
from database.models.user_model import UserPublic, UserRole
from services.policy_service import PolicyService
from services.retention_service import RetentionService

router = APIRouter(prefix="/api/policy", tags=["Policy"])


@router.get("", response_model=PolicyPublic)
async def get_policy(
    service: PolicyService = Depends(get_policy_service),
    _user: UserPublic = Depends(get_current_user),
):
    return await service.get_policy()


@router.put("", response_model=PolicyPublic)
async def update_policy(
    payload: PolicyUpdate,
    service: PolicyService = Depends(get_policy_service),
    user: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    return await service.update_policy(payload, actor_id=user.id)


@router.post("/run-retention-now")
async def run_retention_now(
    service: RetentionService = Depends(get_retention_service),
    _admin: UserPublic = Depends(require_role(UserRole.ADMIN)),
):
    """
    Manual trigger for testing the retention job without waiting for the
    scheduled background interval (see docs/retention.md). Subject to the
    exact same dual-gate check as the scheduled run — this does NOT
    bypass retention_enforcement_enabled.
    """
    return await service.run_purge_cycle()
