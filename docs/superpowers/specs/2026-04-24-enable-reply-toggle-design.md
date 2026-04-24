# 设计文档：可配置的邮件回复功能开关

## 1. 背景
用户希望在 `.env` 配置文件中添加一个开关字段，用于决定是否启用向学生发送确认回复邮件的功能。默认情况下，该功能应处于启用状态。

## 2. 目标
- 在 `.env` 中支持 `ENABLE_REPLY` 字段。
- 当功能禁用时，UI 中的“批量回复”按钮应变为灰色不可点击状态。
- 在自动化工作流和手动触发逻辑中，如果功能禁用，应跳过发送步骤并记录日志。

## 3. 详细方案

### 3.1 配置层 (`config/settings.py`)
- 在 `Settings` 类中添加 `ENABLE_REPLY` 属性。
- 从环境变量读取 `ENABLE_REPLY`，默认为 `"true"`。
- 将字符串转换为布尔值处理。

### 3.2 UI 层 (`gui/components/sidebar.py`)
- 在 `Sidebar` 组件初始化时，根据 `settings.ENABLE_REPLY` 的布尔值设置 `self.btn_reply.setEnabled()`。
- 如果禁用，按钮将显示为灰色且无法点击。

### 3.3 业务逻辑层 (`core/workflow.py`)
- 在 `Workflow.process_submission`（或处理回复的相应步骤）中增加判断：
  ```python
  if settings.ENABLE_REPLY:
      # 执行回复逻辑
  else:
      logger.info("邮件回复功能已禁用，跳过发送步骤。")
  ```

### 3.4 保护层 (`mail/smtp_client.py`)
- 在 `SMTPClient.send_reply` 方法的最开始处添加防御性检查：
  ```python
  if not settings.ENABLE_REPLY:
      return False
  ```

## 4. 权衡分析
- **优点**：提供明确的视觉反馈（按钮禁用），同时在逻辑层确保安全（跳过发送并记录日志）。
- **缺点**：如果用户在应用运行时修改了 `.env`，由于配置通常在启动时加载，可能需要重启应用才能生效。

## 5. 测试计划
- **测试用例 1**：在 `.env` 中设置 `ENABLE_REPLY=false`，启动应用，确认侧边栏“批量回复”按钮为灰色不可用。
- **测试用例 2**：在 `.env` 中设置 `ENABLE_REPLY=false`，运行自动化流程，确认日志中出现“邮件回复功能已禁用”的提示，且未发送邮件。
- **测试用例 3**：不设置或设置 `ENABLE_REPLY=true`，确认一切功能恢复正常。
