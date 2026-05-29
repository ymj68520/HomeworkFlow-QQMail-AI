#!/usr/bin/env python3
"""
修复数据库中不统一的作业名 - 简化版本
直接使用 SQL 来确保更新操作正确执行
"""
import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.models import db_session, Assignment, Submission
from sqlalchemy import text

# 作业名称规范化映射
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
    if not raw_name:
        return raw_name
    raw_name = raw_name.strip()
    for pattern, normalized in ASSIGNMENT_PATTERNS.items():
        if re.search(pattern, raw_name, re.IGNORECASE):
            return normalized
    match = re.search(r'\d+', raw_name)
    if match:
        num = int(match.group())
        if 1 <= num <= 10:
            return f"作业{num}"
    return raw_name


def main():
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

        print("=" * 60)
        print(f"发现 {len(needs_fix)} 个需要修复的作业名：")
        print("=" * 60)
        for item in needs_fix:
            print(f"ID={item['id']}: '{item['old_name']}' -> '{item['new_name']}' "
                  f"({item['submission_count']} 条提交记录)")
        print("=" * 60)

        # 3. 逐个处理每个需要修复的作业
        for item in needs_fix:
            try:
                # 查找目标作业
                target = session.query(Assignment).filter_by(name=item['new_name']).first()

                if target:
                    # 目标作业已存在，需要合并
                    print(f"\n处理 ID={item['id']} ('{item['old_name']}') -> 合并到 ID={target.id} ('{item['new_name']}')")

                    # 使用原始 SQL 更新提交记录
                    session.execute(
                        text("UPDATE submissions SET assignment_id = :target_id WHERE assignment_id = :source_id"),
                        {"target_id": target.id, "source_id": item['id']}
                    )
                    session.flush()

                    # 删除源作业
                    session.execute(
                        text("DELETE FROM assignments WHERE id = :source_id"),
                        {"source_id": item['id']}
                    )
                    session.flush()

                    print(f"  OK: 已合并 {item['submission_count']} 条提交记录")
                else:
                    # 目标作业不存在，直接重命名
                    print(f"\n处理 ID={item['id']} ('{item['old_name']}') -> 重命名为 '{item['new_name']}'")

                    session.execute(
                        text("UPDATE assignments SET name = :new_name WHERE id = :source_id"),
                        {"new_name": item['new_name'], "source_id": item['id']}
                    )
                    session.flush()

                    print(f"  OK: 已重命名")

            except Exception as e:
                print(f"  ERROR: {e}")
                session.rollback()
                raise

        # 4. 提交所有更改
        session.commit()
        print("\n" + "=" * 60)
        print("修复完成！")
        print("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
