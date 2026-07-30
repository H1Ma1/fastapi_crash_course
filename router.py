from fastapi import APIRouter, HTTPException

from repository import TaskRepository
from schemas import StaskAdd, STask, STaskId


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)


@router.post("", response_model=STaskId)
async def add_task(task: StaskAdd):
    task_id = await TaskRepository.add_one(task)

    return {
        "ok": True,
        "task_id": task_id,
    }


@router.get("", response_model=list[STask])
async def get_tasks():
    tasks = await TaskRepository.find_all()

    return tasks


@router.delete("/{task_id}", response_model=STaskId)
async def delete_task(task_id: int):
    deleted = await TaskRepository.delete_one(task_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена",
        )

    return {
        "ok": True,
        "task_id": task_id,
    }