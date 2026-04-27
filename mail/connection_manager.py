"""
IMAP持久连接管理器 - 性能优化核心组件

功能:
- 保持长连接，避免重复连接开销
- 自动心跳检测和重连
- 连接状态监控
- 线程安全
"""
import threading
import time
import imaplib
from typing import Optional, Callable
from mail.imap_client import IMAPClient
from config.settings import settings


class ConnectionManager:
    """
    IMAP持久连接管理器

    设计模式: 单例模式
    线程安全: 使用锁保护连接状态
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self._client: Optional[IMAPClient] = None
        self._connection_lock = threading.RLock()
        self._last_use_time = 0
        self._heartbeat_interval = 30  # 心跳间隔(秒)
        self._auto_reconnect = True
        self._current_folder = None
        self._is_connected = False

    def connect(self) -> bool:
        """
        建立连接

        Returns:
            bool: 连接是否成功
        """
        with self._connection_lock:
            print("[ConnectionManager] connect() called")

            # 如果已经连接，先检查连接是否有效
            if self._is_connected and self._check_connection():
                print("[ConnectionManager] Already connected and valid")
                return True

            # 创建新连接
            print("[ConnectionManager] Creating new IMAPClient...")
            self._client = IMAPClient()
            print("[ConnectionManager] Calling IMAPClient.connect()...")
            if self._client.connect():
                self._is_connected = True
                self._last_use_time = time.time()
                print("[ConnectionManager] Connected successfully")
                return True

            self._is_connected = False
            print("[ConnectionManager] Connection failed")
            return False

    def disconnect(self):
        """断开连接"""
        with self._connection_lock:
            if self._client:
                try:
                    self._client.disconnect()
                except:
                    pass
                finally:
                    self._client = None
                    self._is_connected = False
                    self._current_folder = None
                    print("[ConnectionManager] Disconnected")

    def get_client(self) -> Optional[IMAPClient]:
        """
        获取可用的IMAP客户端

        自动处理重连和心跳检测

        Returns:
            IMAPClient实例或None
        """
        with self._connection_lock:
            # 首次使用或连接断开
            if not self._is_connected or not self._client:
                if not self.connect():
                    return None

            # 检查连接是否仍然有效
            if not self._check_connection():
                if self._auto_reconnect:
                    print("[ConnectionManager] Connection lost, reconnecting...")
                    if not self.connect():
                        return None
                else:
                    return None

            self._last_use_time = time.time()
            return self._client

    def select_folder(self, folder_name: str) -> bool:
        """
        选择文件夹

        Args:
            folder_name: 文件夹名称

        Returns:
            bool: 是否成功
        """
        client = self.get_client()
        if not client:
            return False

        # 如果已经在该文件夹，跳过
        if self._current_folder == folder_name:
            return True

        with self._connection_lock:
            try:
                result = client.select_folder(folder_name)
                if result:
                    self._current_folder = folder_name
                    print(f"[ConnectionManager] Selected folder: {folder_name}")
                return result
            except Exception as e:
                print(f"[ConnectionManager] Error selecting folder: {e}")
                self._is_connected = False
                return False

    def _check_connection(self) -> bool:
        """
        检查连接是否有效

        Returns:
            bool: 连接是否有效
        """
        if not self._client or not self._client.connection:
            return False

        try:
            # 使用NOOP命令检查连接
            self._client.connection.noop()
            return True
        except:
            self._is_connected = False
            return False

    def start_heartbeat(self):
        """启动心跳检测线程"""
        def heartbeat_loop():
            while self._auto_reconnect:
                time.sleep(self._heartbeat_interval)

                # 检查是否需要发送心跳
                if self._is_connected and self._client:
                    with self._connection_lock:
                        if not self._check_connection():
                            print("[ConnectionManager] Heartbeat detected connection lost")
                        else:
                            # 发送NOOP保持连接活跃
                            try:
                                self._client.connection.noop()
                            except:
                                self._is_connected = False

        thread = threading.Thread(target=heartbeat_loop, daemon=True)
        thread.start()
        print("[ConnectionManager] Heartbeat thread started")

    @property
    def is_connected(self) -> bool:
        """当前连接状态"""
        return self._is_connected and self._check_connection()

    @property
    def current_folder(self) -> Optional[str]:
        """当前选择的文件夹"""
        return self._current_folder


# 全局单例实例
connection_manager = ConnectionManager()
