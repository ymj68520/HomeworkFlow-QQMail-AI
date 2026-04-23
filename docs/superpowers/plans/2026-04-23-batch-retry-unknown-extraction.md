# Batch Retry Unknown Extraction - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a post-processing batch retry phase to improve AI extraction accuracy by re-analyzing emails with Unknown results together in a single AI call.

**Architecture:** Two-phase extraction - individual processing first, then batch retry for emails with Unknown (null/None) fields before final marking as read. The batch retry provides more context to the AI by analyzing multiple emails together.

**Tech Stack:** Python 3.x, asyncio, OpenAI API (AsyncOpenAI), pytest for testing

---

## File Structure

**New Files:**
- `tests/test_ai_batch_retry.py` - Unit tests for batch retry functionality
- `tests/test_workflow_batch_retry.py` - Integration tests for workflow with batch retry

**Modified Files:**
- `ai/extractor.py` - Add `batch_retry_unknown()` method
- `core/workflow.py` - Add pending_retry tracking and `process_pending_retry()` method, extract `_process_extracted_info()` helper

**File Responsibilities:**
- `ai/extractor.py`: AI extraction logic and batch retry orchestration
- `core/workflow.py`: Email processing workflow and coordination
- `tests/test_ai_batch_retry.py`: Unit tests for batch retry method
- `tests/test_workflow_batch_retry.py`: Integration tests for full workflow

---

## Task 1: Unit Test - Empty Batch Retry

**Files:**
- Create: `tests/test_ai_batch_retry.py`

- [ ] **Step 1: Write the failing test for empty batch**

```python
# tests/test_ai_batch_retry.py
import pytest
from ai.extractor import ai_extractor

@pytest.mark.asyncio
async def test_batch_retry_unknown_empty_list():
    """Test that empty list returns empty results"""
    result = await ai_extractor.batch_retry_unknown([])
    
    assert result == []
    assert isinstance(result, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_batch_retry.py::test_batch_retry_unknown_empty_list -v`

Expected: FAIL with "AttributeError: 'AIExtractor' object has no attribute 'batch_retry_unknown'"

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_ai_batch_retry.py
git commit -m "test: add failing test for empty batch retry"
```

---

## Task 2: Unit Test - Single Email Batch Retry

**Files:**
- Modify: `tests/test_ai_batch_retry.py`

- [ ] **Step 1: Write the failing test for single email**

```python
# Add to tests/test_ai_batch_retry.py
@pytest.mark.asyncio
async def test_batch_retry_unknown_single_email():
    """Test batch retry with single email"""
    email_list = [{
        'uid': '12345',
        'subject': '2021001张三-作业1',
        'from': '张三 <zhangsan@example.com>',
        'attachments': [{'filename': 'report.pdf', 'content': b''}],
        'previous_result': {
            'is_assignment': True,
            'student_id': None,
            'name': None,
            'assignment_name': None,
            'confidence': 0.3,
            'reasoning': 'Could not extract'
        }
    }]
    
    # Mock the AI client to avoid real API call
    import ai.extractor
    original_client = ai_extractor.client
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps([{
        'is_assignment': True,
        'student_id': '2021001',
        'name': '张三',
        'assignment_name': '作业1',
        'confidence': 0.9,
        'reasoning': 'Successfully extracted from batch'
    }])
    
    ai_extractor.client = MagicMock()
    ai_extractor.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    try:
        result = await ai_extractor.batch_retry_unknown(email_list)
        
        assert len(result) == 1
        assert result[0]['student_id'] == '2021001'
        assert result[0]['name'] == '张三'
        assert result[0]['assignment_name'] == '作业1'
        assert result[0]['confidence'] == 0.9
    finally:
        ai_extractor.client = original_client
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_batch_retry.py::test_batch_retry_unknown_single_email -v`

Expected: FAIL (method not implemented yet)

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_ai_batch_retry.py
git commit -m "test: add failing test for single email batch retry"
```

---

## Task 3: Unit Test - Multiple Emails Batch Retry

**Files:**
- Modify: `tests/test_ai_batch_retry.py`

- [ ] **Step 1: Write the failing test for multiple emails**

```python
# Add to tests/test_ai_batch_retry.py
@pytest.mark.asyncio
async def test_batch_retry_unknown_multiple_emails():
    """Test batch retry with multiple emails"""
    email_list = [
        {
            'uid': '12345',
            'subject': '2021001张三-作业1',
            'from': '张三 <zhangsan@example.com>',
            'attachments': [{'filename': 'report.pdf', 'content': b''}],
            'previous_result': {'student_id': None, 'name': None, 'assignment_name': None}
        },
        {
            'uid': '12346',
            'subject': '2021002李四-作业2',
            'from': '李四 <lisi@example.com>',
            'attachments': [{'filename': 'homework.docx', 'content': b''}],
            'previous_result': {'student_id': None, 'name': None, 'assignment_name': None}
        }
    ]
    
    import ai.extractor
    original_client = ai_extractor.client
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps([
        {
            'is_assignment': True,
            'student_id': '2021001',
            'name': '张三',
            'assignment_name': '作业1',
            'confidence': 0.9,
            'reasoning': 'Extracted'
        },
        {
            'is_assignment': True,
            'student_id': '2021002',
            'name': '李四',
            'assignment_name': '作业2',
            'confidence': 0.85,
            'reasoning': 'Extracted'
        }
    ])
    
    ai_extractor.client = MagicMock()
    ai_extractor.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    try:
        result = await ai_extractor.batch_retry_unknown(email_list)
        
        assert len(result) == 2
        assert result[0]['student_id'] == '2021001'
        assert result[1]['student_id'] == '2021002'
    finally:
        ai_extractor.client = original_client
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_batch_retry.py::test_batch_retry_unknown_multiple_emails -v`

