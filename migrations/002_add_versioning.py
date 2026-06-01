# migrations/002_add_versioning.py
import sqlite3
from config.settings import settings


def migrate(database_path: str = None) -> bool:
    """添加 version 和 is_latest 字段到 submissions 表"""
    db_path = database_path or str(settings.DATABASE_PATH)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(submissions)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'version' not in columns:
            cursor.execute("ALTER TABLE submissions ADD COLUMN version INTEGER DEFAULT 1 NOT NULL")
            print("[OK] Added column 'version'")
        else:
            print("[INFO] Column 'version' already exists, skipping")

        if 'is_latest' not in columns:
            cursor.execute("ALTER TABLE submissions ADD COLUMN is_latest BOOLEAN DEFAULT TRUE")
            print("[OK] Added column 'is_latest'")
        else:
            print("[INFO] Column 'is_latest' already exists, skipping")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_version ON submissions(version)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_latest ON submissions(is_latest)")

        conn.commit()
        print("[OK] Versioning migration completed")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Versioning migration failed: {e}")
        return False
    finally:
        conn.close()


def upgrade():
    migrate()


def downgrade():
    pass