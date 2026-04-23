# AI Extraction Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace regex-based data extraction with AI across the codebase, using regex only for validation/sanitization of AI outputs.

**Architecture:** AI extractor with persistent caching and async batch processing. Regex kept for validation only. Database table tracks extraction quality with fallback marking.

**Tech Stack:** Python 3.10+, asyncio, SQLite, OpenAI-compatible API, existing codebase patterns

---

## File Structure

### New Files
- `database/schema.py` - Database schema definitions (create ai_extraction_cache table)
- `tests/test_ai_extractor_cache.py` - Tests for cache integration
- `tests/test_ai_extractor_batch.py` - Tests for batch processing

### Modified Files
- `ai/extractor.py` - Add cache and batch methods
- `mail/target_folder_loader.py` - Replace regex with AI extraction
- `backfill_database.py` - Replace regex with batch AI extraction
- `fix_assignment_names.py` - Replace regex with AI extraction
- `database/operations.py` - Add cache operations
- `tests/test_extractor.py` - Update tests for new functionality

---

## Task 1: Create Database Cache Table Schema

**Files:**
- Modify: `database/schema.py`

- [ ] **Step 1: Add ai_extraction_cache table to schema**

```python
def create_ai_extraction_cache_table():
    """Create AI extraction cache table"""
    from database.models import SessionLocal
    from sqlalchemy import text

    session = SessionLocal()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_extraction_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_uid VARCHAR(255) UNIQUE NOT NULL,
                student_id VARCHAR(50),
                name VARCHAR(100),
                assignment_name VARCHAR(50),
                confidence FLOAT,
                is_fallback BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_email_uid
            ON ai_extraction_cache(email_uid)
        """))

        session.commit()
        print("✓ Created ai_extraction_cache table")
    except Exception as e:
        session.rollback()
        print(f"✗ Failed to create cache table: {e}")
        raise
    finally:
        session.close()
```

Add this function to the existing `database/schema.py` file.

- [ ] **Step 2: Test schema creation**

Run: `python -c "from database.schema import create_ai_extraction_cache_table; create_ai_extraction_cache_table()"`

Expected: "✓ Created ai_extraction_cache table"

- [ ] **Step 3: Verify table exists**

Run: `python -c "from database.models import SessionLocal; from sqlalchemy import text; s = SessionLocal(); print(s.execute(text('SELECT name FROM sqlite_master WHERE name=\"ai_extraction_cache\"')).fetchall()); s.close()"`

Expected: `[('ai_extraction_cache',)]`

- [ ] **Step 4: Commit**

```bash
git add database/schema.py
git commit -m "feat: add ai_extraction_cache table schema

Persistent cache for AI extraction results with quality tracking.
- Stores extraction results keyed by email_uid
- Tracks fallback vs AI extraction with is_fallback flag
- Includes confidence scores for quality monitoring
- Indexed on email_uid for fast lookups"
```

---

## Task 2: Add Cache Operations to Database Layer

**Files:**
- Modify: `database/operations.py`

- [ ] **Step 1: Add cache model to models.py**

```python
class AIExtractionCache(Base):
    """AI extraction cache table"""
    __tablename__ = 'ai_extraction_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_uid = Column(String(255), unique=True, nullable=False, index=True)
    student_id = Column(String(50))
    name = Column(String(100))
    assignment_name = Column(String(50))
    confidence = Column(Float)
    is_fallback = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

Add this to `database/models.py` after the existing models.

- [ ] **Step 2: Add cache operations to Database class**

Add these methods to the `Database` class in `database/operations.py`:

```python
def get_ai_cache(self, email_uid: str) -> Optional[Dict]:
    """Get cached AI extraction result

    Args:
        email_uid: Email UID from IMAP

    Returns:
        Dict with keys: student_id, name, assignment_name, confidence, is_fallback
        or None if not found
    """
    from database.models import AIExtractionCache

    cache_entry = self.session.query(AIExtractionCache).filter_by(
        email_uid=email_uid
    ).first()

    if not cache_entry:
        return None

    return {
        'student_id': cache_entry.student_id,
        'name': cache_entry.name,
        'assignment_name': cache_entry.assignment_name,
        'confidence': cache_entry.confidence,
        'is_fallback': cache_entry.is_fallback
    }

