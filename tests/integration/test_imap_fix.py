"""
测试IMAP修复的脚本
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_imap_connection():
    """测试IMAP连接和文件夹选择"""
    print("=" * 60)
    print("测试IMAP连接和文件夹选择")
    print("=" * 60)

    try:
        from mail.imap_client import imap_client

        # 测试连接
        print("\n1. 测试连接...")
        if imap_client.connect():
            print("[OK] 成功连接到IMAP服务器")
        else:
            print("[FAIL] 无法连接到IMAP服务器")
            return False

        # 测试选择文件夹
        print("\n2. 测试选择INBOX...")
        if imap_client.select_folder('INBOX'):
            print(f"[OK] 成功选择INBOX文件夹")
            print(f"      当前文件夹: {imap_client.current_folder}")
        else:
            print("[FAIL] 无法选择INBOX文件夹")
            return False

        # 测试获取邮件
        print("\n3. 测试获取邮件...")
        from database.operations import db
        submissions = db.get_all_submissions()

        if not submissions:
            print("[WARNING] 数据库中没有记录，无法测试获取邮件")
            print("          但IMAP连接和文件夹选择已验证成功")
            return True

        # 获取第一条记录的UID进行测试
        test_uid = submissions[0]['email_uid']
        print(f"      测试UID: {test_uid}")

        email_data = imap_client.fetch_email(test_uid)
        if email_data:
            print(f"[OK] 成功获取邮件")
            print(f"      主题: {email_data['subject']}")
            print(f"      发件人: {email_data['from']}")
            print(f"      是否有附件: {len(imap_client.extract_attachments(email_data['message'])) > 0}")
        else:
            print(f"[FAIL] 无法获取邮件 {test_uid}")
            return False

        # 断开连接
        print("\n4. 断开连接...")
        imap_client.disconnect()
        print("[OK] 已断开连接")

        print("\n" + "=" * 60)
        print("[SUCCESS] 所有测试通过！")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\nIMAP修复验证测试\n")

    success = test_imap_connection()

    if success:
        print("\n✓ IMAP修复已验证！")
        print("✓ 现在可以正常使用批量下载功能了")
        print("\n提示：如果仍有问题，请检查：")
        print("  1. 邮箱配置是否正确（.env文件）")
        print("  2. 网络连接是否正常")
        print("  3. 邮箱中的邮件是否存在")
    else:
        print("\n✗ 测试失败，请检查错误信息")

if __name__ == '__main__':
    main()
