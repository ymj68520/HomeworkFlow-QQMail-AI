"""事务性文件操作"""

import shutil
from pathlib import Path
from typing import List, Tuple
from datetime import datetime
from database.models import FileOperationsLog, get_async_session
from core.deduplication.models import FileOperationError


class TransactionalFileOperation:
    """事务性文件操作 - 确保与数据库一致

    所有文件操作都被记录，失败时可以回滚
    """

    def __init__(self, submission_id: int):
        self.submission_id = submission_id
        self.operations: List[Tuple[str, Path]] = []
        self.session_factory = get_async_session()

    async def create_folder(self, path: Path) -> bool:
        """创建文件夹（可回滚）

        Args:
            path: 文件夹路径

        Returns:
            True if successful

        Raises:
            FileOperationError: 如果创建失败
        """
        try:
            path.mkdir(parents=True, exist_ok=True)

            # 记录操作日志
            async with self.session_factory() as session:
                log = FileOperationsLog(
                    submission_id=self.submission_id,
                    operation_type='create_folder',
                    file_path=str(path),
                    status='completed',
                    completed_at=datetime.now()
                )
                session.add(log)
                await session.commit()

            # 记录用于回滚
            self.operations.append(('create_folder', path))
            return True

        except Exception as e:
            raise FileOperationError(f"Failed to create folder {path}: {e}")

    async def save_file(self, path: Path, content: bytes) -> bool:
        """保存文件（可回滚）

        Args:
            path: 文件路径
            content: 文件内容

        Returns:
            True if successful

        Raises:
            FileOperationError: 如果保存失败
        """
        try:
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'wb') as f:
                f.write(content)

            # 记录操作日志
            async with self.session_factory() as session:
                log = FileOperationsLog(
                    submission_id=self.submission_id,
                    operation_type='save_file',
                    file_path=str(path),
                    status='completed',
                    completed_at=datetime.now()
                )
                session.add(log)
                await session.commit()

            # 记录用于回滚
            self.operations.append(('save_file', path))
            return True

        except Exception as e:
            # 清理已创建的文件
            await self._rollback()
            raise FileOperationError(f"Failed to save file {path}: {e}")

    async def delete_file(self, path: Path) -> bool:
        """删除文件

        Args:
            path: 文件路径

        Returns:
            True if successful
        """
        try:
            if path.exists():
                path.unlink()

            async with self.session_factory() as session:
                log = FileOperationsLog(
                    submission_id=self.submission_id,
                    operation_type='delete_file',
                    file_path=str(path),
                    status='completed',
                    completed_at=datetime.now()
                )
                session.add(log)
                await session.commit()

            return True

        except Exception as e:
            raise FileOperationError(f"Failed to delete file {path}: {e}")

    async def _rollback(self):
        """回滚所有文件操作"""
        for op_type, path in reversed(self.operations):
            try:
                if op_type == 'save_file' and path.exists():
                    path.unlink()
                elif op_type == 'create_folder' and path.exists():
                    shutil.rmtree(path)
            except Exception as e:
                print(f"Warning: Failed to rollback {path}: {e}")

    async def cleanup(self):
        """清理资源"""
        # 异步版本不需要特殊清理
        pass
