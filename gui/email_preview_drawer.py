"""邮件预览侧边栏组件"""
import customtkinter as ctk
from typing import Dict, TypedDict, Optional
from datetime import datetime


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

        # 初始化UI
        self._setup_ui()

    def _setup_ui(self) -> None:
        """初始化UI组件

        内容将在后续任务中添加
        """
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

        # 顶部控制栏（固定按钮和关闭按钮）
        self._setup_control_bar()

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

    def _setup_control_bar(self) -> None:
        """设置顶部控制栏（将在后续任务中实现）"""
        pass

    def show(self, submission_data: Dict) -> None:
        """显示/更新侧边栏

        Args:
            submission_data: 包含提交信息的字典
        """
        raise NotImplementedError("将在后续任务中实现")

    def hide(self) -> None:
        """隐藏侧边栏"""
        raise NotImplementedError("将在后续任务中实现")

    def toggle_pin(self) -> None:
        """切换固定状态(固定后不会自动隐藏)"""
        raise NotImplementedError("将在后续任务中实现")