Expected: FAIL (method not implemented yet)

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_ai_batch_retry.py
git commit -m "test: add failing test for multiple emails batch retry"
```

---

## Task 4: Unit Test - Batch Size Limit (Split Large Batches)

**Files:**
- Modify: `tests/test_ai_batch_retry.py`

- [ ] **Step 1: Write the failing test for large batch splitting**

```python
# Add to tests/test_ai_batch_retry.py
@pytest.mark.asyncio
async def test_batch_retry_unknown_large_batch_splitting():
    """Test that batches larger than 20 are split into multiple API calls"""
    # Create 25 emails (should split into 2 batches: 20 + 5)
    email_list = [
        {
            'uid': f'{10000+i}',
            'subject': f'202100{i}学生{i}-作业1',
            'from': f'学生{i} <student{i}@example.com>',
            'attachments': [{'filename': 'file.pdf', 'content': b''}],
            'previous_result': {'student_id': None, 'name': None, 'assignment_name': None}
        }
        for i in range(25)
    ]
    
    import ai.extractor
    original_client = ai_extractor.client
    
    # Track how many times the API is called
    call_count = [0]
    
    async def mock_create(*args, **kwargs):
        call_count[0] += 1
        batch_size = 20 if call_count[0] == 1 else 5
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        
        results = [
            {
                'is_assignment': True,
                'student_id': f'202100{i}',
                'name': f'学生{i}',
                'assignment_name': '作业1',
                'confidence': 0.8,
                'reasoning': 'Extracted'
            }
            for i in range(batch_size)
        ]
        
        mock_response.choices[0].message.content = json.dumps(results)
        return mock_response
    
    ai_extractor.client = MagicMock()
    ai_extractor.client.chat.completions.create = AsyncMock(side_effect=mock_create)
    
    try:
        result = await ai_extractor.batch_retry_unknown(email_list)
        
        assert len(result) == 25
        assert call_count[0] == 2  # Should have made 2 API calls
    finally:
        ai_extractor.client = original_client
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ai_batch_retry.py::test_batch_retry_unknown_large_batch_splitting -v`

Expected: FAIL (method not implemented yet)

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_ai_batch_retry.py
git commit -m "test: add failing test for large batch splitting"
```

---

## Task 5: Implement `batch_retry_unknown()` Method

**Files:**
- Modify: `ai/extractor.py`

- [ ] **Step 1: Add the batch_retry_unknown method implementation**

