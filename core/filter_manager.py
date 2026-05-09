"""筛选管理器 - 管理筛选状态和数据加载器路由"""

from typing import Dict, Optional
from mail.hybrid_data_loader import hybrid_data_loader
from mail.filtered_data_loader import filtered_data_loader


class FilterManager:
    """
    筛选管理器

    负责管理当前筛选状态，检测是否应使用筛选模式，
    并将数据请求路由到对应的数据加载器。
    """

    def __init__(self):
        self.is_filtering = False
        self.current_filters = {
            'student': '全部学生',
            'assignment': '全部作业',
            'status': '全部状态'
        }

    def should_use_filtered_mode(self) -> bool:
        """
        检查是否有非默认的筛选条件

        Returns:
            True 表示应使用筛选模式，False 表示使用正常分页模式
        """
        return (
            self.current_filters['student'] != '全部学生' or
            self.current_filters['assignment'] != '全部作业' or
            self.current_filters['status'] != '全部状态'
        )

    def get_data(
        self,
        page: int = 1,
        per_page: int = 100,
        force_refresh: bool = False
    ) -> Dict:
        """
        路由到对应的数据加载器

        Args:
            page: 页码
            per_page: 每页记录数
            force_refresh: 是否强制刷新

        Returns:
            数据加载结果
        """
        if self.is_filtering:
            # 使用筛选数据加载器
            return filtered_data_loader.get_filtered_page_data(
                page=page,
                per_page=per_page,
                student_filter=self.current_filters['student'],
                assignment_filter=self.current_filters['assignment'],
                status_filter=self.current_filters['status']
            )
        else:
            # 使用正常混合数据加载器
            return hybrid_data_loader.get_page_data(
                page=page,
                per_page=per_page,
                force_refresh=force_refresh
            )

    def update_filters(
        self,
        student: str,
        assignment: str,
        status: str
    ) -> bool:
        """
        更新筛选状态

        Args:
            student: 学生筛选条件
            assignment: 作业筛选条件
            status: 状态筛选条件

        Returns:
            模式是否改变（True 表示从正常模式切换到筛选模式，或反之）
        """
        old_is_filtering = self.is_filtering

        self.current_filters = {
            'student': student,
            'assignment': assignment,
            'status': status
        }

        self.is_filtering = self.should_use_filtered_mode()

        return old_is_filtering != self.is_filtering

    def clear_filters(self) -> bool:
        """
        清除所有筛选条件

        Returns:
            模式是否改变（True 表示从筛选模式切换到正常模式）
        """
        return self.update_filters(
            student='全部学生',
            assignment='全部作业',
            status='全部状态'
        )

    def get_filter_summary(self) -> str:
        """
        获取可读的筛选摘要

        Returns:
            筛选条件摘要字符串
        """
        filters = []

        if self.current_filters['student'] != '全部学生':
            filters.append(f"学生={self.current_filters['student']}")

        if self.current_filters['assignment'] != '全部作业':
            filters.append(f"作业={self.current_filters['assignment']}")

        if self.current_filters['status'] != '全部状态':
            filters.append(f"状态={self.current_filters['status']}")

        return ', '.join(filters) if filters else '无筛选条件'


# 全局单例
filter_manager = FilterManager()
