import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models import Base, CatalogItem, User


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("Не найдена переменная DATABASE_URL")


engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_session():
    async with async_session_maker() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await seed_demo_data()


async def seed_demo_data():
    async with async_session_maker() as session:
        demo_user_result = await session.execute(
            select(User).where(User.id == 1)
        )
        demo_user = demo_user_result.scalar_one_or_none()

        if demo_user is None:
            demo_user = User(
                id=1,
                google_id="demo-user-1",
                email="demo@example.com",
                name="Demo User",
            )
            session.add(demo_user)

        catalog_items = [
            ("The Witcher 3", "game"),
            ("Cyberpunk 2077", "game"),
            ("Elden Ring", "game"),
            ("Red Dead Redemption 2", "game"),
            ("God of War", "game"),

            ("Dune", "book"),
            ("1984", "book"),
            ("The Hobbit", "book"),
            ("Harry Potter", "book"),
            ("Atomic Habits", "book"),

            ("Breaking Bad", "movie"),
            ("Game of Thrones", "movie"),
            ("Interstellar", "movie"),
            ("The Lord of the Rings", "movie"),
            ("The Last of Us", "movie"),
        ]

        for title, category in catalog_items:
            existing_result = await session.execute(
                select(CatalogItem).where(
                    CatalogItem.title == title,
                    CatalogItem.category == category,
                )
            )
            existing_item = existing_result.scalar_one_or_none()

            if existing_item is None:
                session.add(
                    CatalogItem(
                        title=title,
                        category=category,
                        is_approved=True,
                    )
                )

        await session.flush()

        await session.execute(
            text(
                """
                SELECT setval(
                    pg_get_serial_sequence('users', 'id'),
                    COALESCE((SELECT MAX(id) FROM users), 1),
                    true
                )
                """
            )
        )

        await session.commit()