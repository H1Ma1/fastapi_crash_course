from sqlalchemy import select

from database import new_session, TaskTable
from schemas import STask, StaskAdd


class TaskRepository:
    @classmethod
    async def add_one(cls, data: StaskAdd) -> int:
        async with new_session() as session:
            task_dict = data.model_dump()

            task = TaskTable(**task_dict)
            session.add(task)

            await session.flush()
            await session.commit()

            return task.id

    @classmethod
    async def find_all(cls) -> list[STask]:
        async with new_session() as session:
            query = select(TaskTable)
            result = await session.execute(query)
            task_models = result.scalars().all()

            task_schemas = [
                STask.model_validate(task_model)
                for task_model in task_models
            ]

            return task_schemas

    @classmethod
    async def delete_one(cls, task_id: int) -> bool:
        async with new_session() as session:
            task = await session.get(TaskTable, task_id)

            if task is None:
                return False

            await session.delete(task)
            await session.commit()

            return True