"""
QQ邮箱作业收发AI系统 - 应用入口
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from gui.main_window import MainWindow
from core.workflow import workflow
from config.settings import settings

def main():
    """主函数"""
    import sys
    # 修复 Windows 控制台编码问题，并启用行缓冲让日志实时显示
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

    print("="*60)
    print("QQ邮箱作业收发AI系统")
    print("="*60)

    # 验证配置
    try:
        settings.validate()
        print("✓ 配置验证通过")
    except ValueError as e:
        print(f"✗ 配置错误: {e}")
        return

    # 启用数据库WAL模式和异步操作（异步）
    try:
        import asyncio
        from database.models import enable_wal_mode
        from database.async_operations import async_db

        async def init_db():
            await enable_wal_mode()
            # 初始化后台缓存写入器
            await async_db.initialize()

        asyncio.run(init_db())
        print("✓ 数据库WAL模式已启用")
        print("✓ 异步数据库操作已初始化")
    except Exception as e:
        print(f"⚠ 数据库初始化警告: {e}")

    # 启动GUI
    try:
        from PySide6.QtWidgets import QApplication
        from gui.main_window import MainWindow
        import sys

        print("启动图形界面...")
        app = QApplication(sys.argv)
        
        # 加载样式
        try:
            with open("gui/styles/theme.qss", "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except Exception as e:
            print(f"Warning: Could not load theme.qss: {e}")

        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
