#!/usr/bin/env python3
"""
Database migration: Rename email_body to body in submissions table
"""

import sqlite3
import os
from pathlib import Path

def migrate(database_path: str) -> bool:
    """
    Rename email_body to body or add body column if missing.
    """
    if not os.path.exists(database_path):
        print(f"[ERROR] Database file not found: {database_path}")
        return False

    try:
        with sqlite3.connect(database_path) as conn:
            cursor = conn.cursor()

            # Check existing columns
            cursor.execute("PRAGMA table_info(submissions)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            if 'body' in column_names:
                print("[INFO] Column 'body' already exists.")
                return True

            if 'email_body' in column_names:
                print("[INFO] Renaming 'email_body' to 'body'...")
                try:
                    cursor.execute("ALTER TABLE submissions RENAME COLUMN email_body TO body")
                    print("[PASS] Renamed 'email_body' to 'body'.")
                except sqlite3.OperationalError:
                    print("[WARN] RENAME COLUMN failed, likely old SQLite. Falling back to copy-and-recreate...")
                    # Fallback for old SQLite (recreate table)
                    # This is complex, but for a single column rename it might be safer to just add a new column
                    cursor.execute("ALTER TABLE submissions ADD COLUMN body TEXT")
                    cursor.execute("UPDATE submissions SET body = email_body")
                    print("[PASS] Added 'body' and copied data from 'email_body'.")
            else:
                print("[INFO] Adding 'body' column...")
                cursor.execute("ALTER TABLE submissions ADD COLUMN body TEXT")
                print("[PASS] Added 'body' column.")

            conn.commit()
            return True

    except sqlite3.Error as e:
        print(f"[ERROR] Migration failed: {e}")
        return False

if __name__ == "__main__":
    db_path = Path("assignment_submissions.db")
    if not db_path.exists():
        db_path = Path(__file__).parent.parent / "assignment_submissions.db"
    
    print(f"[INFO] Migrating {db_path}...")
    if migrate(str(db_path)):
        print("[SUCCESS] Database is ready.")
    else:
        print("[FAILED] Migration failed.")
