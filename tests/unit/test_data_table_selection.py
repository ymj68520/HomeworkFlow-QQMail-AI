import sys
import os
from pathlib import Path
import time
import threading

# Add root to sys.path
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui.components.data_table import DataTable

def test_data_table_selection():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    table = DataTable()
    data_list = [
        {'student_id': '001', 'student_name': 'Student A'},
        {'student_id': '002', 'student_name': 'Student B'},
        {'student_id': '003', 'student_name': 'Student C'}
    ]
    table.set_data_bulk(data_list)
    
    print("Testing DataTable selection...")
    
    # 1. Verify "Select All" checkbox exists
    if hasattr(table, 'select_all_checkbox'):
        print("[OK] Select All checkbox exists")
    else:
        print("[FAIL] Select All checkbox does not exist")
        return False

    # 2. Initially no rows should be selected
    selected = table.selectionModel().selectedRows()
    if len(selected) == 0:
        print("[OK] Initially no rows selected")
    else:
        print(f"[FAIL] Initially {len(selected)} rows selected, expected 0")
        return False

    # 3. Test Select All
    table.select_all_checkbox.setChecked(True)
    # SelectionModel uses table.collapsible_rows, which are updated via signal
    # In PySide6, signals are usually synchronous within the same thread
    selected = table.selectionModel().selectedRows()
    if len(selected) == 3:
        print("[OK] Select All checked all 3 rows")
    else:
        print(f"[FAIL] Select All resulted in {len(selected)} selected rows, expected 3")
        for i, row in enumerate(table.collapsible_rows):
            print(f"  Row {i} checked: {row.is_checked()}")
        return False
        
    # Verify row indices
    rows = sorted([idx.row() for idx in selected])
    if rows == [0, 1, 2]:
        print("[OK] Selected row indices are correct [0, 1, 2]")
    else:
        print(f"[FAIL] Selected row indices are {rows}, expected [0, 1, 2]")
        return False

    # 4. Test Unselect All
    table.select_all_checkbox.setChecked(False)
    selected = table.selectionModel().selectedRows()
    if len(selected) == 0:
        print("[OK] Unselect All cleared all rows")
    else:
        print(f"[FAIL] Unselect All left {len(selected)} selected rows")
        return False

    # 5. Test manual row selection and selectionModel response
    table.collapsible_rows[1].set_checked(True)
    selected = table.selectionModel().selectedRows()
    if len(selected) == 1 and selected[0].row() == 1:
        print("[OK] Manual selection correctly reflected in selectionModel")
    else:
        print(f"[FAIL] Manual selection check failed: len={len(selected)}")
        return False

    print("DataTable selection test passed!")
    return True

if __name__ == "__main__":
    def run_test():
        try:
            success = test_data_table_selection()
            if success:
                os._exit(0)
            else:
                os._exit(1)
        except Exception as e:
            print(f"[ERROR] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            os._exit(1)

    test_thread = threading.Thread(target=run_test)
    test_thread.daemon = True
    test_thread.start()

    time.sleep(5)
    print("Test timed out after 5 seconds")
    os._exit(1)
