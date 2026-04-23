# AI Extraction Refactor Design

**Date:** 2026-04-23
**Status:** Design Approved
**Priority:** High

## Overview

Refactor regex-based data extraction to use AI consistently across the codebase, using regex only for validation and sanitization of AI outputs.

### Problem Statement

The current system uses AI for extraction in `ai/extractor.py` but falls back to regex when AI fails. Other files (`target_folder_loader.py`, `backfill_database.py`, `fix_assignment_names.py`) use direct regex without AI at all, leading to:

- Brittle pattern matching that fails on format variations
- Inconsistent extraction quality across the codebase
- Difficulty handling international names and unusual formats
- Manual intervention required for edge cases

### Solution

Replace all regex-based extraction with AI while keeping regex for validation/sanitization only. Implement caching and batch processing to address performance concerns.

## Architecture

### Data Flow

```
Email Data → Check Cache → Cache Hit? → Return cached data
              ↓
            Cache Miss → AI Extractor (async) → Validate (regex) → Save to Cache → Return data
              ↓
            AI Fails → Regex Fallback (mark is_fallback=True) → Save to Cache
```

### Components

1. **Database Cache Table** - Persistent storage for AI extraction results
2. **Enhanced AIExtractor** - Batch processing, cache integration, fallback handling
3. **Refactored Extraction Methods** - Replace regex with AI in target files

## Database Schema

### New Table: `ai_extraction_cache`

```sql
CREATE TABLE ai_extraction_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_uid VARCHAR(255) UNIQUE NOT NULL,
    student_id VARCHAR(50),
    name VARCHAR(100),
    assignment_name VARCHAR(50),
    confidence FLOAT,
    is_fallback BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_uid ON ai_extraction_cache(email_uid);
```

**Purpose:** Cache AI extraction results to avoid repeated API calls for the same email.

**Fields:**
- `email_uid` - Unique identifier from IMAP
- `is_fallback` - TRUE if result came from regex fallback (for quality tracking)
- `confidence` - AI confidence score (0-1)

## Enhanced AIExtractor

### New Methods

1. **`async extract_with_cache(email_data: Dict) -> Dict`**
   - Check cache for existing result
   - Return cached result or call AI
   - Save new results to cache

2. **`async batch_extract(email_list: List[Dict]) -> List[Dict]`**
   - Process multiple emails concurrently using `asyncio.gather()`
   - Return results in same order as input
   - Handle partial failures gracefully

3. **`save_to_cache(email_uid: str, result: Dict, is_fallback: bool)`**
   - Insert or update cache record
   - Handle database errors gracefully

4. **`get_from_cache(email_uid: str) -> Optional[Dict]`**
   - Retrieve cached extraction result
   - Return None if not found

### Interface

```python
result = await ai_extractor.extract_with_cache(email_data)
# Returns: {
#   'student_id': str,
#   'name': str,
#   'assignment_name': str,
#   'is_fallback': bool,
#   'confidence': float
# }
```

### Validation (Regex Only)

Regex is kept ONLY for validating and sanitizing AI outputs:
- Extract digits from student_id strings
- Validate name formats (Chinese, English, mixed)
- Normalize assignment names to "作业1/2/3/4" format

## File Refactoring

### File 1: `target_folder_loader.py` (Priority 1)

**Current:** `_extract_from_email()` uses regex extraction

**New:**
```python
async def _extract_from_email(self, email_data) -> Dict:
    result = await ai_extractor.extract_with_cache(email_data)

    return {
        'id': None,
        'student_id': result['student_id'],
        'name': result['name'],
        'email': email_data.get('from', ''),
        'assignment_name': result['assignment_name'],
        'submission_time': self._parse_date(email_data.get('date')),
        'is_late': False,
        'is_downloaded': False,
        'is_replied': False,
        'local_path': None,
        'is_ai_extraction': not result['is_fallback'],  # Track quality
    }
```

**Changes:**
- Remove all regex patterns (lines 147-194)
- Use AI extractor with cache
- Track whether result came from AI or fallback

### File 2: `backfill_database.py` (Priority 2)

**Current:** Sequential regex extraction loop

**New:**
```python
async def backfill_with_ai():
    # Batch process emails in groups of 10
    batch_size = 10
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i+batch_size]
        results = await ai_extractor.batch_extract(batch)

        # Process results and save to database
        for email_data, result in zip(batch, results):
            save_to_database(email_data, result)
```

**Changes:**
- Replace regex extraction loop with batch AI calls
- Process emails concurrently for better performance
- Mark fallback records for quality tracking

