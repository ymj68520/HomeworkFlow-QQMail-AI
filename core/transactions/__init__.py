"""事务管理模块

提供事务性文件操作和错误恢复机制
"""

from core.transactions.file_operations import TransactionalFileOperation
from core.transactions.recovery import RecoveryManager

__all__ = [
    'TransactionalFileOperation',
    'RecoveryManager',
]
