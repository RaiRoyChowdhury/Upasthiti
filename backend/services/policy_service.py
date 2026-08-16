from database.models.policy_model import PolicyPublic, PolicyUpdate
from database.repositories.policy_repository import PolicyRepository


class PolicyService:
    def __init__(self, repo: PolicyRepository):
        self._repo = repo

    async def get_policy(self) -> PolicyPublic:
        doc = await self._repo.get_or_create()
        return PolicyPublic.from_db(doc)

    async def update_policy(self, updates: PolicyUpdate, actor_id: str) -> PolicyPublic:
        doc = await self._repo.update(updates.model_dump(exclude_unset=True), updated_by=actor_id)
        return PolicyPublic.from_db(doc)