```python
# Add to ai/extractor.py, after the batch_extract method (around line 273)

    async def batch_retry_unknown(
        self,
        email_list: List[Dict],
        batch_size: int = 20
    ) -> List[Dict]:
        """
        Retry extraction for emails with Unknown results using batch processing
        
        Args:
            email_list: List of dicts with keys:
                       - uid, subject, from, attachments, previous_result
            batch_size: Max emails per API call (default: 20)
        
        Returns:
            List of extraction results in same order as input
        """
        if not email_list:
            return []
        
        all_results = []
        
        # Process in batches to avoid overwhelming the API
        for i in range(0, len(email_list), batch_size):
            batch = email_list[i:i+batch_size]
            
            # Construct batch prompt
            batch_prompt = self._construct_batch_retry_prompt(batch)
            
            try:
                # Call AI with batch prompt
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": batch_prompt}
                        ],
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    ),
                    timeout=30.0
                )
                
                # Parse batch response
                batch_results = json.loads(response.choices[0].message.content)
                
                # Handle both array and single object responses
                if isinstance(batch_results, list):
                    all_results.extend(batch_results)
                else:
                    # Single result returned (shouldn't happen but handle gracefully)
                    all_results.append(batch_results)
                
            except asyncio.TimeoutError:
                print(f"Batch retry timeout for batch {i//batch_size + 1}")
                # Return None results for this batch
                all_results.extend([
                    {
                        'is_assignment': False,
                        'student_id': None,
                        'name': None,
                        'assignment_name': None,
                        'confidence': 0.0,
                        'reasoning': 'Batch retry timeout'
                    }
                    for _ in batch
                ])
                
            except Exception as e:
                print(f"Batch retry error for batch {i//batch_size + 1}: {e}")
                # Return None results for this batch
                all_results.extend([
                    {
                        'is_assignment': False,
                        'student_id': None,
                        'name': None,
                        'assignment_name': None,
                        'confidence': 0.0,
                        'reasoning': f'Batch retry error: {str(e)}'
                    }
                    for _ in batch
                ])
        
        # Normalize results
        for result in all_results:
            if result.get('student_id'):
                result['student_id'] = self._normalize_student_id(result['student_id'])
            
            if result.get('assignment_name'):
                result['assignment_name'] = self.normalize_assignment_name(
                    result['assignment_name']
                )
        
        return all_results
    
    def _construct_batch_retry_prompt(self, email_list: List[Dict]) -> str:
        """
        Construct prompt for batch retry extraction
        
        Args:
            email_list: List of email dicts with uid, subject, from, attachments
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "The following emails failed initial extraction. Please analyze them together",
            "and extract student information. The context from multiple emails may help",
            "identify patterns.\n\n"
        ]
        
        for idx, email in enumerate(email_list, 1):
            prompt_parts.append(f"Email {idx}:")
            prompt_parts.append(f"  Subject: {email['subject']}")
            prompt_parts.append(f"  From: {email['from']}")
            
            attachments = email.get('attachments', [])
            if attachments:
                attachment_names = [att.get('filename', '') for att in attachments]
                prompt_parts.append(f"  Attachments: {', '.join(attachment_names)}")
            else:
                prompt_parts.append("  Attachments: None")
            
            if email.get('previous_result'):
                prev = email['previous_result']
                prompt_parts.append(f"  Previous failed result: student_id={prev.get('student_id')}, "
                                  f"name={prev.get('name')}, assignment={prev.get('assignment_name')}")
            
            prompt_parts.append("")
        
        prompt_parts.append("\nPlease return a JSON array with extraction results for each email in order.")
        prompt_parts.append("Each result should have: is_assignment, student_id, name, assignment_name, confidence, reasoning.")
        
        return "\n".join(prompt_parts)
    
    def _normalize_student_id(self, student_id: str) -> str:
        """
        Normalize student ID by extracting numeric part
        
        Args:
            student_id: Raw student ID string
        
        Returns:
            Normalized student ID or None
        """
        if not student_id:
            return None
        
        student_id = str(student_id).strip()
        
        # Extract continuous numeric parts
        numbers = re.findall(r'\d+', student_id)
        if numbers:
            # Return the longest numeric sequence (usually the student ID)
            return max(numbers, key=len)
        
        return None
```

- [ ] **Step 2: Run all batch retry tests**

Run: `pytest tests/test_ai_batch_retry.py -v`

Expected: All tests PASS

- [ ] **Step 3: Commit the implementation**

```bash
git add ai/extractor.py
git commit -m "feat: implement batch_retry_unknown method with batch splitting support"
```

---

## Task 6: Add `pending_retry` Tracking to Workflow

**Files:**
- Modify: `core/workflow.py`

- [ ] **Step 1: Add pending_retry initialization**

```python
# Modify core/workflow.py, in the __init__ method (around line 16)

    def __init__(self):
        self.parser = mail_parser
        self.ai = ai_extractor
        self.db = db
        self.storage = storage_manager
        self.imap = imap_client_inbox
        self.smtp = smtp_client
        self.dedup = deduplication_handler
        self.settings = settings
        self.pending_retry = []  # NEW: Track emails needing batch retry
```

- [ ] **Step 2: Run workflow tests to ensure no regression**

Run: `pytest tests/test_workflow.py -v` (if exists) or `pytest tests/ -k workflow -v`

Expected: Existing tests still PASS

- [ ] **Step 3: Commit the change**

```bash
git add core/workflow.py
git commit -m "feat: add pending_retry tracking to AssignmentWorkflow"
```

---

## Task 7: Add Unknown Detection in `process_new_email()`

**Files:**
- Modify: `core/workflow.py`

- [ ] **Step 1: Add Unknown detection after AI extraction**

```python
# Modify core/workflow.py, in process_new_email method, after AI extraction (around line 68)

            # 3. AI提取学生信息
            print("Extracting student info using AI...")
            student_info = await self.ai.extract_student_info(
                subject=email_data['subject'],
                sender=email_data['from'],
                attachments=email_data['attachments']
            )

            print(f"AI Result: is_assignment={student_info['is_assignment']}")
            print(f"  student_id={student_info.get('student_id')}")
            print(f"  name={student_info.get('name')}")
            print(f"  assignment={student_info.get('assignment_name')}")

            # NEW: Check for Unknown fields and add to pending retry
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
                    'email_data': email_data
                })
                print(f"Added to batch retry list (Unknown fields detected)")
```

- [ ] **Step 2: Run workflow tests**

Run: `pytest tests/ -k workflow -v`

Expected: Existing tests still PASS

- [ ] **Step 3: Commit the change**

```bash
git add core/workflow.py
git commit -m "feat: add Unknown field detection and pending retry collection"
```

---

## Task 8: Extract `_process_extracted_info()` Helper Method

