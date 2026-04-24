"""
测试TARGET_FOLDER连接和邮件数量
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from mail.imap_client import imap_client_target

def test_target_folder():
    """测试TARGET_FOLDER连接"""
    print("="*60)
    print("TARGET_FOLDER 连接测试")
    print("="*60)
    print(f"邮箱: {settings.QQ_EMAIL}")
    print(f"目标文件夹: {settings.TARGET_FOLDER}")
    print()

    try:
        # 连接
        print("1. 正在连接到邮件服务器...")
        if not imap_client_target.connect():
            print("[失败] 无法连接到邮件服务器")
            return
        print("[成功] 已连接")

        # 选择文件夹
        print(f"\n2. 正在选择文件夹 '{settings.TARGET_FOLDER}'...")
        if not imap_client_target.select_folder(settings.TARGET_FOLDER):
            print(f"[失败] 无法选择文件夹 '{settings.TARGET_FOLDER}'")
            print("提示：请确认该文件夹在QQ邮箱中存在")
            imap_client_target.disconnect()
            return
        print(f"[成功] 已选择文件夹")

        # 获取邮件数量
        print("\n3. 正在获取邮件数量...")
        status, messages = imap_client_target.connection.search(None, 'ALL')
        if status != 'OK':
            print("[失败] 无法搜索邮件")
            imap_client_target.disconnect()
            return

        email_count = len(messages[0].split())
        print(f"[成功] 找到 {email_count} 封邮件")

        if email_count == 0:
            print("\n提示：TARGET_FOLDER 中没有邮件")
            print("建议：")
            print("  1. 先向INBOX发送测试邮件")
            print("  2. 等待系统处理并移动到TARGET_FOLDER")
            print("  3. 然后再启动GUI")
        else:
            print(f"\n提示：TARGET_FOLDER 中有 {email_count} 封邮件")
            print(f"首次加载可能需要 {email_count * 0.1:.1f} 秒...")

        # 断开连接
        imap_client_target.disconnect()
        print("\n测试完成")

    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_target_folder()
