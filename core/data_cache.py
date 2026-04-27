"""
数据缓存系统 - 三层缓存策略

L1: 当前页数据 (内存，最快)
L2: 前后页预加载 (内存，快速)
L3: 数据库持久化 (慢，但可靠)

设计目标:
- 减少IMAP查询次数
- 减少数据库查询次数
- 提供快速的数据访问
- 自动管理缓存失效
"""
import threading
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import OrderedDict


class LRUCache:
    """
    带过期时间的LRU缓存

    用于L2缓存: 存储预加载的页面数据
    """

    def __init__(self, capacity: int = 5, ttl_seconds: int = 300):
        """
        Args:
            capacity: 最大缓存条目数
            ttl_seconds: 缓存过期时间(秒)
        """
        self.capacity = capacity
        self.ttl = timedelta(seconds=ttl_seconds)
        self.cache: OrderedDict[int, Dict] = OrderedDict()
        self.timestamps: Dict[int, datetime] = {}
        self._lock = threading.RLock()

    def get(self, page: int) -> Optional[Dict]:
        """获取指定页的缓存数据"""
        with self._lock:
            if page not in self.cache:
                return None

            # 检查是否过期
            if datetime.now() - self.timestamps[page] > self.ttl:
                del self.cache[page]
                del self.timestamps[page]
                return None

            # LRU: 移到末尾
            self.cache.move_to_end(page)
            return self.cache[page]

    def put(self, page: int, data: Dict):
        """缓存指定页的数据"""
        with self._lock:
            # 更新时间戳
            self.timestamps[page] = datetime.now()

            # 如果已存在，更新并移到末尾
            if page in self.cache:
                self.cache.move_to_end(page)
                self.cache[page] = data
                return

            # 检查容量
            if len(self.cache) >= self.capacity:
                # 删除最旧的
                oldest = next(iter(self.cache))
                del self.cache[oldest]
                del self.timestamps[oldest]

            self.cache[page] = data

    def invalidate(self, page: int = None):
        """
        使缓存失效

        Args:
            page: 指定页码，None表示清空全部
        """
        with self._lock:
            if page is None:
                self.cache.clear()
                self.timestamps.clear()
            elif page in self.cache:
                del self.cache[page]
                del self.timestamps[page]

    def has(self, page: int) -> bool:
        """检查是否有指定页的缓存"""
        with self._lock:
            return page in self.cache and \
                   datetime.now() - self.timestamps[page] <= self.ttl


class DataCache:
    """
    三层数据缓存系统

    L1缓存: 当前页数据，快速访问
    L2缓存: LRU缓存预加载页面
    L3缓存: 数据库持久化
    """

    def __init__(self, per_page: int = 100):
        self.per_page = per_page

        # L1缓存: 当前页数据
        self._current_page: int = 1
        self._current_data: List[Dict] = []
        self._total_count: int = 0
        self._total_pages: int = 1

        # L2缓存: 预加载页面 (默认缓存5页，5分钟过期)
        self._page_cache = LRUCache(capacity=5, ttl_seconds=300)

        # 元数据缓存 (UID到ID的映射等)
        self._uid_to_id: Dict[str, int] = {}
        self._message_id_to_id: Dict[str, int] = {}

        self._lock = threading.RLock()

    def get_page_data(self, page: int) -> Optional[List[Dict]]:
        """
        获取指定页数据

        查找顺序: L1 -> L2 -> L3(需要加载)

        Args:
            page: 页码

        Returns:
            数据列表，如果缓存中没有返回None
        """
        with self._lock:
            # L1: 当前页
            if page == self._current_page:
                return self._current_data

            # L2: 缓存页
            cached = self._page_cache.get(page)
            if cached:
                return cached.get('data', [])

            return None

    def set_page_data(self, page: int, data: List[Dict],
                     total_count: int = None, total_pages: int = None):
        """
        设置页数据

        Args:
            page: 页码
            data: 数据列表
            total_count: 总记录数
            total_pages: 总页数
        """
        with self._lock:
            # 更新L1缓存
            if page == self._current_page or self._current_data is None:
                self._current_page = page
                self._current_data = data

            # 更新L2缓存
            self._page_cache.put(page, {
                'data': data,
                'total_count': total_count or self._total_count,
                'total_pages': total_pages or self._total_pages
            })

            # 更新元数据
            if total_count is not None:
                self._total_count = total_count
            if total_pages is not None:
                self._total_pages = total_pages

            # 更新UID映射
            for item in data:
                if 'email_uid' in item and item['email_uid']:
                    self._uid_to_id[item['email_uid']] = item.get('id')
                if 'message_id' in item and item['message_id']:
                    self._message_id_to_id[item['message_id']] = item.get('id')

    def get_submission_by_uid(self, uid: str) -> Optional[Dict]:
        """根据UID快速查找记录"""
        with self._lock:
            # 先从当前页查找
            for item in self._current_data:
                if item.get('email_uid') == uid:
                    return item

            # 从元数据映射获取ID
            if uid in self._uid_to_id:
                return {'id': self._uid_to_id[uid]}

            return None

    def update_single_record(self, uid: str, updates: Dict[str, Any]):
        """
        更新单个记录

        用于增量更新，避免完全重新加载

        Args:
            uid: 邮件UID
            updates: 要更新的字段
        """
        with self._lock:
            # 更新当前页中的记录
            for item in self._current_data:
                if item.get('email_uid') == uid:
                    item.update(updates)
                    break

            # 更新L2缓存中的记录
            for page_key in list(self._page_cache.cache.keys()):
                page_data = self._page_cache.cache[page_key]['data']
                for item in page_data:
                    if item.get('email_uid') == uid:
                        item.update(updates)
                        break

    def invalidate_page(self, page: int = None):
        """
        使指定页缓存失效

        Args:
            page: 页码，None表示清空L2缓存
        """
        with self._lock:
            if page is None:
                self._page_cache.invalidate()
            else:
                self._page_cache.invalidate(page)
                # 如果失效的是当前页，清空L1
                if page == self._current_page:
                    self._current_data = []

    def invalidate_record(self, uid: str):
        """
        使指定记录的缓存失效

        用于记录删除后更新缓存

        Args:
            uid: 邮件UID
        """
        with self._lock:
            # 从当前页移除
            self._current_data = [
                item for item in self._current_data
                if item.get('email_uid') != uid
            ]

            # 从元数据映射移除
            if uid in self._uid_to_id:
                del self._uid_to_id[uid]

            # 从L2缓存移除
            for page_key in list(self._page_cache.cache.keys()):
                page_data = self._page_cache.cache[page_key]['data']
                page_data[:] = [
                    item for item in page_data
                    if item.get('email_uid') != uid
                ]

            # 更新计数
            self._total_count = max(0, self._total_count - 1)

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def total_pages(self) -> int:
        return self._total_pages

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._current_page = 1
            self._current_data = []
            self._total_count = 0
            self._total_pages = 1
            self._page_cache.invalidate()
            self._uid_to_id.clear()
            self._message_id_to_id.clear()


# 全局缓存实例
data_cache = DataCache()