**Files:**
- Modify: `core/workflow.py`

- [ ] **Step 1: Extract workflow logic into helper method**

```python
# Add to core/workflow.py, after the process_new_email method (around line 212)

    async def _process_extracted_info(
        self,
        email_uid: str,
        email_data: Dict,
        student_info: Dict,
        is_retry: bool = False
    ) -> dict:
        """
        Process email with already-extracted student info
        This contains steps 5-13 from process_new_email to avoid code duplication
        
        Args:
            email_uid: Email UID
            email_data: Parsed email data
            student_info: Extracted student information
            is_retry: Whether this is a retry from batch processing
        
        Returns:
            Processing result dictionary
        """
        print(f"\n{'='*50}")
        if is_retry:
            print(f"Re-processing email (from batch retry): {email_uid}")
        else:
            print(f"Processing extracted info: {email_uid}")
        print(f"{'='*50}")
        
        # 5. 判断是否为作业提交
        if not student_info.get('is_assignment'):
            print("Not an assignment submission, marking as read")
            self.parser.mark_as_read(email_uid)
            self.db.log_email_action(
                email_uid=email_uid,
                action='marked_read',
                folder='INBOX',
                details='Not an assignment'
            )
            return {'success': True, 'action': 'marked_read', 'reason': 'not_assignment'}

        # 6. 验证必要信息
        student_id = student_info.get('student_id')
        student_name = student_info.get('name')
        assignment_name = student_info.get('assignment_name')

        if not all([student_id, student_name, assignment_name]):
            print("Missing required information, marking as read")
            self.parser.mark_as_read(email_uid)
            self.db.log_email_action(
                email_uid=email_uid,
                action='marked_read',
                folder='INBOX',
                details=f'Missing info: student_id={student_id}, name={student_name}, assignment={assignment_name}'
            )
            return {'success': True, 'action': 'marked_read', 'reason': 'missing_info'}

        # 7. 检查是否为重复提交
        is_duplicate, dup_result = await self.dedup.check_and_handle_duplicate(
            student_id=student_id,
            student_name=student_name,
            assignment_name=assignment_name,
            email_uid=email_uid,
            sender_email=email_data['sender_email'],
            email_subject=email_data['subject'],
            attachments=email_data['attachments']
        )

        if is_duplicate:
            if dup_result.get('success'):
                print(f"Duplicate submission updated: {student_id} - {assignment_name}")
                return {'success': True, 'action': 'updated_duplicate', 'data': dup_result}
            else:
                print(f"Failed to handle duplicate: {dup_result.get('error')}")
                return {'success': False, 'error': dup_result.get('error'), 'action': 'duplicate_failed'}

        # 8. 保存附件到本地
        print("Storing attachments locally...")
        local_path = self.storage.store_submission(
            assignment_name=assignment_name,
            student_id=student_id,
            name=student_name,
            attachments=email_data['attachments']
        )

        print(f"Files stored at: {local_path}")

        # 9. 存储到数据库
        print("Saving to database...")
        submission = self.db.create_submission(
            student_id=student_id,
            assignment_name=assignment_name,
            email_uid=email_uid,
            email_subject=email_data['subject'],
            sender_email=email_data['sender_email'],
            sender_name=student_name,
            submission_time=datetime.now(),
            local_path=local_path
        )

        if not submission:
            return {'success': False, 'error': 'Failed to save to database', 'action': 'db_failed'}

        # 10. 添加附件记录
        for attachment in email_data['attachments']:
            self.db.add_attachment(
                submission_id=submission.id,
                filename=attachment['filename'],
                file_size=attachment['size'],
                local_path=f"{local_path}/{attachment['filename']}"
            )

        # 11. 移动邮件到目标文件夹
        print(f"Moving email to {self.settings.TARGET_FOLDER}...")
        if not self.imap.folder_exists(self.settings.TARGET_FOLDER):
            print(f"Creating target folder: {self.settings.TARGET_FOLDER}")
            self.imap.create_folder(self.settings.TARGET_FOLDER)

        move_success = self.parser.move_to_folder(email_uid, self.settings.TARGET_FOLDER)

        if not move_success:
            print(f"Warning: Failed to move email to {self.settings.TARGET_FOLDER}")

        # 12. 发送确认邮件
        print("Sending confirmation email...")
        self.smtp.send_reply(
            to_email=email_data['sender_email'],
            student_name=student_name,
            assignment_name=assignment_name
        )

        # 13. 标记已回复
        self.db.mark_replied(submission.id)

        # 14. 记录日志
        log_action = 'reprocessed' if is_retry else 'processed'
        self.db.log_email_action(
            email_uid=email_uid,
            action=log_action,
            folder=self.settings.TARGET_FOLDER,
            details=f"{log_action.capitalize()} assignment from {student_id} - {assignment_name}"
        )

        print(f"Successfully {log_action}: {student_id} - {student_name} - {assignment_name}")

        return {
            'success': True,
            'action': log_action,
            'data': {
                'student_id': student_id,
                'name': student_name,
                'assignment': assignment_name,
                'local_path': local_path,
                'submission_id': submission.id
            }
        }
```

