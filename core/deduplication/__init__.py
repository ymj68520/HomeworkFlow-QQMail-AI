"""去重系统模块

提供统一的服务接口用于去重检查和处理
"""

from core.deduplication.models import (
    DeduplicationResult,
    DeduplicationError,
    EmailDuplicateError,
    SubmissionDuplicateError,
    FileOperationError,
    TransactionError
)
from core.deduplication.service import DeduplicationService
from core.deduplication.email_deduplicator import EmailDeduplicator
from core.deduplication.submission_deduplicator import SubmissionDeduplicator
from core.deduplication.version_manager import VersionManager
from core.deduplication.cache_manager import CacheManager

__all__ = [
    'DeduplicationService',
    'DeduplicationResult',
    'EmailDeduplicator',
    'SubmissionDeduplicator',
    'VersionManager',
    'CacheManager',
    'DeduplicationError',
    'EmailDuplicateError',
    'SubmissionDuplicateError',
    'FileOperationError',
    'TransactionError',
]
