import imaplib
import email
from email.header import decode_header
import ssl
import asyncio
from typing import List, Dict, Optional
from config.settings import settings

class IMAPClient:
    def __init__(self):
        self.host = settings.IMAP_SERVER
        self.port = settings.IMAP_PORT
        self.email = settings.QQ_EMAIL
        self.password = settings.QQ_PASSWORD
        self.connection = None
        self.current_folder = None

    def connect(self) -> bool:
        """连接到QQ邮箱IMAP服务器"""
        try:
            context = ssl.create_default_context()
            self.connection = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=context)

            self.connection.login(self.email, self.password)
            self.current_folder = None # 重连后重置文件夹状态，强制重新选择
            print(f"Connected to QQ email: {self.email}")
            return True

        except Exception as e:
            print(f"IMAP connection error: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass
            self.connection = None

    def list_folders(self):
        """列出所有文件夹"""
        try:
            if not self.connection:
                if not self.connect():
                    return []

            status, folders = self.connection.list()
            if status != 'OK':
                return []

            folder_list = []
            for folder in folders:
                # 解码文件夹名称
                folder_bytes = folder[0] if isinstance(folder, tuple) else folder
                if isinstance(folder_bytes, bytes):
                    folder_name = self.decode_header(folder_bytes.decode('utf-8', errors='ignore'))
                else:
                    folder_name = str(folder_bytes)

                folder_list.append(folder_name)

            return folder_list

        except Exception as e:
            print(f"Error listing folders: {e}")
            return []

    def find_folder_by_name(self, target_name: str):
        """根据名称查找文件夹（忽略前缀）"""
        folders = self.list_folders()

        # 尝试精确匹配
        for folder in folders:
            if target_name in folder and folder not in ['INBOX', 'Sent', 'Drafts', 'Junk', 'Trash', 'Deleted Messages', 'Sent Messages', 'QQ邮箱', 'temp']:
                return folder

        return None

    def extract_folder_path(self, folder_string: str) -> str:
        """从QQ邮箱的文件夹列表中提取实际的文件夹路径"""
        # QQ邮箱格式：(\HasNoChildren) "/" "&UXZO1mWHTvZZOQ-/26wlw"
        # 需要提取：&UXZO1mWHTvZZOQ-/26wlw（最后一个引号内的内容）

        if isinstance(folder_string, str):
            # 提取所有引号内的内容，取最后一个
            import re
            matches = re.findall(r'"([^"]+)"', folder_string)
            if matches:
                # 返回最后一个匹配（实际的文件夹路径）
                return matches[-1]

        return folder_string

    def select_folder(self, folder_name: str = 'INBOX') -> bool:
        """选择邮箱文件夹（支持模糊匹配和QQ邮箱前缀）"""
        try:
            if not self.connection:
                if not self.connect():
                    return False

            # 如果是INBOX，直接选择
            if folder_name == 'INBOX':
                status, count = self.connection.select('INBOX')
                if status == 'OK':
                    self.current_folder = 'INBOX'
                    print(f"[PASS] Selected folder 'INBOX', messages: {count[0]}")
                    return True
                return False

            # 查找实际的文件夹名称（可能包含前缀）
            actual_folder = self.find_folder_by_name(folder_name)

            if not actual_folder:
                print(f"[FAIL] Folder '{folder_name}' not found")
                return False

            # 提取QQ邮箱格式的实际路径
            folder_path = self.extract_folder_path(actual_folder)

            # 尝试多种路径格式（QQ邮箱可能有特殊前缀）
            path_attempts = [
                folder_path,                    # 直接使用提取的路径
                f'"{folder_path}"',             # 带引号
            ]

            for attempt_path in path_attempts:
                try:
                    status, count = self.connection.select(attempt_path)
                    if status == 'OK':
                        self.current_folder = folder_path
                        print(f"[PASS] Selected folder '{folder_path}' (matched '{folder_name}')")
                        print(f"       Messages in folder: {count[0]}")
                        return True
                except Exception as e:
                    # 继续尝试下一个路径
                    continue

            print(f"[FAIL] Failed to select folder '{folder_name}'")
            return False

        except Exception as e:
            print(f"[FAIL] Error selecting folder '{folder_name}': {e}")
            return False

    def get_unseen_emails(self) -> List[str]:
        """获取所有未读邮件的UID列表"""
        try:
            if not self.current_folder:
                if not self.select_folder():
                    return []

            status, messages = self.connection.search(None, 'UNSEEN')

            if status != 'OK':
                return []

            email_ids = messages[0].split()
            return [uid.decode() for uid in email_ids]

        except Exception as e:
            print(f"Error getting unseen emails: {e}")
            return []

    def fetch_email(self, email_uid: str) -> Optional[Dict]:
        """获取邮件完整内容"""
        try:
            # 确保已经选择了文件夹
            if not self.current_folder:
                if not self.select_folder('INBOX'):
                    print(f"Error: No folder selected before fetching email {email_uid}")
                    return None

            status, msg_data = self.connection.fetch(email_uid, '(RFC822)')

            if status != 'OK':
                print(f"Error fetching email {email_uid}: IMAP status {status}")
                return None

            # 检查响应数据结构
            if not msg_data or len(msg_data) == 0:
                print(f"Error fetching email {email_uid}: No data returned from IMAP")
                return None

            # 尝试解析邮件内容，处理不同的响应格式
            try:
                # 标准格式: [(response, content), ...]
                if isinstance(msg_data[0], tuple) and len(msg_data[0]) >= 2:
                    raw_email = msg_data[0][1]
                # 备选格式: 可能只有response没有content
                elif len(msg_data) >= 2 and isinstance(msg_data[1], bytes):
                    raw_email = msg_data[1]
                else:
                    print(f"Error fetching email {email_uid}: Unexpected IMAP response format, msg_data={msg_data}")
                    return None
            except (IndexError, TypeError) as e:
                print(f"Error fetching email {email_uid}: Cannot parse IMAP response - {e}")
                return None

            if not raw_email:
                print(f"Error fetching email {email_uid}: Email content is empty")
                return None

            email_message = email.message_from_bytes(raw_email)

            # 提取邮件信息
            email_data = {
                'uid': email_uid,
                'message_id': self.decode_header(email_message['Message-ID']),
                'subject': self.decode_header(email_message['Subject']),
                'from': self.decode_header(email_message['From']),
                'to': self.decode_header(email_message['To']),
                'date': email_message['Date'],
                'message': email_message,
                'raw': raw_email
            }

            return email_data

        except Exception as e:
            print(f"Error fetching email {email_uid}: {e}")
            return None

    def extract_attachments(self, email_message) -> List[Dict]:
        """提取邮件附件"""
        attachments = []

        try:
            for part in email_message.walk():
                if part.get_content_disposition() == 'attachment':
                    filename = part.get_filename()

                    if filename:
                        filename = self.decode_header(filename)
                        content = part.get_payload(decode=True)

                        attachments.append({
                            'filename': filename,
                            'content': content,
                            'content_type': part.get_content_type(),
                            'size': len(content) if content else 0
                        })

        except Exception as e:
            print(f"Error extracting attachments: {e}")

        return attachments

    def mark_as_read(self, email_uid: str) -> bool:
        """标记邮件为已读"""
        try:
            # 确保已经选择了文件夹
            if not self.current_folder:
                if not self.select_folder('INBOX'):
                    return False

            self.connection.store(email_uid, '+FLAGS', '\\Seen')
            return True

        except Exception as e:
            print(f"Error marking email as read: {e}")
            return False

    def move_email(self, email_uid: str, target_folder: str) -> bool:
        """移动邮件到目标文件夹（支持QQ邮箱前缀格式）"""
        try:
            # 确保已经选择了文件夹
            if not self.current_folder:
                if not self.select_folder('INBOX'):
                    return False

            # 查找实际的文件夹名称（可能包含前缀）
            actual_folder = self.find_folder_by_name(target_folder)

            if not actual_folder:
                # 如果找不到，尝试使用原名称
                print(f"[WARN] Folder '{target_folder}' not found in list, trying direct use")
                folder_path = target_folder
            else:
                # 提取QQ邮箱格式的实际路径
                folder_path = self.extract_folder_path(actual_folder)

            # QQ邮箱使用COPY + STORE组合来移动邮件
            # 先复制到目标文件夹
            self.connection.copy(email_uid, folder_path)

            # 然后标记为删除并删除（相当于移动）
            self.connection.store(email_uid, '+FLAGS', '\\Deleted')
            self.connection.expunge()

            print(f"[PASS] Email {email_uid} moved to '{folder_path}'")
            return True

        except Exception as e:
            print(f"[FAIL] Error moving email {email_uid} to {target_folder}: {e}")
            return False

    def delete_email(self, email_uid: str) -> bool:
        """删除邮件"""
        try:
            # 确保已经选择了文件夹
            if not self.current_folder:
                if not self.select_folder('INBOX'):
                    return False

            self.connection.store(email_uid, '+FLAGS', '\\Deleted')
            self.connection.expunge()
            return True

        except Exception as e:
            print(f"Error deleting email: {e}")
            return False

    def create_folder(self, folder_name: str) -> bool:
        """创建新文件夹"""
        try:
            # QQ邮箱的文件夹通常有前缀，直接创建可能不成功
            # 先尝试直接创建
            try:
                self.connection.create(folder_name)
                print(f"Folder '{folder_name}' created successfully")
                return True
            except Exception as e:
                print(f"Direct creation failed: {e}, trying with prefix...")
                # QQ邮箱可能会自动添加前缀，这里记录一下
                # 实际使用中，文件夹通常在移动邮件时自动创建
                print(f"Note: QQ邮箱 may auto-create folders during email operations")
                return False

        except Exception as e:
            print(f"Error creating folder {folder_name}: {e}")
            return False

    def folder_exists(self, folder_name: str) -> bool:
        """检查文件夹是否存在"""
        try:
            status, folders = self.connection.list()
            if status == 'OK':
                for folder in folders:
                    if folder_name in folder.decode():
                        return True
            return False

        except Exception as e:
            print(f"Error checking folder existence: {e}")
            return False

    def decode_header(self, header_value: Optional[str]) -> str:
        """解码邮件头"""
        if not header_value:
            return ""

        try:
            decoded_parts = decode_header(header_value)
            result = ""

            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        result += part.decode(encoding)
                    else:
                        result += part.decode('utf-8', errors='ignore')
                else:
                    result += part

            return result.strip()

        except Exception as e:
            print(f"Error decoding header: {e}")
            return header_value if header_value else ""

    def get_sender_info(self, from_header: str) -> Dict[str, str]:
        """解析发件人信息"""
        if not from_header:
            return {'email': '', 'name': ''}

        try:
            # 格式: "Name <email@example.com>" 或 "email@example.com"
            if '<' in from_header and '>' in from_header:
                name_part = from_header[:from_header.index('<')].strip()
                email_part = from_header[from_header.index('<')+1:from_header.index('>')].strip()

                # 移除引号
                name = name_part.strip('"').strip("'")

                return {
                    'email': email_part,
                    'name': name if name else email_part
                }
            else:
                return {
                    'email': from_header.strip(),
                    'name': from_header.strip()
                }

        except Exception as e:
            print(f"Error parsing sender info: {e}")
            return {'email': from_header, 'name': from_header}

    def get_all_email_headers(self) -> list:
        """获取当前文件夹所有邮件的基本信息（不获取完整内容，提升性能）"""
        try:
            if not self.current_folder:
                if not self.select_folder():
                    return []

            # 搜索所有邮件（不限制UNSEEN）
            status, messages = self.connection.search(None, 'ALL')

            if status != 'OK':
                return []

            email_ids = messages[0].split()
            emails = []

            print(f"正在获取 {len(email_ids)} 封邮件的基本信息...")

            # 批量获取邮件基本信息（使用 FETCH 获取头部）
            batch_size = 100  # 每批处理100封
            for i in range(0, len(email_ids), batch_size):
                batch_ids = email_ids[i:i+batch_size]
                batch_str = b','.join(batch_ids)

                # 只获取邮件头部信息（UID、主题、发件人、日期）
                status, msg_data = self.connection.fetch(batch_str, '(UID RFC822.HEADER)')

                if status != 'OK':
                    continue

                # 解析返回的数据
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        header_data = response_part[1]

                        # 从header中提取基本信息
                        import email
                        from email.message import EmailMessage

                        msg = email.message_from_bytes(header_data)

                        # 提取UID - IMAP响应格式: "1 (UID 123 RFC822.HEADER {size})"
                        uid = None
                        if isinstance(response_part[0], bytes):
                            response_str = response_part[0].decode()
                            # 解析UID，从响应中提取"UID"后面的数字
                            import re
                            uid_match = re.search(r'UID\s+(\d+)', response_str)
                            if uid_match:
                                uid = uid_match.group(1)

                        # 提取基本信息
                        email_data = {
                            'uid': uid,
                            'message_id': self.decode_header(msg.get('Message-ID', '')),
                            'subject': self.decode_header(msg.get('Subject', '')),
                            'from': msg.get('From', ''),
                            'to': msg.get('To', ''),
                            'date': msg.get('Date', ''),
                            'message': None,  # 不获取完整邮件内容
                            'raw': header_data
                        }

                        emails.append(email_data)

                # 显示进度
                processed = min(i + batch_size, len(email_ids))
                print(f"已处理 {processed}/{len(email_ids)} 封邮件...")

            print(f"成功获取 {len(emails)} 封邮件的基本信息")
            return emails

        except Exception as e:
            print(f"Error getting email headers: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_all_emails(self) -> list:
        """获取当前文件夹所有邮件（包括已读）"""
        try:
            if not self.current_folder:
                if not self.select_folder():
                    return []

            # 搜索所有邮件（不限制UNSEEN）
            status, messages = self.connection.search(None, 'ALL')

            if status != 'OK':
                return []

            email_ids = messages[0].split()
            emails = []

            print(f"警告: 即将完整获取 {len(email_ids)} 封邮件，这可能需要较长时间...")
            print(f"建议: 使用 get_all_email_headers() 方法只获取邮件基本信息以提升性能")

            for uid in email_ids:
                email_data = self.fetch_email(uid.decode())
                if email_data:
                    emails.append(email_data)

            return emails
        except Exception as e:
            print(f"Error getting all emails: {e}")
            return []

# 创建两个专用实例
imap_client_inbox = IMAPClient()  # 专门监听INBOX
imap_client_target = IMAPClient()  # 专门访问TARGET_FOLDER
