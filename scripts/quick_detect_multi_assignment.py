#!/usr/bin/env python3
"""
快速检测多作业提交 - 简化版

此脚本快速扫描数据库中的提交记录，统计可能的多作业提交情况。
不进行实际处理，只做统计和展示。

使用方法:
    python scripts/quick_detect_multi_assignment.py
"""

import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.models import db_session, Submission, SubmissionGroup, Attachment
from sqlalchemy import func


def print_section(title):
    """打印分隔线"""
    print("\n" + "="*60)
    print(title)
    print("="*60)


def analyze_multi_assignments():
    """分析多作业提交情况"""
    print_section("多作业提交快速检测")

    with db_session() as session:
        # 1. 基本统计
        print("\n【基本统计】")
        total_submissions = session.query(func.count(Submission.id)).scalar()
        with_group_id = session.query(func.count(Submission.id)).filter(
            Submission.group_id.isnot(None)
        ).scalar()
        without_group_id = total_submissions - with_group_id

        print(f"总提交记录数:           {total_submissions}")
        print(f"已有 group_id 的记录:   {with_group_id} ({with_group_id/total_submissions*100:.1f}%)")
        print(f"没有 group_id 的记录:   {without_group_id} ({without_group_id/total_submissions*100:.1f}%)")

        # 2. 提交组统计
        print("\n【提交组统计】")
        total_groups = session.query(func.count(SubmissionGroup.id)).scalar()
        completed_groups = session.query(func.count(SubmissionGroup.id)).filter(
            SubmissionGroup.status == 'completed'
        ).scalar()
        processing_groups = session.query(func.count(SubmissionGroup.id)).filter(
            SubmissionGroup.status == 'processing'
        ).scalar()
        failed_groups = session.query(func.count(SubmissionGroup.id)).filter(
            SubmissionGroup.status == 'failed'
        ).scalar()
        manual_review_groups = session.query(func.count(SubmissionGroup.id)).filter(
            SubmissionGroup.status == 'manual_review'
        ).scalar()

        print(f"总提交组数:             {total_groups}")
        print(f"  - 已完成:             {completed_groups}")
        print(f"  - 处理中:             {processing_groups}")
        print(f"  - 失败:               {failed_groups}")
        print(f"  - 待人工审核:         {manual_review_groups}")

        # 3. 按组大小统计
        print("\n【组大小分布】")
        group_sizes = session.query(
            Submission.group_id,
            func.count(Submission.id).label('count')
        ).filter(
            Submission.group_id.isnot(None)
        ).group_by(Submission.group_id).all()

        size_distribution = defaultdict(int)
        for group_id, count in group_sizes:
            size_distribution[count] += 1

        print(f"组大小分布 (共 {len(group_sizes)} 个组):")
        for size in sorted(size_distribution.keys()):
            print(f"  {size} 个作业的组:         {size_distribution[size]} 个")

        # 4. 最大的几个组
        print("\n【最大的5个提交组】")
        top_groups = session.query(
            SubmissionGroup.id,
            SubmissionGroup.email_subject,
            SubmissionGroup.sender_name,
            SubmissionGroup.total_assignments,
            SubmissionGroup.status
        ).order_by(
            SubmissionGroup.total_assignments.desc()
        ).limit(5).all()

        for idx, group in enumerate(top_groups, 1):
            print(f"{idx}. 组 ID={group.id}, 作业数={group.total_assignments}, "
                  f"状态={group.status}, 发件人={group.sender_name}")

        # 5. 检测方法分布
        print("\n【检测方法分布】")
        method_distribution = session.query(
            SubmissionGroup.detection_method,
            func.count(SubmissionGroup.id).label('count')
        ).group_by(
            SubmissionGroup.detection_method
        ).all()

        for method, count in method_distribution:
            print(f"  {method or '未知'}:           {count} 个组")

        # 6. 可能需要重新处理的记录
        print("\n【可能需要重新处理的记录】")
        # 查找有多个附件但没有 group_id 的记录
        submissions_with_attachments = session.query(
            Submission.id,
            Submission.email_subject,
            Submission.sender_email,
            func.count(Attachment.id).label('attachment_count')
        ).join(
            Submission.attachments
        ).filter(
            Submission.group_id.is_(None)
        ).group_by(
            Submission.id
        ).having(
            func.count(Attachment.id) >= 2
        ).all()

        print(f"找到 {len(submissions_with_attachments)} 条有 2+ 附件但没有 group_id 的记录:")
        for idx, sub in enumerate(submissions_with_attachments[:10], 1):
            print(f"  {idx}. ID={sub.id}, 附件数={sub.attachment_count}, "
                  f"主题={sub.email_subject[:50]}...")

        if len(submissions_with_attachments) > 10:
            print(f"  ... 还有 {len(submissions_with_attachments) - 10} 条")

        # 7. 建议
        print("\n【建议】")
        if without_group_id > 0:
            print(f"[OK] 有 {without_group_id} 条记录没有 group_id")
            print(f"  建议运行: python scripts/redetect_multi_assignment.py")

            if submissions_with_attachments:
                print(f"[OK] 其中有 {len(submissions_with_attachments)} 条有多附件，很可能是多作业提交")
                print(f"  优先处理这些记录可获得更好的效果")
        else:
            print("[OK] 所有记录都已处理，无需重新检测")

        if failed_groups > 0:
            print(f"[!] 有 {failed_groups} 个组处理失败，可能需要人工检查")

        if manual_review_groups > 0:
            print(f"[!] 有 {manual_review_groups} 个组待人工审核")

    print("\n" + "="*60)


if __name__ == '__main__':
    try:
        analyze_multi_assignments()
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
