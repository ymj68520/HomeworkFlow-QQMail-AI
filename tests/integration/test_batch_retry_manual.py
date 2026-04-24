# test_batch_retry_manual.py
"""
Manual testing script for batch retry functionality

Run with: python test_batch_retry_manual.py
"""

import asyncio
from ai.extractor import ai_extractor

async def test_batch_retry():
    """Manually test batch retry with realistic email data"""

    # Simulate emails with Unknown fields
    test_emails = [
        {
            'uid': '1001',
            'subject': '作业提交',
            'from': '学生 <student@example.com>',
            'attachments': [{'filename': 'report.pdf', 'content': b''}],
            'previous_result': {
                'is_assignment': True,
                'student_id': None,
                'name': None,
                'assignment_name': None,
                'confidence': 0.3,
                'reasoning': 'Could not extract'
            }
        },
        {
            'uid': '1002',
            'subject': '2021001-第一次作业',
            'from': 'Student1 <student1@example.com>',
            'attachments': [{'filename': 'homework.docx', 'content': b''}],
            'previous_result': {
                'is_assignment': True,
                'student_id': '2021001',
                'name': None,
                'assignment_name': None,
                'confidence': 0.5,
                'reasoning': 'Partial extraction'
            }
        },
        {
            'uid': '1003',
            'subject': '张三-实验报告',
            'from': '张三 <zhangsan@example.com>',
            'attachments': [{'filename': 'lab.pdf', 'content': b''}],
            'previous_result': {
                'is_assignment': True,
                'student_id': None,
                'name': '张三',
                'assignment_name': None,
                'confidence': 0.5,
                'reasoning': 'Partial extraction'
            }
        }
    ]

    print("Testing batch retry with 3 emails with Unknown fields...")
    print("="*60)

    results = await ai_extractor.batch_retry_unknown(test_emails)

    print("\nResults:")
    print("="*60)

    for i, (email, result) in enumerate(zip(test_emails, results), 1):
        print(f"\nEmail {i}: {email['uid']}")
        print(f"  Subject: {email['subject']}")
        print(f"  Original: student_id={email['previous_result'].get('student_id')}, "
              f"name={email['previous_result'].get('name')}, "
              f"assignment={email['previous_result'].get('assignment_name')}")
        print(f"  After batch: student_id={result.get('student_id')}, "
              f"name={result.get('name')}, "
              f"assignment={result.get('assignment_name')}")
        print(f"  Confidence: {result.get('confidence', 0):.2f}")

        # Check if extraction improved
        improved = (
            result.get('student_id') and
            result.get('name') and
            result.get('assignment_name')
        )
        print(f"  Status: {'✓ IMPROVED' if improved else '✗ STILL UNKNOWN'}")

    print("\n" + "="*60)
    improved_count = sum(
        1 for r in results
        if r.get('student_id') and r.get('name') and r.get('assignment_name')
    )
    print(f"Summary: {improved_count}/{len(results)} emails improved")
    print("="*60)

if __name__ == '__main__':
    asyncio.run(test_batch_retry())
