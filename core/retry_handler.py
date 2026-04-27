import asyncio
from typing import List, Dict, Optional, Callable
from mail.parser import mail_parser_target
from ai.extractor import ai_extractor
from database.operations import db
from core.workflow import workflow
from config.settings import settings

class RetryHandler:
    """Handles retry and re-analysis operations for failed submissions"""

    # Status codes that indicate abnormal/failed entries
    ABNORMAL_STATUSES = ['ai_error', 'download_failed', 'pending']

    def __init__(self):
        self.parser = mail_parser_target
        self.ai = ai_extractor
        self.db = db
        self.workflow = workflow
        self.settings = settings

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
        # Filter for abnormal entries
        abnormal_entries = [
            s for s in submissions
            if s.get('status') in self.ABNORMAL_STATUSES
        ]

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

        # Ensure IMAP connection
        if not self.parser.connect():
            return {
                **results,
                'error': '无法连接到邮件服务器'
            }

        try:
            for idx, submission in enumerate(abnormal_entries):
                email_uid = submission.get('email_uid')
                student_id = submission.get('student_id', 'Unknown')
                name = submission.get('name', 'Unknown')

                if progress_callback:
                    progress_callback(idx + 1, total, f"正在处理: {name} ({student_id})")

                # Check if email still exists
                if not await self._email_exists(email_uid):
                    results['skipped'] += 1
                    results['details'].append({
                        'email_uid': email_uid,
                        'student_id': student_id,
                        'status': 'skipped',
                        'reason': 'Email no longer exists on server'
                    })
                    continue

                # Re-run full workflow
                try:
                    email_data = self.parser.parse_email(email_uid)
                    if not email_data:
                        results['failed'] += 1
                        results['details'].append({
                            'email_uid': email_uid,
                            'student_id': student_id,
                            'status': 'failed',
                            'reason': 'Failed to parse email'
                        })
                        continue

                    # Re-process with workflow
                    result = await self.workflow._process_extracted_info(
                        email_uid=email_uid,
                        email_data=email_data,
                        student_info=await self._extract_info(email_data),
                        is_retry=True
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

                if progress_callback:
                    progress_callback(idx + 1, total, f"正在重新分析: {student_id}")

                # Fetch fresh email content
                email_data = self._fetch_fresh_email(email_uid)
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

                    # Determine new status based on extraction quality
                    if student_info.get('student_id') and student_info.get('name') and student_info.get('assignment_name'):
                        new_status = 'unreplied'  # Successfully re-analyzed
                    else:
                        new_status = 'ai_error'  # Still has issues

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
                            'old_status': submission.get('status'),
                            'new_status': new_status,
                            'status': 'success'
                        })
                    else:
                        results['failed'] += 1
                        results['details'].append({
                            'email_uid': email_uid,
                            'student_id': student_id,
                            'status': 'failed',
                            'reason': 'Database update failed'
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

    async def _email_exists(self, email_uid: str) -> bool:
        """Check if email still exists on server"""
        try:
            # Try TARGET_FOLDER first
            if self.parser.imap.select_folder(self.settings.TARGET_FOLDER):
                exists = self.parser.uid_exists(email_uid)
                if exists:
                    return True

            # Fallback to INBOX
            if self.parser.imap.select_folder('INBOX'):
                exists = self.parser.uid_exists(email_uid)
                return exists

            return False
        except Exception:
            return False

    def _fetch_fresh_email(self, email_uid: str) -> Optional[Dict]:
        """Fetch fresh email content from IMAP"""
        try:
            # Try TARGET_FOLDER first
            if self.parser.imap.select_folder(self.settings.TARGET_FOLDER):
                email_data = self.parser.parse_email(email_uid)
                if email_data:
                    return email_data

            # Fallback to INBOX
            if self.parser.imap.select_folder('INBOX'):
                email_data = self.parser.parse_email(email_uid)
                if email_data:
                    return email_data

            return None
        except Exception as e:
            print(f"Error fetching email {email_uid}: {e}")
            return None

    async def _extract_info(self, email_data: Dict) -> Dict:
        """Extract student info from email data"""
        return await self.ai.extract_student_info(
            subject=email_data['subject'],
            sender=email_data['sender_email'],
            attachments=email_data.get('attachments', [])
        )

# Global instance
retry_handler = RetryHandler()
