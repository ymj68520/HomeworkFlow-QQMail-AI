import customtkinter as ctk
from tkinter import ttk, messagebox
from typing import List, Dict
from datetime import datetime
from database.operations import db
from config.settings import settings

class CollapsibleFrame(ctk.CTkFrame):
    """可折叠的框架组件"""
    def __init__(self, master, title, is_expanded=True, **kwargs):
        super().__init__(master, **kwargs)
        
        self.is_expanded = is_expanded
        self.title = title
        
        # 标题栏按钮
        self.header_btn = ctk.CTkButton(
            self, 
            text=f"{'▼' if self.is_expanded else '▶'} {self.title}",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            font=("Arial", 14, "bold"),
            command=self.toggle
        )
        self.header_btn.pack(fill="x", padx=2, pady=2)
        
        # 内容区域
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self.is_expanded:
            self.content_frame.pack(fill="x", padx=5, pady=5)

    def toggle(self):
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.is_expanded = False
            self.header_btn.configure(text=f"▶ {self.title}")
        else:
            self.content_frame.pack(fill="x", padx=5, pady=5)
            self.is_expanded = True
            self.header_btn.configure(text=f"▼ {self.title}")

class MainWindow(ctk.CTk):
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.title("QQ邮箱作业收发系统")
        self.geometry("1400x900")

        # 状态映射
        self.STATUS_MAP = {
            'pending': '未处理',
            'ai_error': '识别异常',
            'download_failed': '下载失败',
            'unreplied': '未回复',
            'completed': '已完成',
            'ignored': '已忽略'
        }
        
        self.STATUS_COLORS = {
            'pending': '#FFA500',      # 橙色
            'ai_error': '#FF4500',     # 橙红
            'download_failed': '#FF0000', # 红色
            'unreplied': '#1E90FF',    # 蓝色
            'completed': '#32CD32',    # 绿色
            'ignored': '#808080'       # 灰色
        }

        # 配置主题
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # 数据
        self.all_submissions = []
        self.filtered_submissions = []
        self.selected_items = []

        # 分页状态
        self.current_page = 1
        self.per_page = 100
        self.total_pages = 1
        self.total_count = 0

        # 复选框图像
        self.checkbox_unchecked_img = None
        self.checkbox_checked_img = None
        self.create_checkbox_images()

        # 复选框状态字典 {item_id: bool}
        self.checked_items = {}

        # 创建UI
        self.setup_ui()

        # 启动后台监听
        self.start_background_monitoring()

        # 绑定ESC键关闭侧边栏
        self.bind("<Escape>", lambda e: self._on_esc_key())

        # 延迟加载数据（避免阻塞UI启动）
        self.after(100, self.load_data)

    def create_checkbox_images(self):
        """创建复选框的 PIL PhotoImage 对象"""
        try:
            from PIL import Image, ImageDraw

            # 图像尺寸
            size = 20

            # 创建未选中复选框 (☐)
            unchecked = Image.new('RGBA', (size, size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(unchecked)
            draw.rectangle([2, 2, size-3, size-3], outline='black', width=2)
            self.checkbox_unchecked_img = ctk.CTkImage(unchecked, size=(size, size))

            # 创建已选中复选框 (☑)
            checked = Image.new('RGBA', (size, size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(checked)
            draw.rectangle([2, 2, size-3, size-3], outline='black', width=2)
            # 绘制勾选标记
            draw.line([5, size//2, size//2-2, size-5], fill='black', width=2)
            draw.line([size//2-2, size-5, size-3, 5], fill='black', width=2)
            self.checkbox_checked_img = ctk.CTkImage(checked, size=(size, size))
        except ImportError:
            print("PIL not found, skipping checkbox images")

    def setup_ui(self):
        """创建UI组件"""
        # 顶部标题栏
        header = ctk.CTkFrame(self, height=80)
        header.pack(fill="x", padx=10, pady=(10, 5))

        title = ctk.CTkLabel(
            header,
            text="QQ邮箱作业收发系统",
            font=("Arial", 28, "bold")
        )
        title.pack(pady=20)

        # 主容器
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # 左侧面板 - 筛选和控制
        left_panel = ctk.CTkScrollableFrame(main_container, width=300, label_text="")
        left_panel.pack(side="left", fill="y", padx=(0, 10))

        self.create_left_panel(left_panel)

        # 右侧面板 - 数据展示
        right_panel = ctk.CTkFrame(main_container)
        right_panel.pack(side="right", fill="both", expand=True)

        self.create_right_panel(right_panel)

    def create_left_panel(self, parent):
        """创建左侧筛选面板（重构为可折叠滚动模式）"""
        
        # 1. 筛选条件区块
        self.filter_section = CollapsibleFrame(parent, title="筛选条件", is_expanded=True)
        self.filter_section.pack(fill="x", padx=5, pady=5)
        self._setup_filter_content(self.filter_section.content_frame)

        # 2. 统计信息区块
        self.stats_section = CollapsibleFrame(parent, title="统计信息", is_expanded=False)
        self.stats_section.pack(fill="x", padx=5, pady=5)
        self._setup_stats_content(self.stats_section.content_frame)

        # 3. 批量操作区块
        self.batch_section = CollapsibleFrame(parent, title="批量操作", is_expanded=True)
        self.batch_section.pack(fill="x", padx=5, pady=5)
        self._setup_batch_content(self.batch_section.content_frame)

        # 状态栏保持在底部（注意：由于父容器现在是可滚动的，状态栏可能需要移出滚动区域或特殊处理）
        self.status_label = ctk.CTkLabel(
            self,  # 移出滚动区域，改绑到 self
            text="状态: 就绪",
            anchor="w"
        )
        self.status_label.pack(side="bottom", fill="x", padx=10, pady=10)

    def _setup_filter_content(self, parent):
        # 搜索框
        search_frame = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame.pack(fill="x", pady=5)
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="搜索学号/姓名...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        search_btn = ctk.CTkButton(search_frame, text="搜索", width=60, command=self.on_search)
        search_btn.pack(side="right")

        # 筛选器
        ctk.CTkLabel(parent, text="按学生筛选:").pack(anchor="w", pady=(10, 0))
        self.student_var = ctk.StringVar(value="全部学生")
        self.student_dropdown = ctk.CTkOptionMenu(
            parent, 
            values=["全部学生"],
            variable=self.student_var,
            command=self.on_filter_change
        )
        self.student_dropdown.pack(fill="x", pady=5)

        ctk.CTkLabel(parent, text="按作业筛选:").pack(anchor="w", pady=(10, 0))
        self.assignment_var = ctk.StringVar(value="全部作业")
        self.assignment_dropdown = ctk.CTkOptionMenu(
            parent, 
            values=["全部作业"],
            variable=self.assignment_var,
            command=self.on_filter_change
        )
        self.assignment_dropdown.pack(fill="x", pady=5)

        ctk.CTkLabel(parent, text="按状态筛选:").pack(anchor="w", pady=(10, 0))
        self.status_var = ctk.StringVar(value="全部状态")
        status_options = ["全部状态", "正常", "逾期"] + list(self.STATUS_MAP.values())
        self.status_dropdown = ctk.CTkOptionMenu(
            parent, 
            values=status_options,
            variable=self.status_var,
            command=self.on_filter_change
        )
        self.status_dropdown.pack(fill="x", pady=5)

    def _setup_stats_content(self, parent):
        self.stats_label = ctk.CTkLabel(
            parent,
            text="总提交: 0\n已下载: 0\n已回复: 0",
            justify="left",
            anchor="w"
        )
        self.stats_label.pack(fill="x", padx=5, pady=5)

    def _setup_batch_content(self, parent):
        self.selected_label = ctk.CTkLabel(parent, text="已选择: 0 项")
        self.selected_label.pack(pady=5)

        btns_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btns_frame.pack(fill="x")

        # 第一行并排
        ctk.CTkButton(btns_frame, text="批量下载", command=self.on_batch_download, width=130).grid(row=0, column=0, padx=2, pady=2)
        ctk.CTkButton(btns_frame, text="批量回复", command=self.on_batch_reply, width=130).grid(row=0, column=1, padx=2, pady=2)
        
        # 第二行并排
        ctk.CTkButton(btns_frame, text="批量删除", command=self.on_batch_delete, width=130).grid(row=1, column=0, padx=2, pady=2)
        ctk.CTkButton(btns_frame, text="导出Excel", command=self.on_export_excel, width=130).grid(row=1, column=1, padx=2, pady=2)

    def create_right_panel(self, parent):
        """创建右侧数据展示面板"""
        # 工具栏
        toolbar = ctk.CTkFrame(parent, height=50)
        toolbar.pack(fill="x", padx=10, pady=10)

        # 刷新按钮
        refresh_btn = ctk.CTkButton(
            toolbar,
            text="刷新数据",
            command=self.load_data,
            width=100
        )
        refresh_btn.pack(side="left", padx=5, pady=10)

        # 全选按钮
        select_all_btn = ctk.CTkButton(
            toolbar,
            text="全选",
            command=self.on_select_all,
            width=100
        )
        select_all_btn.pack(side="left", padx=5, pady=10)

        # 清除选择按钮
        clear_selection_btn = ctk.CTkButton(
            toolbar,
            text="清除选择",
            command=self.on_clear_selection,
            width=100
        )
        clear_selection_btn.pack(side="left", padx=5, pady=10)

        # 数据表格
        table_frame = ctk.CTkFrame(parent)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 创建Treeview
        self.tree = ttk.Treeview(
            table_frame,
            show="headings",
            selectmode="extended"
        )

        # 定义列
        columns = ["select", "学号", "姓名", "作业", "收件时间", "提交时间", "状态", "本地路径"]
        self.tree["columns"] = columns

        # 配置列
        self.tree.heading("select", text="✓")
        self.tree.heading("学号", text="学号")
        self.tree.heading("姓名", text="姓名")
        self.tree.heading("作业", text="作业")
        self.tree.heading("收件时间", text="收件时间")
        self.tree.heading("提交时间", text="提交时间")
        self.tree.heading("状态", text="状态")
        self.tree.heading("本地路径", text="本地路径")

        self.tree.column("select", width=40, anchor="center")
        self.tree.column("学号", width=120, anchor="center")
        self.tree.column("姓名", width=100, anchor="center")
        self.tree.column("作业", width=100, anchor="center")
        self.tree.column("收件时间", width=180, anchor="center")
        self.tree.column("提交时间", width=180, anchor="center")
        self.tree.column("状态", width=120, anchor="center")
        self.tree.column("本地路径", width=300, anchor="w")

        # 滚动条
        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )

        # 布局
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 绑定选择事件
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # 绑定点击事件用于复选框切换
        self.tree.bind("<Button-1>", self.on_tree_click)

        # 绑定双击事件用于打开预览
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # 分页控件
        pagination_frame = ctk.CTkFrame(parent)
        pagination_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.page_label = ctk.CTkLabel(
            pagination_frame,
            text=f"第 {self.current_page}/{self.total_pages} 页 (共 {self.total_count} 条)"
        )
        self.page_label.pack(side="left", padx=5)

        ctk.CTkButton(
            pagination_frame,
            text="上一页",
            command=self.on_prev_page,
            width=80
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            pagination_frame,
            text="下一页",
            command=self.on_next_page,
            width=80
        ).pack(side="left", padx=5)

        # 邮件预览侧边栏
        from gui.email_preview_drawer import EmailPreviewDrawer
        self.preview_drawer = EmailPreviewDrawer(self)

    def load_data(self, page: int = 1):
        """加载数据"""
        try:
            self.status_label.configure(text="状态: 正在连接邮件服务器...")
            self.update()

            # 从TARGET_FOLDER获取数据
            from mail.target_folder_loader import target_folder_loader
            result = target_folder_loader.get_from_target_folder(page, self.per_page)

            self.all_submissions = result['submissions']
            self.filtered_submissions = self.all_submissions.copy()
            self.current_page = result['page']
            self.total_pages = result['total_pages']
            self.total_count = result['total']

            # 更新UI
            self.update_dropdowns()
            self.refresh_table()
            self.update_stats()
            self.update_pagination()

            self.status_label.configure(text=f"状态: 就绪（共{self.total_count}封邮件）")

        except Exception as e:
            messagebox.showerror("错误", f"加载数据失败: {str(e)}")
            self.status_label.configure(text="状态: 错误")

    def update_dropdowns(self):
        """更新下拉菜单选项"""
        # 获取所有学生
        students = set()
        for sub in self.all_submissions:
            students.add(f"{sub['student_id']} - {sub['name']}")

        student_list = ["全部学生"] + sorted(list(students))
        self.student_dropdown.configure(values=student_list)

        # 获取所有作业
        assignments = set()
        for sub in self.all_submissions:
            assignments.add(sub['assignment_name'])

        assignment_list = ["全部作业"] + sorted(list(assignments))
        self.assignment_dropdown.configure(values=assignment_list)

    def refresh_table(self):
        """刷新表格数据"""
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 清空选中状态
        self.checked_items.clear()

        # 填充数据
        for sub in self.filtered_submissions:
            status_code = sub.get('status', 'pending')
            status_text = self.STATUS_MAP.get(status_code, '未知')
            
            if sub.get('is_late'):
                status_text += " (逾期)"
                
            checkbox_symbol = "☐"

            # 格式化收件时间
            received_time = sub.get('received_time')
            if received_time:
                if isinstance(received_time, datetime):
                    received_str = received_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    received_str = str(received_time)
            else:
                received_str = "未知"

            values = [
                checkbox_symbol,
                sub['student_id'],
                sub['name'],
                sub['assignment_name'],
                received_str,
                sub['submission_time'].strftime('%Y-%m-%d %H:%M:%S'),
                status_text,
                sub['local_path'] or "未下载"
            ]

            item_id = self.tree.insert("", "end", values=values)

            # 设置颜色标签
            self.tree.tag_configure(status_code, foreground=self.STATUS_COLORS.get(status_code, "black"))
            self.tree.item(item_id, tags=(status_code,))

            # 设置初始复选框状态
            self.checked_items[item_id] = False

    def update_stats(self):
        """更新统计信息"""
        total = len(self.all_submissions)
        downloaded = sum(1 for sub in self.all_submissions if sub.get('status') in ['unreplied', 'completed'])
        replied = sum(1 for sub in self.all_submissions if sub.get('status') == 'completed')

        self.stats_label.configure(
            text=f"总提交: {total}\n已下载: {downloaded}\n已回复: {replied}"
        )

    def on_search(self):
        """搜索"""
        query = self.search_entry.get().strip()

        if not query:
            self.filtered_submissions = self.all_submissions.copy()
        else:
            self.filtered_submissions = [
                sub for sub in self.all_submissions
                if query in str(sub['student_id']) or query in str(sub['name'])
            ]

        self.refresh_table()

    def on_filter_change(self, value):
        """筛选条件改变"""
        student_filter = self.student_var.get()
        assignment_filter = self.assignment_var.get()
        status_filter = self.status_var.get()

        self.filtered_submissions = self.all_submissions.copy()

        # 学生筛选
        if student_filter != "全部学生":
            student_id = student_filter.split(" - ")[0]
            self.filtered_submissions = [
                sub for sub in self.filtered_submissions
                if sub['student_id'] == student_id
            ]

        # 作业筛选
        if assignment_filter != "全部作业":
            self.filtered_submissions = [
                sub for sub in self.filtered_submissions
                if sub['assignment_name'] == assignment_filter
            ]

        # 状态筛选
        if status_filter == "正常":
            self.filtered_submissions = [
                sub for sub in self.filtered_submissions
                if not sub['is_late']
            ]
        elif status_filter == "逾期":
            self.filtered_submissions = [
                sub for sub in self.filtered_submissions
                if sub['is_late']
            ]
        elif status_filter != "全部状态":
            # 查找对应的 code
            target_code = None
            for code, text in self.STATUS_MAP.items():
                if text == status_filter:
                    target_code = code
                    break
            
            if target_code:
                self.filtered_submissions = [
                    sub for sub in self.filtered_submissions
                    if sub.get('status') == target_code
                ]

        self.refresh_table()

    def on_tree_click(self, event) -> None:
        """处理 Treeview 点击事件"""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell" and region != "heading":
            if hasattr(self, 'preview_drawer') and self.preview_drawer.is_visible and not self.preview_drawer.is_pinned:
                self.preview_drawer.hide()
            return

        column = self.tree.identify("column", event.x, event.y)
        if column != "#1":
            return

        item = self.tree.identify_row(event.y)
        if not item:
            return

        self.toggle_checkbox(item)

    def on_tree_double_click(self, event) -> None:
        """处理表格双击事件"""
        try:
            region = self.tree.identify("region", event.x, event.y)
            if region != "cell":
                return

            item = self.tree.identify_row(event.y)
            if not item:
                return

            index = self.tree.index(item)
            if 0 <= index < len(self.filtered_submissions):
                submission_data = self.filtered_submissions[index]
                self.preview_drawer.show(submission_data)

        except Exception as e:
            messagebox.showerror("预览错误", f"无法打开邮件预览：\n{str(e)}")

    def on_tree_select(self, event):
        """表格选择事件"""
        selected_items = self.tree.selection()
        self.selected_items = selected_items
        count = len(selected_items)
        self.selected_label.configure(text=f"已选择: {count} 项")

    def on_select_all(self):
        """全选"""
        items = self.tree.get_children()
        for item_id in items:
            self.checked_items[item_id] = True
            self.tree.set(item_id, "select", "☑")
        self.update_selected_count()

    def on_clear_selection(self):
        """清除选择"""
        items = self.tree.get_children()
        for item_id in items:
            self.checked_items[item_id] = False
            self.tree.set(item_id, "select", "☐")
        self.update_selected_count()

    def toggle_checkbox(self, item_id):
        """切换复选框状态"""
        current_state = self.checked_items.get(item_id, False)
        new_state = not current_state
        self.checked_items[item_id] = new_state
        checkbox_symbol = "☑" if new_state else "☐"
        self.tree.set(item_id, "select", checkbox_symbol)
        self.update_selected_count()

    def update_selected_count(self):
        """更新选中项计数"""
        count = sum(1 for checked in self.checked_items.values() if checked)
        self.selected_label.configure(text=f"已选择: {count} 项")

    def get_checked_submissions(self) -> List[dict]:
        """获取所有选中的记录"""
        checked_items = self.tree.get_children()
        result = []
        for item_id in checked_items:
            if self.checked_items.get(item_id, False):
                index = self.tree.index(item_id)
                if 0 <= index < len(self.filtered_submissions):
                    result.append(self.filtered_submissions[index])
        return result

    def on_batch_download(self):
        """批量下载附件"""
        submissions = self.get_checked_submissions()
        if not submissions:
            messagebox.showwarning("提示", "请先选择要下载的记录")
            return

        result = messagebox.askyesno("确认批量下载", f"确定要下载 {len(submissions)} 条记录的附件吗？")
        if not result: return

        self.configure(cursor="watch")
        self.update()
        
        success_count = 0
        failed_count = 0
        
        try:
            from mail.parser import mail_parser_inbox as mail_parser
            if not mail_parser.connect():
                messagebox.showerror("错误", "无法连接到邮件服务器")
                return

            for idx, sub in enumerate(submissions):
                try:
                    self.status_label.configure(text=f"状态: 正在下载 {idx+1}/{len(submissions)}...")
                    self.update()

                    email_data = mail_parser.parse_email(sub['email_uid'])
                    if not email_data or not email_data.get('attachments'):
                        failed_count += 1
                        continue

                    from storage.manager import storage_manager
                    local_path = storage_manager.store_submission(
                        assignment_name=sub['assignment_name'],
                        student_id=sub['student_id'],
                        name=sub['name'],
                        attachments=email_data['attachments']
                    )

                    if local_path:
                        db.update_submission_local_path(sub['id'], local_path)
                        # 如果是已回复，则状态变为 completed，否则为 unreplied
                        new_status = 'completed' if sub.get('is_replied') else 'unreplied'
                        db.update_submission_status(sub['id'], new_status)
                        success_count += 1
                    else:
                        db.update_submission_status(sub['id'], 'download_failed')
                        failed_count += 1
                except:
                    failed_count += 1

            self.load_data()
            messagebox.showinfo("结果", f"下载完成！成功: {success_count}, 失败: {failed_count}")
            mail_parser.disconnect()
        finally:
            self.configure(cursor="")
            self.status_label.configure(text="状态: 就绪")

    def on_batch_reply(self):
        """批量回复"""
        submissions = self.get_checked_submissions()
        unreplied = [s for s in submissions if s.get('status') == 'unreplied']
        if not unreplied:
            messagebox.showinfo("提示", "没有符合条件的（已下载且未回复）记录")
            return

        if not messagebox.askyesno("确认", f"确定要回复 {len(unreplied)} 条记录吗？"): return

        self.configure(cursor="watch")
        self.update()
        
        success_count = 0
        from mail.smtp_client import smtp_client
        for s in unreplied:
            if smtp_client.send_reply(s['email'], s['name'], s['assignment_name']):
                db.mark_replied(s['id'])
                db.update_submission_status(s['id'], 'completed')
                success_count += 1
        
        self.load_data()
        messagebox.showinfo("结果", f"回复完成！成功: {success_count}")
        self.configure(cursor="")

    def on_batch_delete(self):
        """批量删除"""
        submissions = self.get_checked_submissions()
        if not submissions: return
        if not messagebox.askyesno("确认", f"确定删除这 {len(submissions)} 条记录吗？"): return

        for s in submissions:
            db.delete_submission(s['id'])
        
        self.load_data()
        messagebox.showinfo("结果", "删除完成")

    def on_export_excel(self):
        messagebox.showinfo("提示", "导出Excel功能待实现")

    def update_pagination(self):
        self.page_label.configure(text=f"第 {self.current_page}/{self.total_pages} 页 (共 {self.total_count} 条)")

    def on_prev_page(self):
        if self.current_page > 1: self.load_data(self.current_page - 1)

    def on_next_page(self):
        if self.current_page < self.total_pages: self.load_data(self.current_page + 1)

    def start_background_monitoring(self):
        import threading, asyncio
        def run_monitoring():
            from core.workflow import workflow
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try: loop.run_until_complete(workflow.monitor_inbox(interval=60))
            except: pass
            finally: loop.close()
        threading.Thread(target=run_monitoring, daemon=True).start()

    def _on_esc_key(self):
        if hasattr(self, 'preview_drawer') and self.preview_drawer.is_visible:
            self.preview_drawer.hide()

if __name__ == '__main__':
    app = MainWindow()
    app.mainloop()
