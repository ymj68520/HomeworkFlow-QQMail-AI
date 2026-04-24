"""Unit tests for EmailBodyExtractor class."""

import pytest
import email
from email.message import EmailMessage, Message
from mail.email_body_extractor import EmailBodyExtractor


class TestEmailBodyExtractor:
    """Test suite for EmailBodyExtractor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = EmailBodyExtractor()

    def test_extract_plain_text_simple(self):
        """Test extracting simple plain text email."""
        # Create a simple plain text email
        msg = EmailMessage()
        msg.set_content('This is a simple plain text email.')

        result = self.extractor.extract_body(msg)

        assert result['plain_text'] == 'This is a simple plain text email.'
        assert result['html_markdown'] is None
        assert result['format'] == 'text'

    def test_extract_plain_text_with_cid(self):
        """Test extracting plain text with CID references."""
        msg = EmailMessage()
        msg.set_content('Please see the image: cid:image123@abc and also cid:image456@def')

        result = self.extractor.extract_body(msg)

        assert result['plain_text'] == 'Please see the image: [图片] and also [图片]'
        assert result['html_markdown'] is None
        assert result['format'] == 'text'

    def test_extract_html_to_markdown(self):
        """Test extracting HTML and converting to markdown."""
        msg = EmailMessage()
        html_content = '<h1>Hello</h1><p>This is a <strong>test</strong> email.</p>'
        msg.set_content(html_content, subtype='html')

        result = self.extractor.extract_body(msg)

        assert result['plain_text'] is None
        assert result['html_markdown'] is not None
        assert '# Hello' in result['html_markdown']
        assert 'test' in result['html_markdown']
        assert result['format'] == 'html'

    def test_extract_both_text_and_html(self):
        """Test extracting multipart email with both text and HTML."""
        # Create multipart message
        msg = EmailMessage()

        # Add plain text part
        text_part = EmailMessage()
        text_part.set_content('Plain text version')
        msg.attach(text_part)

        # Add HTML part
        html_part = EmailMessage()
        html_part.set_content('<p>HTML version</p>', subtype='html')
        msg.attach(html_part)

        result = self.extractor.extract_body(msg)

        assert result['plain_text'] == 'Plain text version'
        assert result['html_markdown'] is not None
        assert 'HTML version' in result['html_markdown']
        assert result['format'] == 'both'

    def test_remove_html_images(self):
        """Test that HTML img tags are removed."""
        msg = EmailMessage()
        html_content = '<p>Text before</p><img src="cid:image123" /><p>Text after</p>'
        msg.set_content(html_content, subtype='html')

        result = self.extractor.extract_body(msg)

        assert result['html_markdown'] is not None
        assert '<img' not in result['html_markdown']
        assert 'Text before' in result['html_markdown']
        assert 'Text after' in result['html_markdown']

    def test_empty_email(self):
        """Test handling of empty email."""
        msg = EmailMessage()

        result = self.extractor.extract_body(msg)

        assert result['plain_text'] is None
        assert result['html_markdown'] is None
        assert result['format'] == 'empty'

    def test_chinese_characters(self):
        """Test handling of Chinese characters."""
        msg = EmailMessage()
        chinese_text = '这是一封中文邮件，包含中文内容。'
        msg.set_content(chinese_text)

        result = self.extractor.extract_body(msg)

        assert result['plain_text'] == chinese_text
        assert result['format'] == 'text'
