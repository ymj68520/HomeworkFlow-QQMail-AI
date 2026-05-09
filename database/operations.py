import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from database.models import db_session, Student, Assignment, Submission, Attachment, EmailLog
from sqlalchemy import or_, and_
import sqlite3
import functools
import inspect
from database.write_queue import write_queue

# 数据变更通知器 - 延迟导入以避免循环依赖
def _get_notifier():
    """延迟获取通知器实例，避免启动时的 Qt 依赖问题"""
    try:
        from core.data_change_notifier import data_change_notifier
        return data_change_notifier
    except ImportError:
        return None


def _queued_write(func):
    """
    装饰器：自动将写操作通过写队列执行

    检测调用上下文，自动选择同步或异步执行
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # 检查是否在异步上下文中
        try:
            import asyncio
            asyncio.get_running_loop()
            # 在异步上下文中，直接执行原始函数
            # （因为异步操作已经通过 async_db 处理）
            return func(self, *args, **kwargs)
        except RuntimeError:
            # 同步上下文，通过写队列执行
            def _exec():
                return func(self, *args, **kwargs)
            return write_queue.submit_sync(_exec)

    return wrapper

class DatabaseOperations:
    @property
    def session(self):
        return db_session()

    def __init__(self):
        # 启动写队列
        write_queue.start()

    def _write(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过写队列执行写操作

        自动检测当前是否在异步上下文中：
        - 异步上下文：返回可等待对象
        - 同步上下文：同步等待结果
        """
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            # 在异步上下文中
            return write_queue.submit_async(func, *args, **kwargs)
        except RuntimeError:
            # 同步上下文
            return write_queue.submit_sync(func, *args, **kwargs)

    @_queued_write
    def create_student(self, student_id: str, name: str, email: Optional[str] = None) -> Student:
        """Create or get existing student"""
        student = self.session.query(Student).filter_by(student_id=student_id).first()
        if not student:
            student = Student(student_id=student_id, name=name, email=email)
            self.session.add(student)
            self.session.commit()
            self.session.refresh(student)
        return student

    def get_student(self, student_id: str) -> Optional[Student]:
        """Get student by student_id"""
        return self.session.query(Student).filter_by(student_id=student_id).first()

    @_queued_write
    def create_assignment(self, name: str, deadline: Optional[datetime] = None) -> Assignment:
        """Create or get existing assignment"""
        assignment = self.session.query(Assignment).filter_by(name=name).first()
        if not assignment:
            assignment = Assignment(name=name, deadline=deadline)
            self.session.add(assignment)
            self.session.commit()
            self.session.refresh(assignment)
        return assignment

    def get_assignment(self, name: str) -> Optional[Assignment]:
        """Get assignment by name"""
        return self.session.query(Assignment).filter_by(name=name).first()

    @_queued_write
    def update_assignment_deadline(self, name: str, deadline: datetime) -> bool:
        """Update assignment deadline"""
        assignment = self.get_assignment(name)
        if assignment:
            assignment.deadline = deadline
            self.session.commit()
            return True
        return False

    @_queued_write
    def create_submission(
        self,
        email_uid: str,
        email_subject: str,
        sender_email: str,
        sender_name: str,
        submission_time: datetime,
        message_id: Optional[str] = None,
        student_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        local_path: Optional[str] = None,
        version: int = 1,
        is_latest: bool = True,
        status: str = 'pending',
        error_message: Optional[str] = None,
        body: Optional[str] = None
    ) -> Optional[Submission]:
        """Create or update a submission with status tracking"""
        try:
            # 1. 查找或创建学生 (不调用其他写方法，避免嵌套队列调用)
            student_db_id = None
            assignment_obj = None
            assignment_db_id = None

            if student_id and student_id != 'Unknown':
                student = self.session.query(Student).filter_by(student_id=student_id).first()
                if not student:
                    student = Student(student_id=student_id, name=sender_name or "Unknown", email=sender_email)
                    self.session.add(student)
                    self.session.flush()
                    student_db_id = student.id
                else:
                    student_db_id = student.id
                    # 更新学生信息
                    if student.name != (sender_name or "Unknown"):
                        student.name = sender_name or "Unknown"
                    if sender_email and student.email != sender_email:
                        student.email = sender_email

            # 2. 查找或创建作业 (不调用其他写方法)
            if assignment_name and assignment_name != 'Unknown':
                assignment = self.session.query(Assignment).filter_by(name=assignment_name).first()
                if not assignment:
                    assignment = Assignment(name=assignment_name)
                    self.session.add(assignment)
                    self.session.flush()
                    assignment_obj = assignment
                    assignment_db_id = assignment.id
                else:
                    assignment_obj = assignment
                    assignment_db_id = assignment.id

            # 3. 检查是否已存在记录
            existing = None
            if message_id:
                existing = self.session.query(Submission).filter_by(message_id=message_id).first()

            if not existing:
                existing = self.session.query(Submission).filter_by(email_uid=email_uid).first()

            # 计算是否逾期
            is_late = False
            if assignment_obj and assignment_obj.deadline and submission_time > assignment_obj.deadline:
                is_late = True

            if existing:
                # 更新现有记录
                if student_db_id is not None: existing.student_id = student_db_id
                if assignment_db_id is not None: existing.assignment_id = assignment_db_id
                if message_id: existing.message_id = message_id
                existing.email_uid = email_uid
                existing.email_subject = email_subject
                existing.submission_time = submission_time
                if local_path: existing.local_path = local_path
                if body: existing.body = body
                existing.version = version
                existing.is_latest = is_latest
                existing.is_late = is_late
                existing.status = status
                if error_message:
                    existing.error_message = error_message
                existing.updated_at = datetime.now()
                submission = existing
            else:
                # 创建新记录
                submission = Submission(
                    student_id=student_db_id,
                    assignment_id=assignment_db_id,
                    message_id=message_id,
                    email_uid=email_uid,
                    email_subject=email_subject,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    submission_time=submission_time,
                    body=body,
                    is_late=is_late,
                    local_path=local_path,
                    version=version,
                    is_latest=is_latest,
                    status=status,
                    error_message=error_message
                )
                self.session.add(submission)

            self.session.commit()
            self.session.refresh(submission)

            # 发送数据变更通知
            notifier = _get_notifier()
            if notifier:
                notifier.notify_record_created(
                    uid=email_uid,
                    submission_id=submission.id,
                    student_id=student_id,
                    assignment_name=assignment_name
                )

            return submission

        except Exception as e:
            self.session.rollback()
            print(f"Error creating submission: {e}")
            import traceback
            traceback.print_exc()
            return None

    @_queued_write
    def update_submission_status(self, submission_id: int, status: str, error_message: Optional[str] = None) -> bool:
        """Update submission status and optional error message"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                submission.status = status
                if error_message is not None:
                    submission.error_message = error_message
                
                # 兼容旧字段
                if status == 'completed':
                    submission.is_replied = True
                    submission.is_downloaded = True
                elif status == 'unreplied':
                    submission.is_downloaded = True
                elif status == 'download_failed':
                    submission.is_downloaded = False
                    
                self.session.commit()

                # 发送数据变更通知
                notifier = _get_notifier()
                if notifier:
                    notifier.notify_record_updated(
                        uid=submission.email_uid,
                        submission_id=submission_id,
                        changes={'status': status}
                    )

                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error updating submission status: {e}")
            return False

    @_queued_write
    def update_submission_full(
        self,
        submission_id: Optional[int],
        student_id: str,
        name: str,
        assignment_name: str,
        status: str,
        email: Optional[str] = None,
        email_uid: Optional[str] = None,
        email_subject: Optional[str] = None,
        sender_email: Optional[str] = None,
        submission_time: Optional[datetime] = None
    ) -> bool:
        """
        Full update of a submission, including student and assignment associations.
        If submission_id is not found but email_uid is provided, create a new submission.
        """
        try:
            # 1. Get submission
            submission = None
            if submission_id:
                submission = self.session.query(Submission).filter_by(id=submission_id).first()
            
            if not submission and email_uid:
                submission = self.session.query(Submission).filter_by(email_uid=email_uid).first()
            
            # 2. Get or create student
            student = self.create_student(student_id, name, email)
            student_changed = False
            if student.name != name:
                student.name = name
                student_changed = True
            if email and student.email != email:
                student.email = email
                student_changed = True
            
            if student_changed:
                self.session.add(student)

            # 3. Get or create assignment
            assignment = self.create_assignment(assignment_name)

            # 4. If still no submission, create it now that we have student and assignment IDs
            if not submission:
                if email_uid:
                    print(f"Submission not found for email_uid: {email_uid}, creating new record.")
                    if not submission_time:
                        submission_time = datetime.now()
                    
                    submission = Submission(
                        email_uid=email_uid,
                        email_subject=email_subject or f"Manual Submission - {assignment_name}",
                        sender_email=sender_email or email or "Unknown",
                        sender_name=name or "Unknown",
                        submission_time=submission_time,
                        status=status,
                        student_id=student.id,
                        assignment_id=assignment.id
                    )
                    self.session.add(submission)
                else:
                    print(f"Error: Submission not found (id={submission_id}) and no email_uid provided to create it.")
                    return False

            # 5. Update submission fields (for existing or just created)
            submission.student_id = student.id
            submission.assignment_id = assignment.id
            submission.status = status

            # 5.5 Update new processing_status if it's a new status value
            from database.models import ProcessingStatus
            new_processing_statuses = [s.value for s in ProcessingStatus]
            if status in new_processing_statuses:
                submission.processing_status = status
                submission.processing_status_updated_at = datetime.now()

            # 6. Recalculate late status
            if assignment.deadline and submission.submission_time:
                submission.is_late = submission.submission_time > assignment.deadline
            else:
                submission.is_late = False

            # 7. Update compatibility fields based on status
            if status == 'completed':
                submission.is_replied = True
                submission.is_downloaded = True
            elif status == 'unreplied':
                submission.is_downloaded = True

            self.session.commit()

            # 发送数据变更通知
            notifier = _get_notifier()
            if notifier:
                notifier.notify_record_updated(
                    uid=submission.email_uid,
                    submission_id=submission.id,
                    changes={
                        'student_id': student_id,
                        'name': name,
                        'assignment_name': assignment_name,
                        'status': status
                    }
                )

            return submission.id
        except Exception as e:
            self.session.rollback()
            print(f"Error in update_submission_full: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_submission_by_id(self, submission_id: int) -> Optional[Submission]:
        """Get submission by its database ID"""
        return self.session.query(Submission).filter_by(id=submission_id).first()

    @_queued_write
    def update_submission_field(self, submission_id: Optional[int], field_id: str, new_value: Any, email_uid: Optional[str] = None, message_id: Optional[str] = None) -> bool:
        """Update a single field of a submission. No longer creates records automatically to prevent data corruption."""
        try:
            submission = None
            if submission_id:
                submission = self.session.query(Submission).filter_by(id=submission_id).first()
            
            if not submission and message_id:
                submission = self.session.query(Submission).filter_by(message_id=message_id).first()

            if not submission and email_uid:
                submission = self.session.query(Submission).filter_by(email_uid=email_uid).first()

            if not submission:
                print(f"Error: Submission not found for update (id={submission_id}, uid={email_uid}, msgid={message_id})")
                return False

            if field_id == 'student_id':
                current_name = submission.student.name if submission.student else "Unknown"
                student = self.create_student(new_value, current_name)
                submission.student_id = student.id
            elif field_id == 'name':
                if submission.student:
                    submission.student.name = new_value
                    self.session.add(submission.student)
                else:
                    student = self.create_student("Unknown", new_value)
                    submission.student_id = student.id
            elif field_id == 'assignment_name':
                assignment = self.create_assignment(new_value)
                submission.assignment_id = assignment.id
                if assignment.deadline and submission.submission_time:
                    submission.is_late = submission.submission_time > assignment.deadline
                else:
                    submission.is_late = False
            elif field_id == 'status':
                submission.status = new_value
                # 更新新的processing_status字段（如果是新状态值）
                from database.models import ProcessingStatus
                new_processing_statuses = [s.value for s in ProcessingStatus]
                if new_value in new_processing_statuses:
                    submission.processing_status = new_value
                    submission.processing_status_updated_at = datetime.now()

                if new_value == 'completed':
                    submission.is_replied = True
                    submission.is_downloaded = True
                elif new_value == 'unreplied':
                    submission.is_downloaded = True
                elif new_value == 'pending':
                    submission.is_downloaded = False
                    submission.is_replied = False
            elif field_id == 'message_id':
                submission.message_id = new_value
            elif field_id == 'email_uid':
                submission.email_uid = new_value
            elif field_id == 'body':
                submission.body = new_value

            self.session.commit()

            # 发送数据变更通知
            notifier = _get_notifier()
            if notifier and submission:
                notifier.notify_record_updated(
                    uid=submission.email_uid,
                    submission_id=submission.id,
                    changes={field_id: new_value}
                )

            return True
        except Exception as e:
            self.session.rollback()
            print(f"Error updating submission field: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_submission(self, student_id: str, assignment_name: str) -> Optional[Submission]:
        """Get submission by student_id and assignment_name"""
        return self.session.query(Submission).join(Student).join(Assignment).filter(
            Student.student_id == student_id,
            Assignment.name == assignment_name
        ).first()

    def get_all_submissions(self) -> List[Dict]:
        """Get all submissions with status info"""
        submissions = self.session.query(Submission).all()
        result = []
        for s in submissions:
            result.append({
                'id': s.id,
                'student_id': s.student.student_id if s.student else "Unknown",
                'name': s.student.name if s.student else "Unknown",
                'email': s.student.email if s.student else s.sender_email,
                'assignment_name': s.assignment.name if s.assignment else "Unknown",
                'email_uid': s.email_uid,
                'message_id': s.message_id,
                'submission_time': s.submission_time,
                'is_late': s.is_late,
                'is_downloaded': s.is_downloaded,
                'is_replied': s.is_replied,
                'local_path': s.local_path,
                'status': s.status,
                'error_message': s.error_message,
                'body': s.body
            })
        return result

    def get_submission_by_uid(self, email_uid: str) -> Optional[Submission]:
        """Get submission by email UID"""
        return self.session.query(Submission).filter_by(email_uid=email_uid).first()

    def get_submission_by_message_id(self, message_id: str) -> Optional[Submission]:
        """Get submission by Message-ID"""
        if not message_id:
            return None
        return self.session.query(Submission).filter_by(message_id=message_id).first()

    def get_submissions_bulk(self, uids: List[str] = None, message_ids: List[str] = None) -> Dict[str, Submission]:
        """
        批量查询提交记录 - 性能优化版本

        Args:
            uids: 邮件UID列表
            message_ids: Message-ID列表

        Returns:
            字典 {uid/message_id: Submission}

        注意: 此方法只读，不使用写队列装饰器
        """
        result = {}

        if not uids and not message_ids:
            return result

        try:
            # 构建查询条件
            conditions = []
            lookup_keys = []  # 用于构建返回字典的键

            if uids:
                conditions.append(Submission.email_uid.in_(uids))
                lookup_keys.extend([(u, 'uid') for u in uids])

            if message_ids:
                # 过滤掉空的message_id
                valid_message_ids = [m for m in message_ids if m]
                if valid_message_ids:
                    conditions.append(Submission.message_id.in_(valid_message_ids))
                    lookup_keys.extend([(m, 'msgid') for m in valid_message_ids])

            if not conditions:
                return result

            # 使用OR条件组合查询，一次获取所有记录
            from sqlalchemy import or_
            query = self.session.query(Submission).filter(or_(*conditions))

            # 预加载关联数据以避免N+1查询
            from sqlalchemy.orm import joinedload
            query = query.options(
                joinedload(Submission.student),
                joinedload(Submission.assignment)
            )

            submissions = query.all()

            # 构建返回字典，同时支持uid和message_id作为键
            for sub in submissions:
                if sub.email_uid:
                    result[sub.email_uid] = sub
                if sub.message_id:
                    result[sub.message_id] = sub

            return result

        except Exception as e:
            print(f"Error in bulk query: {e}")
            import traceback
            traceback.print_exc()
            return result

    def get_submissions_dict(self, uids: List[str]) -> Dict[str, Dict]:
        """
        批量查询并返回字典格式的提交信息 - 用于UI显示

        Args:
            uids: 邮件UID列表

        Returns:
            字典 {uid: submission_dict}
        """
        submissions = self.get_submissions_bulk(uids=uids)
        result = {}

        for uid, sub in submissions.items():
            result[uid] = {
                'id': sub.id,
                'student_id': sub.student.student_id if sub.student else "Unknown",
                'name': sub.student.name if sub.student else "Unknown",
                'email': sub.student.email if sub.student else sub.sender_email,
                'assignment_name': sub.assignment.name if sub.assignment else "Unknown",
                'email_uid': sub.email_uid,
                'message_id': sub.message_id,
                'submission_time': sub.submission_time,
                'is_late': sub.is_late,
                'is_downloaded': sub.is_downloaded,
                'is_replied': sub.is_replied,
                'local_path': sub.local_path,
                'status': getattr(sub, 'status', 'pending'),
                'error_message': getattr(sub, 'error_message', None),
                'body': getattr(sub, 'body', None)
            }

        return result

    @_queued_write
    def update_submission_local_path(self, submission_id: int, local_path: str) -> bool:
        """Update submission local path"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                submission.local_path = local_path
                submission.is_downloaded = True
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error updating local path: {e}")
            return False

    @_queued_write
    def update_submission_uid(self, submission_id: int, new_uid: str) -> bool:
        """Update submission email UID (needed if email moved folders)"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                submission.email_uid = new_uid
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error updating submission UID: {e}")
            return False

    @_queued_write
    def mark_replied(self, submission_id: int) -> bool:
        """Mark submission as replied"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                submission.is_replied = True
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error marking replied: {e}")
            return False

    @_queued_write
    def mark_bulk_replied(self, submission_ids: List[int]) -> int:
        """
        批量标记为已回复 - 性能优化版本

        Args:
            submission_ids: 提交记录ID列表

        Returns:
            成功更新的记录数
        """
        try:
            count = self.session.query(Submission).filter(
                Submission.id.in_(submission_ids)
            ).update({
                'is_replied': True,
                'status': 'completed'
            }, synchronize_session=False)

            self.session.commit()

            # 发送数据变更通知
            notifier = _get_notifier()
            if notifier and count > 0:
                notifier.notify_batch_updated(
                    submission_ids=submission_ids,
                    changes={'status': 'completed', 'is_replied': True}
                )

            return count
        except Exception as e:
            self.session.rollback()
            print(f"Error in bulk mark replied: {e}")
            return 0

    @_queued_write
    def update_submissions_status_bulk(self, submission_ids: List[int], status: str) -> int:
        """
        批量更新提交状态 - 性能优化版本

        Args:
            submission_ids: 提交记录ID列表
            status: 新状态

        Returns:
            成功更新的记录数
        """
        try:
            # 根据状态设置相应的字段
            update_data = {'status': status}

            if status == 'completed':
                update_data['is_replied'] = True
                update_data['is_downloaded'] = True
            elif status == 'unreplied':
                update_data['is_downloaded'] = True
            elif status == 'pending':
                update_data['is_downloaded'] = False
                update_data['is_replied'] = False

            count = self.session.query(Submission).filter(
                Submission.id.in_(submission_ids)
            ).update(update_data, synchronize_session=False)

            self.session.commit()

            # 发送数据变更通知
            notifier = _get_notifier()
            if notifier and count > 0:
                notifier.notify_batch_updated(
                    submission_ids=submission_ids,
                    changes={'status': status}
                )

            return count
        except Exception as e:
            self.session.rollback()
            print(f"Error in bulk status update: {e}")
            return 0

    @_queued_write
    def delete_submissions_bulk(self, submission_ids: List[int]) -> int:
        """
        批量删除提交记录 - 性能优化版本

        Args:
            submission_ids: 提交记录ID列表

        Returns:
            成功删除的记录数
        """
        try:
            count = self.session.query(Submission).filter(
                Submission.id.in_(submission_ids)
            ).delete(synchronize_session=False)

            self.session.commit()

            # 发送数据变更通知
            notifier = _get_notifier()
            if notifier and count > 0:
                notifier.notify_batch_deleted(submission_ids=submission_ids)

            return count
        except Exception as e:
            self.session.rollback()
            print(f"Error in bulk delete: {e}")
            return 0

    @_queued_write
    def mark_late_submissions(self, assignment_name: str) -> int:
        """Mark all submissions as late if past deadline"""
        try:
            assignment = self.get_assignment(assignment_name)
            if not assignment or not assignment.deadline:
                return 0

            count = self.session.query(Submission).filter(
                Submission.assignment_id == assignment.id,
                Submission.submission_time > assignment.deadline,
                Submission.is_late == False
            ).update({'is_late': True})

            self.session.commit()
            return count
        except Exception as e:
            self.session.rollback()
            print(f"Error marking late submissions: {e}")
            return 0

    @_queued_write
    def delete_submission(self, submission_id: int) -> bool:
        """Delete submission by ID"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                uid = submission.email_uid
                self.session.delete(submission)
                self.session.commit()

                # 发送数据变更通知
                notifier = _get_notifier()
                if notifier:
                    notifier.notify_record_deleted(
                        submission_id=submission_id,
                        uid=uid
                    )

                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error deleting submission: {e}")
            return False

    @_queued_write
    def add_attachment(self, submission_id: int, filename: str, file_size: int, local_path: str) -> Optional[Attachment]:
        """Add attachment to submission"""
        try:
            attachment = Attachment(
                submission_id=submission_id,
                filename=filename,
                file_size=file_size,
                local_path=local_path
            )
            self.session.add(attachment)
            self.session.commit()
            self.session.refresh(attachment)
            return attachment
        except Exception as e:
            self.session.rollback()
            print(f"Error adding attachment: {e}")
            return None

    def get_attachments(self, submission_id: int) -> List[Attachment]:
        """Get all attachments for a submission"""
        return self.session.query(Attachment).filter_by(submission_id=submission_id).all()

    @_queued_write
    def log_email_action(self, email_uid: str, action: str, folder: str, details: str = None, error_message: str = None):
        """Log email action"""
        try:
            log = EmailLog(
                email_uid=email_uid,
                action=action,
                folder=folder,
                details=details,
                error_message=error_message
            )
            self.session.add(log)
            self.session.commit()
        except Exception as e:
            print(f"Error logging email action: {e}")

    def get_all_students(self) -> List[Student]:
        """Get all students"""
        return self.session.query(Student).all()

    def get_all_assignments(self) -> List[Assignment]:
        """Get all assignments"""
        return self.session.query(Assignment).all()

    def get_all_unique_students(self) -> List[str]:
        """
        获取所有唯一学生的格式化列表

        Returns:
            格式为 "学号 - 姓名" 的字符串列表
        """
        students = self.session.query(Student).order_by(Student.student_id).all()
        return [f"{s.student_id} - {s.name}" for s in students]

    def get_all_unique_assignments(self) -> List[str]:
        """
        获取所有唯一作业名称的列表

        Returns:
            作业名称字符串列表
        """
        assignments = self.session.query(Assignment).order_by(Assignment.name).all()
        return [a.name for a in assignments]

    def filter_submissions(
        self,
        student_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        is_late: Optional[bool] = None,
        is_replied: Optional[bool] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """Filter submissions by various criteria"""
        query = self.session.query(Submission)

        if student_id:
            query = query.join(Student).filter(Student.student_id == student_id)

        if assignment_name:
            query = query.join(Assignment).filter(Assignment.name == assignment_name)

        if is_late is not None:
            query = query.filter(Submission.is_late == is_late)

        if is_replied is not None:
            query = query.filter(Submission.is_replied == is_replied)
            
        if status:
            query = query.filter(Submission.status == status)

        submissions = query.all()
        result = []
        for s in submissions:
            result.append({
                'id': s.id,
                'student_id': s.student.student_id if s.student else "Unknown",
                'name': s.student.name if s.student else "Unknown",
                'email': s.student.email if s.student else s.sender_email,
                'assignment_name': s.assignment.name if s.assignment else "Unknown",
                'email_uid': s.email_uid,
                'message_id': s.message_id,
                'submission_time': s.submission_time,
                'is_late': s.is_late,
                'is_downloaded': s.is_downloaded,
                'is_replied': s.is_replied,
                'local_path': s.local_path,
                'status': s.status,
                'error_message': s.error_message,
                'body': s.body
            })
        return result

    def filter_submissions_paginated(
        self,
        student_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        status: Optional[str] = None,
        is_late: Optional[bool] = None,
        page: int = 1,
        per_page: int = 100
    ) -> Dict[str, Any]:
        """
        Filter submissions with pagination - optimized for large datasets

        Args:
            student_id: Filter by student ID (or "全部学生" for all)
            assignment_name: Filter by assignment name (or "全部作业" for all)
            status: Filter by status text (e.g., "未处理", "已完成", "正常", "逾期")
            is_late: Filter by late status
            page: Page number (1-indexed)
            per_page: Records per page

        Returns:
            {
                'submissions': list of submission dicts,
                'total': int,
                'page': int,
                'per_page': int,
                'total_pages': int
            }
        """
        query = self.session.query(Submission).outerjoin(Student).outerjoin(Assignment)

        # Apply student filter
        if student_id and student_id != '全部学生':
            query = query.filter(Student.student_id == student_id)

        # Apply assignment filter
        if assignment_name and assignment_name != '全部作业':
            query = query.filter(Assignment.name == assignment_name)

        # Apply status filter
        if status:
            if status == '正常':
                query = query.filter(Submission.is_late == False)
            elif status == '逾期':
                query = query.filter(Submission.is_late == True)
            else:
                # Map status text to code
                status_code = self._map_status_text_to_code(status)
                if status_code:
                    query = query.filter(Submission.status == status_code)

        # Apply is_late filter (if specified separately)
        if is_late is not None:
            query = query.filter(Submission.is_late == is_late)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        submissions = query.order_by(
            Submission.submission_time.desc(),
            Submission.id.desc()
        ).offset(offset).limit(per_page).all()

        # Convert to dict format with all required fields
        result = []
        for s in submissions:
            result.append({
                'id': s.id,
                'student_id': s.student.student_id if s.student else "Unknown",
                'name': s.student.name if s.student else "Unknown",
                'email': s.student.email if s.student else s.sender_email,
                'assignment_name': s.assignment.name if s.assignment else "Unknown",
                'email_uid': s.email_uid,
                'message_id': s.message_id,
                'submission_time': s.submission_time,
                'is_late': s.is_late,
                'is_downloaded': s.is_downloaded,
                'is_replied': s.is_replied,
                'local_path': s.local_path,
                'status': s.status,
                'error_message': s.error_message,
                'body': s.body,
                # Include relationship fields for grouping
                'parent_id': s.parent_id,
                'relation_type': s.relation_type if s.relation_type else None,
                'is_primary': s.is_primary,
                'version': s.version,
                'is_latest': s.is_latest
            })

        total_pages = (total + per_page - 1) // per_page if total > 0 else 1

        return {
            'submissions': result,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        }

    def _map_status_text_to_code(self, status_text: str) -> Optional[str]:
        """Map UI status text to database status code"""
        status_map = {
            '未处理': 'pending',
            '识别异常': 'ai_error',
            '下载失败': 'download_failed',
            '未回复': 'unreplied',
            '已完成': 'completed',
            '已忽略': 'ignored'
        }
        return status_map.get(status_text)

    def get_all_submission_versions(
        self,
        student_id: str,
        assignment_name: str
    ) -> List[Submission]:
        """Get all versions of a submission (old and new)"""
        return self.session.query(Submission).join(Student).join(Assignment).filter(
            Student.student_id == student_id,
            Assignment.name == assignment_name
        ).order_by(Submission.version.desc()).all()

    def get_latest_submission(
        self,
        student_id: str,
        assignment_name: str
    ) -> Optional[Submission]:
        """Get only the latest version of a submission"""
        return self.session.query(Submission).join(Student).join(Assignment).filter(
            Student.student_id == student_id,
            Assignment.name == assignment_name,
            Submission.is_latest == True
        ).first()

    @_queued_write
    def mark_old_versions_as_not_latest(
        self,
        student_id: str,
        assignment_name: str,
        exclude_version: int
    ) -> int:
        """Mark all versions except the specified one as not latest"""
        try:
            # First find the student and assignment IDs
            student = self.session.query(Student).filter_by(student_id=student_id).first()
            assignment = self.session.query(Assignment).filter_by(name=assignment_name).first()

            if not student or not assignment:
                return 0

            # Update without JOIN - SQLAlchemy requires this
            count = self.session.query(Submission).filter(
                Submission.student_id == student.id,
                Submission.assignment_id == assignment.id,
                Submission.version != exclude_version
            ).update({'is_latest': False}, synchronize_session=False)

            self.session.commit()
            return count
        except Exception as e:
            self.session.rollback()
            print(f"Error marking old versions: {e}")
            return 0

    def get_connection(self):
        """Get raw sqlite3 connection for direct SQL operations"""
        from config.settings import settings
        return sqlite3.connect(str(settings.DATABASE_PATH))

    @_queued_write
    def save_email_body(self, submission_id: int, body_data: Dict) -> bool:
        """Save email body data to submission

        Args:
            submission_id: Submission ID
            body_data: Dict with keys: plain_text, html_markdown, format

        Returns:
            True on success, False on exception

        Raises:
            ValueError: If body_data missing required keys
        """
        # Validate required keys
        required_keys = {'plain_text', 'html_markdown', 'format'}
        if not all(key in body_data for key in required_keys):
            raise ValueError(f"body_data must contain keys: {required_keys}")

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Serialize body_data to JSON
            json_data = json.dumps(body_data, ensure_ascii=False)

            cursor.execute(
                "UPDATE submissions SET body = ? WHERE id = ?",
                (json_data, submission_id)
            )

            conn.commit()
            return True

        except Exception as e:
            print(f"Error saving email body: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_email_body(self, submission_id: int) -> Optional[Dict]:
        """Get email body data from submission

        Args:
            submission_id: Submission ID

        Returns:
            Dict with keys: plain_text, html_markdown, format
            None if not found or on exception
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT body FROM submissions WHERE id = ?",
                (submission_id,)
            )

            result = cursor.fetchone()

            if result and result[0]:
                return json.loads(result[0])
            return None

        except Exception as e:
            print(f"Error getting email body: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def close(self):
        """Close database session"""
        self.session.close()

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

    @_queued_write
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

# Global database operations instance
db = DatabaseOperations()
