from database import execute_sql, parse_turso_rows
from schemas import StaskAdd, STask


class TaskRepository:
    @classmethod
    async def add_one(cls, data: StaskAdd) -> int:
        result = await execute_sql(
            """
            INSERT INTO tasks (name, description)
            VALUES (?, ?)
            """,
            [
                data.name,
                data.description,
            ],
        )

        return int(result["last_insert_rowid"])

    @classmethod
    async def find_all(cls) -> list[STask]:
        result = await execute_sql(
            """
            SELECT id, name, description
            FROM tasks
            ORDER BY id
            """
        )

        rows = parse_turso_rows(result)

        tasks = [
            STask.model_validate(row)
            for row in rows
        ]

        return tasks

    @classmethod
    async def delete_one(cls, task_id: int) -> bool:
        result = await execute_sql(
            """
            DELETE FROM tasks
            WHERE id = ?
            """,
            [
                task_id,
            ],
        )

        return result.get("affected_row_count", 0) > 0