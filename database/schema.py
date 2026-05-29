import sqlite3
from pathlib import Path
from config.settings import settings

def init_database():
    """Initialize database with all tables and apply all migrations"""
    from database.migration_manager import MigrationManager

    db_path = settings.DATABASE_PATH
    db_path.parent.mkdir(exist_ok=True)

    # Step 1: Create base tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Assignments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) UNIQUE NOT NULL,
                deadline TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Submissions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                message_id VARCHAR(255) UNIQUE,
                email_uid VARCHAR(100) UNIQUE NOT NULL,
                email_subject TEXT,
                sender_email VARCHAR(100),
                sender_name VARCHAR(100),
                body TEXT,
                submission_time TIMESTAMP NOT NULL,
                is_late BOOLEAN DEFAULT FALSE,
                is_downloaded BOOLEAN DEFAULT FALSE,
                is_replied BOOLEAN DEFAULT FALSE,
                local_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (assignment_id) REFERENCES assignments(id)
            )
        ''')

        # Attachments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_size INTEGER,
                local_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            )
        ''')

        # Email log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid VARCHAR(100),
                action VARCHAR(50),
                folder VARCHAR(100),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                error_message TEXT
            )
        ''')

        # Create base indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_assignment ON submissions(assignment_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_message_id ON submissions(message_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_late ON submissions(is_late)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_log_uid ON email_log(email_uid)')

        conn.commit()
        print(f"[OK] Base tables created at {db_path}")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to create base tables: {e}")
        raise
    finally:
        conn.close()

    # Step 2: Apply all pending migrations
    print("[INFO] Applying pending migrations...")
    manager = MigrationManager()
    success, messages = manager.migrate()

    if not success:
        raise RuntimeError("Failed to apply migrations")

    for msg in messages:
        print(msg)

    print(f"\n[SUCCESS] Database initialization completed at {db_path}")

if __name__ == '__main__':
    init_database()

