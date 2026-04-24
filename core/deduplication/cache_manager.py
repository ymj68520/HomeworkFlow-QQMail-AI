"""AI缓存管理组件"""

from typing import Optional, Dict, Any
from database.async_operations import AsyncDatabaseOperations


class CacheManager:
    """AI提取结果缓存管理

    职责：
    - 严格缓存模式：先检查缓存
    - 缓存未命中才调用AI
    - 保存AI结果供后续使用
    """

    def __init__(self, db: AsyncDatabaseOperations):
        self.db = db

    async def get(self, email_uid: str) -> Optional[Dict[str, Any]]:
        """获取缓存的AI提取结果

        Args:
            email_uid: 邮件UID

        Returns:
            缓存的结果字典，如果不存在返回None
        """
        return await self.db.get_ai_cache(email_uid)

    async def set(
        self,
        email_uid: str,
        result: Dict[str, Any],
        is_fallback: bool = False
    ) -> None:
        """保存AI提取结果到缓存

        Args:
            email_uid: 邮件UID
            result: AI提取结果字典
            is_fallback: 是否为fallback结果
        """
        await self.db.save_ai_cache(email_uid, result, is_fallback)

    async def has(self, email_uid: str) -> bool:
        """检查是否有缓存

        Args:
            email_uid: 邮件UID

        Returns:
            True if cache exists, False otherwise
        """
        cached = await self.get(email_uid)
        return cached is not None
