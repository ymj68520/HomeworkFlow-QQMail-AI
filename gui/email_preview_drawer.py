"""邮件预览侧边栏组件"""
import os
import customtkinter as ctk
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
        self.current_data = None  # 当前显示的提交数据
        self.current_submission_data = None  # 当前显示的提交数据（用于刷新）

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

        # 学号（大号字体）
        student_id_label = ctk.CTkLabel(
            self.card_student.content_frame,
            text=f"学号: {data.get('student_id', '未设置')}",
            font=("Arial", self.FONT_SIZE_LARGE, "bold")
        )
        student_id_label.pack(anchor="w", pady=(0, self.PADDING_SECTION))

        # 姓名
        name_label = ctk.CTkLabel(
            self.card_student.content_frame,
            text=f"姓名: {data.get('name', '未设置')}",
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

        # 状态标签容器
        status_frame = ctk.CTkFrame(self.card_student.content_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=(self.PADDING_SECTION, 0))

        # 逾期/正常标签
        is_late = data.get('is_late', False)
        status_text = "逾期" if is_late else "正常"
        status_color = self.COLOR_LATE if is_late else self.COLOR_NORMAL
        status_label = ctk.CTkLabel(
            status_frame,
            text=status_text,
            fg_color=status_color,
            text_color="white",
            corner_radius=4,
            padx=self.PADDING_BADGE,
            pady=self.PADDING_BADGE
        )
        status_label.pack(side="left", padx=(0, self.PADDING_SECTION))

        # 已下载标签
        if data.get('is_downloaded', False):
            downloaded_label = ctk.CTkLabel(
                status_frame,
                text="已下载 ✓",
                fg_color=self.COLOR_DOWNLOADED,
                text_color="white",
                corner_radius=4,
                padx=self.PADDING_BADGE,
                pady=self.PADDING_BADGE
            )
            downloaded_label.pack(side="left", padx=(0, self.PADDING_SECTION))

        # 已回复标签
        if data.get('is_replied', False):
            replied_label = ctk.CTkLabel(
                status_frame,
                text="已回复 ✓",
                fg_color=self.COLOR_REPLIED,
                text_color="white",
                corner_radius=4,
                padx=self.PADDING_BADGE,
                pady=self.PADDING_BADGE
            )
            replied_label.pack(side="left")

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

    def _update_assignment_card(self, data: StudentData) -> None:
        """更新作业信息卡片

        Args:
            data: 包含作业信息的字典
        """
        # 清空现有内容
        for widget in self.card_assignment.content_frame.winfo_children():
            widget.destroy()

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
