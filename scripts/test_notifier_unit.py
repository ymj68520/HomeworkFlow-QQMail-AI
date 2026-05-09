"""
数据变更通知系统 - 单元测试

测试核心功能，不涉及 GUI
"""
import sys
import time

# 添加项目路径
sys.path.insert(0, '.')

from PySide6.QtCore import QCoreApplication, QObject, Slot
from core.data_change_notifier import data_change_notifier, ChangeType


class NotificationReceiver(QObject):
    """通知接收器"""

    def __init__(self):
        super().__init__()
        self.notifications = []

    @Slot(str, dict)
    def on_notification(self, change_type: str, details: dict):
        """接收通知"""
        self.notifications.append({
            'type': change_type,
            'details': details
        })
        print(f"  [Received] {change_type}: {details}")


def test_single_record_notification():
    """测试单条记录通知"""
    print("\n" + "="*50)
    print("Test 1: Single Record Notification")
    print("="*50)

    receiver = NotificationReceiver()
    data_change_notifier.data_changed.connect(receiver.on_notification)

    # 测试记录更新通知
    data_change_notifier.notify_record_updated(
        uid='test123',
        submission_id=1,
        changes={'status': 'completed'}
    )

    # 测试记录创建通知
    data_change_notifier.notify_record_created(
        uid='test456',
        submission_id=2,
        student_id='2021001',
        assignment_name='Homework1'
    )

    # 测试记录删除通知
    data_change_notifier.notify_record_deleted(
        submission_id=3,
        uid='test789'
    )

    time.sleep(0.1)  # 等待信号处理

    assert len(receiver.notifications) == 3, f"Expected 3, got {len(receiver.notifications)}"
    assert receiver.notifications[0]['type'] == ChangeType.RECORD_UPDATED.value
    assert receiver.notifications[1]['type'] == ChangeType.RECORD_CREATED.value
    assert receiver.notifications[2]['type'] == ChangeType.RECORD_DELETED.value

    print(f"  [OK] All 3 notifications received correctly")


def test_batch_notification():
    """测试批量操作通知"""
    print("\n" + "="*50)
    print("Test 2: Batch Operation Notification")
    print("="*50)

    receiver = NotificationReceiver()
    data_change_notifier.data_changed.connect(receiver.on_notification)

    # 测试批量更新
    data_change_notifier.notify_batch_updated(
        submission_ids=[1, 2, 3, 4, 5],
        changes={'status': 'completed'}
    )

    # 测试批量删除
    data_change_notifier.notify_batch_deleted(
        submission_ids=[6, 7, 8]
    )

    time.sleep(0.1)  # 等待信号处理

    assert len(receiver.notifications) == 2, f"Expected 2, got {len(receiver.notifications)}"
    assert receiver.notifications[0]['type'] == ChangeType.BATCH_UPDATED.value
    assert receiver.notifications[0]['details']['count'] == 5
    assert receiver.notifications[1]['type'] == ChangeType.BATCH_DELETED.value
    assert receiver.notifications[1]['details']['count'] == 3

    print(f"  [OK] Batch notifications received correctly")


def test_new_emails_notification():
    """测试新邮件处理通知"""
    print("\n" + "="*50)
    print("Test 3: New Emails Processed Notification")
    print("="*50)

    receiver = NotificationReceiver()
    data_change_notifier.data_changed.connect(receiver.on_notification)

    # 测试新邮件处理完成通知
    data_change_notifier.notify_new_emails_processed(
        count=5,
        details=[
            {'uid': 'email1', 'student_id': '001'},
            {'uid': 'email2', 'student_id': '002'},
        ]
    )

    time.sleep(0.1)  # 等待信号处理

    assert len(receiver.notifications) == 1, f"Expected 1, got {len(receiver.notifications)}"
    assert receiver.notifications[0]['type'] == ChangeType.NEW_EMAILS_PROCESSED.value
    assert receiver.notifications[0]['details']['count'] == 5

    print(f"  [OK] New emails notification received correctly")


def test_refresh_notifications():
    """测试刷新通知"""
    print("\n" + "="*50)
    print("Test 4: Refresh Notifications")
    print("="*50)

    receiver = NotificationReceiver()
    data_change_notifier.data_changed.connect(receiver.on_notification)

    # 测试页面刷新
    data_change_notifier.notify_page_refresh(page=2)

    # 测试全量刷新
    data_change_notifier.notify_full_refresh(reason='manual')

    time.sleep(0.1)  # 等待信号处理

    assert len(receiver.notifications) == 2, f"Expected 2, got {len(receiver.notifications)}"
    assert receiver.notifications[0]['type'] == ChangeType.PAGE_REFRESH.value
    assert receiver.notifications[0]['details']['page'] == 2
    assert receiver.notifications[1]['type'] == ChangeType.FULL_REFRESH.value

    print(f"  [OK] Refresh notifications received correctly")


def test_multiple_receivers():
    """测试多个接收器"""
    print("\n" + "="*50)
    print("Test 5: Multiple Receivers")
    print("="*50)

    receiver1 = NotificationReceiver()
    receiver2 = NotificationReceiver()

    data_change_notifier.data_changed.connect(receiver1.on_notification)
    data_change_notifier.data_changed.connect(receiver2.on_notification)

    # 发送一个通知
    data_change_notifier.notify_record_updated(
        uid='test123',
        submission_id=1
    )

    time.sleep(0.1)  # 等待信号处理

    # 两个接收器都应该收到
    assert len(receiver1.notifications) == 1, f"Receiver1: Expected 1, got {len(receiver1.notifications)}"
    assert len(receiver2.notifications) == 1, f"Receiver2: Expected 1, got {len(receiver2.notifications)}"

    print(f"  [OK] Both receivers received the notification")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Data Change Notification System - Unit Tests")
    print("="*60)

    # 创建 Qt 应用（用于信号机制）
    app = QCoreApplication(sys.argv)

    # 运行测试
    try:
        test_single_record_notification()
        test_batch_notification()
        test_new_emails_notification()
        test_refresh_notifications()
        test_multiple_receivers()

        print("\n" + "="*60)
        print("All tests passed!")
        print("="*60)

        return 0

    except AssertionError as e:
        print(f"\n[FAILED] {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