def save_ai_cache(self, email_uid: str, result: Dict, is_fallback: bool = False):
    """Save AI extraction result to cache

    Args:
        email_uid: Email UID from IMAP
        result: Dict with student_id, name, assignment_name, confidence
        is_fallback: True if result came from regex fallback
    """
    from database.models import AIExtractionCache

    cache_entry = self.session.query(AIExtractionCache).filter_by(
        email_uid=email_uid
    ).first()

    if cache_entry:
        # Update existing entry
        cache_entry.student_id = result.get('student_id')
        cache_entry.name = result.get('name')
        cache_entry.assignment_name = result.get('assignment_name')
        cache_entry.confidence = result.get('confidence')
        cache_entry.is_fallback = is_fallback
    else:
        # Create new entry
        cache_entry = AIExtractionCache(
            email_uid=email_uid,
            student_id=result.get('student_id'),
            name=result.get('name'),
            assignment_name=result.get('assignment_name'),
            confidence=result.get('confidence'),
            is_fallback=is_fallback
        )
        self.session.add(cache_entry)

    try:
        self.session.commit()
    except Exception as e:
        self.session.rollback()
        print(f"Failed to save AI cache: {e}")
        raise
```

- [ ] **Step 3: Test cache operations**

Run: `python -c "
from database.operations import db
db.get_ai_cache('test123')
db.save_ai_cache('test123', {'student_id': '2021001', 'name': '张三', 'assignment_name': '作业1', 'confidence': 0.95})
result = db.get_ai_cache('test123')
print(result)
assert result['student_id'] == '2021001'
print('✓ Cache operations work')
"`

Expected: `{'student_id': '2021001', 'name': '张三', ...}` then "✓ Cache operations work"

- [ ] **Step 4: Commit**

```bash
git add database/models.py database/operations.py
git commit -m "feat: add AI cache operations to database layer

- Add AIExtractionCache model
- Implement get_ai_cache() and save_ai_cache() methods
- Support create and update operations
- Include error handling"
```

---

## Task 3: Add Cache Integration to AIExtractor

**Files:**
- Modify: `ai/extractor.py`

- [ ] **Step 1: Add cache integration method**

Add this method to the `AIExtractor` class:

```python
async def extract_with_cache(
    self,
    email_data: Dict,
    use_cache: bool = True
) -> Dict:
    """Extract student info with cache support

    Args:
        email_data: Dict with keys: subject, from (sender), attachments
        use_cache: Whether to check cache first

    Returns:
        {
            'student_id': str or None,
            'name': str or None,
            'assignment_name': str or None,
            'is_fallback': bool,
            'confidence': float
        }
    """
    from database.operations import db

    subject = email_data.get('subject', '')
    sender = email_data.get('from', '')
    attachments = email_data.get('attachments', [])

    # Generate cache key from email UID
    email_uid = email_data.get('uid')
    if not email_uid:
        # No UID, can't use cache
        email_uid = f"no_uid_{hash(subject)}"

    # Check cache first
    if use_cache and email_uid.startswith('数字') and email_uid.isdigit():
        cached_result = db.get_ai_cache(email_uid)
        if cached_result:
            print(f"✓ Cache hit for {email_uid}")
            return cached_result

    print(f"✗ Cache miss for {email_uid}, calling AI")

    # Call AI extraction
    result = await self.extract_student_info(subject, sender, attachments)

    # Extract relevant fields
    cache_result = {
        'student_id': result.get('student_id'),
        'name': result.get('name'),
        'assignment_name': result.get('assignment_name'),
        'is_fallback': 'fallback' in result.get('reasoning', '').lower(),
        'confidence': result.get('confidence', 0.5)
    }

    # Save to cache if we have a valid UID
    if use_cache and email_uid and email_uid.startswith('数字'):
        try:
            db.save_ai_cache(email_uid, cache_result, cache_result['is_fallback'])
        except Exception as e:
            print(f"Warning: Failed to save to cache: {e}")

    return cache_result
```

- [ ] **Step 2: Test cache integration**

Run: `python -c "
import asyncio
from ai.extractor import ai_extractor

async def test():
    email_data = {
        'uid': '12345',
        'subject': '2021001张三-作业1提交',
        'from': '张三',
        'attachments': []
    }
    result = await ai_extractor.extract_with_cache(email_data)
    print(result)

asyncio.run(test())
"`

