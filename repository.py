from models import CatalogItem, User, UserItem
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CatalogItem, UserItem
from schemas import UserItemAddSchema, UserItemUpdateSchema


DEMO_USER_ID = 1


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
    ) -> list[CatalogItem]:
        query = select(CatalogItem).where(CatalogItem.is_approved == True)

        if category is not None:
            query = query.where(CatalogItem.category == category)

        query = query.order_by(CatalogItem.category, CatalogItem.title)

        result = await session.execute(query)
        return list(result.scalars().all())


class UserItemRepository:
    @classmethod
    async def find_all(
        cls,
        session: AsyncSession,
        user_id: int = DEMO_USER_ID,
    ) -> list[dict]:
        query = (
            select(UserItem, CatalogItem)
            .outerjoin(CatalogItem, UserItem.catalog_item_id == CatalogItem.id)
            .where(UserItem.user_id == user_id)
            .order_by(UserItem.id.desc())
        )

        result = await session.execute(query)
        rows = result.all()

        items = []

        for user_item, catalog_item in rows:
            title = catalog_item.title if catalog_item else user_item.custom_title

            items.append(
                {
                    "id": user_item.id,
                    "user_id": user_item.user_id,
                    "catalog_item_id": user_item.catalog_item_id,
                    "title": title,
                    "custom_title": user_item.custom_title,
                    "category": user_item.category,
                    "status": user_item.status,
                    "notes": user_item.notes,
                    "created_at": user_item.created_at,
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
            catalog_result = await session.execute(
                select(CatalogItem).where(
                    CatalogItem.id == catalog_item_id,
                    CatalogItem.is_approved == True,
                )
            )
            catalog_item = catalog_result.scalar_one_or_none()

            if catalog_item is None:
                raise ValueError("Такого элемента нет в каталоге")

            category = catalog_item.category

            existing_result = await session.execute(
                select(UserItem).where(
                    UserItem.user_id == user_id,
                    UserItem.catalog_item_id == catalog_item_id,
                )
            )
            existing_item = existing_result.scalar_one_or_none()

            if existing_item is not None:
                raise ValueError("Этот элемент уже есть в твоём списке")

        else:
            if not data.custom_title or not data.custom_title.strip():
                raise ValueError("Нужно выбрать элемент из каталога или ввести своё название")

            custom_title = data.custom_title.strip()

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
        item = result.scalar_one_or_none()

        if item is None:
            return False

        if data.status is not None:
            item.status = data.status

        if data.notes is not None:
            item.notes = data.notes

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
        item = result.scalar_one_or_none()

        if item is None:
            return False

        await session.delete(item)
        await session.commit()

        return True