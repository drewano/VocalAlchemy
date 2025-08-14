from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.infrastructure.repositories.base_repository import BaseRepository
from src.infrastructure import sql_models as models
from src.api import schemas


class PromptFlowRepository(BaseRepository):
    async def _get_with_steps(self, flow_id: str) -> Optional[models.PromptFlow]:
        """Private method to fetch a PromptFlow with its steps loaded."""
        result = await self.db.execute(
            select(models.PromptFlow)
            .options(joinedload(models.PromptFlow.steps))
            .where(models.PromptFlow.id == flow_id)
        )
        return result.unique().scalar_one_or_none()

    async def create(
        self, user_id: int, data: schemas.PromptFlowCreate
    ) -> models.PromptFlow:
        flow = models.PromptFlow(
            name=data.name,
            description=data.description,
            user_id=user_id,
        )
        # Attach steps preserving provided order
        flow.steps = [
            models.PromptStep(
                name=step.name,
                content=step.content,
                step_order=step.step_order,
            )
            for step in data.steps
        ]
        self.db.add(flow)
        await self.db.commit()
        await self.db.refresh(flow)
        # Eager load steps after refresh for consistent response
        return await self._get_with_steps(flow.id)

    async def list_by_user(self, user_id: int) -> List[models.PromptFlow]:
        result = await self.db.execute(
            select(models.PromptFlow)
            .options(joinedload(models.PromptFlow.steps))
            .where(models.PromptFlow.user_id == user_id)
            .order_by(models.PromptFlow.name.asc())
        )
        return result.unique().scalars().all()

    async def get_by_id(self, flow_id: str) -> Optional[models.PromptFlow]:
        return await self._get_with_steps(flow_id)

    async def update(
        self, flow: models.PromptFlow, data: schemas.PromptFlowUpdate
    ) -> models.PromptFlow:
        if data.name is not None:
            flow.name = data.name
        if data.description is not None:
            flow.description = data.description

        if data.steps is not None:
            # Replace all steps (simplest reliable approach for reordering and add/remove)
            flow.steps.clear()
            for step in data.steps:
                flow.steps.append(
                    models.PromptStep(
                        name=step.name,
                        content=step.content,
                        step_order=step.step_order,
                    )
                )

        await self.db.commit()
        await self.db.refresh(flow)
        # Reload with steps
        return await self._get_with_steps(flow.id)

    async def delete(self, flow: models.PromptFlow) -> None:
        await self.db.delete(flow)
        await self.db.commit()
