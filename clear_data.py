import sqlite3
import os
from pathlib import Path
from config.settings import settings

def clear_database():
    db_path = settings.DATABASE_PATH
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return

    print(f"正在清理数据库: {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 禁用外键约束以便清理
        cursor.execute("PRAGMA foreign_keys = OFF")

        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            print(f"  清理表: {table}")
            cursor.execute(f"DELETE FROM {table}")
            # 重置自增 ID
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")

        conn.commit()
        print("✓ 数据库清理完成")
        
    except Exception as e:
        print(f"✗ 清理失败: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    clear_database()
