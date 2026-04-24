# Email Body Feature Documentation

## Overview

The Email Body feature enables users to view the full text content of emails directly in the preview drawer. This feature automatically extracts email body content, converts HTML to readable markdown, removes embedded images, and caches results in the database for optimal performance.

## Features

### 1. **Automatic Content Extraction**
- Extracts plain text and HTML content from emails
- Supports multipart messages with both text and HTML
- Handles various email encodings (UTF-8, GBK)
- Processes complex multipart MIME structures

### 2. **HTML to Markdown Conversion**
- Converts HTML emails to readable markdown format
- Preserves links, headings, and formatting
- Uses `html2text` library for high-quality conversion
- Removes all embedded images for cleaner display

### 3. **Image Removal**
- Strips `<img>` tags from HTML content
- Removes `cid:` (Content-ID) references from plain text
- Replaces image references with `[图片]` placeholder
- Prevents display issues with embedded images

### 4. **Database Caching**
- First access: Fetches from IMAP server (slower)
- Subsequent access: Loads from database (instant)
- Stores content in JSON format for flexibility
- Significantly improves UI responsiveness

### 5. **Chinese Character Support**
- Properly handles UTF-8 and GBK encodings
- Preserves Chinese characters in conversion
- Error handling for encoding issues
- Tested with various Chinese content scenarios

### 6. **Lazy Loading**
- Loads body content only when preview drawer opens
- Does not impact initial table load performance
- Shows loading state during IMAP fetch
- Non-blocking UI operations

## Usage Instructions

### Viewing Email Body

1. **Open Preview Drawer**
   - Double-click any email row in the main table
   - Preview drawer slides in from the right

2. **View Email Body**
   - Scroll to the "邮件正文" (Email Body) card
   - Content loads automatically (cached or from server)
   - Use scroll bar to read long emails

3. **Loading States**
   - First access: Shows "正在从服务器加载邮件正文..." (Loading from server...)
   - Subsequent access: Displays content immediately
   - Error state: Shows error message if loading fails

### Content Display Priority

1. **Plain Text** - Displayed if available (preferred format)
2. **HTML as Markdown** - Displayed if only HTML exists
3. **Empty** - Shows "此邮件没有正文内容" (No body content)

## Technical Details

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Preview Drawer UI                     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  邮件正文 (Email Body Card)                      │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  [Scrollable Text Area]                          │   │
│  │  Email content displayed here                    │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
                  Lazy loading trigger
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Database Cache Check                       │
│                                                         │
│  Is email_body in submissions table?                   │
│    YES → Return cached JSON                            │
│    NO  → Fetch from IMAP                               │
└─────────────────────────────────────────────────────────┘
                          ↓
                   (Cache Miss)
                          ↓