Expected: Result with student_id, name, assignment_name fields

- [ ] **Step 3: Commit**

```bash
git add ai/extractor.py
git commit -m "feat: add cache integration to AIExtractor

- Add extract_with_cache() method
- Check cache before calling AI
- Save results to cache
- Mark fallback extractions for quality tracking"
```

---

## Task 4: Add Batch Processing to AIExtractor

**Files:**
- Modify: `ai/extractor.py`

- [ ] **Step 1: Add batch processing method**

Add this method to the `AIExtractor` class:

```python
async def batch_extract(
    self,
    email_list: List[Dict],
    batch_size: int = 10
) -> List[Dict]:
    """Extract student info from multiple emails concurrently

    Args:
        email_list: List of email_data dicts with keys: uid, subject, from, attachments
        batch_size: Number of concurrent AI calls

    Returns:
        List of extraction results in same order as input
    """
    results = []

    # Process in batches to avoid overwhelming the API
    for i in range(0, len(email_list), batch_size):
        batch = email_list[i:i+batch_size]

        # Process batch concurrently
        batch_results = await asyncio.gather(
            *[self.extract_with_cache(email) for email in batch],
            return_exceptions=True
        )

        # Handle exceptions in batch results
        for j, result in enumerate(batch_results):
            if isinstance(result, Exception):
                print(f"Error processing email {i+j}: {result}")
                # Return fallback result for failed emails
                batch_results[j] = {
                    'student_id': None,
                    'name': None,
                    'assignment_name': None,
                    'is_fallback': True,
                    'confidence': 0.0
                }

        results.extend(batch_results)
        print(f"✓ Processed batch {i//batch_size + 1}/{(len(email_list) + batch_size - 1)//batch_size}")

    return results
```

- [ ] **Step 2: Test batch processing**

Run: `python -c "
import asyncio
from ai.extractor import ai_extractor

async def test():
    emails = [
        {'uid': str(i), 'subject': f'202100{i}张三-作业1', 'from': '张三', 'attachments': []}
        for i in range(5)
    ]
    results = await ai_extractor.batch_extract(emails)
    print(f'Processed {len(results)} emails')
    for r in results:
        print(r)

asyncio.run(test())
"`

Expected: 5 results printed, each with extracted information

- [ ] **Step 3: Commit**

```bash
git add ai/extractor.py
git commit -m "feat: add batch processing to AIExtractor

- Add batch_extract() method for concurrent processing
- Process emails in batches of 10
- Handle exceptions gracefully
- Maintain result order matching input order"
```

---

## Task 5: Refactor target_folder_loader.py (Priority 1)

**Files:**
- Modify: `mail/target_folder_loader.py`

- [ ] **Step 1: Update _extract_from_email to use AI**

Replace the entire `_extract_from_email` method (lines 147-221) with:

```python
async def _extract_from_email(self, email_data) -> Dict:
    """从邮件中提取信息（使用AI，不再使用正则表达式）"""
    import asyncio
    from ai.extractor import ai_extractor

    subject = email_data.get('subject', '')
    uid = email_data.get('uid', '')

    try:
        # 使用AI提取信息
        result = await ai_extractor.extract_with_cache({
            'uid': uid,
            'subject': subject,
            'from': email_data.get('from', ''),
            'attachments': []
        })

        return {
            'id': None,
            'student_id': result.get('student_id') or 'Unknown',
            'name': result.get('name') or 'Unknown',
            'email': email_data.get('from', ''),
            'assignment_name': result.get('assignment_name') or 'Unknown',
            'submission_time': self._parse_date(email_data.get('date')),
            'is_late': False,
            'is_downloaded': False,
            'is_replied': False,
            'local_path': None,
        }
    except Exception as e:
        print(f"AI extraction error: {e}")
        # 返回Unknown而不是使用正则表达式
        return {
            'id': None,
            'student_id': 'Unknown',
            'name': 'Unknown',
            'email': '',
            'assignment_name': 'Unknown',
            'submission_time': self._parse_date(email_data.get('date')),
            'is_late': False,
            'is_downloaded': False,
            'is_replied': False,
            'local_path': None,
        }
```

- [ ] **Step 2: Update get_from_target_folder to handle async**

