from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth import create_access_token, get_current_user, verify_google_token
from database import get_session
from models import User
from repository import (
    CatalogRepository,
    FriendshipRepository,
    UserItemRepository,
    UserRepository,
)
from schemas import (
    CatalogItemSchema,
    Category,
    FriendRequestSchema,
    FriendSchema,
    GoogleLoginSchema,
    ItemIdSchema,
    OkSchema,
    Status,
    TokenSchema,
    UserItemAddSchema,
    UserItemSchema,
    UserItemUpdateSchema,
    UserPublicSchema,
    UsernameUpdateSchema,
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
        "username": current_user.username,
        "name": current_user.name,
        "picture": current_user.picture,
    }


@router.patch("/auth/me/username")
async def update_my_username(
    username_data: UsernameUpdateSchema,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        user = await UserRepository.update_username(
            session=session,
            user_id=current_user.id,
            username=username_data.username,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.name,
        "picture": user.picture,
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
    category: Category | None = None,
    status: Status | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    items = await UserItemRepository.find_all(
        session=session,
        user_id=current_user.id,
        category=category,
        status=status,
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


@router.get("/users/search", response_model=list[UserPublicSchema])
async def search_users(
    username: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    users = await UserRepository.search_by_username(
        session=session,
        current_user_id=current_user.id,
        username=username,
    )

    return users


@router.get("/users/{username}/items", response_model=list[UserItemSchema])
async def get_user_items_by_username(
    username: str,
    category: Category | None = None,
    status: Status | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    target_user = await UserRepository.find_by_username(
        session=session,
        username=username,
    )

    if target_user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    is_self = target_user.id == current_user.id

    if not is_self:
        are_friends = await FriendshipRepository.are_friends(
            session=session,
            user_id=current_user.id,
            other_user_id=target_user.id,
        )

        if not are_friends:
            raise HTTPException(
                status_code=403,
                detail="Списки этого пользователя доступны только друзьям",
            )

    items = await UserItemRepository.find_all(
        session=session,
        user_id=target_user.id,
        category=category,
        status=status,
    )

    return items


@router.post("/friends/request/{receiver_id}", response_model=FriendRequestSchema)
async def send_friend_request(
    receiver_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        friend_request = await FriendshipRepository.send_request(
            session=session,
            requester_id=current_user.id,
            receiver_id=receiver_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return friend_request


@router.get("/friends", response_model=list[FriendSchema])
async def get_friends(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    friends = await FriendshipRepository.get_friends(
        session=session,
        user_id=current_user.id,
    )

    return friends


@router.get("/friends/requests/incoming", response_model=list[FriendRequestSchema])
async def get_incoming_friend_requests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    requests = await FriendshipRepository.get_incoming_requests(
        session=session,
        user_id=current_user.id,
    )

    return requests


@router.get("/friends/requests/outgoing", response_model=list[FriendRequestSchema])
async def get_outgoing_friend_requests(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    requests = await FriendshipRepository.get_outgoing_requests(
        session=session,
        user_id=current_user.id,
    )

    return requests


@router.patch("/friends/requests/{request_id}/accept", response_model=OkSchema)
async def accept_friend_request(
    request_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    accepted = await FriendshipRepository.accept_request(
        session=session,
        request_id=request_id,
        current_user_id=current_user.id,
    )

    if not accepted:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    return {"ok": True}


@router.patch("/friends/requests/{request_id}/decline", response_model=OkSchema)
async def decline_friend_request(
    request_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    declined = await FriendshipRepository.decline_request(
        session=session,
        request_id=request_id,
        current_user_id=current_user.id,
    )

    if not declined:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    return {"ok": True}


@router.delete("/friends/{friend_id}", response_model=OkSchema)
async def delete_friend(
    friend_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    deleted = await FriendshipRepository.delete_friend(
        session=session,
        user_id=current_user.id,
        friend_id=friend_id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Друг не найден")

    return {"ok": True}