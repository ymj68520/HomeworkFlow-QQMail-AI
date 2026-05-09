"""
Migration 001: Add submission_groups table and update submissions table

This migration adds support for multi-assignment submissions by:
1. Creating a new submission_groups table to track emails containing multiple assignments
2. Adding group_id and group_order fields to the submissions table
"""
import sqlite3
import os
from pathlib import Path

# Get database path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_PATH = os.path.join(BASE_DIR, 'assignment_submissions.db')


def upgrade():
    """Apply the migration - add submission_groups table and update submissions"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Create submission_groups table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submission_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid VARCHAR(255) UNIQUE NOT NULL,
                message_id VARCHAR(255),
                email_subject TEXT,
                sender_email VARCHAR(100),
                sender_name VARCHAR(100),
                submission_time DATETIME NOT NULL,
                status VARCHAR(20) DEFAULT 'processing' NOT NULL,
                processing_mode VARCHAR(20) NOT NULL,
                total_assignments INTEGER DEFAULT 0,
                total_attachments INTEGER DEFAULT 0,
                detection_method VARCHAR(50),
                ai_confidence FLOAT,
                error_message TEXT,
                error_details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for submission_groups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submission_groups_email_uid
            ON submission_groups(email_uid)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submission_groups_message_id
            ON submission_groups(message_id)
        """)

        # Add group_id column to submissions table
        cursor.execute("""
            ALTER TABLE submissions
            ADD COLUMN group_id INTEGER REFERENCES submission_groups(id)
        """)

        # Add group_order column to submissions table
        cursor.execute("""
            ALTER TABLE submissions
            ADD COLUMN group_order INTEGER DEFAULT 0 NOT NULL
        """)

        # Create index for group_id
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_group_id
            ON submissions(group_id)
        """)

        conn.commit()
        print("Migration 001 upgrade completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Migration 001 upgrade failed: {e}")
        raise
    finally:
        conn.close()


def downgrade():
    """Rollback the migration - remove submission_groups table and group fields from submissions"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        # Get the schema of the current submissions table
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='submissions'
        """)
        old_schema = cursor.fetchone()[0]

        # Create new submissions table without group_id and group_order
        cursor.execute("""
            CREATE TABLE submissions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                message_id VARCHAR(255) UNIQUE,
                email_uid VARCHAR(100) UNIQUE NOT NULL,
                email_subject TEXT,
                sender_email VARCHAR(100),
                sender_name VARCHAR(100),
                body TEXT,
                submission_time DATETIME NOT NULL,
                is_late BOOLEAN DEFAULT 0,
                is_downloaded BOOLEAN DEFAULT 0,
                is_replied BOOLEAN DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                error_message TEXT,
                local_path TEXT,
                version INTEGER DEFAULT 1 NOT NULL,
                is_latest BOOLEAN DEFAULT 1,
                parent_id INTEGER,
                relation_type VARCHAR(20),
                is_primary BOOLEAN DEFAULT 1 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(assignment_id) REFERENCES assignments(id),
                FOREIGN KEY(parent_id) REFERENCES submissions(id)
            )
        """)

        # Copy data from old table to new table (excluding group_id and group_order)
        cursor.execute("""
            INSERT INTO submissions_new (
                id, student_id, assignment_id, message_id, email_uid, email_subject,
                sender_email, sender_name, body, submission_time, is_late, is_downloaded,
                is_replied, status, error_message, local_path, version, is_latest,
                parent_id, relation_type, is_primary, created_at, updated_at
            )
            SELECT
                id, student_id, assignment_id, message_id, email_uid, email_subject,
                sender_email, sender_name, body, submission_time, is_late, is_downloaded,
                is_replied, status, error_message, local_path, version, is_latest,
                parent_id, relation_type, is_primary, created_at, updated_at
            FROM submissions
        """)

        # Drop old table
        cursor.execute("DROP TABLE submissions")

        # Rename new table
        cursor.execute("ALTER TABLE submissions_new RENAME TO submissions")

        # Recreate indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_student_id
            ON submissions(student_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_assignment_id
            ON submissions(assignment_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_message_id
            ON submissions(message_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_parent_id
            ON submissions(parent_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_relation_type
            ON submissions(relation_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_submissions_is_primary
            ON submissions(is_primary)
        """)

        # Drop submission_groups table
        cursor.execute("DROP TABLE IF EXISTS submission_groups")

        conn.commit()
        print("Migration 001 downgrade completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Migration 001 downgrade failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
