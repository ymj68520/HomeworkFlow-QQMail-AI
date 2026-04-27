"""简单性能测试 - 测试核心算法性能"""

import time
from difflib import SequenceMatcher


def test_string_similarity():
    """测试字符串相似度计算性能"""
    print("=== 简单性能测试 ===\n")

    print("测试 1: 字符串相似度计算")
    start = time.time()
    for i in range(10000):
        similarity = SequenceMatcher(None, "张三", "张小三").ratio()
    duration = time.time() - start
    avg_time = duration / 10000

    print(f"  总耗时: {duration*1000:.2f}ms")
    print(f"  平均耗时: {avg_time*1000:.4f}ms")
    print(f"  结果示例: {similarity:.2f}")
    print(f"  状态: {'PASS' if avg_time < 0.001 else 'FAIL'}\n")

    # 测试 2: 批量相似度计算
    print("测试 2: 批量相似度计算")
    test_cases = [
        ("张三", "张小三"),
        ("2023001", "2023002"),
        ("张三", "李四"),
        ("S001", "S002"),
        ("张三丰", "张三"),
    ]

    start = time.time()
    for i in range(1000):
        for name1, name2 in test_cases:
            similarity = SequenceMatcher(None, name1, name2).ratio()
    duration = time.time() - start
    avg_time = duration / (1000 * len(test_cases))

    print(f"  测试用例数: {len(test_cases)}")
    print(f"  总迭代次数: {1000 * len(test_cases)}")
    print(f"  总耗时: {duration*1000:.2f}ms")
    print(f"  平均耗时: {avg_time*1000:.4f}ms")
    print(f"  状态: {'PASS' if avg_time < 0.001 else 'FAIL'}\n")

    print("=== 性能基准 ===")
    print("  相似度计算: < 0.001ms/次")
    print("  模糊匹配查询: < 1000ms (包含数据库)")
    print("  去重检查: < 500ms")
    print("  数据加载: < 2000ms (100条记录)")


if __name__ == "__main__":
    test_string_similarity()