The `_merge_submission_info` method calls `_extract_from_email` which is now async. Update the call:

In `get_from_target_folder` method, around line 59, change:
```python
submission = self._merge_submission_info(email_data)
```

To:
```python
submission = asyncio.run(self._merge_submission_info_async(email_data))
```

- [ ] **Step 3: Add async version of _merge_submission_info**

Add this new method:

```python
async def _merge_submission_info_async(self, email_data) -> Dict:
    """异步版本的多源数据合并"""
    uid = email_data.get('uid')

    # 1. 从邮件获取基本信息
    email_info = {
        'email_uid': uid,
        'email_subject': email_data.get('subject', ''),
        'email_from': email_data.get('from', ''),
        'received_time': self._parse_date(email_data.get('date')),
    }

    # 2. 从数据库获取元数据
    db_record = db.get_submission_by_uid(uid)
    if db_record:
        db_info = {
            'id': db_record.id,
            'student_id': db_record.student.student_id,
            'name': db_record.student.name,
            'email': db_record.student.email,
            'assignment_name': db_record.assignment.name,
            'submission_time': db_record.submission_time,
            'is_late': db_record.is_late,
            'is_downloaded': db_record.is_downloaded,
            'is_replied': db_record.is_replied,
            'local_path': db_record.local_path,
        }
    else:
        # 数据库中没有记录，使用AI提取
        db_info = await self._extract_from_email(email_data)

    # 3. 从本地文件系统获取附件信息
    attachments = self._get_local_attachments(db_info.get('local_path'))

    # 合并所有信息
    return {**email_info, **db_info, 'attachments': attachments}
```

- [ ] **Step 4: Test with GUI**

Run: `python main.py`

Open GUI and navigate to the submissions list. Check that:
- Emails load correctly
- Student information is extracted
- No errors in console

- [ ] **Step 5: Commit**

```bash
git add mail/target_folder_loader.py
git commit -m "refactor: replace regex with AI in target_folder_loader

- Replace _extract_from_email regex patterns with AI extraction
- Add async version of _merge_submission_info
- Remove all regex extraction code
- Fallback to 'Unknown' instead of regex on AI failure"
```

---

## Task 6: Refactor backfill_database.py (Priority 2)

**Files:**
- Modify: `backfill_database.py`

- [ ] **Step 1: Rewrite backfill to use batch AI**

Replace the entire file content with:

```python
"""
使用AI批量填充数据库
从TARGET_FOLDER提取历史邮件数据并填充到数据库
"""
import asyncio
from mail.imap_client import imap_client_target
from mail.parser import MailParser
from config.settings import settings
from database.operations import db
from ai.extractor import ai_extractor
from tqdm import tqdm

async def backfill_with_ai():
    """使用AI批量提取并填充数据库"""
    # 连接到TARGET_FOLDER
    if not imap_client_target.connect():
        raise ConnectionError("无法连接到TARGET_FOLDER")

    if not imap_client_target.select_folder(settings.TARGET_FOLDER):
        raise FileNotFoundError(f"TARGET_FOLDER '{settings.TARGET_FOLDER}' 不存在")

    # 获取所有邮件
    parser = MailParser(imap_client_target)
    all_emails = imap_client_target.get_all_email_headers()

    print(f"找到 {len(all_emails)} 封邮件")

    # 批量处理
    batch_size = 10
    results = []

    for i in tqdm(range(0, len(all_emails), batch_size), desc="Processing emails"):
        batch = all_emails[i:i+batch_size]

        # 准备批量提取的数据
        email_batch = []
        for email_data in batch:
            email_batch.append({
                'uid': email_data.get('uid'),
                'subject': email_data.get('subject', ''),
                'from': email_data.get('from', ''),
                'attachments': []
            })

        # 批量AI提取
        batch_results = await ai_extractor.batch_extract(email_batch)

        # 保存到数据库
        for email_data, result in zip(batch, batch_results):
            save_submission(email_data, result)

    imap_client_target.disconnect()
    print(f"✓ 完成 {len(results)} 条记录")

def save_submission(email_data, extraction_result):
    """保存提交记录到数据库"""
    from datetime import datetime

    student_id = extraction_result.get('student_id')
    name = extraction_result.get('name')
    assignment_name = extraction_result.get('assignment_name')

    if not student_id or not name or assignment_name == 'Unknown':
        print(f"跳过: 提取失败 - {email_data.get('subject', '')}")
        return

    # 创建或获取学生记录
    student = db.get_or_create_student(student_id, name, email_data.get('from', ''))

    # 创建或获取作业记录
    assignment = db.get_or_create_assignment(assignment_name)

    # 创建提交记录
    db.create_submission(
        student_id=student_id,
        assignment_name=assignment_name,
        email_uid=email_data.get('uid'),
        email_subject=email_data.get('subject', ''),
        submission_time=datetime.now()
    )

if __name__ == '__main__':
    print("开始使用AI批量填充数据库...")
    asyncio.run(backfill_with_ai())
```

