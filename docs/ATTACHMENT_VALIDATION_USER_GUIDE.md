# 附件验证系统用户指南

## 概述

附件验证系统用于限制学生提交作业时可接受的文件类型和大小，提高系统安全性和可管理性。

## 默认规则

- **允许的文件类型**: 文档（.pdf, .doc, .docx等）、图片（.png, .jpg等）、压缩文件（.zip, .rar等）
- **单文件大小限制**: 25 MB
- **总大小限制**: 100 MB

## 配置方式

### 方式1: 通过GUI配置

1. 打开应用程序
2. 点击菜单 "设置" → "附件验证规则"
3. 勾选/取消勾选预设文件类型
4. 可选：添加自定义扩展名（每行一个）
5. 调整大小限制
6. 点击 "保存并应用"

### 方式2: 编辑配置文件

配置文件位置: `config/attachment_presets.yaml`

编辑后重启应用即可生效。

### 方式3: 使用CLI工具

```bash
# 查看当前配置
python scripts/manage_attachment_presets.py show

# 验证配置文件
python scripts/manage_attachment_presets.py validate

# 打开编辑器编辑
python scripts/manage_attachment_presets.py edit

# 恢复默认配置
python scripts/manage_attachment_presets.py restore
```

## 拒绝策略

当邮件附件不符合规则时：
- 邮件保持未读状态
- 不保存附件
- 不移动邮件到目标文件夹
- 不发送确认邮件
- 记录拒绝日志到数据库

## 故障排除

### 问题: 配置修改后不生效

解决: 
- GUI配置: 点击"保存并应用"后立即生效
- 文件配置: 需要重启应用

### 问题: 所有邮件都被拒绝

解决:
- 检查配置文件格式是否正确
- 运行 `python scripts/manage_attachment_presets.py validate`
- 恢复默认配置 `python scripts/manage_attachment_presets.py restore`
```