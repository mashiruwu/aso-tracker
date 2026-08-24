import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "aso.db")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS apps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_store_id TEXT UNIQUE,
        name TEXT,
        country TEXT,
        current_version TEXT
    )
    ''')

    # Additive migrations preserve existing local databases.
    app_columns = {row[1] for row in c.execute("PRAGMA table_info(apps)")}
    if "icon_url" not in app_columns:
        c.execute("ALTER TABLE apps ADD COLUMN icon_url TEXT")
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id INTEGER,
        keyword TEXT,
        active BOOLEAN DEFAULT 1,
        UNIQUE(app_id, keyword),
        FOREIGN KEY (app_id) REFERENCES apps(id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword_id INTEGER,
        date TEXT,
        rank INTEGER,
        difficulty INTEGER,
        app_version TEXT,
        FOREIGN KEY (keyword_id) REFERENCES keywords(id)
    )
    ''')

    ranking_columns = {row[1] for row in c.execute("PRAGMA table_info(rankings)")}
    if "source" not in ranking_columns:
        c.execute("ALTER TABLE rankings ADD COLUMN source TEXT DEFAULT 'live'")
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS releases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id INTEGER,
        version TEXT,
        detected_at TEXT,
        FOREIGN KEY (app_id) REFERENCES apps(id)
    )
    ''')
    
    c.execute('''
    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id INTEGER,
        version TEXT,
        date TEXT,
        notes TEXT,
        FOREIGN KEY (app_id) REFERENCES apps(id)
    )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
