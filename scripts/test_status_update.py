"""
测试状态修改功能

验证GUI中的状态编辑功能是否正常工作
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import db_session, ProcessingStatus
from database.operations import db
from core.sync_status_manager import get_sync_status_manager
from sqlalchemy import text


def test_status_update():
    """测试状态更新功能"""
    print("=" * 60)
    print("测试状态修改功能")
    print("=" * 60)

    session = db_session()
    status_mgr = get_sync_status_manager(session)

    try:
        # 1. 获取一条测试记录
        result = session.execute(text("SELECT id, student_id, status, processing_status FROM submissions LIMIT 1"))
        row = result.fetchone()

        if not row:
            print("\n没有记录可以测试")
            return

        submission_id, original_student_id, original_status, original_processing_status = row

        print(f"\n测试记录 ID: {submission_id}")
        print(f"  原状态: {original_status}")
        print(f"  原处理状态: {original_processing_status}")

        # 2. 测试旧状态更新（pending -> completed）
        print(f"\n[测试1] 更新旧状态: {original_status} -> completed")
        result = db.update_submission_full(
            submission_id=submission_id,
            student_id=original_student_id,
            name="测试学生",
            assignment_name="测试作业",
            status='completed',
            email='test@example.com'
        )

        if result:
            # 验证更新
            new_result = session.execute(text("SELECT status, processing_status FROM submissions WHERE id = :id"), {'id': submission_id})
            new_status, new_processing_status = new_result.fetchone()
            print(f"  ✓ 更新成功")
            print(f"  新状态: {new_status}")
            print(f"  新处理状态: {new_processing_status}")
        else:
            print(f"  ✗ 更新失败")

        # 3. 测试新处理状态更新（received -> processing）
        print(f"\n[测试2] 更新新处理状态: received -> processing")
        result = db.update_submission_full(
            submission_id=submission_id,
            student_id=original_student_id,
            name="测试学生",
            assignment_name="测试作业",
            status='processing',
            email='test@example.com'
        )

        if result:
            # 验证更新
            new_result = session.execute(text("SELECT status, processing_status FROM submissions WHERE id = :id"), {'id': submission_id})
            new_status, new_processing_status = new_result.fetchone()
            print(f"  ✓ 更新成功")
            print(f"  新状态: {new_status}")
            print(f"  新处理状态: {new_processing_status}")
        else:
            print(f"  ✗ 更新失败")

        # 4. 测试状态管理器直接更新
        print(f"\n[测试3] 使用状态管理器更新")
        result = status_mgr.transition(
            submission_id, 'processing', 'extracted',
            reason='测试状态管理器更新'
        )

        if result:
            # 验证更新
            new_result = session.execute(text("SELECT processing_status, processing_status_updated_at FROM submissions WHERE id = :id"), {'id': submission_id})
            new_processing_status, updated_at = new_result.fetchone()
            print(f"  ✓ 更新成功")
            print(f"  新处理状态: {new_processing_status}")
            print(f"  更新时间: {updated_at}")
        else:
            print(f"  ✗ 更新失败")

        # 5. 验证历史记录
        print(f"\n[测试4] 验证状态历史记录")
        history = status_mgr.get_history(submission_id, limit=3)
        print(f"  历史记录数: {len(history)}")
        for i, h in enumerate(history, 1):
            print(f"  {i}. {h['status_type']}: {h['old_status']} -> {h['new_status']}")
            if h['reason']:
                print(f"     原因: {h['reason']}")

        # 6. 测试状态字段更新（update_submission_field）
        print(f"\n[测试5] 测试单字段更新")
        result = db.update_submission_field(
            submission_id=submission_id,
            field_id='status',
            new_value='failed'
        )

        if result:
            # 验证更新
            new_result = session.execute(text("SELECT status, processing_status FROM submissions WHERE id = :id"), {'id': submission_id})
            new_status, new_processing_status = new_result.fetchone()
            print(f"  ✓ 更新成功")
            print(f"  新状态: {new_status}")
            print(f"  新处理状态: {new_processing_status}")
        else:
            print(f"  ✗ 更新失败")

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
    test_status_update()


if __name__ == "__main__":
    main()
