# core/version_manager.py
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Optional, Union


class VersionInfo:
    """Information about a submission version"""
    def __init__(self, version: int, path: Path, created_at: str, email_uid: str):
        self.version = version
        self.path = path
        self.created_at = created_at
        self.email_uid = email_uid


class VersionManager:
    """版本管理器：管理作业提交的版本控制"""

    def __init__(self, root_dir: Union[str, Path]):
        """初始化版本管理器

        Args:
            root_dir: 根目录路径，用于存储所有作业提交
        """
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def get_student_dir(self, assignment: str, student_id: str, name: str) -> Path:
        """获取学生作业目录路径

        Args:
            assignment: 作业名称
            student_id: 学号
            name: 学生姓名

        Returns:
            Path: 学生作业目录路径
        """
        # 格式: 作业名称/学号姓名
        assignment_dir = self.root_dir / assignment
        student_dir = assignment_dir / f"{student_id}{name}"
        return student_dir

    def get_next_version(self, student_id: str, name: str, assignment: str) -> int:
        """获取下一个版本号

        Args:
            student_id: 学号
            name: 学生姓名
            assignment: 作业名称

        Returns:
            int: 下一个版本号（从1开始）
        """
        student_dir = self.get_student_dir(assignment, student_id, name)

        # 获取现有版本
        existing_versions = []
        if student_dir.exists():
            for item in student_dir.iterdir():
                if item.is_dir() and item.name.startswith('v') and item.name[1:].isdigit():
                    version_num = int(item.name[1:])
                    existing_versions.append(version_num)

        # 版本号从1开始，下一个版本 = 最大现有版本 + 1（如果没有现有版本则为1）
        return max(existing_versions) + 1 if existing_versions else 1

    def create_version_folder(self, student_id: str, name: str,
                           assignment: str, version: int) -> Path:
        """创建版本文件夹

        Args:
            student_id: 学号
            name: 学生姓名
            assignment: 作业名称
            version: 版本号

        Returns:
            Path: 创建的版本文件夹路径，如果创建失败则返回None
        """
        student_dir = self.get_student_dir(assignment, student_id, name)
        version_dir = student_dir / f"v{version}"

        # 确保父目录存在
        version_dir.mkdir(parents=True, exist_ok=True)

        # 创建_metadata.json文件
        metadata = VersionInfo(
            version=version,
            path=version_dir,
            created_at=datetime.now().isoformat(),
            email_uid=f"{student_id}@university.edu"
        )

        metadata_file = version_dir / "_metadata.json"
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': metadata.version,
                    'path': str(metadata.path),
                    'created_at': metadata.created_at,
                    'email_uid': metadata.email_uid
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # 如果JSON写入失败，清理创建的空目录
            import shutil
            shutil.rmtree(version_dir)
            raise Exception(f"Failed to create metadata file: {e}")

        # 创建_latest标记文件（删除旧的_latest文件）
        latest_file = student_dir / "_latest"
        if latest_file.exists():
            latest_file.unlink()
        latest_file.touch()

        return version_dir

    def get_all_versions(self, student_id: str, name: str, assignment: str) -> List[VersionInfo]:
        """获取指定学生的所有版本信息

        Args:
            student_id: 学号
            name: 学生姓名
            assignment: 作业名称

        Returns:
            List[VersionInfo]: 所有版本信息列表（按升序排列）
        """
        student_dir = self.get_student_dir(assignment, student_id, name)

        if not student_dir.exists():
            return []

        versions = []
        for item in student_dir.iterdir():
            if item.is_dir() and item.name.startswith('v') and item.name[1:].isdigit():
                version_num = int(item.name[1:])
                metadata_file = item / "_metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    versions.append(VersionInfo(
                        version=metadata['version'],
                        path=item,
                        created_at=metadata['created_at'],
                        email_uid=metadata['email_uid']
                    ))

        return sorted(versions, key=lambda v: v.version)

    def get_latest_version(self, student_id: str, name: str, assignment: str) -> Optional[VersionInfo]:
        """获取指定学生的最新版本信息

        Args:
            student_id: 学号
            name: 学生姓名
            assignment: 作业名称

        Returns:
            Optional[VersionInfo]: 最新版本信息，如果没有则返回None
        """
        all_versions = self.get_all_versions(student_id, name, assignment)
        return max(all_versions, key=lambda v: v.version) if all_versions else None

    def get_version_folder(self, student_id: str, name: str,
                          assignment: str, version: int) -> Optional[Path]:
        """获取指定版本文件夹的路径

        Args:
            student_id: 学号
            name: 学生姓名
            assignment: 作业名称
            version: 版本号

        Returns:
            Optional[Path]: 版本文件夹路径，如果不存在则返回None
        """
        student_dir = self.get_student_dir(assignment, student_id, name)
        version_dir = student_dir / f"v{version}"

        return version_dir if version_dir.exists() else None


# 全局实例
version_manager = VersionManager(Path.cwd() / "submissions")
