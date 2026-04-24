"""
调试find_folder_by_name方法
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mail.imap_client import imap_client
from config.settings import settings

def test_find_folder():
    """测试find_folder_by_name方法"""
    print("="*70)
    print("find_folder_by_name方法调试")
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
        print(f"\n[INFO] 目标文件夹名: {target}")

        # 测试find_folder_by_name方法
        print(f"\n[TEST] 调用find_folder_by_name('{target}')...")
        matched_folder = imap_client.find_folder_by_name(target)

        if matched_folder:
            print(f"[PASS] 找到匹配: {matched_folder}")
            print(f"       类型: {type(matched_folder)}")
            print(f"       长度: {len(matched_folder)}")

            # 测试extract_folder_path方法
            print(f"\n[TEST] 调用extract_folder_path()...")
            extracted_path = imap_client.extract_folder_path(matched_folder)
            print(f"[PASS] 提取的路径: {extracted_path}")

            # 尝试不同的选择方式
            print(f"\n[TEST] 尝试选择文件夹...")

            # 方式1: 使用提取的路径
            try:
                print(f"  方式1: '{extracted_path}'")
                status, count = imap_client.connection.select(extracted_path)
                print(f"     状态: {status}, 邮件数: {count[0]}")
                if status == 'OK':
                    print(f"     [PASS] 成功!")
            except Exception as e:
                print(f"     [FAIL] 错误: {str(e)[:80]}")

            # 方式2: 使用带引号的路径
            try:
                print(f"  方式2: '\"{extracted_path}\"'")
                status, count = imap_client.connection.select(f'"{extracted_path}"')
                print(f"     状态: {status}, 邮件数: {count[0]}")
                if status == 'OK':
                    print(f"     [PASS] 成功!")
            except Exception as e:
                print(f"     [FAIL] 错误: {str(e)[:80]}")

        else:
            print(f"[FAIL] 未找到匹配的文件夹")

        imap_client.disconnect()

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_find_folder()
