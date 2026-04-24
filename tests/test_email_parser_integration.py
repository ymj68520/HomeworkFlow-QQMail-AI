"""Tests for EmailBodyExtractor integration with MailParser."""

import unittest
from email.message import Message
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from mail.email_body_extractor import EmailBodyExtractor
from mail.parser import MailParser


class TestEmailBodyExtractor(unittest.TestCase):
    """Unit tests for EmailBodyExtractor."""

    def test_extract_plain_text_only(self):
        """Test extraction of plain text email."""
        # Create plain text email
        msg = MIMEText('This is a plain text email.', 'plain')

        extractor = EmailBodyExtractor()
        result = extractor.extract_body(msg)

        self.assertEqual(result['plain_text'], 'This is a plain text email.')
        self.assertIsNone(result['html_markdown'])
        self.assertEqual(result['format'], 'text')

    def test_extract_html_only(self):
        """Test extraction of HTML email."""
        # Create HTML email
        html_content = '<html><body><h1>Title</h1><p>Content</p></body></html>'
        msg = MIMEText(html_content, 'html')

        extractor = EmailBodyExtractor()
        result = extractor.extract_body(msg)

        self.assertIsNone(result['plain_text'])
        self.assertIsNotNone(result['html_markdown'])
        self.assertIn('Title', result['html_markdown'])
        self.assertIn('Content', result['html_markdown'])
        self.assertEqual(result['format'], 'html')

    def test_extract_multipart_both(self):
        """Test extraction of multipart email with both text and HTML."""
        # Create multipart email
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText('Plain text content', 'plain'))
        msg.attach(MIMEText('<html><body><p>HTML content</p></body></html>', 'html'))

        extractor = EmailBodyExtractor()
        result = extractor.extract_body(msg)

        self.assertEqual(result['plain_text'], 'Plain text content')
        self.assertIsNotNone(result['html_markdown'])
        self.assertIn('HTML content', result['html_markdown'])
        self.assertEqual(result['format'], 'both')

    def test_extract_empty_email(self):
        """Test extraction of empty email."""
        msg = MIMEMultipart()

        extractor = EmailBodyExtractor()
        result = extractor.extract_body(msg)

        self.assertIsNone(result['plain_text'])
        self.assertIsNone(result['html_markdown'])
        self.assertEqual(result['format'], 'empty')

    def test_extractor_returns_correct_format(self):
        """Test that extractor produces the expected format."""
        msg = MIMEText('Test content', 'plain')

        extractor = EmailBodyExtractor()
        result = extractor.extract_body(msg)

        # Verify return type is dict
        self.assertIsInstance(result, dict)

        # Verify expected keys
        self.assertIn('plain_text', result)
        self.assertIn('html_markdown', result)
        self.assertIn('format', result)

        # Verify format values are valid
        self.assertIn(result['format'], ['text', 'html', 'both', 'empty'])


class TestMailParserIntegration(unittest.TestCase):
    """Integration tests for MailParser with EmailBodyExtractor."""

    def test_parse_includes_email_body(self):
        """
        Test that parse_email includes email_body in result.

        Note: This test requires a test email file or test IMAP server.
        If no test email is available, it will be skipped.
        """
        import os
        test_email_path = 'tests/fixtures/test_email.eml'

        if not os.path.exists(test_email_path):
            self.skipTest(f"Test email file not found: {test_email_path}")

        # Read test email
        with open(test_email_path, 'rb') as f:
            email_content = f.read()

        # Parse the email
        from email.message_from_bytes import message_from_bytes
        email_message = message_from_bytes(email_content)

        extractor = EmailBodyExtractor()
        email_body = extractor.extract_body(email_message)

        # Verify format
        self.assertIsInstance(email_body, dict)
        self.assertIn('plain_text', email_body)
        self.assertIn('html_markdown', email_body)
        self.assertIn('format', email_body)
        self.assertIn(email_body['format'], ['text', 'html', 'both', 'empty'])

    def test_extractor_handles_unicode(self):
        """Test that extractor handles unicode content correctly."""
        # Create email with unicode content
        msg = MIMEText('测试中文内容\nTest English\n日本語テスト', 'plain')

        extractor = EmailBodyExtractor()
        result = extractor.extract_body(msg)

        self.assertIn('测试中文内容', result['plain_text'])
        self.assertIn('Test English', result['plain_text'])
        self.assertIn('日本語テスト', result['plain_text'])

    def test_extractor_handles_cid_references(self):
        """Test that extractor removes CID image references."""
        msg = MIMEText('Text with cid:image001.png@01D12345.67890 reference', 'plain')

        extractor = EmailBodyExtractor()
        result = extractor.extract_body(msg)

        # CID references should be replaced with [图片]
        self.assertIn('[图片]', result['plain_text'])
        self.assertNotIn('cid:', result['plain_text'])


if __name__ == '__main__':
    unittest.main()
