"""异步数据库操作类 - 专注于去重系统需要的方法"""

from typing import Optional, Dict, List, Any
from sqlalchemy import select, update
from database.models import (
    get_async_session, Base, Student, Assignment, Submission,
    AIExtractionCache
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
                print(f"Error creating submission: {e}")
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


# 全局实例
async_db = AsyncDatabaseOperations()
