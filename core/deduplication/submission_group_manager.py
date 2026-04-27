"""提交记录分组管理器 - 管理父子关系和版本跟踪"""

from typing import Optional, List
from sqlalchemy import select, update
from database.models import (
    get_async_session, Submission, RelationType
)
from database.async_operations import AsyncDatabaseOperations
import logging

logger = logging.getLogger(__name__)


class SubmissionGroupManager:
    """提交记录分组管理器

    职责：
    - 管理提交记录之间的父子关系
    - 跟踪版本迭代关系
    - 管理可能重复的记录
    - 提供分组查询功能
    """

    def __init__(self, db: AsyncDatabaseOperations):
        """初始化分组管理器

        Args:
            db: 异步数据库操作实例
        """
        self.db = db

    async def get_primary_submission(self, submission_id: int) -> Optional[Submission]:
        """获取主记录

        如果记录本身就是主记录(is_primary=True)，返回自己
        如果是子记录(has parent_id)，返回其父记录
        否则返回None

        Args:
            submission_id: 提交记录ID

        Returns:
            主记录对象，如果不存在返回None
        """
        async with get_async_session()() as session:
            # 获取记录
            result = await session.execute(
                select(Submission).filter_by(id=submission_id)
            )
            submission = result.scalar_one_or_none()

            if not submission:
                return None

            # 如果是主记录，返回自己
            if submission.is_primary:
                return submission

            # 如果有父记录，返回父记录
            if submission.parent_id:
                result = await session.execute(
                    select(Submission).filter_by(id=submission.parent_id)
                )
                return result.scalar_one_or_none()

            # 既不是主记录也没有父记录，返回None
            return None

    async def get_all_children(
        self,
        primary_id: int,
        relation_type: Optional[str] = None
    ) -> List[Submission]:
        """获取主记录的所有子记录

        Args:
            primary_id: 主记录ID
            relation_type: 可选的关系类型过滤器
                          (RelationType.VERSION | RelationType.POSSIBLE_DUP)

        Returns:
            子记录列表
        """
        async with get_async_session()() as session:
            query = select(Submission).filter_by(parent_id=primary_id)

            # 如果指定了关系类型，添加过滤条件
            if relation_type:
                query = query.filter_by(relation_type=relation_type)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def create_relation(
        self,
        parent_id: int,
        child_id: int,
        relation_type: str
    ) -> bool:
        """创建父子关系

        将子记录标记为附属记录：
        - 设置parent_id指向父记录
        - 设置relation_type关系类型
        - 设置is_primary=False

        Args:
            parent_id: 父记录ID
            child_id: 子记录ID
            relation_type: 关系类型 (RelationType.VERSION | RelationType.POSSIBLE_DUP)

        Returns:
            是否创建成功
        """
        async with get_async_session()() as session:
            try:
                # 更新子记录
                result = await session.execute(
                    update(Submission)
                    .filter_by(id=child_id)
                    .values(
                        parent_id=parent_id,
                        relation_type=relation_type,
                        is_primary=False
                    )
                )
                await session.commit()

                if result.rowcount == 0:
                    logger.warning(f"Child submission {child_id} not found")
                    return False

                logger.info(
                    f"Created relation: parent={parent_id}, child={child_id}, "
                    f"type={relation_type}"
                )
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create relation: {e}")
                return False

    async def update_primary_record(
        self,
        old_primary_id: int,
        new_primary_id: int
    ) -> bool:
        """更新主记录

        当发现旧的主记录应该被新记录替换时（如新版本替代旧版本）：
        1. 将旧主记录标记为子记录(parent_id=new_primary, relation_type='version', is_primary=False)
        2. 确保新记录是主记录(parent_id=None, relation_type=None, is_primary=True)
        3. 将旧主记录的子记录重新链接到新主记录

        Args:
            old_primary_id: 旧主记录ID
            new_primary_id: 新主记录ID

        Returns:
            是否更新成功
        """
        async with get_async_session()() as session:
            try:
                # 1. 获取旧主记录的所有子记录
                children_result = await session.execute(
                    select(Submission).filter_by(parent_id=old_primary_id)
                )
                old_children = list(children_result.scalars().all())

                # 2. 将旧主记录标记为子记录
                await session.execute(
                    update(Submission)
                    .filter_by(id=old_primary_id)
                    .values(
                        parent_id=new_primary_id,
                        relation_type=RelationType.VERSION.value,
                        is_primary=False
                    )
                )

                # 3. 确保新记录是主记录
                await session.execute(
                    update(Submission)
                    .filter_by(id=new_primary_id)
                    .values(
                        parent_id=None,
                        relation_type=None,
                        is_primary=True
                    )
                )

                # 4. 将旧主记录的子记录重新链接到新主记录
                if old_children:
                    for child in old_children:
                        await session.execute(
                            update(Submission)
                            .filter_by(id=child.id)
                            .values(parent_id=new_primary_id)
                        )

                await session.commit()

                logger.info(
                    f"Updated primary record: old={old_primary_id}, new={new_primary_id}, "
                    f"relinked {len(old_children)} children"
                )
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to update primary record: {e}")
                return False

    async def get_or_create_primary(
        self,
        student_id: str,
        assignment_name: str
    ) -> Optional[Submission]:
        """获取或查找学生某作业的主记录

        注意：此方法只查找，不创建。如果不存在返回None。

        Args:
            student_id: 学号
            assignment_name: 作业名称

        Returns:
            主记录对象，如果不存在返回None
        """
        # 使用数据库的get_latest_submission方法
        # 它已经查询了is_latest=True的记录，在我们的设计中这也是主记录
        return await self.db.get_latest_submission(student_id, assignment_name)
