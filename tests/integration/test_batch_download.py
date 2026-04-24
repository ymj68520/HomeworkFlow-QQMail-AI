"""
直接测试批量下载的核心逻辑
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_batch_download_logic():
    """测试批量下载逻辑"""
    print("=" * 60)
    print("测试批量下载核心逻辑")
    print("=" * 60)

    try:
        # 1. 获取数据库记录
        print("\n1. 获取数据库记录...")
        from database.operations import db
        submissions = db.get_all_submissions()

        if not submissions:
            print("[ERROR] 数据库中没有记录")
            return False

        print(f"[OK] 获取到 {len(submissions)} 条记录")

        # 取前3条进行测试
        test_submissions = submissions[:3]
        print(f"\n2. 测试前3条记录:")
        for i, sub in enumerate(test_submissions):
            print(f"  {i+1}. UID={sub['email_uid']}")
            print(f"     学号={sub['student_id']}, 姓名={sub['name']}")
            print(f"     作业={sub['assignment_name']}")
            print(f"     本地路径={sub['local_path']}")

        # 3. 连接邮件服务器
        print(f"\n3. 连接到邮件服务器...")
        from mail.parser import mail_parser

        if not mail_parser.connect():
            print("[ERROR] 无法连接到邮件服务器")
            return False
        print("[OK] 邮件服务器连接成功")

        # 4. 逐个测试解析邮件
        print(f"\n4. 测试解析邮件...")
        success_count = 0
        failed_items = []

        for idx, sub in enumerate(test_submissions):
            print(f"\n  [{idx+1}/3] 测试 UID: {sub['email_uid']}")
            print(f"       学号: {sub['student_id']}")

            try:
                # 解析邮件
                email_data = mail_parser.parse_email(sub['email_uid'])

                if not email_data:
                    print(f"       [FAIL] 无法获取邮件数据")
                    failed_items.append(f"{sub['student_id']} - {sub['name']}: 无法获取邮件")
                    continue

                print(f"       [OK] 邮件获取成功")
                print(f"       主题: {email_data.get('subject', 'N/A')}")

                # 检查附件
                attachments = email_data.get('attachments', [])
                print(f"       附件数量: {len(attachments)}")

                if not attachments:
                    print(f"       [WARNING] 无附件")
                    failed_items.append(f"{sub['student_id']} - {sub['name']}: 无附件")
                    continue

                # 显示附件信息
                for att in attachments:
                    print(f"         - {att['filename']} ({att['size']} bytes)")

                print(f"       [OK] 附件提取成功")
                success_count += 1

            except Exception as e:
                print(f"       [ERROR] {str(e)}")
                failed_items.append(f"{sub['student_id']} - {sub['name']}: {str(e)}")

        # 5. 断开连接
        print(f"\n5. 断开连接...")
        mail_parser.disconnect()
        print("[OK] 已断开连接")

        # 6. 显示结果
        print("\n" + "=" * 60)
        print("测试结果")
        print("=" * 60)
        print(f"成功: {success_count} 项")
        print(f"失败: {len(failed_items)} 项")

        if failed_items:
            print("\n失败详情:")
            for item in failed_items:
                print(f"  - {item}")

        print("\n" + "=" * 60)
        return success_count > 0

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n批量下载逻辑测试\n")
    success = test_batch_download_logic()

    if success:
        print("\n[SUCCESS] 测试通过！批量下载功能正常")
    else:
        print("\n[WARNING] 测试未完全成功，请检查上述错误")
        print("\n可能的原因:")
        print("  1. 邮件UID在邮箱中不存在")
        print("  2. 邮件确实没有附件")
        print("  3. 网络连接问题")

if __name__ == '__main__':
    main()
