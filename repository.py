import re
import unicodedata

from auth import hash_password, verify_password
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import CatalogItem, Friendship, User, UserItem
from schemas import UserItemAddSchema, UserItemUpdateSchema


DEMO_USER_ID = 1


def normalize_title(title: str) -> str:
    title = unicodedata.normalize("NFKD", title)
    title = "".join(char for char in title if not unicodedata.combining(char))
    title = title.lower()
    title = title.replace("&", "and")
    title = re.sub(r"[^a-z0-9а-яё]+", "", title)

    return title


def normalize_username(username: str) -> str:
    username = username.strip().lower()

    if username.startswith("@"):
        username = username[1:]

    return username


def user_to_public_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "picture": user.picture,
    }


def friend_request_to_dict(friendship: Friendship) -> dict:
    return {
        "id": friendship.id,
        "status": friendship.status,
        "requester": user_to_public_dict(friendship.requester),
        "receiver": user_to_public_dict(friendship.receiver),
        "created_at": friendship.created_at,
    }


async def find_catalog_item_by_title(
    session: AsyncSession,
    title: str,
    category: str,
) -> CatalogItem | None:
    normalized_user_title = normalize_title(title)

    result = await session.execute(
        select(CatalogItem).where(
            CatalogItem.category == category,
            CatalogItem.is_approved == True,
        )
    )

    catalog_items = result.scalars().all()

    for catalog_item in catalog_items:
        if normalize_title(catalog_item.title) == normalized_user_title:
            return catalog_item

    return None


async def sync_custom_items_with_catalog(
    session: AsyncSession,
    user_id: int,
):
    result = await session.execute(
        select(UserItem).where(
            UserItem.user_id == user_id,
            UserItem.catalog_item_id == None,
            UserItem.custom_title != None,
        )
    )

    custom_items = result.scalars().all()

    was_changed = False

    for user_item in custom_items:
        catalog_item = await find_catalog_item_by_title(
            session=session,
            title=user_item.custom_title,
            category=user_item.category,
        )

        if catalog_item is None:
            continue

        duplicate_result = await session.execute(
            select(UserItem).where(
                UserItem.user_id == user_id,
                UserItem.catalog_item_id == catalog_item.id,
            )
        )

        duplicate_item = duplicate_result.scalar_one_or_none()

        if duplicate_item is not None:
            if duplicate_item.notes is None and user_item.notes is not None:
                duplicate_item.notes = user_item.notes

            await session.delete(user_item)
            was_changed = True
            continue

        user_item.catalog_item_id = catalog_item.id
        user_item.custom_title = None
        user_item.category = catalog_item.category

        was_changed = True

    if was_changed:
        await session.commit()


