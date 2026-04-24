"""
直接使用QQ邮箱文件夹完整路径进行测试
"""
import imaplib
import ssl
import os
from dotenv import load_dotenv

load_dotenv()

QQ_EMAIL = os.getenv('QQ_EMAIL')
QQ_PASSWORD = os.getenv('QQ_PASSWORD')
TARGET_FOLDER = os.getenv('TARGET_FOLDER')

def test_direct_path():
    """直接路径测试"""
    print("="*70)
    print("QQ邮箱文件夹直接路径测试")
    print("="*70)

    try:
        # 连接
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL('imap.qq.com', 993, ssl_context=context)
        mail.login(QQ_EMAIL, QQ_PASSWORD)
        print(f"[SUCCESS] 登录成功")

        # 尝试不同的路径格式来选择26wlw文件夹
        possible_paths = [
            TARGET_FOLDER,
            f'"{TARGET_FOLDER}"',
            f'&UXZO1mWHTvZZOQ-/{TARGET_FOLDER}',
            f'"{TARGET_FOLDER}"',
            f'/"&UXZO1mWHTvZZOQ-/{TARGET_FOLDER}',
            f'"&UXZO1mWHTvZZOQ-/{TARGET_FOLDER}"',
            f'/" "&UXZO1mWHTvZZOQ-/{TARGET_FOLDER}"',
        ]

        print(f"\n尝试 {len(possible_paths)} 种路径格式...")
        for idx, path in enumerate(possible_paths, 1):
            print(f"\n{idx}. 尝试路径: {path}")
            try:
                status, data = mail.select(path)
                print(f"   状态: {status}")
                if status == 'OK':
                    print(f"   [SUCCESS] 成功! 邮件数: {data[0]}")
                    print(f"   当前文件夹: {mail.folder}")

                    # 获取该文件夹中的邮件
                    search_status, search_data = mail.search(None, 'ALL')
                    if search_status == 'OK':
                        email_ids = search_data[0].split()
                        print(f"   邮件数: {len(email_ids)}")

                        if len(email_ids) > 0:
                            print(f"\n   前3封邮件UID:")
                            for uid in email_ids[:3]:
                                print(f"     {uid}")
                            break

                    mail.close()
                    mail.logout()
                    return True
                else:
                    print(f"   失败原因: {data}")
            except Exception as e:
                print(f"   错误: {str(e)[:80]}")

        mail.close()
        mail.logout()

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_direct_path()
