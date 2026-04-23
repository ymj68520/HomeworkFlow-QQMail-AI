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

            submissions = []
            for email_data in page_emails:
                # 合并邮件数据、本地文件和数据库信息
                submission = asyncio.run(self._merge_submission_info_async(email_data))
                if submission:
                    submissions.append(submission)

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
            {
                'id': int,
                'student_id': str,
                'name': str,
                'email': str,
                'assignment_name': str,
                'email_uid': str,
                'email_subject': str,        # 邮件原始主题
                'email_from': str,           # 邮件原始发件人
                'received_time': datetime,   # 收件时间
                'submission_time': datetime,
                'is_late': bool,
                'is_downloaded': bool,
                'is_replied': bool,
                'local_path': str,
                'attachments': list          # 附件列表
            }
        """
        uid = email_data.get('uid')

        # 1. 从邮件获取基本信息
        email_info = {
            'email_uid': uid,
            'email_subject': email_data.get('subject', ''),
            'email_from': email_data.get('from', ''),
            'received_time': self._parse_date(email_data.get('date')),
        }

        # 2. 从数据库获取元数据
        db_record = db.get_submission_by_uid(uid)
        if db_record:
            db_info = {
                'id': db_record.id,
                'student_id': db_record.student.student_id,
                'name': db_record.student.name,
                'email': db_record.student.email,
                'assignment_name': db_record.assignment.name,
                'submission_time': db_record.submission_time,
                'is_late': db_record.is_late,
                'is_downloaded': db_record.is_downloaded,
                'is_replied': db_record.is_replied,
                'local_path': db_record.local_path,
            }
        else:
            # 数据库中没有记录，从邮件主题提取信息
            db_info = self._extract_from_email(email_data)

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

    async def _merge_submission_info_async(self, email_data) -> Dict:
        """异步版本的多源数据合并"""
        uid = email_data.get('uid')

        # 1. 从邮件获取基本信息
        email_info = {
            'email_uid': uid,
            'email_subject': email_data.get('subject', ''),
            'email_from': email_data.get('from', ''),
            'received_time': self._parse_date(email_data.get('date')),
        }

        # 2. 从数据库获取元数据
        db_record = db.get_submission_by_uid(uid)
        if db_record:
            db_info = {
                'id': db_record.id,
                'student_id': db_record.student.student_id,
                'name': db_record.student.name,
                'email': db_record.student.email,
                'assignment_name': db_record.assignment.name,
                'submission_time': db_record.submission_time,
                'is_late': db_record.is_late,
                'is_downloaded': db_record.is_downloaded,
                'is_replied': db_record.is_replied,
                'local_path': db_record.local_path,
            }
        else:
            # 数据库中没有记录，使用AI提取
            db_info = await self._extract_from_email(email_data)

        # 3. 从本地文件系统获取附件信息
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
