"""
测试QQ邮箱文件夹前缀处理
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mail.imap_client import imap_client
from config.settings import settings

def test_folder_handling():
    """测试文件夹处理"""
    print("="*70)
    print("QQ邮箱文件夹前缀处理测试")
    print("="*70)

    # 显示配置
    print(f"\n配置信息:")
    print(f"  QQ邮箱: {settings.QQ_EMAIL}")
    print(f"  目标文件夹: {settings.TARGET_FOLDER}")

    try:
        # 连接到邮箱
        print(f"\n正在连接到QQ邮箱...")
        if not imap_client.connect():
            print("[FAIL] 连接邮箱失败")
            return False

        print("[SUCCESS] 邮箱连接成功")

        # 列出所有文件夹
        print(f"\n正在获取所有文件夹...")
        folders = imap_client.list_folders()

        print(f"\n找到 {len(folders)} 个文件夹:")
        for idx, folder in enumerate(folders, 1):
            print(f"  {idx}. {folder}")

        # 查找目标文件夹
        target_folder = settings.TARGET_FOLDER
        print(f"\n正在查找目标文件夹: {target_folder}")

        matched_folder = imap_client.find_folder_by_name(target_folder)

        if matched_folder:
            print(f"[SUCCESS] 找到匹配的文件夹: {matched_folder}")

            # 尝试选择该文件夹
            print(f"\n正在选择文件夹: {matched_folder}")
            if imap_client.select_folder(target_folder):  # 使用函数名匹配
                print(f"[SUCCESS] 文件夹选择成功")

                # 获取邮件数量
                print(f"\n正在获取邮件信息...")
                # 重新选择以获取邮件数量
                if imap_client.connection.select(matched_folder)[0] == 'OK':
                    status, messages = imap_client.connection.search(None, 'ALL')
                    if status == 'OK':
                        email_ids = messages[0].split()
                        print(f"[INFO] 该文件夹中有 {len(email_ids)} 封邮件")
            else:
                print("[FAIL] 文件夹选择失败")
        else:
            print(f"[INFO] 未找到匹配的文件夹: {target_folder}")
            print(f"[INFO] 这可能是因为:")
            print(f"  1. 文件夹名称不匹配")
            print(f"  2. 文件夹确实不存在")
            print(f"  3. 需要手动创建文件夹")

        # 断开连接
        imap_client.disconnect()

        print(f"\n{'='*70}")
        print("测试完成")
        print(f"{'='*70}")

        return True

    except Exception as e:
        print(f"\n[ERROR] 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_folder_handling()
    sys.exit(0 if success else 1)
