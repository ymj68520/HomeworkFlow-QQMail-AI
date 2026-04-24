"""版本管理组件 - 数据库为主"""

from database.async_operations import AsyncDatabaseOperations


class VersionManager:
    """版本管理器 - 以数据库为主

    职责：
    - 版本号分配（基于数据库查询）
    - 旧版本标记（数据库操作）
    - 不再依赖文件系统_latest文件
    """

    def __init__(self, db: AsyncDatabaseOperations):
        self.db = db

    async def get_next_version(
        self,
        student_id: str,
        assignment_name: str
    ) -> int:
        """获取下一个版本号（基于数据库）

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            下一个版本号（从1开始）
        """
        latest = await self.db.get_latest_submission(student_id, assignment_name)

        if latest and latest.version:
            return latest.version + 1
        return 1

    async def mark_old_versions(
        self,
        student_id: str,
        assignment_name: str,
        current_version: int
    ) -> int:
        """标记旧版本为非最新

        Args:
            student_id: 学号
            assignment_name: 作业名称
            current_version: 当前版本号（保留为最新）

        Returns:
            被标记的旧版本数量
        """
        return await self.db.mark_old_versions_as_not_latest(
            student_id, assignment_name, current_version
        )
