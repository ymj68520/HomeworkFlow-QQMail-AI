"""异步数据库操作类 - 专注于去重系统需要的方法"""

from typing import Optional, Dict, List, Any
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from database.models import (
    get_async_session, Base, Student, Assignment, Submission,
    AIExtractionCache, SubmissionGroup
)
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class AsyncDatabaseOperations:
    """异步数据库操作类"""

    def __init__(self):
        # 创建后台任务队列用于缓存写入
        self._cache_write_queue = asyncio.Queue()
        self._cache_writer_task = None
        self._initialized = False

    async def get_submission_by_uid(self, email_uid: str) -> Optional[Submission]:
        """通过email_uid获取提交记录"""
        async with get_async_session()() as session:
            result = await session.execute(
                select(Submission).filter_by(email_uid=email_uid)
            )
            return result.scalar_one_or_none()

    async def get_latest_submission(
        self,
        student_id: str,
        assignment_name: str
    ) -> Optional[Submission]:
        """获取学生某作业的最新版本"""
        async with get_async_session()() as session:
            # 先获取student和assignment
            student_result = await session.execute(
                select(Student).filter_by(student_id=student_id)
            )
            student = student_result.scalar_one_or_none()

            assignment_result = await session.execute(
                select(Assignment).filter_by(name=assignment_name)
            )
            assignment = assignment_result.scalar_one_or_none()

            if not student or not assignment:
                return None

            # 获取最新版本
            result = await session.execute(
                select(Submission)
                .filter_by(
                    student_id=student.id,
                    assignment_id=assignment.id,
                    is_latest=True
                )
            )
            return result.scalar_one_or_none()

    async def mark_old_versions_as_not_latest(
        self,
        student_id: str,
        assignment_name: str,
        exclude_version: int
    ) -> int:
        """标记旧版本为非最新"""
        async with get_async_session()() as session:
            # 获取student和assignment
            student_result = await session.execute(
                select(Student).filter_by(student_id=student_id)
            )
            student = student_result.scalar_one_or_none()

            assignment_result = await session.execute(
                select(Assignment).filter_by(name=assignment_name)
            )
            assignment = assignment_result.scalar_one_or_none()

            if not student or not assignment:
                return 0

            # 更新旧版本
            result = await session.execute(
                update(Submission)
                .filter_by(
                    student_id=student.id,
                    assignment_id=assignment.id
                )
                .filter(Submission.version != exclude_version)
                .values(is_latest=False)
            )
            await session.commit()
            return result.rowcount

    async def create_submission(
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
        """创建或更新提交记录"""
        async with get_async_session()() as session:
            try:
                # 获取或创建学生
                student_db_id = None
                if student_id and student_id != 'Unknown':
                    student_result = await session.execute(
                        select(Student).filter_by(student_id=student_id)
                    )
                    student = student_result.scalar_one_or_none()
                    if not student:
                        student = Student(
                            student_id=student_id,
                            name=sender_name or "Unknown",
                            email=sender_email
                        )
                        session.add(student)
                        await session.flush()
                        student_db_id = student.id
                    else:
                        student_db_id = student.id

                # 获取或创建作业
                assignment_db_id = None
                assignment_obj = None
                if assignment_name and assignment_name != 'Unknown':
                    assignment_result = await session.execute(
                        select(Assignment).filter_by(name=assignment_name)
                    )
                    assignment = assignment_result.scalar_one_or_none()
                    if not assignment:
                        assignment = Assignment(name=assignment_name)
                        session.add(assignment)
                        await session.flush()
                        assignment_db_id = assignment.id
                    else:
                        assignment_db_id = assignment.id
                        assignment_obj = assignment

                # 检查是否已存在
                existing = None
                if message_id:
                    result = await session.execute(
                        select(Submission).filter_by(message_id=message_id)
                    )
                    existing = result.scalar_one_or_none()

                if not existing:
                    result = await session.execute(
                        select(Submission).filter_by(email_uid=email_uid)
                    )
                    existing = result.scalar_one_or_none()

                # 计算是否逾期
                is_late = False
                if assignment_obj and assignment_obj.deadline:
                    is_late = submission_time > assignment_obj.deadline

                if existing:
                    # 更新现有记录
                    if student_db_id:
                        existing.student_id = student_db_id
                    if assignment_db_id:
                        existing.assignment_id = assignment_db_id
                    if message_id:
                        existing.message_id = message_id
                    existing.email_uid = email_uid
                    existing.email_subject = email_subject
                    existing.submission_time = submission_time
                    if local_path:
                        existing.local_path = local_path
                    if body:
                        existing.body = body
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
                    session.add(submission)

                await session.commit()
                await session.refresh(submission)
                return submission

            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating submission: {e}")
                return None

    async def get_ai_cache(self, email_uid: str) -> Optional[Dict]:
        """获取AI提取缓存"""
        async with get_async_session()() as session:
            result = await session.execute(
                select(AIExtractionCache).filter_by(email_uid=email_uid)
            )
            cache_entry = result.scalar_one_or_none()

            if not cache_entry:
                return None

            return {
                'student_id': cache_entry.student_id,
                'name': cache_entry.name,
                'assignment_name': cache_entry.assignment_name,
                'confidence': cache_entry.confidence,
                'is_fallback': cache_entry.is_fallback
            }

    async def initialize(self):
        """初始化后台缓存写入器"""
        if self._initialized:
            return

        self._cache_writer_task = asyncio.create_task(self._cache_writer_loop())
        self._initialized = True
        logger.info("Async database operations initialized with background cache writer")

    async def close(self):
        """关闭后台任务"""
        if self._cache_writer_task:
            # 停止后台任务
            await self._cache_write_queue.put(None)  # 发送停止信号
            try:
                await asyncio.wait_for(self._cache_writer_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # 超时或被取消，尝试优雅停止
                logger.warning("Cache writer task did not stop gracefully, cancelling")
                # 取消任务
                if not self._cache_writer_task.done():
                    self._cache_writer_task.cancel()
                    try:
                        await self._cache_writer_task
                    except asyncio.CancelledError:
                        pass  # Task was cancelled, expected
            self._cache_writer_task = None
        self._initialized = False

    async def _cache_writer_loop(self):
        """后台缓存写入循环 - 在独立任务中运行"""
        logger.info("Background cache writer started")

        while True:
            cache_data = await self._cache_write_queue.get()

            # None 是停止信号
            if cache_data is None:
                break

            try:
                email_uid, result, is_fallback = cache_data

                # 使用单独的session避免与主流程冲突
                async with get_async_session()() as session:
                    cache_entry = await session.execute(
                        select(AIExtractionCache).filter_by(email_uid=email_uid)
                    )
                    cache_entry = cache_entry.scalar_one_or_none()

                    if cache_entry:
                        # 更新
                        cache_entry.student_id = result.get('student_id')
                        cache_entry.name = result.get('name')
                        cache_entry.assignment_name = result.get('assignment_name')
                        cache_entry.confidence = result.get('confidence')
                        cache_entry.is_fallback = is_fallback
                    else:
                        # 创建
                        cache_entry = AIExtractionCache(
                            email_uid=email_uid,
                            student_id=result.get('student_id'),
                            name=result.get('name'),
                            assignment_name=result.get('assignment_name'),
                            confidence=result.get('confidence'),
                            is_fallback=is_fallback
                        )
                        session.add(cache_entry)

                    await session.commit()
                    logger.debug(f"Cache saved for {email_uid}")

            except Exception as e:
                # 后台任务中的错误只记录，不影响主流程
                logger.warning(f"Background cache save failed for {cache_data[0] if cache_data else 'unknown'}: {e}")

        logger.info("Background cache writer stopped")

    async def save_ai_cache(
        self,
        email_uid: str,
        result: Dict,
        is_fallback: bool = False
    ):
        """保存AI提取结果到缓存 - 非阻塞后台写入

        将缓存写入放入后台队列，立即返回，不阻塞主流程
        """
        if not self._initialized:
            # 如果还没有初始化，先初始化后台任务
            await self.initialize()

        try:
            # 非阻塞地放入队列，如果队列满了就丢弃这次缓存
            self._cache_write_queue.put_nowait((email_uid, result, is_fallback))
        except asyncio.QueueFull:
            # 队列列满了，直接丢弃，不阻塞
            logger.debug("Cache write queue full, dropping cache save")
        except Exception as e:
            logger.warning(f"Failed to queue cache save: {e}")

        # 立即返回，不等待保存完成

    async def update_submission(
        self,
        submission_id: int,
        student_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        email_uid: Optional[str] = None,
        message_id: Optional[str] = None,
        email_subject: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_name: Optional[str] = None,
        submission_time: Optional[datetime] = None,
        body: Optional[str] = None,
        version: Optional[int] = None,
        is_latest: Optional[bool] = None,
        is_primary: Optional[bool] = None,
        parent_id: Optional[int] = None,
        relation_type: Optional[str] = None
    ) -> bool:
        """
        更新提交记录 - 用于版本合并

        Args:
            submission_id: 记录ID
            student_id: 学号
            assignment_name: 作业名称
            email_uid: 邮件UID
            message_id: 消息ID
            email_subject: 邮件主题
            sender_email: 发件人邮箱
            sender_name: 发件人姓名
            submission_time: 提交时间
            body: 邮件正文
            version: 版本号
            is_latest: 是否为最新版本
            is_primary: 是否为主记录
            parent_id: 父记录ID
            relation_type: 关联类型

        Returns:
            是否成功
        """
        async with get_async_session()() as session:
            try:
                # 获取记录
                result = await session.execute(
                    select(Submission).filter_by(id=submission_id)
                )
                submission = result.scalar_one_or_none()

                if not submission:
                    logger.error(f"Submission {submission_id} not found for update")
                    return False

                # 获取或创建学生
                if student_id:
                    student_result = await session.execute(
                        select(Student).filter_by(student_id=student_id)
                    )
                    student = student_result.scalar_one_or_none()
                    if student:
                        submission.student_id = student.id

                # 获取或创建作业
                if assignment_name:
                    assignment_result = await session.execute(
                        select(Assignment).filter_by(name=assignment_name)
                    )
                    assignment = assignment_result.scalar_one_or_none()
                    if assignment:
                        submission.assignment_id = assignment.id

                # 更新字段
                if email_uid is not None:
                    submission.email_uid = email_uid
                if message_id is not None:
                    submission.message_id = message_id
                if email_subject is not None:
                    submission.email_subject = email_subject
                if sender_email is not None:
                    submission.sender_email = sender_email
                if sender_name is not None:
                    submission.sender_name = sender_name
                if submission_time is not None:
                    submission.submission_time = submission_time
                if body is not None:
                    submission.body = body
                if version is not None:
                    submission.version = version
                if is_latest is not None:
                    submission.is_latest = is_latest
                if is_primary is not None:
                    submission.is_primary = is_primary
                if parent_id is not None:
                    submission.parent_id = parent_id
                if relation_type is not None:
                    submission.relation_type = relation_type

                submission.updated_at = datetime.now()

                await session.commit()
                logger.info(f"Updated submission {submission_id}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating submission {submission_id}: {e}")
                import traceback
                traceback.print_exc()
                return False

    async def mark_submission_not_latest(self, submission_id: int) -> bool:
        """
        标记指定记录为非最新版本

        Args:
            submission_id: 记录ID

        Returns:
            是否成功
        """
        async with get_async_session()() as session:
            try:
                result = await session.execute(
                    update(Submission)
                    .filter_by(id=submission_id)
                    .values(is_latest=False)
                )
                await session.commit()
                logger.info(f"Marked submission {submission_id} as not latest")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Error marking submission {submission_id} as not latest: {e}")
                return False

    async def create_submission_group(
        self,
        email_uid: str,
        message_id: Optional[str] = None,
        email_subject: Optional[str] = None,
        sender_email: Optional[str] = None,
        sender_name: Optional[str] = None,
        submission_time: Optional[datetime] = None,
        processing_mode: str = 'multi',
        detection_method: Optional[str] = None,
        ai_confidence: Optional[float] = None,
        total_assignments: int = 0,
        total_attachments: int = 0,
        status: str = 'processing'
    ) -> Optional[SubmissionGroup]:
        """Create a new submission group"""
        async with get_async_session()() as session:
            try:
                group = SubmissionGroup(
                    email_uid=email_uid,
                    message_id=message_id,
                    email_subject=email_subject,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    submission_time=submission_time or datetime.now(),
                    processing_mode=processing_mode,
                    detection_method=detection_method,
                    ai_confidence=ai_confidence,
                    total_assignments=total_assignments,
                    total_attachments=total_attachments,
                    status=status
                )
                session.add(group)
                await session.commit()
                await session.refresh(group)
                return group
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating submission group: {e}")
                return None

    async def get_submission_group_by_email_uid(self, email_uid: str) -> Optional[SubmissionGroup]:
        """Get submission group by email UID"""
        async with get_async_session()() as session:
            result = await session.execute(
                select(SubmissionGroup).where(SubmissionGroup.email_uid == email_uid)
            )
            return result.scalar_one_or_none()

    async def update_group_status(
        self,
        group_id: int,
        status: str,
        total_assignments: Optional[int] = None,
        error_message: Optional[str] = None,
        error_details: Optional[str] = None
    ) -> bool:
        """Update submission group status"""
        async with get_async_session()() as session:
            try:
                result = await session.execute(
                    select(SubmissionGroup).where(SubmissionGroup.id == group_id)
                )
                group = result.scalar_one_or_none()
                if not group:
                    return False

                group.status = status
                if total_assignments is not None:
                    group.total_assignments = total_assignments
                if error_message is not None:
                    group.error_message = error_message
                if error_details is not None:
                    group.error_details = error_details

                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating group status: {e}")
                return False

    async def get_group_with_submissions(self, group_id: int) -> Optional[SubmissionGroup]:
        """Get submission group with all related submissions"""
        async with get_async_session()() as session:
            result = await session.execute(
                select(SubmissionGroup)
                .options(selectinload(SubmissionGroup.submissions))
                .where(SubmissionGroup.id == group_id)
            )
            return result.scalar_one_or_none()

    async def get_multi_assignment_cache(self, cache_key: str) -> Optional[Dict]:
        """Get multi-assignment detection result from cache"""
        async with get_async_session()() as session:
            result = await session.execute(
                select(AIExtractionCache)
                .where(AIExtractionCache.email_uid == cache_key)
            )
            cache_entry = result.scalar_one_or_none()
            if cache_entry:
                return {
                    'is_multi_assignment': True,
                    'is_complete': True,
                    'cached': True
                }
            return None

    async def save_multi_assignment_cache(self, cache_key: str, result: Dict) -> bool:
        """Save multi-assignment detection result to cache"""
        async with get_async_session()() as session:
            try:
                cache_entry = await session.execute(
                    select(AIExtractionCache)
                    .where(AIExtractionCache.email_uid == cache_key)
                )
                cache_entry = cache_entry.scalar_one_or_none()

                if cache_entry:
                    # Update existing entry
                    cache_entry.student_id = result.get('student_id')
                    cache_entry.name = result.get('name')
                    cache_entry.assignment_name = result.get('detection_method')
                    cache_entry.confidence = result.get('overall_confidence', 0.0)
                    cache_entry.is_fallback = False
                else:
                    # Create new entry
                    cache_entry = AIExtractionCache(
                        email_uid=cache_key,
                        student_id=result.get('student_id'),
                        name=result.get('name'),
                        assignment_name=result.get('detection_method'),
                        confidence=result.get('overall_confidence', 0.0),
                        is_fallback=False
                    )
                    session.add(cache_entry)

                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"Error saving multi-assignment cache: {e}")
                return False


# 全局实例
async_db = AsyncDatabaseOperations()
