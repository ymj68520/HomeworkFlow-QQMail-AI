# EmailPreviewDrawer 手动编辑功能重构计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 重构 `EmailPreviewDrawer` 类，增加编辑模式，允许用户手动修改学号、姓名、邮箱、状态和所属作业。

**架构：**
1. **状态控制**：引入 `is_edit_mode` 标识。
2. **UI 动态渲染**：根据模式切换卡片中的 Label 和 Entry/OptionMenu。
3. **数据同步**：通过 `db.update_submission_full` 保存更改并刷新全局 UI。

**技术栈：** Python, CustomTkinter, SQLAlchemy

---

### 任务 1：初始化状态与控件存储

**文件：**
- 修改：`gui/email_preview_drawer.py`

- [ ] **步骤 1：更新 `__init__`**
添加 `self.is_edit_mode = False` 和 `self.edit_widgets = {}`。

- [ ] **步骤 2：Commit**
```bash
git add gui/email_preview_drawer.py
git commit -m "refactor: init edit mode state in EmailPreviewDrawer"
```

---

### 任务 2：重构顶部控制栏与切换逻辑

**文件：**
- 修改：`gui/email_preview_drawer.py`

- [ ] **步骤 1：更新 `_setup_control_bar`**
在“📌 固定”按钮旁边增加“📝 编辑”按钮。实现动态文本（编辑/保存）和“❌ 取消”按钮的显示/隐藏。

- [ ] **步骤 2：实现 `toggle_edit_mode` 方法**
处理模式切换，并在切换时重新调用 `_load_data` 或相应的卡片更新方法。

- [ ] **步骤 3：实现 `_on_cancel_clicked` 方法**
重置 `is_edit_mode` 为 False 并刷新显示。

- [ ] **步骤 4：Commit**
```bash
git add gui/email_preview_drawer.py
git commit -m "feat: add edit/save/cancel controls to EmailPreviewDrawer"
```

---

### 任务 3：重构卡片更新方法（编辑模式支持）

**文件：**
- 修改：`gui/email_preview_drawer.py`

- [ ] **步骤 1：重构 `_update_student_card`**
支持浏览模式（Label）和编辑模式（Entry/OptionMenu）。状态选项从 `self.master.STATUS_MAP` 获取。

- [ ] **步骤 2：重构 `_update_assignment_card`**
支持浏览模式（Label）和编辑模式（OptionMenu）。作业选项动态从 `db.get_all_assignments()` 获取。

- [ ] **步骤 3：Commit**
```bash
git add gui/email_preview_drawer.py
git commit -m "feat: support edit mode UI for student and assignment cards"
```

---

### 任务 4：实现保存逻辑与 UI 联动

**文件：**
- 修改：`gui/email_preview_drawer.py`

- [ ] **步骤 1：实现 `_on_save_clicked` 方法**
验证输入，调用 `db.update_submission_full`，成功后提示并刷新主界面及自身。

- [ ] **步骤 2：Commit**
```bash
git add gui/email_preview_drawer.py
git commit -m "feat: implement save logic and UI refresh in EmailPreviewDrawer"
```

---

### 任务 5：验证与清理

- [ ] **步骤 1：验证功能**
检查编辑模式下的控件是否正确显示，保存是否生效，主界面是否刷新。

- [ ] **步骤 2：最终 Commit**
```bash
git commit --allow-empty -m "feat: support manual field editing in EmailPreviewDrawer"
```
