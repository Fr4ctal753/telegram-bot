import sqlite3

def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        category TEXT
    )
    """)

    conn.commit()
    conn.close()