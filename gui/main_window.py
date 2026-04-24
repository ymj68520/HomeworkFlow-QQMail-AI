import sys
import threading
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QApplication, QMessageBox, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, Signal

from gui.components.sidebar import Sidebar
from gui.components.data_table import DataTable
from gui.components.drawer import Drawer
from gui.components.batch_popup import BatchPopup
from database.operations import db
from database.models import db_session
from mail.target_folder_loader import target_folder_loader
from mail.parser import mail_parser_inbox as mail_parser
from mail.smtp_client import smtp_client
from storage.manager import storage_manager
from core.workflow import workflow

class MainWindow(QMainWindow):
    """主窗口 - PySide6 实现"""
    
    # 定义跨线程更新信号
    update_drawer_signal = Signal(dict, str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("QQ邮箱作业收发系统")
        self.resize(1400, 900)

        # 状态映射
        self.STATUS_MAP = {
            'pending': '未处理',
            'ai_error': '识别异常',
            'download_failed': '下载失败',
            'unreplied': '未回复',
            'completed': '已完成',
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

        # 初始化UI
        self.setup_ui()
        
        # 绑定信号
        self.setup_connections()

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
        
        # 将表格放入垂直布局以支持工具栏或分页（如果需要）
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(20, 20, 20, 20)
        center_layout.addWidget(self.table)
        
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
        
        # 跨线程 UI 更新信号连接
        self.update_drawer_signal.connect(self.drawer.set_details)
        
        # 侧边栏按钮
        self.sidebar.btn_download.clicked.connect(self.on_batch_download)
        self.sidebar.btn_reply.clicked.connect(self.on_batch_reply)
        self.sidebar.btn_delete.clicked.connect(self.on_batch_delete)
        self.sidebar.btn_export.clicked.connect(self.on_export_excel)
        
        # 表格右键菜单
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_context_menu)

    def load_data(self, page: int = 1):
        """加载数据"""
        try:
            self.statusBar().showMessage("正在加载数据...")
            
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
            
            self.statusBar().showMessage(f"已加载 {len(self.all_submissions)} 条记录 (总计 {self.total_count})")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载数据失败: {str(e)}")
            self.statusBar().showMessage("加载失败")

    def update_dropdowns(self):
        """更新下拉菜单选项"""
        self.sidebar.student_filter.blockSignals(True)
        self.sidebar.assignment_filter.blockSignals(True)
        self.sidebar.status_filter.blockSignals(True)

        # 获取当前选中的值，以便刷新后尝试恢复
        curr_student = self.sidebar.student_filter.currentText()
        curr_assignment = self.sidebar.assignment_filter.currentText()
        curr_status = self.sidebar.status_filter.currentText()

        # 学生
        students = set()
        for sub in self.all_submissions:
            students.add(f"{sub['student_id']} - {sub['name']}")
        
        self.sidebar.student_filter.clear()
        self.sidebar.student_filter.addItem("全部学生")
        self.sidebar.student_filter.addItems(sorted(list(students)))
        
        # 作业
        assignments = set()
        for sub in self.all_submissions:
            assignments.add(sub['assignment_name'])
        
        self.sidebar.assignment_filter.clear()
        self.sidebar.assignment_filter.addItem("全部作业")
        self.sidebar.assignment_filter.addItems(sorted(list(assignments)))

        # 状态
        status_options = ["全部状态", "正常", "逾期"] + list(self.STATUS_MAP.values())
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

    def refresh_table(self):
        """刷新表格数据"""
        self.table.clear_data()
        
        for sub in self.filtered_submissions:
            status_code = sub.get('status', 'pending')
            status_text = self.STATUS_MAP.get(status_code, '未知')
            
            if sub.get('is_late'):
                status_text += " (逾期)"

            # 格式化收件时间
            received_time = sub.get('received_time')
            if received_time:
                if isinstance(received_time, datetime):
                    received_str = received_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    received_str = str(received_time)
            else:
                received_str = "未知"

            row_data = {
                "学号": sub['student_id'],
                "姓名": sub['name'],
                "作业": sub['assignment_name'],
                "收件时间": received_str,
                "提交时间": sub['submission_time'].strftime('%Y-%m-%d %H:%M:%S'),
                "状态": status_text,
                "本地路径": sub['local_path'] or "未下载"
            }
            self.table.add_row(row_data)

    def update_stats(self):
        """更新统计信息"""
        total = len(self.all_submissions)
        downloaded = sum(1 for sub in self.all_submissions if sub.get('status') in ['unreplied', 'completed'])
        replied = sum(1 for sub in self.all_submissions if sub.get('status') == 'completed')

        self.sidebar.total_card.value_label.setText(str(total))
        self.sidebar.downloaded_card.value_label.setText(str(downloaded))

    def on_search(self):
        """搜索逻辑"""
        query = self.sidebar.search_input.text().strip()

        if not query:
            self.on_filter_change() # 重新应用当前过滤器
        else:
            self.filtered_submissions = [
                sub for sub in self.all_submissions
                if query in str(sub['student_id']) or query in str(sub['name'])
            ]
            self.refresh_table()

    def on_filter_change(self):
        """筛选逻辑"""
        student_filter = self.sidebar.student_filter.currentText()
        assignment_filter = self.sidebar.assignment_filter.currentText()
        status_filter = self.sidebar.status_filter.currentText()

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

    def on_row_double_clicked(self, row_data):
        """处理行双击：展示抽屉"""
        # 寻找对应的原始数据
        submission = None
        for sub in self.all_submissions:
            if str(sub['student_id']) == str(row_data.get('学号')) and \
               sub['assignment_name'] == row_data.get('作业'):
                submission = sub
                break
        
        if submission:
            details = {
                "学号": submission['student_id'],
                "姓名": submission['name'],
                "作业": submission['assignment_name'],
                "收件时间": row_data.get('收件时间'),
                "提交时间": row_data.get('提交时间'),
                "状态": row_data.get('状态'),
                "本地路径": submission['local_path'] or "未下载"
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
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        submissions = []
        for index in selected_rows:
            row = index.row()
            # 获取学号和作业名作为标识
            student_id = self.table.item(row, 0).text()
            assignment_name = self.table.item(row, 2).text()
            
            for sub in self.all_submissions:
                if str(sub['student_id']) == student_id and sub['assignment_name'] == assignment_name:
                    submissions.append(sub)
                    break
        
        if submissions:
            popup = BatchPopup(self, submissions, on_update=lambda f, v: self.handle_batch_update(submissions, f, v))
            popup.exec()

    def handle_batch_update(self, submissions: List[Dict], field_id: str, new_value: Any):
        """批量更新业务逻辑"""
        success_count = 0
        last_error = None
        
        # 状态转换
        if field_id == 'status':
            for code, text in self.STATUS_MAP.items():
                if text == new_value:
                    new_value = code
                    break

        try:
            for sub in submissions:
                try:
                    if db.update_submission_field(
                        sub.get('id'), 
                        field_id, 
                        new_value, 
                        email_uid=sub.get('email_uid'),
                        message_id=sub.get('message_id')
                    ):
                        success_count += 1
                except Exception as e:
                    last_error = str(e)
            
            if success_count > 0:
                QMessageBox.information(self, "成功", f"已更新 {success_count}/{len(submissions)} 条记录")
                self.load_data(self.current_page)
            else:
                QMessageBox.warning(self, "失败", f"更新失败: {last_error or '未知错误'}")
        finally:
            db_session.remove()

    def on_batch_download(self):
        """批量下载附件"""
        submissions = self.get_selected_submissions()
        if not submissions:
            QMessageBox.information(self, "提示", "请先选择要下载的记录")
            return

        if QMessageBox.question(self, "确认", f"确定要下载 {len(submissions)} 条附件吗？") != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        success_count = 0
        
        try:
            if not mail_parser.connect():
                QMessageBox.critical(self, "错误", "无法连接邮件服务器")
                return

            for idx, sub in enumerate(submissions):
                self.statusBar().showMessage(f"正在下载 ({idx+1}/{len(submissions)}): {sub['name']}")
                QApplication.processEvents()
                
                try:
                    email_data = mail_parser.parse_email(sub['email_uid'])
                    if not email_data or not email_data.get('attachments'):
                        continue

                    local_path = storage_manager.store_submission(
                        assignment_name=sub['assignment_name'],
                        student_id=sub['student_id'],
                        name=sub['name'],
                        attachments=email_data['attachments']
                    )

                    if local_path:
                        db.update_submission_local_path(sub['id'], local_path)
                        new_status = 'completed' if sub.get('is_replied') else 'unreplied'
                        db.update_submission_status(sub['id'], new_status)
                        success_count += 1
                except:
                    pass

            self.load_data(self.current_page)
            QMessageBox.information(self, "完成", f"下载完成！成功: {success_count}/{len(submissions)}")
            mail_parser.disconnect()
        finally:
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("准备就绪")

    def on_batch_reply(self):
        """批量回复邮件"""
        submissions = self.get_selected_submissions()
        unreplied = [s for s in submissions if s.get('status') == 'unreplied']
        if not unreplied:
            QMessageBox.information(self, "提示", "没有符合条件的（已下载且未回复）记录")
            return

        if QMessageBox.question(self, "确认", f"确定要回复 {len(unreplied)} 条记录吗？") != QMessageBox.Yes:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        success_count = 0
        for s in unreplied:
            if smtp_client.send_reply(s['email'], s['name'], s['assignment_name']):
                db.mark_replied(s['id'])
                db.update_submission_status(s['id'], 'completed')
                success_count += 1
        
        self.load_data(self.current_page)
        QMessageBox.information(self, "完成", f"回复完成！成功: {success_count}/{len(unreplied)}")
        QApplication.restoreOverrideCursor()

    def on_batch_delete(self):
        """批量删除记录"""
        submissions = self.get_selected_submissions()
        if not submissions: return
        
        if QMessageBox.question(self, "确认", f"确定删除这 {len(submissions)} 条记录吗？\n邮件将移回收件箱。") != QMessageBox.Yes:
            return

        success_count = 0
        for s in submissions:
            if workflow.delete_submission(s['id']):
                success_count += 1
        
        self.load_data(self.current_page)
        QMessageBox.information(self, "完成", f"删除完成！成功: {success_count}/{len(submissions)}")

    def on_export_excel(self):
        """导出 Excel 占位符"""
        QMessageBox.information(self, "提示", "导出 Excel 功能待实现")

    def get_selected_submissions(self) -> List[dict]:
        """从表格选择中获取数据对象"""
        selected_rows = self.table.selectionModel().selectedRows()
        result = []
        for index in selected_rows:
            row = index.row()
            student_id = self.table.item(row, 0).text()
            assignment_name = self.table.item(row, 2).text()
            for sub in self.all_submissions:
                if str(sub['student_id']) == student_id and sub['assignment_name'] == assignment_name:
                    result.append(sub)
                    break
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
