import sys
import threading
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QApplication, QMessageBox, QAbstractItemView, QPushButton
)
from PySide6.QtCore import Qt, QTimer, Signal

from gui.components.sidebar import Sidebar
from gui.components.data_table import DataTable
from gui.components.drawer import Drawer
from gui.components.collapsible_row import CollapsibleRow
from gui.components.batch_popup import BatchPopup
from gui.components.pagination import PaginationBar
from database.operations import db
from database.models import db_session
from mail.hybrid_data_loader import hybrid_data_loader
from mail.target_folder_loader import target_folder_loader
from mail.parser import mail_parser_inbox, mail_parser_target
from mail.smtp_client import smtp_client
from storage.manager import storage_manager
from core.workflow import workflow
from mail.connection_manager import connection_manager
from core.retry_handler import retry_handler
from gui.components.progress_dialog import ProgressDialog
from core.data_change_notifier import data_change_notifier, ChangeType
from core.filter_manager import filter_manager
from gui.components.filter_indicator import FilterIndicator
from core.filter_options_registry import filter_options_registry

class MainWindow(QMainWindow):
    """主窗口 - PySide6 实现"""
    
    # 定义跨线程更新信号
    update_drawer_signal = Signal(dict, str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("QQ邮箱作业收发系统")
        self.resize(1400, 900)

        # 状态映射（向后兼容）
        self.STATUS_MAP = {
            'pending': '未处理',
            'ai_error': '识别异常',
            'download_failed': '下载失败',
            'unreplied': '未回复',
            'completed': '已完成',
            'ignored': '已忽略'
        }

        # 新状态映射（独立状态系统）
        self.PROCESSING_STATUS_MAP = {
            'received': '已接收',
            'processing': '处理中',
            'extracted': '已提取',
            'downloading': '下载中',
            'downloaded': '已下载',
            'replying': '回复中',
            'replied': '已回复',
            'failed': '处理失败',
            'ignored': '已忽略'
        }

        # 数据
        self.all_submissions = []
        self.filtered_submissions = []
        
        # 分页状态
        self.current_page = 1
        self.per_page = 100
        self.total_pages = 1
        self.total_count = 0

        # 筛选管理器
        self.filter_manager = filter_manager

        # 初始化UI
        self.setup_ui()
        
        # 绑定信号
        self.setup_connections()

        # 启动连接管理器心跳检测
        try:
            connection_manager.start_heartbeat()
            print("[INIT] ConnectionManager heartbeat started")
        except Exception as e:
            print(f"[INIT] Failed to start heartbeat: {e}")
            import traceback
            traceback.print_exc()

        # 启动后台监听
        self.start_background_monitoring()

        # 延迟加载数据
        QTimer.singleShot(100, self.load_data)

    def setup_ui(self):
        """创建布局和组件"""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 左侧：侧边栏
        self.sidebar = Sidebar()
        self.main_layout.addWidget(self.sidebar)

        # 中央：数据表格
        self.table = DataTable()
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.set_headers(["学号", "姓名", "作业", "收件时间", "提交时间", "状态", "本地路径"], stretch_column=6)

        # 筛选模式指示器
        self.filter_indicator = FilterIndicator()
        self.filter_indicator.hide()  # 初始隐藏

        # 分页导航栏
        self.pagination = PaginationBar()

        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setObjectName("RefreshButton")
        self.refresh_btn.setFixedSize(80, 32)  # 与分页按钮高度一致
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        
        # 将刷新按钮添加到分页栏的最右侧
        self.pagination.layout().addWidget(self.refresh_btn)

        # 将表格和分页栏放入垂直布局
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(20, 20, 20, 20)
        center_layout.setSpacing(15)

        # 添加筛选指示器（初始隐藏）
        center_layout.addWidget(self.filter_indicator)

        center_layout.addWidget(self.table)
        center_layout.addWidget(self.pagination)

        self.main_layout.addWidget(center_container)

        # 右侧隐藏层：抽屉
        self.drawer = Drawer(self)
        self.drawer.hide()

        # 状态栏
        self.statusBar().showMessage("准备就绪")

    def setup_connections(self):
        """绑定信号与槽"""
        # 搜索防抖
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.on_search)
        
        self.sidebar.search_input.textChanged.connect(lambda: self.search_timer.start())

        # 过滤器
        self.sidebar.student_filter.currentIndexChanged.connect(self.on_filter_change)
        self.sidebar.assignment_filter.currentIndexChanged.connect(self.on_filter_change)
        self.sidebar.status_filter.currentIndexChanged.connect(self.on_filter_change)

        # 表格双击
        self.table.rowDoubleClicked.connect(self.on_row_double_clicked)

        # 子记录点击（新功能）
        if hasattr(self.table, 'childClicked'):
            self.table.childClicked.connect(self.on_child_record_clicked)

        # 表格选择变更
        if hasattr(self.table, 'selectionChanged'):
            self.table.selectionChanged.connect(self.update_status_info)

        # 分页导航
        self.pagination.pageChanged.connect(self.on_page_changed)

        # 跨线程 UI 更新信号连接
        self.update_drawer_signal.connect(self.drawer.set_details)
        
        # 侧边栏按钮
        self.sidebar.btn_download.clicked.connect(self.on_batch_download)
        self.sidebar.btn_reply.clicked.connect(self.on_batch_reply)
        self.sidebar.btn_delete.clicked.connect(self.on_batch_delete)
        self.sidebar.btn_export.clicked.connect(self.on_export_excel)

        # 筛选选项刷新按钮
        self.sidebar.refreshFiltersRequested.connect(self.on_refresh_filter_options)

        # New feature buttons
        self.sidebar.btn_smart_retry.clicked.connect(self.on_smart_retry)
        self.sidebar.btn_batch_reanalyze.clicked.connect(self.on_batch_reanalyze)

        # 刷新按钮
        self.refresh_btn.clicked.connect(self.on_refresh_clicked)

        # 筛选指示器
        self.filter_indicator.clearRequested.connect(self.on_clear_filters)

        # 表格右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)

        # 抽屉保存信号
        self.drawer.save_requested.connect(self.handle_drawer_save)

        # 数据变更通知 - 连接到智能刷新处理函数
        data_change_notifier.data_changed.connect(self.on_data_changed)

    def load_data(self, page: int = 1, force_refresh: bool = False):
        """
        加载数据 - 通过筛选管理器路由到对应的数据加载器

        Args:
            page: 页码
            force_refresh: 强制刷新，忽略缓存
        """
        try:
            print(f"[UI] load_data called: page={page}, force_refresh={force_refresh}, filter_mode={self.filter_manager.is_filtering}")
            self.statusBar().showMessage("正在加载数据...")

            # 通过筛选管理器路由到对应的数据加载器
            result = self.filter_manager.get_data(page, self.per_page, force_refresh)
            print(f"[UI] Got result: {len(result.get('submissions', []))} submissions, total={result.get('total', 0)}")

            # 处理分组格式数据（新格式）或平面数据（旧格式）
            submissions_data = result['submissions']

            # 自动合并新选项到 FilterOptionsRegistry
            new_options_count = filter_options_registry.merge_new_options(submissions_data)
            if new_options_count > 0:
                print(f"[UI] Auto-merged {new_options_count} new filter options")

            # 更新筛选选项新项指示器
            self.sidebar.set_filter_new_indicator(filter_options_registry.has_new_options())

            # 检查是否为分组格式（包含 primary_submission 或 assignment_name）
            if submissions_data and isinstance(submissions_data[0], dict) and \
               ('primary_submission' in submissions_data[0] or 'assignment_name' in submissions_data[0]):
                # 新格式：分组数据
                self.all_submissions = submissions_data
                # 为过滤和搜索创建平面视图
                self.filtered_submissions = self._flatten_grouped_data(submissions_data)
            else:
                # 旧格式：平面数据
                self.all_submissions = submissions_data
                self.filtered_submissions = self.all_submissions.copy()

            self.current_page = result['page']
            self.total_pages = result['total_pages']
            self.total_count = result['total']

            print(f"[UI] all_submissions={len(self.all_submissions)}, filtered={len(self.filtered_submissions)}")

            # 更新分页栏
            self.pagination.update_pagination(
                current_page=self.current_page,
                total_pages=self.total_pages,
                total_count=self.total_count
            )

            # 更新筛选模式UI指示器
            self._update_filter_mode_ui()

            # 更新UI - 优化：只在必要时更新下拉菜单
            self.update_dropdowns_if_needed()

            # 根据数据格式选择渲染方式
            if submissions_data and isinstance(submissions_data[0], dict) and \
               ('primary_submission' in submissions_data[0] or 'assignment_name' in submissions_data[0]):
                # 新格式：使用 CollapsibleRow 或 AssignmentGroup
                print("[UI] Using CollapsibleRow/AssignmentGroup rendering...")
                self.refresh_table_collapsible()
            else:
                # 旧格式：使用批量渲染
                print("[UI] Calling refresh_table_bulk...")
                self.refresh_table_bulk()
                print("[UI] refresh_table_bulk completed")

            self.update_stats()
            self.update_status_info()

        except Exception as e:
            import traceback
            print(f"[UI] ERROR in load_data: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"加载数据失败: {str(e)}\n\n详细错误:\n{traceback.format_exc()}")
            self.statusBar().showMessage("加载失败")
            # 使缓存失效
            hybrid_data_loader.invalidate_cache()

            # 尝试回退到旧版本
            print("[UI] Attempting fallback to legacy loader...")
            try:
                self.load_data_legacy(page)
            except Exception as e2:
                print(f"[UI] Legacy loader also failed: {e2}")
                traceback.print_exc()

    def _flatten_grouped_data(self, grouped_data: list) -> list:
        """
        将分组数据展平为平面列表，用于过滤和搜索

        Args:
            grouped_data: 分组数据列表，可能包含 assignment_name 或 primary_submission

        Returns:
            展平后的提交记录列表
        """
        flattened = []
        for item in grouped_data:
            if not isinstance(item, dict):
                continue
                
            # 处理作业分组 (assignment_name + records)
            if 'assignment_name' in item and 'records' in item:
                flattened.extend(self._flatten_grouped_data(item['records']))
                continue
                
            # 处理学生分组 (primary_submission + children)
            primary = item.get('primary_submission')
            if primary:
                flattened.append(primary)
            
            # 添加子记录
            for child in item.get('children', []):
                flattened.append(child)
                
            # 处理平面格式 (fallback)
            if not primary and 'student_id' in item:
                flattened.append(item)
                
        return flattened

    def load_data_legacy(self, page: int = 1):
        """
        加载数据 - 旧版本（作为回退）
        """
        try:
            self.statusBar().showMessage("正在加载数据...")

            result = target_folder_loader.get_from_target_folder(page, self.per_page)

            self.all_submissions = result['submissions']
            self.filtered_submissions = self.all_submissions.copy()
            self.current_page = result['page']
            self.total_pages = result['total_pages']
            self.total_count = result['total']

            # 更新分页栏
            self.pagination.update_pagination(
                current_page=self.current_page,
                total_pages=self.total_pages,
                total_count=self.total_count
            )

            # 更新UI
            self.update_dropdowns()
            self.refresh_table()
            self.update_stats()

            self.update_status_info()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载数据失败: {str(e)}")
            self.statusBar().showMessage("加载失败")

    def on_page_changed(self, page: int):
        """处理分页变更"""
        self.load_data(page)

    def update_status_info(self):
        """统一更新状态栏信息，显示加载数和选中数"""
        loaded_count = len(self.filtered_submissions)
        total_count = getattr(self, 'total_count', 0)
        selected_count = len(self.table.selectionModel().selectedRows())

        msg = f"已加载 {loaded_count} 条记录 (总计 {total_count})"
        if selected_count > 0:
            msg += f" | 已选择 {selected_count} 条记录"

        self.statusBar().showMessage(msg)

        # Enable/disable batch re-analyze button based on selection
        self.sidebar.btn_batch_reanalyze.setEnabled(selected_count > 0)

    def update_dropdowns(self):
        """
        更新下拉菜单选项 - 使用 FilterOptionsRegistry

        优化：从全局注册表获取选项，而不是仅从当前页面提取
        """
        self.sidebar.student_filter.blockSignals(True)
        self.sidebar.assignment_filter.blockSignals(True)
        self.sidebar.status_filter.blockSignals(True)

        # 获取当前选中的值，以便刷新后尝试恢复
        curr_student = self.sidebar.student_filter.currentText()
        curr_assignment = self.sidebar.assignment_filter.currentText()
        curr_status = self.sidebar.status_filter.currentText()

        # 从 FilterOptionsRegistry 获取选项
        student_options = filter_options_registry.get_student_options(include_all=True)
        assignment_options = filter_options_registry.get_assignment_options(include_all=True)
        status_options = filter_options_registry.get_status_options(include_all=True)

        # 更新学生下拉框
        self.sidebar.student_filter.clear()
        self.sidebar.student_filter.addItems(student_options)

        # 更新作业下拉框
        self.sidebar.assignment_filter.clear()
        self.sidebar.assignment_filter.addItems(assignment_options)

        # 更新状态下拉框
        self.sidebar.status_filter.clear()
        self.sidebar.status_filter.addItems(status_options)

        # 恢复选择
        idx = self.sidebar.student_filter.findText(curr_student)
        if idx >= 0: self.sidebar.student_filter.setCurrentIndex(idx)

        idx = self.sidebar.assignment_filter.findText(curr_assignment)
        if idx >= 0: self.sidebar.assignment_filter.setCurrentIndex(idx)

        idx = self.sidebar.status_filter.findText(curr_status)
        if idx >= 0: self.sidebar.status_filter.setCurrentIndex(idx)

        self.sidebar.student_filter.blockSignals(False)
        self.sidebar.assignment_filter.blockSignals(False)
        self.sidebar.status_filter.blockSignals(False)

    def update_dropdowns_if_needed(self):
        """
        智能更新下拉菜单 - 只在必要时更新

        优化: 避免每次翻页都重建下拉菜单
        现在基于 FilterOptionsRegistry 的变更状态来决定是否更新
        """
        # 检查是否需要更新（基于注册表的变更标记）
        if filter_options_registry.has_new_options():
            print("[UI] Filter options registry has new options, updating dropdowns")
            self.update_dropdowns()
        elif not hasattr(self, '_dropdowns_initialized'):
            # 首次初始化
            self.update_dropdowns()
            self._dropdowns_initialized = True

    def refresh_table_collapsible(self):
        """
        使用 CollapsibleRow 或 AssignmentGroup 刷新表格 - 支持分组数据
        """
        # 直接使用 DataTable 的 set_data，它已经能处理多种格式（平面、学生分组、作业分组）
        self.table.set_data(self.all_submissions)

    def refresh_table_bulk(self):
        """
        批量刷新表格 - 性能优化版本

        使用批量渲染，避免逐行添加导致的多次重绘
        """
        # 准备数据
        table_data = []
        for sub in self.filtered_submissions:
            # 兼容分组格式和平面格式
            sub_data = sub.get('primary_submission') if isinstance(sub, dict) and 'primary_submission' in sub else sub
            
            # 如果依然没有 student_id (可能是作业分组项)，则跳过或展平
            if not isinstance(sub_data, dict) or 'student_id' not in sub_data:
                continue

            status_code = sub_data.get('status', 'pending')
            status_text = self.STATUS_MAP.get(status_code, '未知')

            if sub_data.get('is_late'):
                status_text += " (逾期)"

            # 格式化收件时间
            received_time = sub_data.get('received_time')
            if received_time:
                if isinstance(received_time, datetime):
                    received_str = received_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    received_str = str(received_time)
            else:
                received_str = "未知"

            row_data = {
                "学号": sub_data.get('student_id', '-'),
                "姓名": sub_data.get('student_name') or sub_data.get('name', '-'),
                "作业": sub_data.get('assignment_name', '-'),
                "收件时间": received_str,
                "提交时间": self._format_time(sub_data.get('submission_time')),
                "状态": status_text,
                "本地路径": sub_data.get('local_path') or "未下载"
            }
            table_data.append(row_data)

        # 批量设置数据
        self.table.set_data_bulk(table_data)

    def smart_refresh(self, changed_uids: list = None):
        """
        智能刷新 - 只更新变化的部分

        Args:
            changed_uids: 发生变化的记录UID列表，None表示完全刷新
        """
        if changed_uids is None:
            # 完全刷新
            self.load_data(self.current_page)
        elif not changed_uids:
            # 仅更新统计信息
            self.update_stats()
            self.update_status_info()
        else:
            # 增量更新指定的记录
            # 如果使用 CollapsibleRow，可能需要重新渲染整个表格
            if self.filtered_submissions and isinstance(self.filtered_submissions[0], dict) and 'primary_submission' in self.filtered_submissions[0]:
                # 新格式：重新加载页面
                self.load_data(self.current_page)
            else:
                # 旧格式：增量更新
                self.update_records_incremental(changed_uids)

    def update_records_incremental(self, uids: list):
        """
        增量更新指定记录

        Args:
            uids: 要更新的记录UID列表
        """
        # 找到需要更新的行
        for uid in uids:
            for row_idx in range(self.table.rowCount()):
                # 通过学号和作业名匹配
                student_id = self.table.item(row_idx, 0).text()
                assignment_name = self.table.item(row_idx, 2).text()

                # 在all_submissions中查找对应记录
                for sub in self.all_submissions:
                    target_submission = None
                    target_student_id = ''
                    target_assignment_name = ''

                    if isinstance(sub, dict) and 'primary_submission' in sub:
                        # 新格式：分组数据
                        primary = sub['primary_submission']
                        target_student_id = str(primary.get('student_id', ''))
                        target_assignment_name = primary.get('assignment_name', '')
                        if primary.get('email_uid') == uid:
                            target_submission = primary
                    else:
                        # 旧格式：平面数据
                        target_student_id = str(sub.get('student_id', ''))
                        target_assignment_name = sub.get('assignment_name', '')
                        if sub.get('email_uid') == uid:
                            target_submission = sub

                    if (target_student_id == student_id and
                        target_assignment_name == assignment_name and
                        target_submission):

                        # 更新表格行
                        status_code = target_submission.get('status', 'pending')
                        status_text = self.STATUS_MAP.get(status_code, '未知')
                        if target_submission.get('is_late'):
                            status_text += " (逾期)"

                        self.table.update_rows_bulk({
                            row_idx: {
                                "状态": status_text,
                                "本地路径": target_submission.get('local_path') or "未下载"
                            }
                        })
                        break

        self.update_stats()
        self.update_status_info()

    def _get_student_groups(self, data: list) -> list:
        """
        从各种格式中提取学生分组列表 ({primary_submission, children})
        """
        groups = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if 'assignment_name' in item and 'records' in item:
                # 作业分组 -> 提取其中的学生分组
                groups.extend(item['records'])
            elif 'primary_submission' in item:
                # 已经是学生分组
                groups.append(item)
            elif 'student_id' in item:
                # 平面记录 -> 包装为学生分组
                groups.append({'primary_submission': item, 'children': []})
        return groups

    def refresh_table(self):
        """
        刷新表格数据

        根据数据格式自动选择渲染方式
        """
        self.table.clear_data()

        if not self.filtered_submissions:
            return

        # 检查是否为新格式（学生分组或作业分组）
        first = self.filtered_submissions[0]
        is_new_format = isinstance(first, dict) and ('primary_submission' in first or 'assignment_name' in first)

        if is_new_format:
            # 新格式：使用 DataTable.set_data 处理
            self.table.set_data(self.filtered_submissions)
        else:
            # 旧格式：手动填充传统表格
            self.refresh_table_bulk()

    def update_stats(self):
        """更新统计信息"""
        # 获取展平的数据进行统计
        flat_all = self._flatten_grouped_data(self.all_submissions)
        total = len(flat_all)

        # 计算已下载和已回复数量
        downloaded = 0
        replied = 0

        for sub in flat_all:
            if sub.get('status') in ['unreplied', 'completed']:
                downloaded += 1
            if sub.get('status') == 'completed':
                replied += 1

        self.sidebar.total_card.value_label.setText(str(total))
        self.sidebar.downloaded_card.value_label.setText(str(downloaded))

    def on_search(self):
        """搜索逻辑"""
        query = self.sidebar.search_input.text().strip()

        if not query:
            self.on_filter_change() # 重新应用当前过滤器
        else:
            # 统一转换为学生分组进行搜索
            student_groups = self._get_student_groups(self.all_submissions)
            self.filtered_submissions = []

            for group in student_groups:
                primary = group.get('primary_submission', {})
                children = group.get('children', [])
                all_submissions = [primary] + children

                # 在主记录和子记录中搜索
                found = False
                for sub in all_submissions:
                    if (query in str(sub.get('student_id', '')) or
                        query in str(sub.get('student_name', '')) or
                        query in str(sub.get('name', ''))):
                        found = True
                        break

                if found:
                    self.filtered_submissions.append(group)

            self.refresh_table()

        self.update_status_info()

    def on_filter_change(self):
        """
        筛选逻辑 - 使用筛选管理器处理跨页筛选
        """
        # 获取当前筛选值
        student_filter = self.sidebar.student_filter.currentText()
        assignment_filter = self.sidebar.assignment_filter.currentText()
        status_filter = self.sidebar.status_filter.currentText()

        print(f"[UI] Filter changed: student={student_filter}, assignment={assignment_filter}, status={status_filter}")

        # 更新筛选管理器
        mode_changed = self.filter_manager.update_filters(
            student=student_filter,
            assignment=assignment_filter,
            status=status_filter
        )

        print(f"[UI] Filter mode changed: {mode_changed}, is_filtering={self.filter_manager.is_filtering}")

        # 如果模式改变，使缓存失效
        if mode_changed:
            hybrid_data_loader.invalidate_cache()

        # 清空搜索框（筛选改变时重置搜索）
        self.sidebar.search_input.blockSignals(True)
        self.sidebar.search_input.clear()
        self.sidebar.search_input.blockSignals(False)

        # 重新加载数据（筛选模式下从数据库加载所有匹配记录）
        self.load_data(page=1, force_refresh=True)

        # 更新筛选模式指示器
        self._update_filter_indicator()
        self._update_filter_mode_restrictions()

        # 更新状态栏
        self._update_status_bar_for_filter_mode()

    def _filter_assignment_groups(self, assignment_groups: list, student_filter: str,
                                   assignment_filter: str, status_filter: str) -> list:
        """
        过滤作业分组格式的数据

        Args:
            assignment_groups: 作业分组列表 [{assignment_name, records}]
            student_filter: 学生筛选条件
            assignment_filter: 作业筛选条件
            status_filter: 状态筛选条件

        Returns:
            过滤后的作业分组列表
        """
        filtered = []

        for group in assignment_groups:
            if not isinstance(group, dict):
                continue

            assignment_name = group.get('assignment_name', '')
            records = group.get('records', [])

            # 作业筛选 - 如果作业不匹配，跳过整个作业组
            if assignment_filter != "全部作业" and assignment_name != assignment_filter:
                continue

            # 过滤该作业组内的学生组
            filtered_records = self._filter_student_groups(
                records, student_filter, "全部作业", status_filter
            )

            # 如果该作业组还有符合条件的学生组，保留该作业组
            if filtered_records:
                filtered.append({
                    'assignment_name': assignment_name,
                    'records': filtered_records
                })

        return filtered

    def _filter_student_groups(self, student_groups: list, student_filter: str,
                               assignment_filter: str, status_filter: str) -> list:
        """
        过滤学生分组格式的数据

        Args:
            student_groups: 学生分组列表 [{primary_submission, children}]
            student_filter: 学生筛选条件
            assignment_filter: 作业筛选条件
            status_filter: 状态筛选条件

        Returns:
            过滤后的学生分组列表
        """
        filtered = []

        for group in student_groups:
            if not isinstance(group, dict):
                continue

            primary = group.get('primary_submission', {})
            children = group.get('children', [])

            # 收集该学生组的所有提交记录（主记录 + 子记录）
            all_submissions = [primary] + children

            # 学生筛选
            if student_filter != "全部学生":
                student_id = student_filter.split(" - ")[0]
                if primary.get('student_id') != student_id:
                    continue

            # 作业筛选 - 检查所有提交记录
            if assignment_filter != "全部作业":
                has_matching_assignment = any(
                    sub.get('assignment_name') == assignment_filter
                    for sub in all_submissions
                )
                if not has_matching_assignment:
                    continue

            # 状态筛选 - 检查所有提交记录
            if status_filter == "正常":
                has_normal = any(
                    not sub.get('is_late', False) for sub in all_submissions
                )
                if not has_normal:
                    continue
            elif status_filter == "逾期":
                has_late = any(
                    sub.get('is_late', False) for sub in all_submissions
                )
                if not has_late:
                    continue
            elif status_filter != "全部状态":
                target_code = None
                for code, text in self.STATUS_MAP.items():
                    if text == status_filter:
                        target_code = code
                        break

                if target_code:
                    has_status = any(
                        sub.get('status') == target_code for sub in all_submissions
                    )
                    if not has_status:
                        continue

            # 该学生组符合筛选条件
            filtered.append(group)

        return filtered

    def on_row_double_clicked(self, row_data):
        """
        处理行双击：展示抽屉

        Args:
            row_data: 行数据字典，可能来自 CollapsibleRow 或传统表格
        """
        # 处理来自 CollapsibleRow 的数据（新格式）
        if 'student_id' in row_data:
            submission = row_data
            details = {
                "学号": submission.get('student_id', ''),
                "姓名": submission.get('student_name') or submission.get('name', ''),
                "作业": submission.get('assignment_name', ''),
                "收件时间": self._format_time(submission.get('received_time')),
                "提交时间": self._format_time(submission.get('submission_time')),
                "状态": self._format_status(submission),
                "本地路径": submission.get('local_path') or "未下载"
            }
        else:
            # 处理来自传统表格的数据（旧格式，保持向后兼容）
            student_id = str(row_data.get('学号'))
            assignment_name = row_data.get('作业')
            
            all_student_groups = self._get_student_groups(self.all_submissions)
            submission = None
            for group in all_student_groups:
                primary = group.get('primary_submission', {})
                if str(primary.get('student_id', '')) == student_id and \
                   primary.get('assignment_name', '') == assignment_name:
                    submission = primary
                    break

            if not submission:
                return

            details = {
                "学号": submission.get('student_id', ''),
                "姓名": submission.get('student_name') or submission.get('name', ''),
                "作业": submission.get('assignment_name', ''),
                "收件时间": row_data.get('收件时间'),
                "提交时间": row_data.get('提交时间'),
                "状态": row_data.get('状态'),
                "本地路径": submission.get('local_path') or "未下载"
            }

        # 检查是否有缓存的正文
        body = submission.get('body')
        if not body:
            # 尝试从数据库加载（如果之前保存过）
            if submission.get('id'):
                db_sub = db.get_submission_by_id(submission['id'])
                if db_sub and hasattr(db_sub, 'body') and db_sub.body:
                    body = db_sub.body
                    submission['body'] = body

        # 如果还是没有，异步拉取
        if not body:
            self.drawer.set_details(details, "正在从服务器拉取正文...")
            self.drawer.open_drawer()
            # 启动线程拉取
            threading.Thread(
                target=self.fetch_email_body,
                args=(submission, details),
                daemon=True
            ).start()
        else:
            self.drawer.set_details(details, body)
            self.drawer.open_drawer()

    def on_child_record_clicked(self, child_data: dict):
        """
        处理子记录点击事件

        Args:
            child_data: 子记录数据字典，包含 student_id, student_name, assignment_name 等
        """
        # 子记录数据格式与主记录类似，直接使用相同的处理逻辑
        details = {
            "学号": child_data.get('student_id', ''),
            "姓名": child_data.get('student_name', ''),
            "作业": child_data.get('assignment_name', ''),
            "收件时间": self._format_time(child_data.get('received_time')),
            "提交时间": self._format_time(child_data.get('submission_time')),
            "状态": self._format_status(child_data),
            "本地路径": child_data.get('local_path') or "未下载"
        }

        # 检查是否有缓存的正文
        body = child_data.get('body')
        if not body:
            # 尝试从数据库加载
            if child_data.get('id'):
                db_sub = db.get_submission_by_id(child_data['id'])
                if db_sub and hasattr(db_sub, 'body') and db_sub.body:
                    body = db_sub.body
                    child_data['body'] = body

        # 如果还是没有，异步拉取
        if not body:
            self.drawer.set_details(details, "正在从服务器拉取正文...")
            self.drawer.open_drawer()
            # 启动线程拉取
            threading.Thread(
                target=self.fetch_email_body,
                args=(child_data, details),
                daemon=True
            ).start()
        else:
            self.drawer.set_details(details, body)
            self.drawer.open_drawer()

    def _format_time(self, time_value) -> str:
        """
        格式化时间值为字符串

        Args:
            time_value: 时间值（datetime、字符串或None）

        Returns:
            格式化的时间字符串
        """
        if not time_value:
            return "未知"
        if isinstance(time_value, datetime):
            return time_value.strftime('%Y-%m-%d %H:%M:%S')
        return str(time_value)

    def _format_status(self, record: dict) -> str:
        """
        格式化状态文本 - 支持新旧状态系统

        Args:
            record: 记录数据字典

        Returns:
            格式化的状态文本
        """
        # 优先使用新的处理状态
        processing_status = record.get('processing_status')
        if processing_status:
            status_text = self.PROCESSING_STATUS_MAP.get(processing_status, '未知')
        else:
            # 向后兼容：使用旧状态字段
            status_code = record.get('status', 'pending')
            status_text = self.STATUS_MAP.get(status_code, '未知')

        if record.get('is_late'):
            status_text += " (逾期)"
        return status_text

    def fetch_email_body(self, submission, details):
        """后台拉取邮件正文"""
        try:
            from mail.parser import mail_parser_target
            from config.settings import settings
            
            if mail_parser_target.connect():
                email_uid = submission.get('email_uid')
                message_id = submission.get('message_id')
                email_data = None
                
                # 策略 1: 在目标文件夹按 UID 查找
                if email_uid:
                    mail_parser_target.imap.select_folder(settings.TARGET_FOLDER)
                    print(f"[FETCH] Strategy 1: Fetching UID {email_uid} in {settings.TARGET_FOLDER}")
                    email_data = mail_parser_target.parse_email(email_uid)
                
                # 策略 2: 如果失败且有 Message-ID，在目标文件夹按 Message-ID 查找
                if not email_data and message_id:
                    print(f"[FETCH] Strategy 2: Trying Message-ID {message_id} in {settings.TARGET_FOLDER}")
                    new_uid = mail_parser_target.imap.find_email_by_message_id(message_id, settings.TARGET_FOLDER)
                    if new_uid:
                        email_data = mail_parser_target.parse_email(new_uid)
                        if email_data:
                            print(f"[FETCH] Found and fixed UID: {email_uid} -> {new_uid}")
                            # 修复数据库中的 UID
                            if submission.get('id'):
                                db.update_submission_field(submission['id'], 'email_uid', new_uid)
                                submission['email_uid'] = new_uid

                # 策略 3: 如果还是失败，在 INBOX 中查找 (可能邮件还没被移动)
                if not email_data:
                    print(f"[FETCH] Strategy 3: Searching in INBOX")
                    mail_parser_target.imap.select_folder('INBOX')
                    if email_uid:
                        email_data = mail_parser_target.parse_email(email_uid)
                    
                    if not email_data and message_id:
                        new_uid = mail_parser_target.imap.find_email_by_message_id(message_id, 'INBOX')
                        if new_uid:
                            email_data = mail_parser_target.parse_email(new_uid)
                            if email_data:
                                print(f"[FETCH] Found in INBOX, UID: {new_uid}")

                if email_data and 'email_body' in email_data:
                    body_dict = email_data['email_body']
                    body = body_dict.get('plain_text') or body_dict.get('html_markdown') or "邮件内容为空"
                    
                    # 更新缓存
                    submission['body'] = body
                    
                    # 如果数据库支持，也可以存入数据库
                    if submission.get('id'):
                        try:
                            db.update_submission_field(submission['id'], 'body', body)
                        except: pass
                    
                    # 发送信号回到主线程更新 UI
                    self.update_drawer_signal.emit(details, body)
                else:
                    self.update_drawer_signal.emit(details, "无法从服务器获取邮件正文 (UID/Message-ID 不匹配)")

                mail_parser_target.disconnect()
        except Exception as e:
            print(f"Error fetching email body: {e}")
            self.update_drawer_signal.emit(details, f"拉取正文失败: {str(e)}")

    def on_context_menu(self, pos):
        """显示右键菜单以进行批量修改"""
        checked_rows = self.table.get_checked_rows()
        if not checked_rows:
            return

        submissions = [row.get_submission_data() for row in checked_rows]

        if submissions:
            popup = BatchPopup(self, submissions, on_update=lambda f, v: self.handle_batch_update(submissions, f, v))
            popup.exec()

    def handle_batch_update(self, submissions: List[Dict], field_id: str, new_value: Any):
        """批量更新业务逻辑 - 性能优化版本"""
        # 状态转换
        if field_id == 'status':
            for code, text in self.STATUS_MAP.items():
                if text == new_value:
                    new_value = code
                    break

        try:
            submission_ids = [s.get('id') for s in submissions if s.get('id')]

            if not submission_ids:
                QMessageBox.warning(self, "失败", "没有有效的记录ID")
                return

            # 使用批量更新
            if field_id == 'status':
                success_count = db.update_submissions_status_bulk(submission_ids, new_value)
            else:
                # 其他字段逐个更新（因为可能涉及关联表）
                success_count = 0
                for sub_id in submission_ids:
                    sub = next((s for s in submissions if s.get('id') == sub_id), None)
                    if sub and db.update_submission_field(
                        sub_id, field_id, new_value,
                        email_uid=sub.get('email_uid'),
                        message_id=sub.get('message_id')
                    ):
                        success_count += 1

            if success_count > 0:
                # 使用增量更新
                changed_uids = [s.get('email_uid') for s in submissions if s.get('id') in submission_ids[:success_count]]
                self.smart_refresh(changed_uids)
                QMessageBox.information(self, "成功", f"已更新 {success_count}/{len(submissions)} 条记录")
            else:
                QMessageBox.warning(self, "失败", "更新失败: 未知错误")
        finally:
            db_session.remove()

    def handle_drawer_save(self, updated_data: dict):
        """处理抽屉发起的单条记录更新"""
        # 1. 获取定位信息
        old_student_id = str(self.drawer.current_details.get("学号"))
        old_assignment_name = self.drawer.current_details.get("作业")
        
        # 2. 查找原始记录
        submission = None
        all_student_groups = self._get_student_groups(self.all_submissions)
        for group in all_student_groups:
            primary = group.get('primary_submission', {})
            if str(primary.get('student_id', '')) == old_student_id and \
               primary.get('assignment_name', '') == old_assignment_name:
                submission = primary
                break
        
        if not submission or not submission.get('id'):
            QMessageBox.warning(self, "失败", "无法定位记录ID")
            return

        # 3. 字段映射 (UI中文 -> 数据库英文字段)
        new_status_text = updated_data.get("状态")
        new_status_code = submission.get('status')
        if new_status_text:
            for code, text in self.STATUS_MAP.items():
                if text == new_status_text:
                    new_status_code = code
                    break

        try:
            # 4. 执行完整更新
            success = db.update_submission_full(
                submission_id=submission['id'],
                student_id=updated_data.get("学号", submission.get('student_id')),
                name=updated_data.get("姓名", submission.get('student_name')),
                assignment_name=updated_data.get("作业", submission.get('assignment_name')),
                status=new_status_code,
                email=submission.get('email'),
                email_uid=submission.get('email_uid'),
                email_subject=submission.get('email_subject'),
                sender_email=submission.get('sender_email'),
                submission_time=submission.get('submission_time')
            )

            if success:
                # 5. 退出编辑模式并刷新
                self.drawer.is_edit_mode = False
                self.drawer._update_edit_btn_style()
                self.load_data(self.current_page, force_refresh=True)
                QMessageBox.information(self, "成功", "记录已成功更新")
            else:
                QMessageBox.warning(self, "失败", "数据库更新失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"更新出错: {str(e)}")
        finally:
            db_session.remove()

    def on_batch_download(self):
        """批量下载附件 - 鲁棒版本 (支持跨文件夹查找)"""
        submissions = self.get_selected_submissions()
        if not submissions:
            QMessageBox.information(self, "提示", "请先选择要下载的记录")
            return

        if QMessageBox.question(self, "确认", f"确定要下载 {len(submissions)} 条附件吗？") != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        success_count = 0
        from config.settings import settings
        
        try:
            # 预先连接两个解析器
            mail_parser_inbox.connect()
            mail_parser_target.connect()

            for idx, sub in enumerate(submissions):
                self.statusBar().showMessage(f"正在处理 ({idx+1}/{len(submissions)}): {sub['name']}")
                QApplication.processEvents()
                
                email_uid = sub.get('email_uid')
                message_id = sub.get('message_id')
                email_data = None
                
                # --- 策略 1: 在 INBOX 中查找 (针对新邮件) ---
                if email_uid:
                    print(f"[DOWNLOAD] Strategy 1: Fetching UID {email_uid} in INBOX")
                    # 确保选择了 INBOX
                    mail_parser_inbox.imap.select_folder('INBOX')
                    email_data = mail_parser_inbox.parse_email(email_uid)
                
                # --- 策略 2: 在 TARGET_FOLDER 中查找 (针对已处理邮件) ---
                if not email_data and email_uid:
                    print(f"[DOWNLOAD] Strategy 2: Fetching UID {email_uid} in {settings.TARGET_FOLDER}")
                    if mail_parser_target.imap.select_folder(settings.TARGET_FOLDER):
                        email_data = mail_parser_target.parse_email(email_uid)

                # --- 策略 3: 使用 Message-ID 跨文件夹查找 ---
                if not email_data and message_id:
                    print(f"[DOWNLOAD] Strategy 3: Searching Message-ID {message_id}")
                    # 先看目标文件夹
                    if mail_parser_target.imap.select_folder(settings.TARGET_FOLDER):
                        new_uid = mail_parser_target.imap.find_email_by_message_id(message_id, settings.TARGET_FOLDER)
                        if new_uid:
                            email_data = mail_parser_target.parse_email(new_uid)
                            if email_data:
                                print(f"[DOWNLOAD] Found by Message-ID in {settings.TARGET_FOLDER}, updating UID: {email_uid} -> {new_uid}")
                                if sub.get('id'):
                                    db.update_submission_field(sub['id'], 'email_uid', new_uid)
                                    sub['email_uid'] = new_uid

                    # 再看收件箱
                    if not email_data:
                        new_uid = mail_parser_inbox.imap.find_email_by_message_id(message_id, 'INBOX')
                        if new_uid:
                            email_data = mail_parser_inbox.parse_email(new_uid)
                            if email_data:
                                print(f"[DOWNLOAD] Found by Message-ID in INBOX, updating UID: {email_uid} -> {new_uid}")
                                if sub.get('id'):
                                    db.update_submission_field(sub['id'], 'email_uid', new_uid)
                                    sub['email_uid'] = new_uid

                # --- 处理下载 ---
                if email_data and email_data.get('attachments'):
                    try:
                        local_path = storage_manager.store_submission(
                            assignment_name=sub['assignment_name'],
                            student_id=sub['student_id'],
                            name=sub['name'],
                            attachments=email_data['attachments']
                        )

                        if local_path:
                            if sub.get('id'):
                                db.update_submission_local_path(sub['id'], local_path)
                                new_status = 'completed' if sub.get('is_replied') else 'unreplied'
                                db.update_submission_status(sub['id'], new_status)
                            
                            sub['local_path'] = local_path
                            success_count += 1
                    except Exception as e:
                        print(f"[DOWNLOAD] Error storing attachments: {e}")
                else:
                    print(f"[DOWNLOAD] Failed to find email or attachments for {sub['name']}")

            self.load_data(self.current_page)
            QMessageBox.information(self, "完成", f"下载完成！成功: {success_count}/{len(submissions)}")
            
            mail_parser_inbox.disconnect()
            mail_parser_target.disconnect()
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("准备就绪")

    def on_batch_reply(self):
        """批量回复邮件 - 性能优化版本"""
        submissions = self.get_selected_submissions()
        unreplied = [s for s in submissions if s.get('status') == 'unreplied']
        if not unreplied:
            QMessageBox.information(self, "提示", "没有符合条件的（已下载且未回复）记录")
            return

        if QMessageBox.question(self, "确认", f"确定要回复 {len(unreplied)} 条记录吗？") != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        success_ids = []
        failed_count = 0

        # 批量发送邮件
        for s in unreplied:
            self.statusBar().showMessage(f"正在回复 ({len(success_ids)+1}/{len(unreplied)}): {s['name']}")
            QApplication.processEvents()

            if smtp_client.send_reply(s['email'], s['name'], s['assignment_name']):
                success_ids.append(s['id'])
            else:
                failed_count += 1

        # 批量更新数据库
        if success_ids:
            db.update_submissions_status_bulk(success_ids, 'completed')
            # 使用增量更新而不是完全重新加载
            changed_uids = [s.get('email_uid') for s in unreplied if s['id'] in success_ids]
            self.smart_refresh(changed_uids)

        QMessageBox.information(self, "完成", f"回复完成！成功: {len(success_ids)}/{len(unreplied)}")
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage("准备就绪")

    def on_batch_delete(self):
        """批量删除记录 - 性能优化版本"""
        submissions = self.get_selected_submissions()
        if not submissions: return

        if QMessageBox.question(self, "确认", f"确定删除这 {len(submissions)} 条记录吗？\n邮件将移回收件箱。") != QMessageBox.Yes:
            return

        # 收集ID
        submission_ids = [s['id'] for s in submissions]
        uids = [s.get('email_uid') for s in submissions]

        # 批量删除数据库记录
        success_count = db.delete_submissions_bulk(submission_ids)

        # 从缓存中移除
        for uid in uids:
            hybrid_data_loader.remove_record(uid)

        # 使用增量更新
        self.smart_refresh([])  # 仅更新统计
        self.refresh_table_bulk()  # 重新渲染当前页（因为记录减少）

        QMessageBox.information(self, "完成", f"删除完成！成功: {success_count}/{len(submissions)}")

    def on_export_excel(self):
        """导出 Excel 占位符"""
        QMessageBox.information(self, "提示", "导出 Excel 功能待实现")

    def on_smart_retry(self):
        """智能重试：重新处理当前页面的所有异常条目"""
        # Find abnormal entries on current page
        abnormal_entries = [
            s for s in self.filtered_submissions
            if s.get('status') in retry_handler.ABNORMAL_STATUSES
        ]

        if not abnormal_entries:
            QMessageBox.information(
                self,
                "提示",
                "当前页面没有需要重试的异常条目。\n\n"
                f"异常状态包括: {', '.join(['识别异常', '下载失败', '未处理'])}"
            )
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "确认智能重试",
            f"找到 {len(abnormal_entries)} 条异常记录。\n\n"
            "将对这些记录重新运行完整的分析流程（从IMAP重新拉取、AI识别、存储等）。\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Show progress dialog with initial progress
        progress = ProgressDialog(self, title="智能重试中...", cancelable=False)
        # Initialize with 0 progress to show determinate state
        progress.set_progress(0, len(abnormal_entries))
        progress.set_status("准备处理异常条目...")
        progress.show()

        # Run in background thread
        def run_smart_retry():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                def make_progress_callback():
                    """Factory function to capture closure variables correctly"""
                    def _callback(curr, total, msg):
                        # Capture values at the time of callback creation
                        def _update():
                            progress.set_progress(curr, total)
                            progress.set_detail(msg)
                        QTimer.singleShot(0, _update)
                    return _callback

                result = loop.run_until_complete(
                    retry_handler.smart_retry_page(
                        self.filtered_submissions,
                        progress_callback=make_progress_callback()
                    )
                )
                # Update UI on main thread
                QTimer.singleShot(0, lambda: show_retry_result(result))
            finally:
                loop.close()

        def show_retry_result(result):
            # Update progress dialog to show completion
            success = result['failed'] == 0
            progress.set_complete(success=success)

            # Build detailed summary
            summary_parts = [
                f"总计: {result['total']} 条",
                f"成功: {result['success']} 条",
                f"失败: {result['failed']} 条",
                f"跳过: {result['skipped']} 条"
            ]

            # Add error details if any
            if result.get('details'):
                failed_details = [d for d in result['details'] if d.get('status') == 'failed']
                if failed_details:
                    summary_parts.append(f"\n\n失败详情:")
                    for detail in failed_details[:5]:  # Show first 5 failures
                        reason = detail.get('reason', '未知错误')[:30]
                        summary_parts.append(f"  - {detail.get('student_id', '?')}: {reason}")
                    if len(failed_details) > 5:
                        summary_parts.append(f"  ... 还有 {len(failed_details) - 5} 条失败记录")

            if result.get('error'):
                summary_parts.append(f"\n\n系统错误: {result['error']}")

            summary = "智能重试完成！\n\n" + "\n".join(summary_parts)

            # Close progress dialog and show result
            progress.accept()
            QMessageBox.information(self, "智能重试结果", summary)

            # Refresh current page to show updated statuses
            self.load_data(self.current_page, force_refresh=True)

        # Start background thread
        thread = threading.Thread(target=run_smart_retry, daemon=True)
        thread.start()

    def on_batch_reanalyze(self):
        """批量AI重析：重新分析选中的条目"""
        submissions = self.get_selected_submissions()
        if not submissions:
            QMessageBox.information(self, "提示", "请先选择要重新分析的记录")
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "确认批量AI重析",
            f"已选择 {len(submissions)} 条记录。\n\n"
            "将从IMAP服务器重新拉取邮件内容并使用AI重新分析。\n"
            "这将更新数据库中的学号、姓名、作业名称等信息。\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Show progress dialog with initial progress
        progress = ProgressDialog(self, title="批量AI重析中...", cancelable=False)
        # Initialize with 0 progress to show determinate state
        progress.set_progress(0, len(submissions))
        progress.set_status("准备重新分析...")
        progress.show()

        # Run in background thread
        def run_batch_reanalyze():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                def make_progress_callback():
                    """Factory function to capture closure variables correctly"""
                    def _callback(curr, total, msg):
                        # Capture values at the time of callback creation
                        def _update():
                            progress.set_progress(curr, total)
                            progress.set_detail(msg)
                        QTimer.singleShot(0, _update)
                    return _callback

                result = loop.run_until_complete(
                    retry_handler.batch_reanalyze(
                        submissions,
                        progress_callback=make_progress_callback()
                    )
                )
                # Update UI on main thread
                QTimer.singleShot(0, lambda: show_reanalyze_result(result))
            finally:
                loop.close()

        def show_reanalyze_result(result):
            # Update progress dialog to show completion
            success = result['failed'] == 0
            progress.set_complete(success=success)

            # Build detailed summary
            summary_parts = [
                f"总计: {result['total']} 条",
                f"成功: {result['success']} 条",
                f"失败: {result['failed']} 条"
            ]

            # Add error details if any
            if result.get('details'):
                failed_details = [d for d in result['details'] if d.get('status') == 'failed']
                if failed_details:
                    summary_parts.append(f"\n\n失败详情:")
                    for detail in failed_details[:5]:  # Show first 5 failures
                        reason = detail.get('reason', '未知错误')[:30]
                        summary_parts.append(f"  - {detail.get('student_id', '?')}: {reason}")
                    if len(failed_details) > 5:
                        summary_parts.append(f"  ... 还有 {len(failed_details) - 5} 条失败记录")

            if result.get('error'):
                summary_parts.append(f"\n\n系统错误: {result['error']}")

            summary = "批量AI重析完成！\n\n" + "\n".join(summary_parts)

            # Close progress dialog and show result
            progress.accept()
            QMessageBox.information(self, "批量AI重析结果", summary)

            # Refresh current page to show updated data
            self.load_data(self.current_page, force_refresh=True)

        # Start background thread
        thread = threading.Thread(target=run_batch_reanalyze, daemon=True)
        thread.start()

    def on_refresh_clicked(self):
        """处理刷新按钮点击事件 - 重置筛选条件并重新加载数据"""
        try:
            # 显示加载状态
            self.statusBar().showMessage("正在刷新...")
            QApplication.processEvents()

            # 重置筛选条件到默认值
            self.sidebar.student_filter.blockSignals(True)
            self.sidebar.assignment_filter.blockSignals(True)
            self.sidebar.status_filter.blockSignals(True)

            self.sidebar.student_filter.setCurrentIndex(0)
            self.sidebar.assignment_filter.setCurrentIndex(0)
            self.sidebar.status_filter.setCurrentIndex(0)

            self.sidebar.student_filter.blockSignals(False)
            self.sidebar.assignment_filter.blockSignals(False)
            self.sidebar.status_filter.blockSignals(False)

            # 清空搜索框
            self.sidebar.search_input.blockSignals(True)
            self.sidebar.search_input.clear()
            self.sidebar.search_input.blockSignals(False)

            # 清除缓存并重新加载数据
            hybrid_data_loader.invalidate_cache()
            self.load_data(page=1, force_refresh=True)

            # 显示完成状态
            self.statusBar().showMessage("刷新完成")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"刷新失败: {str(e)}")
            self.statusBar().showMessage("刷新失败")

    def on_data_changed(self, change_type: str, details: dict):
        """
        处理数据变更通知 - 智能刷新策略

        根据变更类型选择最合适的刷新方式，避免不必要的全量刷新。

        Args:
            change_type: 变更类型 (来自 ChangeType 枚举)
            details: 变更详情
        """
        try:
            print(f"[DataChange] Received: {change_type}, details: {details}")

            # 处理不同的变更类型
            if change_type == ChangeType.RECORD_UPDATED.value:
                # 单条记录更新 - 智能增量更新
                uid = details.get('uid')
                submission_id = details.get('submission_id')
                changes = details.get('changes', {})

                if uid:
                    # 更新缓存中的记录
                    hybrid_data_loader.update_single_record(uid, changes)

                    # 检查是否在当前页面，如果是则增量更新
                    self._update_record_in_table(uid, submission_id, changes)

                elif submission_id:
                    # 没有 UID 的情况，通过 ID 查找
                    self._update_record_by_id(submission_id, changes)

            elif change_type == ChangeType.RECORD_CREATED.value:
                # 新记录创建 - 需要重新加载（因为可能有新记录）
                print("[DataChange] New record created, refreshing...")
                hybrid_data_loader.invalidate_cache()
                self.load_data(self.current_page, force_refresh=True)

            elif change_type == ChangeType.RECORD_DELETED.value:
                # 记录删除 - 从表格移除并更新统计
                submission_id = details.get('submission_id')
                uid = details.get('uid')

                if uid:
                    hybrid_data_loader.remove_record(uid)

                # 刷新当前页
                self.load_data(self.current_page, force_refresh=False)

            elif change_type == ChangeType.BATCH_UPDATED.value:
                # 批量更新 - 刷新当前页
                submission_ids = details.get('submission_ids', [])
                count = details.get('count', 0)

                print(f"[DataChange] Batch updated {count} records")

                # 使缓存失效
                hybrid_data_loader.invalidate_cache()
                # 刷新当前页
                self.load_data(self.current_page, force_refresh=True)

            elif change_type == ChangeType.BATCH_DELETED.value:
                # 批量删除 - 刷新当前页
                submission_ids = details.get('submission_ids', [])
                count = details.get('count', 0)

                print(f"[DataChange] Batch deleted {count} records")

                # 使缓存失效
                hybrid_data_loader.invalidate_cache()
                # 刷新当前页
                self.load_data(self.current_page, force_refresh=True)

            elif change_type == ChangeType.PAGE_REFRESH.value:
                # 页面刷新请求
                page = details.get('page')
                if page is None:
                    page = self.current_page

                print(f"[DataChange] Page refresh requested for page {page}")
                hybrid_data_loader.invalidate_cache()
                self.load_data(page, force_refresh=True)

            elif change_type == ChangeType.NEW_EMAILS_PROCESSED.value:
                # 新邮件处理完成 - 刷新第一页
                count = details.get('count', 0)

                print(f"[DataChange] New emails processed: {count}")

                # 显示通知
                self.statusBar().showMessage(f"检测到 {count} 封新邮件并已处理完成")
                # 刷新第一页
                hybrid_data_loader.invalidate_cache()
                self.load_data(page=1, force_refresh=True)

            elif change_type == ChangeType.FULL_REFRESH.value:
                # 全量刷新请求
                reason = details.get('reason', '')
                print(f"[DataChange] Full refresh requested: {reason}")

                hybrid_data_loader.invalidate_cache()
                self.load_data(page=1, force_refresh=True)

        except Exception as e:
            import traceback
            print(f"[DataChange] Error handling change: {e}")
            traceback.print_exc()

    def _update_record_in_table(self, uid: str, submission_id: int, changes: dict):
        """
        在表格中增量更新指定记录

        Args:
            uid: 邮件 UID
            submission_id: 记录 ID
            changes: 变更的字段
        """
        try:
            # 检查当前页面是否包含此记录
            found = False

            # 在分组数据中查找
            for group in self.all_submissions:
                if not isinstance(group, dict):
                    continue

                # 处理作业分组
                if 'assignment_name' in group and 'records' in group:
                    for student_group in group['records']:
                        primary = student_group.get('primary_submission', {})
                        if primary.get('email_uid') == uid or primary.get('id') == submission_id:
                            # 更新主记录
                            primary.update(changes)
                            # 更新子记录中的相同字段
                            for child in student_group.get('children', []):
                                for key in changes:
                                    if key in child:
                                        child[key] = changes[key]
                            found = True
                            break

                # 处理学生分组
                elif 'primary_submission' in group:
                    primary = group['primary_submission']
                    if primary.get('email_uid') == uid or primary.get('id') == submission_id:
                        primary.update(changes)
                        found = True
                        break

                # 处理平面数据
                elif group.get('email_uid') == uid or group.get('id') == submission_id:
                    group.update(changes)
                    found = True
                    break

                if found:
                    break

            if found:
                # 记录在当前页，刷新表格显示
                print(f"[DataChange] Updated record in current page: uid={uid}")
                self.refresh_table_collapsible()
                self.update_stats()
                self.update_status_info()
            else:
                # 记录不在当前页，检查是否需要更新统计
                print(f"[DataChange] Record not in current page: uid={uid}")
                self.update_stats()

        except Exception as e:
            print(f"[DataChange] Error updating record in table: {e}")
            import traceback
            traceback.print_exc()

    def _update_record_by_id(self, submission_id: int, changes: dict):
        """
        通过记录 ID 更新表格中的记录

        Args:
            submission_id: 记录 ID
            changes: 变更的字段
        """
        try:
            for group in self.all_submissions:
                if not isinstance(group, dict):
                    continue

                # 处理作业分组
                if 'assignment_name' in group and 'records' in group:
                    for student_group in group['records']:
                        primary = student_group.get('primary_submission', {})
                        if primary.get('id') == submission_id:
                            primary.update(changes)
                            self.refresh_table_collapsible()
                            self.update_stats()
                            self.update_status_info()
                            return

                # 处理学生分组
                elif 'primary_submission' in group:
                    primary = group['primary_submission']
                    if primary.get('id') == submission_id:
                        primary.update(changes)
                        self.refresh_table_collapsible()
                        self.update_stats()
                        self.update_status_info()
                        return

                # 处理平面数据
                elif group.get('id') == submission_id:
                    group.update(changes)
                    self.refresh_table_collapsible()
                    self.update_stats()
                    self.update_status_info()
                    return

        except Exception as e:
            print(f"[DataChange] Error updating record by ID: {e}")
            import traceback
            traceback.print_exc()

    def get_selected_submissions(self) -> List[dict]:
        """
        从表格选择中获取数据对象

        支持各种数据格式
        """
        result = []
        for row in self.table.get_checked_rows():
            result.append(row.get_submission_data())
        return result

    def start_background_monitoring(self):
        """后台异步监控邮件"""
        def run_monitoring():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(workflow.monitor_inbox(interval=60))
            except:
                pass
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_monitoring, daemon=True)
        thread.start()

    def resizeEvent(self, event):
        """处理窗口大小变化以同步抽屉高度"""
        super().resizeEvent(event)
        if self.drawer.isVisible():
            self.drawer.setFixedHeight(self.height())
            self.drawer.move(self.width() - self.drawer.width(), 0)

    # ==================== 筛选模式相关方法 ====================

    def on_clear_filters(self):
        """清除所有筛选条件，恢复到正常分页模式"""
        # 如果当前不在筛选模式，无需清除
        if not self.filter_manager.is_filtering:
            QMessageBox.information(self, "提示", "当前没有激活的筛选条件")
            return

        # 显示确认对话框
        filter_summary = self.filter_manager.get_filter_summary()
        reply = QMessageBox.question(
            self,
            "确认清除筛选",
            f"当前激活的筛选条件：\n\n{filter_summary}\n\n"
            "清除筛选后将返回正常分页模式，显示所有邮件记录。\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 显示进度对话框
        progress = ProgressDialog(self, title="清除筛选中...", cancelable=False)
        progress.set_progress(0, 100)
        progress.set_status("正在清除筛选条件...")
        progress.show()

        def do_clear_filters():
            """在后台线程中执行清除筛选操作"""
            try:
                # 步骤 1: 重置侧边栏筛选控件
                QTimer.singleShot(0, lambda: progress.set_progress(20, 100))
                QTimer.singleShot(0, lambda: progress.set_detail("重置筛选控件..."))
                QApplication.processEvents()

                self.sidebar.student_filter.blockSignals(True)
                self.sidebar.assignment_filter.blockSignals(True)
                self.sidebar.status_filter.blockSignals(True)

                self.sidebar.student_filter.setCurrentIndex(0)
                self.sidebar.assignment_filter.setCurrentIndex(0)
                self.sidebar.status_filter.setCurrentIndex(0)

                self.sidebar.student_filter.blockSignals(False)
                self.sidebar.assignment_filter.blockSignals(False)
                self.sidebar.status_filter.blockSignals(False)

                # 步骤 2: 清空搜索框
                QTimer.singleShot(0, lambda: progress.set_progress(40, 100))
                QTimer.singleShot(0, lambda: progress.set_detail("清空搜索框..."))
                QApplication.processEvents()

                self.sidebar.search_input.blockSignals(True)
                self.sidebar.search_input.clear()
                self.sidebar.search_input.blockSignals(False)

                # 步骤 3: 清除筛选管理器状态
                QTimer.singleShot(0, lambda: progress.set_progress(60, 100))
                QTimer.singleShot(0, lambda: progress.set_detail("重置筛选状态..."))
                QApplication.processEvents()

                mode_changed = self.filter_manager.clear_filters()
                print(f"[UI] Filters cleared, mode_changed={mode_changed}, is_filtering={self.filter_manager.is_filtering}")

                # 步骤 4: 使缓存失效
                if mode_changed:
                    QTimer.singleShot(0, lambda: progress.set_progress(80, 100))
                    QTimer.singleShot(0, lambda: progress.set_detail("使缓存失效..."))
                    QApplication.processEvents()
                    hybrid_data_loader.invalidate_cache()

                # 步骤 5: 重新加载数据
                QTimer.singleShot(0, lambda: progress.set_progress(90, 100))
                QTimer.singleShot(0, lambda: progress.set_detail("重新加载数据..."))
                QApplication.processEvents()

                self.load_data(page=1, force_refresh=True)

                # 步骤 6: 更新UI
                QTimer.singleShot(0, lambda: progress.set_progress(100, 100))
                QTimer.singleShot(0, lambda: progress.set_detail("完成"))
                QApplication.processEvents()

                self._update_filter_indicator()
                self._update_filter_mode_restrictions()
                self._update_status_bar_for_filter_mode()

                # 完成后关闭进度对话框并显示成功消息
                QTimer.singleShot(0, lambda: show_success_message())

            except Exception as e:
                import traceback
                print(f"[UI] Error clearing filters: {e}")
                traceback.print_exc()
                QTimer.singleShot(0, lambda: show_error_message(str(e)))

        def show_success_message():
            """显示成功消息"""
            progress.set_complete(success=True)
            progress.accept()
            QMessageBox.information(self, "完成", "筛选条件已清除，返回正常分页模式")

        def show_error_message(error_msg):
            """显示错误消息"""
            progress.set_complete(success=False)
            progress.accept()
            QMessageBox.critical(self, "错误", f"清除筛选失败: {error_msg}")

        # 在后台线程中执行
        thread = threading.Thread(target=do_clear_filters, daemon=True)
        thread.start()

    def _update_filter_indicator(self):
        """更新筛选指示器组件"""
        if self.filter_manager.is_filtering:
            self.filter_indicator.set_filters(self.filter_manager.current_filters)
        else:
            self.filter_indicator.clear_filters()

    def _update_filter_mode_ui(self):
        """更新筛选模式相关的UI元素"""
        if self.filter_manager.is_filtering:
            # 筛选模式：显示筛选指示器
            self.filter_indicator.show()
        else:
            # 正常模式：隐藏筛选指示器
            self.filter_indicator.hide()

    def _update_filter_mode_restrictions(self):
        """
        根据筛选模式更新功能限制

        筛选模式下：
        - 禁用刷新按钮
        - 暂停后台监控
        """
        if self.filter_manager.is_filtering:
            # 禁用刷新按钮
            self.refresh_btn.setEnabled(False)
            self.refresh_btn.setToolTip("请先清除筛选以恢复刷新功能")

            # 暂停后台监控
            self._pause_background_monitoring()
        else:
            # 启用刷新按钮
            self.refresh_btn.setEnabled(True)
            self.refresh_btn.setToolTip("刷新数据")

            # 恢复后台监控
            self._resume_background_monitoring()

    def _update_status_bar_for_filter_mode(self):
        """更新状态栏以显示当前模式"""
        if self.filter_manager.is_filtering:
            filter_info = self.filter_manager.get_filter_summary()
            self.statusBar().showMessage(f"🔍 筛选模式: {filter_info}")
        else:
            self.statusBar().showMessage("正常分页模式")

    def _pause_background_monitoring(self):
        """暂停后台监控"""
        try:
            if hasattr(workflow, 'pause_monitoring'):
                workflow.pause_monitoring()
                print("[UI] Background monitoring paused")
        except Exception as e:
            print(f"[UI] Failed to pause monitoring: {e}")

    def _resume_background_monitoring(self):
        """恢复后台监控"""
        try:
            if hasattr(workflow, 'resume_monitoring'):
                workflow.resume_monitoring()
                print("[UI] Background monitoring resumed")
        except Exception as e:
            print(f"[UI] Failed to resume monitoring: {e}")

    def on_refresh_filter_options(self):
        """
        手动刷新筛选选项 - 从数据库重新扫描所有选项
        """
        try:
            self.statusBar().showMessage("正在刷新筛选选项...")
            QApplication.processEvents()

            # 执行手动刷新
            result = filter_options_registry.manual_refresh()

            # 更新下拉菜单
            self.update_dropdowns()

            # 清除新选项标记
            filter_options_registry.clear_new_flag()
            self.sidebar.set_filter_new_indicator(False)

            # 显示结果
            stats = filter_options_registry.get_stats()
            msg = (
                f"筛选选项刷新完成！\n\n"
                f"学生总数: {stats['total_students']}\n"
                f"作业总数: {stats['total_assignments']}\n"
                f"状态总数: {stats['total_statuses']}\n\n"
                f"上次全量扫描: {stats['last_full_scan'].strftime('%Y-%m-%d %H:%M:%S') if stats['last_full_scan'] else '未知'}"
            )

            if result.get('new_students', 0) > 0 or result.get('new_assignments', 0) > 0:
                msg += f"\n\n本次新增：\n"
                msg += f"学生: {result['new_students']} 个\n"
                msg += f"作业: {result['new_assignments']} 个"

            QMessageBox.information(self, "刷新完成", msg)
            self.statusBar().showMessage("筛选选项已刷新")

        except Exception as e:
            import traceback
            print(f"[UI] Error refreshing filter options: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"刷新筛选选项失败: {str(e)}")
            self.statusBar().showMessage("刷新失败")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 加载样式
    try:
        with open("gui/styles/theme.qss", "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"Warning: Could not load theme.qss: {e}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
