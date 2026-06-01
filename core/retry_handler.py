import asyncio
from typing import List, Dict, Optional, Callable
from mail.parser import mail_parser_target
from ai.extractor import ai_extractor
from database.operations import db
from core.workflow import workflow
from core.async_status_manager import get_async_status_manager
from database.async_operations import async_db
from config.settings import settings
from database.models import ProcessingStatus, AIExtractionStatus, DownloadStatus, AsyncSessionLocal

class RetryHandler:
    """Handles retry and re-analysis operations for failed submissions"""

    # 旧状态码（向后兼容）
    ABNORMAL_STATUSES = ['ai_error', 'download_failed', 'pending']

    # 新状态码（使用独立状态系统）
    ABNORMAL_PROCESSING_STATUSES = [ProcessingStatus.FAILED.value]
    ABNORMAL_AI_STATUSES = [AIExtractionStatus.FAILED.value]
    ABNORMAL_DOWNLOAD_STATUSES = [DownloadStatus.FAILED.value]

    def __init__(self):
        self.parser = mail_parser_target
        self.ai = ai_extractor
        self.db = db
        self.async_db = async_db
        self.workflow = workflow
        self.settings = settings
        self.status_mgr = None  # 延迟初始化

    def _get_status_manager(self):
        """获取状态管理器实例 - 每次创建新会话以避免锁问题"""
        # Create a new AsyncSession for each call to avoid SQLite lock issues
        session = AsyncSessionLocal()
        return get_async_status_manager(session)

    async def smart_retry_page(
        self,
        submissions: List[Dict],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict:
        """
        Re-process all abnormal entries on the current page

        Args:
            submissions: List of submission dicts from current page
            progress_callback: Optional callback(current, total, message)

        Returns:
            {
                'total': int,
                'success': int,
                'failed': int,
                'skipped': int,
                'details': List[Dict]
            }
        """
        # Filter for abnormal entries - 同时支持新旧状态系统
        abnormal_entries = []
        for s in submissions:
            # 优先使用新状态系统
            if s.get('processing_status') in self.ABNORMAL_PROCESSING_STATUSES:
                abnormal_entries.append(s)
            elif s.get('ai_status') in self.ABNORMAL_AI_STATUSES:
                abnormal_entries.append(s)
            elif s.get('download_status') in self.ABNORMAL_DOWNLOAD_STATUSES:
                abnormal_entries.append(s)
            # 向后兼容：旧状态字段
            elif s.get('status') in self.ABNORMAL_STATUSES:
                abnormal_entries.append(s)

        total = len(abnormal_entries)
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0, 'details': []}

        results = {
            'total': total,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }

        # Initial progress callback to show total
        if progress_callback:
            progress_callback(0, total, f"准备处理 {total} 条异常记录...")

        try:
            for idx, submission in enumerate(abnormal_entries):
                email_uid = submission.get('email_uid')
                student_id = submission.get('student_id', 'Unknown')
                name = submission.get('name', 'Unknown')

                if progress_callback:
                    progress_callback(idx + 1, total, f"正在处理: {name} ({student_id})")

                # Ensure IMAP connection (connect once, use for all emails)
                if not self.parser.imap.connection:
                    if progress_callback:
                        progress_callback(idx + 1, total, f"连接邮件服务器...")
                    if not self.parser.connect():
                        return {
                            **results,
                            'error': '无法连接到邮件服务器'
                        }

                # Check if email still exists
                submission_id = submission.get('id')
                message_id = submission.get('message_id')
                
                email_found = await self._email_exists(email_uid)
                
                # If not found by UID, try finding by Message-ID (handles moved emails)
                if not email_found and message_id:
                    print(f"[RetryHandler] UID {email_uid} not found, searching by Message-ID {message_id}...")
                    new_uid = self.parser.imap.find_email_by_message_id(message_id, self.settings.TARGET_FOLDER)
                    if not new_uid:
                        new_uid = self.parser.imap.find_email_by_message_id(message_id, 'INBOX')
                    
                    if new_uid:
                        print(f"[RetryHandler] Found email with new UID: {new_uid}")
                        email_uid = new_uid
                        # Update UID in database to prevent future lookup failures
                        self.db.update_submission_uid(submission_id, new_uid)
                        email_found = True

                if not email_found:
                    results['skipped'] += 1
                    results['details'].append({
                        'email_uid': email_uid,
                        'student_id': student_id,
                        'status': 'skipped',
                        'reason': 'Email no longer exists on server'
                    })
                    continue

                # 根据异常类型选择不同的重试路径
                is_ai_fail = self._is_ai_failure(submission)

                try:
                    # 两种路径都需要重新获取邮件数据（附件需要重新下载）
                    email_data = self.parser.parse_email(str(email_uid))
                    if not email_data:
                        results['failed'] += 1
                        results['details'].append({
                            'email_uid': email_uid,
                            'student_id': student_id,
                            'status': 'failed',
                            'reason': 'Failed to parse email'
                        })
                        continue

                    if is_ai_fail:
                        # PATH A: AI识别异常 → 从头重新处理（重新AI提取 + 完整后续流程）
                        print(f"[RetryHandler] AI failure for {student_id}, re-running full pipeline")
                        student_info = await self._extract_info(email_data)
                        result = await self.workflow._process_extracted_info(
                            email_uid=str(email_uid),
                            email_data=email_data,
                            student_info=student_info,
                            is_retry=True
                        )
                    else:
                        # PATH B: 其他异常（下载失败、回复失败等）→ 跳过AI提取，使用已有学生信息
                        print(f"[RetryHandler] Non-AI failure for {student_id}, skipping AI extraction")
                        existing_student_info = await self._get_existing_student_info(submission_id)
                        if not existing_student_info or not existing_student_info.get('student_id'):
                            results['failed'] += 1
                            results['details'].append({
                                'email_uid': email_uid,
                                'student_id': student_id,
                                'status': 'failed',
                                'reason': '无法从数据库加载学生信息'
                            })
                            continue

                        result = await self.workflow._process_extracted_info(
                            email_uid=str(email_uid),
                            email_data=email_data,
                            student_info=existing_student_info,
                            is_retry=True,
                            existing_submission_id=submission_id
                        )

                    if result.get('success'):
                        results['success'] += 1
                        results['details'].append({
                            'email_uid': email_uid,
                            'student_id': student_id,
                            'status': 'success',
                            'action': result.get('action')
                        })
                    else:
                        results['failed'] += 1
                        results['details'].append({
                            'email_uid': email_uid,
                            'student_id': student_id,
                            'status': 'failed',
                            'reason': result.get('error', 'Unknown error')
                        })

                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'email_uid': email_uid,
                        'student_id': student_id,
                        'status': 'failed',
                        'reason': str(e)
                    })

        finally:
            self.parser.disconnect()

        return results

    async def batch_reanalyze(
        self,
        submissions: List[Dict],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict:
        """
        Re-analyze selected entries using AI with fresh IMAP content

        Args:
            submissions: List of submission dicts (user-selected)
            progress_callback: Optional callback(current, total, message)

        Returns:
            {
                'total': int,
                'success': int,
                'failed': int,
                'details': List[Dict]
            }
        """
        total = len(submissions)
        if total == 0:
            return {'total': 0, 'success': 0, 'failed': 0, 'details': []}

        results = {
            'total': total,
            'success': 0,
            'failed': 0,
            'details': []
        }

        # Initial progress callback
        if progress_callback:
            progress_callback(0, total, f"准备重新分析 {total} 条记录...")

        # Ensure IMAP connection
        if not self.parser.connect():
            return {
                **results,
                'error': '无法连接到邮件服务器'
            }

        try:
            for idx, submission in enumerate(submissions):
                email_uid = submission.get('email_uid')
                submission_id = submission.get('id')
                student_id = submission.get('student_id', 'Unknown')

                # 如果没有数据库记录，先创建一个新的记录
                if not submission_id:
                    print(f"[RetryHandler] No database record found for {email_uid}, creating new record...")

                if progress_callback:
                    progress_callback(idx + 1, total, f"正在重新分析: {student_id}")

                # Fetch fresh email content
                email_data = self._fetch_fresh_email(str(email_uid))
                if not email_data:
                    results['failed'] += 1
                    results['details'].append({
                        'email_uid': email_uid,
                        'student_id': student_id,
                        'status': 'failed',
                        'reason': 'Failed to fetch email from server'
                    })
                    continue

                # Re-run AI extraction
                try:
                    student_info = await self.ai.extract_student_info(
                        subject=email_data['subject'],
                        sender=email_data['sender_email'],
                        attachments=email_data.get('attachments', [])
                    )

                    # Update database with new extraction results
                    new_student_id = student_info.get('student_id') or submission.get('student_id')
                    new_name = student_info.get('name') or submission.get('name')
                    new_assignment = student_info.get('assignment_name') or submission.get('assignment_name')

                    # 如果没有数据库记录，先创建一个新的记录
                    if not submission_id:
                        print(f"[RetryHandler] No database record found, creating new record for {email_uid}")

                        # 创建新的提交记录
                        import json
                        from datetime import datetime
                        body_json = json.dumps(email_data.get('email_body'), ensure_ascii=False) if email_data.get('email_body') else None

                        new_submission = await self.async_db.create_submission(
                            email_uid=email_uid,
                            email_subject=email_data.get('subject'),
                            sender_email=email_data.get('sender_email'),
                            sender_name=new_name,
                            submission_time=datetime.now(),
                            message_id=email_data.get('message_id'),
                            student_id=new_student_id,
                            assignment_name=new_assignment,
                            status='unreplied',
                            body=body_json
                        )

                        if not new_submission:
                            results['failed'] += 1
                            results['details'].append({
                                'email_uid': email_uid,
                                'student_id': new_student_id,
                                'status': 'failed',
                                'reason': 'Failed to create database record'
                            })
                            continue

                        submission_id = new_submission.id
                        print(f"[RetryHandler] Created new database record with ID {submission_id}")

                    # Determine new status based on extraction quality
                    if student_info.get('student_id') and student_info.get('name') and student_info.get('assignment_name'):
                        # Successfully re-analyzed - check for duplicates and merge
                        print(f"[RetryHandler] Re-analysis successful for {new_student_id} - {new_assignment}")
                        print(f"[RetryHandler] Checking for existing duplicates...")

                        # Check for duplicates using deduplication service
                        dedup_result = await self.workflow.dedup_service.check_submission(
                            student_id=new_student_id,
                            assignment_name=new_assignment
                        )

                        if dedup_result.is_duplicate and dedup_result.duplicate_type == 'submission':
                            # Found existing submission - need to merge as new version
                            print(f"[RetryHandler] Found duplicate submission (version {dedup_result.submission.version})")
                            print(f"[RetryHandler] Merging as new version...")

                            # Get next version number
                            next_version = dedup_result.version

                            # Import here to avoid circular dependency
                            import json
                            body_json = json.dumps(email_data.get('email_body'), ensure_ascii=False) if email_data.get('email_body') else None

                            # Update current submission to become a new version
                            # This involves: setting parent_id, updating version, marking as latest
                            success = await self._merge_as_new_version(
                                submission_id=submission_id,
                                email_uid=email_uid,
                                email_data=email_data,
                                student_info=student_info,
                                new_version=next_version,
                                original_submission_id=dedup_result.submission.id
                            )

                            if success:
                                results['success'] += 1
                                results['details'].append({
                                    'email_uid': email_uid,
                                    'student_id': new_student_id,
                                    'status': 'success',
                                    'action': 'merged_as_new_version',
                                    'new_version': next_version,
                                    'parent_id': dedup_result.submission.id
                                })
                            else:
                                results['failed'] += 1
                                results['details'].append({
                                    'email_uid': email_uid,
                                    'student_id': new_student_id,
                                    'status': 'failed',
                                    'reason': 'Failed to merge as new version'
                                })
                        else:
                            # No duplicate found - just update the current record
                            print(f"[RetryHandler] No duplicate found, updating current record")

                            new_status = 'unreplied'
                            status_mgr = self._get_status_manager()
                            try:
                                await status_mgr.transition(
                                    submission_id, 'ai_extraction', AIExtractionStatus.SUCCESS,
                                    reason='重新AI提取成功'
                                )

                                success = self.db.update_submission_full(
                                    submission_id=submission_id,
                                    student_id=new_student_id,
                                    name=new_name,
                                    assignment_name=new_assignment,
                                    status=new_status,
                                    email=submission.get('email'),
                                    email_uid=email_uid,
                                    email_subject=email_data.get('subject'),
                                    sender_email=email_data.get('sender_email'),
                                    submission_time=submission.get('submission_time')
                                )

                                if success:
                                    results['success'] += 1
                                    results['details'].append({
                                        'email_uid': email_uid,
                                        'student_id': new_student_id,
                                        'status': 'success',
                                        'action': 'updated'
                                    })
                                else:
                                    results['failed'] += 1
                                    results['details'].append({
                                        'email_uid': email_uid,
                                        'student_id': new_student_id,
                                        'status': 'failed',
                                        'reason': 'Database update failed'
                                    })
                            finally:
                                await status_mgr.close()
                    else:
                        # Still has issues after re-analysis
                        new_status = 'ai_error'
                        status_mgr = self._get_status_manager()
                        try:
                            await status_mgr.transition(
                                submission_id, 'ai_extraction', AIExtractionStatus.FAILED,
                                reason='重新AI提取仍然失败'
                            )

                            success = self.db.update_submission_full(
                                submission_id=submission_id,
                                student_id=new_student_id,
                                name=new_name,
                                assignment_name=new_assignment,
                                status=new_status,
                                email=submission.get('email'),
                                email_uid=email_uid,
                                email_subject=email_data.get('subject'),
                                sender_email=email_data.get('sender_email'),
                                submission_time=submission.get('submission_time')
                            )

                            if success:
                                results['failed'] += 1  # Still failed, so count as failed
                                results['details'].append({
                                    'email_uid': email_uid,
                                    'student_id': new_student_id,
                                    'status': 'failed',
                                    'reason': 'AI extraction still incomplete',
                                    'action': 'updated_with_errors'
                                })
                            else:
                                results['failed'] += 1
                                results['details'].append({
                                    'email_uid': email_uid,
                                    'student_id': new_student_id,
                                    'status': 'failed',
                                    'reason': 'Database update failed'
                                })
                        finally:
                            await status_mgr.close()

                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'email_uid': email_uid,
                        'student_id': student_id,
                        'status': 'failed',
                        'reason': str(e)
                    })

        finally:
            self.parser.disconnect()

        return results

    def _is_ai_failure(self, submission: Dict) -> bool:
        """判断是否为AI识别异常（需要从头重新处理）"""
        # 新状态系统: ai_status == 'failed'
        if submission.get('ai_status') == AIExtractionStatus.FAILED.value:
            return True
        # 旧状态系统: status == 'ai_error'
        if submission.get('status') == 'ai_error':
            return True
        # pending 表示从未完成过处理，也需要AI重新提取
        if submission.get('status') == 'pending':
            return True
        return False

    async def _get_existing_student_info(self, submission_id: int) -> Optional[Dict]:
        """从数据库加载已有的学生信息（用于跳过AI提取的重试路径）"""
        submission = self.db.get_submission_by_id(submission_id)
        if not submission:
            return None
        return {
            'student_id': submission.student.student_id if submission.student else None,
            'name': submission.student.name if submission.student else None,
            'assignment_name': submission.assignment.name if submission.assignment else None,
            'is_assignment': True,
        }

    async def _email_exists(self, email_uid: str) -> bool:
        """Check if email still exists on server"""
        try:
            # Try TARGET_FOLDER first
            if self.parser.imap.select_folder(self.settings.TARGET_FOLDER):
                exists = self.parser.imap.uid_exists(str(email_uid))
                if exists:
                    print(f"[RetryHandler] Email {email_uid} found in TARGET_FOLDER")
                    return True

            # Fallback to INBOX
            if self.parser.imap.select_folder('INBOX'):
                exists = self.parser.imap.uid_exists(str(email_uid))
                if exists:
                    print(f"[RetryHandler] Email {email_uid} found in INBOX")
                    return exists

            print(f"[RetryHandler] Email {email_uid} not found in either folder")
            return False
        except Exception as e:
            print(f"[RetryHandler] Error checking email {email_uid}: {e}")
            return False

    def _fetch_fresh_email(self, email_uid: str) -> Optional[Dict]:
        """Fetch fresh email content from IMAP"""
        try:
            # Try TARGET_FOLDER first
            if self.parser.imap.select_folder(self.settings.TARGET_FOLDER):
                # Check if UID exists before parsing
                if self.parser.imap.uid_exists(email_uid):
                    email_data = self.parser.parse_email(email_uid)
                    if email_data:
                        return email_data

            # Fallback to INBOX only if not found in TARGET_FOLDER
            if self.parser.imap.select_folder('INBOX'):
                # Check if UID exists before parsing
                if self.parser.imap.uid_exists(email_uid):
                    email_data = self.parser.parse_email(email_uid)
                    if email_data:
                        return email_data

            print(f"[RetryHandler] Email {email_uid} not found in either folder")
            return None
        except Exception as e:
            print(f"[RetryHandler] Error fetching email {email_uid}: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _extract_info(self, email_data: Dict) -> Dict:
        """Extract student info from email data"""
        return await self.ai.extract_student_info(
            subject=email_data['subject'],
            sender=email_data['sender_email'],
            attachments=email_data.get('attachments', [])
        )

    async def _merge_as_new_version(
        self,
        submission_id: int,
        email_uid: str,
        email_data: Dict,
        student_info: Dict,
        new_version: int,
        original_submission_id: int
    ) -> bool:
        """
        将当前提交合并为现有记录的新版本

        Args:
            submission_id: 当前提交记录ID
            email_uid: 邮件UID
            email_data: 邮件数据
            student_info: 学生信息
            new_version: 新版本号
            original_submission_id: 原始提交记录ID

        Returns:
            是否成功
        """
        if not submission_id:
            print(f"[RetryHandler] Cannot merge submission with ID None")
            return False

        try:
            import json
            from datetime import datetime

            body_json = json.dumps(email_data.get('email_body'), ensure_ascii=False) if email_data.get('email_body') else None

            # 使用异步数据库更新
            success = await self.async_db.update_submission(
                submission_id=submission_id,
                student_id=student_info.get('student_id'),
                assignment_name=student_info.get('assignment_name'),
                email_uid=email_uid,
                message_id=email_data.get('message_id'),
                email_subject=email_data.get('subject'),
                sender_email=email_data.get('sender_email'),
                sender_name=student_info.get('name'),
                submission_time=datetime.now(),
                body=body_json,
                version=new_version,
                is_latest=True,
                is_primary=False,  # 这是一个子版本
                parent_id=original_submission_id,
                relation_type='version'
            )

            if not success:
                print(f"[RetryHandler] Failed to update submission {submission_id}")
                return False

            # 使用状态管理器更新状态
            status_mgr = self._get_status_manager()
            try:
                await status_mgr.transition(
                    submission_id, 'ai_extraction', AIExtractionStatus.SUCCESS,
                    reason='重新AI提取成功并合并为新版本'
                )
                await status_mgr.transition(
                    submission_id, 'processing', ProcessingStatus.DOWNLOADED,
                    reason='已合并为新版本'
                )

                # 标记原记录为非最新版本
                await self.async_db.mark_submission_not_latest(original_submission_id)

                print(f"[RetryHandler] Successfully merged submission {submission_id} as version {new_version} of {original_submission_id}")
                return True
            finally:
                await status_mgr.close()

        except Exception as e:
            print(f"[RetryHandler] Error merging as new version: {e}")
            import traceback
            traceback.print_exc()
            return False

# Global instance
retry_handler = RetryHandler()
