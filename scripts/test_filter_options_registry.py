# -*- coding: utf-8 -*-
"""测试 FilterOptionsRegistry 功能"""

import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.filter_options_registry import FilterOptionsRegistry


def test_basic_functionality():
    """测试基本功能"""
    print("=" * 50)
    print("测试 FilterOptionsRegistry 基本功能")
    print("=" * 50)

    # 创建注册表实例（注意：这会触发数据库查询）
    registry = FilterOptionsRegistry()

    # 获取统计信息
    stats = registry.get_stats()
    print(f"\n[*] 注册表统计:")
    print(f"  - 学生总数: {stats['total_students']}")
    print(f"  - 作业总数: {stats['total_assignments']}")
    print(f"  - 状态总数: {stats['total_statuses']}")
    print(f"  - 最后更新: {stats['last_update']}")
    print(f"  - 最后扫描: {stats['last_full_scan']}")

    # 获取选项列表
    print(f"\n[*] 学生选项 (前5个):")
    students = registry.get_student_options()
    for student in students[:5]:
        print(f"  - {student}")
    if len(students) > 5:
        print(f"  ... 还有 {len(students) - 5} 个")

    print(f"\n[*] 作业选项 (前5个):")
    assignments = registry.get_assignment_options()
    for assignment in assignments[:5]:
        print(f"  - {assignment}")
    if len(assignments) > 5:
        print(f"  ... 还有 {len(assignments) - 5} 个")

    print(f"\n[*] 状态选项:")
    statuses = registry.get_status_options()
    for status in statuses:
        print(f"  - {status}")


def test_merge_new_options():
    """测试合并新选项功能"""
    print("\n" + "=" * 50)
    print("测试合并新选项功能")
    print("=" * 50)

    registry = FilterOptionsRegistry()

    # 获取初始数量
    initial_students = len(registry.get_student_options(include_all=False))
    initial_assignments = len(registry.get_assignment_options(include_all=False))

    print(f"\n初始状态:")
    print(f"  - 学生数: {initial_students}")
    print(f"  - 作业数: {initial_assignments}")

    # 模拟新的提交记录
    new_submissions = [
        {
            'primary_submission': {
                'student_id': '999',
                'student_name': '测试学生',
                'assignment_name': '测试作业',
                'status': 'pending'
            },
            'children': []
        },
        {
            'primary_submission': {
                'student_id': '998',
                'student_name': '另一个测试',
                'assignment_name': '现有作业',  # 假设这个作业已存在
                'status': 'pending'
            },
            'children': []
        }
    ]

    # 合并新选项
    new_count = registry.merge_new_options(new_submissions)

    print(f"\n合并结果:")
    print(f"  - 新增选项数: {new_count}")

    # 获取更新后的数量
    updated_students = len(registry.get_student_options(include_all=False))
    updated_assignments = len(registry.get_assignment_options(include_all=False))

    print(f"\n更新后状态:")
    print(f"  - 学生数: {initial_students} -> {updated_students}")
    print(f"  - 作业数: {initial_assignments} -> {updated_assignments}")


def test_manual_refresh():
    """测试手动刷新功能"""
    print("\n" + "=" * 50)
    print("测试手动刷新功能")
    print("=" * 50)

    registry = FilterOptionsRegistry()

    print("\n执行手动刷新...")
    result = registry.manual_refresh()

    print(f"\n刷新结果:")
    print(f"  - 学生总数: {result['students']}")
    print(f"  - 作业总数: {result['assignments']}")
    print(f"  - 新增学生: {result['new_students']}")
    print(f"  - 新增作业: {result['new_assignments']}")


def test_has_new_options():
    """测试新选项标记功能"""
    print("\n" + "=" * 50)
    print("测试新选项标记功能")
    print("=" * 50)

    registry = FilterOptionsRegistry()

    print(f"\n初始状态 - has_new_options: {registry.has_new_options()}")

    # 添加一些新选项
    new_submissions = [
        {
            'primary_submission': {
                'student_id': '888',
                'student_name': '标记测试学生',
                'assignment_name': '标记测试作业',
                'status': 'pending'
            },
            'children': []
        }
    ]

    new_count = registry.merge_new_options(new_submissions)
    print(f"添加了 {new_count} 个新选项")
    print(f"合并后 - has_new_options: {registry.has_new_options()}")

    # 清除标记
    registry.clear_new_flag()
    print(f"清除标记后 - has_new_options: {registry.has_new_options()}")


if __name__ == '__main__':
    try:
        # 运行所有测试
        test_basic_functionality()
        test_merge_new_options()
        test_manual_refresh()
        test_has_new_options()

        print("\n" + "=" * 50)
        print("[OK] 所有测试完成！")
        print("=" * 50)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
