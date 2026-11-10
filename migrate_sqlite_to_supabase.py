import os
import sqlite3
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = "instance/recipes.db"

TABLES = [
    "tag",
    "recipe",
    "recipe_ingredient",
    "recipe_tags",
]

# Read Supabase connection string
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL not found in .env")

# Convert SQLAlchemy URL to psycopg2-compatible URL
database_url = database_url.replace(
    "postgresql+psycopg2://",
    "postgresql://",
    1
)

sqlite_db = sqlite3.connect(SQLITE_PATH)
sqlite_db.row_factory = sqlite3.Row

pg_db = psycopg2.connect(database_url)

try:
    with pg_db:
        with pg_db.cursor() as cursor:

            # Safety check: refuse to overwrite existing data
            for table in TABLES:
                cursor.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(
                        sql.Identifier(table)
                    )
                )
                count = cursor.fetchone()[0]

                if count != 0:
                    raise RuntimeError(
                        f"Supabase table '{table}' already contains "
                        f"{count} rows. Migration stopped safely."
                    )

            print("Supabase tables are empty. Starting migration...\n")

            for table in TABLES:
                rows = sqlite_db.execute(
                    f'SELECT * FROM "{table}"'
                ).fetchall()

                if not rows:
                    print(f"{table}: 0 rows")
                    continue

                columns = rows[0].keys()

                insert_query = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({})"
                ).format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(
                        map(sql.Identifier, columns)
                    ),
                    sql.SQL(", ").join(
                        [sql.Placeholder()] * len(columns)
                    )
                )

                values = []

                for row in rows:
                        record = []

                        for column in columns:
                            value = row[column]

        # Convert SQLite integer Boolean to Python Boolean
                            if table == "recipe" and column == "is_favorite":
                                value = bool(value) if value is not None else False

                            record.append(value)

                values.append(tuple(record))

                cursor.executemany(insert_query, values)

                print(f"{table}: {len(rows)} rows transferred")

            # Reset PostgreSQL ID sequences
            for table in ["recipe", "recipe_ingredient", "tag"]:
                cursor.execute(
                    "SELECT pg_get_serial_sequence(%s, 'id')",
                    (table,)
                )
                sequence = cursor.fetchone()[0]

                if sequence:
                    cursor.execute(
                        sql.SQL("""
                            SELECT setval(
                                %s::regclass,
                                COALESCE(MAX(id), 1),
                                MAX(id) IS NOT NULL
                            )
                            FROM {}
                        """).format(sql.Identifier(table)),
                        (sequence,)
                    )

    print("\nMigration completed successfully!")

except Exception:
    print("\nMigration failed. Transaction rolled back.")
    raise

finally:
    sqlite_db.close()
    pg_db.close()
