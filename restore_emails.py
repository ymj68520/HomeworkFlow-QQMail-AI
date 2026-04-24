import imaplib
import email
from mail.imap_client import IMAPClient
from config.settings import settings

def restore_emails():
    """将目标文件夹中的所有邮件移回收件箱并标记为未读"""
    client = IMAPClient()
    if not client.connect():
        print("无法连接到邮箱")
        return

    target_folder = settings.TARGET_FOLDER
    print(f"正在从 '{target_folder}' 恢复邮件到 'INBOX'...")

    try:
        # 选择目标文件夹
        if not client.select_folder(target_folder):
            print(f"无法选择文件夹: {target_folder}，可能已为空或不存在。")
            return

        # 搜索所有邮件
        status, messages = client.connection.search(None, 'ALL')
        if status != 'OK' or not messages[0]:
            print("文件夹中没有邮件。")
            return

        uids = messages[0].split()
        print(f"找到 {len(uids)} 封邮件，准备恢复...")

        for uid in uids:
            uid_str = uid.decode()
            # 复制到 INBOX
            client.connection.copy(uid_str, 'INBOX')
            # 在 INBOX 中标记为未读（需要重新连接或切换文件夹来操作新副本，
            # 但更简单的方法是先移过去，然后让 process_inbox 整体扫描）
            # 实际上 copy 过去的邮件在 INBOX 中默认就是未读的（如果原始邮件是未读的话）
            # 为了保险，我们稍后在 INBOX 中统一处理
            
            # 标记原邮件为删除
            client.connection.store(uid_str, '+FLAGS', '\\Deleted')

        # 彻底删除原文件夹中的邮件
        client.connection.expunge()
        print(f"成功将 {len(uids)} 封邮件移回 INBOX。")

        # 切换到 INBOX 确保它们都是未读状态
        client.select_folder('INBOX')
        status, messages = client.connection.search(None, 'ALL')
        if status == 'OK' and messages[0]:
            uids = messages[0].split()
            for uid in uids:
                client.connection.store(uid, '-FLAGS', '\\Seen')
            print("已将收件箱中的所有邮件标记为未读。")

    except Exception as e:
        print(f"恢复邮件时出错: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    restore_emails()
