"""
数据变更通知系统

使用 Qt 信号机制实现跨线程的数据变更通知，
当数据库或后台处理的数据发生变化时，自动通知UI刷新。

设计原则：
1. 全局单例：确保所有组件使用同一个通知器
2. 线程安全：使用 Qt 机制确保跨线程安全
3. 类型化通知：区分不同的变更类型，支持智能刷新
4. 解耦设计：通知者不需要知道谁在监听
"""
from PySide6.QtCore import QObject, Signal
from typing import Optional, Dict, Any, List
from enum import Enum


class ChangeType(Enum):
    """数据变更类型"""
    # 单条记录更新
    RECORD_UPDATED = "record_updated"
    # 单条记录创建
    RECORD_CREATED = "record_created"
    # 单条记录删除
    RECORD_DELETED = "record_deleted"

    # 批量更新
    BATCH_UPDATED = "batch_updated"
    # 批量删除
    BATCH_DELETED = "batch_deleted"

    # 页面级刷新
    PAGE_REFRESH = "page_refresh"

    # 新邮件处理完成
    NEW_EMAILS_PROCESSED = "new_emails_processed"

    # 强制全量刷新
    FULL_REFRESH = "full_refresh"


class DataChangeNotifier(QObject):
    """
    数据变更通知器

    全局单例，通过信号机制实现跨线程的数据变更通知。

    使用方式：
        1. 数据变更时调用 notify_* 方法
        2. UI 连接 data_changed 信号并处理刷新
    """

    # 信号定义：变更类型、变更详情
    data_changed = Signal(str, dict)

    _instance: Optional['DataChangeNotifier'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True

    def notify_record_updated(self, uid: str, submission_id: int = None,
                             changes: Dict[str, Any] = None):
        """
        通知单条记录更新

        Args:
            uid: 邮件UID
            submission_id: 记录ID
            changes: 变更的字段字典
        """
        self.data_changed.emit(
            ChangeType.RECORD_UPDATED.value,
            {
                'uid': uid,
                'submission_id': submission_id,
                'changes': changes or {}
            }
        )

    def notify_record_created(self, uid: str, submission_id: int,
                             student_id: str = None, assignment_name: str = None):
        """
        通知新记录创建

        Args:
            uid: 邮件UID
            submission_id: 记录ID
            student_id: 学号
            assignment_name: 作业名称
        """
        self.data_changed.emit(
            ChangeType.RECORD_CREATED.value,
            {
                'uid': uid,
                'submission_id': submission_id,
                'student_id': student_id,
                'assignment_name': assignment_name
            }
        )

    def notify_record_deleted(self, submission_id: int, uid: str = None):
        """
        通知记录删除

        Args:
            submission_id: 记录ID
            uid: 邮件UID
        """
        self.data_changed.emit(
            ChangeType.RECORD_DELETED.value,
            {
                'submission_id': submission_id,
                'uid': uid
            }
        )

    def notify_batch_updated(self, submission_ids: List[int],
                            changes: Dict[str, Any] = None):
        """
        通知批量更新

        Args:
            submission_ids: 记录ID列表
            changes: 变更的字段字典
        """
        self.data_changed.emit(
            ChangeType.BATCH_UPDATED.value,
            {
                'submission_ids': submission_ids,
                'count': len(submission_ids),
                'changes': changes or {}
            }
        )

    def notify_batch_deleted(self, submission_ids: List[int]):
        """
        通知批量删除

        Args:
            submission_ids: 记录ID列表
        """
        self.data_changed.emit(
            ChangeType.BATCH_DELETED.value,
            {
                'submission_ids': submission_ids,
                'count': len(submission_ids)
            }
        )

    def notify_page_refresh(self, page: int = None):
        """
        通知页面刷新

        Args:
            page: 页码，None表示当前页
        """
        self.data_changed.emit(
            ChangeType.PAGE_REFRESH.value,
            {'page': page}
        )

    def notify_new_emails_processed(self, count: int, details: List[Dict] = None):
        """
        通知新邮件处理完成

        Args:
            count: 处理的邮件数量
            details: 处理详情列表
        """
        self.data_changed.emit(
            ChangeType.NEW_EMAILS_PROCESSED.value,
            {
                'count': count,
                'details': details or []
            }
        )

    def notify_full_refresh(self, reason: str = ""):
        """
        通知需要全量刷新

        Args:
            reason: 刷新原因
        """
        self.data_changed.emit(
            ChangeType.FULL_REFRESH.value,
            {'reason': reason}
        )


# 全局实例
data_change_notifier = DataChangeNotifier()
