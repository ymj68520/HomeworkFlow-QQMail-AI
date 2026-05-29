"""多作业提交检测器模块"""

import json
import hashlib
import asyncio
import logging
import re
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from config.settings import settings
from ai.prompts import (
    MULTI_ASSIGNMENT_SYSTEM_PROMPT,
    get_multi_assignment_user_prompt,
    get_multi_assignment_body_prompt
)
from database.async_operations import async_db

logger = logging.getLogger(__name__)

# 作业名称规范化映射 - 与 extractor.py 保持一致
# 注意：中文数字匹配必须放在阿拉伯数字之前，避免"作业四"匹配到数字4
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
        raw_name: 原始作业名称（可能是 "实验3"、"作业四"、"Assignment 2" 等）

    Returns:
        规范化后的作业名称（"作业1"、"作业2" 等）
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
        if 1 <= num <= 10:  # 支持更多作业
            return f"作业{num}"

    # 默认返回原始值
    return raw_name


class MultiAssignmentDetector:
    """多作业提交检测器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.API_KEY,
            base_url=settings.LLM_BASE_URL
        )
        self.model = settings.LLM_MODEL
        self.config = settings.MULTI_ASSIGNMENT_CONFIG

    async def detect_multi_assignment(
        self,
        subject: str,
        sender: str,
        attachments: List[Dict],
        email_body: Optional[Dict] = None
    ) -> Dict:
        """
        检测是否为多作业提交

        Args:
            subject: 邮件主题
            sender: 发件人信息
            attachments: 附件列表 [{'filename': ..., 'content': ...}]
            email_body: 邮件正文 {'plain_text': ..., 'html_markdown': ...}

        Returns:
            Detection result dict with keys:
            - is_multi_assignment: bool
            - is_complete: bool
            - detection_method: str
            - assignments: List[Dict]
            - unassigned_attachments: List[str]
            - overall_confidence: float
            - student_id: str or None
            - name: str or None
            - reasoning: str
        """
        if not settings.ENABLE_MULTI_ASSIGNMENT:
            return self._single_assignment_result()

        # Build cache key
        cache_key = self._build_cache_key(subject, sender, attachments)

        # Check cache
        cached = await async_db.get_multi_assignment_cache(cache_key)
        if cached:
            return cached

        # Step 1: Subject analysis
        if self.config['enable_subject_detection']:
            result = await self._analyze_subject(subject, sender, attachments)
            if result['is_multi_assignment'] and result['is_complete']:
                await self._save_cache(cache_key, result)
                return result

        # Step 2: Filename analysis
        if self.config['enable_filename_detection']:
            result = await self._analyze_filenames(subject, sender, attachments)
            if result['is_multi_assignment'] and result['is_complete']:
                await self._save_cache(cache_key, result)
                return result

        # Step 3: Body analysis
        if self.config['enable_body_detection'] and email_body:
            result = await self._analyze_body(subject, sender, attachments, email_body)
            if result['is_multi_assignment'] and result['is_complete']:
                await self._save_cache(cache_key, result)
                return result

        # All methods failed
        result = self._single_assignment_result()
        await self._save_cache(cache_key, result)
        return result

    def _single_assignment_result(self) -> Dict:
        """返回单作业结果"""
        return {
            'is_multi_assignment': False,
            'is_complete': False,
            'detection_method': 'none',
            'assignments': [],
            'unassigned_attachments': [],
            'overall_confidence': 0.0,
            'student_id': None,
            'name': None,
            'reasoning': '未检测到多作业提交'
        }

    async def _analyze_subject(self, subject: str, sender: str, attachments: List[Dict]) -> Dict:
        """从邮件主题识别"""
        prompt = get_multi_assignment_user_prompt(subject, sender, attachments, 'subject')
        try:
            result = await self._call_ai(prompt)
            result['detection_method'] = 'subject'
            return self._validate_result(result, attachments)
        except Exception as e:
            logger.error(f"Error in subject analysis: {e}")
            return self._single_assignment_result()

    async def _analyze_filenames(self, subject: str, sender: str, attachments: List[Dict]) -> Dict:
        """从附件文件名识别"""
        prompt = get_multi_assignment_user_prompt(subject, sender, attachments, 'filename')
        try:
            result = await self._call_ai(prompt)
            result['detection_method'] = 'filename'
            return self._validate_result(result, attachments)
        except Exception as e:
            logger.error(f"Error in filename analysis: {e}")
            return self._single_assignment_result()

    async def _analyze_body(self, subject: str, sender: str, attachments: List[Dict], email_body: Dict) -> Dict:
        """从邮件正文识别"""
        body_text = email_body.get('plain_text') or email_body.get('html_markdown', '')
        if not body_text:
            return self._single_assignment_result()

        prompt = get_multi_assignment_body_prompt(subject, sender, attachments, body_text)
        try:
            result = await self._call_ai(prompt)
            result['detection_method'] = 'body'
            return self._validate_result(result, attachments)
        except Exception as e:
            logger.error(f"Error in body analysis: {e}")
            return self._single_assignment_result()

    async def _call_ai(self, prompt: str) -> Dict:
        """调用AI进行识别"""
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": MULTI_ASSIGNMENT_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                ),
                timeout=30.0
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except asyncio.TimeoutError:
            logger.error("AI extraction timeout")
            return self._single_assignment_result()
        except Exception as e:
            logger.error(f"AI extraction error: {e}")
            return self._single_assignment_result()

    def _validate_result(self, result: Dict, attachments: List[Dict]) -> Dict:
        """验证和标准化AI返回结果"""
        # 规范化作业名称
        for assignment in result.get('assignments', []):
            if assignment.get('assignment_name'):
                original_name = assignment['assignment_name']
                normalized_name = normalize_assignment_name(original_name)
                if original_name != normalized_name:
                    logger.info(f"规范化作业名: '{original_name}' -> '{normalized_name}'")
                assignment['assignment_name'] = normalized_name

        # Check confidence threshold
        overall_confidence = result.get('overall_confidence', 0.0)
        if overall_confidence < self.config['min_confidence_threshold']:
            result['is_complete'] = False
            result['reasoning'] = f"置信度{overall_confidence}低于阈值{self.config['min_confidence_threshold']}"
            return result

        # Check if all attachments are assigned
        attachment_names = {att['filename'] for att in attachments}
        assigned_names = set()

        for assignment in result.get('assignments', []):
            for att_name in assignment.get('attachments', []):
                assigned_names.add(att_name)

        unassigned = list(attachment_names - assigned_names)

        if unassigned and self.config['strict_mode']:
            result['is_complete'] = False
            result['unassigned_attachments'] = unassigned
            result['reasoning'] = f"以下附件无法确定归属: {', '.join(unassigned)}"
        else:
            result['is_complete'] = True
            result['unassigned_attachments'] = []

        return result

    def _build_cache_key(self, subject: str, sender: str, attachments: List[Dict]) -> str:
        """构建缓存键"""
        key_data = f"{subject}:{sender}"
        if attachments:
            attachment_info = ":".join([f"{att.get('filename','')}{att.get('size',0)}" for att in attachments])
            key_data += f":{attachment_info}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def _save_cache(self, cache_key: str, result: Dict):
        """保存到缓存"""
        try:
            # Convert result to JSON-serializable format
            cache_data = {
                'is_multi_assignment': result.get('is_multi_assignment', False),
                'is_complete': result.get('is_complete', False),
                'detection_method': result.get('detection_method', 'none'),
                'assignments': result.get('assignments', []),
                'unassigned_attachments': result.get('unassigned_attachments', []),
                'overall_confidence': result.get('overall_confidence', 0.0),
                'student_id': result.get('student_id'),
                'name': result.get('name'),
                'reasoning': result.get('reasoning', '')
            }
            await async_db.save_multi_assignment_cache(cache_key, cache_data)
        except Exception as e:
            logger.error(f"Warning: Failed to save multi-assignment cache: {e}")


# Global instance
multi_assignment_detector = MultiAssignmentDetector()