- [ ] **Step 2: Refactor process_new_email to use the helper**

```python
# Modify core/workflow.py, process_new_email method
# Replace steps 5-13 (lines 86-143) with a call to the helper:

            # 4-14. Process extracted information using helper method
            if has_unknown and not student_info.get('is_assignment'):
                # Already marked as read in the check above, skip processing
                pass
            else:
                result = await self._process_extracted_info(
                    email_uid=email_uid,
                    email_data=email_data,
                    student_info=student_info,
                    is_retry=False
                )
                
                if not result['success']:
                    return result
                
                if result['action'] in ['processed', 'updated_duplicate']:
                    return result
```

- [ ] **Step 3: Run workflow tests**

Run: `pytest tests/ -k workflow -v`

Expected: All existing tests PASS

- [ ] **Step 4: Commit the refactoring**

```bash
git add core/workflow.py
git commit -m "refactor: extract _process_extracted_info helper method to avoid code duplication"
```

---

## Task 9: Implement `process_pending_retry()` Method

**Files:**
- Modify: `core/workflow.py`

- [ ] **Step 1: Add the process_pending_retry method**

```python
# Add to core/workflow.py, after the _process_extracted_info method

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
            print("Calling batch AI extraction...")
            retry_results = await self.ai.batch_retry_unknown(self.pending_retry)

            # Process each result
            for i, (email_info, new_result) in enumerate(zip(self.pending_retry, retry_results)):
                email_uid = email_info['uid']

                # Check if extraction improved
                if (new_result.get('student_id') and
                    new_result.get('name') and
                    new_result.get('assignment_name')):

                    print(f"\n✓ Batch retry succeeded for {email_uid}")
                    print(f"  student_id={new_result['student_id']}")
                    print(f"  name={new_result['name']}")
                    print(f"  assignment={new_result['assignment_name']}")
                    print(f"  confidence={new_result.get('confidence', 0):.2f}")

                    # Re-process through workflow using helper
                    email_data = email_info['email_data']
                    
                    # Verify email hasn't been moved yet
                    try:
                        # Check if email still exists in INBOX
                        if self.parser.uid_exists(email_uid):
                            result = await self._process_extracted_info(
                                email_uid=email_uid,
                                email_data=email_data,
                                student_info=new_result,
                                is_retry=True
                            )
                            
                            if result['success'] and result['action'] in ['processed', 'reprocessed']:
                                results['retry_success'] += 1
                            else:
                                print(f"Warning: Re-processing failed for {email_uid}: {result.get('error')}")
                                results['retry_failed'] += 1
                        else:
                            print(f"Info: Email {email_uid} no longer in INBOX, skipping re-processing")
                            results['retry_failed'] += 1
                    
                    except Exception as e:
                        print(f"Error re-processing {email_uid}: {e}")
                        import traceback
                        traceback.print_exc()
                        results['retry_failed'] += 1

                else:
                    print(f"\n✗ Batch retry still failed for {email_uid}")
                    print(f"  student_id={new_result.get('student_id')}")
                    print(f"  name={new_result.get('name')}")
                    print(f"  assignment={new_result.get('assignment_name')}")
                    results['retry_failed'] += 1

            print(f"\n{'='*50}")
            print(f"Batch retry complete:")
            print(f"  Total: {results['total']}")
            print(f"  Succeeded: {results['retry_success']}")
            print(f"  Still failed: {results['retry_failed']}")
            print(f"{'='*50}\n")

        except Exception as e:
            print(f"Error in batch retry phase: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Clear pending list
            self.pending_retry = []

        return results
```

- [ ] **Step 2: Add uid_exists method to parser (if not exists)**

```python
# Add to mail/parser.py (or wherever mail_parser_inbox is defined)

    def uid_exists(self, uid: str) -> bool:
        """
        Check if an email UID still exists in the current folder
        
        Args:
            uid: Email UID to check
        
        Returns:
            True if UID exists, False otherwise
        """
        try:
            # Try to fetch the email to see if it exists
            result = self.imap.uid('FETCH', uid, '(UID)')
            return bool(result)
        except Exception:
            return False
```

- [ ] **Step 3: Integrate process_pending_retry into process_inbox**

```python
# Modify core/workflow.py, in process_inbox method
# Add before the final summary print (around line 258, before the print("="*50) line):

            # Process emails with Unknown results using batch retry
            await self.process_pending_retry()
```

- [ ] **Step 4: Run workflow tests**

Run: `pytest tests/ -k workflow -v`

Expected: All tests PASS

- [ ] **Step 5: Commit the implementation**

```bash
git add core/workflow.py mail/parser.py
git commit -m "feat: implement process_pending_retry method with batch retry phase"
```

---

## Task 10: Integration Test - Full Workflow with Batch Retry

