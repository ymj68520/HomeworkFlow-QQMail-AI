"""批量修改悬浮弹出层组件"""
import customtkinter as ctk
from typing import List, Dict, Callable, Any, Optional

class BatchEditPopup(ctk.CTkToplevel):
    """批量修改悬浮弹出层"""

    def __init__(self, master, submissions: List[Dict], on_update: Callable[[str, Any], None], **kwargs):
        super().__init__(master, **kwargs)

        self.submissions = submissions
        self.on_update = on_update
        
        # UI 配置
        self.width = 300
        self.height = 350
        
        # 无边框设置
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # 初始定位在鼠标位置
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        
        # 防止超出屏幕边界 (简单处理)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        if x + self.width > screen_width: x = screen_width - self.width
        if y + self.height > screen_height: y = screen_height - self.height
        
        self.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
        # 样式
        self.configure(fg_color=("#F8F9FA", "#212529"))
        
        # 绑定点击外部自动关闭
        self.bind("<FocusOut>", lambda e: self.destroy())
        
        # 主容器
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=2, pady=2)
        
        # 标题栏
        header = ctk.CTkFrame(self.container, height=30, fg_color=("#E9ECEF", "#343A40"))
        header.pack(fill="x")
        
        title = ctk.CTkLabel(header, text=f"批量修改 ({len(submissions)} 项)", font=("Arial", 12, "bold"))
        title.pack(side="left", padx=10)
        
        close_btn = ctk.CTkButton(header, text="✕", width=25, height=25, fg_color="transparent", 
                                 hover_color=("#DEE2E6", "#495057"), text_color=("gray10", "gray90"),
                                 command=self.destroy)
        close_btn.pack(side="right", padx=2)

        # 内容区域
        self.content_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 初始视图：字段选择
        self.show_field_list()
        
        # 获取焦点以便能够接收 FocusOut
        self.after(10, self.focus_set)

    def clear_content(self):
        """清空内容区域"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_field_list(self):
        """显示字段列表视图"""
        self.clear_content()
        
        ctk.CTkLabel(self.content_frame, text="选择要修改的字段:", font=("Arial", 11)).pack(anchor="w", pady=(0, 10))
        
        fields = [
            ("学号", "student_id", "text"),
            ("姓名", "name", "text"),
            ("作业名称", "assignment_name", "dropdown"),
            ("状态", "status", "dropdown")
        ]
        
        for label, field_id, field_type in fields:
            btn = ctk.CTkButton(
                self.content_frame, 
                text=label, 
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("#E9ECEF", "#343A40"),
                height=35,
                command=lambda l=label, i=field_id, t=field_type: self.show_edit_view(l, i, t)
            )
            btn.pack(fill="x", pady=2)

    def show_edit_view(self, label: str, field_id: str, field_type: str):
        """显示编辑视图"""
        self.clear_content()
        
        # 返回按钮
        back_btn = ctk.CTkButton(
            self.content_frame, 
            text="← 返回列表", 
            width=80, 
            height=25,
            fg_color="transparent",
            text_color="#339AF0",
            hover_color=("#E9ECEF", "#343A40"),
            command=self.show_field_list
        )
        back_btn.pack(anchor="w", pady=(0, 15))
        
        ctk.CTkLabel(self.content_frame, text=f"修改 {label} 为:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))
        
        # 输入组件
        input_widget = None
        if field_type == "text":
            input_widget = ctk.CTkEntry(self.content_frame, placeholder_text=f"请输入新{label}...")
            input_widget.pack(fill="x", pady=10)
        elif field_type == "dropdown":
            values = []
            if field_id == "status":
                # 获取主窗口的状态映射
                if hasattr(self.master, 'STATUS_MAP'):
                    values = list(self.master.STATUS_MAP.values())
                else:
                    values = ["未处理", "识别异常", "下载失败", "未回复", "已完成", "已忽略"]
            elif field_id == "assignment_name":
                # 获取已有的作业列表
                from database.operations import db
                assignments = db.get_all_assignments()
                values = [a.name for a in assignments] if assignments else ["默认作业"]
            
            input_widget = ctk.CTkOptionMenu(self.content_frame, values=values)
            input_widget.pack(fill="x", pady=10)
            if values: input_widget.set(values[0])
            
        # 确认按钮
        confirm_btn = ctk.CTkButton(
            self.content_frame, 
            text=f"确认修改 {len(self.submissions)} 条记录",
            fg_color="#51CF66",
            hover_color="#40C057",
            command=lambda: self.on_confirm(field_id, input_widget.get())
        )
        confirm_btn.pack(fill="x", side="bottom", pady=10)

    def on_confirm(self, field_id: str, new_value: Any):
        """点击确认"""
        if not new_value:
            from tkinter import messagebox
            messagebox.showwarning("提示", "值不能为空")
            return
            
        self.on_update(field_id, new_value)
        self.destroy()
