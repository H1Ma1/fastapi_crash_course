import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


Category = Literal["game", "book", "anime"]
Status = Literal["planned", "completed", "dropped"]
FriendshipStatus = Literal["pending", "accepted", "declined"]

def normalize_username_value(username: str) -> str:
    username = username.strip().lower()

    if username.startswith("@"):
        username = username[1:]

    return username


def validate_username_value(username: str) -> str:
    username = normalize_username_value(username)

    if not re.fullmatch(r"[a-z0-9_]{3,20}", username):
        raise ValueError(
            "Username должен быть 3-20 символов: только латинские буквы, цифры и _"
        )

    return username

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
    rating: int | None = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, rating: int | None) -> int | None:
        if rating is None:
            return rating

        if rating < 1 or rating > 10:
            raise ValueError("Оценка должна быть от 1 до 10")

        return rating

class UserItemSchema(BaseModel):
    id: int
    user_id: int
    catalog_item_id: int | None = None
    title: str
    custom_title: str | None = None
    category: Category
    status: Status
    rating: int | None = None
    notes: str | None = None
    created_at: datetime | str
    


class ItemIdSchema(BaseModel):
    ok: bool = True
    item_id: int


class OkSchema(BaseModel):
    ok: bool = True


class GoogleLoginSchema(BaseModel):
    credential: str


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None = None
    username: str | None = None
    name: str | None = None
    picture: str | None = None


class UserPublicSchema(BaseModel):
    id: int
    username: str | None = None
    name: str | None = None
    picture: str | None = None


class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSchema


class UsernameUpdateSchema(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        username = username.strip().lower()

        if username.startswith("@"):
            username = username[1:]

        if not re.fullmatch(r"[a-z0-9_]{3,20}", username):
            raise ValueError(
                "Username должен быть 3-20 символов: только латинские буквы, цифры и _"
            )

        return username


class FriendRequestSchema(BaseModel):
    id: int
    status: FriendshipStatus
    requester: UserPublicSchema
    receiver: UserPublicSchema
    created_at: datetime | str


class FriendSchema(BaseModel):
    friendship_id: int
    friend: UserPublicSchema

class RegisterSchema(BaseModel):
    username: str
    password: str
    name: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        return validate_username_value(username)

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        if len(password) < 6:
            raise ValueError("Пароль должен быть минимум 6 символов")

        if len(password) > 72:
            raise ValueError("Пароль слишком длинный. Максимум 72 символа")

        return password


class LoginSchema(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        return normalize_username_value(username)