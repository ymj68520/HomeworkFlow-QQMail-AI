"""提交级别去重组件"""

from typing import Optional
from database.models import Submission
from database.async_operations import AsyncDatabaseOperations


class SubmissionDeduplicator:
    """提交级别去重 - 基于student_id + assignment_name

    职责：
    - 检测学生是否重复提交同一作业
    - 返回最新版本用于版本管理
    """

    def __init__(self, db: AsyncDatabaseOperations):
        self.db = db

    async def check(self, student_id: str, assignment_name: str) -> bool:
        """检查学生是否已提交该作业

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            True if submission exists, False otherwise
        """
        latest = await self.get_latest(student_id, assignment_name)
        return latest is not None

    async def get_latest(
        self,
        student_id: str,
        assignment_name: str
    ) -> Optional[Submission]:
        """获取最新提交记录

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            Latest Submission record if exists, None otherwise
        """
        return await self.db.get_latest_submission(student_id, assignment_name)
