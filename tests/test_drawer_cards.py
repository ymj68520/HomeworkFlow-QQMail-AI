import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.email_preview_drawer import EmailPreviewDrawer
import customtkinter as ctk
from datetime import datetime
import tempfile
import os

# 创建测试数据
test_data = {
    'student_id': '2021001',
    'name': '张三',
    'email': 'zhangsan@example.com',
    'is_late': False,
    'is_downloaded': True,
    'is_replied': False
}

# 测试邮件信息卡片
test_email_data = {
    'email_subject': '作业1提交 - Python程序设计',
    'email_from': '李四 <lisi@example.com>',
    'received_time': datetime.now(),
    'submission_time': datetime.now(),
    'email_uid': '12345'
}

# 创建窗口
root = ctk.CTk()
root.geometry("400x600")

drawer = EmailPreviewDrawer(root)
drawer.pack(fill="both", expand=True)

# 测试更新卡片
drawer._update_student_card(test_data)
drawer._update_email_card(test_email_data)

# 测试作业信息卡片
test_assignment_data = {
    'assignment_name': 'Python程序设计作业1',
    'local_path': 'D:/submissions/作业1/2021001张三',
    'id': 42
}
drawer._update_assignment_card(test_assignment_data)

# 测试附件卡片
temp_dir = tempfile.mkdtemp()
test_file = os.path.join(temp_dir, "test_assignment.py")
with open(test_file, 'w', encoding='utf-8') as f:
    f.write("# 测试作业\nprint('Hello World')")

test_attachments_data = {
    'attachments': [
        {
            'filename': 'test_assignment.py',
            'size': 1024,
            'path': test_file
        }
    ]
}
drawer._update_attachments_card(test_attachments_data)

print(f"临时测试文件创建在: {test_file}")
print("测试窗口已打开，请检查附件卡片是否正确显示")

# 测试显示/隐藏
root.update()  # 确保窗口已渲染

print("测试显示...")
drawer.show(test_data)
time.sleep(1)

print("测试更新...")
drawer.show(test_email_data)
time.sleep(1)

print("测试隐藏...")
drawer.hide()
time.sleep(1)

print("测试固定...")
drawer.toggle_pin()
print(f"是否固定: {drawer.is_pinned}")
drawer.toggle_pin()
print(f"是否固定: {drawer.is_pinned}")

root.mainloop()

# 清理临时文件
try:
    os.remove(test_file)
    os.rmdir(temp_dir)
    print("临时文件已清理")
except:
    print("临时文件清理失败（可能已被删除）")
