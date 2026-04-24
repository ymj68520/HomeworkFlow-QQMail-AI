# Email Body Text Display Feature Design

**Date:** 2026-04-24
**Status:** Approved
**Author:** Claude Sonnet

## Overview

Add email body text display to the preview drawer with database caching. The feature extracts and displays plain text email content, removes images, converts HTML to markdown, and caches results in the database for performance.

## Requirements

### Functional Requirements

1. **Email Body Display**: Show email body text in a dedicated card in the preview drawer
2. **Content Type Support**:
   - Prefer plain text over HTML when both available
   - Convert HTML to markdown when only HTML exists
   - Remove all embedded images (`<img>` tags, `cid:` references)
3. **Database Caching**: Store extracted body in database on first access, retrieve from cache on subsequent views
4. **Lazy Loading**: Load body on-demand when preview drawer opens (not during initial table load)

### Non-Functional Requirements

1. **Performance**: First load may be slower (IMAP fetch), subsequent views must be instant (database read)
2. **Encoding**: Properly handle UTF-8 and GBK Chinese character encoding
3. **Error Handling**: Gracefully handle fetch failures, encoding errors, corrupted HTML
4. **UI Responsiveness**: Show loading state during IMAP fetch

## Architecture

### Components

#### 1. Email Body Extractor (`mail/email_body_extractor.py`)

**Purpose**: Extract and process email body text from raw email messages

**Methods**:
```python
class EmailBodyExtractor:
    def extract_body(self, email_message) -> dict:
        """
        Extract email body from email.message.Message

        Returns:
            {
                'plain_text': str,      # Plain text content (or None)
                'html_markdown': str,   # HTML converted to markdown (or None)
                'format': str           # 'text', 'html', or 'both'
            }
        """

    def _extract_plain_text(self, email_message) -> Optional[str]:
        """Extract plain text content from message"""

    def _extract_html_as_markdown(self, email_message) -> Optional[str]:
        """Convert HTML content to markdown using html2text

        Configuration:
        - Ignore links: Keep links inline
        - Ignore images: Remove all images
        - Body width: 0 (no wrapping)
        - Unicode characters: Preserve
        """

    def _remove_images(self, text: str) -> str:
        """Remove <img> tags and cid: references from text"""
```

**Dependencies**:
- `email` (standard library)
- `html2text` for HTML to markdown conversion

#### 2. Database Schema Update

**Migration**: `migrations/add_email_body_column.py`

Add column to `submissions` table:
```sql
ALTER TABLE submissions ADD COLUMN email_body TEXT;
-- JSON format: {"plain_text": "...", "html_markdown": "...", "format": "text/html"}
```

**New Database Methods** (`database/operations.py`):
```python
def save_email_body(submission_id: int, body_data: dict) -> bool:
    """Save or update email body JSON in database"""

def get_email_body(submission_id: int) -> Optional[dict]:
    """Retrieve email body JSON from database"""
```

#### 3. Enhanced Email Parser (`mail/parser.py`)

**Update**:
```python
class MailParser:
    def parse_email(self, email_uid: str) -> Optional[Dict]:
        """
        Enhanced to include email body extraction

        Returns:
            {
                # ... existing fields ...
                'email_body': dict  # From EmailBodyExtractor
            }
        """
```

#### 4. Preview Drawer Enhancement (`gui/email_preview_drawer.py`)

**New Card**:
```python
def _setup_ui(self):
    # ... existing cards ...

    # Card 5: Email Body (NEW)
    self.card_email_body = self._create_card("邮件正文")
    self.card_email_body.pack(fill="x", pady=(0, 15))

def _update_email_body_card(self, data: StudentData) -> None:
    """Update email body card with text content"""
    # Check database cache
    body_data = db.get_email_body(data['id'])

    if body_data:
        # Display cached content
        self._display_body_text(body_data)
    else:
        # Show loading state
        self._show_body_loading()

        # Fetch from IMAP in background
        self.after(10, self._load_email_body_from_imap, data)
```

**UI Components**:
- Scrollable text area for long content
- Loading indicator during IMAP fetch
- Error message display on failure
- Empty state when no body available

## Data Flow

### First Access (Cache Miss)

```
User double-clicks row
    ↓
Preview drawer opens
    ↓
_check_email_body_in_database(submission_id)
    → Returns NULL
    ↓
Show "正在从服务器加载邮件正文..."
    ↓
Fetch email from IMAP server
    ↓
EmailBodyExtractor.extract_body(message)
    → Extract plain text OR
    → Convert HTML to markdown
    → Remove all images
    ↓
db.save_email_body(submission_id, body_data)
    ↓
Display body text in card
```

### Subsequent Access (Cache Hit)

```
User double-clicks row
    ↓
Preview drawer opens
    ↓
_check_email_body_in_database(submission_id)
    → Returns JSON data
    ↓
Display body text immediately
```

