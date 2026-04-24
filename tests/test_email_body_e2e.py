"""
End-to-End Integration Tests for Email Body Feature.

This module tests the complete workflow:
1. Extract email body from email message
2. Save to database
3. Retrieve from database
4. Verify format consistency throughout
"""

import pytest
import json
import tempfile
import os
import sqlite3
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime

from mail.email_body_extractor import EmailBodyExtractor
from database.operations import DatabaseOperations
from database.schema import init_database
from config.settings import settings


@pytest.fixture
def test_db():
    """Create a temporary test database with email_body column."""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

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
    try:
        os.unlink(db_path)
    except PermissionError:
        pass  # Windows file locking issue


@pytest.fixture
def db_ops(test_db):
    """Create DatabaseOperations instance that uses test database."""
    return DatabaseOperations()


@pytest.fixture
def sample_submission(db_ops, test_db):
    """Create a sample submission in the test database."""
    # Use raw SQL to create submission
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

    # Create submission
    submission_time = datetime.now().isoformat()
    cursor.execute(
        """INSERT INTO submissions
           (student_id, assignment_id, email_uid, email_subject, sender_email,
            sender_name, submission_time, local_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (student_id, assignment_id, "test@example.com/12345", "测试作业提交",
         "test@example.com", "张三", submission_time, "/tmp/test.zip")
    )

    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return submission_id


class TestEmailBodyE2E:
    """End-to-end integration tests for email body feature."""

    def test_extractor_output_format(self):
        """
        Unit Test: Verify JSON serializable format.

        Test that extractor output can be serialized to JSON and
        deserialized back without data loss.
        """
        extractor = EmailBodyExtractor()

        # Create test email with both plain text and HTML
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText('Plain text content with 中文', 'plain'))
        msg.attach(MIMEText(
            '<html><body><h1>HTML Title</h1><p>HTML content with <strong>formatting</strong></p></body></html>',
            'html'
        ))

        # Extract body
        body_data = extractor.extract_body(msg)

        # Verify structure
        assert isinstance(body_data, dict)
        assert 'plain_text' in body_data
        assert 'html_markdown' in body_data
        assert 'format' in body_data

        # Verify can serialize to JSON
        try:
            json_str = json.dumps(body_data, ensure_ascii=False)
            assert isinstance(json_str, str)
            assert len(json_str) > 0
        except (TypeError, ValueError) as e:
            pytest.fail(f"Failed to serialize to JSON: {e}")

        # Verify can deserialize back
        try:
            deserialized_data = json.loads(json_str)
            assert isinstance(deserialized_data, dict)

            # Verify data integrity after round-trip
            assert deserialized_data['plain_text'] == body_data['plain_text']
            assert deserialized_data['html_markdown'] == body_data['html_markdown']
            assert deserialized_data['format'] == body_data['format']
        except (TypeError, ValueError) as e:
            pytest.fail(f"Failed to deserialize from JSON: {e}")

    def test_extractor_output_format_with_chinese(self):
        """
        Unit Test: Verify JSON serializable format with Chinese characters.

        Test that Chinese characters are properly preserved during
        JSON serialization and deserialization.
        """
        extractor = EmailBodyExtractor()

        # Create test email with Chinese content
        msg = MIMEText('这是一封包含中文、日本語、한국어的邮件。', 'plain')

        # Extract body
        body_data = extractor.extract_body(msg)

        # Verify can serialize to JSON with ensure_ascii=False
        json_str = json.dumps(body_data, ensure_ascii=False)

        # Verify Chinese characters are preserved (not escaped)
        assert '中文' in json_str
        assert '日本語' in json_str
        assert '한국어' in json_str

        # Verify can deserialize and data is intact
        deserialized_data = json.loads(json_str)
        assert deserialized_data['plain_text'] == body_data['plain_text']
        assert '中文' in deserialized_data['plain_text']

    def test_extractor_output_format_with_special_characters(self):
        """
        Unit Test: Verify JSON serializable format with special characters.

        Test that special characters, quotes, and emoji are properly handled.
        """
        extractor = EmailBodyExtractor()

        # Create test email with special characters
        text_content = """
        Email with special characters:
        - Double quotes: "test"
        - Single quotes: 'test'
        - Emoji: 😀 🎉 🚀
        - Math symbols: x² + y² = z²
        - Unicode: α, β, γ, δ
        """
        msg = MIMEText(text_content, 'plain')

        # Extract body
        body_data = extractor.extract_body(msg)

        # Verify can serialize to JSON
        json_str = json.dumps(body_data, ensure_ascii=False)

        # Verify can deserialize
        deserialized_data = json.loads(json_str)

        # Verify special characters are preserved
        assert '"test"' in deserialized_data['plain_text']
        assert "'test'" in deserialized_data['plain_text']
        assert '😀' in deserialized_data['plain_text']
        assert 'x²' in deserialized_data['plain_text']

    def test_full_workflow_plain_text(self, db_ops, sample_submission):
        """
        Integration Test: Full workflow with plain text email.

        Workflow:
        1. Create email message with plain text
        2. Extract body using EmailBodyExtractor
        3. Save to database using DatabaseOperations
        4. Retrieve from database
        5. Verify format consistency
        """
        extractor = EmailBodyExtractor()

        # Step 1: Create email message
        msg = MIMEText('This is a plain text email for testing full workflow.', 'plain')

        # Step 2: Extract body
        extracted_body = extractor.extract_body(msg)
        assert extracted_body['format'] == 'text'
        assert extracted_body['plain_text'] is not None
        assert extracted_body['html_markdown'] is None

        # Step 3: Save to database
        submission_id = sample_submission
        save_result = db_ops.save_email_body(submission_id, extracted_body)
        assert save_result is True

        # Step 4: Retrieve from database
        retrieved_body = db_ops.get_email_body(submission_id)
        assert retrieved_body is not None

        # Step 5: Verify format consistency
        assert retrieved_body['plain_text'] == extracted_body['plain_text']
        assert retrieved_body['html_markdown'] == extracted_body['html_markdown']
        assert retrieved_body['format'] == extracted_body['format']

    def test_full_workflow_html_email(self, db_ops, sample_submission):
        """
        Integration Test: Full workflow with HTML email.

        Workflow:
        1. Create email message with HTML content
        2. Extract body (converts HTML to markdown)
        3. Save to database
        4. Retrieve from database
        5. Verify format consistency
        """
        extractor = EmailBodyExtractor()

        # Step 1: Create HTML email
        html_content = '''
        <html>
        <body>
            <h1>作业提交</h1>
            <p>这是<strong>HTML格式</strong>的邮件内容。</p>
            <ul>
                <li>项目1</li>
                <li>项目2</li>
            </ul>
        </body>
        </html>
        '''
        msg = MIMEText(html_content, 'html')

        # Step 2: Extract body
        extracted_body = extractor.extract_body(msg)
        assert extracted_body['format'] == 'html'
        assert extracted_body['plain_text'] is None
        assert extracted_body['html_markdown'] is not None

        # Step 3: Save to database
        submission_id = sample_submission
        save_result = db_ops.save_email_body(submission_id, extracted_body)
        assert save_result is True

        # Step 4: Retrieve from database
        retrieved_body = db_ops.get_email_body(submission_id)
        assert retrieved_body is not None

        # Step 5: Verify format consistency
        assert retrieved_body['plain_text'] == extracted_body['plain_text']
        assert retrieved_body['html_markdown'] == extracted_body['html_markdown']
        assert retrieved_body['format'] == extracted_body['format']

        # Verify HTML was converted to markdown
        assert '作业提交' in retrieved_body['html_markdown']
        assert 'HTML格式' in retrieved_body['html_markdown']
        # html2text converts <ul><li> to "*  item" with indentation
        assert '项目1' in retrieved_body['html_markdown']
        assert '项目2' in retrieved_body['html_markdown']

    def test_full_workflow_multipart_email(self, db_ops, sample_submission):
        """
        Integration Test: Full workflow with multipart email (both text and HTML).

        Workflow:
        1. Create multipart email with both plain text and HTML
        2. Extract body
        3. Save to database
        4. Retrieve from database
        5. Verify both formats are preserved
        """
        extractor = EmailBodyExtractor()

        # Step 1: Create multipart email
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText('Plain text version of the email.', 'plain'))
        msg.attach(MIMEText(
            '<html><body><h1>HTML Version</h1><p>HTML content here.</p></body></html>',
            'html'
        ))

        # Step 2: Extract body
        extracted_body = extractor.extract_body(msg)
        assert extracted_body['format'] == 'both'
        assert extracted_body['plain_text'] is not None
        assert extracted_body['html_markdown'] is not None

        # Step 3: Save to database
        submission_id = sample_submission
        save_result = db_ops.save_email_body(submission_id, extracted_body)
        assert save_result is True

        # Step 4: Retrieve from database
        retrieved_body = db_ops.get_email_body(submission_id)
        assert retrieved_body is not None

        # Step 5: Verify both formats are preserved
        assert retrieved_body['plain_text'] == extracted_body['plain_text']
        assert retrieved_body['html_markdown'] == extracted_body['html_markdown']
        assert retrieved_body['format'] == 'both'

    def test_full_workflow_with_chinese_content(self, db_ops, sample_submission):
        """
        Integration Test: Full workflow with Chinese content.

        Verify that Chinese characters are preserved throughout the entire workflow.
        """
        extractor = EmailBodyExtractor()

        # Step 1: Create email with Chinese content
        msg = MIMEText('学生张三提交了作业1。请查收附件。', 'plain')

        # Step 2: Extract body
        extracted_body = extractor.extract_body(msg)

        # Step 3: Save to database
        submission_id = sample_submission
        save_result = db_ops.save_email_body(submission_id, extracted_body)
        assert save_result is True

        # Step 4: Retrieve from database
        retrieved_body = db_ops.get_email_body(submission_id)

        # Step 5: Verify Chinese characters are preserved
        assert retrieved_body is not None
        assert '张三' in retrieved_body['plain_text']
        assert '作业1' in retrieved_body['plain_text']
        assert '请查收附件' in retrieved_body['plain_text']

    def test_full_workflow_update_body(self, db_ops, sample_submission):
        """
        Integration Test: Full workflow with body update.

        Verify that updating email body works correctly.
        """
        extractor = EmailBodyExtractor()

        # Step 1: Create and save initial email body
        msg1 = MIMEText('Initial email content.', 'plain')
        initial_body = extractor.extract_body(msg1)

        submission_id = sample_submission
        save_result = db_ops.save_email_body(submission_id, initial_body)
        assert save_result is True

        # Verify initial content
        retrieved = db_ops.get_email_body(submission_id)
        assert retrieved['plain_text'] == 'Initial email content.'

        # Step 2: Update with new content
        msg2 = MIMEText('Updated email content with new information.', 'plain')
        updated_body = extractor.extract_body(msg2)

        save_result = db_ops.save_email_body(submission_id, updated_body)
        assert save_result is True

        # Step 3: Verify update
        retrieved = db_ops.get_email_body(submission_id)
        assert retrieved['plain_text'] == 'Updated email content with new information.'
        assert retrieved['plain_text'] != 'Initial email content.'

    def test_full_workflow_with_cid_references(self, db_ops, sample_submission):
        """
        Integration Test: Full workflow with CID image references.

        Verify that CID references are properly handled throughout the workflow.
        """
        extractor = EmailBodyExtractor()

        # Step 1: Create email with CID references
        msg = MIMEText('Please see the image: cid:image001.png@01D12345 and another: cid:image002.jpg')
        extracted_body = extractor.extract_body(msg)

        # Step 2: Verify CID references were replaced
        assert '[图片]' in extracted_body['plain_text']
        assert 'cid:' not in extracted_body['plain_text']

        # Step 3: Save to database
        submission_id = sample_submission
        save_result = db_ops.save_email_body(submission_id, extracted_body)
        assert save_result is True

        # Step 4: Retrieve from database
        retrieved_body = db_ops.get_email_body(submission_id)

        # Step 5: Verify CID replacements are preserved
        assert retrieved_body is not None
        assert '[图片]' in retrieved_body['plain_text']
        assert 'cid:' not in retrieved_body['plain_text']

    def test_full_workflow_empty_email(self, db_ops, sample_submission):
        """
        Integration Test: Full workflow with empty email.

        Verify that empty emails are handled correctly.
        """
        extractor = EmailBodyExtractor()

        # Step 1: Create empty email
        msg = EmailMessage()
        extracted_body = extractor.extract_body(msg)

        # Step 2: Verify empty format
        assert extracted_body['format'] == 'empty'
        assert extracted_body['plain_text'] is None
        assert extracted_body['html_markdown'] is None

        # Step 3: Save to database
        submission_id = sample_submission
        save_result = db_ops.save_email_body(submission_id, extracted_body)
        assert save_result is True

        # Step 4: Retrieve from database
        retrieved_body = db_ops.get_email_body(submission_id)

        # Step 5: Verify empty format is preserved
        assert retrieved_body is not None
        assert retrieved_body['format'] == 'empty'
        assert retrieved_body['plain_text'] is None
        assert retrieved_body['html_markdown'] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
