import asyncio
import hashlib
import os
from pathlib import Path

import asyncpg

DATABASE_DSN = os.environ["CHAT_DATABASE_DSN"]
MIGRATIONS_DIR = Path("/app/migrations")


async def main():
    conn = await asyncpg.connect(DATABASE_DSN)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_schema_migrations (
                version TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.name
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()

            row = await conn.fetchrow(
                "SELECT checksum FROM chat_schema_migrations WHERE version = $1",
                version,
            )

            if row:
                if row["checksum"] != checksum:
                    raise RuntimeError(
                        f"Migration checksum mismatch for {version}: "
                        f"database={row['checksum']} file={checksum}"
                    )
                print(f"SKIP {version}")
                continue

            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    """
                    INSERT INTO chat_schema_migrations(version, checksum)
                    VALUES ($1, $2)
                    """,
                    version,
                    checksum,
                )
            print(f"APPLIED {version}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())