### File 3: `fix_assignment_names.py` (Priority 3)

**Current:** Regex patterns to extract correct assignment number

**New:**
```python
async def extract_correct_assignment(email_subject: str) -> str:
    email_data = {'subject': email_subject, 'from': '', 'attachments': []}
    result = await ai_extractor.extract_with_cache(email_data)
    return result['assignment_name']
```

**Changes:**
- Remove regex patterns (lines 95-119)
- Use AI to understand context and extract assignment
- Leverage cache for repeated email subjects

## Error Handling

### AI Failures

- **Timeout** → Fallback to regex, mark `is_fallback=True`
- **API Error** → Fallback to regex, mark `is_fallback=True`
- **Invalid JSON** → Fallback to regex, mark `is_fallback=True`

### Validation Failures

- **Student ID format invalid** → Set to `None`, reduce confidence by 30%
- **Name format invalid** → Set to `None`, reduce confidence by 30%
- **Assignment name can't normalize** → Return raw value, log warning

### Cache Failures

- **Database error** → Log warning, continue without cache
- **Cache collision** → Update existing record with `updated_at` timestamp

### Logging Strategy

- Log all fallback occurrences for quality monitoring
- Log cache hits/misses for performance tracking
- Log validation failures for debugging
- Include `is_fallback` flag in database records

## Performance Considerations

### Async Batch Processing

- Use `asyncio.gather()` for concurrent AI calls
- Batch size of 10 emails per request to balance speed and API limits
- Process emails in parallel during backfill operations

### Caching Strategy

- Check cache before calling AI (avoids redundant API calls)
- Persistent cache survives restarts
- Cache key: `email_uid` (unique identifier)
- No TTL - cache is valid indefinitely since emails don't change

### Expected Performance

- **Cache Hit:** ~1ms (database lookup)
- **Cache Miss (AI):** ~500ms-2s (API call)
- **Cache Miss (Fallback):** ~1ms (regex)
- **Batch Processing:** Near-linear speedup with concurrent calls

## Testing Strategy

### Unit Tests

1. Test AIExtractor cache integration (hit/miss scenarios)
2. Test batch processing with mock AI responses
3. Test regex validation still works correctly
4. Test fallback behavior with simulated failures (timeout, error, invalid JSON)

### Integration Tests

1. Test `target_folder_loader.py` with real emails from database
2. Test cache persistence across application restarts
3. Test concurrent batch processing under load
4. Test fallback marking in database records

### Quality Tests

1. Compare AI vs regex extraction accuracy on historical data
2. Measure cache hit rates in production usage
3. Track fallback percentages (target: <5%)
4. Performance benchmarks: AI vs regex vs cached AI

### Test Data

- Use existing real emails from database
- Include edge cases: missing fields, unusual formats, international names
- Test both Chinese and English names
- Test various assignment name formats

## Migration Strategy

### Phase 1: Infrastructure (Week 1)
1. Create `ai_extraction_cache` table
2. Enhance AIExtractor with new methods
3. Add unit tests for cache and batch processing

### Phase 2: GUI Integration (Week 1)
4. Refactor `target_folder_loader.py`
5. Test with GUI in development
6. Monitor fallback rates and cache performance

### Phase 3: Bulk Processing (Week 2)
7. Refactor `backfill_database.py`
8. Run backfill on existing emails
9. Validate results and fix any issues

### Phase 4: Maintenance Scripts (Week 2)
10. Refactor `fix_assignment_names.py`
11. Run one-time fix for existing bad records
12. Clean up old regex patterns

### Rollback Plan

- Keep regex fallback code for safety
- Can revert to old extraction methods if issues arise
- Cache table can be dropped without affecting core functionality
- Git allows easy rollback of code changes

## Success Metrics

### Quality Metrics
- Fallback rate < 5% (most extractions use AI)
- Extraction accuracy > 95% (measured on test data)
- Reduction in manual intervention requests

### Performance Metrics
- Cache hit rate > 80% for repeated emails
- Average extraction time < 100ms (with cache)
- Batch processing speedup > 5x for backfill operations

### Maintenance Metrics
- Reduction in regex pattern maintenance
- Easier debugging with structured AI responses
- Better handling of edge cases and international formats

## Future Enhancements

1. **Confidence Thresholding** - Auto-review low-confidence extractions
2. **User Correction Loop** - Learn from manual corrections
3. **Fine-tuned Models** - Train on course-specific email patterns
4. **Multi-language Support** - Extend beyond Chinese/English names
5. **Analytics Dashboard** - Track extraction quality over time
