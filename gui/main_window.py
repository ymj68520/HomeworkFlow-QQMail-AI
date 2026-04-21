import customtkinter as ctk
from tkinter import ttk, messagebox
import asyncio
from datetime import datetime
from typing import List
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

        # 复选框图像
        self.checkbox_unchecked_img = None
        self.checkbox_checked_img = None
        self.create_checkbox_images()

        # 复选框状态字典 {item_id: bool}
        self.checked_items = {}

        # 创建UI
        self.setup_ui()

        # 加载数据
        self.load_data()

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
        columns = ["select", "学号", "姓名", "作业", "提交时间", "状态", "本地路径"]
        self.tree["columns"] = columns

        # 配置列
        self.tree.heading("select", text="✓")
        self.tree.heading("学号", text="学号")
        self.tree.heading("姓名", text="姓名")
        self.tree.heading("作业", text="作业")
        self.tree.heading("提交时间", text="提交时间")
        self.tree.heading("状态", text="状态")
        self.tree.heading("本地路径", text="本地路径")

        self.tree.column("select", width=40, anchor="center")
        self.tree.column("学号", width=120, anchor="center")
        self.tree.column("姓名", width=100, anchor="center")
        self.tree.column("作业", width=100, anchor="center")
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

    def load_data(self):
        """加载数据"""
        try:
            self.status_label.configure(text="状态: 加载中...")

            # 从数据库加载所有提交记录
            self.all_submissions = db.get_all_submissions()
            self.filtered_submissions = self.all_submissions.copy()

            # 更新下拉菜单
            self.update_dropdowns()

            # 刷新表格
            self.refresh_table()

            # 更新统计
            self.update_stats()

            self.status_label.configure(text="状态: 就绪")

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
            values = [
                checkbox_symbol,
                sub['student_id'],
                sub['name'],
                sub['assignment_name'],
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

    def on_batch_download(self):
        """批量下载"""
        messagebox.showinfo("提示", "批量下载功能待实现")

    def on_batch_reply(self):
        """批量回复"""
        messagebox.showinfo("提示", "批量回复功能待实现")

    def on_batch_delete(self):
        """批量删除"""
        messagebox.showinfo("提示", "批量删除功能待实现")

    def on_export_excel(self):
        """导出Excel"""
        messagebox.showinfo("提示", "导出Excel功能待实现")
