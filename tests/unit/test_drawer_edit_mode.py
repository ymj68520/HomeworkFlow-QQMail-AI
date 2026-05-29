import sys
import os
from PySide6.QtWidgets import QApplication, QWidget, QLineEdit, QComboBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QTimer

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.insert(0, project_root)

# Set path for gui module imports
os.environ["PYTHONPATH"] = project_root + os.pathsep + os.environ.get("PYTHONPATH", "")

from gui.components.drawer import Drawer

def run_test():
    app = QApplication(sys.argv)
    
    # Timeout after 5 seconds
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: (print("Test timed out!"), sys.exit(1)))
    timer.start(5000)

    parent = QWidget()
    drawer = Drawer(parent)
    
    details = {
        "学号": "2021001",
        "姓名": "张三",
        "作业": "作业1",
        "状态": "待分析"
    }
    drawer.set_details(details, "测试正文")
    
    print("Checking initial state...")
    assert drawer.is_edit_mode is False
    assert drawer.edit_btn.text() == "📝 编辑"
    
    print("Clicking Edit...")
    QTest.mouseClick(drawer.edit_btn, Qt.LeftButton)
    assert drawer.is_edit_mode is True
    assert drawer.edit_btn.text() == "💾 保存"
    
    # Verify widgets
    assert "学号" in drawer.edit_widgets
    assert isinstance(drawer.edit_widgets["学号"], QLineEdit)
    assert drawer.edit_widgets["学号"].text() == "2021001"
    
    assert "状态" in drawer.edit_widgets
    assert isinstance(drawer.edit_widgets["状态"], QComboBox)
    assert drawer.edit_widgets["状态"].currentText() == "待分析"
    
    print("Modifying values...")
    drawer.edit_widgets["姓名"].setText("李四")
    drawer.edit_widgets["状态"].setCurrentText("已通过")
    
    # Click Save and check signal
    emitted_data = None
    def on_save(data):
        nonlocal emitted_data
        emitted_data = data
        
    drawer.save_requested.connect(on_save)
    
    print("Clicking Save...")
    QTest.mouseClick(drawer.edit_btn, Qt.LeftButton)
    
    assert drawer.is_edit_mode is False
    assert drawer.edit_btn.text() == "📝 编辑"
    assert emitted_data is not None
    assert emitted_data["姓名"] == "李四"
    assert emitted_data["状态"] == "已通过"
    assert emitted_data["学号"] == "2021001"
    
    print("Test passed!")
    timer.stop()
    return True

if __name__ == "__main__":
    try:
        if run_test():
            sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
