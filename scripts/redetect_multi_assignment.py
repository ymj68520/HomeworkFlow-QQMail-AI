#!/usr/bin/env python3
"""
重新检测所有历史邮件的多作业情况

此脚本会：
1. 查找所有没有 group_id 的提交记录
2. 重新运行多作业检测
3. 更新数据库中的 group_id 和 group_order 字段
4. 生成检测报告

使用方法:
    python scripts/redetect_multi_assignment.py [--force] [--dry-run]

选项:
    --force: 强制重新检测所有记录（包括已有 group_id 的）
    --dry-run: 只检测不更新数据库，用于测试
    --limit: 限制处理的记录数量（用于测试）
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.models import db_session, Submission, SubmissionGroup, Attachment
from database.async_operations import async_db
from mail.imap_client import imap_client_target
from mail.parser import MailParser
from ai.multi_assignment_detector import MultiAssignmentDetector
from core.multi_assignment_processor import multi_assignment_processor
from config.settings import settings
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MultiAssignmentRedetector:
    """多作业重新检测器"""

    def __init__(self, force: bool = False, dry_run: bool = False, limit: Optional[int] = None):
        self.force = force
        self.dry_run = dry_run
        self.limit = limit
        self.detector = MultiAssignmentDetector()
        self.imap = imap_client_target
        self.parser = MailParser(self.imap)

        # 统计信息
        self.stats = {
            'total_processed': 0,
            'multi_assignment_detected': 0,
            'single_assignment': 0,
            'detection_failed': 0,
            'already_processed': 0,
            'errors': 0
        }

    async def run(self):
        """执行重新检测流程"""
        logger.info("="*60)
        logger.info("多作业重新检测开始")
        logger.info(f"模式: {'强制重新检测' if self.force else '仅检测未处理的'}")
        logger.info(f"测试模式: {'是' if self.dry_run else '否'}")
        if self.limit:
            logger.info(f"限制记录数: {self.limit}")
        logger.info("="*60)

        try:
            # 1. 获取需要处理的记录
            submissions = await self._get_submissions_to_process()
            logger.info(f"找到 {len(submissions)} 条需要处理的记录")

            if not submissions:
                logger.info("没有需要处理的记录")
                return

            # 2. 连接到 IMAP
            if not self.imap.connect():
                logger.error("无法连接到 IMAP 服务器")
                return

            if not self.imap.select_folder(settings.TARGET_FOLDER):
                logger.error(f"无法选择文件夹: {settings.TARGET_FOLDER}")
                return

            # 3. 处理每条记录
            for idx, submission in enumerate(submissions, 1):
                logger.info(f"\n处理进度: {idx}/{len(submissions)}")

                try:
                    await self._process_submission(submission)
                except Exception as e:
                    logger.error(f"处理记录 {submission.id} 时出错: {e}")
                    self.stats['errors'] += 1
                    continue

            # 4. 断开连接
            self.imap.disconnect()

            # 5. 输出统计报告
            self._print_report()

        except Exception as e:
            logger.exception(f"重新检测过程中出错: {e}")

    async def _get_submissions_to_process(self) -> List[Submission]:
        """获取需要处理的提交记录"""
        with db_session() as session:
            query = session.query(Submission)

            if self.force:
                # 强制模式：获取所有记录
                logger.info("强制模式：获取所有提交记录")
            else:
                # 正常模式：只获取没有 group_id 的记录
                query = query.filter(Submission.group_id.is_(None))
                logger.info("正常模式：仅获取没有 group_id 的记录")

            # 添加学生和作业的预加载以提升性能
            from sqlalchemy.orm import joinedload
            query = query.options(
                joinedload(Submission.student),
                joinedload(Submission.assignment)
            )

            # 应用限制
            if self.limit:
                query = query.limit(self.limit)

            submissions = query.all()
            # 复制到列表中，因为数据库会话会在函数结束时关闭
            return list(submissions)

    async def _process_submission(self, submission: Submission):
        """处理单条提交记录"""
        self.stats['total_processed'] += 1

        logger.info(f"处理记录 ID={submission.id}, UID={submission.email_uid}")

        # 检查是否已经处理过
        if submission.group_id and not self.force:
            logger.info(f"记录已有 group_id={submission.group_id}，跳过")
            self.stats['already_processed'] += 1
            return

        # 检查是否属于现有的 group
        if submission.group_id:
            existing_group = await async_db.get_submission_group_by_email_uid(submission.email_uid)
            if existing_group and not self.force:
                logger.info(f"邮件 {submission.email_uid} 已在 group {existing_group.id} 中，跳过")
                self.stats['already_processed'] += 1
                return

        # 获取邮件数据
        email_data = await self._fetch_email_data(submission)
        if not email_data:
            logger.warning(f"无法获取邮件数据: {submission.email_uid}")
            self.stats['detection_failed'] += 1
            return

        # 运行多作业检测
        detection_result = await self._detect_multi_assignment(email_data)

        if detection_result['is_multi_assignment']:
            await self._handle_multi_assignment(submission, email_data, detection_result)
        else:
            await self._handle_single_assignment(submission)

    async def _fetch_email_data(self, submission: Submission) -> Optional[Dict]:
        """获取邮件数据"""
        try:
            # 使用 MailParser 解析邮件
            parsed_data = self.parser.parse_email(submission.email_uid)
            if not parsed_data:
                logger.warning(f"无法从 IMAP 获取邮件: {submission.email_uid}")
                return None

            # 构建标准格式
            email_data = {
                'uid': parsed_data.get('uid'),
                'message_id': parsed_data.get('uid'),  # 使用 uid 作为 message_id
                'subject': parsed_data.get('subject', ''),
                'from': parsed_data.get('sender_email', ''),
                'sender_email': parsed_data.get('sender_email', ''),
                'sender_name': parsed_data.get('sender_name', ''),
                'date': parsed_data.get('date'),
                'attachments': [
                    {
                        'filename': att.get('filename', ''),
                        'size': att.get('size', 0),
                        'content': att.get('content')  # 可能为空
                    }
                    for att in parsed_data.get('attachments', [])
                ],
                'email_body': parsed_data.get('email_body', {
                    'plain_text': None,
                    'html_markdown': None
                })
            }

            return email_data

        except Exception as e:
            logger.error(f"获取邮件数据时出错: {e}")
            return None

    async def _detect_multi_assignment(self, email_data: Dict) -> Dict:
        """运行多作业检测"""
        try:
            result = await self.detector.detect_multi_assignment(
                subject=email_data.get('subject', ''),
                sender=email_data.get('from', ''),
                attachments=email_data.get('attachments', []),
                email_body=email_data.get('email_body')
            )

            logger.info(f"检测完成: is_multi={result['is_multi_assignment']}, "
                       f"method={result['detection_method']}, "
                       f"confidence={result['overall_confidence']:.2f}")

            if result['is_multi_assignment']:
                assignments = result.get('assignments', [])
                logger.info(f"检测到 {len(assignments)} 个作业:")
                for idx, assign in enumerate(assignments, 1):
                    logger.info(f"  {idx}. {assign.get('assignment_name', 'Unknown')} "
                               f"({len(assign.get('attachments', []))} 个附件)")

            return result

        except Exception as e:
            logger.error(f"多作业检测时出错: {e}")
            return {
                'is_multi_assignment': False,
                'is_complete': False,
                'detection_method': 'error',
                'assignments': [],
                'overall_confidence': 0.0,
                'reasoning': f'检测出错: {str(e)}'
            }

    async def _handle_multi_assignment(
        self,
        submission: Submission,
        email_data: Dict,
        detection_result: Dict
    ):
        """处理检测到的多作业提交"""
        logger.info(f"检测到多作业提交，开始处理...")

        if self.dry_run:
            logger.info("[DRY-RUN] 跳过实际处理")
            self.stats['multi_assignment_detected'] += 1
            return

        try:
            # 使用 multi_assignment_processor 处理
            result = await multi_assignment_processor.process_multi_assignment(
                email_uid=submission.email_uid,
                email_data=email_data,
                detection_result=detection_result
            )

            if result['success']:
                logger.info(f"✓ 多作业处理成功: group_id={result['group_id']}")
                self.stats['multi_assignment_detected'] += 1
            else:
                logger.warning(f"✗ 多作业处理失败: {result.get('error', 'Unknown error')}")
                self.stats['detection_failed'] += 1

        except Exception as e:
            logger.error(f"处理多作业提交时出错: {e}")
            self.stats['detection_failed'] += 1

    async def _handle_single_assignment(self, submission: Submission):
        """处理单作业提交"""
        logger.info(f"检测为单作业提交")

        if self.dry_run:
            logger.info("[DRY-RUN] 跳过更新")
            self.stats['single_assignment'] += 1
            return

        # 单作业提交不需要特殊处理，保持原样
        self.stats['single_assignment'] += 1

    def _print_report(self):
        """打印统计报告"""
        logger.info("\n" + "="*60)
        logger.info("检测完成 - 统计报告")
        logger.info("="*60)
        logger.info(f"总处理记录数:     {self.stats['total_processed']}")
        logger.info(f"检测为多作业:     {self.stats['multi_assignment_detected']}")
        logger.info(f"检测为单作业:     {self.stats['single_assignment']}")
        logger.info(f"检测失败:         {self.stats['detection_failed']}")
        logger.info(f"已处理(跳过):     {self.stats['already_processed']}")
        logger.info(f"处理错误:         {self.stats['errors']}")
        logger.info("="*60)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='重新检测所有历史邮件的多作业情况',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制重新检测所有记录（包括已有 group_id 的）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只检测不更新数据库，用于测试'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='限制处理的记录数量（用于测试）'
    )

    args = parser.parse_args()

    # 创建检测器并运行
    redetector = MultiAssignmentRedetector(
        force=args.force,
        dry_run=args.dry_run,
        limit=args.limit
    )

    await redetector.run()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n用户中断，退出...")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"程序异常退出: {e}")
        sys.exit(1)
