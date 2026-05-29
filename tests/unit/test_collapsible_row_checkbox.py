import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from PySide6.QtWidgets import QApplication, QCheckBox
from gui.components.collapsible_row import CollapsibleRow

def test_collapsible_row_checkbox():
    # 创建 QApplication 实例
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    data = {
        'student_id': '123',
        'student_name': 'Test Student',
        'assignment_name': 'Assignment 1',
        'submission_time': '2023-10-01T10:00:00',
        'status': 'pending',
        'local_path': '/path/to/file'
    }
    
    print("Testing CollapsibleRow checkbox...")
    row = CollapsibleRow(data)
    
    # 1. 验证复选框是否存在
    if hasattr(row, 'checkbox') and isinstance(row.checkbox, QCheckBox):
        print("[OK] Checkbox exists and is correct type")
    else:
        print("[FAIL] Checkbox does not exist or is incorrect type")
        return False
        
    # 2. 验证初始状态
    if not row.is_checked():
        print("[OK] Initial state is unchecked")
    else:
        print("[FAIL] Initial state is checked")
        return False
        
    # 3. 验证 set_checked(True)
    row.set_checked(True)
    if row.is_checked():
        print("[OK] set_checked(True) works")
    else:
        print("[FAIL] set_checked(True) failed")
        return False
        
    # 4. 验证 set_checked(False)
    row.set_checked(False)
    if not row.is_checked():
        print("[OK] set_checked(False) works")
    else:
        print("[FAIL] set_checked(False) failed")
        return False

    # 5. 验证样式设置（宽度）
    if row.checkbox.minimumWidth() == 24 and row.checkbox.maximumWidth() == 24:
        print("[OK] Checkbox width is set to 24")
    else:
        print(f"[FAIL] Checkbox width is min={row.checkbox.minimumWidth()}, max={row.checkbox.maximumWidth()}, expected 24")
        return False

    print("CollapsibleRow checkbox test passed!")
    return True

if __name__ == "__main__":
    import threading
    import time

    def run_test():
        try:
            success = test_collapsible_row_checkbox()
            if success:
                os._exit(0)
            else:
                os._exit(1)
        except Exception as e:
            print(f"[ERROR] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            os._exit(1)

    # 启动测试线程
    test_thread = threading.Thread(target=run_test)
    test_thread.daemon = True
    test_thread.start()
    
    # 超时保护
    time.sleep(5)
    print("Test timed out after 5 seconds")
    os._exit(1)
