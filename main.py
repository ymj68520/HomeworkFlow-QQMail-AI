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

    # 启动GUI
    try:
        print("启动图形界面...")
        app = MainWindow()
        app.mainloop()
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
