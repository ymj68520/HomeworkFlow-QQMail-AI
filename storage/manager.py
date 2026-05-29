import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from config.settings import settings

class StorageManager:
    """本地文件存储管理器"""

    def __init__(self):
        self.root = settings.SUBMISSIONS_DIR
        self.root.mkdir(exist_ok=True)

        # 元数据文件
        self.metadata_file = self.root / '_metadata.json'
        self.index_file = self.root / '_index.json'

        # 初始化元数据
        self._init_metadata()

    def _init_metadata(self):
        """初始化元数据文件"""
        if not self.metadata_file.exists():
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

        if not self.index_file.exists():
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

    def store_submission(
        self,
        assignment_name: str,
        student_id: str,
        name: str,
        attachments: List[Dict]
    ) -> str:
        """
        存储学生作业

        创建目录结构：submissions/作业1/2021001张三/

        Args:
            assignment_name: 作业名称（如"作业1"）
            student_id: 学号
            name: 姓名
            attachments: 附件列表

        Returns:
            本地存储路径
        """
        try:
            # 1. 创建目录结构
            assignment_dir = self.root / assignment_name
            student_dir = assignment_dir / f"{student_id}{name}"

            assignment_dir.mkdir(exist_ok=True)
            student_dir.mkdir(exist_ok=True)

            saved_files = []

            # 2. 保存附件
            for attachment in attachments:
                filename = attachment['filename']
                content = attachment['content']

                # 处理重复文件名
                file_path = student_dir / filename
                if file_path.exists():
                    file_path = self._resolve_duplicate_filename(file_path)

                # 保存文件
                with open(file_path, 'wb') as f:
                    f.write(content)

                saved_files.append({
                    'filename': filename,
                    'path': str(file_path),
                    'size': len(content)
                })

                print(f"  Saved: {filename} ({len(content)} bytes)")

            # 3. 更新元数据
            self._update_metadata(student_dir, {
                'student_id': student_id,
                'name': name,
                'assignment': assignment_name,
                'files': saved_files,
                'saved_at': datetime.now().isoformat()
            })

            # 4. 更新索引
            self._update_index(student_id, name, assignment_name, str(student_dir))

            return str(student_dir)

        except Exception as e:
            print(f"Error storing submission: {e}")
            return None

    def _resolve_duplicate_filename(self, file_path: Path) -> Path:
        """解决重复文件名"""
        base = file_path.stem
        ext = file_path.suffix
        parent = file_path.parent

        counter = 1
        while True:
            new_path = parent / f"{base} ({counter}){ext}"
            if not new_path.exists():
                return new_path
            counter += 1

    def _update_metadata(self, student_dir: Path, data: dict):
        """更新学生目录的元数据"""
        metadata_path = student_dir / '_metadata.json'

        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error updating metadata: {e}")

    def _update_index(self, student_id: str, name: str, assignment: str, path: str):
        """更新全局索引"""
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)

            key = f"{student_id}_{name}_{assignment}"
            index[key] = {
                'student_id': student_id,
                'name': name,
                'assignment': assignment,
                'path': path,
                'updated_at': datetime.now().isoformat()
            }

            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error updating index: {e}")

    def delete_files(self, local_path: str) -> bool:
        """删除本地文件"""
        try:
            path = Path(local_path)
            if path.exists() and path.is_dir():
                import shutil
                shutil.rmtree(path)
                print(f"Deleted local files: {path}")
                return True
            return False

        except Exception as e:
            print(f"Error deleting files: {e}")
            return False

    def get_file_hash(self, content: bytes) -> str:
        """计算文件哈希值"""
        return hashlib.sha256(content).hexdigest()

    def verify_file_integrity(self, file_path: Path, expected_size: int) -> bool:
        """验证文件完整性"""
        try:
            if not file_path.exists():
                return False

            actual_size = file_path.stat().st_size
            return actual_size == expected_size

        except Exception as e:
            print(f"Error verifying file integrity: {e}")
            return False

    def get_submission_files(self, local_path: str) -> List[str]:
        """获取提交的所有文件路径"""
        try:
            path = Path(local_path)
            if not path.exists():
                return []

            files = []
            for item in path.iterdir():
                if item.is_file() and not item.name.startswith('_'):
                    files.append(str(item))

            return files

        except Exception as e:
            print(f"Error getting submission files: {e}")
            return []

    def get_assignment_stats(self, assignment_name: str) -> dict:
        """获取作业统计信息"""
        try:
            assignment_dir = self.root / assignment_name
            if not assignment_dir.exists():
                return {'total_students': 0, 'total_files': 0}

            student_dirs = [d for d in assignment_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]

            total_files = 0
            for student_dir in student_dirs:
                files = [f for f in student_dir.iterdir() if f.is_file() and not f.name.startswith('_')]
                total_files += len(files)

            return {
                'total_students': len(student_dirs),
                'total_files': total_files
            }

        except Exception as e:
            print(f"Error getting assignment stats: {e}")
            return {'total_students': 0, 'total_files': 0}

    def get_all_assignments(self) -> List[str]:
        """获取所有作业目录"""
        try:
            assignments = []
            for item in self.root.iterdir():
                if item.is_dir() and not item.name.startswith('_'):
                    assignments.append(item.name)
            return sorted(assignments)

        except Exception as e:
            print(f"Error getting assignments: {e}")
            return []

# Global storage manager instance
storage_manager = StorageManager()
