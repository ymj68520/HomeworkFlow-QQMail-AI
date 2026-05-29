#!/usr/bin/env python
"""
修复提交记录的版本标志 (is_latest, is_primary)

问题：
- 多个版本的 is_latest 都是 1
- is_primary 标志设置不正确
- parent_id 和 relation_type 没有正确设置

修复策略：
1. 对于每个学生+作业组合，找到最高版本号
2. 将最高版本的 is_latest 设为 1，其他版本设为 0
3. 将最高版本的 is_primary 设为 1，其他版本设为 0
4. 将其他版本的 parent_id 指向最高版本，relation_type 设为 'version'
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, update, and_, func
from database.models import get_async_session, Submission, Student, Assignment
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VersionFlagFixer:
    """版本标志修复工具"""

    def __init__(self):
        self.fixed_count = 0
        self.error_count = 0

    async def fix_all(self):
        """修复所有提交记录的版本标志"""
        logger.info("开始修复提交记录的版本标志...")
        logger.info("=" * 60)

        try:
            async with get_async_session()() as session:
                # 1. 查找所有需要修复的记录（存在多个版本的学生+作业组合）
                logger.info("步骤 1: 查找需要修复的记录...")

                # 查找每个学生+作业组合的版本信息
                stmt = (
                    select(
                        Student.id.label('student_id'),
                        Assignment.id.label('assignment_id'),
                        func.count(Submission.id).label('version_count'),
                        func.max(Submission.version).label('max_version')
                    )
                    .join(Submission, Submission.student_id == Student.id)
                    .join(Assignment, Submission.assignment_id == Assignment.id)
                    .group_by(Student.id, Assignment.id)
                    .having(func.count(Submission.id) > 1)
                )

                result = await session.execute(stmt)
                multi_version_groups = result.all()

                logger.info(f"找到 {len(multi_version_groups)} 个学生+作业组合有多个版本")

                if not multi_version_groups:
                    logger.info("没有需要修复的记录")
                    return True

                # 2. 显示需要修复的记录
                logger.info("\n步骤 2: 需要修复的记录预览...")
                await self._preview_records(session, multi_version_groups)

                # 3. 执行修复
                logger.info("\n步骤 3: 执行修复...")
                success = await self._perform_fix(session, multi_version_groups)

                if success:
                    await session.commit()
                    logger.info("\n修复成功完成！")
                    logger.info(f"修复了 {self.fixed_count} 条记录")
                else:
                    await session.rollback()
                    logger.error("\n修复失败，已回滚所有更改")
                    return False

                return True

        except Exception as e:
            logger.exception(f"修复过程发生错误: {e}")
            return False

    async def _preview_records(self, session, multi_version_groups):
        """预览需要修复的记录"""
        shown = 0
        for group in multi_version_groups[:10]:  # 只显示前10个
            student_id = group.student_id
            assignment_id = group.assignment_id
            version_count = group.version_count
            max_version = group.max_version

            # 获取学生和作业信息
            student_result = await session.execute(
                select(Student).where(Student.id == student_id)
            )
            student = student_result.scalar_one_or_none()

            assignment_result = await session.execute(
                select(Assignment).where(Assignment.id == assignment_id)
            )
            assignment = assignment_result.scalar_one_or_none()

            # 获取所有版本的提交记录
            submissions_result = await session.execute(
                select(Submission)
                .where(
                    and_(
                        Submission.student_id == student_id,
                        Submission.assignment_id == assignment_id
                    )
                )
                .order_by(Submission.version.desc())
            )
            submissions = submissions_result.scalars().all()

            logger.info(f"\n  {student.name} ({student.student_id}) - {assignment.name}")
            logger.info(f"  总版本数: {version_count}, 最高版本: {max_version}")
            logger.info(f"  当前状态:")
            for sub in submissions:
                logger.info(f"    版本{sub.version}: is_latest={sub.is_latest}, is_primary={sub.is_primary}, parent_id={sub.parent_id}, relation_type={sub.relation_type}")

            shown += 1

        if len(multi_version_groups) > 10:
            logger.info(f"\n... 还有 {len(multi_version_groups) - 10} 个组合未显示")

    async def _perform_fix(self, session, multi_version_groups):
        """执行修复"""
        try:
            for i, group in enumerate(multi_version_groups, 1):
                try:
                    student_id = group.student_id
                    assignment_id = group.assignment_id
                    max_version = group.max_version

                    # 获取所有版本的提交记录
                    submissions_result = await session.execute(
                        select(Submission)
                        .where(
                            and_(
                                Submission.student_id == student_id,
                                Submission.assignment_id == assignment_id
                            )
                        )
                        .order_by(Submission.version.desc())
                    )
                    submissions = submissions_result.scalars().all()

                    # 找到最新版本（is_latest 应该为 1 的版本）
                    latest_submission = None
                    for sub in submissions:
                        if sub.version == max_version:
                            latest_submission = sub
                            break

                    if not latest_submission:
                        logger.warning(f"[{i}/{len(multi_version_groups)}] 未找到最高版本 {max_version}")
                        continue

                    # 修复最新版本
                    if not latest_submission.is_latest or not latest_submission.is_primary:
                        await session.execute(
                            update(Submission)
                            .where(Submission.id == latest_submission.id)
                            .values(
                                is_latest=True,
                                is_primary=True,
                                parent_id=None,
                                relation_type=None
                            )
                        )
                        self.fixed_count += 1
                        logger.info(f"[{i}/{len(multi_version_groups)}] 修复最新版本 {latest_submission.version} (ID={latest_submission.id})")

                    # 修复其他版本
                    for sub in submissions:
                        if sub.id != latest_submission.id:
                            # 确保旧版本被正确标记
                            if sub.is_latest or sub.is_primary or sub.parent_id != latest_submission.id or sub.relation_type != 'version':
                                await session.execute(
                                    update(Submission)
                                    .where(Submission.id == sub.id)
                                    .values(
                                        is_latest=False,
                                        is_primary=False,
                                        parent_id=latest_submission.id,
                                        relation_type='version'
                                    )
                                )
                                self.fixed_count += 1

                except Exception as e:
                    logger.error(f"处理组合 {i} 时出错: {e}")
                    self.error_count += 1
                    continue

            return True

        except Exception as e:
            logger.exception(f"修复过程发生错误: {e}")
            return False


async def main():
    """主函数"""
    print("=" * 60)
    print("提交记录版本标志修复工具")
    print("=" * 60)
    print()

    fixer = VersionFlagFixer()
    success = await fixer.fix_all()

    print()
    print("=" * 60)
    if success:
        print("修复完成！")
        if fixer.error_count > 0:
            print(f"\n警告: {fixer.error_count} 个组合处理失败")
    else:
        print("修复失败！请检查错误信息")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