**Files:**
- Create: `tests/test_workflow_batch_retry.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_workflow_batch_retry.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.workflow import workflow

@pytest.mark.asyncio
async def test_workflow_with_batch_retry():
    """Test full workflow with emails that have Unknown fields"""
    
    # Mock parser
    mock_parser = MagicMock()
    mock_parser.connect.return_value = True
    mock_parser.disconnect.return_value = None
    mock_parser.uid_exists.return_value = True
    
    # Mock 3 emails with different missing fields
    mock_parser.get_new_emails.return_value = [
        {
            'uid': '1001',
            'subject': '提交作业',  # Missing: student_id, name, assignment
            'from': 'Unknown <unknown@test.com>',
            'sender_email': 'unknown@test.com',
            'sender_name': 'Unknown',
            'has_attachments': True,
            'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
        },
        {
            'uid': '1002',
            'subject': '2021001-作业1',  # Missing: name
            'from': 'Student1 <student1@test.com>',
            'sender_email': 'student1@test.com',
            'sender_name': 'Student1',
            'has_attachments': True,
            'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
        },
        {
            'uid': '1003',
            'subject': '张三-作业1',  # Missing: student_id
            'from': '张三 <zhangsan@test.com>',
            'sender_email': 'zhangsan@test.com',
            'sender_name': '张三',
            'has_attachments': True,
            'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
        }
    ]
    
    # Mock parse_email
    async def mock_parse_email(uid):
        emails = {
            '1001': {
                'uid': '1001',
                'subject': '提交作业',
                'from': 'Unknown <unknown@test.com>',
                'sender_email': 'unknown@test.com',
                'sender_name': 'Unknown',
                'has_attachments': True,
                'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
            },
            '1002': {
                'uid': '1002',
                'subject': '2021001-作业1',
                'from': 'Student1 <student1@test.com>',
                'sender_email': 'student1@test.com',
                'sender_name': 'Student1',
                'has_attachments': True,
                'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
            },
            '1003': {
                'uid': '1003',
                'subject': '张三-作业1',
                'from': '张三 <zhangsan@test.com>',
                'sender_email': 'zhangsan@test.com',
                'sender_name': '张三',
                'has_attachments': True,
                'attachments': [{'filename': 'file.pdf', 'size': 1024, 'content': b''}]
            }
        }
        return emails.get(uid)
    
    mock_parser.parse_email = mock_parse_email
    
    # Mock AI extraction - individual phase returns partial/missing data
    async def mock_extract_individual(subject, sender, attachments):
        if '2021001' in subject:
            return {
                'is_assignment': True,
                'student_id': '2021001',
                'name': None,  # Missing
                'assignment_name': '作业1',
                'confidence': 0.6,
                'reasoning': 'Partial extraction'
            }
        elif '张三' in subject:
            return {
                'is_assignment': True,
                'student_id': None,  # Missing
                'name': '张三',
                'assignment_name': '作业1',
                'confidence': 0.6,
                'reasoning': 'Partial extraction'
            }
        else:
            return {
                'is_assignment': True,
                'student_id': None,
                'name': None,
                'assignment_name': None,
                'confidence': 0.3,
                'reasoning': 'Could not extract'
            }
    
    # Mock AI batch retry - returns complete data
    async def mock_batch_retry(email_list):
        # Simulate batch AI fixing the missing fields
        return [
            {
                'is_assignment': True,
                'student_id': '2021002',
                'name': '学生2',
                'assignment_name': '作业1',
                'confidence': 0.85,
                'reasoning': 'Batch extracted'
            },
            {
                'is_assignment': True,
                'student_id': '2021001',
                'name': '学生1',
                'assignment_name': '作业1',
                'confidence': 0.9,
                'reasoning': 'Batch extracted'
            },
            {
                'is_assignment': True,
                'student_id': '2021003',
                'name': '张三',
                'assignment_name': '作业1',
                'confidence': 0.88,
                'reasoning': 'Batch extracted'
            }
        ]
    
    # Apply mocks
    with patch.object(workflow, 'parser', mock_parser):
        with patch.object(workflow.ai, 'extract_student_info', side_effect=mock_extract_individual):
            with patch.object(workflow.ai, 'batch_retry_unknown', side_effect=mock_batch_retry):
                # Mock other dependencies
                with patch.object(workflow.storage, 'store_submission', return_value='/path/to/submission'):
                    with patch.object(workflow.db, 'create_submission') as mock_create:
                        mock_submission = MagicMock()
                        mock_submission.id = 123
                        mock_create.return_value = mock_submission
                        
                        with patch.object(workflow.db, 'add_attachment'):
                            with patch.object(workflow.db, 'log_email_action'):
                                with patch.object(workflow.db, 'mark_replied'):
                                    with patch.object(workflow.parser, 'mark_as_read'):
                                        with patch.object(workflow.parser, 'move_to_folder', return_value=True):
                                            with patch.object(workflow.smtp, 'send_reply'):
                                                with patch.object(workflow.dedup, 'check_and_handle_duplicate', return_value=(False, {})):
                                                    
                                                    # Run workflow
                                                    result = await workflow.process_inbox()
                                                    
                                                    # Verify pending_retry was populated
                                                    assert len(workflow.pending_retry) == 0  # Cleared after batch
                                                    
                                                    # Verify batch retry was called
                                                    workflow.ai.batch_retry_unknown.assert_called_once()
                                                    
                                                    # Verify all emails were processed
                                                    assert result['total'] == 3
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_workflow_batch_retry.py::test_workflow_with_batch_retry -v`

