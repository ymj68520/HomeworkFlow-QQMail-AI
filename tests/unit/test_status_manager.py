"""
状态管理器单元测试
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from database.models import db_session, Base, engine
from database.operations import DatabaseOperations
from core.sync_status_manager import SyncStatusManager
from core.status_manager import TRANSITION_RULES
from sqlalchemy import text


class TestStatusManager(unittest.TestCase):
    """状态管理器单元测试"""

    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.db = DatabaseOperations()

    def setUp(self):
        """每个测试前的准备"""
        self.session = db_session()
        self.status_mgr = SyncStatusManager(self.session)

    def tearDown(self):
        """每个测试后的清理"""
        self.session.close()

    def test_transition_rules_exist(self):
        """测试状态转换规则存在"""
        self.assertIn('processing', TRANSITION_RULES)
        self.assertIn('ai_extraction', TRANSITION_RULES)
        self.assertIn('download', TRANSITION_RULES)
        self.assertIn('reply', TRANSITION_RULES)

    def test_can_transition_valid(self):
        """测试合法的状态转换"""
        # 处理状态的合法转换
        self.assertTrue(self.status_mgr.can_transition('received', 'processing', 'processing'))
        self.assertTrue(self.status_mgr.can_transition('processing', 'extracted', 'processing'))
        self.assertTrue(self.status_mgr.can_transition('extracted', 'downloading', 'processing'))

        # AI提取状态的合法转换
        self.assertTrue(self.status_mgr.can_transition('pending', 'extracting', 'ai_extraction'))
        self.assertTrue(self.status_mgr.can_transition('extracting', 'success', 'ai_extraction'))

        # 下载状态的合法转换
        self.assertTrue(self.status_mgr.can_transition('pending', 'downloading', 'download'))
        self.assertTrue(self.status_mgr.can_transition('downloading', 'success', 'download'))

        # 回复状态的合法转换
        self.assertTrue(self.status_mgr.can_transition('pending', 'sending', 'reply'))
        self.assertTrue(self.status_mgr.can_transition('sending', 'success', 'reply'))

    def test_can_transition_invalid(self):
        """测试非法的状态转换"""
        # 不允许从终态转换到其他状态
        self.assertFalse(self.status_mgr.can_transition('replied', 'processing', 'processing'))
        self.assertFalse(self.status_mgr.can_transition('success', 'pending', 'ai_extraction'))

        # 不允许跨类型转换
        self.assertFalse(self.status_mgr.can_transition('received', 'sending', 'reply'))

    def test_validate_transition(self):
        """测试状态转换验证"""
        # 合法转换
        is_valid, error = self.status_mgr._validate_transition(
            'received', 'processing', 'processing'
        )
        self.assertTrue(is_valid)
        self.assertEqual(error, '')

        # 非法转换
        is_valid, error = self.status_mgr._validate_transition(
            'replied', 'processing', 'processing'
        )
        self.assertFalse(is_valid)
        self.assertIn('Invalid transition', error)

    def test_get_legacy_status(self):
        """测试向后兼容的状态计算"""
        # 各种组合的测试
        test_cases = [
            ({'processing_status': 'ignored'}, 'ignored'),
            ({'processing_status': 'replied'}, 'completed'),
            ({'processing_status': 'downloaded'}, 'unreplied'),
            ({'ai_status': 'failed'}, 'ai_error'),
            ({'download_status': 'failed'}, 'download_failed'),
            ({'processing_status': 'received'}, 'pending'),
        ]

        for statuses, expected in test_cases:
            # 补充完整的status字典
            full_statuses = {
                'processing_status': 'received',
                'ai_status': 'pending',
                'download_status': 'pending',
                'reply_status': 'pending'
            }
            full_statuses.update(statuses)

            result = self.status_mgr.get_legacy_status(full_statuses)
            self.assertEqual(result, expected, f"Failed for {statuses}")

    def test_get_retry_status(self):
        """测试重试状态获取"""
        # 处理状态的重置
        retry_status = self.status_mgr._get_retry_status('processing', 'failed')
        self.assertEqual(retry_status, 'processing')

        # AI提取状态的重置
        retry_status = self.status_mgr._get_retry_status('ai_extraction', 'failed')
        self.assertEqual(retry_status, 'pending')

        # 下载状态的重置
        retry_status = self.status_mgr._get_retry_status('download', 'failed')
        self.assertEqual(retry_status, 'pending')

        # 回复状态的重置
        retry_status = self.status_mgr._get_retry_status('reply', 'failed')
        self.assertEqual(retry_status, 'pending')

    def test_get_abnormal_statuses(self):
        """测试异常状态列表"""
        abnormal = self.status_mgr.get_abnormal_statuses()
        self.assertIn('failed', abnormal)
        self.assertIn('ai_error', abnormal)
        self.assertIn('download_failed', abnormal)
        self.assertIn('pending', abnormal)

    def test_get_all_statuses_empty(self):
        """测试获取不存在的记录的状态"""
        statuses = self.status_mgr.get_all_statuses(999999)
        self.assertEqual(statuses, {})

    def test_get_history_empty(self):
        """测试获取不存在记录的历史"""
        history = self.status_mgr.get_history(999999)
        self.assertEqual(history, [])


class TestStatusManagerIntegration(unittest.TestCase):
    """状态管理器集成测试（需要数据库）"""

    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.db = DatabaseOperations()

    def setUp(self):
        """每个测试前的准备"""
        self.session = db_session()
        self.status_mgr = SyncStatusManager(self.session)

        # 创建测试学生和作业
        self.student = self.db.create_student('TEST001', '测试学生')
        self.assignment = self.db.create_assignment('测试作业')

    def tearDown(self):
        """每个测试后的清理"""
        # 清理测试数据
        try:
            self.session.execute(text("DELETE FROM submissions WHERE student_id = :sid"), {'sid': self.student.id})
            self.session.execute(text("DELETE FROM students WHERE student_id = 'TEST001'"))
            self.session.execute(text("DELETE FROM assignments WHERE name = '测试作业'"))
            self.session.commit()
        except:
            self.session.rollback()
        finally:
            self.session.close()

    def test_create_submission_with_status(self):
        """测试创建带新状态的提交记录"""
        from datetime import datetime
        submission = self.db.create_submission(
            email_uid='test_uid_001',
            email_subject='测试邮件',
            sender_email='test@example.com',
            sender_name='测试学生',
            submission_time=datetime.now(),
            student_id='TEST001',
            assignment_name='测试作业',
            status='pending'
        )

        self.assertIsNotNone(submission)
        self.assertEqual(submission.processing_status, 'received')
        self.assertEqual(submission.ai_status, 'pending')
        self.assertEqual(submission.download_status, 'pending')
        self.assertEqual(submission.reply_status, 'pending')

    def test_transition_workflow(self):
        """测试完整的状态转换工作流"""
        from datetime import datetime
        # 创建提交记录
        submission = self.db.create_submission(
            email_uid='test_uid_002',
            email_subject='测试邮件2',
            sender_email='test@example.com',
            sender_name='测试学生',
            submission_time=datetime.now(),
            student_id='TEST001',
            assignment_name='测试作业',
            status='pending'
        )

        submission_id = submission.id

        # 模拟处理流程
        # 1. 开始AI提取
        result = self.status_mgr.transition(
            submission_id, 'ai_extraction', 'extracting',
            reason='开始AI提取'
        )
        self.assertTrue(result)

        # 2. AI提取成功
        result = self.status_mgr.transition(
            submission_id, 'ai_extraction', 'success',
            reason='AI提取成功',
            metadata={'confidence': 0.95}
        )
        self.assertTrue(result)

        # 3. 开始下载
        result = self.status_mgr.transition(
            submission_id, 'download', 'downloading',
            reason='开始下载附件'
        )
        self.assertTrue(result)

        # 4. 下载成功
        result = self.status_mgr.transition(
            submission_id, 'download', 'success',
            reason='附件下载成功'
        )
        self.assertTrue(result)

        # 5. 开始发送回复
        result = self.status_mgr.transition(
            submission_id, 'reply', 'sending',
            reason='开始发送回复'
        )
        self.assertTrue(result)

        # 6. 回复成功
        result = self.status_mgr.transition(
            submission_id, 'reply', 'success',
            reason='回复发送成功'
        )
        self.assertTrue(result)

        # 验证最终状态
        statuses = self.status_mgr.get_all_statuses(submission_id)
        self.assertEqual(statuses['ai_status'], 'success')
        self.assertEqual(statuses['download_status'], 'success')
        self.assertEqual(statuses['reply_status'], 'success')

        # 验证历史记录
        history = self.status_mgr.get_history(submission_id)
        self.assertEqual(len(history), 6)

    def test_invalid_transition_blocked(self):
        """测试非法转换被阻止"""
        from datetime import datetime
        # 创建提交记录
        submission = self.db.create_submission(
            email_uid='test_uid_003',
            email_subject='测试邮件3',
            sender_email='test@example.com',
            sender_name='测试学生',
            submission_time=datetime.now(),
            student_id='TEST001',
            assignment_name='测试作业',
            status='pending'
        )

        # 尝试非法转换：从终态转换到其他状态
        result = self.status_mgr.transition(
            submission.id, 'processing', 'replied',
            reason='非法转换测试'
        )
        # 这个转换应该是无效的，因为当前状态是 received，不能直接跳到 replied
        self.assertFalse(result)

    def test_reset_to_retry(self):
        """测试重置为重试状态"""
        from datetime import datetime
        # 创建提交记录
        submission = self.db.create_submission(
            email_uid='test_uid_004',
            email_subject='测试邮件4',
            sender_email='test@example.com',
            sender_name='测试学生',
            submission_time=datetime.now(),
            student_id='TEST001',
            assignment_name='测试作业',
            status='pending'
        )

        # 设置为失败状态
        self.status_mgr.transition(
            submission.id, 'ai_extraction', 'failed',
            reason='AI提取失败'
        )

        # 重置为重试
        result = self.status_mgr.reset_to_retry(
            submission.id, 'ai_extraction'
        )
        self.assertTrue(result)

        # 验证状态已重置
        status = self.status_mgr.get_status(submission.id, 'ai_extraction')
        self.assertEqual(status, 'pending')


if __name__ == '__main__':
    unittest.main()
