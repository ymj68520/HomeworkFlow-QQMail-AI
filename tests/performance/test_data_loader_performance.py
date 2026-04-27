"""性能测试 - 测试数据加载器性能"""

import asyncio
import sys
import time

# 添加项目根目录到路径
sys.path.insert(0, 'D:/Programs/Python/qq邮箱作业收发')

from mail.hybrid_data_loader import hybrid_data_loader


async def test_loading_performance():
    """测试数据加载性能"""
    print("=== 数据加载器性能测试 ===\n")

    # 测试 1: 加载第一页（100条记录）
    print("测试 1: 加载第一页（100条记录）")
    start = time.time()
    result = await hybrid_data_loader.get_page_data(page=1, per_page=100)
    duration = time.time() - start

    print(f"  耗时: {duration:.2f}s")
    print(f"  记录数: {len(result['submissions'])}")
    print(f"  总数: {result['pagination']['total']}")
    print(f"  状态: {'✅ PASS' if duration < 2.0 else '❌ FAIL'} (期望 < 2.0s)\n")

    # 测试 2: 加载多页
    print("测试 2: 加载多页")
    start = time.time()
    page1 = await hybrid_data_loader.get_page_data(page=1, per_page=50)
    page2 = await hybrid_data_loader.get_page_data(page=2, per_page=50)
    duration = time.time() - start

    print(f"  耗时: {duration:.2f}s")
    print(f"  第1页: {len(page1['submissions'])} 条")
    print(f"  第2页: {len(page2['submissions'])} 条")
    print(f"  状态: {'✅ PASS' if duration < 3.0 else '❌ FAIL'} (期望 < 3.0s)\n")

    # 测试 3: 去重检查性能
    print("测试 3: 去重检查性能")
    from core.deduplication import DeduplicationService
    from database.async_operations import async_db

    service = DeduplicationService(async_db)

    start = time.time()
    result = await service.check_submission("TEST001", "测试作业")
    duration = time.time() - start

    print(f"  耗时: {duration*1000:.2f}ms")
    print(f"  是否重复: {result.is_duplicate}")
    print(f"  状态: {'✅ PASS' if duration < 0.5 else '❌ FAIL'} (期望 < 500ms)\n")

    # 测试 4: 模糊匹配性能
    print("测试 4: 模糊匹配性能")
    from core.deduplication.fuzzy_matcher import FuzzyMatcher

    matcher = FuzzyMatcher(async_db)

    start = time.time()
    duplicates = await matcher.find_possible_duplicates(
        student_id="TEST001",
        name="测试学生",
        assignment_name="测试作业"
    )
    duration = time.time() - start

    print(f"  耗时: {duration*1000:.2f}ms")
    print(f"  可能的重复数: {len(duplicates)}")
    print(f"  状态: {'✅ PASS' if duration < 1.0 else '❌ FAIL'} (期望 < 1000ms)\n")

    # 测试 5: 分组查询性能
    print("测试 5: 分组查询性能")
    from core.deduplication.submission_group_manager import SubmissionGroupManager

    group_mgr = SubmissionGroupManager(async_db)

    # 假设第一个记录有子记录
    if result['submissions']:
        first_id = result['submissions'][0]['id']

        start = time.time()
        children = await group_mgr.get_all_children(first_id)
        duration = time.time() - start

        print(f"  耗时: {duration*1000:.2f}ms")
        print(f"  子记录数: {len(children)}")
        print(f"  状态: {'✅ PASS' if duration < 0.5 else '❌ FAIL'} (期望 < 500ms)\n")

    print("=== 性能测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_loading_performance())
