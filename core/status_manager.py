"""
状态管理器 - 独立状态系统核心服务

提供统一的状态转换接口，支持多维度状态管理：
- processing_status: 处理状态
- ai_status: AI提取状态
- download_status: 下载状态
- reply_status: 回复状态
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


# 状态转换规则矩阵
TRANSITION_RULES = {
    'processing': {
        'received': ['processing', 'ignored'],
        'processing': ['extracted', 'failed'],
        'extracted': ['downloading'],
        'downloading': ['downloaded', 'failed'],
        'downloaded': ['replying'],
        'replying': ['replied', 'failed'],
        'replied': [],  # 终态
        'failed': ['processing'],  # 可重试
        'ignored': []  # 终态
    },
    'ai_extraction': {
        'pending': ['extracting'],
        'extracting': ['success', 'failed', 'fallback'],
        'success': [],  # 终态
        'failed': ['pending'],  # 可重试
        'fallback': []  # 终态
    },
    'download': {
        'pending': ['downloading'],
        'downloading': ['success', 'failed'],
        'success': [],  # 终态
        'failed': ['pending']  # 可重试
    },
    'reply': {
        'pending': ['sending'],
        'sending': ['success', 'failed', 'skipped'],
        'success': [],  # 终态
        'failed': ['pending'],  # 可重试
        'skipped': []  # 终态
    }
}

# 向后兼容的状态映射
LEGACY_STATUS_MAP = {
    'processing_status': {
        'ignored': 'ignored',
        'replied': 'completed',
        'failed': 'pending'  # 可能是各种失败
    },
    'download_status': {
        'success': 'unreplied'
    },
    'ai_status': {
        'failed': 'ai_error'
    }
}


class BaseStatusManager(ABC):
    """状态管理器基类"""

    def __init__(self, db_session):
        self.db = db_session

    def can_transition(self, current: str, new: str, status_type: str) -> bool:
        """验证状态转换是否合法"""
        if status_type not in TRANSITION_RULES:
            return False

        valid_transitions = TRANSITION_RULES[status_type].get(current, [])
        return new in valid_transitions

    def _validate_transition(
        self,
        current: str,
        new: str,
        status_type: str
    ) -> Tuple[bool, str]:
        """验证转换并返回 (is_valid, error_message)"""
        if status_type not in TRANSITION_RULES:
            return False, f"Unknown status type: {status_type}"

        if current not in TRANSITION_RULES[status_type]:
            return False, f"Unknown current status: {current} for type {status_type}"

        valid_transitions = TRANSITION_RULES[status_type].get(current, [])
        if new not in valid_transitions:
            return False, f"Invalid transition: {current} -> {new} for {status_type}"

        return True, ""

    @abstractmethod
    def transition(
        self,
        submission_id: int,
        status_type: str,
        new_status: str,
        reason: str = None,
        metadata: Dict = None
    ) -> bool:
        """执行状态转换，自动记录历史"""
        pass

    @abstractmethod
    def transition_batch(
        self,
        submission_ids: List[int],
        status_type: str,
        new_status: str,
        reason: str = None
    ) -> Dict[str, int]:
        """批量状态转换"""
        pass

    @abstractmethod
    def get_status(
        self,
        submission_id: int,
        status_type: str
    ) -> Optional[str]:
        """获取指定类型的状态"""
        pass

    @abstractmethod
    def get_all_statuses(self, submission_id: int) -> Dict[str, str]:
        """获取所有维度的状态"""
        pass

    def get_legacy_status(self, statuses: Dict[str, str]) -> str:
        """从新状态计算向后兼容的旧状态值"""
        proc_status = statuses.get('processing_status', 'received')
        dl_status = statuses.get('download_status', 'pending')
        ai_status = statuses.get('ai_status', 'pending')
        reply_status = statuses.get('reply_status', 'pending')

        # 按优先级判断
        if proc_status == 'ignored':
            return 'ignored'
        if proc_status == 'replied' or reply_status == 'success':
            return 'completed'
        if dl_status == 'failed':
            return 'download_failed'
        if ai_status == 'failed':
            return 'ai_error'
        if proc_status == 'downloaded' or dl_status == 'success':
            return 'unreplied'

        return 'pending'

    @abstractmethod
    def get_history(
        self,
        submission_id: int,
        status_type: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取状态历史记录"""
        pass

    @abstractmethod
    def reset_to_retry(
        self,
        submission_id: int,
        status_type: str = None
    ) -> bool:
        """重置为可重试状态"""
        pass

    @abstractmethod
    def get_failed_submissions(
        self,
        status_type: str = None,
        status_code: str = None
    ) -> List[Dict]:
        """获取失败的提交记录"""
        pass

    def _get_retry_status(self, status_type: str, current_status: str) -> Optional[str]:
        """获取重试时的目标状态"""
        retry_rules = {
            'processing': {
                'failed': 'processing',
                'ai_error': 'processing'
            },
            'ai_extraction': {
                'failed': 'pending'
            },
            'download': {
                'failed': 'pending'
            },
            'reply': {
                'failed': 'pending'
            }
        }

        return retry_rules.get(status_type, {}).get(current_status)

    def get_abnormal_statuses(self) -> List[str]:
        """获取需要重试的异常状态列表"""
        return ['failed', 'ai_error', 'download_failed', 'pending']
