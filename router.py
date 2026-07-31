from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth import create_access_token, get_current_user, verify_google_token
from database import get_session
from models import User
from repository import CatalogRepository, UserItemRepository, UserRepository
from schemas import (
    CatalogItemSchema,
    Category,
    GoogleLoginSchema,
    ItemIdSchema,
    TokenSchema,
    UserItemAddSchema,
    UserItemSchema,
    UserItemUpdateSchema,
)


router = APIRouter(tags=["WatchReadPlay"])


@router.post("/auth/google", response_model=TokenSchema)
async def google_login(
    login_data: GoogleLoginSchema,
    session: AsyncSession = Depends(get_session),
):
    google_user = verify_google_token(login_data.credential)

    user = await UserRepository.get_or_create_google_user(
        session,
        google_user,
    )

    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/auth/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
    }


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
    current_user: User = Depends(get_current_user),
):
    items = await UserItemRepository.find_all(
        session,
        current_user.id,
    )
    return items


@router.post("/items", response_model=ItemIdSchema)
async def add_user_item(
    item: UserItemAddSchema,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        item_id = await UserItemRepository.add_one(
            session,
            item,
            current_user.id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {"ok": True, "item_id": item_id}


@router.patch("/items/{item_id}", response_model=ItemIdSchema)
async def update_user_item(
    item_id: int,
    item: UserItemUpdateSchema,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    updated = await UserItemRepository.update_one(
        session,
        item_id,
        item,
        current_user.id,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Элемент не найден")

    return {"ok": True, "item_id": item_id}


@router.delete("/items/{item_id}", response_model=ItemIdSchema)
async def delete_user_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    deleted = await UserItemRepository.delete_one(
        session,
        item_id,
        current_user.id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Элемент не найден")

    return {"ok": True, "item_id": item_id}