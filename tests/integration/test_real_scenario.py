# -*- coding: utf-8 -*-
"""
真实场景测试：处理TARGET_FOLDER中的所有邮件
"""
import sys
from pathlib import Path
import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime

sys.path.insert(0, str(Path(__file__).parent))

from mail.imap_client import imap_client
from ai.extractor import ai_extractor
from database.operations import db
from config.settings import settings

def test_real_scenario():
    """测试真实场景：处理所有邮件"""
    print("="*70)
    print("真实场景测试：处理TARGET_FOLDER中的所有邮件")
    print("="*70)

    try:
        # 连接并选择目标文件夹
        if not imap_client.connect():
            print("[FAIL] 连接失败")
            return

        print("[PASS] 连接成功")

        # 选择目标文件夹
        target_folder = settings.TARGET_FOLDER
        if not imap_client.select_folder(target_folder):
            print("[FAIL] 无法选择文件夹: " + target_folder)
            return

        print("[PASS] 成功选择文件夹: " + target_folder)

        # 获取所有邮件
        import imaplib
        status, messages = imap_client.connection.search(None, 'ALL')
        if status != 'OK':
            print("[FAIL] 搜索邮件失败")
            return

        email_ids = messages[0].split()
        print("\n[INFO] 找到 " + str(len(email_ids)) + " 封邮件")

        # 处理每封邮件
        results = {
            'total': len(email_ids),
            'processed': 0,
            'assignments': {},
            'errors': []
        }

        print("\n[INFO] 开始处理邮件...")

        max_process = min(10, len(email_ids))
        for idx in range(max_process):
            try:
                email_uid = email_ids[idx].decode()
                current_num = idx + 1
                print("\n[" + str(current_num) + "/" + str(max_process) + "] 处理邮件 UID: " + email_uid)

                # 获取邮件
                email_data = imap_client.fetch_email(email_uid)
                if not email_data:
                    print("  [WARN] 无法获取邮件")
                    results['errors'].append(email_uid + ": 无法获取邮件")
                    continue

                subject = email_data['subject'][:60] if email_data['subject'] else ""
                sender = email_data['from'][:50] if email_data['from'] else ""
                print("  主题: " + subject + "...")
                print("  发件人: " + sender + "...")

                # 提取附件
                attachments = imap_client.extract_attachments(email_data['message'])
                print("  附件数: " + str(len(attachments)))

                if not attachments:
                    print("  [INFO] 无附件，跳过")
                    continue

                # AI提取学生信息
                attachment_names = [att['filename'] for att in attachments]
                print("  附件文件名: " + str(attachment_names))

                # 使用asyncio运行异步的AI提取
                student_info = asyncio.run(ai_extractor.extract_student_info(
                    email_data['subject'],
                    email_data['from'],
                    attachments  # 传入完整附件信息（不仅仅是文件名）
                ))

                print("  AI提取结果:")
                print("    是作业: " + str(student_info['is_assignment']))
                if student_info['is_assignment']:
                    print("    学号: " + str(student_info['student_id']))
                    print("    姓名: " + str(student_info['name']))
                    print("    作业名: " + str(student_info['assignment_name']))
                    print("    置信度: " + str(round(student_info['confidence'], 2)))

                    # 统计作业
                    assignment_name = student_info['assignment_name']
                    if assignment_name not in results['assignments']:
                        results['assignments'][assignment_name] = 0
                    results['assignments'][assignment_name] += 1
                    results['processed'] += 1

                    # 存储到数据库
                    try:
                        # 解析发件人信息
                        sender_info = imap_client.get_sender_info(email_data['from'])

                        # 解析日期字符串为datetime对象
                        try:
                            if isinstance(email_data['date'], str):
                                submission_time = parsedate_to_datetime(email_data['date'])
                            else:
                                submission_time = email_data['date']
                        except:
                            submission_time = datetime.now()

                        submission = db.create_submission(
                            student_id=student_info['student_id'],
                            assignment_name=assignment_name,
                            email_uid=email_uid,
                            email_subject=email_data['subject'],
                            sender_email=sender_info['email'],
                            sender_name=student_info['name'],  # 使用AI提取的姓名
                            submission_time=submission_time
                        )

                        if submission:
                            # 添加附件记录
                            for att in attachments:
                                db.add_attachment(
                                    submission_id=submission.id,
                                    filename=att['filename'],
                                    file_size=att['size'],
                                    local_path=""  # 暂时为空，后续下载时更新
                                )

                            print("    [PASS] 已存储到数据库 (ID: " + str(submission.id) + ")")
                        else:
                            print("    [WARN] 数据库存储失败")
                    except Exception as e:
                        error_msg = str(e)[:60]
                        print("    [WARN] 数据库存储失败: " + error_msg)
                        results['errors'].append(email_uid + ": " + error_msg)

                else:
                    print("    [INFO] AI判断为非作业邮件，跳过")
                    results['errors'].append(email_uid + ": 非作业邮件")

            except Exception as e:
                error_msg = str(e)[:80]
                print("  [ERROR] 处理失败: " + error_msg)
                email_uid_str = email_ids[idx].decode() if idx < len(email_ids) else "unknown"
                results['errors'].append(email_uid_str + ": " + error_msg)
                import traceback
                traceback.print_exc()

        # 打印统计结果
        print("\n" + "="*70)
        print("处理结果统计")
        print("="*70)
        print("总邮件数: " + str(results['total']))
        print("已处理: " + str(results['processed']))
        print("\n作业分布:")
        for assignment_name, count in results['assignments'].items():
            print("  " + assignment_name + ": " + str(count) + " 封")

        if results['errors']:
            print("\n错误: " + str(len(results['errors'])))
            for error in results['errors'][:5]:
                print("  - " + error)
            if len(results['errors']) > 5:
                print("  ... 还有 " + str(len(results['errors']) - 5) + " 个错误")

        imap_client.disconnect()

    except Exception as e:
        print("\n[ERROR] " + str(e))
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_real_scenario()
