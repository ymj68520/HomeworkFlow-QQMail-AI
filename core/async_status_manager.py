"""
异步状态管理器 - 用于异步数据库操作
"""
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from core.status_manager import BaseStatusManager


class AsyncStatusManager(BaseStatusManager):
    """异步状态管理器"""

    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)

    async def transition(
        self,
        submission_id: int,
        status_type: str,
        new_status: str,
        reason: str = None,
        metadata: Dict = None
    ) -> bool:
        """执行状态转换，自动记录历史"""
        try:
            # 获取当前状态
            current_status = await self.get_status(submission_id, status_type)
            if current_status is None:
                # 新记录，允许设置初始状态
                current_status = 'pending'

            # 验证转换
            is_valid, error_msg = self._validate_transition(
                current_status, new_status, status_type
            )
            if not is_valid:
                print(f"[StatusManager] Invalid transition: {error_msg}")
                return False

            # 确定字段名
            status_field = f"{status_type}_status"
            updated_at_field = f"{status_type}_status_updated_at"

            # 更新状态
            update_query = text(f"""
                UPDATE submissions
                SET {status_field} = :new_status,
                    {updated_at_field} = CURRENT_TIMESTAMP
                WHERE id = :submission_id
            """)

            await self.db.execute(update_query, {
                'new_status': new_status,
                'submission_id': submission_id
            })

            # 记录历史
            await self._record_history(
                submission_id, status_type, current_status, new_status, reason, metadata
            )

            # 更新兼容的旧status字段
            await self._update_legacy_status(submission_id)

            await self.db.commit()
            return True

        except Exception as e:
            await self.db.rollback()
            print(f"[StatusManager] Error in transition: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def transition_batch(
        self,
        submission_ids: List[int],
        status_type: str,
        new_status: str,
        reason: str = None
    ) -> Dict[str, int]:
        """批量状态转换"""
        results = {'success': 0, 'failed': 0}

        for submission_id in submission_ids:
            if await self.transition(submission_id, status_type, new_status, reason):
                results['success'] += 1
            else:
                results['failed'] += 1

        return results

    async def get_status(
        self,
        submission_id: int,
        status_type: str
    ) -> Optional[str]:
        """获取指定类型的状态"""
        try:
            status_field = f"{status_type}_status"
            query = text(f"""
                SELECT {status_field} FROM submissions WHERE id = :submission_id
            """)

            result = await self.db.execute(query, {'submission_id': submission_id})
            row = result.fetchone()
            return row[0] if row else None

        except Exception as e:
            print(f"[StatusManager] Error getting status: {e}")
            return None

    async def get_all_statuses(self, submission_id: int) -> Dict[str, str]:
        """获取所有维度的状态"""
        try:
            query = text("""
                SELECT processing_status, ai_status, download_status, reply_status
                FROM submissions WHERE id = :submission_id
            """)

            result = await self.db.execute(query, {'submission_id': submission_id})
            row = result.fetchone()

            if row:
                return {
                    'processing_status': row[0],
                    'ai_status': row[1],
                    'download_status': row[2],
                    'reply_status': row[3]
                }
            return {}

        except Exception as e:
            print(f"[StatusManager] Error getting all statuses: {e}")
            return {}

    async def get_history(
        self,
        submission_id: int,
        status_type: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取状态历史记录"""
        try:
            if status_type:
                query = text("""
                    SELECT status_type, old_status, new_status, reason, extra_data, created_at
                    FROM status_history
                    WHERE submission_id = :submission_id AND status_type = :status_type
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)
                params = {'submission_id': submission_id, 'status_type': status_type, 'limit': limit}
            else:
                query = text("""
                    SELECT status_type, old_status, new_status, reason, extra_data, created_at
                    FROM status_history
                    WHERE submission_id = :submission_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)
                params = {'submission_id': submission_id, 'limit': limit}

            result = await self.db.execute(query, params)
            rows = result.fetchall()

            history = []
            for row in rows:
                import json
                history.append({
                    'status_type': row[0],
                    'old_status': row[1],
                    'new_status': row[2],
                    'reason': row[3],
                    'extra_data': json.loads(row[4]) if row[4] else None,
                    'created_at': row[5]
                })

            return history

        except Exception as e:
            print(f"[StatusManager] Error getting history: {e}")
            return []

    async def reset_to_retry(
        self,
        submission_id: int,
        status_type: str = None
    ) -> bool:
        """重置为可重试状态"""
        try:
            statuses = await self.get_all_statuses(submission_id)
            if not statuses:
                return False

            # 如果未指定status_type，自动检测并重置失败的
            if status_type is None:
                # 检查各个状态，重置失败的
                for stype, svalue in statuses.items():
                    sname = stype.replace('_status', '')
                    if svalue in ['failed', 'download_failed']:
                        retry_status = self._get_retry_status(sname, svalue)
                        if retry_status:
                            await self.transition(
                                submission_id, sname, retry_status,
                                reason=f"Auto-reset from {svalue} for retry"
                            )
                return True

            # 重置指定的状态类型
            current_status = statuses.get(f"{status_type}_status")
            retry_status = self._get_retry_status(status_type, current_status)

            if retry_status:
                return await self.transition(
                    submission_id, status_type, retry_status,
                    reason=f"Reset from {current_status} for retry"
                )

            return False

        except Exception as e:
            print(f"[StatusManager] Error in reset_to_retry: {e}")
            return False

    async def get_failed_submissions(
        self,
        status_type: str = None,
        status_code: str = None
    ) -> List[Dict]:
        """获取失败的提交记录"""
        try:
            if status_type and status_code:
                status_field = f"{status_type}_status"
                query = text(f"""
                    SELECT s.id, s.email_uid, s.student_id, s.assignment_id,
                           s.{status_field}, st.student_id, a.name
                    FROM submissions s
                    LEFT JOIN students st ON s.student_id = st.id
                    LEFT JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.{status_field} = :status_code
                    ORDER BY s.created_at DESC
                """)
                params = {'status_code': status_code}
            elif status_type:
                status_field = f"{status_type}_status"
                query = text(f"""
                    SELECT s.id, s.email_uid, s.student_id, s.assignment_id,
                           s.{status_field}, st.student_id, a.name
                    FROM submissions s
                    LEFT JOIN students st ON s.student_id = st.id
                    LEFT JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.{status_field} IN ('failed', 'download_failed', 'ai_error')
                    ORDER BY s.created_at DESC
                """)
                params = {}
            else:
                # 获取所有异常状态的记录
                query = text("""
                    SELECT s.id, s.email_uid, s.student_id, s.assignment_id,
                           s.processing_status, s.ai_status, s.download_status, s.reply_status,
                           st.student_id, a.name
                    FROM submissions s
                    LEFT JOIN students st ON s.student_id = st.id
                    LEFT JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.processing_status = 'failed'
                       OR s.ai_status = 'failed'
                       OR s.download_status = 'failed'
                       OR s.reply_status = 'failed'
                    ORDER BY s.created_at DESC
                """)
                params = {}

            result = await self.db.execute(query, params)
            rows = result.fetchall()

            submissions = []
            for row in rows:
                if status_type:
                    submissions.append({
                        'id': row[0],
                        'email_uid': row[1],
                        'student_db_id': row[2],
                        'assignment_id': row[3],
                        'status': row[4],
                        'student_id': row[5],
                        'assignment_name': row[6]
                    })
                else:
                    submissions.append({
                        'id': row[0],
                        'email_uid': row[1],
                        'student_db_id': row[2],
                        'assignment_id': row[3],
                        'processing_status': row[4],
                        'ai_status': row[5],
                        'download_status': row[6],
                        'reply_status': row[7],
                        'student_id': row[8],
                        'assignment_name': row[9]
                    })

            return submissions

        except Exception as e:
            print(f"[StatusManager] Error getting failed submissions: {e}")
            return []

    async def _record_history(
        self,
        submission_id: int,
        status_type: str,
        old_status: str,
        new_status: str,
        reason: str = None,
        metadata: Dict = None
    ):
        """记录状态变化历史"""
        try:
            import json
            extra_data = json.dumps(metadata) if metadata else None

            query = text("""
                INSERT INTO status_history
                (submission_id, status_type, old_status, new_status, reason, extra_data, created_at)
                VALUES (:submission_id, :status_type, :old_status, :new_status, :reason, :extra_data, CURRENT_TIMESTAMP)
            """)

            await self.db.execute(query, {
                'submission_id': submission_id,
                'status_type': status_type,
                'old_status': old_status,
                'new_status': new_status,
                'reason': reason,
                'extra_data': extra_data
            })

        except Exception as e:
            print(f"[StatusManager] Error recording history: {e}")

    async def _update_legacy_status(self, submission_id: int):
        """更新兼容的旧status字段"""
        try:
            statuses = await self.get_all_statuses(submission_id)
            legacy_status = self.get_legacy_status(statuses)

            query = text("""
                UPDATE submissions
                SET status = :status
                WHERE id = :submission_id
            """)

            await self.db.execute(query, {
                'status': legacy_status,
                'submission_id': submission_id
            })

        except Exception as e:
            print(f"[StatusManager] Error updating legacy status: {e}")


# 全局实例（延迟初始化）
_async_status_manager = None


def get_async_status_manager(db_session: AsyncSession):
    """获取异步状态管理器实例"""
    global _async_status_manager
    if _async_status_manager is None:
        _async_status_manager = AsyncStatusManager(db_session)
    return _async_status_manager
