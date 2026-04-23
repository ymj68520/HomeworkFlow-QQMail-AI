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
    # 连接到TARGET_FOLDER
    if not imap_client_target.connect():
        raise ConnectionError("无法连接到TARGET_FOLDER")

    if not imap_client_target.select_folder(settings.TARGET_FOLDER):
        raise FileNotFoundError(f"TARGET_FOLDER '{settings.TARGET_FOLDER}' 不存在")

    # 获取所有邮件
    parser = MailParser(imap_client_target)
    all_emails = imap_client_target.get_all_email_headers()

    print(f"找到 {len(all_emails)} 封邮件")

    # 批量处理
    batch_size = 10
    results = []

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
            save_submission(email_data, result)

    imap_client_target.disconnect()
    print(f"✓ 完成 {len(results)} 条记录")

def save_submission(email_data, extraction_result):
    """保存提交记录到数据库"""
    from datetime import datetime

    student_id = extraction_result.get('student_id')
    name = extraction_result.get('name')
    assignment_name = extraction_result.get('assignment_name')

    if not student_id or not name or assignment_name == 'Unknown':
        print(f"跳过: 提取失败 - {email_data.get('subject', '')}")
        return

    # 创建或获取学生记录
    student = db.get_or_create_student(student_id, name, email_data.get('from', ''))

    # 创建或获取作业记录
    assignment = db.get_or_create_assignment(assignment_name)

    # 创建提交记录
    db.create_submission(
        student_id=student,
        assignment_name=assignment_name,
        email_uid=email_data.get('uid'),
        email_subject=email_data.get('subject', ''),
        submission_time=datetime.now()
    )

if __name__ == '__main__':
    print("开始使用AI批量填充数据库...")
    asyncio.run(backfill_with_ai())
