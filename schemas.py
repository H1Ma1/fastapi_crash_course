from pydantic import BaseModel, ConfigDict


class StaskAdd(BaseModel):
    name: str
    description: str | None = None


class STask(StaskAdd):
    model_config = ConfigDict(from_attributes=True)

    id: int



class STaskId(BaseModel):
    ok: bool = True
    task_id: int 