"""Migration: Add status and error_message columns to submissions table"""

import sqlite3
import os

def migrate(database_path: str):
    if not os.path.exists(database_path):
        print(f"[ERROR] Database not found: {database_path}")
        return False

    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute("PRAGMA table_info(submissions)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'status' not in columns:
            cursor.execute("ALTER TABLE submissions ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
            print("[PASS] Added column 'status'")
        
        if 'error_message' not in columns:
            cursor.execute("ALTER TABLE submissions ADD COLUMN error_message TEXT")
            print("[PASS] Added column 'error_message'")

        # 迁移现有数据状态
        # 逻辑：
        # 如果 is_replied = 1 -> completed
        # 如果 is_downloaded = 1 且 is_replied = 0 -> unreplied
        # 其他设为 pending
        cursor.execute("""
            UPDATE submissions 
            SET status = 'completed' 
            WHERE is_replied = 1
        """)
        cursor.execute("""
            UPDATE submissions 
            SET status = 'unreplied' 
            WHERE is_downloaded = 1 AND is_replied = 0 AND (status = 'pending' OR status IS NULL)
        """)

        conn.commit()
        print("[PASS] Successfully updated existing submission statuses")
        return True

    except sqlite3.Error as e:
        print(f"[ERROR] Migration failed: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(project_root, 'assignment_submissions.db')
    
    print(f"Migrating database: {db_path}")
    if migrate(db_path):
        print("Migration completed successfully")
    else:
        print("Migration failed")
