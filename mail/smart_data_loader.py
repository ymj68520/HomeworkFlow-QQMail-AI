"""
智能数据加载器 - 性能优化版本

优化项:
1. 使用持久连接管理器
2. 批量数据库查询
3. 三层缓存策略
4. 懒加载邮件正文
5. 增量更新支持
"""
from mail.connection_manager import connection_manager
from mail.parser import MailParser
from mail.imap_client import imap_client_target
from config.settings import settings
from database.operations import db
from core.data_cache import data_cache
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set
import asyncio


class SmartDataLoader:
    """
    智能数据加载器

    核心优化:
    - 持久IMAP连接
    - 批量数据库查询
    - 多层缓存
    - 增量更新
    """

    def __init__(self):
        # 使用持久连接管理器
        self.connection_manager = connection_manager
        # 备用客户端（当连接管理器不可用时）
        self.fallback_client = imap_client_target
        self.parser = None  # 延迟初始化

        # 缓存状态
        self._all_uids_cache = None
        self._total_count = 0
        self._cache_valid = False

    def _get_client(self):
        """获取可用的IMAP客户端"""
        print("[SmartLoader] _get_client called")

        # 首先尝试持久连接
        client = self.connection_manager.get_client()
        print(f"[SmartLoader] connection_manager.get_client() returned: {client is not None}")

        if client:
            if not self.parser:
                print("[SmartLoader] Creating new MailParser")
                self.parser = MailParser(client)
            return client

        # 回退到传统方式
        print("[SmartLoader] Falling back to traditional client")
        return self.fallback_client

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
        print(f"[SmartLoader] get_page_data: page={page}, per_page={per_page}, force_refresh={force_refresh}")

        # 检查缓存
        if not force_refresh:
            cached = data_cache.get_page_data(page)
            if cached:
                print(f"[SmartLoader] Cache HIT for page {page}")
                return {
                    'submissions': cached,
                    'total': data_cache.total_count,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': data_cache.total_pages
                }
            else:
                print(f"[SmartLoader] Cache MISS for page {page}")

        # 从IMAP加载数据
        try:
            # 使用持久连接
            print("[SmartLoader] Getting IMAP client...")
            client = self._get_client()
            if not client:
                print("[SmartLoader] ERROR: Cannot get IMAP client!")
                raise ConnectionError("无法获取IMAP连接")

            # 确保选择了正确的文件夹
            if self.connection_manager.current_folder != settings.TARGET_FOLDER:
                if not self.connection_manager.select_folder(settings.TARGET_FOLDER):
                    raise FileNotFoundError(f"无法选择文件夹: {settings.TARGET_FOLDER}")

            # 获取所有UID列表（带缓存）
            if self._all_uids_cache is None or force_refresh or not self._cache_valid:
                self._all_uids_cache = self._get_all_uids()
                self._total_count = len(self._all_uids_cache)
                self._cache_valid = True

            # 分页计算
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, self._total_count)

            if start_idx >= self._total_count:
                return {
                    'submissions': [],
                    'total': self._total_count,
                    'page': page,
                    'per_page': per_page,
                    'total_pages': max(1, (self._total_count + per_page - 1) // per_page)
                }

            # 获取当前页的UID列表
            page_uids = self._all_uids_cache[start_idx:end_idx]

            # 批量获取邮件头信息
            page_emails = self._get_emails_headers_batch(page_uids)

            # 批量查询数据库（性能优化关键）
            db_records = self._batch_query_database(page_uids)

            # 合并数据
            submissions = self._merge_data_fast(page_emails, db_records)

            # 更新缓存
            total_pages = max(1, (self._total_count + per_page - 1) // per_page)
            data_cache.set_page_data(page, submissions, self._total_count, total_pages)

            return {
                'submissions': submissions,
                'total': self._total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }

        except Exception as e:
            # 出错时使缓存失效
            self._cache_valid = False
            raise e

    def _get_all_uids(self) -> List[str]:
        """
        获取所有邮件UID列表

        只获取UID，不获取完整内容，大幅提升性能

        Returns:
            UID列表
        """
        client = self._get_client()
        if not client or not client.connection:
            # 回退到传统方式
            if not self.fallback_client.connect():
                raise ConnectionError("无法连接到IMAP服务器")
            self.fallback_client.select_folder(settings.TARGET_FOLDER)
            emails = self.fallback_client.get_all_email_headers()
            self.fallback_client.disconnect()
            return [e.get('uid') for e in emails if e.get('uid')]

        # 使用持久连接
        try:
            import imaplib
            conn = client.connection

            # 搜索所有邮件
            status, messages = conn.search(None, 'ALL')
            if status != 'OK':
                return []

            email_ids = messages[0].split()
            uids = []

            # 批量获取UID
            batch_size = 500
            for i in range(0, len(email_ids), batch_size):
                batch_ids = email_ids[i:i + batch_size]
                batch_str = b','.join(batch_ids)

                # 只获取UID
                status, data = conn.fetch(batch_str, '(UID)')
                if status != 'OK':
                    continue

                for response_part in data:
                    if isinstance(response_part, tuple):
                        # 解析UID
                        import re
                        text = response_part[0].decode() if isinstance(response_part[0], bytes) else str(response_part[0])
                        uid_match = re.search(r'UID\s+(\d+)', text)
                        if uid_match:
                            uids.append(uid_match.group(1))

            return uids

        except Exception as e:
            print(f"Error getting UIDs: {e}")
            raise

    def _get_emails_headers_batch(self, uids: List[str]) -> List[Dict]:
        """
        批量获取邮件头信息

        Args:
            uids: UID列表

        Returns:
            邮件头信息列表
        """
        client = self._get_client()
        if not client or not client.connection:
            return []

        try:
            import imaplib
            import email
            conn = client.connection
            emails = []

            # 批量获取邮件头
            batch_size = 100
            for i in range(0, len(uids), batch_size):
                batch_uids = uids[i:i + batch_size]
                # 使用UID FETCH命令
                batch_str = ','.join(batch_uids)

                status, data = conn.fetch(batch_str, '(UID RFC822.HEADER)')
                if status != 'OK':
                    continue

                for idx, response_part in enumerate(data):
                    if isinstance(response_part, tuple):
                        header_data = response_part[1]
                        msg = email.message_from_bytes(header_data)

                        # 提取基本信息
                        email_data = {
                            'uid': batch_uids[idx] if idx < len(batch_uids) else None,
                            'message_id': self._decode_header(msg.get('Message-ID', '')),
                            'subject': self._decode_header(msg.get('Subject', '')),
                            'from': self._decode_header(msg.get('From', '')),
                            'date': msg.get('Date', '')
                        }
                        emails.append(email_data)

            return emails

        except Exception as e:
            print(f"Error getting email headers: {e}")
            return []

    def _batch_query_database(self, uids: List[str]) -> Dict:
        """
        批量查询数据库 - 性能优化关键

        替代原来的N+1查询问题

        Args:
            uids: UID列表

        Returns:
            {uid: submission_dict}
        """
        if not uids:
            return {}

        # 使用新的批量查询方法
        return db.get_submissions_bulk(uids=uids)

    def _merge_data_fast(self, emails: List[Dict], db_records: Dict) -> List[Dict]:
        """
        快速合并邮件数据和数据库记录

        Args:
            emails: 邮件头信息列表
            db_records: 数据库记录字典 {uid: record}

        Returns:
            合并后的提交记录列表
        """
        submissions = []

        for email_data in emails:
            uid = email_data.get('uid')
            msg_id = email_data.get('message_id')

            # 从数据库记录获取详细信息
            db_record = db_records.get(uid) or db_records.get(msg_id)

            # 构建提交记录
            submission = {
                'email_uid': uid,
                'message_id': msg_id,
                'email_subject': email_data.get('subject', ''),
                'email_from': email_data.get('from', ''),
                'received_time': self._parse_date(email_data.get('date')),
            }

            if db_record:
                # 从数据库记录获取详细信息
                submission.update({
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
                    'body': getattr(db_record, 'body', None),
                    'attachments': self._get_local_attachments(db_record.local_path) if db_record.local_path else []
                })
            else:
                # 没有数据库记录 - 使用发件人邮箱作为标识
                from_email = email_data.get('from', '')
                # 尝试解析发件人姓名
                sender_name = ''
                if from_email:
                    # 简单解析发件人信息（格式：Name <email> 或 email）
                    if '<' in from_email and '>' in from_email:
                        sender_name = from_email.split('<')[0].strip().strip('"').strip("'")
                    else:
                        sender_name = from_email

                temp_student_id = from_email.split('@')[0] if '@' in from_email else from_email

                submission.update({
                    'id': None,
                    'student_id': temp_student_id,
                    'name': sender_name or temp_student_id,
                    'email': from_email,
                    'assignment_name': '待识别',
                    'submission_time': self._parse_date(email_data.get('date')),
                    'is_late': False,
                    'is_downloaded': False,
                    'is_replied': False,
                    'local_path': None,
                    'status': 'ai_error',
                    'error_message': '未识别，需手动处理',
                    'attachments': []
                })

            submissions.append(submission)

        return submissions

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

    def _decode_header(self, header: str) -> str:
        """解码邮件头"""
        try:
            from email.header import decode_header
            decoded_parts = decode_header(header)
            result = []
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    result.append(part.decode(encoding or 'utf-8', errors='ignore'))
                else:
                    result.append(str(part))
            return ''.join(result)
        except:
            return str(header)

    def _parse_date(self, date_str: str) -> datetime:
        """解析邮件日期"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()

    def invalidate_cache(self):
        """使缓存失效"""
        self._all_uids_cache = None
        self._cache_valid = False

    def update_single_record(self, uid: str, updates: Dict):
        """
        更新单个记录（增量更新）

        Args:
            uid: 邮件UID
            updates: 要更新的字段
        """
        data_cache.update_single_record(uid, updates)

    def remove_record(self, uid: str):
        """
        删除单个记录

        Args:
            uid: 邮件UID
        """
        data_cache.invalidate_record(uid)
        self._cache_valid = False


# 全局实例
smart_data_loader = SmartDataLoader()