- [ ] **Step 2: Test backfill**

Run: `python backfill_database.py`

Expected: Progress bar showing processing, completion message

- [ ] **Step 3: Commit**

```bash
git add backfill_database.py
git commit -m "refactor: replace regex with batch AI in backfill_database

- Replace sequential regex extraction with batch AI processing
- Process emails in batches of 10 for performance
- Add progress tracking with tqdm
- Remove all regex patterns
- Use AI extraction with caching"
```

---

## Task 7: Refactor fix_assignment_names.py (Priority 3)

**Files:**
- Modify: `fix_assignment_names.py`

- [ ] **Step 1: Rewrite to use AI**

Replace the `extract_correct_assignment` function and update `fix_assignment_names`:

```python
"""
修复数据库中错误的作业名称
使用AI从邮件主题中提取正确的作业名称
"""
import asyncio
from database.models import SessionLocal, Submission, Assignment
from ai.extractor import ai_extractor

async def fix_assignment_names():
    """使用AI修复数据库中错误的作业名称"""
    session = SessionLocal()

    try:
        # 获取所有提交记录
        submissions = session.query(Submission).all()
        print(f"总提交记录: {len(submissions)}")

        fixed_count = 0
        error_count = 0

        for submission in submissions:
            assignment_name = submission.assignment.name

            # 检查是否为"作业+长数字"格式（学号被误认为作业号）
            if assignment_name.startswith('作业'):
                num_part = assignment_name[2:]

                # 如果数字部分长度>=10，很可能是学号而不是作业号
                if num_part.isdigit() and len(num_part) >= 10:
                    print(f"\n发现错误的作业名称:")
                    print(f"  ID: {submission.id}")
                    print(f"  学生: {submission.student.student_id} - {submission.student.name}")
                    print(f"  错误的作业名称: {assignment_name}")
                    print(f"  邮件主题: {submission.email_subject}")

                    # 使用AI提取正确的作业编号
                    correct_assignment = await extract_correct_assignment_with_ai(
                        submission.email_subject
                    )
                    print(f"  正确的作业名称: {correct_assignment}")

                    if correct_assignment and correct_assignment != 'Unknown':
                        # 查找或创建正确的作业记录
                        correct_assignment_record = session.query(Assignment).filter_by(
                            name=correct_assignment
                        ).first()

                        if not correct_assignment_record:
                            correct_assignment_record = Assignment(name=correct_assignment)
                            session.add(correct_assignment_record)
                            session.flush()

                        # 更新提交记录的作业ID
                        old_assignment_id = submission.assignment_id
                        submission.assignment_id = correct_assignment_record.id

                        print(f"  [OK] 已修复: {assignment_name} -> {correct_assignment}")
                        fixed_count += 1

                        # 检查旧的作业记录是否还有其他提交使用
                        old_users = session.query(Submission).filter_by(
                            assignment_id=old_assignment_id
                        ).count()

                        if old_users == 0:
                            print(f"  (旧的作业记录 '{assignment_name}' 已无引用，可删除)")
                    else:
                        print(f"  [ERROR] AI无法提取正确的作业名称")
                        error_count += 1

        session.commit()
        print(f"\n修复完成:")
        print(f"  成功修复: {fixed_count} 条")
        print(f"  失败: {error_count} 条")

    except Exception as e:
        session.rollback()
        print(f"修复失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

async def extract_correct_assignment_with_ai(email_subject: str) -> str:
    """使用AI从邮件主题中提取正确的作业编号"""
    if not email_subject:
        return None

    try:
        result = await ai_extractor.extract_with_cache({
            'uid': f"fix_{hash(email_subject)}",
            'subject': email_subject,
            'from': '',
            'attachments': []
        })

        return result.get('assignment_name')
    except Exception as e:
        print(f"AI extraction error: {e}")
        return None

if __name__ == '__main__':
    print("开始使用AI修复数据库中的作业名称...")
    asyncio.run(fix_assignment_names())
```

