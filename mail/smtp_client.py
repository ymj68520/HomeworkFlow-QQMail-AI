import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime
from typing import Optional
from config.settings import settings

class SMTPClient:
    def __init__(self):
        self.host = settings.SMTP_SERVER
        self.port = settings.SMTP_PORT
        self.email = settings.QQ_EMAIL
        self.password = settings.QQ_PASSWORD
        self.connection = None

    def connect(self) -> bool:
        """连接到QQ邮箱SMTP服务器"""
        try:
            context = ssl.create_default_context()
            self.connection = smtplib.SMTP(self.host, self.port)
            self.connection.starttls(context=context)
            self.connection.login(self.email, self.password)
            return True

        except Exception as e:
            print(f"SMTP connection error: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.connection:
            try:
                self.connection.quit()
            except:
                pass
            self.connection = None

    def send_reply(
        self,
        to_email: str,
        student_name: str,
        assignment_name: str,
        custom_message: Optional[str] = None
    ) -> bool:
        """
        发送确认回复邮件

        Args:
            to_email: 收件人邮箱
            student_name: 学生姓名
            assignment_name: 作业名称
            custom_message: 自定义消息（可选）
        """
        if not settings.ENABLE_REPLY:
            print("DEBUG: SMTPClient.send_reply called but feature is disabled in settings.")
            return False

        try:
            if not self.connection:
                if not self.connect():
                    return False

            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = formataddr(("助教", self.email))
            msg['To'] = to_email
            msg['Subject'] = f"收到确认：{assignment_name} - {student_name}"

            # 邮件正文
            body = self.generate_reply_body(student_name, assignment_name, custom_message)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # 发送邮件
            self.connection.send_message(msg)
            print(f"Reply sent to {to_email}")
            return True

        except Exception as e:
            print(f"Error sending reply to {to_email}: {e}")
            return False

    def generate_reply_body(
        self,
        student_name: str,
        assignment_name: str,
        custom_message: Optional[str] = None
    ) -> str:
        """生成回复邮件正文"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        body = f"""{student_name}同学：

你的{assignment_name}已收到并确认。

"""

        if custom_message:
            body += f"{custom_message}\n\n"

        body += f"""如有问题，请联系助教。

祝学习顺利！

助教
{timestamp}
"""

        return body

    def send_batch_replies(
        self,
        recipients: list,
        delay: float = 2.0
    ) -> dict:
        """
        批量发送回复邮件

        Args:
            recipients: 收件人列表 [{'email': ..., 'name': ..., 'assignment': ...}, ...]
            delay: 发送间隔（秒）

        Returns:
            {'success': int, 'failed': int, 'details': list}
        """
        if not self.connection:
            if not self.connect():
                return {'success': 0, 'failed': len(recipients), 'details': []}

        import time

        results = {'success': 0, 'failed': 0, 'details': []}

        for recipient in recipients:
            try:
                success = self.send_reply(
                    to_email=recipient['email'],
                    student_name=recipient['name'],
                    assignment_name=recipient['assignment']
                )

                if success:
                    results['success'] += 1
                    results['details'].append({'email': recipient['email'], 'status': 'success'})
                else:
                    results['failed'] += 1
                    results['details'].append({'email': recipient['email'], 'status': 'failed'})

                # 延迟避免触发速率限制
                if delay > 0:
                    time.sleep(delay)

            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'email': recipient['email'],
                    'status': 'error',
                    'error': str(e)
                })

        return results

# Global SMTP client instance
smtp_client = SMTPClient()
