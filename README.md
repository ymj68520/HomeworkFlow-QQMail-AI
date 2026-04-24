# QQ邮箱作业收发AI系统

自动化处理学生作业邮件提交的智能系统，使用AI提取学生信息并自动组织存储。

## 功能特性

- 自动监听QQ邮箱收件箱
- AI智能提取学号、姓名、作业名
- 批量重试机制提升提取准确率
- 自动规范化作业名称（作业1/2/3/4）
- 重复提交自动保留最新版本
- 本地文件按作业/学生组织存储
- 自动回复确认邮件（署名"助教"）
- 现代化GUI界面支持批量操作
- 作业截止时间管理和逾期标记
- 导出Excel提交情况表

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置`.env`文件：
```
QQ_EMAIL=你的QQ邮箱
QQ_PASSWORD=QQ邮箱授权码
TARGET_FOLDER=目标文件夹名
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
API_KEY=你的API密钥
LLM_MODEL=Qwen3.6-Plus
```

## 使用

启动应用：
```bash
python main.py
```

系统将自动：
1. 连接QQ邮箱并监听新邮件
2. 使用AI提取学生信息
3. 移动作业邮件到目标文件夹
4. 发送确认邮件给学生
5. 在本地存储作业附件

## 目录结构

```
submissions/
├── 作业1/
│   ├── 2021001张三/
│   │   ├── 实验报告.pdf
│   │   └── 代码.zip
│   └── 2021002李四/
│       └── 报告.docx
├── 作业2/
└── ...
```

## AI Extraction Architecture

The system uses AI for extracting student information from emails:

- **Primary Method:** AI extraction via OpenAI-compatible API
- **Caching:** Results cached in database for performance
- **Fallback:** Regex validation only (no direct regex extraction)
- **Batch Processing:** Concurrent processing for bulk operations
- **Batch Retry:** Two-phase extraction for improved accuracy

### Extraction Flow

#### Phase 1: Individual Processing
1. Check cache for existing result
2. If cache miss, call AI extractor
3. Validate and sanitize AI output with regex
4. Save result to cache
5. Return extracted information

#### Phase 2: Batch Retry (New)
After all individual processing completes, emails with Unknown (null/None) fields are retried together in a single batch AI call. This provides more context to the AI and improves extraction success rates.

**Configuration:**
- Batch size: Maximum 20 emails per API call
- Timeout: 30 seconds per batch
- Fallback: Failed batches don't block the workflow

**Performance Metrics:**
- Number of emails in batch
- Processing duration
- Improvement rate (success / total)
- Per-email average time

**Example Output:**
```
Batch Retry Phase: 3 emails
Calling batch AI extraction...
Batch retry performance:
  Emails processed: 3
  Duration: 4.52 seconds
  Average time per email: 1.51 seconds

✓ Batch retry succeeded for 1002
  student_id=2021001
  name=学生1
  assignment=作业1
  confidence=0.90

Batch retry metrics:
  Improvement rate: 66.7%
  Total processed: 3
  Successfully fixed: 2
  Still failed: 1
```

### Quality Tracking

- `is_fallback` flag tracks regex fallback usage
- Target: <5% fallback rate in production
- Confidence scores stored for analysis
- Batch retry improvement rate tracked for optimization

## GUI功能

- 作业列表展示和筛选
- 批量下载、回复、删除
- 设置作业截止时间
- 导出Excel表格
- 预览确认邮件

## 邮件预览功能

系统支持邮件预览侧边栏，双击表格中任何邮件条目即可查看详细信息，包括：
- 学生信息和提交状态
- 邮件完整信息
- 邮件正文内容（支持HTML转Markdown、图片移除、中文显示）
- 附件列表和文件操作
- 支持智能切换和固定模式

详细使用说明请参考：
- [邮件预览使用指南](docs/EMAIL_PREVIEW_USER_GUIDE.md)
- [邮件正文功能文档](docs/email_body_feature.md)