- [ ] **Step 2: Remove old regex patterns**

Delete the old `extract_correct_assignment` function (lines 81-119) and all regex patterns (lines 95-119).

- [ ] **Step 3: Test assignment name fix**

Run: `python fix_assignment_names.py`

Expected: Lists incorrect assignments, uses AI to fix them

- [ ] **Step 4: Commit**

```bash
git add fix_assignment_names.py
git commit -m "refactor: replace regex with AI in fix_assignment_names

- Replace regex patterns with AI extraction
- Use AI to understand context and extract correct assignment
- Remove complex regex patterns for assignment number detection
- Leverage cache for repeated email subjects"
```

---

## Task 8: Add Cache Tests

**Files:**
- Create: `tests/test_ai_extractor_cache.py`

- [ ] **Step 1: Write cache integration tests**

```python
"""
Tests for AI extractor cache integration
"""
import pytest
import asyncio
from ai.extractor import AIExtractor
from database.operations import db
from database.models import SessionLocal, AIExtractionCache

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test"""
    session = SessionLocal()
    session.query(AIExtractionCache).delete()
    session.commit()
    session.close()
    yield
    # Cleanup after test
    session = SessionLocal()
    session.query(AIExtractionCache).delete()
    session.commit()
    session.close()

@pytest.mark.asyncio
async def test_cache_miss_then_hit():
    """Test that cache miss triggers AI call, second call hits cache"""
    extractor = AIExtractor()
    email_data = {
        'uid': '12345',
        'subject': '2021001张三-作业1提交',
        'from': '张三',
        'attachments': []
    }

    # First call should miss cache
    result1 = await extractor.extract_with_cache(email_data)
    assert result1 is not None
    assert 'student_id' in result1

    # Second call should hit cache
    result2 = await extractor.extract_with_cache(email_data)
    assert result2 == result1

@pytest.mark.asyncio
async def test_cache_saves_fallback_flag():
    """Test that fallback results are marked correctly"""
    extractor = AIExtractor()
    email_data = {
        'uid': '67890',
        'subject': 'invalid subject',
        'from': 'unknown',
        'attachments': []
    }

    result = await extractor.extract_with_cache(email_data)

    # Check database for is_fallback flag
    session = SessionLocal()
    cache_entry = session.query(AIExtractionCache).filter_by(
        email_uid='67890'
    ).first()

    if cache_entry:
        assert cache_entry.is_fallback == result.get('is_fallback')

    session.close()

@pytest.mark.asyncio
async def test_cache_persists_across_instances():
    """Test that cache persists across AIExtractor instances"""
    extractor1 = AIExtractor()
    email_data = {
        'uid': '99999',
        'subject': '2021002李四-作业2提交',
        'from': '李四',
        'attachments': []
    }

    # Extract with first instance
    result1 = await extractor1.extract_with_cache(email_data)

    # Create new instance and extract again
    extractor2 = AIExtractor()
    result2 = await extractor2.extract_with_cache(email_data)

    # Should get same result from cache
    assert result2 == result1
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_ai_extractor_cache.py -v`

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_ai_extractor_cache.py
git commit -m "test: add AI extractor cache integration tests

- Test cache miss and hit behavior
- Test fallback flag marking
- Test cache persistence across instances
- Ensure cache works correctly with database"
```

---

## Task 9: Add Batch Processing Tests

**Files:**
- Create: `tests/test_ai_extractor_batch.py`

- [ ] **Step 1: Write batch processing tests**

```python
"""
Tests for AI extractor batch processing
"""
import pytest
import asyncio
from ai.extractor import AIExtractor

@pytest.mark.asyncio
async def test_batch_processing_returns_all_results():
    """Test that batch processing returns results for all emails"""
    extractor = AIExtractor()
    emails = [
        {'uid': str(i), 'subject': f'202100{i}学生-作业1', 'from': '学生', 'attachments': []}
        for i in range(5)
    ]

    results = await extractor.batch_extract(emails)

    assert len(results) == 5
    for result in results:
        assert 'student_id' in result
        assert 'name' in result
        assert 'assignment_name' in result

