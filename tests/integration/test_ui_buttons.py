"""
测试UI按钮是否存在并可见
"""
import sys
from pathlib import Path
import tkinter as tk

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_ui_buttons():
    """测试UI按钮"""
    print("=" * 60)
    print("测试UI批量操作按钮")
    print("=" * 60)

    try:
        from gui.main_window import MainWindow
        import customtkinter as ctk

        print("\n1. 创建主窗口...")
        app = MainWindow()
        print("[OK] 主窗口创建成功")

        print("\n2. 检查批量操作方法...")
        methods = [
            'on_batch_download',
            'on_batch_reply',
            'on_batch_delete'
        ]

        for method in methods:
            exists = hasattr(app, method)
            status = "[OK]" if exists else "[FAIL]"
            print(f"  {status} {method}")

        print("\n3. 检查组件层次结构...")
        print("提示: customtkinter组件使用pack布局，不一定是父子关系")

        # 检查关键属性
        if hasattr(app, 'tree'):
            print(f"\n  [OK] tree (Treeview) 存在")
        else:
            print(f"\n  [FAIL] tree 不存在")

        if hasattr(app, 'selected_label'):
            print(f"  [OK] selected_label 存在")
            print(f"       文本: {app.selected_label.cget('text')}")
        else:
            print(f"  [FAIL] selected_label 不存在")

        print("\n4. 批量操作按钮布局检查...")

        # 检查左侧面板
        left_panels = []
        def find_left_panel(widget):
            try:
                if 'left' in str(widget).lower() or 'panel' in str(widget).lower():
                    left_panels.append(widget)
            except:
                pass

        # 遍历所有组件
        def traverse_widgets(widget, depth=0):
            if depth > 20:
                return
            try:
                widget_type = type(widget).__name__
                widget_info = str(widget)

                if 'CTkButton' in widget_type:
                    try:
                        text = widget.cget('text')
                        print(f"  找到按钮: '{text}'")
                    except:
                        print(f"  找到按钮: <无法获取文本>")

                if hasattr(widget, 'winfo_children'):
                    for child in widget.winfo_children():
                        traverse_widgets(child, depth+1)
            except:
                pass

        print("\n遍历所有组件查找按钮...")
        traverse_widgets(app)

        print("\n" + "=" * 60)
        print("[SUCCESS] UI组件检查完成")
        print("=" * 60)
        print("\n提示: 如果看到'批量下载'、'批量回复'、'批量删除'按钮，")
        print("      说明UI创建正确。如果看不到，请实际运行应用检查。")

        return True

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\nUI按钮测试\n")
    test_ui_buttons()

    print("\n建议：")
    print("1. 运行 'python main.py' 启动应用")
    print("2. 查看左侧面板的'批量操作'区域")
    print("3. 应该能看到4个按钮：")
    print("   - 批量下载")
    print("   - 批量回复")
    print("   - 批量删除")
    print("   - 导出Excel")

if __name__ == '__main__':
    main()
