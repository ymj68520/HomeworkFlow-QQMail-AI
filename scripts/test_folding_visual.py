"""测试折叠视觉提示效果"""

from PySide6.QtWidgets import QApplication
from gui.components.collapsible_row import CollapsibleRow

# 创建测试数据
test_data = [
    # 无子记录
    {
        'primary_submission': {
            'id': 1,
            'student_id': 'S001',
            'student_name': '张三',
            'assignment_name': '作业1',
            'submission_time': '2026-05-09 10:00',
            'status': 'pending',
            'local_path': '/path/to/file1.pdf'
        },
        'child_count': 0,
        'version_count': 0,
        'possible_dup_count': 0,
        'children': []
    },
    # 只有历史版本
    {
        'primary_submission': {
            'id': 2,
            'student_id': 'S002',
            'student_name': '李四',
            'assignment_name': '作业1',
            'submission_time': '2026-05-09 11:00',
            'status': 'completed',
            'local_path': '/path/to/file2.pdf'
        },
        'child_count': 2,
        'version_count': 2,
        'possible_dup_count': 0,
        'children': [
            {
                'id': 3,
                'student_id': 'S002',
                'student_name': '李四',
                'submission_time': '2026-05-09 09:00',
                'relation_type': 'version',
                'relation_label': '历史版本'
            },
            {
                'id': 4,
                'student_id': 'S002',
                'student_name': '李四',
                'submission_time': '2026-05-09 08:00',
                'relation_type': 'version',
                'relation_label': '历史版本'
            }
        ]
    },
    # 有可能重复
    {
        'primary_submission': {
            'id': 5,
            'student_id': 'S003',
            'student_name': '王五',
            'assignment_name': '作业1',
            'submission_time': '2026-05-09 12:00',
            'status': 'pending',
            'local_path': '/path/to/file3.pdf'
        },
        'child_count': 1,
        'version_count': 0,
        'possible_dup_count': 1,
        'children': [
            {
                'id': 6,
                'student_id': 'S003',
                'student_name': '王五',
                'submission_time': '2026-05-09 11:30',
                'relation_type': 'possible_dup',
                'relation_label': '可能重复'
            }
        ]
    },
    # 混合类型
    {
        'primary_submission': {
            'id': 7,
            'student_id': 'S004',
            'student_name': '赵六',
            'assignment_name': '作业1',
            'submission_time': '2026-05-09 13:00',
            'status': 'pending',
            'local_path': '/path/to/file4.pdf'
        },
        'child_count': 3,
        'version_count': 1,
        'possible_dup_count': 2,
        'children': [
            {
                'id': 8,
                'student_id': 'S004',
                'student_name': '赵六',
                'submission_time': '2026-05-09 12:00',
                'relation_type': 'version',
                'relation_label': '历史版本'
            },
            {
                'id': 9,
                'student_id': 'S004',
                'student_name': '赵六',
                'submission_time': '2026-05-09 11:30',
                'relation_type': 'possible_dup',
                'relation_label': '可能重复'
            },
            {
                'id': 10,
                'student_id': 'S004',
                'student_name': '赵六',
                'submission_time': '2026-05-09 10:00',
                'relation_type': 'possible_dup',
                'relation_label': '可能重复'
            }
        ]
    }
]

if __name__ == '__main__':
    app = QApplication()

    print("测试数据说明：")
    print("1. 张三 - 无子记录（应无折叠按钮，默认边框）")
    print("2. 李四 - 2个历史版本（蓝色边框，按钮显示\"▶ 2\"）")
    print("3. 王五 - 1个可能重复（橙色边框，按钮显示\"▶ 1\"）")
    print("4. 赵六 - 1版本+2重复（橙色边框优先，按钮显示\"▶ 3\"）")
    print("\n预期效果：")
    print("- 无子记录：不显示折叠按钮")
    print("- 有历史版本：左侧蓝色竖条，蓝色按钮")
    print("- 有可能重复：左侧橙色竖条，橙色按钮（优先级更高）")
    print("- 按钮上显示子记录总数")
    print("- 鼠标悬停按钮显示详细分类")

    for data in test_data:
        row = CollapsibleRow(data)
        row.show()

    app.exec()
