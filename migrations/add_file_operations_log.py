"""添加文件操作日志表和索引"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
from pathlib import Path
from config.settings import settings


def upgrade():
    """执行Schema升级"""
    conn = sqlite3.connect(str(settings.DATABASE_PATH))
    cursor = conn.cursor()

    try:
        # 创建文件操作日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_operations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                operation_type VARCHAR(50) NOT NULL,
                file_path TEXT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
            )
        """)

        # 创建复合索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_student_assignment_latest
            ON submissions(student_id, assignment_id, is_latest)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_student_assignment_version
            ON submissions(student_id, assignment_id, version)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_submission
            ON file_operations_log(submission_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_ops_status
            ON file_operations_log(status)
        """)

        conn.commit()
        print("Migration completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def downgrade():
    """回滚变更"""
    conn = sqlite3.connect(str(settings.DATABASE_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("DROP INDEX IF EXISTS idx_file_ops_status")
        cursor.execute("DROP INDEX IF EXISTS idx_file_ops_submission")
        cursor.execute("DROP INDEX IF EXISTS idx_submissions_student_assignment_version")
        cursor.execute("DROP INDEX IF EXISTS idx_submissions_student_assignment_latest")
        cursor.execute("DROP TABLE IF EXISTS file_operations_log")

        conn.commit()
        print("Rollback completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Rollback failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'down':
        downgrade()
    else:
        upgrade()
