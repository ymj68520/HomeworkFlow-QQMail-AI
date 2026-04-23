# Batch Retry Unknown Extraction - Design Spec

**Date:** 2026-04-23
**Status:** Design Approved
**Type:** Feature Enhancement

## Overview

Add a post-processing batch retry phase to improve AI extraction accuracy. When individual email processing returns Unknown (null/None) values for required fields (`student_id`, `name`, `assignment_name`), collect these emails and retry them together in a single batch AI call. This provides more context to the AI and improves extraction success rates.

## Problem Statement

Currently, when AI extraction returns `None/null` for any required field, the email is immediately marked as read and skipped. This fails to leverage the fact that analyzing multiple emails together can provide better context and improve extraction accuracy through pattern recognition.

## Solution

Add a two-phase extraction process:
1. **Individual Phase**: Process each email independently (existing behavior)
2. **Batch Retry Phase**: Collect all emails with Unknown results and retry them together in one AI call

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Individual Processing                     │
│  (Process each email through extract_student_info)           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├─→ Complete Info ✓ ──→ Continue Normal Flow
                       │
                       └─→ Unknown Fields ⚠ ──→ Add to pending_retry[]
                                                        │
                                                        │
┌───────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────┐
│                    Batch Retry Phase                         │
│  (After all individual processing completes)                 │
│  1. Check if pending_retry is not empty                      │
│  2. Call ai_extractor.batch_retry_unknown(pending_retry)     │
│  3. Re-process any emails with now-complete info             │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. New Method: `AIExtractor.batch_retry_unknown()`

**Location:** `ai/extractor.py`

**Signature:**
```python
async def batch_retry_unknown(
    self,
    email_list: List[Dict]
) -> List[Dict]:
```

**Input:**
```python
[
    {
        'uid': str,
        'subject': str,
        'from': str,
        'attachments': List[Dict],
        'previous_result': Dict  # The failed extraction
    },
    ...
]
```

**Output:**
```python
[
    {
        'student_id': str or None,
        'name': str or None,
        'assignment_name': str or None,
        'is_assignment': bool,
        'confidence': float,
        'reasoning': str
    },
    ...
]
```

**Responsibilities:**
- Format all emails into a structured batch prompt
- Make single AI call for all emails
- Parse batch response and return results in same order as input
- Handle batch size limits (max 20 emails per batch)

**Implementation Notes:**
- Use same `SYSTEM_PROMPT` as regular extraction
- Construct user prompt showing all emails together:
  ```
  Please extract student information from these emails that failed initial extraction:

  Email 1:
  Subject: {subject}
  From: {sender}
  Attachments: {attachments}

  Email 2:
  Subject: {subject}
  From: {sender}
  Attachments: {attachments}

  ...

  Return a JSON array with extraction results for each email in order.
  ```
- If batch size > 20, split into multiple API calls
- Use same temperature=0.1 and response_format={"type": "json_object"}

#### 2. Modifications: `AssignmentWorkflow` Class

**Location:** `core/workflow.py`

**Changes:**

**a. Add instance variable:**
```python
def __init__(self):
    # ... existing code ...
    self.pending_retry = []  # Track emails needing batch retry
```

**b. Modify `process_new_email()` method:**

After AI extraction (around line 72), add Unknown detection:

```python
# 3. AI提取学生信息
print("Extracting student info using AI...")
student_info = await self.ai.extract_student_info(...)

# NEW: Check for Unknown fields
has_unknown = (
    not student_info.get('student_id') or
    not student_info.get('name') or
    not student_info.get('assignment_name')
)

if has_unknown and student_info.get('is_assignment'):
    # Add to pending batch retry
    self.pending_retry.append({
        'uid': email_uid,
        'subject': email_data['subject'],
        'from': email_data['from'],
        'attachments': email_data['attachments'],
        'previous_result': student_info,
        'email_data': email_data  # Store full data for re-processing
    })
    print(f"Added to batch retry list (Unknown fields detected)")
```

Continue with existing flow (will mark as read if missing required info).

**c. Add new method `process_pending_retry()`:**

```python
async def process_pending_retry(self) -> dict:
    """
    Process emails with Unknown extraction results using batch retry

    Returns:
        Results summary with counts of successful retries
    """
    if not self.pending_retry:
        print("No emails pending batch retry")
        return {'total': 0, 'retry_success': 0, 'retry_failed': 0}

    print(f"\n{'='*50}")
    print(f"Batch Retry Phase: {len(self.pending_retry)} emails")
    print(f"{'='*50}")

    results = {
        'total': len(self.pending_retry),
        'retry_success': 0,
        'retry_failed': 0
    }

    try:
        # Call batch retry
        retry_results = await self.ai.batch_retry_unknown(self.pending_retry)

        # Process each result
        for i, (email_info, new_result) in enumerate(zip(self.pending_retry, retry_results)):
            email_uid = email_info['uid']

            # Check if extraction improved
            if (new_result.get('student_id') and
                new_result.get('name') and
                new_result.get('assignment_name')):

                print(f"✓ Batch retry succeeded for {email_uid}")
                print(f"  student_id={new_result['student_id']}")
                print(f"  name={new_result['name']}")
                print(f"  assignment={new_result['assignment_name']}")

                # Re-process through workflow
                # Note: Need to extract workflow logic into separate method to avoid recursion
                results['retry_success'] += 1

            else:
                print(f"✗ Batch retry still failed for {email_uid}")
                results['retry_failed'] += 1

        print(f"\nBatch retry complete:")
        print(f"  Total: {results['total']}")
        print(f"  Succeeded: {results['retry_success']}")
        print(f"  Still failed: {results['retry_failed']}")
        print(f"{'='*50}\n")

    except Exception as e:
        print(f"Error in batch retry: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clear pending list
        self.pending_retry = []

    return results
```