## Implementation Details

### Email Body Extraction Strategy

1. **Walk message parts**: Iterate through `email_message.walk()`
2. **Check content type**:
   - `text/plain`: Use directly
   - `text/html`: Convert to markdown using `html2text`
   - `multipart/*`: Recurse into parts
3. **Remove images**:
   - Strip `<img>` tags from HTML before conversion
   - Remove `cid:` (Content-ID) references from plain text
4. **Clean whitespace**:
   - Normalize line breaks
   - Trim excess whitespace
   - Handle Chinese character encoding (UTF-8, GBK)

### Database Storage Format

```json
{
    "plain_text": "这是邮件正文内容...",
    "html_markdown": "# 标题\n\n这是从HTML转换的内容...",
    "format": "both"  // or "text", "html"
}
```

### Display Priority

1. If `plain_text` exists: Display it
2. Else if `html_markdown` exists: Display it
3. Else: Show "暂无邮件正文内容"

### Error Handling

| Scenario | Handling |
|----------|----------|
| IMAP fetch failed | Show "无法加载邮件正文：网络错误" |
| Encoding error | Show "邮件正文编码错误" |
| HTML conversion failed | Show "HTML转换失败，尝试显示原文" |
| Database save failed | Show content anyway, log error |
| Empty email body | Show "此邮件没有正文内容" |

## UI Design

### Email Body Card Layout

```
┌─────────────────────────────────────────┐
│ 邮件正文                                │
├─────────────────────────────────────────┤
│                                         │
│ [Scrollable text area]                  │
│                                         │
│ 这是邮件的正文内容...                   │
│                                         │
│ 支持中文显示                            │
│                                         │
│                                         │
└─────────────────────────────────────────┘
```

### Loading State

```
┌─────────────────────────────────────────┐
│ 邮件正文                                │
├─────────────────────────────────────────┤
│ ⏳ 正在从服务器加载邮件正文...          │
└─────────────────────────────────────────┘
```

### Error State

```
┌─────────────────────────────────────────┐
│ 邮件正文                                │
├─────────────────────────────────────────┤
│ ⚠️ 无法加载邮件正文                     │
│ 网络连接失败，请稍后重试                │
└─────────────────────────────────────────┘
```

## Dependencies

### New Dependencies

Add to `requirements.txt`:
```
html2text==2020.1.16
```

### Existing Dependencies

- `email` (standard library) - Email parsing
- `customtkinter` - UI components
- `sqlite3` (standard library) - Database storage

## Testing Strategy

### Unit Tests

1. **EmailBodyExtractor**:
   - Test plain text extraction
   - Test HTML to markdown conversion
   - Test image removal
   - Test encoding handling (UTF-8, GBK)

2. **Database operations**:
   - Test saving email body
   - Test retrieving email body
   - Test JSON serialization/deserialization

### Integration Tests

1. **End-to-end flow**:
   - Load preview drawer
   - Fetch email from IMAP
   - Extract body
   - Save to database
   - Display in UI

2. **Cache behavior**:
   - First access (IMAP fetch)
   - Second access (database read)

### Manual Tests

1. Test with plain text emails
2. Test with HTML emails
3. Test with emails containing embedded images
4. Test with Chinese characters
5. Test with very long email bodies (scrolling)
6. Test error scenarios (network failure, encoding errors)

## Migration Plan

### Phase 1: Database Schema

1. Create migration script `migrations/add_email_body_column.py`
2. Run migration to add `email_body` column
3. Verify schema update

### Phase 2: Backend Implementation

1. Create `EmailBodyExtractor` class
2. Update `MailParser.parse_email()` to extract body
3. Add database methods `save_email_body()`, `get_email_body()`
4. Write unit tests

### Phase 3: UI Implementation

1. Add email body card to preview drawer
2. Implement display logic
3. Implement loading states
4. Handle errors gracefully

### Phase 4: Integration

1. Connect UI to backend
2. Test end-to-end flow
3. Performance testing
4. Bug fixes

## Rollout Plan

1. Deploy database migration (low risk, additive change)
2. Deploy backend code (backward compatible, no UI impact)
3. Deploy UI changes (visible to users)
4. Monitor logs for errors
5. Gather user feedback

## Future Enhancements

1. **Search functionality**: Search within email bodies
2. **Export**: Export email body as text file
3. **Formatting options**: Toggle between plain text and markdown views
4. **Attachment preview**: Show attachment metadata in body
5. **Full email view**: Option to view raw email source

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| HTML conversion fails | Medium | Fallback to showing raw HTML stripped of tags |
| Large email bodies | Medium | Implement text truncation with "Show more" button |
| Database storage grows | Low | Email bodies are text-only, minimal storage impact |
| Encoding errors | Medium | Try multiple encodings (UTF-8, GBK), show error on failure |
| Performance degradation | Low | Only load body when preview opens, not during table load |
