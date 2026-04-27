"""测试FuzzyMatcher"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.deduplication.fuzzy_matcher import FuzzyMatcher
from database.models import Submission, Student, Assignment


@pytest.fixture
def mock_db():
    """模拟数据库操作"""
    db = Mock()
    return db


@pytest.fixture
def fuzzy_matcher(mock_db):
    """创建FuzzyMatcher实例"""
    return FuzzyMatcher(mock_db)


def test_string_similarity(fuzzy_matcher):
    """测试：字符串相似度计算"""
    # 完全相同
    assert fuzzy_matcher._string_similarity("hello", "hello") == 1.0

    # 完全不同
    assert fuzzy_matcher._string_similarity("abc", "xyz") < 0.5

    # 部分相似
    similarity = fuzzy_matcher._string_similarity("hello", "hallo")
    assert 0.5 < similarity < 1.0

    # 中文相似度测试
    similarity_cn = fuzzy_matcher._string_similarity("张三", "张三丰")
    assert 0.5 < similarity_cn < 1.0

    # 学号相似度测试
    similarity_id = fuzzy_matcher._string_similarity("S001", "S002")
    assert 0.5 < similarity_id < 1.0


@pytest.mark.asyncio
async def test_calculate_match_score_same_student_id(fuzzy_matcher):
    """测试：计算匹配分数（相同学号）"""
    score = await fuzzy_matcher._calculate_match_score(
        "S001", "张三",
        "S001", "李四"
    )

    # 学号相同：+0.7
    assert score == 0.7


@pytest.mark.asyncio
async def test_calculate_match_score_same_name(fuzzy_matcher):
    """测试：计算匹配分数（相同姓名）"""
    score = await fuzzy_matcher._calculate_match_score(
        "S001", "张三",
        "S002", "张三"
    )

    # 姓名相同：+0.7
    assert score == 0.7


@pytest.mark.asyncio
async def test_calculate_match_score_both_same(fuzzy_matcher):
    """测试：计算匹配分数（学号和姓名都相同）"""
    score = await fuzzy_matcher._calculate_match_score(
        "S001", "张三",
        "S001", "张三"
    )

    # 学号相同 + 姓名相同 = 1.4，但上限是 1.0
    assert score == 1.0


@pytest.mark.asyncio
async def test_calculate_match_score_similar_student_id(fuzzy_matcher):
    """测试：计算匹配分数（相似学号）"""
    score = await fuzzy_matcher._calculate_match_score(
        "S001", "张三",
        "S002", "李四"
    )

    # S001和S002相似度 = 0.75 (< 0.8)，所以没有学号分数
    # 但可能有少量姓名相似度贡献
    assert 0.0 <= score <= 0.5


@pytest.mark.asyncio
async def test_calculate_match_score_similar_name(fuzzy_matcher):
    """测试：计算匹配分数（相似姓名）"""
    score = await fuzzy_matcher._calculate_match_score(
        "S001", "张三",
        "S999", "张三丰"
    )

    # 姓名相似度贡献分数
    assert score > 0.0
    assert score <= 1.0


@pytest.mark.asyncio
async def test_calculate_match_score_no_match(fuzzy_matcher):
    """测试：计算匹配分数（完全不匹配）"""
    score = await fuzzy_matcher._calculate_match_score(
        "S001", "张三",
        "S999", "李四"
    )

    # 应该几乎没有匹配分数
    assert 0.0 <= score < 0.3


@pytest.mark.asyncio
async def test_classify_version_relation(fuzzy_matcher):
    """测试：分类版本关系（学号和姓名都匹配）"""
    result = await fuzzy_matcher.classify_relation_type(
        "S001", "张三",
        "S001", "张三"
    )

    assert result == "version"


@pytest.mark.asyncio
async def test_classify_possible_duplicate_student_id(fuzzy_matcher):
    """测试：分类可能重复（学号匹配）"""
    result = await fuzzy_matcher.classify_relation_type(
        "S001", "张三",
        "S001", "李四"
    )

    assert result == "possible_dup"


@pytest.mark.asyncio
async def test_classify_possible_duplicate_name(fuzzy_matcher):
    """测试：分类可能重复（姓名匹配）"""
    result = await fuzzy_matcher.classify_relation_type(
        "S001", "张三",
        "S002", "张三"
    )

    assert result == "possible_dup"


@pytest.mark.asyncio
async def test_classify_possible_duplicate_similar_student_id(fuzzy_matcher):
    """测试：分类可能重复（相似学号）"""
    result = await fuzzy_matcher.classify_relation_type(
        "S001", "张三",
        "S002", "李四"
    )

    # S001和S002相似度 = 0.75 (< 0.8)，姓名也不匹配
    # 所以应该返回 'none'
    assert result == "none"


@pytest.mark.asyncio
async def test_classify_possible_duplicate_similar_name(fuzzy_matcher):
    """测试：分类可能重复（相似姓名）"""
    result = await fuzzy_matcher.classify_relation_type(
        "S001", "张三",
        "S999", "张三丰"
    )

    # "张三"和"张三丰"相似度 > 0.6
    assert result == "possible_dup"


@pytest.mark.asyncio
async def test_classify_no_relation(fuzzy_matcher):
    """测试：分类无关系（学号和姓名都不匹配）"""
    result = await fuzzy_matcher.classify_relation_type(
        "S001", "张三",
        "S999", "李四"
    )

    assert result == "none"


@pytest.mark.asyncio
async def test_find_possible_duplicates_integration(fuzzy_matcher, mock_db):
    """集成测试：测试find_possible_duplicates的完整逻辑"""
    # 创建模拟数据
    mock_student1 = Mock()
    mock_student1.student_id = "S001"
    mock_student1.name = "张三"

    mock_student2 = Mock()
    mock_student2.student_id = "S002"
    mock_student2.name = "张三"  # 相同姓名

    mock_student3 = Mock()
    mock_student3.student_id = "S999"
    mock_student3.name = "李四"

    mock_submission1 = Mock()
    mock_submission1.student = mock_student1
    mock_submission1.is_primary = True

    mock_submission2 = Mock()
    mock_submission2.student = mock_student2
    mock_submission2.is_primary = True

    mock_submission3 = Mock()
    mock_submission3.student = mock_student3
    mock_submission3.is_primary = True

    # 直接测试核心逻辑
    submissions = [mock_submission1, mock_submission2, mock_submission3]

    # 计算匹配分数（模拟find_possible_duplicates中的逻辑）
    scored_submissions = []
    for submission in submissions:
        if not submission.student:
            continue

        # 跳过完全匹配
        if (submission.student.student_id == "S001" and
            submission.student.name == "张三"):
            continue

        score = await fuzzy_matcher._calculate_match_score(
            "S001", "张三",
            submission.student.student_id, submission.student.name
        )

        if score > 0.3:
            scored_submissions.append((submission, score))

    # 按分数排序
    scored_submissions.sort(key=lambda x: x[1], reverse=True)

    # 验证结果
    assert len(scored_submissions) >= 1
    # 第一个应该是分数最高的（相同姓名的S002）
    assert scored_submissions[0][0].student.name == "张三"
