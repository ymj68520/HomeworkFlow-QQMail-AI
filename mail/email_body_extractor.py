"""Email body extractor for extracting plain text and HTML content from email messages."""

import html2text
import re
from email.message import Message
from typing import Dict, Optional


class EmailBodyExtractor:
    """Extract plain text and HTML content from email messages."""

    def __init__(self):
        """Configure html2text with appropriate settings."""
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True
        self.html_converter.body_width = 0
        self.html_converter.unicode_snob = True

    def extract_body(self, email_message: Message) -> Dict[str, Optional[str]]:
        """
        Extract body content from an email message.

        Args:
            email_message: Email message object from email.message_from_bytes

        Returns:
            Dictionary with keys:
                - plain_text: Plain text content (or None)
                - html_markdown: HTML content converted to markdown (or None)
                - format: 'text', 'html', 'both', or 'empty'
        """
        plain_text = self._extract_plain_text(email_message)
        html_markdown = self._extract_html_as_markdown(email_message)

        # Determine format
        if plain_text and html_markdown:
            format_type = 'both'
        elif plain_text:
            format_type = 'text'
        elif html_markdown:
            format_type = 'html'
        else:
            format_type = 'empty'

        return {
            'plain_text': plain_text,
            'html_markdown': html_markdown,
            'format': format_type
        }

    def _extract_plain_text(self, email_message: Message) -> Optional[str]:
        """
        Extract plain text content from email message.

        Args:
            email_message: Email message object

        Returns:
            Plain text content with cid: references replaced, or None
        """
        try:
            # Check if this is a multipart message
            if email_message.is_multipart():
                # Walk through all parts
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))

                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue

                    # Look for text/plain content
                    if content_type == 'text/plain':
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Decode with UTF-8 and error handling
                            text = payload.decode('utf-8', errors='replace')
                            # Remove cid: references
                            text = self._remove_images(text)
                            return text.strip()
            else:
                # Not multipart, check if it's text/plain
                if email_message.get_content_type() == 'text/plain':
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        text = payload.decode('utf-8', errors='replace')
                        text = self._remove_images(text)
                        return text.strip()

            return None

        except Exception as e:
            print(f"Error extracting plain text: {e}")
            return None

    def _extract_html_as_markdown(self, email_message: Message) -> Optional[str]:
        """
        Extract HTML content and convert to markdown.

        Args:
            email_message: Email message object

        Returns:
            HTML content converted to markdown, or None
        """
        try:
            html_content = None

            # Check if this is a multipart message
            if email_message.is_multipart():
                # Walk through all parts
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))

                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue

                    # Look for text/html content
                    if content_type == 'text/html':
                        payload = part.get_payload(decode=True)
                        if payload:
                            html_content = payload.decode('utf-8', errors='replace')
                            break
            else:
                # Not multipart, check if it's text/html
                if email_message.get_content_type() == 'text/html':
                    payload = email_message.get_payload(decode=True)
                    if payload:
                        html_content = payload.decode('utf-8', errors='replace')

            if not html_content:
                return None

            # Remove HTML images before conversion
            html_content = self._remove_html_images(html_content)

            # Convert HTML to markdown
            markdown = self.html_converter.handle(html_content)

            # Clean up whitespace
            markdown = markdown.strip()

            return markdown if markdown else None

        except Exception as e:
            print(f"Error extracting HTML as markdown: {e}")
            return None

    def _remove_images(self, text: str) -> str:
        """
        Remove image references from text.

        Args:
            text: Text content

        Returns:
            Text with cid: references replaced with [图片]
        """
        # Replace cid: references with [图片]
        text = re.sub(r'cid:[^\s<>"]+', '[图片]', text)
        return text

    def _remove_html_images(self, html: str) -> str:
        """
        Remove HTML img tags from content.

        Args:
            html: HTML content

        Returns:
            HTML with img tags removed
        """
        # Remove HTML img tags
        html = re.sub(r'<img[^>]*>', '', html, flags=re.IGNORECASE)
        # Also replace cid: references in attributes
        html = re.sub(r'cid:[^\s<>"]+', '[图片]', html)
        return html
