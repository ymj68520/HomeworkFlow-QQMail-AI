import customtkinter as ctk
from tkinter import ttk, messagebox
from typing import List
from datetime import datetime
from database.operations import db
from config.settings import settings

class MainWindow(ctk.CTk):
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.title("QQ邮箱作业收发系统")
        self.geometry("1400x900")

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

        # 延迟加载数据（避免阻塞UI启动）
        self.after(100, self.load_data)

    def create_checkbox_images(self):
        """创建复选框的 PIL PhotoImage 对象"""
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
        left_panel = ctk.CTkFrame(main_container, width=300)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)

        self.create_left_panel(left_panel)

        # 右侧面板 - 数据展示
        right_panel = ctk.CTkFrame(main_container)
        right_panel.pack(side="right", fill="both", expand=True)

        self.create_right_panel(right_panel)

    def create_left_panel(self, parent):
        """创建左侧筛选面板"""
        # 标题
        title = ctk.CTkLabel(
            parent,
            text="筛选条件",
            font=("Arial", 18, "bold")
        )
        title.pack(pady=(20, 10))

        # 搜索框
        search_frame = ctk.CTkFrame(parent)
        search_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(search_frame, text="搜索:").pack(anchor="w", padx=5, pady=5)

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="学号或姓名")
        self.search_entry.pack(fill="x", padx=5, pady=5)

        search_btn = ctk.CTkButton(
            search_frame,
            text="搜索",
            command=self.on_search
        )
        search_btn.pack(fill="x", padx=5, pady=5)

        # 学生筛选
        student_frame = ctk.CTkFrame(parent)
        student_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(student_frame, text="学生:").pack(anchor="w", padx=5, pady=5)

        self.student_var = ctk.StringVar(value="全部学生")
        self.student_dropdown = ctk.CTkOptionMenu(
            student_frame,
            variable=self.student_var,
            values=["全部学生"],
            command=self.on_filter_change
        )
        self.student_dropdown.pack(fill="x", padx=5, pady=5)

        # 作业筛选
        assignment_frame = ctk.CTkFrame(parent)
        assignment_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(assignment_frame, text="作业:").pack(anchor="w", padx=5, pady=5)

        self.assignment_var = ctk.StringVar(value="全部作业")
        self.assignment_dropdown = ctk.CTkOptionMenu(
            assignment_frame,
            variable=self.assignment_var,
            values=["全部作业"],
            command=self.on_filter_change
        )
        self.assignment_dropdown.pack(fill="x", padx=5, pady=5)

        # 状态筛选
        status_frame = ctk.CTkFrame(parent)
        status_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(status_frame, text="状态:").pack(anchor="w", padx=5, pady=5)

        self.status_var = ctk.StringVar(value="全部")
        self.status_dropdown = ctk.CTkOptionMenu(
            status_frame,
            variable=self.status_var,
            values=["全部", "正常", "逾期"],
            command=self.on_filter_change
        )
        self.status_dropdown.pack(fill="x", padx=5, pady=5)

        # 统计信息
        stats_frame = ctk.CTkFrame(parent)
        stats_frame.pack(fill="x", padx=10, pady=20)

        ctk.CTkLabel(
            stats_frame,
            text="统计信息",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="总提交: 0\n已下载: 0\n已回复: 0",
            justify="left"
        )
        self.stats_label.pack(pady=10)

        # 批量操作按钮
        batch_frame = ctk.CTkFrame(parent)
        batch_frame.pack(fill="x", padx=10, pady=20)

        ctk.CTkLabel(
            batch_frame,
            text="批量操作",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        self.selected_label = ctk.CTkLabel(
            batch_frame,
            text="已选择: 0 项"
        )
        self.selected_label.pack(pady=5)

        ctk.CTkButton(
            batch_frame,
            text="批量下载",
            command=self.on_batch_download
        ).pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(
            batch_frame,
            text="批量回复",
            command=self.on_batch_reply
        ).pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(
            batch_frame,
            text="批量删除",
            command=self.on_batch_delete
        ).pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(
            batch_frame,
            text="导出Excel",
            command=self.on_export_excel
        ).pack(fill="x", padx=5, pady=5)

        # 状态栏
        self.status_label = ctk.CTkLabel(
            parent,
            text="状态: 就绪",
            anchor="w"
        )
        self.status_label.pack(side="bottom", fill="x", padx=10, pady=10)

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
        self.tree.column("状态", width=100, anchor="center")
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

        # 邮件预览侧边栏（初始隐藏）
        from gui.email_preview_drawer import EmailPreviewDrawer
        self.preview_drawer = EmailPreviewDrawer(self)
        # 不pack/place，等待双击事件触发显示

    def load_data(self, page: int = 1):
        """加载数据 - 从TARGET_FOLDER分页拉取"""
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

        except ConnectionError as e:
            messagebox.showerror("连接错误", f"无法连接到邮件服务器：{str(e)}")
            self.status_label.configure(text="状态: 连接失败")
        except FileNotFoundError as e:
            messagebox.showerror("文件夹错误", str(e))
            self.status_label.configure(text="状态: 文件夹不存在")
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
            status = "逾期" if sub['is_late'] else "正常"
            checkbox_symbol = "☐"  # 初始都未选中

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
                status,
                sub['local_path'] or "未下载"
            ]

            item_id = self.tree.insert("", "end", values=values)

            # 设置初始复选框状态（默认未选中）
            self.checked_items[item_id] = False

    def update_stats(self):
        """更新统计信息"""
        total = len(self.all_submissions)
        downloaded = sum(1 for sub in self.all_submissions if sub['is_downloaded'])
        replied = sum(1 for sub in self.all_submissions if sub['is_replied'])

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
                if query in sub['student_id'] or query in sub['name']
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

        self.refresh_table()

    def on_tree_click(self, event):
        """处理 Treeview 点击事件，切换复选框状态"""
        # 识别点击的列和区域
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify("column", event.x, event.y)

        # "select" 列是第 1 列（索引从 0 或 1 开始，取决于 Treeview）
        # Treeview 的列索引：#0 是图标列，#1 是第一列
        # 我们的 "select" 列应该是 #1

        if column != "#1":
            return

        # 获取点击的 item
        item = self.tree.identify_row(event.y)
        if not item:
            return

        # 切换复选框状态
        self.toggle_checkbox(item)

    def on_tree_double_click(self, event) -> None:
        """处理表格双击事件，打开预览侧边栏

        Args:
            event: 事件对象
        """
        # 识别点击的条目
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        # 获取点击的条目
        item = self.tree.identify_row(event.y)
        if not item:
            return

        # 获取该条目的数据
        index = self.tree.index(item)
        if 0 <= index < len(self.filtered_submissions):
            submission_data = self.filtered_submissions[index]

            # 显示预览侧边栏
            self.preview_drawer.show(submission_data)

            print(f"已打开预览: {submission_data.get('student_id')} - {submission_data.get('name')}")

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
        """切换单行的复选框状态

        Args:
            item_id: Treeview item ID
        """
        # 切换状态
        current_state = self.checked_items.get(item_id, False)
        new_state = not current_state
        self.checked_items[item_id] = new_state

        # 更新显示
        checkbox_symbol = "☑" if new_state else "☐"
        self.tree.set(item_id, "select", checkbox_symbol)

        # 更新选中计数
        self.update_selected_count()

    def update_selected_count(self):
        """更新选中项计数标签"""
        count = sum(1 for checked in self.checked_items.values() if checked)
        self.selected_label.configure(text=f"已选择: {count} 项")

    def get_checked_submissions(self) -> List[dict]:
        """获取所有选中的提交记录

        Returns:
            选中记录的列表，每个记录包含完整的 submission 信息
        """
        checked_items = self.tree.get_children()
        result = []

        for item_id in checked_items:
            if self.checked_items.get(item_id, False):
                # 获取该 item 在 filtered_submissions 中的索引
                index = self.tree.index(item_id)
                if 0 <= index < len(self.filtered_submissions):
                    result.append(self.filtered_submissions[index])

        return result

    def on_batch_download(self):
        """批量下载附件"""
        print("DEBUG: 批量下载按钮被点击")
        submissions = self.get_checked_submissions()
        print(f"DEBUG: 获取到 {len(submissions)} 条选中记录")

        if not submissions:
            messagebox.showwarning("提示", "请先选择要下载的记录")
            return

        # 确认对话框
        result = messagebox.askyesno(
            "确认批量下载",
            f"确定要重新下载 {len(submissions)} 条记录的附件吗？\n已存在的文件将被覆盖。"
        )

        if not result:
            return

        # 禁用窗口
        self.configure(cursor="watch")
        self.update()
        self.status_label.configure(text="状态: 批量下载中...")

        success_count = 0
        failed_count = 0
        failed_items = []

        try:
            from mail.parser import mail_parser_inbox as mail_parser

            # 先连接到邮件服务器
            print("DEBUG: 正在连接到邮件服务器...")
            if not mail_parser.connect():
                messagebox.showerror("错误", "无法连接到邮件服务器，请检查网络连接和配置")
                return
            print("DEBUG: 邮件服务器连接成功")

            for idx, sub in enumerate(submissions):
                try:
                    self.status_label.configure(
                        text=f"状态: 正在下载第 {idx+1}/{len(submissions)} 项..."
                    )
                    self.update()

                    # 解析邮件获取附件
                    print(f"DEBUG: 正在解析邮件 UID={sub['email_uid']}")
                    email_data = mail_parser.parse_email(sub['email_uid'])

                    print(f"DEBUG: email_data={type(email_data)}")
                    if email_data:
                        # 安全地打印主题（避免编码错误）
                        try:
                            subject = email_data.get('subject', '')
                            print(f"DEBUG: 邮件主题={subject}")
                        except:
                            print(f"DEBUG: 邮件主题=<包含特殊字符，无法显示>")
                        print(f"DEBUG: 附件数量={len(email_data.get('attachments', []))}")

                    if not email_data or not email_data.get('attachments'):
                        failed_items.append(f"{sub['student_id']} - {sub['name']}: 无附件")
                        failed_count += 1
                        print(f"DEBUG: 跳过（无附件）")
                        continue

                    # 重新保存附件
                    from storage.manager import storage_manager
                    local_path = storage_manager.store_submission(
                        assignment_name=sub['assignment_name'],
                        student_id=sub['student_id'],
                        name=sub['name'],
                        attachments=email_data['attachments']
                    )

                    if local_path:
                        # 更新数据库
                        db.update_submission_local_path(sub['id'], local_path)
                        success_count += 1
                    else:
                        failed_items.append(f"{sub['student_id']} - {sub['name']}: 保存失败")
                        failed_count += 1

                except Exception as e:
                    error_msg = str(e)
                    # 截断过长的错误信息
                    if len(error_msg) > 100:
                        error_msg = error_msg[:100] + "..."

                    print(f"DEBUG: 处理记录时出错: {error_msg}")
                    failed_items.append(f"{sub['student_id']} - {sub['name']}: {error_msg}")
                    failed_count += 1

                    # 继续处理下一条记录，不中断
                    continue

            # 刷新数据
            self.load_data()

            # 显示结果
            message = f"批量下载完成！\n\n成功: {success_count} 项\n失败: {failed_count} 项"
            if failed_items:
                message += "\n\n失败详情:\n" + "\n".join(failed_items[:5])
                if len(failed_items) > 5:
                    message += f"\n... 还有 {len(failed_items)-5} 项"

            messagebox.showinfo("批量下载结果", message)

            # 断开邮件服务器连接
            mail_parser.disconnect()

        except Exception as e:
            messagebox.showerror("错误", f"批量下载失败: {str(e)}")
            try:
                mail_parser.disconnect()
            except:
                pass

        finally:
            # 恢复窗口
            self.configure(cursor="")
            self.status_label.configure(text="状态: 就绪")

    def on_batch_reply(self):
        """批量回复邮件"""
        print("DEBUG: 批量回复按钮被点击")
        submissions = self.get_checked_submissions()
        print(f"DEBUG: 获取到 {len(submissions)} 条选中记录")

        if not submissions:
            messagebox.showwarning("提示", "请先选择要回复的记录")
            return

        # 过滤出未回复的记录
        unreplied_submissions = [sub for sub in submissions if not sub['is_replied']]

        if not unreplied_submissions:
            messagebox.showinfo("提示", "选中的记录都已回复过")
            return

        # 确认对话框
        result = messagebox.askyesno(
            "确认批量回复",
            f"将给 {len(unreplied_submissions)} 条未回复记录发送确认邮件。\n\n是否继续？"
        )

        if not result:
            return

        # 禁用窗口
        self.configure(cursor="watch")
        self.update()
        self.status_label.configure(text="状态: 批量回复中...")

        success_count = 0
        failed_count = 0
        failed_items = []

        try:
            from mail.smtp_client import smtp_client

            for idx, sub in enumerate(unreplied_submissions):
                try:
                    self.status_label.configure(
                        text=f"状态: 正在回复第 {idx+1}/{len(unreplied_submissions)} 项..."
                    )
                    self.update()

                    # 发送邮件
                    sent = smtp_client.send_reply(
                        to_email=sub['email'],
                        student_name=sub['name'],
                        assignment_name=sub['assignment_name']
                    )

                    if sent:
                        # 标记为已回复
                        db.mark_replied(sub['id'])
                        success_count += 1
                    else:
                        failed_items.append(f"{sub['student_id']} - {sub['name']}: 发送失败")
                        failed_count += 1

                    # 延迟避免触发速率限制
                    import time
                    time.sleep(1.0)

                except Exception as e:
                    failed_items.append(f"{sub['student_id']} - {sub['name']}: {str(e)}")
                    failed_count += 1

            # 刷新数据
            self.load_data()

            # 显示结果
            message = f"批量回复完成！\n\n成功: {success_count} 项\n失败: {failed_count} 项"
            if failed_items:
                message += "\n\n失败详情:\n" + "\n".join(failed_items[:5])
                if len(failed_items) > 5:
                    message += f"\n... 还有 {len(failed_items)-5} 项"

            messagebox.showinfo("批量回复结果", message)

        except Exception as e:
            messagebox.showerror("错误", f"批量回复失败: {str(e)}")

        finally:
            # 恢复窗口
            self.configure(cursor="")
            self.status_label.configure(text="状态: 就绪")

    def show_delete_confirmation_dialog(self, submissions: List[dict]) -> bool:
        """显示批量删除确认对话框

        Args:
            submissions: 要删除的提交记录列表

        Returns:
            用户是否确认删除
        """
        # 创建对话框窗口
        dialog = ctk.CTkToplevel(self)
        dialog.title("确认删除")
        dialog.geometry("500x400")

        # 设置为模态对话框
        dialog.transient(self)
        dialog.grab_set()

        # 结果
        result = [False]

        # 标题
        title_label = ctk.CTkLabel(
            dialog,
            text=f"确认删除以下 {len(submissions)} 条记录？",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=20)

        # 警告文本
        warning_label = ctk.CTkLabel(
            dialog,
            text="⚠️ 此操作不可撤销！",
            font=("Arial", 14),
            text_color="red"
        )
        warning_label.pack(pady=5)

        # 记录列表（使用 Scrollable frame）
        from customtkinter import CTkScrollableFrame

        scrollable_frame = CTkScrollableFrame(dialog, height=200)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=10)

        for sub in submissions:
            item_label = ctk.CTkLabel(
                scrollable_frame,
                text=f"• {sub['student_id']} - {sub['name']} - {sub['assignment_name']}",
                anchor="w"
            )
            item_label.pack(fill="x", pady=2)

        # 按钮容器
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(fill="x", padx=20, pady=20)

        def on_confirm():
            result[0] = True
            dialog.destroy()

        def on_cancel():
            result[0] = False
            dialog.destroy()

        # 确认按钮
        confirm_btn = ctk.CTkButton(
            button_frame,
            text="确认删除",
            command=on_confirm,
            fg_color="red",
            hover_color="darkred"
        )
        confirm_btn.pack(side="left", expand=True, padx=5)

        # 取消按钮
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="取消",
            command=on_cancel
        )
        cancel_btn.pack(side="left", expand=True, padx=5)

        # 等待对话框关闭
        dialog.wait_window()
        return result[0]

    def on_batch_delete(self):
        """批量删除记录"""
        print("DEBUG: 批量删除按钮被点击")
        submissions = self.get_checked_submissions()
        print(f"DEBUG: 获取到 {len(submissions)} 条选中记录")

        if not submissions:
            messagebox.showwarning("提示", "请先选择要删除的记录")
            return

        # 显示确认对话框
        confirmed = self.show_delete_confirmation_dialog(submissions)
        if not confirmed:
            return

        # 禁用窗口
        self.configure(cursor="watch")
        self.update()
        self.status_label.configure(text="状态: 批量删除中...")

        success_count = 0
        failed_count = 0
        failed_items = []

        try:
            from storage.manager import storage_manager

            for idx, sub in enumerate(submissions):
                try:
                    self.status_label.configure(
                        text=f"状态: 正在删除第 {idx+1}/{len(submissions)} 项..."
                    )
                    self.update()

                    # 删除本地文件
                    if sub['local_path']:
                        storage_manager.delete_files(sub['local_path'])

                    # 从数据库删除（级联删除附件记录）
                    deleted = db.delete_submission(sub['id'])

                    if deleted:
                        success_count += 1
                    else:
                        failed_items.append(f"{sub['student_id']} - {sub['name']}: 数据库删除失败")
                        failed_count += 1

                except Exception as e:
                    # 即使文件删除失败，也尝试删除数据库记录以保持一致性
                    try:
                        db.delete_submission(sub['id'])
                        failed_items.append(f"{sub['student_id']} - {sub['name']}: 文件删除失败但数据库已删除")
                        failed_count += 1
                    except:
                        failed_items.append(f"{sub['student_id']} - {sub['name']}: 删除完全失败: {str(e)}")
                        failed_count += 1

            # 清除选择
            self.on_clear_selection()

            # 刷新数据
            self.load_data()

            # 显示结果
            message = f"批量删除完成！\n\n成功: {success_count} 项\n失败: {failed_count} 项"
            if failed_items:
                message += "\n\n失败详情:\n" + "\n".join(failed_items[:5])
                if len(failed_items) > 5:
                    message += f"\n... 还有 {len(failed_items)-5} 项"

            messagebox.showinfo("批量删除结果", message)

        except Exception as e:
            messagebox.showerror("错误", f"批量删除失败: {str(e)}")

        finally:
            # 恢复窗口
            self.configure(cursor="")
            self.status_label.configure(text="状态: 就绪")

    def on_export_excel(self):
        """导出Excel"""
        messagebox.showinfo("提示", "导出Excel功能待实现")

    def update_pagination(self):
        """更新分页显示"""
        self.page_label.configure(
            text=f"第 {self.current_page}/{self.total_pages} 页 (共 {self.total_count} 条)"
        )

    def on_prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.load_data(self.current_page - 1)

    def on_next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.load_data(self.current_page + 1)

    def start_background_monitoring(self):
        """启动后台INBOX监听"""
        import threading
        import asyncio

        def run_monitoring():
            from core.workflow import workflow
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(workflow.monitor_inbox(interval=60))
            except Exception as e:
                print(f"监听出错: {e}")
            finally:
                loop.close()

        monitor_thread = threading.Thread(target=run_monitoring, daemon=True)
        monitor_thread.start()
        self.status_label.configure(text="状态: 后台监听已启动")