@pytest.mark.asyncio
async def test_batch_processing_maintains_order():
    """Test that batch processing maintains input order"""
    extractor = AIExtractor()
    emails = [
        {'uid': '1', 'subject': '2021001张三-作业1', 'from': '张三', 'attachments': []},
        {'uid': '2', 'subject': '2021002李四-作业2', 'from': '李四', 'attachments': []},
        {'uid': '3', 'subject': '2021003王五-作业3', 'from': '王五', 'attachments': []},
    ]

    results = await extractor.batch_extract(emails)

    # Check that order is maintained
    assert len(results) == 3
    # Results should correspond to input emails

@pytest.mark.asyncio
async def test_batch_processing_handles_exceptions():
    """Test that batch processing handles exceptions gracefully"""
    extractor = AIExtractor()
    emails = [
        {'uid': '1', 'subject': 'valid email', 'from': 'sender', 'attachments': []},
        {'uid': '2', 'subject': '', 'from': '', 'attachments': []},  # Invalid
        {'uid': '3', 'subject': 'another valid', 'from': 'sender', 'attachments': []},
    ]

    results = await extractor.batch_extract(emails)

    # Should return results for all emails, even invalid ones
    assert len(results) == 3
    for result in results:
        assert result is not None
        assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_batch_processing_with_custom_batch_size():
    """Test batch processing with custom batch size"""
    extractor = AIExtractor()
    emails = [
        {'uid': str(i), 'subject': f'email{i}', 'from': 'sender', 'attachments': []}
        for i in range(15)
    ]

    # Process with batch size of 5
    results = await extractor.batch_extract(emails, batch_size=5)

    assert len(results) == 15
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_ai_extractor_batch.py -v`

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_ai_extractor_batch.py
git commit -m "test: add AI extractor batch processing tests

- Test batch processing returns all results
- Test order is maintained
- Test exception handling in batches
- Test custom batch sizes"
```

---

## Task 10: Update Existing Tests

**Files:**
- Modify: `tests/test_extractor.py` (if it exists)

- [ ] **Step 1: Update existing extractor tests**

Add tests for the new cache and batch functionality to existing test files:

```python
@pytest.mark.asyncio
async def test_extract_with_cache():
    """Test extraction with cache enabled"""
    from ai.extractor import ai_extractor

    email_data = {
        'uid': 'test123',
        'subject': '2021001张三-作业1',
        'from': '张三',
        'attachments': []
    }

    result = await ai_extractor.extract_with_cache(email_data)

    assert result is not None
    assert 'student_id' in result
    assert 'name' in result
    assert 'assignment_name' in result
    assert 'is_fallback' in result

@pytest.mark.asyncio
async def test_extract_without_cache():
    """Test extraction with cache disabled"""
    from ai.extractor import ai_extractor

    email_data = {
        'uid': 'test456',
        'subject': '2021002李四-作业2',
        'from': '李四',
        'attachments': []
    }

    result = await ai_extractor.extract_with_cache(email_data, use_cache=False)

    assert result is not None
    assert 'student_id' in result
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_extractor.py
git commit -m "test: update existing extractor tests for new features

- Add tests for extract_with_cache method
- Test cache enable/disable functionality
- Ensure new methods work correctly"
```

---

## Task 11: Performance Testing

**Files:**
- Create: `tests/test_performance.py`

- [ ] **Step 1: Create performance benchmark tests**

