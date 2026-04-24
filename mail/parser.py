from mail.imap_client import imap_client_inbox, imap_client_target
from mail.email_body_extractor import EmailBodyExtractor
from typing import Dict, Optional

class MailParser:
    """邮件解析器 - 整合IMAP客户端和解析逻辑"""

    def __init__(self, imap_client=None):
        self.imap = imap_client

    def connect(self) -> bool:
        """连接到邮箱"""
        return self.imap.connect()

    def disconnect(self):
        """断开连接"""
        self.imap.disconnect()

    def parse_email(self, email_uid: str) -> Optional[Dict]:
        """
        完整解析一封邮件

        Returns:
            {
                'uid': str,
                'subject': str,
                'sender_email': str,
                'sender_name': str,
                'to': str,
                'date': str,
                'has_attachments': bool,
                'attachments': [
                    {
                        'filename': str,
                        'content': bytes,
                        'content_type': str,
                        'size': int
                    },
                    ...
                ],
                'email_body': {
                    'plain_text': str or None,
                    'html_markdown': str or None,
                    'format': 'text', 'html', 'both', or 'empty'
                }
            }
        """
        # 获取邮件
        email_data = self.imap.fetch_email(email_uid)
        if not email_data:
            return None

        # 解析发件人信息
        sender_info = self.imap.get_sender_info(email_data['from'])

        # 提取附件
        attachments = self.imap.extract_attachments(email_data['message'])

        # 提取邮件正文
        extractor = EmailBodyExtractor()
        email_body = extractor.extract_body(email_data['message'])

        return {
            'uid': email_data['uid'],
            'subject': email_data['subject'],
            'sender_email': sender_info['email'],
            'sender_name': sender_info['name'],
            'to': email_data['to'],
            'date': email_data['date'],
            'has_attachments': len(attachments) > 0,
            'attachments': attachments,
            'email_body': email_body
        }

    def get_new_emails(self) -> list:
        """获取所有未读邮件并解析"""
        # 获取未读邮件UID列表
        unseen_uids = self.imap.get_unseen_emails()

        parsed_emails = []
        for uid in unseen_uids:
            parsed = self.parse_email(uid)
            if parsed:
                parsed_emails.append(parsed)

        return parsed_emails

    def mark_as_read(self, email_uid: str) -> bool:
        """标记邮件为已读"""
        return self.imap.mark_as_read(email_uid)

    def move_to_folder(self, email_uid: str, folder_name: str) -> bool:
        """移动邮件到指定文件夹"""
        return self.imap.move_email(email_uid, folder_name)

    def delete_email(self, email_uid: str) -> bool:
        """删除邮件"""
        return self.imap.delete_email(email_uid)

    def uid_exists(self, uid: str) -> bool:
        """
        Check if an email UID still exists in the current folder

        Args:
            uid: Email UID to check

        Returns:
            True if UID exists, False otherwise
        """
        try:
            # Try to fetch the email to see if it exists
            result = self.imap.uid('FETCH', uid, '(UID)')
            return bool(result)
        except Exception:
            return False

# 创建两个专用解析器实例
mail_parser_inbox = MailParser(imap_client_inbox)
mail_parser_target = MailParser(imap_client_target)
