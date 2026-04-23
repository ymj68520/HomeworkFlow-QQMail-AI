# Regex Patterns Documentation

## Overview

After the AI extraction refactor, regex patterns are now used **ONLY for validation and sanitization purposes**. All direct data extraction is handled by AI.

## Intentional Regex Usage

### 1. AI Extractor (`ai/extractor.py`)

**Purpose:** Validation and sanitization of AI-extracted data

#### Validation Patterns (Lines 16-23)
- **Assignment normalization:** `r'[一11][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)'`
  - Validates assignment names extracted by AI
  - Ensures consistent naming: "作业1", "作业2", etc.

#### Data Validation (Lines 50+)
- **Student ID validation:**
  - `r'^\d{6,15}$'` - Pure numeric IDs
  - `r'^[A-Za-z]\d{6,10}$'` - Alphanumeric IDs

- **Name validation:**
  - `r'^[\u4e00-\u9fa5]{2,6}$'` - Chinese names
  - `r'^[\u4e00-\u9fa5··]{2,10}$'` - Chinese names with dots
  - `r'^[A-Za-z\s\.\-]{2,30}$'` - English names
  - `r'^[\u4e00-\u9fa5A-Za-z\s\.\-]{2,30}$'` - Mixed names

#### Fallback Extraction (Lines 60+)
- **Backup extraction when AI fails:**
  - `r'\d+'` - Extract numbers from student IDs
  - `r'作业'` - Search for assignment keywords
  - Used ONLY when `is_fallback=True` flag is set

### 2. IMAP Client (`mail/imap_client.py`)

**Purpose:** Email folder parsing (not student data extraction)

#### Folder Path Extraction (Line 89)
- `r'"([^"]+)"'` - Extract folder names from IMAP LIST responses
- Used for parsing QQ mailbox folder structures
- NOT related to student information extraction

#### UID Extraction (Line 122)
- `r'UID\s+(\d+)'` - Parse email UIDs from IMAP responses
- Used for email tracking and management

### 3. Debug Utilities (`debug/debug_folders.py`)

**Purpose:** Development/testing utilities only

- `r'"([^"]+)"'` - Parse folder strings for debugging
- Not used in production workflow

## Quality Tracking

### Fallback Rate Monitoring

The system tracks regex fallback usage with the `is_fallback` flag in the database:

```python
# In ai/extractor.py
result = {
    'is_fallback': True,  # Set when regex extraction is used
    'confidence': 0.5,    # Lower confidence for regex fallback
    # ... other fields
}
```

**Target:** <5% fallback rate in production

### Monitoring Query

```sql
-- Check fallback rate
SELECT
    COUNT(*) FILTER (WHERE is_fallback = TRUE) * 100.0 / COUNT(*) as fallback_rate
FROM ai_extraction_cache;
```

## Migration Summary

### Before Refactor
- ❌ Regex used for direct extraction from email content
- ❌ Inconsistent extraction accuracy
- ❌ No caching of extraction results

### After Refactor
- ✅ AI used for primary extraction
- ✅ Regex used only for validation/sanitization
- ✅ Caching improves performance
- ✅ Quality tracking with `is_fallback` flag
- ✅ Confidence scores for analysis

## Testing Strategy

1. **Validation Tests:** Ensure regex patterns correctly validate AI output
2. **Fallback Tests:** Verify regex extraction works when AI fails
3. **Quality Tests:** Monitor fallback rate stays below 5%
4. **Performance Tests:** Cache hit rate >80% for repeated emails

## Conclusion

All remaining regex patterns are **intentional and necessary** for:
1. Validating AI-extracted data (ensuring data quality)
2. Parsing email protocol responses (IMAP folder management)
3. Providing fallback extraction when AI fails (graceful degradation)

**No regex patterns are used for direct student data extraction in the main workflow.**
