from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated

from repository import TaskRepository
from schemas import StaskAdd, STask


router = APIRouter(
    prefix="/tasks",
)


@router.post("")
async def add_task(
    task: Annotated[StaskAdd, Depends()],
):
    task_id = await TaskRepository.add_one(task)
    return {"ok": True, "task_id": task_id}


@router.get("")
async def get_tasks() -> list[STask]:
    tasks = await TaskRepository.find_all()
    return tasks


@router.delete("/{task_id}")
async def delete_task(task_id: int):
    deleted = await TaskRepository.delete_one(task_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    return {"ok": True, "deleted_task_id": task_id}