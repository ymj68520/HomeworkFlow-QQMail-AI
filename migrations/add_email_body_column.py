#!/usr/bin/env python3
"""
Database migration: Add email_body column to submissions table

This migration adds a TEXT column named 'email_body' to store extracted
email body content as JSON.
"""

import sqlite3
import os
from pathlib import Path


def migrate(database_path: str) -> bool:
    """
    Add email_body column to submissions table.

    Args:
        database_path: Path to the SQLite database file

    Returns:
        True if migration succeeded, False otherwise
    """
    # Check if database file exists
    if not os.path.exists(database_path):
        print(f"[ERROR] Database file not found: {database_path}")
        return False

    conn = None
    try:
        # Connect to database
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        # Check if email_body column already exists
        cursor.execute("PRAGMA table_info(submissions)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'email_body' in column_names:
            print("[INFO] Column 'email_body' already exists in submissions table")
            return True

        # Add email_body column
        print("[INFO] Adding email_body column to submissions table...")
        cursor.execute("ALTER TABLE submissions ADD COLUMN email_body TEXT")

        # Commit changes
        conn.commit()
        print("[PASS] Added column 'email_body' to submissions table")
        return True

    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
        return False

    finally:
        # Close connection
        if conn:
            conn.close()
            print("[INFO] Database connection closed")


if __name__ == "__main__":
    # Construct path to database (matches config/settings.py DATABASE_PATH)
    script_dir = Path(__file__).parent
    db_path = script_dir.parent / "assignment_submissions.db"

    print(f"[INFO] Starting migration for database: {db_path}")

    # Run migration
    success = migrate(str(db_path))

    if success:
        print("\n[SUCCESS] Migration completed successfully")
    else:
        print("\n[FAILED] Migration failed")
