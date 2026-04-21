import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.email_preview_drawer import EmailPreviewDrawer
import customtkinter as ctk

# 创建测试数据
test_data = {
    'student_id': '2021001',
    'name': '张三',
    'email': 'zhangsan@example.com',
    'is_late': False,
    'is_downloaded': True,
    'is_replied': False
}

# 创建窗口
root = ctk.CTk()
root.geometry("400x600")

drawer = EmailPreviewDrawer(root)
drawer.pack(fill="both", expand=True)

# 测试更新卡片
drawer._update_student_card(test_data)

root.mainloop()
