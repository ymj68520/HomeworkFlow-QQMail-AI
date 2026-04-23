"""
Performance benchmarks for AI extraction
"""
import pytest
import asyncio
import time
from ai.extractor import AIExtractor

@pytest.mark.asyncio
@pytest.mark.slow
async def test_cache_performance():
    """Test that cache provides significant speedup"""
    extractor = AIExtractor()
    email_data = {
        'uid': '12345',  # Must be numeric for cache to work
        'subject': '2021001张三-作业1',
        'from': '张三',
        'attachments': []
    }

    # First call (cache miss)
    start = time.time()
    await extractor.extract_with_cache(email_data)
    first_call_time = time.time() - start

    # Second call (cache hit)
    start = time.time()
    await extractor.extract_with_cache(email_data)
    second_call_time = time.time() - start

    # Cache hit should be much faster
    assert second_call_time < first_call_time / 10
    print(f"First call: {first_call_time:.3f}s, Cache hit: {second_call_time:.3f}s")

@pytest.mark.asyncio
@pytest.mark.slow
async def test_batch_vs_sequential():
    """Compare batch vs sequential processing performance"""
    extractor = AIExtractor()

    # Use timestamp-based UIDs to ensure no cache hits
    import time as time_module
    timestamp = int(time_module.time() * 1000)

    # Sequential processing with unique UIDs (no cache hits)
    sequential_emails = [
        {'uid': str(timestamp + i), 'subject': f'202100{i}学生-作业1', 'from': '学生', 'attachments': []}
        for i in range(10)
    ]

    start = time.time()
    for email in sequential_emails:
        await extractor.extract_with_cache(email)
    sequential_time = time.time() - start

    # Batch processing with different UIDs (no cache hits from sequential)
    batch_emails = [
        {'uid': str(timestamp + i + 1000), 'subject': f'202100{i}学生-作业1', 'from': '学生', 'attachments': []}
        for i in range(10)
    ]

    start = time.time()
    await extractor.batch_extract(batch_emails)
    batch_time = time.time() - start

    # Batch should be faster
    print(f"Sequential: {sequential_time:.3f}s, Batch: {batch_time:.3f}s")
    # Batch should be at least 2x faster
    assert batch_time < sequential_time / 2
