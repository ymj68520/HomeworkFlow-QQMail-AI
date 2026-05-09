"""
混合数据加载器 - 使用原始IMAP逻辑 + 优化数据库查询

这个版本更安全，因为它使用经过验证的IMAP逻辑，
但仍然使用批量数据库查询来提升性能。
"""
from mail.imap_client import imap_client_target
from mail.parser import MailParser
from config.settings import settings
from database.operations import db
from core.data_cache import data_cache
from core.data_transform import DataTransformService
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import asyncio


class HybridDataLoader:
    """
    混合数据加载器

    - 使用原始的target_folder_loader的IMAP逻辑（已验证）
    - 使用批量数据库查询（优化）
    - 使用缓存系统
    """

    def __init__(self):
        self.imap = imap_client_target
        self.parser = MailParser(self.imap)
        self.data_transform = DataTransformService()
        self._cached_emails = None
        self._total_count = 0

    def get_page_data(self, page: int = 1, per_page: int = 100,
                     force_refresh: bool = False) -> Dict:
        """
        获取分页数据

        Args:
            page: 页码
            per_page: 每页记录数
            force_refresh: 强制刷新，忽略缓存

        Returns:
            {
                'submissions': list,
                'total': int,
                'page': int,
                'per_page': int,
                'total_pages': int
            }
        """
        print(f"[HybridLoader] get_page_data: page={page}, per_page={per_page}")

        # 检查缓存
        if not force_refresh:
            cached = data_cache.get_page_data(page)
            if cached:
                print(f"[HybridLoader] Cache HIT for page {page}")
                return {
                    'submissions': cached,
                    'total': data_cache.total_count,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': data_cache.total_pages
                }

        # 从IMAP加载数据（使用原始逻辑）
        try:
            print("[HybridLoader] Connecting to IMAP...")
            # 连接到TARGET_FOLDER
            if not self.imap.connect():
                raise ConnectionError("无法连接到TARGET_FOLDER")

            # 选择TARGET_FOLDER
            if not self.imap.select_folder(settings.TARGET_FOLDER):
                raise FileNotFoundError(f"TARGET_FOLDER '{settings.TARGET_FOLDER}' 不存在")

            # 获取所有邮件（包括已读）
            if self._cached_emails is None or force_refresh:
                print("[HybridLoader] Getting all email headers...")
                # 使用优化的方法只获取邮件基本信息，提升性能
                all_emails = self.imap.get_all_email_headers()
                self._cached_emails = all_emails
                self._total_count = len(all_emails)
                print(f"[HybridLoader] Got {self._total_count} emails")
            else:
                all_emails = self._cached_emails

            # 分页处理
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_emails = all_emails[start_idx:end_idx]
            print(f"[HybridLoader] Page {page}: emails {start_idx} to {end_idx}")

            # 使用批量处理提升性能
            print("[HybridLoader] Processing emails...")
            raw_submissions = self._batch_merge_submission_info(page_emails)
            print(f"[HybridLoader] Got {len(raw_submissions)} raw submissions")

            # 新增：转换为分组格式（按作业分组）
            grouped_submissions = self.data_transform.transform_to_grouped_format(raw_submissions, group_by_assignment=True)
            print(f"[HybridLoader] Got {len(grouped_submissions)} assignment groups")

            self.imap.disconnect()

            total_pages = (self._total_count + per_page - 1) // per_page

            # 更新缓存
            data_cache.set_page_data(page, grouped_submissions, self._total_count, total_pages)

            return {
                'submissions': grouped_submissions,
                'total': self._total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }

        except Exception as e:
            # 确保断开连接
            try:
                self.imap.disconnect()
            except:
                pass

            import traceback
            print(f"[HybridLoader] ERROR: {e}")
            traceback.print_exc()
            raise e

    def _batch_merge_submission_info(self, page_emails: List[Dict]) -> List[Dict]:
        """
        批量合并提交信息 - 使用批量数据库查询优化（同步版本）

        Args:
            page_emails: 当前页的邮件列表

        Returns:
            合并后的提交信息列表
        """
        # 收集所有UID和Message-ID
        uids = [e.get('uid') for e in page_emails if e.get('uid')]
        message_ids = [e.get('message_id') for e in page_emails if e.get('message_id')]

        print(f"[HybridLoader] Batch querying DB for {len(uids)} UIDs and {len(message_ids)} Message-IDs")

        # 批量查询数据库（关键优化）
        db_records = db.get_submissions_bulk(uids=uids, message_ids=message_ids)

        print(f"[HybridLoader] Got {len(db_records)} DB records")

        # 合并数据
        submissions = []
        for email_data in page_emails:
            uid = email_data.get('uid')
            msg_id = email_data.get('message_id')

            # 从批量查询结果中获取记录
            db_record = db_records.get(uid) or db_records.get(msg_id)

            submission = self._merge_single_record(email_data, db_record)
            submissions.append(submission)

        # 新增：查询并添加子记录（重复提交）
        # 获取所有主记录的ID
        primary_ids = [s.get('id') for s in submissions if s.get('id')]
        if primary_ids:
            # 查询所有这些主记录的子记录
            from database.models import Submission
            from sqlalchemy.orm import joinedload
            child_records = db.session.query(Submission).filter(
                Submission.parent_id.in_(primary_ids)
            ).options(
                joinedload(Submission.student),
                joinedload(Submission.assignment)
            ).all()

            # 将子记录转换为字典格式并添加
            for child in child_records:
                child_dict = {
                    'id': child.id,
                    'email_uid': child.email_uid,
                    'message_id': child.message_id,
                    'email_subject': child.email_subject,
                    'email_from': child.email_from if hasattr(child, 'email_from') else child.sender_email,
                    'sender_email': child.sender_email,
                    'sender_name': child.sender_name,
                    'received_time': None,  # 子记录没有单独的收件时间
                    'student_id': child.student_id if hasattr(child, 'student_id') else (child.student.student_id if child.student else "Unknown"),
                    'name': child.student.name if child.student else "Unknown",
                    'student_name': child.student.name if child.student else "Unknown",  # 保持一致性
                    'student_email': child.student.email if child.student else None,
                    'assignment_name': child.assignment.name if child.assignment else "Unknown",
                    'assignment_id': child.assignment_id if hasattr(child, 'assignment_id') else None,
                    'submission_time': child.submission_time,
                    'is_late': child.is_late,
                    'is_downloaded': child.is_downloaded,
                    'is_replied': child.is_replied,
                    'local_path': child.local_path,
                    'status': getattr(child, 'status', 'pending'),
                    'error_message': getattr(child, 'error_message', None),
                    'body': getattr(child, 'body', None),
                    'attachments': self._get_local_attachments(child.local_path) if child.local_path else [],
                    'parent_id': child.parent_id,
                    'relation_type': child.relation_type if hasattr(child.relation_type, 'value') else child.relation_type,
                    'is_primary': child.is_primary,
                    'version': child.version,
                    'is_latest': child.is_latest,
                }
                submissions.append(child_dict)

        return submissions

    def _merge_single_record(self, email_data: Dict, db_record) -> Dict:
        """合并单条记录"""
        uid = email_data.get('uid')
        msg_id = email_data.get('message_id')

        # 1. 从邮件获取基本信息
        submission = {
            'email_uid': uid,
            'message_id': msg_id,
            'email_subject': email_data.get('subject', ''),
            'email_from': email_data.get('from', ''),
            'received_time': self._parse_date(email_data.get('date')),
            'parent_id': None,  # 新增：父记录ID，用于分组显示
            'relation_type': None,  # 新增：关联类型（primary/related）
            'is_primary': True,  # 新增：是否为主记录
        }

        # 2. 从数据库获取元数据
        if db_record:
            submission.update({
                'id': db_record.id,
                'student_id': db_record.student.student_id if db_record.student else "Unknown",
                'name': db_record.student.name if db_record.student else "Unknown",
                'student_name': db_record.student.name if db_record.student else "Unknown",  # 保持一致性
                'email': db_record.student.email if db_record.student else db_record.sender_email,
                'assignment_name': db_record.assignment.name if db_record.assignment else "Unknown",
                'submission_time': db_record.submission_time,
                'is_late': db_record.is_late,
                'is_downloaded': db_record.is_downloaded,
                'is_replied': db_record.is_replied,
                'local_path': db_record.local_path,
                'status': getattr(db_record, 'status', 'pending'),
                'error_message': getattr(db_record, 'error_message', None),
                'body': getattr(db_record, 'body', None),
                'attachments': self._get_local_attachments(db_record.local_path) if db_record.local_path else [],
                # 去重关系字段（从数据库读取）
                'parent_id': db_record.parent_id,
                'relation_type': db_record.relation_type if hasattr(db_record.relation_type, 'value') else db_record.relation_type,
                'is_primary': db_record.is_primary,
                'version': db_record.version,
                'is_latest': db_record.is_latest
            })
        else:
            # 数据库中没有记录 - 使用发件人邮箱作为标识
            from_email = email_data.get('from', '')
            # 尝试解析发件人姓名
            sender_name = ''
            if from_email:
                # 简单解析发件人信息（格式：Name <email> 或 email）
                if '<' in from_email and '>' in from_email:
                    sender_name = from_email.split('<')[0].strip().strip('"').strip("'")
                else:
                    sender_name = from_email

            subject = email_data.get('subject', '')

            # 尝试从邮箱提取临时学号标识（格式：QQ号@qq.com）
            temp_student_id = from_email.split('@')[0] if '@' in from_email else from_email

            submission.update({
                'id': None,
                'student_id': temp_student_id,
                'name': sender_name or temp_student_id,
                'student_name': sender_name or temp_student_id,  # 保持一致性
                'email': from_email,
                'assignment_name': '待识别',
                'submission_time': self._parse_date(email_data.get('date')),
                'is_late': False,
                'is_downloaded': False,
                'is_replied': False,
                'local_path': None,
                'status': 'pending',
                'error_message': None,
                'attachments': []
            })

        return submission

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

    def _parse_date(self, date_str: str) -> datetime:
        """解析邮件日期"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()

    def invalidate_cache(self):
        """使缓存失效"""
        self._cached_emails = None

    def update_single_record(self, uid: str, updates: Dict):
        """更新单个记录"""
        data_cache.update_single_record(uid, updates)

    def remove_record(self, uid: str):
        """删除单个记录"""
        data_cache.invalidate_record(uid)


# 全局实例
hybrid_data_loader = HybridDataLoader()
