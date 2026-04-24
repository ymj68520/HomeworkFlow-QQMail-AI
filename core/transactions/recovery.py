"""错误恢复管理器"""

from typing import Optional
from datetime import datetime, timedelta
from database.models import FileOperationsLog, get_async_session


class RecoveryManager:
    """错误恢复管理器

    处理未完成的文件操作，恢复系统到一致状态
    """

    def __init__(self):
        self.session_factory = get_async_session()

    async def recover_incomplete_operations(self) -> dict:
        """恢复未完成的文件操作

        Returns:
            恢复结果统计: {'total': int, 'recovered': int, 'failed': int}
        """
        async with self.session_factory()() as session:
            result = await session.execute(
                select(FileOperationsLog).filter_by(status='pending')
            )
            pending = result.scalars().all()

        results = {'total': len(pending), 'recovered': 0, 'failed': 0}

        for log in pending:
            try:
                if await self._retry_operation(log):
                    results['recovered'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                print(f"Failed to recover operation {log.id}: {e}")
                results['failed'] += 1

        return results

    async def _retry_operation(self, log: FileOperationsLog) -> bool:
        """重试失败的操作

        Args:
            log: 操作日志记录

        Returns:
            True if successful
        """
        from pathlib import Path

        if log.operation_type == 'save_file':
            path = Path(log.file_path)
            if path.exists():
                async with self.session_factory()() as session:
                    # 重新查询以获取session
                    result = await session.execute(
                        select(FileOperationsLog).filter_by(id=log.id)
                    )
                    log = result.scalar_one_or_none()

                    if log:
                        log.status = 'completed'
                        log.completed_at = datetime.now()
                        await session.commit()
                return True
            else:
                async with self.session_factory()() as session:
                    result = await session.execute(
                        select(FileOperationsLog).filter_by(id=log.id)
                    )
                    log = result.scalar_one_or_none()

                    if log:
                        log.error_message = f"File not found: {log.file_path}"
                        await session.commit()
                return False

        return False

    async def cleanup_old_logs(self, days: int = 7) -> int:
        """清理旧的已完成日志

        Args:
            days: 保留天数
        """
        cutoff = datetime.now() - timedelta(days=days)

        async with self.session_factory()() as session:
            result = await session.execute(
                select(FileOperationsLog).filter(
                    FileOperationsLog.status == 'completed',
                    FileOperationsLog.completed_at < cutoff
                )
            )
            old_logs = result.scalars().all()

            count = len(old_logs)
            for log in old_logs:
                await session.delete(log)

            await session.commit()
            return count


# 需要导入select
from sqlalchemy import select
