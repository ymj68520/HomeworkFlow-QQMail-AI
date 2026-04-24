"""
测试修复后的QQ邮箱文件夹选择功能
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mail.imap_client import imap_client
from config.settings import settings

def test_folder_selection():
    """测试文件夹选择功能"""
    print("="*70)
    print("QQ邮箱文件夹选择测试（修复版）")
    print("="*70)

    try:
        # 连接
        if not imap_client.connect():
            print("[FAIL] 连接失败")
            return

        print("[PASS] 连接成功")

        # 列出所有文件夹
        folders = imap_client.list_folders()
        print(f"\n[INFO] 找到 {len(folders)} 个文件夹:")
        for idx, folder in enumerate(folders, 1):
            print(f"  {idx}. {folder}")

        # 找到目标文件夹
        target = settings.TARGET_FOLDER
        print(f"\n[INFO] 正在查找目标文件夹: {target}")

        # 尝试选择目标文件夹
        print(f"\n[TEST] 尝试选择文件夹 '{target}'...")
        if imap_client.select_folder(target):
            print("[PASS] 文件夹选择成功!")

            # 获取未读邮件
            print(f"\n[TEST] 获取未读邮件...")
            unseen = imap_client.get_unseen_emails()
            print(f"[INFO] 未读邮件数: {len(unseen)}")

            if unseen:
                print(f"[INFO] 前3封邮件UID:")
                for uid in unseen[:3]:
                    print(f"     {uid}")

            # 搜索所有邮件
            print(f"\n[TEST] 搜索所有邮件...")
            import imaplib
            status, messages = imap_client.connection.search(None, 'ALL')
            if status == 'OK':
                email_ids = messages[0].split()
                print(f"[PASS] 找到 {len(email_ids)} 封邮件")

                if len(email_ids) > 0:
                    print(f"\n[INFO] 获取第一封邮件详情...")
                    email_uid = email_ids[0].decode()
                    email_data = imap_client.fetch_email(email_uid)

                    if email_data:
                        print(f"[PASS] 邮件获取成功")
                        print(f"       主题: {email_data['subject'][:50]}...")
                        print(f"       发件人: {email_data['from'][:50]}...")

                        # 获取附件
                        attachments = imap_client.extract_attachments(email_data['message'])
                        print(f"       附件数: {len(attachments)}")

                        for att in attachments:
                            print(f"         - {att['filename']} ({att['size']} bytes)")
                    else:
                        print("[FAIL] 邮件获取失败")
            else:
                print(f"[FAIL] 搜索失败: {status}")

        else:
            print("[FAIL] 文件夹选择失败")

        imap_client.disconnect()

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_folder_selection()
