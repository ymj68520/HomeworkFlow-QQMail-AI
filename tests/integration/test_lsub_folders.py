"""
使用LSUB命令获取QQ邮箱可操作文件夹列表
"""
import imaplib
import ssl
import os
from dotenv import load_dotenv

load_dotenv()

QQ_EMAIL = os.getenv('QQ_EMAIL')
QQ_PASSWORD = os.getenv('QQ_PASSWORD')
TARGET_FOLDER = os.getenv('TARGET_FOLDER')

def test_lsub_folders():
    """测试LSUB命令"""
    print("="*70)
    print("QQ邮箱LSUB命令测试")
    print("="*70)

    try:
        # 连接
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL('imap.qq.com', 993, ssl_context=context)
        mail.login(QQ_EMAIL, QQ_PASSWORD)
        print(f"[SUCCESS] 登录成功")

        # 使用LSUB列出订阅的文件夹
        print(f"\n使用LSUB列出文件夹...")
        try:
            response = mail.lsub()
            print(f"LSUB响应状态: {response[0]}")
            if response[0] == 'OK':
                print(f"找到 {len(response[1])} 个文件夹:")
                for idx, item in enumerate(response[1], 1):
                    print(f"  {idx}. {item}")
        except Exception as e:
            print(f"LSUB错误: {e}")

        # 尝试LSUB列出所有文件夹（包括未订阅的）
        print(f"\n使用LSUB列出所有文件夹...")
        try:
            response = mail.lsub('', '*', '')
            print(f"LSUB '' *响应状态: {response[0]}")
            if response[0] == 'OK':
                print(f"找到 {len(response[1])} 个文件夹:")
                for idx, item in enumerate(response[1], 1):
                    print(f"  {idx}. {item}")
                    # 检查是否包含目标文件夹
                    if TARGET_FOLDER in str(item):
                        print(f"     ^^^ 包含目标文件夹!")
        except Exception as e:
            print(f"LSUB '' *错误: {e}")

        # 尝试STATUS命令查看文件夹状态
        print(f"\n使用STATUS查看文件夹状态...")
        try:
            response = mail.status()
            print(f"STATUS响应: {response}")
            print(f"STATUS响应类型: {type(response)}")
        except Exception as e:
            print(f"STATUS错误: {e}")

        # 尝试EXAMINE命令
        print(f"\n使用EXAMINE命令查看文件夹...")
        try:
            response = mail.examine()
            print(f"EXAMINE响应: {response}")
        except Exception as e:
            print(f"EXAMINE错误: {e}")

        # 尝试直接搜索包含目标文件夹名的邮件
        print(f"\n搜索包含'{TARGET_FOLDER}'的邮件...")
        try:
            mail.select('INBOX')
            # 搜索主题中包含文件夹名的邮件
            status, messages = mail.search(None, f'SUBJECT "{TARGET_FOLDER}"')
            if status == 'OK':
                email_ids = messages[0].split()
                print(f"找到 {len(email_ids)} 封邮件")
                if email_ids and len(email_ids) > 0:
                    print(f"第一封邮件UID: {email_ids[0]}")
            else:
                print(f"搜索状态: {status}")
        except Exception as e:
            print(f"搜索错误: {e}")

        mail.logout()

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_lsub_folders()
