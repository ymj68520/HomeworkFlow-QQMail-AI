"""
Test database methods for email body storage and retrieval.

Tests the save_email_body() and get_email_body() methods added to
DatabaseOperations class.
"""

import pytest
import tempfile
import os
import sqlite3
from pathlib import Path


@pytest.fixture
def test_db():
    """Create a temporary test database"""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize test database
    from database.schema import init_database
    from config.settings import settings

    # Save original database path
    original_db_path = settings.DATABASE_PATH

    # Override database path to test database
    settings.DATABASE_PATH = Path(db_path)

    # Initialize database schema
    init_database()

    # Add email_body column (migration)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(submissions)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]

    if 'email_body' not in column_names:
        cursor.execute("ALTER TABLE submissions ADD COLUMN email_body TEXT")
        conn.commit()
    conn.close()

    yield db_path

    # Cleanup: restore original path and delete test database
    settings.DATABASE_PATH = original_db_path
    # Close any open connections
    try:
        os.unlink(db_path)
    except PermissionError:
        pass  # Windows file locking issue


@pytest.fixture
def sample_submission(test_db):
    """Create a sample submission using raw SQL for testing"""
    # Use raw SQL to create submission since ORM uses wrong database
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Create student
    cursor.execute(
        "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?)",
        ("2024001", "张三", "test@example.com")
    )

    # Create assignment
    cursor.execute(
        "INSERT INTO assignments (name) VALUES (?)",
        ("作业1",)
    )

    # Get IDs
    cursor.execute("SELECT id FROM students WHERE student_id = ?", ("2024001",))
    student_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM assignments WHERE name = ?", ("作业1",))
    assignment_id = cursor.fetchone()[0]

    # Create submission (use only columns that exist in base schema)
    from datetime import datetime
    submission_time = datetime.now().isoformat()

    cursor.execute(
        """INSERT INTO submissions
           (student_id, assignment_id, email_uid, email_subject, sender_email, sender_name, submission_time, local_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (student_id, assignment_id, "test@example.com/12345", "测试作业提交", "test@example.com", "张三", submission_time, "/tmp/test.zip")
    )

    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return submission_id


@pytest.fixture
def db_ops(test_db):
    """Create DatabaseOperations instance that uses test database"""
    from database.operations import DatabaseOperations
    # Need to ensure the db ops uses the test database
    # We'll do this by making sure settings.DATABASE_PATH points to test_db
    return DatabaseOperations()


def test_save_and_get_email_body(db_ops, sample_submission):
    """Test saving and retrieving email body data"""
    submission_id = sample_submission

    # Sample body data
    body_data = {
        'plain_text': 'This is a plain text email body.',
        'html_markdown': '# HTML Email\n\nThis is **formatted** text.',
        'format': 'both'
    }

    # Save email body
    result = db_ops.save_email_body(submission_id, body_data)
    assert result is True, "save_email_body should return True on success"

    # Retrieve email body
    retrieved_data = db_ops.get_email_body(submission_id)
    assert retrieved_data is not None, "get_email_body should return data"

    # Verify data integrity
    assert retrieved_data['plain_text'] == body_data['plain_text']
    assert retrieved_data['html_markdown'] == body_data['html_markdown']
    assert retrieved_data['format'] == body_data['format']


def test_get_nonexistent_body(db_ops):
    """Test retrieving email body with invalid ID returns None"""
    # Try to get email body for non-existent submission
    result = db_ops.get_email_body(99999)
    assert result is None, "get_email_body should return None for non-existent ID"


def test_update_email_body(db_ops, sample_submission):
    """Test updating existing email body"""
    submission_id = sample_submission

    # Initial body data
    initial_body = {
        'plain_text': 'Initial text',
        'html_markdown': '**Initial markdown**',
        'format': 'html_only'
    }

    # Save initial email body
    result = db_ops.save_email_body(submission_id, initial_body)
    assert result is True

    # Retrieve and verify
    retrieved = db_ops.get_email_body(submission_id)
    assert retrieved['plain_text'] == 'Initial text'

    # Update with new data
    updated_body = {
        'plain_text': 'Updated text',
        'html_markdown': '**Updated markdown**',
        'format': 'both'
    }

    result = db_ops.save_email_body(submission_id, updated_body)
    assert result is True

    # Retrieve and verify update
    retrieved = db_ops.get_email_body(submission_id)
    assert retrieved['plain_text'] == 'Updated text'
    assert retrieved['html_markdown'] == '**Updated markdown**'
    assert retrieved['format'] == 'both'


def test_save_body_with_chinese(db_ops, sample_submission):
    """Test saving and retrieving email body with Chinese characters"""
    submission_id = sample_submission

    # Body data with Chinese characters
    body_data = {
        'plain_text': '这是一封中文邮件。包含简体中文字符。',
        'html_markdown': '# 中文标题\n\n这是**粗体**文字和*斜体*文字。',
        'format': 'both'
    }

    # Save email body with Chinese characters
    result = db_ops.save_email_body(submission_id, body_data)
    assert result is True, "save_email_body should handle Chinese characters"

    # Retrieve and verify Chinese characters are preserved
    retrieved_data = db_ops.get_email_body(submission_id)
    assert retrieved_data is not None
    assert retrieved_data['plain_text'] == body_data['plain_text']
    assert retrieved_data['html_markdown'] == body_data['html_markdown']

    # Verify specific Chinese characters
    assert '中文邮件' in retrieved_data['plain_text']
    assert '简体中文' in retrieved_data['plain_text']
    assert '中文标题' in retrieved_data['html_markdown']
    assert '粗体' in retrieved_data['html_markdown']


def test_save_body_with_special_characters(db_ops, sample_submission):
    """Test saving email body with special characters and emoji"""
    submission_id = sample_submission

    # Body data with special characters
    body_data = {
        'plain_text': 'Email with quotes: "test" and \'single\' and emoji 😀',
        'html_markdown': '# Markdown\n\nCode: `code block`\n\nMath: x² + y² = z²',
        'format': 'both'
    }

    # Save and retrieve
    result = db_ops.save_email_body(submission_id, body_data)
    assert result is True

    retrieved_data = db_ops.get_email_body(submission_id)
    assert retrieved_data is not None
    assert retrieved_data['plain_text'] == body_data['plain_text']
    assert 'emoji' in retrieved_data['plain_text']
    assert 'x²' in retrieved_data['html_markdown']


def test_get_email_body_after_deletion(db_ops, sample_submission, test_db):
    """Test getting email body after submission is deleted"""
    submission_id = sample_submission

    # Save email body
    body_data = {
        'plain_text': 'Test text',
        'html_markdown': '**Test**',
        'format': 'both'
    }
    db_ops.save_email_body(submission_id, body_data)

    # Verify it exists
    retrieved = db_ops.get_email_body(submission_id)
    assert retrieved is not None

    # Delete the submission using raw SQL (since ORM uses wrong DB)
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))
    conn.commit()
    conn.close()

    # Try to get email body - should return None
    retrieved = db_ops.get_email_body(submission_id)
    assert retrieved is None, "get_email_body should return None after submission deletion"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
