"""
修复数据库中错误的作业名称
使用AI从邮件主题中提取正确的作业名称
"""
import asyncio
from database.models import SessionLocal, Submission, Assignment
from ai.extractor import ai_extractor

async def fix_assignment_names():
    """使用AI修复数据库中错误的作业名称"""
    session = SessionLocal()

    try:
        # 获取所有提交记录
        submissions = session.query(Submission).all()
        print(f"总提交记录: {len(submissions)}")

        fixed_count = 0
        error_count = 0

        for submission in submissions:
            assignment_name = submission.assignment.name

            # 检查是否为"作业+长数字"格式（学号被误认为作业号）
            if assignment_name.startswith('作业'):
                num_part = assignment_name[2:]

                # 如果数字部分长度>=10，很可能是学号而不是作业号
                if num_part.isdigit() and len(num_part) >= 10:
                    print(f"\n发现错误的作业名称:")
                    print(f"  ID: {submission.id}")
                    print(f"  学生: {submission.student.student_id} - {submission.student.name}")
                    print(f"  错误的作业名称: {assignment_name}")
                    print(f"  邮件主题: {submission.email_subject}")

                    # 使用AI提取正确的作业编号
                    correct_assignment = await extract_correct_assignment_with_ai(
                        submission.email_subject
                    )
                    print(f"  正确的作业名称: {correct_assignment}")

                    if correct_assignment and correct_assignment != 'Unknown':
                        # 查找或创建正确的作业记录
                        correct_assignment_record = session.query(Assignment).filter_by(
                            name=correct_assignment
                        ).first()

                        if not correct_assignment_record:
                            correct_assignment_record = Assignment(name=correct_assignment)
                            session.add(correct_assignment_record)
                            session.flush()

                        # 更新提交记录的作业ID
                        old_assignment_id = submission.assignment_id
                        submission.assignment_id = correct_assignment_record.id

                        print(f"  [OK] 已修复: {assignment_name} -> {correct_assignment}")
                        fixed_count += 1

                        # 检查旧的作业记录是否还有其他提交使用
                        old_users = session.query(Submission).filter_by(
                            assignment_id=old_assignment_id
                        ).count()

                        if old_users == 0:
                            print(f"  (旧的作业记录 '{assignment_name}' 已无引用，可删除)")
                    else:
                        print(f"  [ERROR] AI无法提取正确的作业名称")
                        error_count += 1

        session.commit()
        print(f"\n修复完成:")
        print(f"  成功修复: {fixed_count} 条")
        print(f"  失败: {error_count} 条")

    except Exception as e:
        session.rollback()
        print(f"修复失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

async def extract_correct_assignment_with_ai(email_subject: str) -> str:
    """使用AI从邮件主题中提取正确的作业编号"""
    if not email_subject:
        return None

    try:
        result = await ai_extractor.extract_with_cache({
            'uid': f"fix_{hash(email_subject)}",
            'subject': email_subject,
            'from': '',
            'attachments': []
        })

        return result.get('assignment_name')
    except Exception as e:
        print(f"AI extraction error: {e}")
        return None

if __name__ == '__main__':
    print("开始使用AI修复数据库中的作业名称...")
    asyncio.run(fix_assignment_names())
