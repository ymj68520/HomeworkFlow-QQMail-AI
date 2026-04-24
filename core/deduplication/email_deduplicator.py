"""邮件级别去重组件"""

from typing import Optional
from database.models import Submission
from database.async_operations import AsyncDatabaseOperations


class EmailDeduplicator:
    """邮件级别去重 - 基于email_uid

    职责：
    - 防止同一封邮件被重复处理
    - 基于email_uid唯一约束判断
    """

    def __init__(self, db: AsyncDatabaseOperations):
        self.db = db

    async def check(self, email_uid: str) -> bool:
        """检查邮件是否已处理

        Args:
            email_uid: 邮件UID

        Returns:
            True if email exists, False otherwise
        """
        existing = await self.get_existing(email_uid)
        return existing is not None

    async def get_existing(self, email_uid: str) -> Optional[Submission]:
        """获取已存在的邮件记录

        Args:
            email_uid: 邮件UID

        Returns:
            Submission record if exists, None otherwise
        """
        return await self.db.get_submission_by_uid(email_uid)
