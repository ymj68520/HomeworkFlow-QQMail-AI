"""多作业提交处理器模块"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from database.models import Submission, SubmissionGroup, Attachment
from database.async_operations import async_db
from storage.manager import storage_manager
from mail.smtp_client import smtp_client
from config.settings import settings

logger = logging.getLogger(__name__)


class MultiAssignmentProcessor:
    """多作业提交处理器 - 处理包含多个作业的邮件提交"""

    def __init__(self):
        self.async_db = async_db
        self.storage = storage_manager
        self.smtp = smtp_client
        self.settings = settings

    async def process_multi_assignment(
        self,
        email_uid: str,
        email_data: Dict,
        detection_result: Dict
    ) -> Dict:
        """
        处理多作业提交的完整流程

        Args:
            email_uid: 邮件UID
            email_data: 邮件数据字典
            detection_result: 多作业检测结果

        Returns:
            处理结果字典:
            {
                'success': bool,
                'group_id': int or None,
                'submissions': List[Dict],
                'error': str or None,
                'action': str  # 'processed', 'manual_review', 'failed', 'already_processed'
            }
        """
        logger.info(f"Processing multi-assignment submission: {email_uid}")

        try:
            # 0. 幂等性检查 - 防止重复处理同一邮件
            existing_group = await self.async_db.get_submission_group_by_email_uid(email_uid)
            if existing_group:
                logger.info(f"Email {email_uid} already processed (group {existing_group.id}), returning existing result")
                return {
                    'success': existing_group.status in ['completed', 'partial'],
                    'group_id': existing_group.id,
                    'submissions': [],  # 简化返回，避免重复查询
                    'error': None if existing_group.status in ['completed', 'partial'] else f'Already processed with status: {existing_group.status}',
                    'action': 'already_processed'
                }

            # 1. 检查检测结果完整性
            if not detection_result.get('is_complete'):
                logger.warning(f"Incomplete detection result for {email_uid}")
                return await self._handle_incomplete(email_uid, email_data, detection_result)

            # 2. 创建提交组
            group = await self._create_group(email_uid, email_data, detection_result)
            if not group:
                return {
                    'success': False,
                    'group_id': None,
                    'submissions': [],
                    'error': 'Failed to create submission group',
                    'action': 'failed'
                }

            logger.info(f"Created submission group {group.id} for {email_uid}")

            # 3. 处理每个作业
            submissions = []
            assignments = detection_result.get('assignments', [])
            student_info = {
                'student_id': detection_result.get('student_id'),
                'name': detection_result.get('name')
            }

            for idx, assignment_info in enumerate(assignments, start=1):
                try:
                    submission = await self._process_assignment(
                        group=group,
                        assignment_info=assignment_info,
                        group_order=idx,
                        email_data=email_data,
                        student_info=student_info
                    )

                    if submission:
                        submissions.append({
                            'id': submission.id,
                            'assignment_name': assignment_info.get('assignment_name'),
                            'status': 'created'
                        })
                        logger.info(f"Created submission {submission.id} for assignment {assignment_info.get('assignment_name')}")
                    else:
                        submissions.append({
                            'id': None,
                            'assignment_name': assignment_info.get('assignment_name'),
                            'status': 'failed'
                        })
                        logger.error(f"Failed to create submission for assignment {assignment_info.get('assignment_name')}")

                except Exception as e:
                    logger.exception(f"Error processing assignment {assignment_info.get('assignment_name')}: {e}")
                    submissions.append({
                        'id': None,
                        'assignment_name': assignment_info.get('assignment_name'),
                        'status': 'error',
                        'error': str(e)
                    })

            # 4. 更新组状态
            success_count = sum(1 for s in submissions if s['status'] == 'created')
            total_count = len(assignments)

            if success_count == total_count:
                # 全部成功
                await self.async_db.update_group_status(
                    group.id,
                    status='completed',
                    total_assignments=success_count
                )
            elif success_count > 0:
                # 部分成功
                await self.async_db.update_group_status(
                    group.id,
                    status='partial',
                    total_assignments=success_count,
                    error_message=f'只成功处理了 {success_count}/{total_count} 个作业'
                )
            else:
                # 全部失败
                await self.async_db.update_group_status(
                    group.id,
                    status='failed',
                    total_assignments=0,
                    error_message='所有作业处理失败'
                )
                return {
                    'success': False,
                    'group_id': group.id,
                    'submissions': submissions,
                    'error': 'All assignments failed to process',
                    'action': 'failed'
                }

            # 5. 发送确认邮件
            if success_count > 0:
                try:
                    await self._send_confirmation_email(
                        group=group,
                        submissions=submissions,
                        to_email=email_data.get('sender_email', '')
                    )
                except Exception as e:
                    logger.exception(f"Error sending confirmation email: {e}")
                    # 确认邮件失败不影响整体处理结果

            return {
                'success': success_count > 0,
                'group_id': group.id,
                'submissions': submissions,
                'error': None if success_count == total_count else f'Partial success: {success_count}/{total_count}',
                'action': 'processed'
            }

        except Exception as e:
            logger.exception(f"Error in process_multi_assignment: {e}")
            # 尝试回滚
            if 'group' in locals() and group:
                await self._rollback_group(group.id, str(e))

            return {
                'success': False,
                'group_id': group.id if 'group' in locals() else None,
                'submissions': [],
                'error': str(e),
                'action': 'failed'
            }

    async def _create_group(
        self,
        email_uid: str,
        email_data: Dict,
        detection_result: Dict
    ) -> Optional[SubmissionGroup]:
        """
        创建提交组记录

        Args:
            email_uid: 邮件UID
            email_data: 邮件数据
            detection_result: 检测结果

        Returns:
            SubmissionGroup对象或None
        """
        try:
            # 计算总附件数
            assignments = detection_result.get('assignments', [])
            total_attachments = sum(
                len(assignment.get('attachments', []))
                for assignment in assignments
            )

            group = await self.async_db.create_submission_group(
                email_uid=email_uid,
                message_id=email_data.get('message_id'),
                email_subject=email_data.get('subject'),
                sender_email=email_data.get('sender_email'),
                sender_name=email_data.get('sender_name'),
                submission_time=datetime.now(),
                processing_mode='multi',
                detection_method=detection_result.get('detection_method'),
                ai_confidence=detection_result.get('overall_confidence'),
                total_assignments=len(assignments),
                total_attachments=total_attachments,
                status='processing'
            )

            return group

        except Exception as e:
            logger.error(f"Error creating submission group: {e}")
            return None

    async def _process_assignment(
        self,
        group: SubmissionGroup,
        assignment_info: Dict,
        group_order: int,
        email_data: Dict,
        student_info: Dict
    ) -> Optional[Submission]:
        """
        处理单个作业

        Args:
            group: 提交组对象
            assignment_info: 单个作业信息
            group_order: 在组中的顺序
            email_data: 原始邮件数据
            student_info: 学生信息

        Returns:
            Submission对象或None
        """
        try:
            # 1. 提取作业信息
            assignment_name = assignment_info.get('assignment_name')
            if not assignment_name:
                logger.error("Missing assignment_name in assignment_info")
                return None

            # 2. 过滤属于该作业的附件
            assignment_attachments = assignment_info.get('attachments', [])
            filtered_attachments = [
                att for att in email_data.get('attachments', [])
                if att['filename'] in assignment_attachments
            ]

            if not filtered_attachments:
                logger.warning(f"No attachments found for assignment {assignment_name}")
                # 继续处理，可能有些作业没有附件

            # 3. 存储附件到本地
            student_id = student_info.get('student_id', 'Unknown')
            name = student_info.get('name', 'Unknown')

            local_path = self.storage.store_submission(
                assignment_name=assignment_name,
                student_id=student_id,
                name=name,
                attachments=filtered_attachments
            )

            if not local_path:
                logger.error(f"Failed to store files for assignment {assignment_name}")
                return None

            # 4. 创建提交记录
            submission = await self.async_db.create_submission(
                email_uid=group.email_uid,
                message_id=email_data.get('message_id'),
                email_subject=email_data.get('subject'),
                sender_email=email_data.get('sender_email'),
                sender_name=name,
                submission_time=datetime.now(),
                student_id=student_id,
                assignment_name=assignment_name,
                local_path=local_path,
                status='pending',
                body=json.dumps(email_data.get('email_body'), ensure_ascii=False) if email_data.get('email_body') else None
            )

            if not submission:
                logger.error(f"Failed to create submission record for assignment {assignment_name}")
                return None

            # 5. 设置group关联
            submission.group_id = group.id
            submission.group_order = group_order
            submission.is_primary = False  # 多作业提交中的记录都不是主记录

            # 6. 添加附件记录
            for attachment in filtered_attachments:
                try:
                    await self._add_attachment_record(
                        submission_id=submission.id,
                        filename=attachment['filename'],
                        file_size=attachment['size'],
                        local_path=f"{local_path}/{attachment['filename']}"
                    )
                except Exception as e:
                    logger.error(f"Error adding attachment record for {attachment['filename']}: {e}")

            # 7. 提交更改
            await self.async_db.update_submission(
                submission_id=submission.id,
                group_id=group.id,
                group_order=group_order,
                is_primary=False
            )

            return submission

        except Exception as e:
            logger.exception(f"Error in _process_assignment: {e}")
            return None

    async def _add_attachment_record(
        self,
        submission_id: int,
        filename: str,
        file_size: int,
        local_path: str
    ) -> bool:
        """
        添加附件记录到数据库

        Args:
            submission_id: 提交记录ID
            filename: 文件名
            file_size: 文件大小
            local_path: 本地路径

        Returns:
            是否成功
        """
        try:
            from sqlalchemy import select
            from database.models import get_async_session, Attachment

            # 使用async_db模式创建session，保持一致性
            async with get_async_session()() as session:
                attachment = Attachment(
                    submission_id=submission_id,
                    filename=filename,
                    file_size=file_size,
                    local_path=local_path
                )
                session.add(attachment)
                await session.commit()
                await session.refresh(attachment)
                logger.debug(f"Added attachment record: {filename} for submission {submission_id}")
                return True

        except Exception as e:
            logger.error(f"Error adding attachment record: {e}")
            return False

    async def _handle_incomplete(
        self,
        email_uid: str,
        email_data: Dict,
        detection_result: Dict
    ) -> Dict:
        """
        处理不完整的识别结果

        创建一个manual_review状态的组，等待人工处理

        Args:
            email_uid: 邮件UID
            email_data: 邮件数据
            detection_result: 检测结果

        Returns:
            处理结果
        """
        logger.warning(f"Creating manual review group for {email_uid}")

        try:
            # 创建待人工审核的组
            group = await self.async_db.create_submission_group(
                email_uid=email_uid,
                message_id=email_data.get('message_id'),
                email_subject=email_data.get('subject'),
                sender_email=email_data.get('sender_email'),
                sender_name=email_data.get('sender_name'),
                submission_time=datetime.now(),
                processing_mode='multi',
                detection_method=detection_result.get('detection_method'),
                ai_confidence=detection_result.get('overall_confidence'),
                total_assignments=0,
                total_attachments=len(email_data.get('attachments', [])),
                status='manual_review'
            )

            if not group:
                return {
                    'success': False,
                    'group_id': None,
                    'submissions': [],
                    'error': 'Failed to create manual review group',
                    'action': 'failed'
                }

            # 保存错误详情
            error_details = json.dumps({
                'reasoning': detection_result.get('reasoning', ''),
                'unassigned_attachments': detection_result.get('unassigned_attachments', []),
                'assignments': detection_result.get('assignments', []),
                'student_id': detection_result.get('student_id'),
                'name': detection_result.get('name')
            }, ensure_ascii=False)

            await self.async_db.update_group_status(
                group.id,
                status='manual_review',
                error_message=detection_result.get('reasoning', 'Incomplete detection'),
                error_details=error_details
            )

            logger.info(f"Created manual review group {group.id} for {email_uid}")

            return {
                'success': True,
                'group_id': group.id,
                'submissions': [],
                'error': 'Manual review required',
                'action': 'manual_review'
            }

        except Exception as e:
            logger.exception(f"Error in _handle_incomplete: {e}")
            return {
                'success': False,
                'group_id': None,
                'submissions': [],
                'error': str(e),
                'action': 'failed'
            }

    async def _send_confirmation_email(
        self,
        group: SubmissionGroup,
        submissions: List[Dict],
        to_email: str
    ) -> bool:
        """
        发送多作业提交的综合确认邮件

        Args:
            group: 提交组对象
            submissions: 提交记录列表
            to_email: 收件人邮箱

        Returns:
            是否发送成功
        """
        if not self.settings.ENABLE_REPLY:
            logger.info("Reply feature is disabled, skipping confirmation email")
            return False

        if not to_email:
            logger.error("No recipient email address provided")
            return False

        try:
            # 构建邮件内容
            student_name = group.sender_name or '同学'
            assignment_names = [s['assignment_name'] for s in submissions if s['status'] == 'created']

            if not assignment_names:
                logger.error("No successful submissions to confirm")
                return False

            # 邮件主题
            subject = f"收到确认：{len(assignment_names)}个作业 - {student_name}"

            # 邮件正文
            body_lines = [
                f"{student_name}同学：",
                "",
                f"你的以下{len(assignment_names)}个作业已收到并确认：",
                ""
            ]

            for idx, assignment_name in enumerate(assignment_names, start=1):
                body_lines.append(f"{idx}. {assignment_name}")

            body_lines.extend([
                "",
                "如有问题，请联系助教。",
                "",
                "祝学习顺利！",
                "",
                "助教",
                datetime.now().strftime('%Y-%m-%d %H:%M')
            ])

            body = "\n".join(body_lines)

            # 发送邮件
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from email.utils import formataddr

            if not self.smtp.connection:
                if not self.smtp.connect():
                    logger.error("Failed to connect to SMTP server")
                    return False

            msg = MIMEMultipart()
            msg['From'] = formataddr(("助教", self.smtp.email))
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            self.smtp.connection.send_message(msg)
            logger.info(f"Multi-assignment confirmation email sent to {to_email}")

            # 移动邮件到目标文件夹
            # 注意：这里简化处理，实际可能需要更复杂的逻辑
            # 因为原始邮件已经包含多个作业，移动一次即可

            return True

        except Exception as e:
            logger.exception(f"Error sending confirmation email: {e}")
            return False

    async def _rollback_group(self, group_id: int, error_message: str):
        """
        回滚group处理，标记为失败状态并清理孤立文件

        Args:
            group_id: 组ID
            error_message: 错误信息
        """
        try:
            logger.error(f"Rolling back group {group_id}: {error_message}")

            # 获取组及其所有提交记录，以便清理文件
            group_with_submissions = await self.async_db.get_group_with_submissions(group_id)

            # 清理已存储的文件（如果有）
            if group_with_submissions:
                for submission in group_with_submissions.submissions:
                    if submission.local_path:
                        try:
                            deleted = self.storage.delete_files(submission.local_path)
                            if deleted:
                                logger.info(f"Cleaned up orphaned files for submission {submission.id}: {submission.local_path}")
                            else:
                                logger.warning(f"Failed to delete files or files not found: {submission.local_path}")
                        except Exception as file_error:
                            logger.error(f"Error deleting files for submission {submission.id}: {file_error}")
                            # 文件删除失败不影响回滚流程继续

            # 更新组状态为失败
            await self.async_db.update_group_status(
                group_id,
                status='failed',
                error_message=error_message,
                error_details=json.dumps({
                    'rollback_reason': error_message,
                    'rollback_time': datetime.now().isoformat(),
                    'files_cleaned': group_with_submissions is not None
                }, ensure_ascii=False)
            )

            # 注意：不删除已创建的submission记录，保留它们用于审计和故障排查
            # 可以通过group.status='failed'来识别这些记录

        except Exception as e:
            logger.exception(f"Error during rollback of group {group_id}: {e}")


# Global instance
multi_assignment_processor = MultiAssignmentProcessor()
