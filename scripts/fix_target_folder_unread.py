#!/usr/bin/env python
"""
修复脚本：将TARGET_FOLDER中的所有邮件标记为已读

用途：修复因move_email()没有标记已读而导致的问题，
     防止已处理的邮件被重复检测为新邮件
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mail.imap_client import imap_client_target
from config.settings import settings

def fix_target_folder_unread():
    """将TARGET_FOLDER中的所有邮件标记为已读"""

    print(f"开始修复 {settings.TARGET_FOLDER} 中的未读邮件...")

    # 连接到邮箱
    if not imap_client_target.connect():
        print("无法连接到邮箱")
        return False

    try:
        # 选择目标文件夹
        if not imap_client_target.select_folder(settings.TARGET_FOLDER):
            print(f"无法选择文件夹: {settings.TARGET_FOLDER}")
            return False

        # 获取所有未读邮件
        print(f"正在搜索 {settings.TARGET_FOLDER} 中的未读邮件...")
        status, messages = imap_client_target.connection.uid('search', None, 'UNSEEN')

        if status != 'OK':
            print("搜索未读邮件失败")
            return False

        unseen_uids = messages[0].split()

        if not unseen_uids:
            print(f"✓ {settings.TARGET_FOLDER} 中没有未读邮件")
            return True

        print(f"找到 {len(unseen_uids)} 封未读邮件，正在标记为已读...")

        # 标记所有未读邮件为已读
        success_count = 0
        for uid in unseen_uids:
            try:
                uid_str = uid.decode()
                imap_client_target.connection.uid('store', uid_str, '+FLAGS', '\\Seen')
                success_count += 1
                if success_count <= 5 or success_count % 20 == 0:
                    print(f"  [OK] 已标记 {success_count}/{len(unseen_uids)}")
            except Exception as e:
                print(f"  [FAIL] UID {uid}: {e}")

        print(f"\n完成！已将 {success_count}/{len(unseen_uids)} 封邮件标记为已读")
        return True

    except Exception as e:
        print(f"修复过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        imap_client_target.disconnect()

if __name__ == "__main__":
    print("=" * 50)
    print("TARGET_FOLDER 未读邮件修复工具")
    print("=" * 50)
    print(f"目标文件夹: {settings.TARGET_FOLDER}")
    print()

    success = fix_target_folder_unread()

    print()
    print("=" * 50)
    if success:
        print("修复完成！")
        print("\n提示：请重启应用程序以使更改生效")
    else:
        print("修复失败！请检查错误信息")
    print("=" * 50)
