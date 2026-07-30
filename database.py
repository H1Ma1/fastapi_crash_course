import os

import httpx
from dotenv import load_dotenv


load_dotenv()


TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")


if not TURSO_DATABASE_URL:
    raise RuntimeError("Не найдена переменная TURSO_DATABASE_URL")

if not TURSO_AUTH_TOKEN:
    raise RuntimeError("Не найдена переменная TURSO_AUTH_TOKEN")


def get_turso_http_url() -> str:
    """
    Turso даёт URL вида:
    libsql://fastapi-tasks-h1ma1.aws-us-west-2.turso.io

    Для HTTP API нужен:
    https://fastapi-tasks-h1ma1.aws-us-west-2.turso.io/v2/pipeline
    """
    if TURSO_DATABASE_URL.startswith("libsql://"):
        base_url = TURSO_DATABASE_URL.replace("libsql://", "https://", 1)
    else:
        base_url = TURSO_DATABASE_URL

    return base_url.rstrip("/") + "/v2/pipeline"


TURSO_HTTP_URL = get_turso_http_url()


def to_turso_arg(value):
    """
    Turso ждёт аргументы в специальном формате:
    {"type": "text", "value": "..."}
    {"type": "integer", "value": "1"}
    """
    if value is None:
        return {"type": "null"}

    if isinstance(value, bool):
        return {
            "type": "integer",
            "value": "1" if value else "0",
        }

    if isinstance(value, int):
        return {
            "type": "integer",
            "value": str(value),
        }

    if isinstance(value, float):
        return {
            "type": "float",
            "value": str(value),
        }

    return {
        "type": "text",
        "value": str(value),
    }


async def execute_sql(sql: str, args: list | None = None) -> dict:
    stmt = {
        "sql": sql,
    }

    if args is not None:
        stmt["args"] = [to_turso_arg(arg) for arg in args]

    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": stmt,
            },
            {
                "type": "close",
            },
        ]
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            TURSO_HTTP_URL,
            headers={
                "Authorization": f"Bearer {TURSO_AUTH_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    response.raise_for_status()

    data = response.json()
    first_result = data["results"][0]

    if first_result["type"] != "ok":
        raise RuntimeError(f"Turso error: {first_result}")

    return first_result["response"]["result"]


def parse_turso_rows(result: dict) -> list[dict]:
    cols = result.get("cols", [])
    rows = result.get("rows", [])

    col_names = [col["name"] for col in cols]

    parsed_rows = []

    for row in rows:
        item = {}

        for col_name, cell in zip(col_names, row):
            if cell["type"] == "null":
                item[col_name] = None
            else:
                item[col_name] = cell.get("value")

        parsed_rows.append(item)

    return parsed_rows


async def create_tables():
    await execute_sql(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
        """
    )


async def delete_tables():
    await execute_sql("DROP TABLE IF EXISTS tasks")