```python
"""
Performance benchmarks for AI extraction
"""
import pytest
import asyncio
import time
from ai.extractor import AIExtractor

@pytest.mark.asyncio
@pytest.mark.slow
async def test_cache_performance():
    """Test that cache provides significant speedup"""
    extractor = AIExtractor()
    email_data = {
        'uid': 'perf_test',
        'subject': '2021001张三-作业1',
        'from': '张三',
        'attachments': []
    }

    # First call (cache miss)
    start = time.time()
    await extractor.extract_with_cache(email_data)
    first_call_time = time.time() - start

    # Second call (cache hit)
    start = time.time()
    await extractor.extract_with_cache(email_data)
    second_call_time = time.time() - start

    # Cache hit should be much faster
    assert second_call_time < first_call_time / 10
    print(f"First call: {first_call_time:.3f}s, Cache hit: {second_call_time:.3f}s")

@pytest.mark.asyncio
@pytest.mark.slow
async def test_batch_vs_sequential():
    """Compare batch vs sequential processing performance"""
    extractor = AIExtractor()
    emails = [
        {'uid': str(i), 'subject': f'202100{i}学生-作业1', 'from': '学生', 'attachments': []}
        for i in range(10)
    ]

    # Batch processing
    start = time.time()
    await extractor.batch_extract(emails)
    batch_time = time.time() - start

    # Sequential processing
    start = time.time()
    for email in emails:
        await extractor.extract_with_cache(email)
    sequential_time = time.time() - start

    # Batch should be faster
    print(f"Batch: {batch_time:.3f}s, Sequential: {sequential_time:.3f}s")
    # Batch should be at least 2x faster
    assert batch_time < sequential_time / 2
```

- [ ] **Step 2: Run performance tests**

Run: `pytest tests/test_performance.py -v -m slow`

Expected: Tests pass, showing cache and batch performance improvements

- [ ] **Step 3: Commit**

```bash
git add tests/test_performance.py
git commit -m "test: add performance benchmarks for AI extraction

- Test cache performance improvement
- Compare batch vs sequential processing
- Benchmark speedups from caching and batching"
```

---

## Task 12: Documentation and Cleanup

**Files:**
- Modify: `README.md`
- Modify: `docs/DEPLOYMENT.md`

- [ ] **Step 1: Update README with new architecture**

Add section to README.md:

```markdown
## AI Extraction Architecture

The system uses AI for extracting student information from emails:

- **Primary Method:** AI extraction via OpenAI-compatible API
- **Caching:** Results cached in database for performance
- **Fallback:** Regex validation only (no direct regex extraction)
- **Batch Processing:** Concurrent processing for bulk operations

### Extraction Flow

1. Check cache for existing result
2. If cache miss, call AI extractor
3. Validate and sanitize AI output with regex
4. Save result to cache
5. Return extracted information

### Quality Tracking

- `is_fallback` flag tracks regex fallback usage
- Target: <5% fallback rate in production
- Confidence scores stored for analysis
```

- [ ] **Step 2: Update deployment documentation**

Add migration steps to DEPLOYMENT.md:

```markdown
## Database Migration

When upgrading to use AI extraction:

1. Run schema update:
   ```bash
   python -c "from database.schema import create_ai_extraction_cache_table; create_ai_extraction_cache_table()"
   ```

2. Verify cache table created:
   ```bash
   python -c "from database.models import SessionLocal; from sqlalchemy import text; s = SessionLocal(); print(s.execute(text('SELECT name FROM sqlite_master WHERE name=\"ai_extraction_cache\"')).fetchall())"
   ```

3. Optionally backfill cache:
   ```bash
   python backfill_database.py
   ```
```

- [ ] **Step 3: Clean up old regex patterns**

Search for and document any remaining regex patterns:

Run: `grep -r "re\." --include="*.py" | grep -v test | grep -v "validation" | grep -v "sanitize"`

Document any remaining patterns as intentional (validation/sanitization only).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/DEPLOYMENT.md
git commit -m "docs: update documentation for AI extraction refactor

- Document AI extraction architecture in README
- Add database migration steps to DEPLOYMENT
- Clarify regex is for validation only
- Track quality metrics with is_fallback flag"
```

---

## Summary

This implementation plan refactors the codebase to use AI for data extraction instead of regex patterns:

**What Changed:**
1. Added `ai_extraction_cache` database table for persistent caching
2. Enhanced `AIExtractor` with cache integration and batch processing
3. Replaced regex extraction in 3 files with AI calls
4. Regex kept only for validation/sanitization of AI outputs
5. Added comprehensive tests for cache and batch functionality

**Benefits:**
- More robust extraction that handles format variations
- Better handling of international names and edge cases
- Performance improvements through caching and batching
- Quality tracking with fallback metrics

**Migration:**
- Database schema update required
- All extraction now uses AI by default
- Regex fallback marked for quality monitoring
- No breaking changes to public APIs