**d. Modify `process_inbox()` method:**

After processing all individual emails (before the summary print), add:

```python
# Process emails with Unknown results
await self.process_pending_retry()
```

**e. Extract workflow logic to avoid recursion:**

To allow re-processing emails without infinite recursion, extract the core processing logic (steps 5-13 from `process_new_email()`) into a separate method:

```python
async def _process_extracted_info(
    self,
    email_uid: str,
    email_data: Dict,
    student_info: Dict
) -> dict:
    """
    Process email with already-extracted student info
    (Steps 5-13 from process_new_email)
    """
    # Steps 5-13 from existing process_new_email()
    # ...
```

Then both `process_new_email()` and `process_pending_retry()` can call this method.

## Data Structures

### Pending Retry Item
```python
{
    'uid': str,                    # Email UID
    'subject': str,                # Email subject
    'from': str,                   # Sender info
    'attachments': List[Dict],     # Attachments
    'previous_result': Dict,       # Failed extraction result
    'email_data': Dict             # Full email data for re-processing
}
```

### Batch Retry Result
```python
{
    'total': int,                  # Total emails retried
    'retry_success': int,          # Successfully fixed
    'retry_failed': int            # Still have Unknown fields
}
```

## Error Handling

### Batch Retry API Failures
- **Timeout**: Log error, keep emails marked as read, clear pending_retry
- **Invalid JSON response**: Log error, keep emails marked as read
- **Network error**: Log error, keep emails marked as read

### Batch Size Handling
- If pending_retry > 20 emails, split into multiple batches
- Process each batch sequentially
- Aggregate all results before re-processing

### Re-processing Safety
- Before re-processing, check if email already moved to target folder
- Skip re-processing if UID no longer exists in INBOX
- Add duplicate detection to prevent double-processing
- If re-processing fails partway through, continue with remaining emails

### Edge Cases
- **Empty pending_retry**: Skip batch phase, log "No emails pending batch retry"
- **All succeed**: Re-process all, clear pending_retry
- **All fail**: Log failure, clear pending_retry, stay marked as read
- **Partial success**: Only re-process successful ones

## Testing Strategy

### Unit Tests

**Test: `batch_retry_unknown()`**
- Empty list → returns empty list
- Single email → returns one result
- Multiple emails (5) → returns 5 results in order
- Large batch (25 emails) → splits into 2 API calls
- API timeout → handles gracefully, returns results with None values

**Test: Batch prompt generation**
- Verify prompt structure includes all email info
- Verify previous results are mentioned for context
- Verify JSON array format request

**Test: Batch splitting logic**
- 20 emails → 1 batch
- 21 emails → 2 batches (20 + 1)
- 45 emails → 3 batches (20 + 20 + 5)

### Integration Tests

**Test: Full workflow with Unknown emails**
1. Create 3 mock emails with missing fields
2. Run `process_inbox()`
3. Verify all 3 added to pending_retry
4. Verify batch_retry_unknown called once
5. Verify re-processing of successful ones

**Test: Mixed good and bad emails**
1. Create 5 emails (2 good, 3 bad)
2. Run workflow
3. Verify 2 processed normally
4. Verify 3 go to batch retry
5. Verify batch retry called once

**Test: Re-processing safety**
1. Create email that goes to batch retry
2. Manually move it to target folder before batch phase
3. Run batch retry
4. Verify email skipped (not duplicated)

### Manual Testing Scenarios

**Scenario 1: Multiple emails with different missing fields**
- Email 1: Missing student_id
- Email 2: Missing name
- Email 3: Missing assignment_name
- Expected: Batch fixes at least 2 out of 3

**Scenario 2: No clear information even in batch**
- Emails with very obscure subjects
- Expected: All still fail, marked as read

**Scenario 3: Empty batch retry**
- All emails process successfully individually
- Expected: Batch phase skipped

**Scenario 4: Large batch**
- 30 emails with Unknown fields
- Expected: Split into 2 batches, results aggregated

### Performance Metrics

Add logging for:
- `pending_retry_count`: Number of emails in each batch
- `batch_retry_duration`: Time taken for batch API call
- `retry_improvement_rate`: (Success after batch) / (Total in batch)
- `batch_api_tokens_used`: Token consumption

## Success Criteria

- [ ] Unknown emails are collected during individual processing
- [ ] Batch retry is called after all individual processing
- [ ] Successfully re-extracted emails are fully processed
- [ ] Failed batch retries don't crash the workflow
- [ ] Unit tests cover batch_retry_unknown method
- [ ] Integration tests cover full workflow with retry
- [ ] Manual testing confirms improvement in extraction rate
- [ ] Performance metrics logged for monitoring

## Future Enhancements

1. **Adaptive batching**: Adjust batch size based on historical success rates
2. **Confidence threshold**: Include emails with low confidence (not just None) in batch retry
3. **Learning from patterns**: Store successful batch patterns to improve individual extraction
4. **Manual review queue**: For emails that fail both individual and batch extraction

## Open Questions

None at this time.
