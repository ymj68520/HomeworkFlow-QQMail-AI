"""
全局数据库写队列 - 解决 SQLite 并发写问题

只有一个写线程处理所有写操作，确保数据库操作串行执行。
"""
import threading
import queue
import logging
from typing import Callable, Any, Optional
from concurrent.futures import Future
import traceback

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 改为 INFO 级别，减少 DEBUG 输出
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WriteQueue:
    """
    全局数据库写队列

    所有数据库写操作通过此队列串行执行，避免 SQLite 锁定冲突。
    """

    _instance: Optional['WriteQueue'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = True

        logger.info("WriteQueue initialized")

    def start(self):
        """启动写队列工作线程"""
        if self._running:
            logger.debug("Write queue already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="DatabaseWriteQueue",
            daemon=False  # 改为非守护线程，确保任务完成
        )
        self._worker_thread.start()
        logger.info(f"Database write queue worker started (thread: {self._worker_thread.name}, alive: {self._worker_thread.is_alive()})")

    def stop(self):
        """停止写队列"""
        if not self._running:
            return

        self._running = False
        # 发送停止信号
        self._queue.put(None)

        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
            if self._worker_thread.is_alive():
                logger.warning("Write queue worker did not stop gracefully")

        logger.info("Database write queue stopped")

    def _worker_loop(self):
        """工作线程循环"""
        logger.info(f"Write queue worker loop started (thread: {threading.current_thread().name})")

        while self._running:
            try:
                logger.debug(f"Waiting for task... (queue size: {self._queue.qsize()})")
                task = self._queue.get(timeout=1.0)
                logger.debug(f"Got task: {task}")

                if task is None:  # 停止信号
                    logger.info("Received stop signal")
                    break

                func, args, kwargs, future = task
                logger.debug(f"Executing function: {func.__name__ if hasattr(func, '__name__') else 'lambda'}")

                try:
                    result = func(*args, **kwargs)
                    logger.debug(f"Function completed successfully: {result}")
                    if future:
                        future.set_result(result)
                        logger.debug("Future result set")
                except Exception as e:
                    logger.error(f"Write operation failed: {e}")
                    logger.debug(traceback.format_exc())
                    if future:
                        future.set_exception(e)
                        logger.debug("Future exception set")

            except queue.Empty:
                logger.debug("Queue empty, continuing...")
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                logger.debug(traceback.format_exc())

        logger.info("Write queue worker loop stopped")

    def submit(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Future:
        """
        提交写操作到队列

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Future 对象，可用于获取结果

        Example:
            future = write_queue.submit(db.create_submission, ...)
            result = future.result(timeout=5.0)
        """
        if not self._running:
            self.start()

        future = Future()
        self._queue.put((func, args, kwargs, future))
        return future

    def submit_sync(
        self,
        func: Callable[..., Any],
        *args,
        timeout: float = 30.0,
        **kwargs
    ) -> Any:
        """
        提交写操作并同步等待结果

        Args:
            func: 要执行的函数
            *args: 位置参数
            timeout: 超时时间（秒）
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            TimeoutError: 超时
            Exception: 函数执行异常
        """
        future = self.submit(func, *args, **kwargs)
        return future.result(timeout=timeout)

    def submit_async(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ):
        """
        提交写操作并返回异步可等待对象

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            可等待的协程

        Example:
            result = await write_queue.submit_async(db.create_submission, ...)
        """
        import asyncio

        if not self._running:
            self.start()

        future = self.submit(func, *args, **kwargs)
        return asyncio.wrap_future(future)

    @property
    def queue_size(self) -> int:
        """获取当前队列大小"""
        return self._queue.qsize()


# 全局实例
write_queue = WriteQueue()


def with_write_queue(func: Callable) -> Callable:
    """
    装饰器：自动将函数调用通过写队列执行

    Example:
        @with_write_queue
        def create_submission(...):
            ...

        # 现在所有调用都会通过写队列
        create_submission(...)  # 自动通过队列
    """
    def wrapper(*args, **kwargs):
        # 检测是否在事件循环中
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            # 在异步上下文中，返回协程
            return write_queue.submit_async(func, *args, **kwargs)
        except RuntimeError:
            # 没有事件循环，同步执行
            return write_queue.submit_sync(func, *args, **kwargs)

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper._original_func = func
    return wrapper
