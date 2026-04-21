"""邮件预览侧边栏组件"""
import customtkinter as ctk
from typing import Dict

class EmailPreviewDrawer(ctk.CTkFrame):
    """邮件预览侧边栏 - 从右侧滑入显示邮件详情"""

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

    def _update_student_card(self, data: Dict) -> None:
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
            font=("Arial", 18, "bold")
        )
        student_id_label.pack(anchor="w", pady=(0, 8))

        # 姓名
        name_label = ctk.CTkLabel(
            self.card_student.content_frame,
            text=f"姓名: {data.get('name', '未设置')}",
            font=("Arial", 12)
        )
        name_label.pack(anchor="w", pady=(0, 8))

        # 邮箱
        email = data.get('email', '未设置')
        email_label = ctk.CTkLabel(
            self.card_student.content_frame,
            text=f"邮箱: {email if email else '未设置'}",
            font=("Arial", 11)
        )
        email_label.pack(anchor="w", pady=(0, 12))

        # 状态标签容器
        status_frame = ctk.CTkFrame(self.card_student.content_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=(8, 0))

        # 逾期/正常标签
        is_late = data.get('is_late', False)
        status_text = "逾期" if is_late else "正常"
        status_color = "#FF6B6B" if is_late else "#51CF66"  # 红色/绿色
        status_label = ctk.CTkLabel(
            status_frame,
            text=status_text,
            fg_color=status_color,
            text_color="white",
            corner_radius=4,
            padx=8,
            pady=4
        )
        status_label.pack(side="left", padx=(0, 8))

        # 已下载标签
        if data.get('is_downloaded', False):
            downloaded_label = ctk.CTkLabel(
                status_frame,
                text="已下载 ✓",
                fg_color="#339AF0",  # 蓝色
                text_color="white",
                corner_radius=4,
                padx=8,
                pady=4
            )
            downloaded_label.pack(side="left", padx=(0, 8))

        # 已回复标签
        if data.get('is_replied', False):
            replied_label = ctk.CTkLabel(
                status_frame,
                text="已回复 ✓",
                fg_color="#CC5DE8",  # 紫色
                text_color="white",
                corner_radius=4,
                padx=8,
                pady=4
            )
            replied_label.pack(side="left")

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
