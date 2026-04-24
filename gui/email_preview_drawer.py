"""邮件预览侧边栏组件"""
import os
import customtkinter as ctk
import threading
from typing import Dict, TypedDict, Optional
from datetime import datetime


def _ease_out_cubic(t: float) -> float:
    """缓动函数：先快后慢（用于滑入）"""
    return 1 - pow(1 - t, 3)


def _ease_in_cubic(t: float) -> float:
    """缓动函数：先慢后快（用于滑出）"""
    return pow(t, 3)


class StudentData(TypedDict, total=False):
    """学生信息数据结构"""
    student_id: str
    name: str
    email: str
    is_late: bool
    is_downloaded: bool
    is_replied: bool
    email_subject: str
    email_from: str
    received_time: Optional[datetime]
    submission_time: Optional[datetime]
    email_uid: str
    assignment_name: str
    local_path: Optional[str]
    id: Optional[int]
    attachments: list  # List of attachment dicts

class EmailPreviewDrawer(ctk.CTkFrame):
    """邮件预览侧边栏 - 从右侧滑入显示邮件详情"""

    # 字体大小常量
    FONT_SIZE_LARGE = 18
    FONT_SIZE_TITLE = 14
    FONT_SIZE_NORMAL = 12
    FONT_SIZE_SMALL = 11

    # 内边距常量
    PADDING_CARD = 12
    PADDING_SECTION = 8
    PADDING_BADGE = 4

    # 颜色常量
    COLOR_LATE = "#FF6B6B"
    COLOR_NORMAL = "#51CF66"
    COLOR_DOWNLOADED = "#339AF0"
    COLOR_REPLIED = "#CC5DE8"

    # 邮件正文相关常量
    EMAIL_BODY_MAX_LENGTH = 5000
    IMAP_TIMEOUT_MS = 10000

    def __init__(self, parent, **kwargs) -> None:
        """初始化邮件预览侧边栏

        Args:
            parent: 父容器组件
            **kwargs: 传递给CTkFrame的其他参数
        """
        super().__init__(parent, **kwargs)

        # 配置参数
        self.width_ratio = 0.3  # 侧边栏宽度占屏幕宽度的比例
        self.min_width = 400    # 最小宽度(像素)
        self.max_width = 800    # 最大宽度(像素)
        self.is_pinned = False  # 是否固定显示(不自动隐藏)
        self.is_visible = False # 当前是否可见
        self.is_edit_mode = False # 是否处于编辑模式
        self.current_data = None  # 当前显示的提交数据
        self.current_submission_data = None  # 当前显示的提交数据（用于刷新）
        self.edit_widgets = {}   # 存储编辑模式下的控件引用

        # Animation state
        self._animation_id = None

        # 初始化UI
        self._setup_ui()

    def _cancel_animation(self) -> None:
        """取消当前正在进行的动画"""
        if self._animation_id is not None:
            self.after_cancel(self._animation_id)
            self._animation_id = None

    def _setup_ui(self) -> None:
        """初始化UI组件"""
        # 顶部控制栏（固定按钮和关闭按钮）- 必须最先创建
        self._setup_control_bar()

        # 滚动容器（支持内容过多时滚动）
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="邮件详情")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 卡片1: 学生信息
        self.card_student = self._create_card("学生信息")
        self.card_student.pack(fill="x", pady=(0, 15))

        # 卡片2: 邮件信息
        self.card_email = self._create_card("邮件信息")
        self.card_email.pack(fill="x", pady=(0, 15))

        # 卡片3: 作业信息
        self.card_assignment = self._create_card("作业信息")
        self.card_assignment.pack(fill="x", pady=(0, 15))

        # 卡片4: 附件列表
        self.card_attachments = self._create_card("附件列表")
        self.card_attachments.pack(fill="x", pady=(0, 15))

        # 卡片5: 邮件正文 (NEW)
        self.card_email_body = self._create_card("邮件正文")
        self.card_email_body.pack(fill="x", pady=(0, 15))

    def _create_card(self, title: str) -> ctk.CTkFrame:
        """创建信息卡片

        Args:
            title: 卡片标题

        Returns:
            信息卡片框架
        """
        card = ctk.CTkFrame(self.scroll_frame)

        # 标题
        title_label = ctk.CTkLabel(
            card,
            text=title,
            font=("Arial", 14, "bold")
        )
        title_label.pack(anchor="w", padx=12, pady=(12, 8))

        # 内容容器（后续填充具体字段）
        content_frame = ctk.CTkFrame(card, fg_color="transparent")
        content_frame.pack(fill="x", padx=12, pady=(0, 12))

        # 存储内容框架引用，用于后续更新
        setattr(card, 'content_frame', content_frame)

        return card

    def _update_student_card(self, data: StudentData) -> None:
        """更新学生信息卡片

        Args:
            data: 包含学生信息的字典
        """
        # 清空现有内容
        for widget in self.card_student.content_frame.winfo_children():
            widget.destroy()
        
        # 重置当前卡片的编辑控件
        self.edit_widgets['student_id'] = None
        self.edit_widgets['name'] = None
        self.edit_widgets['email'] = None
        self.edit_widgets['status'] = None

        if self.is_edit_mode:
            # --- 编辑模式 ---
            # 学号
            student_id = data.get('student_id', '')
            ctk.CTkLabel(self.card_student.content_frame, text="学号:", font=("Arial", self.FONT_SIZE_SMALL)).pack(anchor="w")
            id_entry = ctk.CTkEntry(self.card_student.content_frame, font=("Arial", self.FONT_SIZE_NORMAL))
            id_entry.insert(0, student_id)
            id_entry.pack(fill="x", pady=(0, self.PADDING_SECTION))
            self.edit_widgets['student_id'] = id_entry

            # 姓名
            name = data.get('name', '')
            ctk.CTkLabel(self.card_student.content_frame, text="姓名:", font=("Arial", self.FONT_SIZE_SMALL)).pack(anchor="w")
            name_entry = ctk.CTkEntry(self.card_student.content_frame, font=("Arial", self.FONT_SIZE_NORMAL))
            name_entry.insert(0, name)
            name_entry.pack(fill="x", pady=(0, self.PADDING_SECTION))
            self.edit_widgets['name'] = name_entry

            # 邮箱
            email = data.get('email', '') or data.get('email_from', '')
            ctk.CTkLabel(self.card_student.content_frame, text="邮箱:", font=("Arial", self.FONT_SIZE_SMALL)).pack(anchor="w")
            email_entry = ctk.CTkEntry(self.card_student.content_frame, font=("Arial", self.FONT_SIZE_NORMAL))
            email_entry.insert(0, email)
            email_entry.pack(fill="x", pady=(0, self.PADDING_SECTION))
            self.edit_widgets['email'] = email_entry

            # 状态
            status_code = data.get('status', 'pending')
            ctk.CTkLabel(self.card_student.content_frame, text="状态:", font=("Arial", self.FONT_SIZE_SMALL)).pack(anchor="w")
            
            # 获取映射
            status_map = getattr(self.master, 'STATUS_MAP', {'pending': '未处理'})
            # 反向映射用于获取显示文本
            status_options = list(status_map.values())
            current_status_text = status_map.get(status_code, status_code)
            
            status_menu = ctk.CTkOptionMenu(
                self.card_student.content_frame,
                values=status_options,
                font=("Arial", self.FONT_SIZE_NORMAL)
            )
            status_menu.set(current_status_text)
            status_menu.pack(fill="x", pady=(0, self.PADDING_SECTION))
            self.edit_widgets['status'] = status_menu
            
        else:
            # --- 浏览模式 (原代码逻辑) ---
            # 学号（大号字体）
            student_id = data.get('student_id') or "未知 (提取失败)"
            student_id_label = ctk.CTkLabel(
                self.card_student.content_frame,
                text=f"学号: {student_id}",
                font=("Arial", self.FONT_SIZE_LARGE, "bold")
            )
            student_id_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

            # 姓名
            name = data.get('name') or "未知"
            name_label = ctk.CTkLabel(
                self.card_student.content_frame,
                text=f"姓名: {name}",
                font=("Arial", self.FONT_SIZE_NORMAL)
            )
            name_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

            # 邮箱
            email = data.get('email', '未设置')
            email_label = ctk.CTkLabel(
                self.card_student.content_frame,
                text=f"邮箱: {email if email else '未设置'}",
                font=("Arial", self.FONT_SIZE_SMALL)
            )
            email_label.pack(anchor="w", pady=(0, self.PADDING_CARD))

            # 异常信息 (如果有)
            error_msg = data.get('error_message')
            if error_msg:
                error_label = ctk.CTkLabel(
                    self.card_student.content_frame,
                    text=f"⚠ 异常: {error_msg}",
                    font=("Arial", self.FONT_SIZE_SMALL),
                    text_color="#FF4500",
                    wraplength=350,
                    justify="left"
                )
                error_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

            # 状态标签容器
            status_frame = ctk.CTkFrame(self.card_student.content_frame, fg_color="transparent")
            status_frame.pack(fill="x", pady=(self.PADDING_SECTION, 0))

            # 核心状态标签
            status_code = data.get('status', 'pending')
            # 从父窗口获取映射（如果存在）
            status_text = "未知"
            status_color = "#808080"
            if hasattr(self.master, 'STATUS_MAP'):
                status_text = self.master.STATUS_MAP.get(status_code, status_code)
                status_color = self.master.STATUS_COLORS.get(status_code, status_color)
            
            status_badge = ctk.CTkLabel(
                status_frame,
                text=status_text,
                fg_color=status_color,
                text_color="white",
                corner_radius=4,
                padx=self.PADDING_BADGE,
                pady=self.PADDING_BADGE
            )
            status_badge.pack(side="left", padx=(0, self.PADDING_SECTION))

            # 逾期标签
            if data.get('is_late', False):
                late_label = ctk.CTkLabel(
                    status_frame,
                    text="逾期",
                    fg_color=self.COLOR_LATE,
                    text_color="white",
                    corner_radius=4,
                    padx=self.PADDING_BADGE,
                    pady=self.PADDING_BADGE
                )
                late_label.pack(side="left", padx=(0, self.PADDING_SECTION))

    def _update_assignment_card(self, data: StudentData) -> None:
        """更新作业信息卡片

        Args:
            data: 包含作业信息的字典
        """
        # 清空现有内容
        for widget in self.card_assignment.content_frame.winfo_children():
            widget.destroy()

        self.edit_widgets['assignment_name'] = None

        if self.is_edit_mode:
            # --- 编辑模式 ---
            from database.operations import db
            assignments = db.get_all_assignments()
            assignment_names = [a.name for a in assignments]
            current_name = data.get('assignment_name', '未设置')
            
            ctk.CTkLabel(self.card_assignment.content_frame, text="作业名称:", font=("Arial", self.FONT_SIZE_SMALL)).pack(anchor="w")
            
            assignment_menu = ctk.CTkOptionMenu(
                self.card_assignment.content_frame,
                values=assignment_names if assignment_names else [current_name],
                font=("Arial", self.FONT_SIZE_NORMAL)
            )
            assignment_menu.set(current_name)
            assignment_menu.pack(fill="x", pady=(0, self.PADDING_SECTION))
            self.edit_widgets['assignment_name'] = assignment_menu
        else:
            # --- 浏览模式 ---
            # 作业名称
            assignment_name = data.get('assignment_name', '未设置')
            name_label = ctk.CTkLabel(
                self.card_assignment.content_frame,
                text=f"作业名称: {assignment_name}",
                font=("Arial", self.FONT_SIZE_TITLE, "bold")
            )
            name_label.pack(anchor="w", pady=(0, self.PADDING_CARD))

            # 本地存储路径
            local_path = data.get('local_path')
            if local_path:
                # 可点击的路径标签
                path_button = ctk.CTkButton(
                    self.card_assignment.content_frame,
                    text=f"📁 {local_path}",
                    command=lambda: self._copy_path_to_clipboard(local_path),
                    anchor="w",
                    fg_color="#E9ECEF",
                    text_color="black",
                    hover_color="#DEE2E6"
                )
                path_button.pack(fill="x", pady=(0, self.PADDING_SECTION))
            else:
                no_path_label = ctk.CTkLabel(
                    self.card_assignment.content_frame,
                    text="本地路径: 未下载",
                    font=("Arial", self.FONT_SIZE_NORMAL),
                    text_color="gray"
                )
                no_path_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

            # 数据库记录ID
            record_id = data.get('id')
            if record_id:
                id_label = ctk.CTkLabel(
                    self.card_assignment.content_frame,
                    text=f"数据库ID: {record_id}",
                    font=("Arial", 10),
                    text_color="gray"
                )
                id_label.pack(anchor="w")

    def _update_email_card(self, data: StudentData) -> None:
        """更新邮件信息卡片

        Args:
            data: 包含邮件信息的字典
        """
        # 清空现有内容
        for widget in self.card_email.content_frame.winfo_children():
            widget.destroy()

        # 邮件主题（大标题）
        subject = data.get('email_subject', '未设置')
        if len(subject) > 100:  # 限制长度
            subject = subject[:97] + "..."

        subject_label = ctk.CTkLabel(
            self.card_email.content_frame,
            text=subject,
            font=("Arial", self.FONT_SIZE_TITLE, "bold"),
            wraplength=600
        )
        subject_label.pack(anchor="w", pady=(0, self.PADDING_CARD))

        # 发件人
        email_from = data.get('email_from', '未设置')
        from_label = ctk.CTkLabel(
            self.card_email.content_frame,
            text=f"发件人: {email_from}",
            font=("Arial", self.FONT_SIZE_NORMAL)
        )
        from_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

        # 收件时间
        received_time = data.get('received_time')
        if received_time:
            if isinstance(received_time, datetime):
                received_str = received_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                received_str = str(received_time)
        else:
            received_str = "未设置"

        received_label = ctk.CTkLabel(
            self.card_email.content_frame,
            text=f"收件时间: {received_str}",
            font=("Arial", self.FONT_SIZE_NORMAL)
        )
        received_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

        # 提交时间
        submission_time = data.get('submission_time')
        if submission_time:
            if isinstance(submission_time, datetime):
                submission_str = submission_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                submission_str = str(submission_time)
        else:
            submission_str = "未设置"

        submission_label = ctk.CTkLabel(
            self.card_email.content_frame,
            text=f"提交时间: {submission_str}",
            font=("Arial", self.FONT_SIZE_NORMAL)
        )
        submission_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

        # 邮件UID（小号灰色）
        email_uid = data.get('email_uid', '未设置')
        uid_label = ctk.CTkLabel(
            self.card_email.content_frame,
            text=f"UID: {email_uid}",
            font=("Arial", 9),
            text_color="gray"
        )
        uid_label.pack(anchor="w")

    def _copy_path_to_clipboard(self, path: str) -> None:
        """复制路径到剪贴板

        Args:
            path: 要复制的文件路径
        """
        root = self.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(path)
        print(f"已复制路径: {path}")

    def _update_attachments_card(self, data: StudentData) -> None:
        """更新附件列表卡片

        Args:
            data: 包含附件信息的字典
        """
        # 清空现有内容
        for widget in self.card_attachments.content_frame.winfo_children():
            widget.destroy()

        attachments = data.get('attachments', [])

        if not attachments:
            # 空状态
            empty_label = ctk.CTkLabel(
                self.card_attachments.content_frame,
                text="无附件",
                font=("Arial", self.FONT_SIZE_NORMAL),
                text_color="gray"
            )
            empty_label.pack(anchor="w", pady=8)
            return

        # 为每个附件创建操作行
        for idx, attachment in enumerate(attachments):
            self._create_attachment_row(attachment, idx)

    def _create_attachment_row(self, attachment: Dict, idx: int) -> None:
        """创建附件操作行

        Args:
            attachment: 附件信息字典
            idx: 附件索引
        """
        # 附件行容器
        row_frame = ctk.CTkFrame(self.card_attachments.content_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=(0, self.PADDING_SECTION))

        # 文件名（可换行）
        filename = attachment.get('filename', '未命名')
        if len(filename) > 50:
            filename = filename[:47] + "..."

        name_label = ctk.CTkLabel(
            row_frame,
            text=f"📄 {filename}",
            font=("Arial", 10),
            anchor="w"
        )
        name_label.pack(side="left", fill="x", expand=True)

        # 文件大小
        size = attachment.get('size', 0)
        size_str = self._format_size(size)
        size_label = ctk.CTkLabel(
            row_frame,
            text=size_str,
            font=("Arial", 9),
            text_color="gray",
            width=80
        )
        size_label.pack(side="left", padx=(self.PADDING_SECTION, 0))

        # 操作按钮容器
        button_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
        button_frame.pack(side="left", padx=(self.PADDING_SECTION, 0))

        # 打开文件按钮
        file_path = attachment.get('path')
        if file_path and os.path.exists(file_path):
            open_btn = ctk.CTkButton(
                button_frame,
                text="打开",
                width=50,
                height=28,
                command=lambda p=file_path: self._open_file(p)
            )
            open_btn.pack(side="left", padx=(0, 4))

            # 打开文件夹按钮
            folder_btn = ctk.CTkButton(
                button_frame,
                text="定位",
                width=50,
                height=28,
                command=lambda p=file_path: self._open_folder(p)
            )
            folder_btn.pack(side="left", padx=(0, 4))

            # 重命名按钮
            rename_btn = ctk.CTkButton(
                button_frame,
                text="重命名",
                width=50,
                height=28,
                command=lambda p=file_path, n=filename: self._rename_file(p, n)
            )
            rename_btn.pack(side="left")

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小

        Args:
            size_bytes: 文件大小（字节）

        Returns:
            格式化后的文件大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _open_file(self, file_path: str):
        """打开文件（跨平台）"""
        if not os.path.exists(file_path):
            self._show_error("文件不存在", f"文件已被移动或删除：\n{file_path}")
            return

        try:
            import platform
            import subprocess

            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(['open', file_path])
            else:  # Linux
                subprocess.call(['xdg-open', file_path])

            print(f"已打开文件: {file_path}")
        except PermissionError:
            self._show_error("权限不足", "没有权限打开此文件，请检查文件权限")
        except Exception as e:
            print(f"打开文件失败: {e}")
            self._show_error("打开失败", f"无法打开文件：\n{str(e)}")

    def _open_folder(self, file_path: str):
        """在文件管理器中定位文件"""
        if not os.path.exists(file_path):
            self._show_error("文件不存在", f"文件已被移动或删除：\n{file_path}")
            return

        try:
            import platform
            import subprocess

            if platform.system() == 'Windows':
                subprocess.call(['explorer', '/select,', file_path])
            elif platform.system() == 'Darwin':  # macOS
                subprocess.call(['open', '-R', file_path])
            else:  # Linux
                subprocess.call(['nautilus', file_path])

            print(f"已定位文件: {file_path}")
        except PermissionError:
            self._show_error("权限不足", "没有权限访问此文件夹")
        except Exception as e:
            print(f"定位文件失败: {e}")
            self._show_error("定位失败", f"无法定位文件：\n{str(e)}")

    def _rename_file(self, file_path: str, old_name: str):
        """重命名文件"""
        from tkinter import simpledialog

        new_name = simpledialog.askstring(
            "重命名文件",
            f"原文件名: {old_name}\n\n请输入新文件名:",
            initialvalue=old_name
        )

        if not new_name or new_name == old_name:
            return

        if not os.path.exists(file_path):
            self._show_error("文件不存在", f"文件已被移动或删除：\n{file_path}")
            return

        try:
            import shutil
            directory = os.path.dirname(file_path)
            new_path = os.path.join(directory, new_name)

            if os.path.exists(new_path):
                self._show_error("重命名失败", f"目标文件名已存在：\n{new_name}")
                return

            shutil.move(file_path, new_path)
            print(f"已重命名: {old_name} -> {new_name}")

            # 显示成功消息
            self._show_info("重命名成功", f"文件已重命名为：\n{new_name}")

            # 刷新当前显示
            if self.current_data:
                self.show(self.current_data)

        except PermissionError:
            self._show_error("权限不足", "没有权限重命名此文件")
        except Exception as e:
            print(f"重命名失败: {e}")
            self._show_error("重命名失败", f"无法重命名文件：\n{str(e)}")

    def _show_error(self, title: str, message: str) -> None:
        """显示错误对话框

        Args:
            title: 对话框标题
            message: 错误消息
        """
        from tkinter import messagebox
        messagebox.showerror(title, message)

    def _show_info(self, title: str, message: str) -> None:
        """显示信息对话框

        Args:
            title: 对话框标题
            message: 信息消息
        """
        from tkinter import messagebox
        messagebox.showinfo(title, message)

    def _setup_control_bar(self) -> None:
        """设置顶部控制栏"""
        control_bar = ctk.CTkFrame(self, fg_color="transparent", height=40)
        control_bar.pack(side="top", fill="x")

        # 左侧：当前条目标题
        self.title_label = ctk.CTkLabel(
            control_bar,
            text="邮件详情",
            font=("Arial", 12, "bold")
        )
        self.title_label.pack(side="left", padx=10, pady=5)

        # 右侧：按钮容器
        button_container = ctk.CTkFrame(control_bar, fg_color="transparent")
        button_container.pack(side="right", padx=10)

        # 取消按钮 (仅在编辑模式显示)
        self.cancel_button = ctk.CTkButton(
            button_container,
            text="❌ 取消",
            width=80,
            height=30,
            command=self._on_cancel_clicked,
            fg_color="#FF922B",
            text_color="white",
            hover_color="#F76707"
        )
        # 初始不显示

        # 编辑/保存按钮
        self.edit_button = ctk.CTkButton(
            button_container,
            text="📝 编辑",
            width=80,
            height=30,
            command=self.toggle_edit_mode,
            fg_color="#339AF0",
            text_color="white",
            hover_color="#228BE6"
        )
        self.edit_button.pack(side="left", padx=(0, 5))

        # 固定按钮
        self.pin_button = ctk.CTkButton(
            button_container,
            text="📌 固定",
            width=80,
            height=30,
            command=self.toggle_pin,
            fg_color="#E9ECEF",
            text_color="black",
            hover_color="#DEE2E6"
        )
        self.pin_button.pack(side="left", padx=(0, 5))

        # 关闭按钮
        close_button = ctk.CTkButton(
            button_container,
            text="✕",
            width=35,
            height=30,
            command=self.hide,
            fg_color="#FF6B6B",
            text_color="white",
            hover_color="#FA5252"
        )
        close_button.pack(side="left")

    def toggle_edit_mode(self) -> None:
        """切换编辑模式"""
        if self.is_edit_mode:
            # 当前是编辑模式，点击的是"保存"
            self._on_save_clicked()
        else:
            # 当前是浏览模式，进入编辑模式
            self.is_edit_mode = True
            self.edit_button.configure(text="💾 保存", fg_color="#51CF66", hover_color="#40C057")
            self.cancel_button.pack(side="left", padx=(0, 5), before=self.edit_button)
            
            # 刷新显示以显示输入控件
            if self.current_data:
                self._load_data(self.current_data)

    def _on_cancel_clicked(self) -> None:
        """点击取消按钮"""
        self.is_edit_mode = False
        self.edit_button.configure(text="📝 编辑", fg_color="#339AF0", hover_color="#228BE6")
        self.cancel_button.pack_forget()
        
        # 刷新显示以恢复原始数据
        if self.current_data:
            self._load_data(self.current_data)

    def _on_save_clicked(self) -> None:
        """保存编辑后的数据"""
        if not self.current_data:
            return

        # 1. 收集数据
        try:
            new_student_id = self.edit_widgets['student_id'].get().strip()
            new_name = self.edit_widgets['name'].get().strip()
            new_email = self.edit_widgets['email'].get().strip()
            new_status_text = self.edit_widgets['status'].get()
            new_assignment_name = self.edit_widgets['assignment_name'].get()

            # 2. 验证
            if not new_student_id:
                self._show_error("验证失败", "学号不能为空")
                return
            if not new_name:
                self._show_error("验证失败", "姓名不能为空")
                return

            # 3. 状态文本映射回 Code
            status_map = getattr(self.master, 'STATUS_MAP', {})
            new_status_code = 'pending'
            for code, text in status_map.items():
                if text == new_status_text:
                    new_status_code = code
                    break

            # 4. 调用数据库更新
            from database.operations import db
            submission_id = self.current_data.get('id')
            email_uid = self.current_data.get('email_uid')
            email_subject = self.current_data.get('email_subject')
            sender_email = self.current_data.get('email_from')
            submission_time = self.current_data.get('submission_time') or self.current_data.get('received_time')
            
            result = db.update_submission_full(
                submission_id=submission_id,
                student_id=new_student_id,
                name=new_name,
                assignment_name=new_assignment_name,
                status=new_status_code,
                email=new_email,
                email_uid=email_uid,
                email_subject=email_subject,
                sender_email=sender_email,
                submission_time=submission_time
            )

            if result:
                self._show_info("成功", "记录已成功更新")
                
                # 5. 更新本地缓存数据以刷新显示
                self.current_data['id'] = result
                self.current_data['student_id'] = new_student_id
                self.current_data['name'] = new_name
                self.current_data['email'] = new_email
                self.current_data['status'] = new_status_code
                self.current_data['assignment_name'] = new_assignment_name
                
                # 6. 退出编辑模式并刷新
                self.is_edit_mode = False
                self.edit_button.configure(text="📝 编辑", fg_color="#339AF0", hover_color="#228BE6")
                self.cancel_button.pack_forget()
                
                # 刷新侧边栏
                self._load_data(self.current_data)
                
                # 刷新主界面 (如果主界面有这个方法)
                if hasattr(self.master, 'load_data'):
                    current_page = getattr(self.master, 'current_page', 1)
                    self.master.load_data(current_page)
            else:
                self._show_error("错误", "更新数据库失败，请检查日志")

        except Exception as e:
            print(f"Error saving data: {e}")
            self._show_error("保存出错", f"发生意外错误: {str(e)}")

    def show(self, submission_data: Dict):
        """显示/更新侧边栏"""
        self.current_data = submission_data

        # 显示加载状态
        self.title_label.configure(text="加载中...")

        # 使用after避免阻塞UI
        self.after(10, self._load_data, submission_data)

    def _load_data(self, submission_data: Dict):
        """加载数据（在after回调中执行）"""
        # 更新标题栏
        student_id = submission_data.get('student_id', 'Unknown')
        name = submission_data.get('name', 'Unknown')
        self.title_label.configure(text=f"{student_id} - {name}")

        # 更新所有卡片
        self._update_student_card(submission_data)
        self._update_email_card(submission_data)
        self._update_assignment_card(submission_data)
        self._update_attachments_card(submission_data)
        self._update_email_body_card(submission_data)

        # 如果未显示，执行滑入动画
        if not self.is_visible:
            self._slide_in()
        else:
            # 如果已显示，执行内容切换动画
            self._fade_content()

        self.is_visible = True

    def _slide_in(self) -> None:
        """滑入动画 - 优化版"""
        # 取消现有动画
        self._cancel_animation()

        # 计算目标宽度
        parent_width = self.master.winfo_width()
        target_width = int(parent_width * self.width_ratio)
        target_width = max(self.min_width, min(target_width, self.max_width))

        # 设置初始位置（屏幕右侧外）
        self.place(x=parent_width, y=0, relheight=1)
        self.place_configure(width=target_width)

        # 执行滑入动画（使用缓动函数）
        current_x = parent_width
        target_x = parent_width - target_width
        duration = 300  # ms
        fps = 60
        total_frames = int(duration * fps / 1000)

        def animate(frame):
            nonlocal current_x
            if frame < total_frames:
                progress = frame / total_frames
                eased_progress = _ease_out_cubic(progress)
                current_x = parent_width - (parent_width - target_x) * eased_progress
                self.place_configure(x=current_x)
                self._animation_id = self.after(int(1000 // fps), animate, frame + 1)
            else:
                self.place_configure(x=target_x)
                self._animation_id = None

        animate(0)

    def _fade_content(self) -> None:
        """内容切换淡入淡出效果（简化版，仅更新内容）"""
        # 简单实现：直接更新内容，后续可以添加真正的淡入淡出动画
        pass

    def hide(self) -> None:
        """隐藏侧边栏 - 优化动画"""
        if not self.is_visible:
            return

        # 取消现有动画
        self._cancel_animation()

        # 执行滑出动画
        parent_width = self.master.winfo_width()
        current_x = self.winfo_x()
        target_x = parent_width
        duration = 300  # ms
        fps = 60
        total_frames = int(duration * fps / 1000)

        def animate(frame):
            nonlocal current_x
            if frame < total_frames:
                progress = frame / total_frames
                eased_progress = _ease_in_cubic(progress)
                current_x += (target_x - current_x) * eased_progress
                self.place_configure(x=current_x)
                self._animation_id = self.after(int(1000 // fps), animate, frame + 1)
            else:
                self.place_forget()
                self.is_visible = False
                self._animation_id = None

        animate(0)

    def toggle_pin(self) -> None:
        """切换固定状态（固定后不会自动隐藏）"""
        self.is_pinned = not self.is_pinned

        # 更新固定按钮视觉状态
        if hasattr(self, 'pin_button'):
            if self.is_pinned:
                self.pin_button.configure(fg_color="#FFD43B", text="📌 已固定")
            else:
                self.pin_button.configure(fg_color="#E9ECEF", text="📌 固定")

        print(f"固定状态: {'已固定' if self.is_pinned else '未固定'}")

    def _update_email_body_card(self, data: StudentData) -> None:
        """更新邮件正文卡片

        Args:
            data: 包含提交信息的字典
        """
        # 清空现有内容
        for widget in self.card_email_body.content_frame.winfo_children():
            widget.destroy()

        # 获取提交ID
        submission_id = data.get('id')
        if not submission_id:
            self._show_body_error("无法获取提交ID", data)
            return

        # 从数据库获取邮件正文
        from database.operations import db
        body_data = db.get_email_body(submission_id)

        if body_data:
            # 显示缓存的内容
            self._display_body_content(body_data)
        else:
            # 显示加载状态并从IMAP加载
            self._show_body_loading()
            self.after(100, lambda: self._load_email_body_from_imap(data))

    def _display_body_content(self, body_data: Dict) -> None:
        """显示邮件正文内容

        Args:
            body_data: 邮件正文数据，包含 keys: plain_text, html_markdown, format
        """
        # 清空现有内容
        for widget in self.card_email_body.content_frame.winfo_children():
            widget.destroy()

        # 优先使用纯文本，其次使用HTML转Markdown
        content = body_data.get('plain_text') or body_data.get('html_markdown', '')
        format_type = body_data.get('format', 'unknown')

        # 如果没有内容
        if not content or content.strip() == '':
            no_content_label = ctk.CTkLabel(
                self.card_email_body.content_frame,
                text="此邮件没有正文内容",
                font=("Arial", self.FONT_SIZE_NORMAL),
                text_color="gray"
            )
            no_content_label.pack(anchor="w", pady=8)
            return

        # 处理大型邮件正文 - 截断至指定长度
        was_truncated = False
        if len(content) > self.EMAIL_BODY_MAX_LENGTH:
            original_length = len(content)
            content = content[:self.EMAIL_BODY_MAX_LENGTH]
            was_truncated = True

        # 显示格式标签
        format_labels = {
            'text': '纯文本',
            'html': 'HTML转Markdown',
            'both': '纯文本+HTML',
            'empty': '无内容'
        }
        format_text = format_labels.get(format_type, '未知格式')

        format_badge = ctk.CTkLabel(
            self.card_email_body.content_frame,
            text=format_text,
            fg_color="#74C0FC",
            text_color="white",
            corner_radius=4,
            padx=self.PADDING_BADGE,
            pady=self.PADDING_BADGE,
            font=("Arial", 9)
        )
        format_badge.pack(anchor="w", pady=(0, self.PADDING_SECTION))

        # 创建可滚动文本框
        scrollable_frame = ctk.CTkScrollableFrame(
            self.card_email_body.content_frame,
            height=200,
            label_text=""
        )
        scrollable_frame.pack(fill="both", expand=True, pady=(0, self.PADDING_CARD))

        # 显示文本内容
        text_label = ctk.CTkLabel(
            scrollable_frame,
            text=content,
            font=("Arial", 10),
            anchor="w",
            justify="left",
            wraplength=600
        )
        text_label.pack(anchor="w", padx=5, pady=5)

        # 如果内容被截断，显示提示
        if was_truncated:
            truncation_label = ctk.CTkLabel(
                self.card_email_body.content_frame,
                text=f"⚠️ 内容过长（{original_length}字符），已截断至{self.EMAIL_BODY_MAX_LENGTH}字符显示",
                font=("Arial", 9),
                text_color="#FFA000",
                wraplength=600
            )
            truncation_label.pack(anchor="w", pady=(0, self.PADDING_CARD))

    def _show_body_loading(self) -> None:
        """显示邮件正文加载状态"""
        # 清空现有内容
        for widget in self.card_email_body.content_frame.winfo_children():
            widget.destroy()

        loading_label = ctk.CTkLabel(
            self.card_email_body.content_frame,
            text="⏳ 正在从服务器加载邮件正文...",
            font=("Arial", self.FONT_SIZE_NORMAL),
            text_color="gray"
        )
        loading_label.pack(anchor="w", pady=8)

    def _show_body_error(self, error_message: str, submission_data: Optional[StudentData] = None) -> None:
        """显示邮件正文加载错误

        Args:
            error_message: 错误消息
            submission_data: 提交数据（用于重试按钮），可选
        """
        # 清空现有内容
        for widget in self.card_email_body.content_frame.winfo_children():
            widget.destroy()

        error_label = ctk.CTkLabel(
            self.card_email_body.content_frame,
            text=f"⚠️ {error_message}",
            font=("Arial", self.FONT_SIZE_NORMAL),
            text_color="#FF6B6B",
            wraplength=600
        )
        error_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

        # 如果提供了提交数据，显示重试按钮
        if submission_data:
            retry_button = ctk.CTkButton(
                self.card_email_body.content_frame,
                text="🔄 重试加载",
                width=100,
                height=30,
                command=lambda: self._load_email_body_from_imap(submission_data),
                fg_color="#FFA500",
                text_color="white",
                hover_color="#FF8C00"
            )
            retry_button.pack(anchor="w", pady=(0, self.PADDING_CARD))

    def _load_email_body_from_imap(self, data: StudentData) -> None:
        """从IMAP服务器加载邮件正文（使用后台线程和超时处理）

        Args:
            data: 包含提交信息的字典
        """
        email_uid = data.get('email_uid')
        submission_id = data.get('id')

        if not email_uid or not submission_id:
            self._show_body_error("缺少必要信息（UID或提交ID）", data)
            return

        # 显示加载状态
        self._show_body_loading()

        # 用于检查线程是否完成
        thread_complete = threading.Event()
        thread_result = {'success': False, 'error': None, 'body_data': None}
        thread_lock = threading.Lock()

        def load_in_background():
            """在后台线程中执行IMAP操作"""
            try:
                # 导入邮件解析器和配置
                from mail.parser import mail_parser_target
                from database.operations import db
                from config.settings import settings

                # 连接到邮件服务器
                if not mail_parser_target.connect():
                    with thread_lock:
                        thread_result['error'] = "无法连接到邮件服务器"
                    return

                # 选择目标文件夹（必需！）
                target_folder = settings.TARGET_FOLDER
                if not mail_parser_target.imap.select_folder(target_folder):
                    with thread_lock:
                        thread_result['error'] = f"无法选择文件夹: {target_folder}"
                    return

                # 解析邮件
                parsed_email = mail_parser_target.parse_email(email_uid)
                mail_parser_target.disconnect()

                if not parsed_email:
                    with thread_lock:
                        thread_result['error'] = "无法解析邮件"
                    return

                # 提取邮件正文数据
                body_data = parsed_email.get('email_body')
                if not body_data:
                    with thread_lock:
                        thread_result['error'] = "邮件中没有正文信息"
                    return

                # 保存到数据库
                db.save_email_body(submission_id, body_data)

                # 成功 - 使用锁保护写入
                with thread_lock:
                    thread_result['success'] = True
                    thread_result['body_data'] = body_data

            except Exception as e:
                print(f"Error loading email body from IMAP: {e}")
                with thread_lock:
                    thread_result['error'] = f"加载失败: {str(e)}"
            finally:
                thread_complete.set()

        # 启动后台线程
        thread = threading.Thread(target=load_in_background, daemon=True)
        thread.start()

        # 检查超时的回调函数（10秒后）
        def check_timeout():
            with thread_lock:
                if not thread_complete.is_set():
                    # 线程仍在运行，超时
                    self._show_body_error("加载超时（>10秒），请重试", data)
                elif thread_result.get('success'):
                    # 成功完成
                    self._display_body_content(thread_result['body_data'])
                else:
                    # 完成但有错误
                    self._show_body_error(thread_result.get('error') or "未知错误", data)

        # 10秒后检查超时
        self.after(self.IMAP_TIMEOUT_MS, check_timeout)

