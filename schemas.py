from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


Category = Literal["game", "book", "movie"]
Status = Literal["planned", "completed", "dropped"]


class CatalogItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: Category
    image_url: str | None = None
    description: str | None = None


class UserItemAddSchema(BaseModel):
    catalog_item_id: int | None = None
    custom_title: str | None = None
    category: Category
    status: Status = "planned"
    notes: str | None = None


class UserItemUpdateSchema(BaseModel):
    status: Status | None = None
    notes: str | None = None


class UserItemSchema(BaseModel):
    id: int
    user_id: int
    catalog_item_id: int | None = None
    title: str
    custom_title: str | None = None
    category: Category
    status: Status
    notes: str | None = None
    created_at: datetime


class ItemIdSchema(BaseModel):
    ok: bool = True
    item_id: int