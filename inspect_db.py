import sqlite3

db = sqlite3.connect("instance/recipes.db")

tables = db.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table'
    AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""").fetchall()

for (table,) in tables:
    print(f"\n{'='*50}")
    print("TABLE:", table)

    columns = db.execute(f'PRAGMA table_info("{table}")').fetchall()

    for col in columns:
        print(f"  Column: {col[1]} | Type: {col[2]} | Primary Key: {col[5]}")

    count = db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print("  Rows:", count)

db.close()
