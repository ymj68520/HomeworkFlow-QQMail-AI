# 可配置的邮件回复功能开关实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 `.env` 中通过 `ENABLE_REPLY` 字段控制邮件确认回复功能。禁用时，UI 按钮变灰，自动化流程跳过发送步骤并记录日志。

**架构：**
- **配置层**：`config/settings.py` 负责读取环境变量并解析为布尔值。
- **UI 层**：`gui/components/sidebar.py` 在初始化时设置按钮的 `Enabled` 状态。
- **业务层**：`core/workflow.py` 在处理流程中增加条件判断。
- **防御层**：`mail/smtp_client.py` 在方法入口处拦截。

**技术栈：** Python, PySide6, python-dotenv

---

### 任务 1：扩展配置类

**文件：**
- 修改：`config/settings.py`
- 修改：`.env` (添加默认配置示例)

- [ ] **步骤 1：修改 `config/settings.py` 添加 `ENABLE_REPLY` 逻辑**

```python
# 在 Settings.__init__ 中添加
self.ENABLE_REPLY = os.getenv('ENABLE_REPLY', 'true').lower() == 'true'
```

- [ ] **步骤 2：更新 `validate` 方法（可选，非强制项，但建议添加默认处理）**

- [ ] **步骤 3：在 `.env` 中添加示例字段**
```text
ENABLE_REPLY=true
```

- [ ] **步骤 4：Commit**
```bash
git add config/settings.py .env
git commit -m "feat(config): add ENABLE_REPLY setting"
```

---

### 任务 2：UI 侧边栏适配

**文件：**
- 修改：`gui/components/sidebar.py`

- [ ] **步骤 1：在 `Sidebar` 初始化中应用配置**
在 `setup_ui` 方法中，找到 `self.btn_reply` 的创建位置后添加：
```python
self.btn_reply.setEnabled(settings.ENABLE_REPLY)
if not settings.ENABLE_REPLY:
    self.btn_reply.setToolTip("邮件回复功能已在配置中禁用")
```

- [ ] **步骤 2：Commit**
```bash
git add gui/components/sidebar.py
git commit -m "feat(ui): disable reply button based on config"
```

---

### 任务 3：业务逻辑与日志记录

**文件：**
- 修改：`core/workflow.py`

- [ ] **步骤 1：定位回复逻辑并添加判断**
在 `process_submission`（或类似的处理步骤）中寻找调用 `smtp_client.send_reply` 的位置。
```python
if settings.ENABLE_REPLY:
    reply_sent = self.smtp.send_reply(...)
    # ... 原有逻辑
else:
    print("DEBUG: 邮件回复功能已禁用，跳过发送步骤。")
    # 如果有 logger，优先使用 logger.info
```

- [ ] **步骤 2：Commit**
```bash
git add core/workflow.py
git commit -m "feat(core): skip reply logic if disabled"
```

---

### 任务 4：后端保护与最终校验

**文件：**
- 修改：`mail/smtp_client.py`

- [ ] **步骤 1：修改 `send_reply` 方法**
```python
def send_reply(self, ...):
    if not settings.ENABLE_REPLY:
        print("DEBUG: SMTPClient.send_reply called but feature is disabled.")
        return False
    # ... 原有逻辑
```

- [ ] **步骤 2：Commit**
```bash
git add mail/smtp_client.py
git commit -m "feat(mail): add defensive check in send_reply"
```

---

### 任务 5：验证

- [ ] **步骤 1：验证禁用状态**
1. 修改 `.env` 为 `ENABLE_REPLY=false`。
2. 启动 `python main.py`。
3. 检查“批量回复邮件”按钮是否为灰色（不可点）。

- [ ] **步骤 2：验证启用状态**
1. 修改 `.env` 为 `ENABLE_REPLY=true`。
2. 重启应用。
3. 检查按钮是否恢复正常。

- [ ] **步骤 3：验证自动化流程日志**
1. 保持禁用状态。
2. 触发一次作业处理。
3. 检查控制台输出是否包含“邮件回复功能已禁用”。