┌─────────────────────────────────────────────────────────┐
│              EmailBodyExtractor                         │
│                                                         │
│  1. Parse email.message.Message                        │
│  2. Extract plain text OR HTML                         │
│  3. Convert HTML to markdown                           │
│  4. Remove images and cid: references                  │
│  5. Return JSON with all formats                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Database Storage                           │
│                                                         │
│  Save to submissions.email_body column:                │
│  {                                                      │
│    "plain_text": "...",                                │
│    "html_markdown": "...",                             │
│    "format": "text/html/both/empty"                    │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

### Database Schema

**Table:** `submissions`

**Column:** `email_body` (TEXT, nullable)

**JSON Format:**
```json
{
  "plain_text": "Plain text content or null",
  "html_markdown": "# Markdown converted from HTML\n\nContent...",
  "format": "text" | "html" | "both" | "empty"
}
```

**Format Types:**
- `text`: Email contains only plain text
- `html`: Email contains only HTML
- `both`: Email contains both plain text and HTML
- `empty`: Email has no body content

### EmailBodyExtractor Class

**Location:** `mail/email_body_extractor.py`

**Methods:**

```python
class EmailBodyExtractor:
    def extract_body(self, email_message: Message) -> Dict[str, Optional[str]]:
        """
        Main extraction method.

        Args:
            email_message: email.message.Message object

        Returns:
            {
                'plain_text': str or None,
                'html_markdown': str or None,
                'format': 'text' | 'html' | 'both' | 'empty'
            }
        """

    def _extract_plain_text(self, email_message: Message) -> Optional[str]:
        """Extract plain text content from email."""

    def _extract_html_as_markdown(self, email_message: Message) -> Optional[str]:
        """Extract HTML and convert to markdown."""

    def _remove_images(self, text: str) -> str:
        """Remove cid: references from plain text."""

    def _remove_html_images(self, html: str) -> str:
        """Remove <img> tags from HTML."""
```

**Configuration (html2text):**
- `ignore_links = False` - Keep links inline
- `ignore_images = True` - Remove all images
- `body_width = 0` - No line wrapping
- `unicode_snob = True` - Preserve Unicode characters

### Database Operations

**Location:** `database/operations.py`

**Methods:**

```python
def save_email_body(submission_id: int, body_data: dict) -> bool:
    """
    Save email body JSON to database.

    Args:
        submission_id: Submission record ID
        body_data: Dictionary from EmailBodyExtractor.extract_body()

    Returns:
        True if successful, False otherwise
    """

def get_email_body(submission_id: int) -> Optional[dict]:
    """
    Retrieve email body JSON from database.

    Args:
        submission_id: Submission record ID

    Returns:
        Dictionary with body data or None if not found
    """
```

### Integration Points

1. **MailParser** (`mail/parser.py`)
   - Enhanced `parse_email()` to extract body
   - Returns email body in parsed email data

2. **Preview Drawer** (`gui/email_preview_drawer.py`)
   - Added "邮件正文" card
   - Lazy loading on drawer open
   - Loading states and error handling

3. **Database Migration** (`migrations/add_email_body_column.py`)
   - Adds `email_body` column to `submissions` table
   - Safe migration (nullable column)

## Troubleshooting

### Issue: Email body shows "正在从服务器加载..." indefinitely

**Possible Causes:**
1. IMAP server connection slow or timeout
2. Network connectivity issues
3. Large email body taking time to process

**Solutions:**
- Check internet connection
- Wait longer (large emails may take 10-30 seconds)
- Close and reopen preview drawer to retry
- Check application logs for IMAP errors

### Issue: Email body displays "无法加载邮件正文"

**Possible Causes:**
1. IMAP fetch failed (network error)
2. Email deleted from server
3. Encoding error (corrupted email)

**Solutions:**
- Verify email still exists on server
- Check network connectivity
- Review application logs for specific error
- Try viewing email in email client to verify

### Issue: Chinese characters display as garbled text

**Possible Causes:**
1. Encoding detection failed
2. Email uses unsupported encoding
3. Database encoding issue

**Solutions:**
- Most encoding issues are handled automatically
- Check if email displays correctly in other email clients
- Report issue if reproducible with specific email

### Issue: HTML formatting looks incorrect

**Possible Causes:**
1. Complex HTML structure
2. CSS styles not supported in markdown
3. Malformed HTML in original email

**Solutions:**
- HTML to markdown is best-effort conversion
- Some complex formatting may not translate perfectly
- Plain text version (if available) may be more readable
- Consider viewing original email in client if critical

### Issue: Embedded images still show

**Possible Causes:**
1. Image references in unexpected format
2. New image embedding technique not handled

**Solutions:**
- Most image references are removed automatically
- Report issue with sample email for improvement
- Use `[图片]` placeholder as indication of removed images

### Issue: Database storage growing too large

**Possible Causes:**
1. Many emails with large bodies cached
2. JSON storage overhead

**Solutions:**
- Email bodies are text-only (no images)
- Typical email body: 1-10 KB
- 1000 emails ≈ 1-10 MB database growth
- Database can be cleaned by deleting old submissions

### Issue: Performance degradation when opening preview

**Possible Causes:**
1. Many uncached emails (first access)
2. Slow IMAP server
3. Network latency

**Solutions:**
- First access is always slower (IMAP fetch)
- Subsequent views use cache (instant)
- Consider pre-warming cache by viewing emails during off-hours
- Check IMAP server response time

## Testing

### Unit Tests

**Test Files:**
- `tests/test_email_body_extractor.py` - EmailBodyExtractor class tests
- `tests/test_database_body_methods.py` - Database operations tests
- `tests/test_email_body_e2e.py` - End-to-end workflow tests

**Run Tests:**
```bash
pytest tests/test_email_body_extractor.py -v
pytest tests/test_database_body_methods.py -v
pytest tests/test_email_body_e2e.py -v
```

**Test Coverage:**
- Plain text extraction
- HTML to markdown conversion
- Image removal (HTML and plain text)
- Chinese character handling
- Empty email handling
- Multipart messages
- Database save/retrieve operations
- JSON serialization
- Special characters and encoding

### Manual Testing Checklist

- [ ] View plain text email
- [ ] View HTML-only email
- [ ] View multipart email (text + HTML)
- [ ] View email with embedded images
- [ ] View email with Chinese characters
- [ ] View very long email (scrolling)
- [ ] Test cache behavior (open same email twice)
- [ ] Test loading state (slow connection)
- [ ] Test error handling (disconnect network)
- [ ] Test empty email (no body)

## Dependencies

**Python Packages:**
- `html2text==2020.1.16` - HTML to markdown conversion

**Standard Library:**
- `email` - Email message parsing
- `re` - Regular expressions for image removal

**Existing Dependencies:**
- `customtkinter` - UI components
- `sqlalchemy` - Database operations

## Performance Metrics

### Typical Performance

- **First Access (IMAP):** 2-10 seconds
  - Depends on email size and network speed
  - Includes IMAP fetch, parsing, conversion

- **Subsequent Access (Cache):** <100ms
  - Database read is nearly instant
  - No network overhead

- **Email Body Size:** 1-10 KB (text only)
  - HTML converted to markdown is compact
  - Images removed, no binary data

### Database Impact

- **Storage:** ~1-10 MB per 1000 emails
- **Query Time:** <50ms for cached body
- **Index:** No additional indexes needed (uses existing submission ID)

## Future Enhancements

### Planned Features

1. **Search in Email Bodies**
   - Full-text search across all email content
   - Filter by keyword in body

2. **Export Email Body**
   - Export as .txt or .md file
   - Copy to clipboard button

3. **Format Toggle**
   - Switch between plain text and markdown views
   - View raw HTML source

4. **Attachment Preview in Body**
   - Show attachment list inline
   - Quick access to attachment metadata

5. **Text Truncation with "Show More"**
   - Display first N characters
   - Expand to show full content
   - Better performance for very long emails

### Known Limitations

1. **HTML Formatting**
   - Complex HTML may not convert perfectly
   - CSS styles not preserved
   - Some layouts may look different

2. **Embedded Images**
   - All images are removed (by design)
   - Cannot view embedded images in preview
   - Use attachment viewer for image files

3. **Rich Text**
   - RTF (Rich Text Format) not supported
   - Falls back to plain text if conversion fails

4. **Digital Signatures**
   - Signatures not validated
   - Signature content shown as text

## Support

### Getting Help

1. **Check Logs:** Review application logs for error messages
2. **Documentation:** Read this documentation and user guides
3. **Test:** Run unit tests to verify feature working
4. **Report:** Include email sample (redacted) when reporting issues

### Related Documentation

- [Email Preview User Guide](EMAIL_PREVIEW_USER_GUIDE.md) - How to use preview drawer
- [Deployment Guide](DEPLOYMENT.md) - Setup and configuration
- [Quick Start](QUICKSTART.md) - Getting started with the system

## Changelog

### Version 1.0 (2026-04-24)
- Initial implementation
- Email body extraction and display
- HTML to markdown conversion
- Database caching
- Image removal
- Chinese character support
- Lazy loading
- Comprehensive testing
