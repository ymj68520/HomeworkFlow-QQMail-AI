"""筛选选项注册表 - 管理全局筛选选项的自动和手动更新"""

from typing import Set, Dict, List, Optional
from datetime import datetime
from database.operations import db
import threading


class FilterOptionsRegistry:
    """
    筛选选项注册表

    维护全局的学生、作业、状态选项缓存，
    支持自动合并新选项和手动刷新。
    """

    def __init__(self):
        # 选项缓存
        self._students: Set[str] = set()
        self._assignments: Set[str] = set()
        self._statuses: Set[str] = set()

        # 最后更新时间
        self._last_update: Optional[datetime] = None
        self._last_full_scan: Optional[datetime] = None

        # 锁用于线程安全
        self._lock = threading.Lock()

        # 变更标记
        self._has_new_options = False

        # 初始化时执行全量扫描
        self._perform_full_scan()

    def _perform_full_scan(self):
        """从数据库执行全量扫描，获取所有唯一选项"""
        try:
            print("[FilterRegistry] Performing full scan...")

            # 获取所有唯一的学生
            students = db.get_all_unique_students()
            self._students = set(students)

            # 获取所有唯一的作业
            assignments = db.get_all_unique_assignments()
            self._assignments = set(assignments)

            # 状态是预定义的，不需要扫描
            self._statuses = {
                "全部状态", "正常", "逾期",
                "未处理", "识别异常", "下载失败",
                "未回复", "已完成", "已忽略"
            }

            self._last_full_scan = datetime.now()
            self._last_update = datetime.now()
            self._has_new_options = False

            print(f"[FilterRegistry] Full scan completed: "
                  f"{len(self._students)} students, "
                  f"{len(self._assignments)} assignments")

        except Exception as e:
            print(f"[FilterRegistry] Error during full scan: {e}")
            import traceback
            traceback.print_exc()

    def merge_new_options(self, submissions: List[dict]) -> int:
        """
        从提交记录中合并新的选项到注册表

        Args:
            submissions: 提交记录列表（可以是分组格式或平面格式）

        Returns:
            新增的选项数量
        """
        with self._lock:
            new_count = 0
            old_student_count = len(self._students)
            old_assignment_count = len(self._assignments)

            # 展平分组数据
            flat_data = self._flatten_submissions(submissions)

            # 提取并合并学生选项
            for sub in flat_data:
                sid = sub.get('student_id', '')
                name = sub.get('student_name') or sub.get('name', '')
                if sid or name:
                    student_option = f"{sid} - {name}"
                    if student_option not in self._students:
                        self._students.add(student_option)
                        new_count += 1

            # 提取并合并作业选项
            for sub in flat_data:
                assignment = sub.get('assignment_name', '').strip()
                if assignment and assignment not in self._assignments:
                    self._assignments.add(assignment)
                    new_count += 1

            # 如果有新增，更新标记和时间
            if new_count > 0:
                self._has_new_options = True
                self._last_update = datetime.now()
                print(f"[FilterRegistry] Merged {new_count} new options: "
                      f"students {old_student_count}->{len(self._students)}, "
                      f"assignments {old_assignment_count}->{len(self._assignments)}")

            return new_count

    def _flatten_submissions(self, submissions: List[dict]) -> List[dict]:
        """
        将各种格式的提交记录展平为平面列表

        Args:
            submissions: 可能是平面、学生分组或作业分组格式

        Returns:
            展平后的提交记录列表
        """
        flattened = []

        for item in submissions:
            if not isinstance(item, dict):
                continue

            # 处理作业分组 (assignment_name + records)
            if 'assignment_name' in item and 'records' in item:
                flattened.extend(self._flatten_submissions(item['records']))
                continue

            # 处理学生分组 (primary_submission + children)
            primary = item.get('primary_submission')
            if primary:
                flattened.append(primary)

            # 添加子记录
            for child in item.get('children', []):
                flattened.append(child)

            # 处理平面格式 (fallback)
            if not primary and 'student_id' in item:
                flattened.append(item)

        return flattened

    def get_student_options(self, include_all: bool = True) -> List[str]:
        """
        获取学生选项列表（排序后）

        Args:
            include_all: 是否包含"全部学生"选项

        Returns:
            排序后的学生选项列表
        """
        with self._lock:
            options = sorted(list(self._students))
            if include_all:
                options = ["全部学生"] + options
            return options

    def get_assignment_options(self, include_all: bool = True) -> List[str]:
        """
        获取作业选项列表（排序后）

        Args:
            include_all: 是否包含"全部作业"选项

        Returns:
            排序后的作业选项列表
        """
        with self._lock:
            options = sorted(list(self._assignments))
            if include_all:
                options = ["全部作业"] + options
            return options

    def get_status_options(self, include_all: bool = True) -> List[str]:
        """
        获取状态选项列表

        Args:
            include_all: 是否包含"全部状态"选项

        Returns:
            状态选项列表
        """
        with self._lock:
            options = list(self._statuses)
            if include_all:
                # 确保"全部状态"在最前
                if "全部状态" in options:
                    options.remove("全部状态")
                options = ["全部状态"] + sorted(options)
            return options

    def manual_refresh(self) -> Dict[str, int]:
        """
        手动刷新 - 从数据库重新扫描所有选项

        Returns:
            刷新结果统计 {'students': N, 'assignments': M}
        """
        with self._lock:
            old_student_count = len(self._students)
            old_assignment_count = len(self._assignments)

            self._perform_full_scan()

            return {
                'students': len(self._students),
                'assignments': len(self._assignments),
                'new_students': len(self._students) - old_student_count,
                'new_assignments': len(self._assignments) - old_assignment_count
            }

    def has_new_options(self) -> bool:
        """检查是否有新增选项"""
        return self._has_new_options

    def clear_new_flag(self):
        """清除新增选项标记"""
        self._has_new_options = False

    def get_last_update_time(self) -> Optional[datetime]:
        """获取最后更新时间"""
        return self._last_update

    def get_last_full_scan_time(self) -> Optional[datetime]:
        """获取最后全量扫描时间"""
        return self._last_full_scan

    def get_stats(self) -> Dict[str, any]:
        """
        获取注册表统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            return {
                'total_students': len(self._students),
                'total_assignments': len(self._assignments),
                'total_statuses': len(self._statuses),
                'last_update': self._last_update,
                'last_full_scan': self._last_full_scan,
                'has_new_options': self._has_new_options
            }


# 全局单例
filter_options_registry = FilterOptionsRegistry()
