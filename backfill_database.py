"""
使用AI批量填充数据库
从TARGET_FOLDER提取历史邮件数据并填充到数据库
"""
import asyncio
from mail.imap_client import imap_client_target
from mail.parser import MailParser
from config.settings import settings
from database.operations import db
from ai.extractor import ai_extractor
from tqdm import tqdm

async def backfill_with_ai():
    """使用AI批量提取并填充数据库"""
    try:
        # 连接到TARGET_FOLDER
        if not imap_client_target.connect():
            raise ConnectionError("无法连接到TARGET_FOLDER")

        if not imap_client_target.select_folder(settings.TARGET_FOLDER):
            raise FileNotFoundError(f"TARGET_FOLDER '{settings.TARGET_FOLDER}' 不存在")

        # 获取所有邮件
        all_emails = imap_client_target.get_all_email_headers()

        print(f"找到 {len(all_emails)} 封邮件")

        # 批量处理
        batch_size = 10
        success_count = 0
        error_count = 0

        for i in tqdm(range(0, len(all_emails), batch_size), desc="Processing emails"):
            batch = all_emails[i:i+batch_size]

            # 准备批量提取的数据
            email_batch = []
            for email_data in batch:
                email_batch.append({
                    'uid': email_data.get('uid'),
                    'subject': email_data.get('subject', ''),
                    'from': email_data.get('from', ''),
                    'attachments': []
                })

            # 批量AI提取
            batch_results = await ai_extractor.batch_extract(email_batch)

            # 保存到数据库
            for email_data, result in zip(batch, batch_results):
                if save_submission(email_data, result):
                    success_count += 1
                else:
                    error_count += 1

        print(f"✓ 完成: 成功 {success_count} 条, 失败 {error_count} 条")
        return success_count, error_count

    except Exception as e:
        print(f"✗ 批量填充失败: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0
    finally:
        # 确保断开IMAP连接
        try:
            imap_client_target.disconnect()
        except:
            pass

def save_submission(email_data, extraction_result):
    """保存提交记录到数据库

    Args:
        email_data: Dict with 'uid', 'subject', 'from' keys
        extraction_result: Dict with 'student_id', 'name', 'assignment_name' keys

    Returns:
        bool: True if successful, False otherwise
    """
    from datetime import datetime
    from email.utils import parseaddr

    try:
        student_id = extraction_result.get('student_id')
        name = extraction_result.get('name')
        assignment_name = extraction_result.get('assignment_name')

        # 验证必需字段
        if not student_id or not name or not assignment_name or assignment_name == 'Unknown':
            print(f"跳过: 提取失败 - {email_data.get('subject', '')}")
            return False

        # 解析发件人邮箱
        sender_email = email_data.get('from', '')
        # 如果from字段包含 "Name <email>" 格式，提取邮箱
        if '<' in sender_email and '>' in sender_email:
            sender_email = parseaddr(sender_email)[1]

        # 使用正确的数据库API创建提交记录
        # create_submission会自动创建或获取student和assignment记录
        submission = db.create_submission(
            student_id=student_id,
            assignment_name=assignment_name,
            email_uid=str(email_data.get('uid', '')),
            email_subject=email_data.get('subject', ''),
            sender_email=sender_email,
            sender_name=name,
            submission_time=datetime.now(),
            version=1,
            is_latest=True
        )

        if submission:
            return True
        else:
            print(f"跳过: 数据库保存失败 - {email_data.get('subject', '')}")
            return False

    except Exception as e:
        print(f"保存失败: {email_data.get('subject', '')} - {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("开始使用AI批量填充数据库...")
    asyncio.run(backfill_with_ai())
