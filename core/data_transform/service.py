"""数据转换服务 - 将数据库记录转换为前端展示格式"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from database.models import Submission, RelationType


@dataclass
class FormattedChildRecord:
    """格式化的子记录"""
    id: int
    student_id: str
    student_name: str
    assignment_name: str
    submission_time: str
    version: int
    relation_type: Optional[str] = None
    relation_label: Optional[str] = None
    is_primary: bool = False


@dataclass
class FormattedPrimaryRecord:
    """格式化的主记录（用于前端展示）"""
    id: int
    student_id: str
    student_name: str
    assignment_name: str
    submission_time: str
    version: int
    is_primary: bool = True
    # 统计字段
    child_count: int = 0
    version_count: int = 0
    possible_dup_count: int = 0
    # 子记录列表
    children: List[FormattedChildRecord] = field(default_factory=list)


class DataTransformService:
    """数据转换服务 - 将数据库记录转换为前端展示格式"""

    @staticmethod
    def transform_to_grouped_format(
        raw_submissions: List[Any],
        group_by_assignment: bool = True
    ) -> List[Dict[str, Any]]:
        """
        将原始提交数据转换为分组格式，适合前端折叠行展示

        Args:
            raw_submissions: 原始提交记录列表（可以是 ORM 对象或字典）
            group_by_assignment: 是否按作业名称分组（默认True）

        Returns:
            分组后的记录列表，每个主记录包含子记录和统计信息
        """
        # 分离主记录和子记录
        primary_records = []
        child_records = []

        for record in raw_submissions:
            # 支持字典和 ORM 对象
            is_primary = (
                record.get('is_primary', True)
                if isinstance(record, dict)
                else record.is_primary
            )

            if is_primary:
                primary_records.append(record)
            else:
                child_records.append(record)

        # 构建关系树：{parent_id: [children]}
        relation_tree = DataTransformService.build_relation_tree(child_records)

        # 转换为主记录格式（先关联子记录）
        primary_with_children = []
        for primary in primary_records:
            primary_dict = DataTransformService._record_to_dict(primary)
            primary_id = primary_dict['id']

            # 获取该主记录的所有子记录
            children = relation_tree.get(primary_id, [])

            # 分类子记录
            version_children = []
            possible_dup_children = []
            for child in children:
                relation_type = (
                    child.get('relation_type')
                    if isinstance(child, dict)
                    else child.relation_type.value if child.relation_type else None
                )
                if relation_type == RelationType.VERSION.value:
                    version_children.append(child)
                elif relation_type == RelationType.POSSIBLE_DUP.value:
                    possible_dup_children.append(child)

            # 格式化子记录
            formatted_children = DataTransformService._format_children(
                version_children, possible_dup_children
            )

            # 构建主记录数据
            primary_with_children.append({
                'primary_submission': primary_dict,
                'child_count': len(children),
                'version_count': len(version_children),
                'possible_dup_count': len(possible_dup_children),
                'is_collapsible': len(children) > 0,
                'children': formatted_children
            })

        # 如果需要按作业分组
        if group_by_assignment:
            return DataTransformService._group_by_assignment(primary_with_children)
        else:
            return primary_with_children

    @staticmethod
    def _group_by_assignment(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按作业名称分组记录

        Args:
            records: 主记录列表（包含子记录）

        Returns:
            按作业分组后的记录列表
        """
        # 按作业名称分组
        assignment_groups = {}
        for record in records:
            primary = record.get('primary_submission', {})
            assignment_name = primary.get('assignment_name', '未知作业')

            if assignment_name not in assignment_groups:
                assignment_groups[assignment_name] = []

            assignment_groups[assignment_name].append(record)

        # 转换为作业分组格式
        result = []
        for assignment_name, group_records in sorted(assignment_groups.items()):
            # 统计该作业的信息
            total_submissions = len(group_records)
            total_children = sum(r.get('child_count', 0) for r in group_records)

            result.append({
                'assignment_name': assignment_name,
                'total_submissions': total_submissions,
                'total_children': total_children,
                'records': group_records  # 该作业下的所有学生提交记录
            })

        return result

    @staticmethod
    def _format_children(
        version_children: List[Any],
        possible_dup_children: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        格式化子记录，添加关系标签

        Args:
            version_children: 历史版本子记录
            possible_dup_children: 可能重复的子记录

        Returns:
            格式化后的子记录列表
        """
        formatted = []

        # 格式化历史版本
        for child in version_children:
            child_dict = DataTransformService._record_to_dict(child)
            child_dict['relation_label'] = '📚 历史版本'
            formatted.append(child_dict)

        # 格式化可能重复
        for child in possible_dup_children:
            child_dict = DataTransformService._record_to_dict(child)
            child_dict['relation_label'] = '🔄 可能重复'
            formatted.append(child_dict)

        return formatted

    @staticmethod
    def build_relation_tree(submissions: List[Any]) -> Dict[int, List[Dict[str, Any]]]:
        """
        构建关系树：{parent_id: [children]}

        Args:
            submissions: 子记录列表

        Returns:
            父ID到子记录列表的映射
        """
        tree = {}

        for submission in submissions:
            child_dict = DataTransformService._record_to_dict(submission)
            parent_id = child_dict.get('parent_id')

            if parent_id:
                if parent_id not in tree:
                    tree[parent_id] = []
                tree[parent_id].append(child_dict)

        return tree

    @staticmethod
    def _record_to_dict(record: Any) -> Dict[str, Any]:
        """
        将记录转换为字典格式，处理嵌套的学生数据

        Args:
            record: ORM 对象或字典

        Returns:
            标准化的字典格式
        """
        if isinstance(record, dict):
            # 已经是字典，直接返回
            return record.copy()

        # ORM 对象转换为字典
        result = {
            'id': record.id,
            'student_id': record.student_id,
            'assignment_id': record.assignment_id,
            'message_id': record.message_id,
            'email_uid': record.email_uid,
            'email_subject': record.email_subject,
            'sender_email': record.sender_email,
            'sender_name': record.sender_name,
            'submission_time': record.submission_time.isoformat()
            if record.submission_time
            else None,
            'is_late': record.is_late,
            'is_downloaded': record.is_downloaded,
            'is_replied': record.is_replied,
            'status': record.status,
            'local_path': record.local_path,
            'version': record.version,
            'is_latest': record.is_latest,
            'parent_id': record.parent_id,
            'relation_type': record.relation_type.value
            if record.relation_type
            else None,
            'is_primary': record.is_primary,
        }

        # 处理嵌套的学生数据
        if hasattr(record, 'student') and record.student:
            result['student_name'] = record.student.name
            result['student_email'] = record.student.email
        else:
            # 如果没有嵌套数据，尝试从已有的字段中获取
            result['student_name'] = getattr(record, 'student_name', None)
            result['student_email'] = getattr(record, 'student_email', None)

        # 处理嵌套的作业数据
        if hasattr(record, 'assignment') and record.assignment:
            result['assignment_name'] = record.assignment.name
        else:
            result['assignment_name'] = getattr(record, 'assignment_name', None)

        # 处理附件数据
        if hasattr(record, 'attachments'):
            result['attachments'] = [
                {
                    'id': att.id,
                    'filename': att.filename,
                    'file_size': att.file_size,
                    'local_path': att.local_path,
                }
                for att in record.attachments
            ]
        else:
            result['attachments'] = getattr(record, 'attachments', [])

        return result
