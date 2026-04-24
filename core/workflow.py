import asyncio
from datetime import datetime
from typing import Optional, Dict
from mail.parser import mail_parser_inbox as mail_parser, mail_parser_target
from ai.extractor import ai_extractor
from database.operations import db
from storage.manager import storage_manager
from mail.imap_client import imap_client_inbox
from mail.smtp_client import smtp_client
from core.deduplication import deduplication_handler
from config.settings import settings
from database.models import SubmissionStatus, Submission

class AssignmentWorkflow:
    """作业处理主流程"""

    def __init__(self):
        self.parser = mail_parser
        self.ai = ai_extractor
        self.db = db
        self.storage = storage_manager
        self.imap = imap_client_inbox
        self.smtp = smtp_client
        self.dedup = deduplication_handler
        self.settings = settings
        self.pending_retry = []  # Track emails needing batch retry

    async def process_new_email(self, email_uid: str) -> dict:
        """
        处理新邮件的完整流程

        Args:
            email_uid: 邮件UID

        Returns:
            处理结果字典
        """
        print(f"\nProcessing email: {email_uid}")

        try:
            # 1. 解析邮件
            email_data = self.parser.parse_email(email_uid)
            if not email_data:
                return {'success': False, 'error': 'Failed to parse email', 'action': 'skipped'}

            print(f"Subject: {email_data['subject']}")
            print(f"From: {email_data['sender_name']} ({email_data['sender_email']})")
            print(f"Attachments: {len(email_data['attachments'])}")

            # 2. 检查是否有附件
            if not email_data['has_attachments']:
                print("No attachments found, marking as read")
                self.parser.mark_as_read(email_uid)
                # 记录为忽略
                self.db.create_submission(
                    email_uid=email_uid,
                    message_id=email_data.get('message_id'),
                    email_subject=email_data['subject'],
                    sender_email=email_data['sender_email'],
                    sender_name=email_data['sender_name'],
                    submission_time=datetime.now(),
                    status=SubmissionStatus.IGNORED.value,
                    error_message='No attachments'
                )
                self.db.log_email_action(
                    email_uid=email_uid,
                    action='marked_read',
                    folder='INBOX',
                    details='No attachments'
                )
                return {'success': True, 'action': 'marked_read', 'reason': 'no_attachments'}

            # 3. AI提取学生信息
            print("Extracting student info using AI...")
            student_info = await self.ai.extract_student_info(
                subject=email_data['subject'],
                sender=email_data['sender_email'],
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

            # 4. 判断是否为作业提交
            if not student_info.get('is_assignment'):
                print("Not an assignment submission, marking as read")
                self.parser.mark_as_read(email_uid)
                # 记录为忽略
                self.db.create_submission(
                    email_uid=email_uid,
                    message_id=email_data.get('message_id'),
                    email_subject=email_data['subject'],
                    sender_email=email_data['sender_email'],
                    sender_name=email_data['sender_name'],
                    submission_time=datetime.now(),
                    status=SubmissionStatus.IGNORED.value,
                    error_message='Not an assignment'
                )
                self.db.log_email_action(
                    email_uid=email_uid,
                    action='marked_read',
                    folder='INBOX',
                    details='Not an assignment'
                )
                return {'success': True, 'action': 'marked_read', 'reason': 'not_assignment'}

            # 5. 验证必要信息
            student_id = student_info.get('student_id')
            student_name = student_info.get('name')
            assignment_name = student_info.get('assignment_name')

            if not all([student_id, student_name, assignment_name]):
                print("Missing required information, marking as read")
                self.parser.mark_as_read(email_uid)
                # 记录为 AI 提取异常
                self.db.create_submission(
                    email_uid=email_uid,
                    email_subject=email_data['subject'],
                    sender_email=email_data['sender_email'],
                    sender_name=email_data['sender_name'],
                    submission_time=datetime.now(),
                    status=SubmissionStatus.AI_ERROR.value,
                    error_message=f'Missing info: student_id={student_id}, name={student_name}, assignment={assignment_name}'
                )
                self.db.log_email_action(
                    email_uid=email_uid,
                    action='marked_read',
                    folder='INBOX',
                    details=f'Missing info: student_id={student_id}, name={student_name}, assignment={assignment_name}'
                )
                return {'success': True, 'action': 'marked_read', 'reason': 'missing_info'}

            # 6. 继续处理正常流程
            return await self._process_extracted_info(email_uid, email_data, student_info)

        except Exception as e:
            print(f"Error processing email {email_uid}: {e}")
            import traceback
            traceback.print_exc()

            self.db.log_email_action(
                email_uid=email_uid,
                action='error',
                folder='INBOX',
                error_message=str(e)
            )

            return {'success': False, 'error': str(e), 'action': 'error'}

    async def _process_extracted_info(
        self,
        email_uid: str,
        email_data: Dict,
        student_info: Dict,
        is_retry: bool = False
    ) -> dict:
        """
        Process email with already-extracted student info
        This contains steps from deduplication to reply

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

        # 获取必要信息
        student_id = student_info.get('student_id')
        student_name = student_info.get('name')
        assignment_name = student_info.get('assignment_name')

        # 1. 检查是否为重复提交
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

        # 2. 保存附件到本地
        print("Storing attachments locally...")
        local_path = self.storage.store_submission(
            assignment_name=assignment_name,
            student_id=student_id,
            name=student_name,
            attachments=email_data['attachments']
        )

        print(f"Files stored at: {local_path}")

        # 3. 存储到数据库
        print("Saving to database...")
        status = SubmissionStatus.UNREPLIED.value if local_path else SubmissionStatus.DOWNLOAD_FAILED.value
        submission = self.db.create_submission(
            student_id=student_id,
            assignment_name=assignment_name,
            email_uid=email_uid,
            email_subject=email_data['subject'],
            sender_email=email_data['sender_email'],
            sender_name=student_name,
            submission_time=datetime.now(),
            local_path=local_path,
            status=status
        )

        if not submission:
            return {'success': False, 'error': 'Failed to save to database', 'action': 'db_failed'}

        # 4. 添加附件记录
        for attachment in email_data['attachments']:
            self.db.add_attachment(
                submission_id=submission.id,
                filename=attachment['filename'],
                file_size=attachment['size'],
                local_path=f"{local_path}/{attachment['filename']}"
            )

        # 5. 移动邮件到目标文件夹
        print(f"Moving email to {self.settings.TARGET_FOLDER}...")
        if not self.imap.folder_exists(self.settings.TARGET_FOLDER):
            print(f"Creating target folder: {self.settings.TARGET_FOLDER}")
            self.imap.create_folder(self.settings.TARGET_FOLDER)

        move_success = self.parser.move_to_folder(email_uid, self.settings.TARGET_FOLDER)

        if not move_success:
            print(f"Warning: Failed to move email to {self.settings.TARGET_FOLDER}")

        # 6. 发送确认邮件
        print("Sending confirmation email...")
        reply_sent = self.smtp.send_reply(
            to_email=email_data['sender_email'],
            student_name=student_name,
            assignment_name=assignment_name
        )

        # 7. 标记已回复
        if reply_sent:
            self.db.mark_replied(submission.id)
            self.db.update_submission_status(submission.id, SubmissionStatus.COMPLETED.value)

        # 8. 记录日志
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

    def delete_submission(self, submission_id: int) -> bool:
        """
        处理删除逻辑：
        1. 从数据库获取记录
        2. 将邮件从TARGET_FOLDER移动回INBOX
        3. 删除本地文件
        4. 删除数据库记录
        """
        # 1. Fetch submission
        submission = self.db.session.query(Submission).filter_by(id=submission_id).first()
        if not submission:
            print(f"Submission {submission_id} not found in DB.")
            return False
            
        email_uid = submission.email_uid
        local_path = submission.local_path
        
        # 2. Move email back to INBOX
        if self.settings.TARGET_FOLDER:
            # 确保连接
            if not mail_parser_target.imap.connection:
                mail_parser_target.connect()
                
            # 选择 TARGET_FOLDER
            if mail_parser_target.imap.select_folder(self.settings.TARGET_FOLDER):
                # 移动回 INBOX
                success = mail_parser_target.imap.move_email(email_uid, 'INBOX')
                if not success:
                    print(f"Warning: Failed to move email {email_uid} back to INBOX")
                else:
                    self.db.log_email_action(
                        email_uid=email_uid,
                        action='moved_to_inbox',
                        folder=self.settings.TARGET_FOLDER,
                        details="Moved back to INBOX during deletion"
                    )
            else:
                print(f"Warning: Could not select folder {self.settings.TARGET_FOLDER}")
        
        # 3. Delete local files
        if local_path:
            self.storage.delete_files(local_path)
            
        # 4. Delete DB record
        return self.db.delete_submission(submission_id)

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
            import time
            batch_start_time = time.time()

            retry_results = await self.ai.batch_retry_unknown(self.pending_retry)

            batch_duration = time.time() - batch_start_time

            # Log performance metrics
            print(f"\nBatch retry performance:")
            print(f"  Emails processed: {len(self.pending_retry)}")
            print(f"  Duration: {batch_duration:.2f} seconds")
            print(f"  Average time per email: {batch_duration/len(self.pending_retry):.2f} seconds")

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

            # Calculate improvement rate
            improvement_rate = (results['retry_success'] / results['total'] * 100) if results['total'] > 0 else 0
            print(f"\nBatch retry metrics:")
            print(f"  Improvement rate: {improvement_rate:.1f}%")
            print(f"  Total processed: {results['total']}")
            print(f"  Successfully fixed: {results['retry_success']}")
            print(f"  Still failed: {results['retry_failed']}")

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

    async def process_inbox(self) -> dict:
        """处理收件箱中的所有未读邮件"""
        print("\n" + "="*50)
        print("Starting inbox processing...")
        print("="*50)

        # 连接到邮箱
        if not self.parser.connect():
            return {'success': False, 'error': 'Failed to connect to email', 'processed': 0}

        try:
            # 获取所有未读邮件
            new_emails = self.parser.get_new_emails()
            print(f"Found {len(new_emails)} new emails")

            results = {
                'total': len(new_emails),
                'processed': 0,
                'marked_read': 0,
                'errors': 0,
                'details': []
            }

            # 处理每封邮件
            for email_data in new_emails:
                result = await self.process_new_email(email_data['uid'])
                results['details'].append(result)

                if result['success']:
                    if result['action'] == 'processed':
                        results['processed'] += 1
                    elif result['action'] == 'marked_read':
                        results['marked_read'] += 1
                    elif result['action'] == 'updated_duplicate':
                        results['processed'] += 1
                else:
                    results['errors'] += 1

            # Process emails with Unknown results using batch retry
            await self.process_pending_retry()

            print("\n" + "="*50)
            print(f"Processing complete:")
            print(f"  Total emails: {results['total']}")
            print(f"  Processed: {results['processed']}")
            print(f"  Marked as read: {results['marked_read']}")
            print(f"  Errors: {results['errors']}")
            print("="*50 + "\n")

            return results

        finally:
            self.parser.disconnect()

    async def monitor_inbox(self, interval: int = 60):
        """持续监听收件箱"""
        print(f"Starting inbox monitoring (interval: {interval}s)...")

        while True:
            try:
                await self.process_inbox()
                await asyncio.sleep(interval)

            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval * 2)

# Global workflow instance
workflow = AssignmentWorkflow()
