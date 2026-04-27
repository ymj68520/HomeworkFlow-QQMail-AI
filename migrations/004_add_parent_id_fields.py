"""添加 parent_id, relation_type, is_primary 字段到 submissions 表

Migration: 004_add_parent_id_fields
Description: Adds fields for tracking submission relationships (versioning and deduplication)
Fields:
  - parent_id: Foreign key to parent submission (self-referential)
  - relation_type: Type of relationship (version/possible_dup) - see RelationType enum
  - is_primary: Whether this is the primary record in a relationship group

ROLLBACK LIMITATIONS:
  Due to SQLite's limitation of not supporting DROP COLUMN in ALTER TABLE:
  - This rollback only removes indexes, NOT the columns themselves
  - The columns (parent_id, relation_type, is_primary) will remain in the database
  - To fully remove these columns, a full table recreation would be required
  - Consider this before running rollback in production
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import engine
from sqlalchemy import text

def migrate() -> bool:
    """执行迁移

    Returns:
        bool: True if migration succeeded, False otherwise
    """
    try:
        # 使用 SQLAlchemy engine
        with engine.connect() as conn:
            # 开启事务
            trans = conn.begin()

            try:
                # 添加新字段
                conn.execute(text("ALTER TABLE submissions ADD COLUMN parent_id INTEGER REFERENCES submissions(id)"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN relation_type TEXT"))
                conn.execute(text("ALTER TABLE submissions ADD COLUMN is_primary BOOLEAN DEFAULT 1"))

                # 创建索引
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_parent ON submissions(parent_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_relation ON submissions(relation_type)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_primary ON submissions(is_primary)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_submissions_student_assignment ON submissions(student_id, assignment_id)"))

                trans.commit()
                print("[OK] Migration completed successfully")
                print("  - Added fields: parent_id, relation_type, is_primary")
                print("  - Created indexes: idx_submissions_parent, idx_submissions_relation, idx_submissions_primary, idx_submissions_student_assignment")

            except Exception as e:
                trans.rollback()
                print(f"[ERROR] Migration failed: {e}")
                raise

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def rollback() -> bool:
    """回滚迁移

    WARNING: Due to SQLite limitations, this only removes indexes.
    The columns (parent_id, relation_type, is_primary) will remain.

    Returns:
        bool: True if rollback succeeded, False otherwise
    """
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                # SQLite 不支持 DROP COLUMN，需要重建表
                # 这里只删除索引
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_student_assignment"))
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_primary"))
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_relation"))
                conn.execute(text("DROP INDEX IF EXISTS idx_submissions_parent"))

                trans.commit()
                print("[OK] Rollback completed (indexes removed)")
                print("  Note: SQLite doesn't support DROP COLUMN, fields remain but unused")

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
    parser = argparse.ArgumentParser(description="Database migration for deduplication refactoring")
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate()
