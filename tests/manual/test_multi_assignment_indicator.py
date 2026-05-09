"""手动测试多作业组指示器功能"""

import sys
import os

# 设置UTF-8编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from gui.components.collapsible_row import CollapsibleRow
from gui.components.data_table import DataTable
from core.data_transform.service import DataTransformService


def test_enrich_with_group_info():
    """测试组信息丰富功能"""
    print("Testing enrich_with_group_info...")

    # 模拟数据
    records = [
        {'id': 1, 'student_id': '1001', 'group_id': 10, 'assignment_name': '作业1'},
        {'id': 2, 'student_id': '1002', 'group_id': 10, 'assignment_name': '作业2'},
        {'id': 3, 'student_id': '1003', 'group_id': None, 'assignment_name': '作业1'},
        {'id': 4, 'student_id': '1004', 'group_id': 20, 'assignment_name': '作业3'},
        {'id': 5, 'student_id': '1005', 'group_id': 20, 'assignment_name': '作业4'},
        {'id': 6, 'student_id': '1006', 'group_id': 20, 'assignment_name': '作业5'},
    ]

    # 丰富组信息
    enriched = DataTransformService.enrich_with_group_info(records)

    # 验证结果
    assert enriched[0]['group_total'] == 2, f"Expected 2, got {enriched[0]['group_total']}"
    assert enriched[1]['group_total'] == 2, f"Expected 2, got {enriched[1]['group_total']}"
    assert enriched[2]['group_total'] == 1, f"Expected 1, got {enriched[2]['group_total']}"
    assert enriched[3]['group_total'] == 3, f"Expected 3, got {enriched[3]['group_total']}"
    assert enriched[4]['group_total'] == 3, f"Expected 3, got {enriched[4]['group_total']}"
    assert enriched[5]['group_total'] == 3, f"Expected 3, got {enriched[5]['group_total']}"

    print("✓ enrich_with_group_info test passed")


def test_ui_indicator():
    """测试UI指示器显示"""
    print("\nTesting UI indicator display...")

    app = QApplication(sys.argv)

    # 测试多作业组记录
    multi_group_data = {
        'primary_submission': {
            'id': 1,
            'student_id': '1001',
            'student_name': '张三',
            'assignment_name': '作业1',
            'submission_time': '2026-05-09 10:00',
            'status': 'pending',
            'local_path': '/path/to/file',
            'group_id': 10,
            'group_total': 3,
            'child_count': 0,
            'version_count': 0,
            'possible_dup_count': 0,
        },
        'child_count': 0,
        'version_count': 0,
        'possible_dup_count': 0,
        'is_collapsible': False,
        'children': []
    }

    row1 = CollapsibleRow(multi_group_data)
    print(f"✓ Multi-group row created with group_total={multi_group_data['primary_submission']['group_total']}")

    # 测试单作业记录
    single_group_data = {
        'primary_submission': {
            'id': 2,
            'student_id': '1002',
            'student_name': '李四',
            'assignment_name': '作业2',
            'submission_time': '2026-05-09 11:00',
            'status': 'completed',
            'local_path': '/path/to/file2',
            'group_id': None,
            'group_total': 1,
            'child_count': 0,
            'version_count': 0,
            'possible_dup_count': 0,
        },
        'child_count': 0,
        'version_count': 0,
        'possible_dup_count': 0,
        'is_collapsible': False,
        'children': []
    }

    row2 = CollapsibleRow(single_group_data)
    print(f"✓ Single-group row created with group_total={single_group_data['primary_submission']['group_total']}")

    # 测试数据表格
    data_table = DataTable()
    test_data = [
        {
            'assignment_name': '作业1',
            'total_submissions': 2,
            'total_children': 0,
            'records': [multi_group_data, single_group_data]
        }
    ]
    data_table.set_data(test_data)
    print("✓ DataTable created and populated with test data")

    print("\n✓ All UI indicator tests passed")


if __name__ == '__main__':
    try:
        test_enrich_with_group_info()
        test_ui_indicator()
        print("\n" + "="*50)
        print("All tests passed successfully!")
        print("="*50)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
