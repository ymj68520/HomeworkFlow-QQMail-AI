"""性能测试脚本 - 测试去重系统性能

使用方法:
    cd D:/Programs/Python/qq邮箱作业收发
    python tests/performance/run_performance_test.py
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def main():
    print("=== 去重系统性能测试 ===\n")

    # 测试 1: 导入性能
    print("测试 1: 模块导入性能")
    start = time.time()
    from core.deduplication.fuzzy_matcher import FuzzyMatcher
    from core.deduplication.submission_group_manager import SubmissionGroupManager
    from core.deduplication import DeduplicationService
    from database.async_operations import AsyncDatabaseOperations
    duration = time.time() - start
    print(f"  耗时: {duration*1000:.2f}ms")
    print(f"  状态: {'PASS' if duration < 1.0 else 'FAIL'}\n")

    # 测试 2: 字符串相似度计算性能
    print("测试 2: 字符串相似度计算性能")
    from difflib import SequenceMatcher

    start = time.time()
    for i in range(10000):
        similarity = SequenceMatcher(None, "张三", "张小三").ratio()
    duration = time.time() - start
    avg_time = duration / 10000

    print(f"  总耗时: {duration*1000:.2f}ms")
    print(f"  平均耗时: {avg_time*1000:.4f}ms")
    print(f"  状态: {'PASS' if avg_time < 0.001 else 'FAIL'}\n")

    # 测试 3: 关系分类性能
    print("测试 3: 关系分类性能")
    from database.async_operations import async_db
    matcher = FuzzyMatcher(async_db)

    start = time.time()
    for i in range(1000):
        relation = await matcher._classify_relation(
            match_score=0.85,
            same_student_id=True,
            same_name=False
        )
    duration = time.time() - start
    avg_time = duration / 1000

    print(f"  总耗时: {duration*1000:.2f}ms")
    print(f"  平均耗时: {avg_time*1000:.4f}ms")
    print(f"  状态: {'PASS' if avg_time < 0.001 else 'FAIL'}\n")

    print("=== 性能测试说明 ===")
    print("注意: 完整的性能测试需要:")
    print("  1. 运行中的数据库")
    print("  2. 实际的测试数据")
    print("  3. 完整的应用程序上下文")
    print("\n当前测试仅验证核心算法性能，不包括数据库查询。")
    print("完整测试请参考: tests/manual/deduplication_test_cases.md")


if __name__ == "__main__":
    asyncio.run(main())
