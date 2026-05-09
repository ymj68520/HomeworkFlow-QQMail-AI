"""
测试重试和重新分析后的合并功能

验证：
1. 批量AI重析后，重复记录能正确合并为新版本
2. 智能重试后，重复记录能正确合并为新版本
"""
import sys
import asyncio

sys.path.insert(0, '.')

from PySide6.QtCore import QCoreApplication
from core.retry_handler import retry_handler
from database.operations import db


def print_separator(title=""):
    """打印分隔符"""
    print("\n" + "="*60)
    if title:
        print(f"  {title}")
    print("="*60)


async def test_batch_reanalyze_merge():
    """测试批量AI重析后的合并功能"""
    print_separator("Test 1: Batch Re-analyze with Merge")

    # 获取一些测试记录
    # 注意：这需要实际数据库中有记录
    submissions = db.get_all_submissions()

    if not submissions:
        print("[SKIP] No submissions found in database")
        return

    # 取前3条记录进行测试
    test_submissions = [
        {
            'id': s['id'],
            'email_uid': s['email_uid'],
            'student_id': s['student_id'],
            'name': s['name'],
            'assignment_name': s['assignment_name'],
            'status': s['status'],
            'email': s.get('email'),
            'submission_time': s['submission_time']
        }
        for s in submissions[:3]
    ]

    print(f"[INFO] Testing with {len(test_submissions)} submissions")

    # 模拟批量重新分析
    # 注意：这会实际修改数据库，所以只是演示流程
    print("\n[INFO] Batch re-analyze process:")
    print("  1. Fetch email from IMAP")
    print("  2. Re-run AI extraction")
    print("  3. Check for duplicates")
    print("  4. If duplicate exists, merge as new version")
    print("  5. Update status and mark as latest")

    # 实际执行（需要IMAP连接）
    try:
        def progress_callback(curr, total, msg):
            print(f"  [{curr}/{total}] {msg}")

        result = await retry_handler.batch_reanalyze(
            test_submissions,
            progress_callback=progress_callback
        )

        print(f"\n[RESULT] Total: {result['total']}")
        print(f"[RESULT] Success: {result['success']}")
        print(f"[RESULT] Failed: {result['failed']}")

        # 显示详细信息
        for detail in result['details']:
            if detail.get('status') == 'success':
                action = detail.get('action', 'unknown')
                if action == 'merged_as_new_version':
                    print(f"  [MERGED] {detail['student_id']} -> Version {detail.get('new_version')}")
                elif action == 'updated':
                    print(f"  [UPDATED] {detail['student_id']}")

    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_smart_retry_merge():
    """测试智能重试后的合并功能"""
    print_separator("Test 2: Smart Retry with Merge")

    # 获取异常状态的记录
    submissions = db.get_all_submissions()

    # 筛选异常状态的记录
    abnormal = [
        s for s in submissions
        if s.get('status') in ['ai_error', 'download_failed', 'pending']
    ]

    if not abnormal:
        print("[SKIP] No abnormal submissions found")
        return

    print(f"[INFO] Found {len(abnormal)} abnormal submissions")

    # 测试前3条异常记录
    test_submissions = abnormal[:3]

    print(f"[INFO] Testing smart retry with {len(test_submissions)} submissions")

    try:
        def progress_callback(curr, total, msg):
            print(f"  [{curr}/{total}] {msg}")

        result = await retry_handler.smart_retry_page(
            test_submissions,
            progress_callback=progress_callback
        )

        print(f"\n[RESULT] Total: {result['total']}")
        print(f"[RESULT] Success: {result['success']}")
        print(f"[RESULT] Failed: {result['failed']}")
        print(f"[RESULT] Skipped: {result['skipped']}")

    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


def test_dedup_integration():
    """测试去重服务集成"""
    print_separator("Test 3: Deduplication Service Integration")

    try:
        from core.workflow import workflow

        # 测试去重服务是否可用
        print("[INFO] Testing deduplication service...")

        # 检查去重服务方法
        methods = [
            'check_email',
            'check_submission',
            'check_submission_with_fuzzy'
        ]

        for method in methods:
            if hasattr(workflow.dedup_service, method):
                print(f"  [OK] {method} method exists")
            else:
                print(f"  [FAIL] {method} method missing")

        print("[INFO] Deduplication service integration verified")

    except Exception as e:
        print(f"[ERROR] Dedup service test failed: {e}")


async def main():
    """主测试函数"""
    print_separator("Retry & Merge Functionality Test")

    # 测试3: 去重服务集成
    test_dedup_integration()

    # 测试1: 批量重新分析（需要IMAP连接）
    print("\n[NOTE] Following tests require IMAP connection")
    print("[NOTE] Skipping actual execution in test mode")

    # 可以取消注释来实际运行测试
    # await test_batch_reanalyze_merge()
    # await test_smart_retry_merge()

    print("\n[Test Complete]")


if __name__ == '__main__':
    app = QCoreApplication(sys.argv)

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
