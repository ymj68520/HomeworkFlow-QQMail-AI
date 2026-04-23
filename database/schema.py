import sqlite3
from pathlib import Path
from config.settings import settings

def init_database():
    """Initialize database with all tables"""
    db_path = settings.DATABASE_PATH
    db_path.parent.mkdir(exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
            email_uid VARCHAR(100) UNIQUE NOT NULL,
            email_subject TEXT,
            sender_email VARCHAR(100),
            sender_name VARCHAR(100),
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

    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_assignment ON submissions(assignment_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_late ON submissions(is_late)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_log_uid ON email_log(email_uid)')

    conn.commit()
    conn.close()

    print(f"Database initialized at {db_path}")

def create_ai_extraction_cache_table():
    """Create AI extraction cache table"""
    from database.models import SessionLocal
    from sqlalchemy import text

    session = SessionLocal()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_extraction_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid VARCHAR(255) UNIQUE NOT NULL,
                student_id VARCHAR(50),
                name VARCHAR(100),
                assignment_name VARCHAR(50),
                confidence FLOAT,
                is_fallback BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_email_uid
            ON ai_extraction_cache(email_uid)
        """))

        session.commit()
        print("[OK] Created ai_extraction_cache table")
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Failed to create cache table: {e}")
        raise
    finally:
        session.close()

if __name__ == '__main__':
    init_database()
