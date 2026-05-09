"""添加独立状态系统

Migration: 005_add_independent_status
Description: Adds independent status system with multiple status dimensions
Changes:
  1. Create status_history table to track all status changes
  2. Add independent status fields to submissions table:
     - processing_status / processing_status_updated_at
     - ai_status / ai_status_updated_at
     - download_status / download_status_updated_at
     - reply_status / reply_status_updated_at
  3. Migrate existing data to new status fields
  4. Create indexes for performance
  5. Keep legacy 'status' field for backward compatibility

ROLLBACK LIMITATIONS:
  Due to SQLite's limitation of not supporting DROP COLUMN in ALTER TABLE:
  - This rollback only removes the status_history table and indexes
  - The new status columns will remain in the database
  - To fully remove these columns, a full table recreation would be required
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import engine
from sqlalchemy import text
import json

# 现有状态到新状态的映射
STATUS_MIGRATION_MAP = {
    'pending': {
        'processing_status': 'received',
        'ai_status': 'pending',
        'download_status': 'pending',
        'reply_status': 'pending'
    },
    'ai_error': {
        'processing_status': 'failed',
        'ai_status': 'failed',
        'download_status': 'pending',
        'reply_status': 'pending'
    },
    'download_failed': {
        'processing_status': 'failed',
        'ai_status': 'success',
        'download_status': 'failed',
        'reply_status': 'pending'
    },
    'unreplied': {
        'processing_status': 'downloaded',
        'ai_status': 'success',
        'download_status': 'success',
        'reply_status': 'pending'
    },
    'completed': {
        'processing_status': 'replied',
        'ai_status': 'success',
        'download_status': 'success',
        'reply_status': 'success'
    },
    'ignored': {
        'processing_status': 'ignored',
        'ai_status': 'pending',
        'download_status': 'pending',
        'reply_status': 'pending'
    }
}

def migrate() -> bool:
    """执行迁移

    Returns:
        bool: True if migration succeeded, False otherwise
    """
    try:
        with engine.connect() as conn:
            trans = conn.begin()

            try:
                print("[STEP 1] Creating status_history table...")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS status_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        status_type TEXT NOT NULL,
                        old_status TEXT,
                        new_status TEXT NOT NULL,
                        reason TEXT,
                        extra_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
                    )
                """))

                # 创建索引
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_status_history_submission ON status_history(submission_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_status_history_type ON status_history(status_type)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_status_history_created ON status_history(created_at)"))

                print("[STEP 2] Adding new status columns to submissions table...")
                # 添加独立状态字段
                conn.execute(text("ALTER TABLE submissions ADD COLUMN processing_status TEXT DEFAULT 'received'"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN ai_status TEXT DEFAULT 'pending'"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN download_status TEXT DEFAULT 'pending'"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN reply_status TEXT DEFAULT 'pending'"))

                # 添加状态更新时间戳
                conn.execute(text("ALTER TABLE submissions ADD COLUMN processing_status_updated_at TIMESTAMP"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN ai_status_updated_at TIMESTAMP"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN download_status_updated_at TIMESTAMP"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN reply_status_updated_at TIMESTAMP"))

                print("[STEP 3] Migrating existing data...")
                # 查询所有现有记录
                result = conn.execute(text("SELECT id, status FROM submissions"))
                submissions = result.fetchall()

                migrated_count = 0
                for submission_id, old_status in submissions:
                    if old_status in STATUS_MIGRATION_MAP:
                        new_statuses = STATUS_MIGRATION_MAP[old_status]
                        conn.execute(text("""
                            UPDATE submissions
                            SET processing_status = :proc_status,
                                ai_status = :ai_status,
                                download_status = :dl_status,
                                reply_status = :reply_status,
                                processing_status_updated_at = CURRENT_TIMESTAMP,
                                ai_status_updated_at = CURRENT_TIMESTAMP,
                                download_status_updated_at = CURRENT_TIMESTAMP,
                                reply_status_updated_at = CURRENT_TIMESTAMP
                            WHERE id = :id
                        """), {
                            'proc_status': new_statuses['processing_status'],
                            'ai_status': new_statuses['ai_status'],
                            'dl_status': new_statuses['download_status'],
                            'reply_status': new_statuses['reply_status'],
                            'id': submission_id
                        })
                        migrated_count += 1

                print(f"[STEP 4] Creating indexes for performance...")
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_processing ON submissions(processing_status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_ai ON submissions(ai_status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_download ON submissions(download_status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_reply ON submissions(reply_status)"))

                trans.commit()

                print("[OK] Migration completed successfully")
                print(f"  - Created status_history table with indexes")
                print(f"  - Added 8 new columns to submissions table")
                print(f"  - Migrated {migrated_count} submissions to new status system")
                print(f"  - Created indexes for performance optimization")
                print(f"  - Legacy 'status' field preserved for backward compatibility")

            except Exception as e:
                trans.rollback()
                print(f"[ERROR] Migration failed: {e}")
                import traceback
                traceback.print_exc()
                raise

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def rollback() -> bool:
    """回滚迁移

    WARNING: Due to SQLite limitations, this only removes the status_history
    table and indexes. The new status columns will remain.

    Returns:
        bool: True if rollback succeeded, False otherwise
    """
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                print("[STEP 1] Dropping indexes...")
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_reply"))
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_download"))
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_ai"))
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_processing"))
                conn.execute(text("DROP INDEX IF EXISTS idx_status_history_created"))
                conn.execute(text("DROP INDEX IF EXISTS idx_status_history_type"))
                conn.execute(text("DROP INDEX IF EXISTS idx_status_history_submission"))

                print("[STEP 2] Dropping status_history table...")
                conn.execute(text("DROP TABLE IF EXISTS status_history"))

                trans.commit()
                print("[OK] Rollback completed")
                print("  Note: SQLite doesn't support DROP COLUMN, new status columns remain")

            except Exception as e:
                trans.rollback()
                print(f"[ERROR] Rollback failed: {e}")
                raise

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return False

    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Database migration for independent status system")
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate()
