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

        # Submission groups table (must exist before submissions due to FK)
        cursor.execute('''
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
        ''')

        # Submissions table (包含ORM模型所需的全部字段)
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
                status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                error_message TEXT,
                local_path TEXT,
                version INTEGER DEFAULT 1 NOT NULL,
                is_latest BOOLEAN DEFAULT TRUE,
                parent_id INTEGER,
                relation_type VARCHAR(20),
                is_primary BOOLEAN DEFAULT TRUE NOT NULL,
                group_id INTEGER,
                group_order INTEGER DEFAULT 0 NOT NULL,
                processing_status TEXT DEFAULT 'received',
                ai_status TEXT DEFAULT 'pending',
                download_status TEXT DEFAULT 'pending',
                reply_status TEXT DEFAULT 'pending',
                processing_status_updated_at TIMESTAMP,
                ai_status_updated_at TIMESTAMP,
                download_status_updated_at TIMESTAMP,
                reply_status_updated_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (assignment_id) REFERENCES assignments(id),
                FOREIGN KEY (parent_id) REFERENCES submissions(id),
                FOREIGN KEY (group_id) REFERENCES submission_groups(id)
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

        # Status history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                status_type TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                reason TEXT,
                extra_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            )
        ''')

        # AI extraction cache table
        cursor.execute('''
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
        ''')

        # File operations log table
        cursor.execute('''
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
        ''')

        # Attachment validation rules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachment_validation_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name VARCHAR(50) UNIQUE NOT NULL,
                allowed_extensions TEXT NOT NULL,
                extension_categories TEXT,
                max_file_size_mb FLOAT NOT NULL,
                max_total_size_mb FLOAT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 插入默认附件验证规则（如果不存在）
        cursor.execute("SELECT COUNT(*) FROM attachment_validation_rules WHERE rule_name = 'default'")
        if cursor.fetchone()[0] == 0:
            import json
            default_extensions = json.dumps([
                ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
                ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
                ".zip", ".rar", ".7z", ".tar", ".gz"
            ])
            cursor.execute('''
                INSERT INTO attachment_validation_rules
                (rule_name, allowed_extensions, max_file_size_mb, max_total_size_mb, is_active)
                VALUES (?, ?, ?, ?, ?)
            ''', ('default', default_extensions, 25.0, 100.0, True))

        # Create base indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_student ON submissions(student_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_assignment ON submissions(assignment_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_message_id ON submissions(message_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_late ON submissions(is_late)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_log_uid ON email_log(email_uid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_group_id ON submissions(group_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_parent ON submissions(parent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_relation ON submissions(relation_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_primary ON submissions(is_primary)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_processing ON submissions(processing_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_ai ON submissions(ai_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_download ON submissions(download_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submissions_reply ON submissions(reply_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status_history_submission ON status_history(submission_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status_history_type ON status_history(status_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status_history_created ON status_history(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_cache_email_uid ON ai_extraction_cache(email_uid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_cache_type ON ai_extraction_cache(cache_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_ops_submission ON file_operations_log(submission_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_ops_status ON file_operations_log(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submission_groups_email_uid ON submission_groups(email_uid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_submission_groups_message_id ON submission_groups(message_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attachment_rules_active ON attachment_validation_rules(is_active)')

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

