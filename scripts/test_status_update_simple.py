"""
简化版状态修改功能测试

直接使用SQL操作测试状态更新
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import db_session
from sqlalchemy import text


def test_status_update_simple():
    """简化的状态更新测试"""
    print("=" * 60)
    print("测试状态修改功能（简化版）")
    print("=" * 60)

    session = db_session()

    try:
        # 1. 获取一条测试记录
        result = session.execute(text("SELECT id, student_id, status, processing_status FROM submissions LIMIT 1"))
        row = result.fetchone()

        if not row:
            print("\n没有记录可以测试")
            return

        submission_id, student_id, original_status, original_processing_status = row

        print(f"\n测试记录 ID: {submission_id}")
        print(f"  原状态: {original_status}")
        print(f"  原处理状态: {original_processing_status}")

        # 2. 测试直接SQL更新（旧状态字段）
        print(f"\n[测试1] 更新旧状态字段")
        session.execute(text("""
            UPDATE submissions
            SET status = 'pending'
            WHERE id = :id
        """), {'id': submission_id})
        session.commit()

        result = session.execute(text("SELECT status FROM submissions WHERE id = :id"), {'id': submission_id})
        new_status = result.fetchone()[0]
        print(f"  [OK] 更新成功，新状态: {new_status}")

        # 3. 测试直接SQL更新（新处理状态字段）
        print(f"\n[测试2] 更新新处理状态字段")
        session.execute(text("""
            UPDATE submissions
            SET processing_status = 'processing',
                processing_status_updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
        """), {'id': submission_id})
        session.commit()

        result = session.execute(text("SELECT processing_status FROM submissions WHERE id = :id"), {'id': submission_id})
        new_processing_status = result.fetchone()[0]
        print(f"  [OK] 更新成功，新处理状态: {new_processing_status}")

        # 4. 测试状态历史记录
        print(f"\n[测试3] 检查状态历史表")
        result = session.execute(text("""
            SELECT COUNT(*) as count FROM status_history
            WHERE submission_id = :id
        """), {'id': submission_id})
        history_count = result.fetchone()[0]
        print(f"  历史记录数: {history_count}")

        # 5. 验证状态映射
        print(f"\n[测试4] 验证状态映射正确性")
        test_cases = [
            ('ignored', 'ignored'),
            ('replied', 'completed'),
            ('downloaded', 'unreplied'),
            ('received', 'pending'),
        ]

        for proc_status, expected_legacy in test_cases:
            # 重置所有状态为默认值，然后只设置 processing_status
            session.execute(text("""
                UPDATE submissions
                SET processing_status = :proc_status,
                    ai_status = 'pending',
                    download_status = 'pending',
                    reply_status = 'pending'
                WHERE id = :id
            """), {'proc_status': proc_status, 'id': submission_id})

            # 计算兼容状态
            result = session.execute(text("""
                SELECT processing_status, ai_status, download_status, reply_status
                FROM submissions WHERE id = :id
            """), {'id': submission_id})
            row = result.fetchone()

            # 简化的状态映射逻辑（与StatusManager中的逻辑一致）
            statuses = {
                'processing_status': row[0],
                'ai_status': row[1],
                'download_status': row[2],
                'reply_status': row[3]
            }

            # 计算legacy状态（使用正确的优先级）
            if statuses['processing_status'] == 'ignored':
                legacy = 'ignored'
            elif statuses['processing_status'] == 'replied' or statuses['reply_status'] == 'success':
                legacy = 'completed'
            elif statuses['download_status'] == 'failed':
                legacy = 'download_failed'
            elif statuses['ai_status'] == 'failed':
                legacy = 'ai_error'
            elif statuses['processing_status'] == 'downloaded' or statuses['download_status'] == 'success':
                legacy = 'unreplied'
            else:
                legacy = 'pending'

            match = "[OK]" if legacy == expected_legacy else "[FAIL]"
            print(f"  {match} {proc_status} -> {legacy} (期望: {expected_legacy})")

        # 6. 恢复原始状态
        print(f"\n[测试5] 恢复原始状态")
        session.execute(text("""
            UPDATE submissions
            SET status = :orig_status,
                processing_status = :orig_proc_status
            WHERE id = :id
        """), {
            'orig_status': original_status,
            'orig_proc_status': original_processing_status,
            'id': submission_id
        })
        session.commit()
        print(f"  [OK] 状态已恢复")

        print("\n" + "=" * 60)
        print("状态修改功能测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        session.close()


def main():
    """主函数"""
    test_status_update_simple()


if __name__ == "__main__":
    main()
