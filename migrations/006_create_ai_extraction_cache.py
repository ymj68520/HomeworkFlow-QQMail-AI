"""创建AI提取缓存表 (AIExtractionCache)

这个迁移创建ai_extraction_cache表，用于缓存AI提取的结果，
支持单作业和多作业两种缓存类型。
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
        with engine.connect() as conn:
            trans = conn.begin()

            try:
                # 创建ai_extraction_cache表
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ai_extraction_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email_uid VARCHAR(255) UNIQUE NOT NULL,
                        student_id VARCHAR(50),
                        name VARCHAR(100),
                        assignment_name VARCHAR(50),
                        confidence FLOAT,
                        is_fallback BOOLEAN DEFAULT FALSE,
                        cache_data TEXT,
                        cache_type VARCHAR(20) DEFAULT 'single',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))

                # 创建索引
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ai_cache_email_uid ON ai_extraction_cache(email_uid)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ai_cache_type ON ai_extraction_cache(cache_type)"))

                trans.commit()
                print("[OK] Created ai_extraction_cache table with indexes")
                print("  - Fields: id, email_uid, student_id, name, assignment_name, confidence, is_fallback, cache_data, cache_type, created_at, updated_at")
                print("  - Indexes: idx_ai_cache_email_uid, idx_ai_cache_type")

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

    Returns:
        bool: True if rollback succeeded, False otherwise
    """
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(text("DROP INDEX IF EXISTS idx_ai_cache_type"))
                conn.execute(text("DROP INDEX IF EXISTS idx_ai_cache_email_uid"))
                conn.execute(text("DROP TABLE IF EXISTS ai_extraction_cache"))

                trans.commit()
                print("[OK] Rollback completed")

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
    parser = argparse.ArgumentParser(description="Create AI extraction cache table")
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        migrate()
