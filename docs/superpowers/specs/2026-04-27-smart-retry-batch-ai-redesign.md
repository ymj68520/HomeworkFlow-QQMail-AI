# Smart Retry & Batch AI Re-analysis Design

**Date:** 2026-04-27
**Author:** Claude Code
**Status:** Approved

## Overview

This design adds two new features to the QQ email assignment collection system:

1. **Smart Retry (智能重试)** - Re-run complete analysis workflow for abnormal entries
2. **Batch AI Re-analysis (批量AI重析)** - Re-analyze selected entries using AI with fresh IMAP content

## Requirements

### Feature 1: Smart Retry (智能重试)

**Target Status:** All non-success status types
- `ai_error` (识别异常)
- `download_failed` (下载失败)
- `pending` (未处理)

**Workflow:**
1. Scan current page for entries with target statuses
2. For each entry:
   - Re-fetch email from IMAP (TARGET_FOLDER or INBOX fallback)
   - Re-run complete workflow (AI extraction, deduplication, storage, DB update)
   - Handle duplicate submission cases
3. Update UI to reflect new statuses
4. Show progress dialog with count of processed entries

**Error Handling:**
- Skip entries that no longer exist in IMAP
- Log errors for individual entries without stopping batch
- Show summary of success/failure counts

### Feature 2: Batch AI Re-analysis (批量AI重析)

**Target:** User-selected entries only (like existing batch operations)

**Workflow:**
1. Validate user has selected at least one entry
2. Show confirmation dialog
3. For each selected entry:
   - Fetch fresh email content from IMAP (prioritize over DB cache)
   - Re-run AI extraction only (not full workflow)
   - Update database with new extraction results
   - Update UI status
4. Show progress dialog
5. Display summary of results

**Data Source Priority:**
1. IMAP server (TARGET_FOLDER)
2. INBOX (if not found in TARGET_FOLDER)
3. Database cache (if IMAP unavailable)

## UI Design

### Sidebar Buttons

Add two new buttons to the sidebar (`gui/components/sidebar.py`):

```python
# New buttons
self.btn_smart_retry = QPushButton("智能重试")
self.btn_batch_reanalyze = QPushButton("批量AI重析")
```

**Button States:**
- Smart Retry: Always enabled (scans current page)
- Batch AI Re-analysis: Only enabled when entries are selected

### Progress Dialog

Create a reusable progress dialog (`gui/components/progress_dialog.py`) to show:
- Current operation description
- Progress bar for batch operations
- Current item being processed
- Cancel button (optional)

## Architecture

### New Components

```
gui/
├── components/
│   ├── progress_dialog.py      # New: reusable progress dialog
│   └── ...
core/
├── retry_handler.py             # New: handles retry logic
└── ...
```

### Core Logic: Retry Handler

Create `core/retry_handler.py` with:

```python
class RetryHandler:
    async def smart_retry_page(self, page_submissions: List[Dict]) -> Dict
    async def batch_reanalyze(self, selected_submissions: List[Dict]) -> Dict
```

### Data Flow

**Smart Retry:**
```
UI → RetryHandler.smart_retry_page()
    → For each entry:
        → Fetch from IMAP
        → workflow.process_new_email() (full pipeline)
    → Return results
← UI updates table
```

**Batch AI Re-analysis:**
```
UI → RetryHandler.batch_reanalyze()
    → For each entry:
        → Fetch from IMAP
        → ai_extractor.extract_student_info()
        → db.update_submission_full()
    → Return results
← UI updates table
```

## Implementation Notes

### IMAP Connection Management

- Reuse existing `mail.connection_manager` for connection pooling
- Ensure connections are available before starting batch operations
- Handle connection errors gracefully

### Database Updates

- Use existing `db.update_submission_full()` for complete updates
- Use existing `db.update_submissions_status_bulk()` for status changes
- Ensure all updates go through write queue

### UI Updates

- Use existing `smart_refresh()` for incremental table updates
- Update status bar with progress
- Show summary dialog on completion

### Error Handling

- Individual entry failures should not stop batch operation
- Log all errors for debugging
- Show user-friendly error messages
- Provide option to view detailed error log

## Testing Strategy

1. **Unit Tests:**
   - Test `RetryHandler` methods with mock IMAP and AI
   - Test database update logic

2. **Integration Tests:**
   - Test with real IMAP connection (test account)
   - Test with various email formats
   - Test error scenarios

3. **UI Tests:**
   - Test button enable/disable states
   - Test progress dialog behavior
   - Test cancellation (if implemented)

## Success Criteria

1. Smart Retry successfully processes all abnormal entries on current page
2. Batch AI Re-analysis correctly re-analyzes selected entries
3. UI remains responsive during operations (threading/async)
4. No duplicate records created during retry
5. Database remains consistent after operations
6. User receives clear feedback on operation results

## Future Enhancements

- Add scheduling for automatic retry of failed entries
- Add filtering options (e.g., retry only entries with specific error types)
- Add undo functionality for batch re-analysis
- Export retry/re-analysis results to CSV
