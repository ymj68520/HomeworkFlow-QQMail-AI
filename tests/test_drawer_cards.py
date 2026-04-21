import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.email_preview_drawer import EmailPreviewDrawer
import customtkinter as ctk
from datetime import datetime

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

root.mainloop()
