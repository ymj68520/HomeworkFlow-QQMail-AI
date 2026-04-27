"""模糊匹配服务 - 用于检测可能的重复提交"""

from typing import List, Optional
from difflib import SequenceMatcher
from database.async_operations import AsyncDatabaseOperations
from database.models import Submission, Student, Assignment, RelationType
from sqlalchemy import select
from database.models import get_async_session
from sqlalchemy.orm import selectinload


class FuzzyMatcher:
    """模糊匹配器 - 用于检测可能的重复提交

    职责：
    - 基于学号和姓名的模糊匹配
    - 计算匹配分数
    - 分类重复关系类型
    """

    def __init__(self, db: AsyncDatabaseOperations):
        """初始化模糊匹配器

        Args:
            db: 异步数据库操作实例
        """
        self.db = db

    async def find_possible_duplicates(
        self,
        student_id: str,
        name: str,
        assignment_name: str
    ) -> List[Submission]:
        """查找可能的重复提交

        Args:
            student_id: 学号
            name: 学生姓名
            assignment_name: 作业名称

        Returns:
            可能重复的提交列表，按匹配分数降序排序
        """
        async with get_async_session()() as session:
            # 先获取作业信息
            assignment_result = await session.execute(
                select(Assignment).filter_by(name=assignment_name)
            )
            assignment = assignment_result.scalar_one_or_none()

            if not assignment:
                return []

            # 获取所有该作业的主要提交记录（is_primary=True）
            submissions_result = await session.execute(
                select(Submission)
                .filter_by(
                    assignment_id=assignment.id,
                    is_primary=True
                )
                .options(
                    selectinload(Submission.student)
                )
            )
            submissions = submissions_result.scalars().all()

            # 计算每个提交的匹配分数
            scored_submissions = []
            for submission in submissions:
                if not submission.student:
                    continue

                # 跳过完全匹配（学号和姓名都相同）
                if (submission.student.student_id == student_id and
                    submission.student.name == name):
                    continue

                # 计算匹配分数
                score = await self._calculate_match_score(
                    student_id, name,
                    submission.student.student_id, submission.student.name
                )

                # 只保留有一定匹配度的提交
                if score > 0.3:  # 最低阈值
                    scored_submissions.append((submission, score))

            # 按匹配分数降序排序
            scored_submissions.sort(key=lambda x: x[1], reverse=True)

            # 返回排序后的提交列表
            return [sub for sub, score in scored_submissions]

    async def get_all_submissions_for_assignment(
        self,
        assignment_name: str
    ) -> List[Submission]:
        """获取指定作业的所有主要提交记录

        这是一个辅助方法，用于测试和简化mock

        Args:
            assignment_name: 作业名称

        Returns:
            提交列表
        """
        async with get_async_session()() as session:
            # 先获取作业信息
            assignment_result = await session.execute(
                select(Assignment).filter_by(name=assignment_name)
            )
            assignment = assignment_result.scalar_one_or_none()

            if not assignment:
                return []

            # 获取所有该作业的主要提交记录（is_primary=True）
            submissions_result = await session.execute(
                select(Submission)
                .filter_by(
                    assignment_id=assignment.id,
                    is_primary=True
                )
                .options(
                    selectinload(Submission.student)
                )
            )
            return submissions_result.scalars().all()

    async def _calculate_match_score(
        self,
        student_id1: str,
        name1: str,
        student_id2: str,
        name2: str
    ) -> float:
        """计算两个提交之间的匹配分数

        Args:
            student_id1: 第一个提交的学号
            name1: 第一个提交的姓名
            student_id2: 第二个提交的学号
            name2: 第二个提交的姓名

        Returns:
            匹配分数 (0.0 - 1.0)
        """
        score = 0.0

        # 学号匹配
        if student_id1 == student_id2:
            score += 0.7
        else:
            # 学号相似度
            student_id_sim = self._string_similarity(student_id1, student_id2)
            if student_id_sim > 0.8:
                score += 0.4

        # 姓名匹配
        if name1 == name2:
            score += 0.7
        else:
            # 姓名相似度
            name_sim = self._string_similarity(name1, name2)
            score += name_sim * 0.5

        # 确保分数在 0.0 - 1.0 之间
        return min(score, 1.0)

    def _string_similarity(self, str1: str, str2: str) -> float:
        """计算两个字符串的相似度

        Args:
            str1: 第一个字符串
            str2: 第二个字符串

        Returns:
            相似度 (0.0 - 1.0)
        """
        return SequenceMatcher(None, str1, str2).ratio()

    async def classify_relation_type(
        self,
        student_id1: str,
        name1: str,
        student_id2: str,
        name2: str
    ) -> str:
        """分类两个提交之间的关系类型

        Args:
            student_id1: 第一个提交的学号
            name1: 第一个提交的姓名
            student_id2: 第二个提交的学号
            name2: 第二个提交的姓名

        Returns:
            关系类型: 'version', 'possible_dup', 'none'
        """
        # 检查是否为版本关系（学号和姓名都匹配）
        if student_id1 == student_id2 and name1 == name2:
            return 'version'

        # 检查是否为可能重复（至少一个字段匹配或高度相似）
        student_id_match = (student_id1 == student_id2 or
                           self._string_similarity(student_id1, student_id2) > 0.8)
        name_match = (name1 == name2 or
                     self._string_similarity(name1, name2) > 0.6)

        if student_id_match or name_match:
            return 'possible_dup'

        return 'none'
