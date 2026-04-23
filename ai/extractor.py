import json
import re
import asyncio
from openai import AsyncOpenAI
from typing import Dict, List, Optional
from config.settings import settings
from ai.prompts import SYSTEM_PROMPT, get_user_prompt

class AIExtractor:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.API_KEY,
            base_url=settings.LLM_BASE_URL
        )
        self.model = settings.LLM_MODEL

        # 作业名称规范化映射
        self.assignment_patterns = {
            r'[一11][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业1',
            r'[二2two][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业2',
            r'[三3three][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业3',
            r'[四4four][\s]*(?:次|个)?[\s]*(?:作业|实验|assignment|homework|work)': '作业4',
        }

    async def extract_student_info(
        self,
        subject: str,
        sender: str,
        attachments: List[Dict]
    ) -> Dict:
        """
        使用AI提取学生信息

        Args:
            subject: 邮件主题
            sender: 发件人信息
            attachments: 附件列表 [{'filename': ..., 'content': ...}]

        Returns:
            {
                'is_assignment': bool,
                'student_id': str or None,
                'name': str or None,
                'assignment_name': str or None,
                'confidence': float,
                'reasoning': str
            }
        """
        try:
            user_prompt = get_user_prompt(subject, sender, attachments)

            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                ),
                timeout=30.0
            )

            result = json.loads(response.choices[0].message.content)

            # 规范化学号：提取纯数字部分
            if result.get('student_id'):
                student_id = str(result['student_id']).strip()
                # 提取连续的数字部分
                numbers = re.findall(r'\d+', student_id)
                if numbers:
                    # 取最长的一组数字（通常是学号）
                    result['student_id'] = max(numbers, key=len)
                else:
                    result['student_id'] = None

            # 规范化作业名称
            if result.get('assignment_name'):
                result['assignment_name'] = self.normalize_assignment_name(
                    result['assignment_name']
                )

            # 验证学号格式（放宽验证）
            if result.get('student_id'):
                if not self.validate_student_id(result['student_id']):
                    # 如果验证失败，但学号是纯数字且长度合理（6-15位），仍然接受
                    if result['student_id'].isdigit() and 6 <= len(result['student_id']) <= 15:
                        pass  # 接受这个学号
                    else:
                        result['student_id'] = None
                        result['confidence'] *= 0.7

            # 验证姓名格式
            if result.get('name'):
                if not self.validate_name(result['name']):
                    result['name'] = None
                    result['confidence'] *= 0.7

            return result

        except asyncio.TimeoutError:
            print("AI extraction timeout, using fallback")
            return self.fallback_extract(subject, sender, attachments)

        except Exception as e:
            print(f"AI extraction error: {e}, using fallback")
            return self.fallback_extract(subject, sender, attachments)

    def fallback_extract(
        self,
        subject: str,
        sender: str,
        attachments: List[Dict]
    ) -> Dict:
        """
        AI失败时的备用提取方法（使用正则表达式）
        """
        result = {
            'is_assignment': False,
            'student_id': None,
            'name': None,
            'assignment_name': None,
            'confidence': 0.5,
            'reasoning': 'Using regex fallback'
        }

        # 检查是否有附件（作业提交的必要条件）
        if not attachments:
            result['reasoning'] = 'No attachments found'
            return result

        result['is_assignment'] = True

        # 提取学号（支持更长的学号）
        student_id_patterns = [
            r'(\d{12,15})',  # 12-15位数字（长学号优先）
            r'(\d{8,12})',  # 8-12位数字
            r'(\d{6,10})',  # 6-10位数字
        ]
        for pattern in student_id_patterns:
            match = re.search(pattern, subject)
            if match:
                result['student_id'] = match.group(1)
                break

        # 提取姓名
        name_pattern = r'([\u4e00-\u9fa5]{2,4})'
        name_match = re.search(name_pattern, subject)
        if name_match:
            result['name'] = name_match.group(1)

        # 提取作业名称
        for pattern, normalized in self.assignment_patterns.items():
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                result['assignment_name'] = normalized
                break

        # 从发件人信息中提取
        if sender:
            # 尝试从发件人姓名中提取
            name_match = re.search(name_pattern, sender)
            if name_match and not result['name']:
                result['name'] = name_match.group(1)

        return result

    async def extract_with_cache(
        self,
        email_data: Dict,
        use_cache: bool = True
    ) -> Dict:
        """Extract student info with cache support

        Args:
            email_data: Dict with keys: subject, from (sender), attachments
            use_cache: Whether to check cache first

        Returns:
            {
                'student_id': str or None,
                'name': str or None,
                'assignment_name': str or None,
                'is_fallback': bool,
                'confidence': float
            }
        """
        from database.operations import db

        subject = email_data.get('subject', '')
        sender = email_data.get('from', '')
        attachments = email_data.get('attachments', [])

        # Generate cache key from email UID
        email_uid = email_data.get('uid')
        if not email_uid:
            # No UID, can't use cache
            email_uid = f"no_uid_{hash(subject)}"

        # Check cache first
        if use_cache and email_uid.isdigit():
            cached_result = db.get_ai_cache(email_uid)
            if cached_result:
                print(f"[Cache hit] {email_uid}")
                return cached_result

        print(f"[Cache miss] {email_uid}, calling AI")

        # Call AI extraction
        result = await self.extract_student_info(subject, sender, attachments)

        # Extract relevant fields
        cache_result = {
            'student_id': result.get('student_id'),
            'name': result.get('name'),
            'assignment_name': result.get('assignment_name'),
            'is_fallback': 'fallback' in result.get('reasoning', '').lower(),
            'confidence': result.get('confidence', 0.5)
        }

        # Save to cache if we have a valid UID
        if use_cache and email_uid and email_uid.isdigit():
            try:
                db.save_ai_cache(email_uid, cache_result, cache_result['is_fallback'])
            except Exception as e:
                print(f"Warning: Failed to save to cache: {e}")

        return cache_result

    def normalize_assignment_name(self, raw_name: str) -> str:
        """
        规范化作业名称为"作业1/2/3/4"格式
        """
        if not raw_name:
            return None

        raw_name = raw_name.strip()

        # 检查已知模式
        for pattern, normalized in self.assignment_patterns.items():
            if re.search(pattern, raw_name, re.IGNORECASE):
                return normalized

        # 尝试提取数字
        match = re.search(r'\d+', raw_name)
        if match:
            num = int(match.group())
            if 1 <= num <= 4:
                return f"作业{num}"

        # 默认返回原始值
        return raw_name

    def validate_student_id(self, student_id: str) -> bool:
        """
        验证学号格式（进一步放宽验证条件）
        支持：6-15位纯数字（涵盖各种学号格式）
        """
        if not student_id:
            return False

        # 纯数字6-15位（支持长学号，如12-15位）
        if re.match(r'^\d{6,15}$', student_id):
            return True

        # 字母开头+6-10位数字
        if re.match(r'^[A-Za-z]\d{6,10}$', student_id):
            return True

        return False

    def validate_name(self, name: str) -> bool:
        """
        验证姓名格式（支持中文、英文、少数民族姓名）
        """
        if not name:
            return False

        # 标准中文姓名：2-6个汉字
        if re.match(r'^[\u4e00-\u9fa5]{2,6}$', name):
            return True

        # 包含点号的姓名（如维族人名：伊木然·斯拉木）
        if re.match(r'^[\u4e00-\u9fa5··]{2,10}$', name):
            return True

        # 英文姓名：2-30个英文字符（支持空格、点号、连字符）
        if re.match(r'^[A-Za-z\s\.\-]{2,30}$', name):
            return True

        # 混合姓名（中英文混合）
        if re.match(r'^[\u4e00-\u9fa5A-Za-z\s\.\-]{2,30}$', name):
            return True

        return False

# Global AI extractor instance
ai_extractor = AIExtractor()
