"""为现有数据建立去重关系（parent_id, relation_type, is_primary）"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import db_session, Submission, Student, Assignment
from sqlalchemy import and_, or_, func
from datetime import datetime

def build_deduplication_relations():
    """为现有数据建立去重关系"""
    try:
        print("开始为现有数据建立去重关系...")

        # 1. 查找所有提交记录
        all_submissions = db_session.query(Submission).all()
        print(f"找到 {len(all_submissions)} 条提交记录")

        # 2. 按 student_id + assignment_name 分组
        from sqlalchemy.orm import joinedload

        grouped = {}
        for sub in all_submissions:
            student_id = sub.student_id if hasattr(sub, 'student') else None
            assignment_id = sub.assignment_id

            if student_id and assignment_id:
                key = (student_id, assignment_id)
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(sub)

        print(f"分为 {len(grouped)} 个学生-作业组合")

        # 3. 为每个组建立版本关系
        updated_count = 0
        for (student_id, assignment_id), group in grouped.items():
            # 按提交时间排序
            group.sort(key=lambda x: x.submission_time if x.submission_time else datetime.min)

            # 最新的作为主记录
            for i, sub in enumerate(group):
                if i == 0:
                    # 最新记录是主记录
                    if sub.is_primary != True:
                        sub.is_primary = True
                        sub.parent_id = None
                        sub.relation_type = None
                        updated_count += 1
                else:
                    # 旧记录作为子记录
                    sub.is_primary = False
                    sub.parent_id = group[0].id
                    sub.relation_type = 'version'
                    sub.version = i + 1
                    updated_count += 1

        # 4. 查找可能的重复（学号或姓名相同但作业不同）
        print("\n查找可能的重复...")
        for (student_id, assignment_id), group in grouped.items():
            if len(group) > 1:
                # 对于有多条记录的学生，检查是否有其他可能的重复
                # 这里简化处理，只处理同一个学生-作业的重复
                pass

        # 5. 提交更改
        db_session.commit()
        print(f"✓ 成功更新 {updated_count} 条记录")
        print(f"  - 主记录: {len([s for s in all_submissions if s.is_primary])}")
        print(f"  - 子记录: {len([s for s in all_submissions if not s.is_primary])}")

        # 6. 验证结果
        print("\n验证结果:")
        primary_count = db_session.query(Submission).filter_by(is_primary=True).count()
        child_count = db_session.query(Submission).filter_by(is_primary=False).count()
        print(f"  主记录: {primary_count}")
        print(f"  子记录: {child_count}")

        # 7. 显示有子记录的主记录
        records_with_children = db_session.query(Submission).filter_by(is_primary=True).all()
        records_with_children = [r for r in records_with_children if db_session.query(Submission).filter_by(parent_id=r.id).count() > 0]
        print(f"\n有子记录的主记录: {len(records_with_children)}")

        for r in records_with_children[:10]:  # 只显示前10个
            child_count = db_session.query(Submission).filter_by(parent_id=r.id).count()
            student = r.student if hasattr(r, 'student') else None
            assignment = r.assignment if hasattr(r, 'assignment') else None
            student_id = student.student_id if student else "Unknown"
            assignment_name = assignment.name if assignment else "Unknown"
            print(f"  - {student_id} - {assignment_name}: {child_count} 条子记录")

        if len(records_with_children) > 10:
            print(f"  ... 还有 {len(records_with_children) - 10} 条记录")

        return True

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        db_session.rollback()
        return False

if __name__ == "__main__":
    build_deduplication_relations()
