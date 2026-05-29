#!/usr/bin/env python3
"""
修复数据库中不统一的作业名

此脚本会：
1. 查找所有需要规范化的作业名
2. 将它们统一为"作业X"格式
3. 更新 assignments 表

使用方法:
    python scripts/fix_assignment_names.py [--dry-run] [--force]

选项:
    --dry-run: 只显示将要执行的操作，不实际修改数据库
    --force: 强制执行，无需确认
"""

import sys
import os
import re
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.models import db_session, Assignment, Submission

# 作业名称规范化映射
# 注意：中文数字匹配必须放在阿拉伯数字之前
ASSIGNMENT_PATTERNS = {
    r'(?:作业|实验)[\s]*五': '作业5',
    r'(?:作业|实验)[\s]*四': '作业4',
    r'(?:作业|实验)[\s]*三': '作业3',
    r'(?:作业|实验)[\s]*二': '作业2',
    r'(?:作业|实验)[\s]*一': '作业1',
    r'[五5five][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业5',
    r'[四4four][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业4',
    r'[三3three][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业3',
    r'[二2two][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业2',
    r'[一11][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业1',
}


def normalize_assignment_name(raw_name: str) -> str:
    """
    规范化作业名称为"作业1/2/3/4/5"格式

    Args:
        raw_name: 原始作业名称

    Returns:
        规范化后的作业名称
    """
    if not raw_name:
        return raw_name

    raw_name = raw_name.strip()

    # 检查已知模式
    for pattern, normalized in ASSIGNMENT_PATTERNS.items():
        if re.search(pattern, raw_name, re.IGNORECASE):
            return normalized

    # 尝试提取阿拉伯数字
    match = re.search(r'\d+', raw_name)
    if match:
        num = int(match.group())
        if 1 <= num <= 10:
            return f"作业{num}"

    # 默认返回原始值
    return raw_name


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='修复数据库中不统一的作业名',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只显示将要执行的操作，不实际修改数据库'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制执行，无需确认'
    )

    args = parser.parse_args()

    with db_session() as session:
        # 1. 查询所有作业名
        assignments = session.query(Assignment).all()

        # 2. 找出需要修复的作业
        needs_fix = []
        for assignment in assignments:
            normalized = normalize_assignment_name(assignment.name)
            if assignment.name != normalized:
                submission_count = session.query(Submission).filter(
                    Submission.assignment_id == assignment.id
                ).count()
                needs_fix.append({
                    'id': assignment.id,
                    'old_name': assignment.name,
                    'new_name': normalized,
                    'submission_count': submission_count
                })

        if not needs_fix:
            print("所有作业名已是规范格式，无需修复。")
            return

        # 3. 显示将要执行的修复操作
        print("=" * 60)
        print(f"发现 {len(needs_fix)} 个需要修复的作业名：")
        print("=" * 60)
        for item in needs_fix:
            print(f"ID={item['id']}: '{item['old_name']}' -> '{item['new_name']}' "
                  f"({item['submission_count']} 条提交记录)")
        print("=" * 60)

        if args.dry_run:
            print("\n[DRY-RUN] 模式：不会实际修改数据库")
            return

        # 4. 确认执行
        if not args.force:
            response = input("\n确认执行修复操作？(yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("操作已取消")
                return

        # 5. 执行修复
        print("\n开始修复...")
        success_count = 0
        for item in needs_fix:
            try:
                assignment = session.query(Assignment).filter_by(id=item['id']).first()
                if assignment:
                    # 检查是否已存在同名作业
                    existing = session.query(Assignment).filter_by(name=item['new_name']).first()
                    if existing and existing.id != item['id']:
                        print(f"  警告: 目标作业名 '{item['new_name']}' 已存在 (ID={existing.id})，将合并")
                        # 使用 no_autoflush 避免自动刷新导致的问题
                        with session.no_autoflush:
                            # 更新该作业的所有提交记录指向目标作业
                            submissions = session.query(Submission).filter_by(assignment_id=item['id']).all()
                            for sub in submissions:
                                sub.assignment_id = existing.id
                            # 删除重复的作业记录
                            session.delete(assignment)
                        session.commit()  # 提交这个合并操作
                    else:
                        # 直接更新作业名
                        assignment.name = item['new_name']
                    success_count += 1
                    print(f"  OK {item['old_name']} -> {item['new_name']}")
            except Exception as e:
                print(f"  ERROR: 修复失败: {e}")
                session.rollback()  # 回滚失败的操作

        # 最终提交（处理直接更新的情况）
        try:
            session.commit()
        except Exception as e:
            print(f"最终提交失败: {e}")
            session.rollback()

        print("=" * 60)
        print(f"修复完成！成功处理 {success_count}/{len(needs_fix)} 个作业名")
        print("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