class UserRepository:
    @classmethod
    async def get_or_create_google_user(
        cls,
        session: AsyncSession,
        google_user: dict,
    ) -> User:
        google_id = google_user["google_id"]
        email = google_user["email"]
        name = google_user.get("name")
        picture = google_user.get("picture")

        result = await session.execute(
            select(User).where(User.google_id == google_id)
        )
        user = result.scalar_one_or_none()

        if user is not None:
            user.email = email
            user.name = name
            user.picture = picture

            await session.commit()
            await session.refresh(user)

            return user

        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is not None:
            user.google_id = google_id
            user.name = name
            user.picture = picture

            await session.commit()
            await session.refresh(user)

            return user

        user = User(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        return user

    @classmethod
    async def update_username(
        cls,
        session: AsyncSession,
        user_id: int,
        username: str,
    ) -> User:
        username = normalize_username(username)

        user = await session.get(User, user_id)

        if user is None:
            raise ValueError("Пользователь не найден")

        result = await session.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user is not None and existing_user.id != user_id:
            raise ValueError("Этот username уже занят")

        user.username = username

        await session.commit()
        await session.refresh(user)

        return user

    @classmethod
    async def search_by_username(
        cls,
        session: AsyncSession,
        current_user_id: int,
        username: str,
    ) -> list[dict]:
        username = normalize_username(username)

        if len(username) < 2:
            return []

        result = await session.execute(
            select(User)
            .where(
                User.id != current_user_id,
                User.username != None,
                User.username.ilike(f"%{username}%"),
            )
            .order_by(User.username)
            .limit(10)
        )

        users = result.scalars().all()

        return [user_to_public_dict(user) for user in users]

    @classmethod
    async def find_by_username(
        cls,
        session: AsyncSession,
        username: str,
    ) -> User | None:
        username = normalize_username(username)

        result = await session.execute(
            select(User).where(User.username == username)
        )

        return result.scalar_one_or_none()
    @classmethod
    async def register_with_password(
        cls,
        session: AsyncSession,
        username: str,
        password: str,
        name: str | None = None,
    ) -> User:
        username = normalize_username(username)

        result = await session.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            raise ValueError("Этот username уже занят")

        user = User(
            username=username,
            password_hash=hash_password(password),
            name=name or username,
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        return user

    @classmethod
    async def login_with_password(
        cls,
        session: AsyncSession,
        username: str,
        password: str,
    ) -> User:
        username = normalize_username(username)

        result = await session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError("Неверный username или пароль")

        if user.password_hash is None:
            raise ValueError("У этого аккаунта нет входа по паролю")

        if not verify_password(password, user.password_hash):
            raise ValueError("Неверный username или пароль")

        return user
    @classmethod
    async def link_google_to_user(
        cls,
        session: AsyncSession,
        user_id: int,
        google_user: dict,
    ) -> User:
        google_id = google_user["google_id"]
        email = google_user["email"]
        name = google_user.get("name")
        picture = google_user.get("picture")

        current_user = await session.get(User, user_id)

        if current_user is None:
            raise ValueError("Пользователь не найден")

        result = await session.execute(
            select(User).where(User.google_id == google_id)
        )
        user_with_google = result.scalar_one_or_none()

        if user_with_google is not None and user_with_google.id != user_id:
            raise ValueError("Этот Google аккаунт уже привязан к другому пользователю")

        result = await session.execute(
            select(User).where(User.email == email)
        )
        user_with_email = result.scalar_one_or_none()

        if user_with_email is not None and user_with_email.id != user_id:
            raise ValueError("Этот email уже используется другим аккаунтом")

        current_user.google_id = google_id
        current_user.email = email
        current_user.picture = picture

        if not current_user.name and name:
            current_user.name = name

        await session.commit()
        await session.refresh(current_user)

        return current_user


class CatalogRepository:
    @classmethod
    async def find_all(
        cls,
        session: AsyncSession,
        category: str | None = None,
    ):
        stmt = select(CatalogItem).where(CatalogItem.is_approved == True)

        if category:
            stmt = stmt.where(CatalogItem.category == category)

        stmt = stmt.order_by(CatalogItem.category, CatalogItem.title)

        result = await session.execute(stmt)

        return result.scalars().all()


class UserItemRepository:
    @classmethod
    async def find_all(
        cls,
        session: AsyncSession,
        user_id: int = DEMO_USER_ID,
        category: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        await sync_custom_items_with_catalog(session, user_id)

        stmt = (
            select(UserItem, CatalogItem.title)
            .outerjoin(CatalogItem, UserItem.catalog_item_id == CatalogItem.id)
            .where(UserItem.user_id == user_id)
        )

        if category:
            stmt = stmt.where(UserItem.category == category)

        if status:
            stmt = stmt.where(UserItem.status == status)

        stmt = stmt.order_by(UserItem.id.desc())

        result = await session.execute(stmt)
        rows = result.all()

        items = []

        for user_item, catalog_title in rows:
            items.append(
                {
                    "id": user_item.id,
                    "user_id": user_item.user_id,
                    "catalog_item_id": user_item.catalog_item_id,
                    "title": catalog_title or user_item.custom_title,
                    "custom_title": user_item.custom_title,
                    "category": user_item.category,
                    "status": user_item.status,
                    "rating": user_item.rating,
                    "notes": user_item.notes,
                    "created_at": user_item.created_at.isoformat()
                    if user_item.created_at
                    else None,
                }
            )

        return items

    @classmethod
    async def add_one(
        cls,
        session: AsyncSession,
        data: UserItemAddSchema,
        user_id: int = DEMO_USER_ID,
    ) -> int:
        catalog_item_id = data.catalog_item_id
        custom_title = None
        category = data.category

        if catalog_item_id is not None:
            catalog_item = await session.get(CatalogItem, catalog_item_id)

            if catalog_item is None or not catalog_item.is_approved:
                raise ValueError("Такого элемента нет в каталоге")

            category = catalog_item.category

            result = await session.execute(
                select(UserItem).where(
                    UserItem.user_id == user_id,
                    UserItem.catalog_item_id == catalog_item_id,
                )
            )

            existing = result.scalar_one_or_none()

            if existing:
                raise ValueError("Этот элемент уже есть в твоём списке")

        else:
            if not data.custom_title or not data.custom_title.strip():
                raise ValueError("Нужно выбрать элемент из каталога или ввести своё название")

            typed_title = data.custom_title.strip()

            catalog_item = await find_catalog_item_by_title(
                session=session,
                title=typed_title,
                category=category,
            )

            if catalog_item is not None:
                catalog_item_id = catalog_item.id
                category = catalog_item.category

                result = await session.execute(
                    select(UserItem).where(
                        UserItem.user_id == user_id,
                        UserItem.catalog_item_id == catalog_item_id,
                    )
                )

                existing = result.scalar_one_or_none()

                if existing:
                    raise ValueError("Этот элемент уже есть в твоём списке")

            else:
                custom_title = typed_title

        user_item = UserItem(
            user_id=user_id,
            catalog_item_id=catalog_item_id,
            custom_title=custom_title,
            category=category,
            status=data.status,
            notes=data.notes,
        )

        session.add(user_item)
        await session.commit()
        await session.refresh(user_item)

        return user_item.id

    @classmethod
    async def update_one(
        cls,
        session: AsyncSession,
        item_id: int,
        data: UserItemUpdateSchema,
        user_id: int = DEMO_USER_ID,
    ) -> bool:
        result = await session.execute(
            select(UserItem).where(
                UserItem.id == item_id,
                UserItem.user_id == user_id,
            )
        )

        user_item = result.scalar_one_or_none()

        if user_item is None:
            return False

        fields_set = data.model_fields_set

        next_status = user_item.status

        if "status" in fields_set and data.status is not None:
            next_status = data.status

        if "rating" in fields_set and data.rating is not None:
            if next_status != "completed":
                raise ValueError("Оценку можно поставить только завершённому элементу")

        if "status" in fields_set and data.status is not None:
            user_item.status = data.status

            if user_item.status != "completed":
                user_item.rating = None

        if "notes" in fields_set:
            user_item.notes = data.notes

        if "rating" in fields_set:
            if data.rating is not None and user_item.status != "completed":
                raise ValueError("Оценку можно поставить только завершённому элементу")

            user_item.rating = data.rating

        await session.commit()

        return True

    @classmethod
    async def delete_one(
        cls,
        session: AsyncSession,
        item_id: int,
        user_id: int = DEMO_USER_ID,
    ) -> bool:
        result = await session.execute(
            select(UserItem).where(
                UserItem.id == item_id,
                UserItem.user_id == user_id,
            )
        )

        user_item = result.scalar_one_or_none()

        if user_item is None:
            return False

        await session.delete(user_item)
        await session.commit()

        return True


class FriendshipRepository:
    @classmethod
    async def find_relation_between_users(
        cls,
        session: AsyncSession,
        user_id: int,
        other_user_id: int,
    ) -> Friendship | None:
        result = await session.execute(
            select(Friendship).where(
                or_(
                    and_(
                        Friendship.requester_id == user_id,
                        Friendship.receiver_id == other_user_id,
                    ),
                    and_(
                        Friendship.requester_id == other_user_id,
                        Friendship.receiver_id == user_id,
                    ),
                )
            )
        )

        return result.scalar_one_or_none()

    @classmethod
    async def are_friends(
        cls,
        session: AsyncSession,
        user_id: int,
        other_user_id: int,
    ) -> bool:
        relation = await cls.find_relation_between_users(
            session,
            user_id,
            other_user_id,
        )

        return relation is not None and relation.status == "accepted"

    @classmethod
    async def get_friendship_with_users(
        cls,
        session: AsyncSession,
        friendship_id: int,
    ) -> Friendship:
        result = await session.execute(
            select(Friendship)
            .options(
                selectinload(Friendship.requester),
                selectinload(Friendship.receiver),
            )
            .where(Friendship.id == friendship_id)
        )

        return result.scalar_one()

    @classmethod
    async def send_request(
        cls,
        session: AsyncSession,
        requester_id: int,
        receiver_id: int,
    ) -> dict:
        if requester_id == receiver_id:
            raise ValueError("Нельзя добавить самого себя в друзья")

        receiver = await session.get(User, receiver_id)

        if receiver is None:
            raise ValueError("Пользователь не найден")

        relation = await cls.find_relation_between_users(
            session,
            requester_id,
            receiver_id,
        )

        if relation is not None:
            if relation.status == "accepted":
                raise ValueError("Вы уже друзья")

            if relation.status == "pending":
                if relation.requester_id == requester_id:
                    raise ValueError("Заявка уже отправлена")

                raise ValueError("Этот пользователь уже отправил тебе заявку")

            if relation.status == "declined":
                relation.requester_id = requester_id
                relation.receiver_id = receiver_id
                relation.status = "pending"

                await session.commit()
                await session.refresh(relation)

                relation = await cls.get_friendship_with_users(session, relation.id)

                return friend_request_to_dict(relation)

        friendship = Friendship(
            requester_id=requester_id,
            receiver_id=receiver_id,
            status="pending",
        )

        session.add(friendship)
        await session.commit()
        await session.refresh(friendship)

        friendship = await cls.get_friendship_with_users(session, friendship.id)

        return friend_request_to_dict(friendship)

    @classmethod
    async def get_incoming_requests(
        cls,
        session: AsyncSession,
        user_id: int,
    ) -> list[dict]:
        result = await session.execute(
            select(Friendship)
            .options(
                selectinload(Friendship.requester),
                selectinload(Friendship.receiver),
            )
            .where(
                Friendship.receiver_id == user_id,
                Friendship.status == "pending",
            )
            .order_by(Friendship.id.desc())
        )

        requests = result.scalars().all()

        return [friend_request_to_dict(request) for request in requests]

    @classmethod
    async def get_outgoing_requests(
        cls,
        session: AsyncSession,
        user_id: int,
    ) -> list[dict]:
        result = await session.execute(
            select(Friendship)
            .options(
                selectinload(Friendship.requester),
                selectinload(Friendship.receiver),
            )
            .where(
                Friendship.requester_id == user_id,
                Friendship.status == "pending",
            )
            .order_by(Friendship.id.desc())
        )

        requests = result.scalars().all()

        return [friend_request_to_dict(request) for request in requests]

    @classmethod
    async def accept_request(
        cls,
        session: AsyncSession,
        request_id: int,
        current_user_id: int,
    ) -> bool:
        friendship = await session.get(Friendship, request_id)

        if friendship is None:
            return False

        if friendship.receiver_id != current_user_id:
            return False

        if friendship.status != "pending":
            return False

        friendship.status = "accepted"

        await session.commit()

        return True

    @classmethod
    async def decline_request(
        cls,
        session: AsyncSession,
        request_id: int,
        current_user_id: int,
    ) -> bool:
        friendship = await session.get(Friendship, request_id)

        if friendship is None:
            return False

        if friendship.receiver_id != current_user_id:
            return False

        if friendship.status != "pending":
            return False

        friendship.status = "declined"

        await session.commit()

        return True

    @classmethod
    async def get_friends(
        cls,
        session: AsyncSession,
        user_id: int,
    ) -> list[dict]:
        result = await session.execute(
            select(Friendship)
            .options(
                selectinload(Friendship.requester),
                selectinload(Friendship.receiver),
            )
            .where(
                or_(
                    Friendship.requester_id == user_id,
                    Friendship.receiver_id == user_id,
                ),
                Friendship.status == "accepted",
            )
        )

        friendships = result.scalars().all()

        friends = []

        for friendship in friendships:
            if friendship.requester_id == user_id:
                friend = friendship.receiver
            else:
                friend = friendship.requester

            friends.append(
                {
                    "friendship_id": friendship.id,
                    "friend": user_to_public_dict(friend),
                }
            )

        return friends

    @classmethod
    async def delete_friend(
        cls,
        session: AsyncSession,
        user_id: int,
        friend_id: int,
    ) -> bool:
        friendship = await cls.find_relation_between_users(
            session,
            user_id,
            friend_id,
        )

        if friendship is None:
            return False

        if friendship.status != "accepted":
            return False

        await session.delete(friendship)
        await session.commit()

        return True