Expected: PASS

- [ ] **Step 3: Commit the integration test**

```bash
git add tests/test_workflow_batch_retry.py
git commit -m "test: add integration test for workflow with batch retry"
```

---

## Task 11: Manual Testing Script

**Files:**
- Create: `test_batch_retry_manual.py`

- [ ] **Step 1: Create manual testing script**

```python
# test_batch_retry_manual.py
"""
Manual testing script for batch retry functionality

Run with: python test_batch_retry_manual.py
"""

import asyncio
from ai.extractor import ai_extractor

async def test_batch_retry():
    """Manually test batch retry with realistic email data"""
    
    # Simulate emails with Unknown fields
    test_emails = [
        {
            'uid': '1001',
            'subject': '作业提交',
            'from': '学生 <student@example.com>',
            'attachments': [{'filename': 'report.pdf', 'content': b''}],
            'previous_result': {
                'is_assignment': True,
                'student_id': None,
                'name': None,
                'assignment_name': None,
                'confidence': 0.3,
                'reasoning': 'Could not extract'
            }
        },
        {
            'uid': '1002',
            'subject': '2021001-第一次作业',
            'from': 'Student1 <student1@example.com>',
            'attachments': [{'filename': 'homework.docx', 'content': b''}],
            'previous_result': {
                'is_assignment': True,
                'student_id': '2021001',
                'name': None,
                'assignment_name': None,
                'confidence': 0.5,
                'reasoning': 'Partial extraction'
            }
        },
        {
            'uid': '1003',
            'subject': '张三-实验报告',
            'from': '张三 <zhangsan@example.com>',
            'attachments': [{'filename': 'lab.pdf', 'content': b''}],
            'previous_result': {
                'is_assignment': True,
                'student_id': None,
                'name': '张三',
                'assignment_name': None,
                'confidence': 0.5,
                'reasoning': 'Partial extraction'
            }
        }
    ]
    
    print("Testing batch retry with 3 emails with Unknown fields...")
    print("="*60)
    
    results = await ai_extractor.batch_retry_unknown(test_emails)
    
    print("\nResults:")
    print("="*60)
    
    for i, (email, result) in enumerate(zip(test_emails, results), 1):
        print(f"\nEmail {i}: {email['uid']}")
        print(f"  Subject: {email['subject']}")
        print(f"  Original: student_id={email['previous_result'].get('student_id')}, "
              f"name={email['previous_result'].get('name')}, "
              f"assignment={email['previous_result'].get('assignment_name')}")
        print(f"  After batch: student_id={result.get('student_id')}, "
              f"name={result.get('name')}, "
              f"assignment={result.get('assignment_name')}")
        print(f"  Confidence: {result.get('confidence', 0):.2f}")
        
        # Check if extraction improved
        improved = (
            result.get('student_id') and
            result.get('name') and
            result.get('assignment_name')
        )
        print(f"  Status: {'✓ IMPROVED' if improved else '✗ STILL UNKNOWN'}")
    
    print("\n" + "="*60)
    improved_count = sum(
        1 for r in results 
        if r.get('student_id') and r.get('name') and r.get('assignment_name')
    )
    print(f"Summary: {improved_count}/{len(results)} emails improved")
    print("="*60)

if __name__ == '__main__':
    asyncio.run(test_batch_retry())
```

- [ ] **Step 2: Run manual test**

Run: `python test_batch_retry_manual.py`

Expected: Script executes successfully and shows extraction results

- [ ] **Step 3: Commit the manual test script**

```bash
git add test_batch_retry_manual.py
git commit -m "test: add manual testing script for batch retry functionality"
```

---

## Task 12: Performance Metrics Logging

**Files:**
- Modify: `core/workflow.py`

- [ ] **Step 1: Add performance metrics to process_pending_retry**

```python
# Modify core/workflow.py, in process_pending_retry method
# Add timing and metrics logging (add after the "print(f'Calling batch AI extraction...')" line):

            # Call batch retry
            print("Calling batch AI extraction...")
            import time
            batch_start_time = time.time()
            
            retry_results = await self.ai.batch_retry_unknown(self.pending_retry)
            
            batch_duration = time.time() - batch_start_time
            
            # Log performance metrics
            print(f"\nBatch retry performance:")
            print(f"  Emails processed: {len(self.pending_retry)}")
            print(f"  Duration: {batch_duration:.2f} seconds")
            print(f"  Average time per email: {batch_duration/len(self.pending_retry):.2f} seconds")
```

- [ ] **Step 2: Add improvement rate calculation**

