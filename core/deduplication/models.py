"""去重系统数据模型"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from database.models import Submission


@dataclass
class DeduplicationResult:
    """去重检查结果"""
    is_duplicate: bool                          # 是否重复
    duplicate_type: Optional[str] = None        # 'email' | 'submission' | None
    action: str = 'new'                         # 'skip' | 'update_version' | 'new'
    submission: Optional[Submission] = None     # 相关提交记录
    version: Optional[int] = None               # 版本号
    cached_data: Optional[Dict[str, Any]] = None  # 缓存的AI数据
    error: Optional[str] = None                 # 错误信息
    message: str = ""                           # 人类可读消息


@dataclass
class EmailDuplicateInfo:
    """邮件重复信息"""
    email_uid: str
    existing_submission: Submission


@dataclass
class SubmissionDuplicateInfo:
    """提交重复信息"""
    student_id: str
    assignment_name: str
    latest_version: int
    latest_submission: Submission


class DeduplicationError(Exception):
    """去重服务基础异常"""
    pass


class EmailDuplicateError(DeduplicationError):
    """邮件重复异常"""

    def __init__(self, email_uid: str, existing_submission: Submission):
        self.email_uid = email_uid
        self.existing_submission = existing_submission
        super().__init__(f"Email {email_uid} already processed")


class SubmissionDuplicateError(DeduplicationError):
    """提交重复异常"""

    def __init__(self, student_id: str, assignment_name: str, latest_version: int):
        self.student_id = student_id
        self.assignment_name = assignment_name
        self.latest_version = latest_version
        super().__init__(
            f"Submission already exists: {student_id} - {assignment_name}, "
            f"latest version: {latest_version}"
        )


class FileOperationError(DeduplicationError):
    """文件操作异常"""
    pass


class TransactionError(DeduplicationError):
    """事务异常"""
    pass
