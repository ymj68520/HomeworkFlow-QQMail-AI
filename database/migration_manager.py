"""
数据库迁移管理器

自动按顺序应用所有迁移脚本，确保数据库架构与代码保持同步。
支持重复执行（幂等性），不会因为字段已存在而报错。
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import List, Tuple
import sqlite3
from config.settings import settings


class MigrationManager:
    """数据库迁移管理器"""

    def __init__(self, migrations_dir: str = None):
        """
        初始化迁移管理器

        Args:
            migrations_dir: 迁移脚本目录路径，默认为项目根目录下的migrations
        """
        project_root = Path(__file__).parent.parent

        if migrations_dir is None:
            migrations_dir = project_root / "migrations"

        self.migrations_dir = Path(migrations_dir)
        self.extra_migrations_dir = project_root / "database" / "migrations"
        self.db_path = settings.DATABASE_PATH

        # 确保迁移目录存在
        if not self.migrations_dir.exists():
            raise FileNotFoundError(f"Migration directory not found: {self.migrations_dir}")

    def _ensure_migration_table(self):
        """确保迁移记录表存在"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    migration_name VARCHAR(255) NOT NULL UNIQUE,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_applied_migrations(self) -> List[str]:
        """获取已应用的迁移列表"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT migration_name FROM schema_migrations ORDER BY id")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def _mark_migration_applied(self, migration_name: str):
        """标记迁移为已应用"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO schema_migrations (migration_name) VALUES (?)",
                (migration_name,)
            )
            conn.commit()
        finally:
            conn.close()

    def _discover_migrations(self) -> List[Tuple[str, Path]]:
        """
        发现所有迁移脚本（扫描 migrations/ 和 database/migrations/ 两个目录）

        Returns:
            按文件名排序的迁移列表 [(migration_name, migration_path), ...]
        """
        migrations = []

        # 扫描主迁移目录
        for py_file in sorted(self.migrations_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            migrations.append((py_file.stem, py_file))

        # 扫描 database/migrations/ 目录
        if self.extra_migrations_dir.exists():
            for py_file in sorted(self.extra_migrations_dir.glob("*.py")):
                if py_file.name == "__init__.py":
                    continue
                # 避免同名冲突
                name = py_file.stem
                if not any(n == name for n, _ in migrations):
                    migrations.append((name, py_file))

        # 按文件名排序确保执行顺序
        migrations.sort(key=lambda x: x[0])
        return migrations

    def _load_migration_module(self, migration_path: Path):
        """
        动态加载迁移模块

        Args:
            migration_path: 迁移脚本路径

        Returns:
            迁移模块
        """
        spec = importlib.util.spec_from_file_location(migration_path.stem, migration_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _has_migrate_function(self, module) -> bool:
        """检查模块是否有migrate或upgrade函数"""
        return (hasattr(module, 'migrate') and callable(module.migrate)) or \
               (hasattr(module, 'upgrade') and callable(module.upgrade))

    def migrate(self, dry_run: bool = False) -> Tuple[bool, List[str]]:
        """
        执行所有未应用的迁移

        Args:
            dry_run: 如果为True，只显示将要执行的迁移，不实际执行

        Returns:
            (success, messages) - 是否成功，消息列表
        """
        messages = []

        try:
            # 确保迁移记录表存在
            self._ensure_migration_table()

            # 获取已应用的迁移
            applied_migrations = self._get_applied_migrations()
            messages.append(f"[INFO] Found {len(applied_migrations)} already applied migrations")

            # 发现所有迁移
            all_migrations = self._discover_migrations()
            messages.append(f"[INFO] Found {len(all_migrations)} total migration scripts")

            # 过滤出未应用的迁移
            pending_migrations = [
                (name, path) for name, path in all_migrations
                if name not in applied_migrations
            ]

            if not pending_migrations:
                messages.append("[INFO] No pending migrations to apply")
                return True, messages

            messages.append(f"[INFO] {len(pending_migrations)} migrations pending execution")

            if dry_run:
                messages.append("[DRY RUN] Would apply the following migrations:")
                for name, path in pending_migrations:
                    messages.append(f"  - {name}")
                return True, messages

            # 执行每个待应用的迁移
            success_count = 0
            for migration_name, migration_path in pending_migrations:
                messages.append(f"\n[PROCESSING] Applying migration: {migration_name}")

                try:
                    # 加载迁移模块
                    module = self._load_migration_module(migration_path)

                    # 检查是否有migrate函数
                    if not self._has_migrate_function(module):
                        messages.append(f"[WARN] Migration {migration_name} has no migrate() function, skipping")
                        continue

                    # 执行迁移（支持 migrate() 和 upgrade() 两种函数签名）
                    import inspect
                    import asyncio

                    if hasattr(module, 'migrate') and callable(module.migrate):
                        migrate_fn = module.migrate
                    else:
                        migrate_fn = module.upgrade

                    # 有些迁移需要database_path参数，有些不带参数
                    sig = inspect.signature(migrate_fn)
                    params = list(sig.parameters.keys())

                    if len(params) > 0 and params[0] == 'database_path':
                        result = migrate_fn(str(self.db_path))
                    elif asyncio.iscoroutinefunction(migrate_fn):
                        result = asyncio.run(migrate_fn())
                    else:
                        result = migrate_fn()

                    # 检查结果
                    if result is False:
                        messages.append(f"[ERROR] Migration {migration_name} failed")
                        return False, messages

                    # 标记为已应用
                    self._mark_migration_applied(migration_name)
                    messages.append(f"[OK] Migration {migration_name} applied successfully")
                    success_count += 1

                except Exception as e:
                    messages.append(f"[ERROR] Failed to apply migration {migration_name}: {e}")
                    import traceback
                    messages.append(traceback.format_exc())
                    return False, messages

            messages.append(f"\n[SUCCESS] Applied {success_count}/{len(pending_migrations)} migrations")
            return True, messages

        except Exception as e:
            messages.append(f"[ERROR] Migration manager failed: {e}")
            import traceback
            messages.append(traceback.format_exc())
            return False, messages

    def get_status(self) -> dict:
        """
        获取迁移状态

        Returns:
            包含迁移状态的字典
        """
        self._ensure_migration_table()

        applied = self._get_applied_migrations()
        all_migrations = self._discover_migrations()

        pending = [name for name, _ in all_migrations if name not in applied]

        return {
            "total": len(all_migrations),
            "applied": len(applied),
            "pending": len(pending),
            "applied_migrations": applied,
            "pending_migrations": pending
        }


def run_migrations(dry_run: bool = False) -> bool:
    """
    便捷函数：运行所有迁移

    Args:
        dry_run: 如果为True，只显示将要执行的迁移

    Returns:
        是否成功
    """
    manager = MigrationManager()
    success, messages = manager.migrate(dry_run=dry_run)

    for msg in messages:
        print(msg)

    return success


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Database migration manager')
    parser.add_argument('--dry-run', action='store_true', help='Show pending migrations without applying')
    parser.add_argument('--status', action='store_true', help='Show migration status')
    args = parser.parse_args()

    manager = MigrationManager()

    if args.status:
        status = manager.get_status()
        print(f"Total migrations: {status['total']}")
        print(f"Applied: {status['applied']}")
        print(f"Pending: {status['pending']}")
        if status['pending_migrations']:
            print(f"\nPending migrations:")
            for name in status['pending_migrations']:
                print(f"  - {name}")
    else:
        success = run_migrations(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