```python
# Add to process_pending_retry method, before the final summary:

            # Calculate improvement rate
            improvement_rate = (results['retry_success'] / results['total'] * 100) if results['total'] > 0 else 0
            print(f"\nBatch retry metrics:")
            print(f"  Improvement rate: {improvement_rate:.1f}%")
            print(f"  Total processed: {results['total']}")
            print(f"  Successfully fixed: {results['retry_success']}")
            print(f"  Still failed: {results['retry_failed']}")
```

- [ ] **Step 3: Run tests to verify logging works**

Run: `pytest tests/test_workflow_batch_retry.py -v -s`

Expected: Logs show performance metrics

- [ ] **Step 4: Commit metrics logging**

```bash
git add core/workflow.py
git commit -m "feat: add performance metrics logging to batch retry phase"
```

---

## Task 13: Documentation Update

**Files:**
- Modify: `README.md` (or create docs/FEATURES.md if it doesn't exist)

- [ ] **Step 1: Add feature documentation**

```markdown
# Add to README.md or docs/FEATURES.md

## Batch Retry Unknown Extraction

The system includes a two-phase extraction process to improve AI accuracy:

### Individual Phase
Each email is processed independently through AI extraction to extract:
- Student ID
- Student Name  
- Assignment Name

### Batch Retry Phase
After all individual processing completes, emails with Unknown (null/None) fields
are collected and retried together in a single batch AI call. This provides more
context to the AI and improves extraction success rates.

### Configuration
- **Batch size**: Maximum 20 emails per API call (configurable)
- **Timeout**: 30 seconds per batch
- **Fallback**: Failed batches don't block the workflow

### Performance Metrics
The batch retry phase logs:
- Number of emails in batch
- Processing duration
- Improvement rate (success / total)
- Per-email average time

### Example Output
```
Batch Retry Phase: 3 emails
Calling batch AI extraction...
Batch retry performance:
  Emails processed: 3
  Duration: 4.52 seconds
  Average time per email: 1.51 seconds

✓ Batch retry succeeded for 1002
  student_id=2021001
  name=学生1
  assignment=作业1
  confidence=0.90

Batch retry metrics:
  Improvement rate: 66.7%
  Total processed: 3
  Successfully fixed: 2
  Still failed: 1
```
```

- [ ] **Step 2: Commit documentation**

```bash
git add README.md
# or: git add docs/FEATURES.md
git commit -m "docs: add batch retry feature documentation"
```

---

## Task 14: Final Integration Test

**Files:**
- None (run existing tests)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`

Expected: All tests PASS

- [ ] **Step 2: Run specific batch retry tests**

Run: `pytest tests/test_ai_batch_retry.py tests/test_workflow_batch_retry.py -v`

Expected: All batch retry tests PASS

- [ ] **Step 3: Verify no regressions**

Run: `pytest tests/ -v --tb=short`

Expected: No test failures

---

## Task 15: Code Review and Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Review all changes**

Run: `git diff master`

Check:
- Code follows existing patterns
- No hardcoded values
- Proper error handling
- Clear logging messages
- Type hints where appropriate

- [ ] **Step 2: Run linting (if configured)**

Run: `flake8 .` or `ruff check .` (whichever is configured)

Expected: No linting errors

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: complete batch retry unknown extraction feature

- Add batch_retry_unknown() method to AIExtractor
- Add pending_retry tracking to AssignmentWorkflow
- Implement process_pending_retry() method
- Extract _process_extracted_info() helper to avoid duplication
- Add comprehensive unit and integration tests
- Add performance metrics logging
- Add manual testing script

This improves AI extraction accuracy by re-analyzing emails with
Unknown results together in a batch, providing more context for
pattern recognition."
```

---

## Success Criteria Verification

- [ ] All unit tests pass (`pytest tests/test_ai_batch_retry.py -v`)
- [ ] All integration tests pass (`pytest tests/test_workflow_batch_retry.py -v`)
- [ ] Manual test script runs successfully (`python test_batch_retry_manual.py`)
- [ ] Full test suite passes with no regressions (`pytest tests/ -v`)
- [ ] Performance metrics are logged during batch retry
- [ ] Documentation is updated
- [ ] Code follows existing patterns and style

---

## Notes for Implementation

1. **AI Prompt Design**: The batch retry prompt emphasizes that analyzing multiple emails together provides context. The prompt includes previous failed results to help the AI understand what was missing.

2. **Batch Size Limit**: Set to 20 emails per API call to avoid overwhelming the AI model and hitting token limits. This can be adjusted based on performance testing.

3. **Error Handling**: Failed batches don't crash the workflow. They return None results and the emails stay marked as read (safe fallback).

4. **Re-processing Safety**: Before re-processing, we verify the email still exists in INBOX using `uid_exists()` to avoid duplicate processing.

5. **Performance Metrics**: Logging helps monitor the effectiveness of batch retry and identify patterns in extraction failures.

6. **Future Enhancements**: Consider adaptive batching based on historical success rates, or including low-confidence (not just None) extractions in batch retry.
