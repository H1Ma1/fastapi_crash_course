from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from repository import CatalogRepository, UserItemRepository
from schemas import (
    CatalogItemSchema,
    Category,
    ItemIdSchema,
    UserItemAddSchema,
    UserItemSchema,
    UserItemUpdateSchema,
)


router = APIRouter(tags=["WatchReadPlay"])


@router.get("/catalog", response_model=list[CatalogItemSchema])
async def get_catalog(
    category: Category | None = None,
    session: AsyncSession = Depends(get_session),
):
    items = await CatalogRepository.find_all(session, category)
    return items


@router.get("/items", response_model=list[UserItemSchema])
async def get_user_items(
    session: AsyncSession = Depends(get_session),
):
    items = await UserItemRepository.find_all(session)
    return items


@router.post("/items", response_model=ItemIdSchema)
async def add_user_item(
    item: UserItemAddSchema,
    session: AsyncSession = Depends(get_session),
):
    try:
        item_id = await UserItemRepository.add_one(session, item)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {"ok": True, "item_id": item_id}


@router.patch("/items/{item_id}", response_model=ItemIdSchema)
async def update_user_item(
    item_id: int,
    item: UserItemUpdateSchema,
    session: AsyncSession = Depends(get_session),
):
    updated = await UserItemRepository.update_one(session, item_id, item)

    if not updated:
        raise HTTPException(status_code=404, detail="Элемент не найден")

    return {"ok": True, "item_id": item_id}


@router.delete("/items/{item_id}", response_model=ItemIdSchema)
async def delete_user_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    deleted = await UserItemRepository.delete_one(session, item_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Элемент не найден")

    return {"ok": True, "item_id": item_id}