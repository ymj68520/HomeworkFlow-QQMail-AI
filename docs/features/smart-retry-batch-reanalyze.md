# Smart Retry & Batch AI Re-analysis Features

## Overview

This feature adds two new capabilities to the QQ Email Assignment Collection System:

1. **Smart Retry (智能重试)** - Automatically re-process all failed/abnormal submissions on the current page
2. **Batch AI Re-analysis (批量AI重析)** - Manually re-analyze selected submissions using fresh email content

## Smart Retry

### Purpose

Re-run the complete analysis pipeline for entries that failed during initial processing. This is useful for:
- Network issues that caused temporary failures
- AI extraction errors that might succeed on retry
- Incomplete downloads that need retrying

### Target Statuses

The following statuses are considered "abnormal" and will be re-processed:
- `ai_error` (识别异常) - AI failed to extract student information
- `download_failed` (下载失败) - Attachment download failed
- `pending` (未处理) - Entry was not processed

### How to Use

1. Navigate to any page in the submission list
2. Click the "智能重试" (Smart Retry) button in the sidebar
3. Confirm the operation in the dialog
4. A progress dialog shows the retry progress
5. Results summary shows success/failure counts
6. The page automatically refreshes to show updated statuses

### What Happens

For each abnormal entry:
1. Re-fetches the email from IMAP server (TARGET_FOLDER → INBOX fallback)
2. Re-runs the complete workflow:
   - AI extraction
   - Deduplication check
   - Attachment storage
   - Database update
   - Email move to target folder
3. Handles duplicate submissions (creates new version)
4. Updates UI with new status

## Batch AI Re-analysis

### Purpose

Re-extract student information from selected entries using fresh email content. This is useful when:
- AI extraction produced incorrect results
- Student information needs to be updated
- Manual correction of extraction errors

### How to Use

1. Select one or more entries in the table (Ctrl+click for multiple)
2. Click the "批量AI重析" (Batch AI Re-analysis) button
3. Confirm the operation
4. Progress dialog shows re-analysis progress
5. Results summary shows how many succeeded/failed
6. The page refreshes to show updated data

### What Happens

For each selected entry:
1. Fetches fresh email content from IMAP (prioritizes IMAP over database cache)
2. Re-runs AI extraction on the fresh content
3. Updates database with new extraction results
4. Updates status based on extraction quality:
   - Success → `unreplied` (if all fields extracted)
   - Still has issues → `ai_error`

## Technical Details

### Components

- `core/retry_handler.py` - Core logic for retry and re-analysis operations
- `gui/components/progress_dialog.py` - Reusable progress dialog
- `gui/components/sidebar.py` - UI buttons
- `gui/main_window.py` - Button handlers and UI integration

### Thread Safety

All operations run in background threads to keep UI responsive:
- Smart retry uses `threading.Thread` with `asyncio` event loop
- Progress updates use `QTimer.singleShot` for thread-safe UI updates
- IMAP connections are properly managed per thread

### Error Handling

- Individual entry failures don't stop the batch operation
- Summary shows count of successes vs failures
- Detailed error messages for each failed entry
- Graceful handling of missing emails on server

## Troubleshooting

### "No abnormal entries found" message

This means the current page has no entries with abnormal status. Try:
- Changing to a different page
- Adjusting filters to show more entries
- Checking if entries are already in success status

### "Failed to connect to email server"

Check:
- Internet connection is stable
- IMAP credentials are correct in settings
- Mail server is accessible

### Smart retry shows many "skipped" entries

This means emails no longer exist on the server. They may have been:
- Deleted manually
- Moved to a different folder
- Processed and archived

### Batch re-analysis still shows errors

If AI extraction continues to fail:
1. Check the email subject format - should contain student ID and assignment name
2. Verify email has attachments (required for assignment detection)
3. Review AI model configuration in settings
4. Check logs for detailed error messages
