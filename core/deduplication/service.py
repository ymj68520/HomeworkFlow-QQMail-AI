"""统一去重服务"""

from typing import Optional, Dict, Any
from database.async_operations import AsyncDatabaseOperations
from core.deduplication.models import DeduplicationResult
from core.deduplication.email_deduplicator import EmailDeduplicator
from core.deduplication.submission_deduplicator import SubmissionDeduplicator
from core.deduplication.version_manager import VersionManager
from core.deduplication.cache_manager import CacheManager


class DeduplicationService:
    """统一去重服务 - 唯一入口

    职责：
    - 协调各子组件完成去重检查
    - 管理返回值标准化
    - 提供统一的检查接口
    """

    def __init__(self, db: AsyncDatabaseOperations):
        self.db = db
        self.email_deduplicator = EmailDeduplicator(db)
        self.submission_deduplicator = SubmissionDeduplicator(db)
        self.version_manager = VersionManager(db)
        self.cache_manager = CacheManager(db)

    async def check_email(self, email_uid: str) -> DeduplicationResult:
        """检查邮件是否重复

        Args:
            email_uid: 邮件UID

        Returns:
            DeduplicationResult with duplicate_type='email' if duplicate
        """
        is_duplicate = await self.email_deduplicator.check(email_uid)

        if is_duplicate:
            existing = await self.email_deduplicator.get_existing(email_uid)
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type='email',
                action='skip',
                submission=existing,
                message=f"Email {email_uid} already processed"
            )

        return DeduplicationResult(is_duplicate=False, action='new')

    async def check_submission(
        self,
        student_id: str,
        assignment_name: str
    ) -> DeduplicationResult:
        """检查提交是否重复

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            DeduplicationResult with duplicate_type='submission' if duplicate
        """
        is_duplicate = await self.submission_deduplicator.check(
            student_id, assignment_name
        )

        if is_duplicate:
            latest = await self.submission_deduplicator.get_latest(
                student_id, assignment_name
            )
            next_version = await self.version_manager.get_next_version(
                student_id, assignment_name
            )

            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type='submission',
                action='update_version',
                submission=latest,
                version=next_version,
                message=f"Duplicate submission: {student_id} - {assignment_name}, "
                       f"current version: {latest.version}, next version: {next_version}"
            )

        return DeduplicationResult(is_duplicate=False, action='new')

    async def check_all(
        self,
        email_uid: str,
        student_id: str,
        assignment_name: str
    ) -> DeduplicationResult:
        """执行完整去重检查：缓存 -> 邮件 -> 提交

        Args:
            email_uid: 邮件UID
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            DeduplicationResult with complete check results
        """
        # 1. 检查缓存
        cached_data = await self.cache_manager.get(email_uid)

        # 2. 检查邮件重复
        email_result = await self.check_email(email_uid)
        if email_result.is_duplicate:
            email_result.cached_data = cached_data
            return email_result

        # 3. 检查提交重复
        submission_result = await self.check_submission(student_id, assignment_name)
        submission_result.cached_data = cached_data

        return submission_result
