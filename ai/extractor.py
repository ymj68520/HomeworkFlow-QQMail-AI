import json
import re
import asyncio
import hashlib
from openai import AsyncOpenAI
from typing import Dict, List, Optional
from config.settings import settings
from ai.prompts import SYSTEM_PROMPT, get_user_prompt
from database.async_operations import async_db

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
        使用AI提取学生信息（带缓存）

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
        # 1. 构建缓存键
        cache_key = self._build_cache_key(subject, sender, attachments)

        # 2. 先检查缓存
        cached = await async_db.get_ai_cache(cache_key)
        if cached:
            print(f"AI cache hit for {cache_key}")
            return cached

        # 3. 缓存未命中，调用AI
        print(f"AI cache miss, calling API for {cache_key}")
        result = await self._extract_from_ai(subject, sender, attachments)

        # 4. 保存到缓存
        await async_db.save_ai_cache(cache_key, result, is_fallback=False)

        return result

    def _build_cache_key(self, subject: str, sender: str, attachments: List[Dict]) -> str:
        """构建缓存键"""
        key_data = f"{subject}:{sender}"
        if attachments:
            # 使用第一个附件的文件名和大小作为缓存键的一部分
            first_file = attachments[0]
            key_data += f":{first_file.get('filename', '')}:{first_file.get('size', 0)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def _extract_from_ai(
        self,
        subject: str,
        sender: str,
        attachments: List[Dict]
    ) -> Dict:
        """实际调用AI提取信息"""
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

    async def fallback_extract(
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
        subject = email_data.get('subject', '')
        sender = email_data.get('from', '')
        attachments = email_data.get('attachments', [])

        # Call main extraction method (now has built-in cache support)
        result = await self.extract_student_info(subject, sender, attachments)

        # Extract relevant fields for cache format
        return {
            'student_id': result.get('student_id'),
            'name': result.get('name'),
            'assignment_name': result.get('assignment_name'),
            'is_fallback': 'fallback' in result.get('reasoning', '').lower(),
            'confidence': result.get('confidence', 0.5)
        }

    async def batch_extract(
        self,
        email_list: List[Dict],
        batch_size: int = 10
    ) -> List[Dict]:
        """Extract student info from multiple emails concurrently

        Args:
            email_list: List of email_data dicts with keys: uid, subject, from, attachments
            batch_size: Number of concurrent AI calls

        Returns:
            List of extraction results in same order as input
        """
        results = []

        # Process in batches to avoid overwhelming the API
        for i in range(0, len(email_list), batch_size):
            batch = email_list[i:i+batch_size]

            # Process batch concurrently
            batch_results = await asyncio.gather(
                *[self.extract_with_cache(email) for email in batch],
                return_exceptions=True
            )

            # Handle exceptions in batch results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    print(f"Error processing email {i+j}: {result}")
                    # Return fallback result for failed emails
                    batch_results[j] = {
                        'student_id': None,
                        'name': None,
                        'assignment_name': None,
                        'is_fallback': True,
                        'confidence': 0.0
                    }

            results.extend(batch_results)
            print(f"Processed batch {i//batch_size + 1}/{(len(email_list) + batch_size - 1)//batch_size}")

        return results

    async def batch_retry_unknown(
        self,
        email_list: List[Dict],
        batch_size: int = 20
    ) -> List[Dict]:
        """
        Retry extraction for emails with Unknown results using batch processing

        Args:
            email_list: List of dicts with keys:
                       - uid, subject, from, attachments, previous_result
            batch_size: Max emails per API call (default: 20)

        Returns:
            List of extraction results in same order as input
        """
        if not email_list:
            return []

        all_results = []

        # Process in batches to avoid overwhelming the API
        for i in range(0, len(email_list), batch_size):
            batch = email_list[i:i+batch_size]

            # Construct batch prompt
            batch_prompt = self._construct_batch_retry_prompt(batch)

            try:
                # Call AI with batch prompt
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": batch_prompt}
                        ],
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    ),
                    timeout=30.0
                )

                # Parse batch response
                batch_results = json.loads(response.choices[0].message.content)

                # Handle both array and single object responses
                if isinstance(batch_results, list):
                    all_results.extend(batch_results)
                else:
                    # Single result returned (shouldn't happen but handle gracefully)
                    all_results.append(batch_results)

            except asyncio.TimeoutError:
                print(f"Batch retry timeout for batch {i//batch_size + 1}")
                # Return None results for this batch
                all_results.extend([
                    {
                        'is_assignment': False,
                        'student_id': None,
                        'name': None,
                        'assignment_name': None,
                        'confidence': 0.0,
                        'reasoning': 'Batch retry timeout'
                    }
                    for _ in batch
                ])

            except Exception as e:
                print(f"Batch retry error for batch {i//batch_size + 1}: {e}")
                # Return None results for this batch
                all_results.extend([
                    {
                        'is_assignment': False,
                        'student_id': None,
                        'name': None,
                        'assignment_name': None,
                        'confidence': 0.0,
                        'reasoning': f'Batch retry error: {str(e)}'
                    }
                    for _ in batch
                ])

        # Normalize results
        for result in all_results:
            if result.get('student_id'):
                result['student_id'] = self._normalize_student_id(result['student_id'])

            if result.get('assignment_name'):
                result['assignment_name'] = self.normalize_assignment_name(
                    result['assignment_name']
                )

        return all_results

    def _construct_batch_retry_prompt(self, email_list: List[Dict]) -> str:
        """
        Construct prompt for batch retry extraction

        Args:
            email_list: List of email dicts with uid, subject, from, attachments

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "The following emails failed initial extraction. Please analyze them together",
            "and extract student information. The context from multiple emails may help",
            "identify patterns.\n\n"
        ]

        for idx, email in enumerate(email_list, 1):
            prompt_parts.append(f"Email {idx}:")
            prompt_parts.append(f"  Subject: {email['subject']}")
            prompt_parts.append(f"  From: {email['from']}")

            attachments = email.get('attachments', [])
            if attachments:
                attachment_names = [att.get('filename', '') for att in attachments]
                prompt_parts.append(f"  Attachments: {', '.join(attachment_names)}")
            else:
                prompt_parts.append("  Attachments: None")

            if email.get('previous_result'):
                prev = email['previous_result']
                prompt_parts.append(f"  Previous failed result: student_id={prev.get('student_id')}, "
                                  f"name={prev.get('name')}, assignment={prev.get('assignment_name')}")

            prompt_parts.append("")

        prompt_parts.append("\nPlease return a JSON array with extraction results for each email in order.")
        prompt_parts.append("Each result should have: is_assignment, student_id, name, assignment_name, confidence, reasoning.")

        return "\n".join(prompt_parts)

    def _normalize_student_id(self, student_id: str) -> str:
        """
        Normalize student ID by extracting numeric part

        Args:
            student_id: Raw student ID string

        Returns:
            Normalized student ID or None
        """
        if not student_id:
            return None

        student_id = str(student_id).strip()

        # Extract continuous numeric parts
        numbers = re.findall(r'\d+', student_id)
        if numbers:
            # Return the longest numeric sequence (usually the student ID)
            return max(numbers, key=len)

        return None

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
