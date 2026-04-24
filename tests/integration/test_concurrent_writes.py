"""
测试数据库并发写操作

验证写队列是否正常工作，确保不会出现数据库锁定错误。
"""
import sys
import time
import threading
from datetime import datetime
from database.operations import db
from database.write_queue import write_queue

# 修复 Windows 控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

# 测试计数器
success_count = 0
error_count = 0
lock = threading.Lock()


def create_test_submissions(thread_id: int, count: int):
    """在指定线程中创建多个测试提交记录"""
    global success_count, error_count

    for i in range(count):
        try:
            result = db.create_submission(
                email_uid=f"test_{thread_id}_{i}",
                email_subject=f"Test Subject {thread_id}-{i}",
                sender_email=f"test{thread_id}@example.com",
                sender_name=f"Test User {thread_id}",
                submission_time=datetime.now(),
                student_id=f"student_{thread_id}",
                assignment_name=f"assignment_{thread_id % 3 + 1}",
                status='pending'
            )

            with lock:
                if result:
                    success_count += 1
                else:
                    error_count += 1
                    print(f"[Thread {thread_id}] Failed to create submission #{i}")

        except Exception as e:
            import traceback
            with lock:
                error_count += 1
                print(f"[Thread {thread_id}] Error at #{i}: {e}")
                traceback.print_exc()


def test_concurrent_writes():
    """测试并发写操作"""
    print("=" * 60)
    print("数据库并发写操作测试")
    print("=" * 60)
    print(f"写队列状态: {'运行中' if write_queue._running else '未启动'}")
    print()

    # 启动写队列
    write_queue.start()
    print("✓ 写队列已启动")
    print()

    # 测试参数
    num_threads = 5
    submissions_per_thread = 10

    print(f"启动 {num_threads} 个线程，每个线程创建 {submissions_per_thread} 条记录...")
    print()

    threads = []
    start_time = time.time()

    # 创建并启动线程
    for i in range(num_threads):
        thread = threading.Thread(
            target=create_test_submissions,
            args=(i, submissions_per_thread),
            name=f"WriterThread-{i}",
            daemon=False
        )
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join(timeout=30.0)
        if thread.is_alive():
            print(f"警告: 线程 {thread.name} 超时")

    elapsed = time.time() - start_time

    # 打印结果
    print()
    print("=" * 60)
    print("测试结果")
    print("=" * 60)
    print(f"总耗时: {elapsed:.2f} 秒")
    print(f"成功: {success_count} 条")
    print(f"失败: {error_count} 条")
    print(f"队列当前大小: {write_queue.queue_size}")
    print()

    if error_count == 0:
        print("✓ 所有写操作成功完成，无数据库锁定错误！")
    else:
        print("✗ 部分写操作失败")

    return error_count == 0


if __name__ == "__main__":
    try:
        success = test_concurrent_writes()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被中断")
        exit(1)
