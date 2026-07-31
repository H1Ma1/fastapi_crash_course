import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CatalogItem, User, UserItem
from schemas import UserItemAddSchema, UserItemUpdateSchema


DEMO_USER_ID = 1


def normalize_title(title: str) -> str:
    """
    Превращает название в удобный вид для сравнения.

    Примеры:
    "DELTARUNE" -> "deltarune"
    "Del Tarune" -> "deltarune"
    "Baldur's Gate 3" -> "baldursgate3"
    "Baldurs Gate 3" -> "baldursgate3"
    """
    title = unicodedata.normalize("NFKD", title)
    title = "".join(char for char in title if not unicodedata.combining(char))
    title = title.lower()
    title = title.replace("&", "and")
    title = re.sub(r"[^a-z0-9а-яё]+", "", title)

    return title


async def find_catalog_item_by_title(
    session: AsyncSession,
    title: str,
    category: str,
) -> CatalogItem | None:
    """
    Ищет элемент в общем каталоге по названию,
    игнорируя регистр, пробелы, знаки препинания.
    """
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
    """
    Если пользователь раньше добавил своё название,
    а теперь такое название уже есть в catalog_items,
    то мы превращаем custom item в нормальную ссылку на catalog_item.

    Пример:
    user_items:
      custom_title = "DelTARUNE"
      catalog_item_id = null

    catalog_items:
      title = "DELTARUNE"

    После синхронизации:
      custom_title = null
      catalog_item_id = id игры DELTARUNE
    """
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
    ) -> list[dict]:
        await sync_custom_items_with_catalog(session, user_id)

        stmt = (
            select(UserItem, CatalogItem.title)
            .outerjoin(CatalogItem, UserItem.catalog_item_id == CatalogItem.id)
            .where(UserItem.user_id == user_id)
            .order_by(UserItem.id.desc())
        )

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

        if data.status is not None:
            user_item.status = data.status

        if data.notes is not None:
            user_item.notes = data.notes

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