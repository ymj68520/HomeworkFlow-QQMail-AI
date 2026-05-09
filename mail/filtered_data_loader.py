"""筛选数据加载器 - 从数据库加载所有符合条件的记录（跨页筛选）"""

from typing import Dict, List, Any, Optional
from database.operations import db
from core.data_transform.service import DataTransformService


class FilteredDataLoader:
    """
    筛选数据加载器

    当应用筛选条件时，使用此加载器从数据库获取所有符合条件的记录，
    绕过 IMAP 分页限制，实现真正的跨页筛选。
    """

    def __init__(self):
        self.data_transform = DataTransformService()

    def get_filtered_page_data(
        self,
        page: int = 1,
        per_page: int = 100,
        student_filter: str = None,
        assignment_filter: str = None,
        status_filter: str = None
    ) -> Dict:
        """
        获取筛选后的分页数据

        Args:
            page: 页码（从 1 开始）
            per_page: 每页记录数
            student_filter: 学生筛选条件
            assignment_filter: 作业筛选条件
            status_filter: 状态筛选条件

        Returns:
            {
                'submissions': 分组格式的提交记录列表,
                'total': 符合条件的总记录数,
                'page': 当前页码,
                'per_page': 每页记录数,
                'total_pages': 总页数
            }
        """
        # 构建数据库查询参数
        criteria = self._build_filter_criteria(
            student_filter, assignment_filter, status_filter
        )

        # 从数据库查询筛选后的分页数据
        result = db.filter_submissions_paginated(
            page=page,
            per_page=per_page,
            **criteria
        )

        # 将结果转换为分组格式（与现有格式一致）
        grouped_data = self._transform_to_grouped_format(
            result['submissions'],
            group_by_assignment=True
        )

        return {
            'submissions': grouped_data,
            'total': result['total'],
            'page': result['page'],
            'per_page': result['per_page'],
            'total_pages': result['total_pages']
        }

    def _build_filter_criteria(
        self,
        student_filter: str,
        assignment_filter: str,
        status_filter: str
    ) -> Dict[str, Any]:
        """
        将 UI 筛选值转换为数据库查询参数

        Args:
            student_filter: 学生筛选条件（如 "001 - 张三" 或 "全部学生"）
            assignment_filter: 作业筛选条件（如 "作业1" 或 "全部作业"）
            status_filter: 状态筛选条件（如 "已完成" 或 "全部状态"）

        Returns:
            数据库查询参数字典
        """
        criteria = {}

        # 处理学生筛选
        if student_filter and student_filter != '全部学生':
            # 从 "001 - 张三" 格式中提取学号
            student_id = student_filter.split(' - ')[0].strip()
            criteria['student_id'] = student_id

        # 处理作业筛选
        if assignment_filter and assignment_filter != '全部作业':
            criteria['assignment_name'] = assignment_filter

        # 处理状态筛选
        if status_filter and status_filter != '全部状态':
            criteria['status'] = status_filter

        return criteria

    def _transform_to_grouped_format(
        self,
        submissions: List[Dict[str, Any]],
        group_by_assignment: bool = True
    ) -> List[Dict[str, Any]]:
        """
        将查询结果转换为分组格式

        Args:
            submissions: 提交记录列表
            group_by_assignment: 是否按作业分组

        Returns:
            分组后的记录列表
        """
        if not submissions:
            return []

        # 使用 DataTransformService 转换为学生分组格式
        student_groups = self.data_transform.transform_to_grouped_format(
            submissions,
            group_by_assignment=False
        )

        if not group_by_assignment:
            return student_groups

        # 按作业分组
        assignment_groups = {}
        for student_group in student_groups:
            primary = student_group.get('primary_submission', {})
            assignment_name = primary.get('assignment_name', '未知作业')

            if assignment_name not in assignment_groups:
                assignment_groups[assignment_name] = {
                    'assignment_name': assignment_name,
                    'records': []
                }

            assignment_groups[assignment_name]['records'].append(student_group)

        # 转换为列表格式
        result = []
        for group_data in assignment_groups.values():
            # 计算统计信息
            records = group_data['records']
            total_submissions = len(records)
            total_children = sum(
                len(g.get('children', [])) for g in records
            )

            result.append({
                'assignment_name': group_data['assignment_name'],
                'records': records,
                'total_submissions': total_submissions,
                'total_children': total_children
            })

        # 按作业名称排序
        result.sort(key=lambda x: x['assignment_name'])

        return result


# 全局单例
filtered_data_loader = FilteredDataLoader()
