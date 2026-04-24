"""从TARGET_FOLDER拉取已处理邮件数据的模块（支持分页）"""
from mail.imap_client import imap_client_target
from mail.parser import MailParser
from config.settings import settings
from database.operations import db
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import asyncio

class TargetFolderLoader:
    """TARGET_FOLDER数据加载器 - 支持分页和多源数据合并"""

    def __init__(self):
        self.imap = imap_client_target
        self.parser = MailParser(self.imap)
        self._cached_emails = None
        self._total_count = 0

    def get_from_target_folder(self, page: int = 1, per_page: int = 100) -> Dict:
        """
        从TARGET_FOLDER分页获取数据

        Returns:
            {
                'submissions': list,  # 提交记录列表
                'total': int,         # 总记录数
                'page': int,          # 当前页码
                'per_page': int,      # 每页记录数
                'total_pages': int    # 总页数
            }
        """
        try:
            # 连接到TARGET_FOLDER
            if not self.imap.connect():
                raise ConnectionError("无法连接到TARGET_FOLDER")

            # 选择TARGET_FOLDER
            if not self.imap.select_folder(settings.TARGET_FOLDER):
                raise FileNotFoundError(f"TARGET_FOLDER '{settings.TARGET_FOLDER}' 不存在")

            # 获取所有邮件（包括已读）
            if self._cached_emails is None:
                # 使用优化的方法只获取邮件基本信息，提升性能
                all_emails = self.imap.get_all_email_headers()
                self._cached_emails = all_emails
                self._total_count = len(all_emails)
            else:
                all_emails = self._cached_emails

            # 分页处理
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_emails = all_emails[start_idx:end_idx]

            # 使用批量异步处理提升性能
            submissions = asyncio.run(self._batch_merge_submission_info(page_emails))

            self.imap.disconnect()

            return {
                'submissions': submissions,
                'total': self._total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': (self._total_count + per_page - 1) // per_page
            }

        except Exception as e:
            # 确保断开连接
            try:
                self.imap.disconnect()
            except:
                pass
            raise e

    def _merge_submission_info(self, email_data) -> Dict:
        """
        合并多源数据：邮件内容 + 本地文件 + 数据库元数据

        Returns:
            Dict containing merged info
        """
        uid = email_data.get('uid')
        msg_id = email_data.get('message_id')

        # 1. 从邮件获取基本信息
        email_info = {
            'email_uid': uid,
            'message_id': msg_id,
            'email_subject': email_data.get('subject', ''),
            'email_from': email_data.get('from', ''),
            'received_time': self._parse_date(email_data.get('date')),
        }

        # 2. 从数据库获取元数据
        db_record = None
        if msg_id:
            db_record = db.get_submission_by_message_id(msg_id)
        
        if not db_record:
            db_record = db.get_submission_by_uid(uid)
            if db_record and msg_id:
                db.update_submission_field(db_record.id, 'message_id', msg_id)

        if db_record:
            db_info = {
                'id': db_record.id,
                'student_id': db_record.student.student_id if db_record.student else "Unknown",
                'name': db_record.student.name if db_record.student else "Unknown",
                'email': db_record.student.email if db_record.student else db_record.sender_email,
                'assignment_name': db_record.assignment.name if db_record.assignment else "Unknown",
                'submission_time': db_record.submission_time,
                'is_late': db_record.is_late,
                'is_downloaded': db_record.is_downloaded,
                'is_replied': db_record.is_replied,
                'local_path': db_record.local_path,
                'status': getattr(db_record, 'status', 'pending'),
                'error_message': getattr(db_record, 'error_message', None),
            }
        else:
            # 数据库中没有记录，从邮件主题提取信息 (此处无法使用异步AI提取，返回默认)
            db_info = {
                'id': None,
                'student_id': 'Unknown',
                'name': 'Unknown',
                'email': email_data.get('from', ''),
                'assignment_name': 'Unknown',
                'submission_time': self._parse_date(email_data.get('date')),
                'is_late': False,
                'is_downloaded': False,
                'is_replied': False,
                'local_path': None,
                'status': 'pending',
                'error_message': None
            }

        # 3. 从本地文件系统获取附件信息
        attachments = self._get_local_attachments(db_info.get('local_path'))

        # 合并所有信息
        return {**email_info, **db_info, 'attachments': attachments}

    def _parse_date(self, date_str: str) -> datetime:
        """解析邮件日期"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()

    async def _batch_merge_submission_info(self, page_emails: List[Dict]) -> List[Dict]:
        """
        批量异步处理多源数据合并

        Args:
            page_emails: 当前页的邮件列表

        Returns:
            合并后的提交信息列表（过滤掉None值）
        """
        # 创建所有异步任务
        tasks = [self._merge_submission_info_async(email_data) for email_data in page_emails]

        # 使用asyncio.gather并发执行，return_exceptions=True确保部分失败不影响整体
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 过滤掉异常和None值
        submissions = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Error processing email: {result}")
                continue
            if result is not None:
                submissions.append(result)

        return submissions

    async def _merge_submission_info_async(self, email_data) -> Dict:
        """异步版本的多源数据合并 - 增加基于内容的自动修复逻辑"""
        uid = email_data.get('uid')
        msg_id = email_data.get('message_id')

        # 1. 从邮件获取基本信息
        email_info = {
            'email_uid': uid,
            'message_id': msg_id,
            'email_subject': email_data.get('subject', ''),
            'email_from': email_data.get('from', ''),
            'received_time': self._parse_date(email_data.get('date')),
        }

        # 2. 从数据库获取元数据
        db_record = None
        
        # --- 策略 1: 强标识符匹配 ---
        if msg_id:
            db_record = db.get_submission_by_message_id(msg_id)
            
        if not db_record:
            db_record = db.get_submission_by_uid(uid)

        # --- 策略 2: 基于内容识别的自动修复 (针对移动后丢失关联的邮件) ---
        ai_info = None
        if not db_record:
            # 只有在完全匹配不到数据库记录时，才尝试按内容检索
            ai_info = await self._extract_from_email(email_data)
            student_id = ai_info.get('student_id')
            assignment_name = ai_info.get('assignment_name')
            
            if student_id and student_id != 'Unknown' and assignment_name and assignment_name != 'Unknown':
                # A. 尝试寻找已有的旧记录进行链接
                db_record = db.get_submission(student_id, assignment_name)
                
                if db_record:
                    # 发现已有关联记录，立即修复其标识符
                    print(f"[REPAIR] Linked email {uid} to existing record {db_record.id} via content match ({student_id})")
                    db.update_submission_field(db_record.id, 'email_uid', uid)
                    if msg_id:
                        db.update_submission_field(db_record.id, 'message_id', msg_id)
                else:
                    # B. 数据库确实没有记录，执行“自动入库索引”
                    print(f"[INDEX] Auto-creating missing database record for email {uid} ({student_id})")
                    db_record = db.create_submission(
                        email_uid=uid,
                        message_id=msg_id,
                        email_subject=email_info['email_subject'],
                        sender_email=email_info['email_from'],
                        sender_name=ai_info.get('name', 'Unknown'),
                        submission_time=email_info['received_time'],
                        student_id=student_id,
                        assignment_name=assignment_name,
                        status='completed' # 已在处理文件夹中的邮件默认设为已完成
                    )

        # 3. 组织返回信息
        if db_record:
            db_info = {
                'id': db_record.id,
                'student_id': db_record.student.student_id if db_record.student else "Unknown",
                'name': db_record.student.name if db_record.student else "Unknown",
                'email': db_record.student.email if db_record.student else db_record.sender_email,
                'assignment_name': db_record.assignment.name if db_record.assignment else "Unknown",
                'submission_time': db_record.submission_time,
                'is_late': db_record.is_late,
                'is_downloaded': db_record.is_downloaded,
                'is_replied': db_record.is_replied,
                'local_path': db_record.local_path,
                'status': getattr(db_record, 'status', 'pending'),
                'error_message': getattr(db_record, 'error_message', None),
            }
        else:
            # 数据库中确实没有记录且无法匹配，使用刚刚提取的 AI 信息
            db_info = ai_info if ai_info else await self._extract_from_email(email_data)
            db_info['id'] = None
            db_info['status'] = 'pending'
            db_info['error_message'] = None

        # 4. 从本地文件系统获取附件信息
        attachments = self._get_local_attachments(db_info.get('local_path'))

        # 合并所有信息
        return {**email_info, **db_info, 'attachments': attachments}
        attachments = self._get_local_attachments(db_info.get('local_path'))

        # 合并所有信息
        return {**email_info, **db_info, 'attachments': attachments}

    async def _extract_from_email(self, email_data) -> Dict:
        """从邮件中提取信息（使用AI，不再使用正则表达式）"""
        from ai.extractor import ai_extractor

        subject = email_data.get('subject', '')
        uid = email_data.get('uid', '')

        try:
            # 使用AI提取信息
            result = await ai_extractor.extract_with_cache({
                'uid': uid,
                'subject': subject,
                'from': email_data.get('from', ''),
                'attachments': []
            })

            return {
                'id': None,
                'student_id': result.get('student_id') or 'Unknown',
                'name': result.get('name') or 'Unknown',
                'email': email_data.get('from', ''),
                'assignment_name': result.get('assignment_name') or 'Unknown',
                'submission_time': self._parse_date(email_data.get('date')),
                'is_late': False,
                'is_downloaded': False,
                'is_replied': False,
                'local_path': None,
            }
        except Exception as e:
            print(f"AI extraction error: {e}")
            # 返回Unknown而不是使用正则表达式
            return {
                'id': None,
                'student_id': 'Unknown',
                'name': 'Unknown',
                'email': '',
                'assignment_name': 'Unknown',
                'submission_time': self._parse_date(email_data.get('date')),
                'is_late': False,
                'is_downloaded': False,
                'is_replied': False,
                'local_path': None,
            }

    def _get_local_attachments(self, local_path: str) -> List[Dict]:
        """从本地路径获取附件列表"""
        if not local_path:
            return []

        path = Path(local_path)
        if not path.exists():
            return []

        attachments = []
        for file in path.iterdir():
            if file.is_file() and not file.name.startswith('_'):
                attachments.append({
                    'filename': file.name,
                    'size': file.stat().st_size,
                    'path': str(file)
                })

        return attachments

    def clear_cache(self):
        """清除缓存，强制重新加载"""
        self._cached_emails = None
        self._total_count = 0

# 全局实例
target_folder_loader = TargetFolderLoader()
