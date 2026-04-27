# 状态栏刷新按钮实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在主窗口状态栏最右侧添加刷新按钮，点击后重置所有筛选条件并从数据库重新加载数据

**Architecture:** 在 MainWindow 的 setup_ui() 中创建 QPushButton 并添加到状态栏右侧，使用 addPermanentWidget() 实现永久显示。点击时调用 on_refresh_clicked() 方法重置筛选器并调用现有的 load_data() 方法。

**Tech Stack:** PySide6 (Qt), Python 3.x

---

## 文件结构

**修改文件:**
- `gui/main_window.py` - 添加刷新按钮和相关逻辑

**涉及组件:**
- `MainWindow.setup_ui()` - 创建刷新按钮并添加到状态栏
- `MainWindow.setup_connections()` - 连接按钮点击信号
- `MainWindow.on_refresh_clicked()` - 新方法，处理刷新逻辑

---

### Task 1: 在 setup_ui() 中创建刷新按钮

**Files:**
- Modify: `gui/main_window.py:84-120`

- [ ] **Step 1: 添加刷新按钮创建代码**

在 `setup_ui()` 方法中，状态栏初始化之后（第119行之后），添加刷新按钮：

```python
# 状态栏
self.statusBar().showMessage("准备就绪")

# 刷新按钮
self.refresh_btn = QPushButton("刷新")
self.refresh_btn.setFixedSize(80, 24)
self.refresh_btn.setCursor(Qt.PointingHandCursor)
self.statusBar().addPermanentWidget(self.refresh_btn)
```

- [ ] **Step 2: 保存文件并运行程序验证按钮显示**

运行: `python gui/main_window.py`
预期: 窗口正常启动，状态栏右侧显示"刷新"按钮

- [ ] **Step 3: 提交代码**

```bash
git add gui/main_window.py
git commit -m "feat: add refresh button to status bar"
```

---

### Task 2: 在 setup_connections() 中连接按钮信号

**Files:**
- Modify: `gui/main_window.py:121-161`

- [ ] **Step 1: 添加信号连接**

在 `setup_connections()` 方法中，侧边栏按钮连接部分之后（第156行之后），添加刷新按钮信号连接：

```python
# New feature buttons
self.sidebar.btn_smart_retry.clicked.connect(self.on_smart_retry)
self.sidebar.btn_batch_reanalyze.clicked.connect(self.on_batch_reanalyze)

# 刷新按钮
self.refresh_btn.clicked.connect(self.on_refresh_clicked)
```

- [ ] **Step 2: 保存文件**

- [ ] **Step 3: 提交代码**

```bash
git add gui/main_window.py
git commit -m "feat: connect refresh button signal"
```

---

### Task 3: 实现 on_refresh_clicked() 方法

**Files:**
- Modify: `gui/main_window.py` (在 on_batch_reanalyze 方法之后)

- [ ] **Step 1: 添加 on_refresh_clicked() 方法**

在 `get_selected_submissions()` 方法之前（第983行之前），添加新方法：

```python
def on_refresh_clicked(self):
    """处理刷新按钮点击事件 - 重置筛选条件并重新加载数据"""
    try:
        # 显示加载状态
        self.statusBar().showMessage("正在刷新...")
        QApplication.processEvents()

        # 重置筛选条件到默认值
        self.sidebar.student_filter.blockSignals(True)
        self.sidebar.assignment_filter.blockSignals(True)
        self.sidebar.status_filter.blockSignals(True)

        self.sidebar.student_filter.setCurrentIndex(0)
        self.sidebar.assignment_filter.setCurrentIndex(0)
        self.sidebar.status_filter.setCurrentIndex(0)

        self.sidebar.student_filter.blockSignals(False)
        self.sidebar.assignment_filter.blockSignals(False)
        self.sidebar.status_filter.blockSignals(False)

        # 清空搜索框
        self.sidebar.search_input.blockSignals(True)
        self.sidebar.search_input.clear()
        self.sidebar.search_input.blockSignals(False)

        # 清除缓存并重新加载数据
        hybrid_data_loader.invalidate_cache()
        self.load_data(page=1, force_refresh=True)

        # 显示完成状态
        self.statusBar().showMessage("刷新完成")

    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(self, "错误", f"刷新失败: {str(e)}")
        self.statusBar().showMessage("刷新失败")
```

- [ ] **Step 2: 保存文件**

- [ ] **Step 3: 测试刷新功能**

运行: `python gui/main_window.py`
测试步骤:
1. 选择任意筛选条件（学生、作业、状态）
2. 在搜索框输入关键词
3. 点击刷新按钮
预期: 所有筛选条件重置为"全部"，搜索框清空，数据重新加载

- [ ] **Step 4: 提交代码**

```bash
git add gui/main_window.py
git commit -m "feat: implement refresh button click handler"
```

---

### Task 4: 添加可选的按钮样式

**Files:**
- Modify: `gui/styles/theme.qss`

- [ ] **Step 1: 添加刷新按钮专用样式**

在主题文件末尾添加刷新按钮样式（可选，用于更好的视觉效果）：

```css
/* 刷新按钮样式 */
QPushButton#RefreshButton {
    background-color: #F3F4F6;
    color: #374151;
    border: 1px solid #D1D5DB;
    padding: 4px 12px;
}

QPushButton#RefreshButton:hover {
    background-color: #E5E7EB;
}

QPushButton#RefreshButton:pressed {
    background-color: #D1D5DB;
}
```

- [ ] **Step 2: 为按钮设置对象名称**

修改 `gui/main_window.py` 中刷新按钮的创建代码：

```python
self.refresh_btn = QPushButton("刷新")
self.refresh_btn.setObjectName("RefreshButton")
self.refresh_btn.setFixedSize(80, 24)
self.refresh_btn.setCursor(Qt.PointingHandCursor)
```

- [ ] **Step 3: 保存文件并测试样式**

运行: `python gui/main_window.py`
预期: 刷新按钮有灰色背景，悬停时变深，点击时更深

- [ ] **Step 4: 提交代码**

```bash
git add gui/main_window.py gui/styles/theme.qss
git commit -m "style: add custom style for refresh button"
```

---

### Task 5: 手动测试完整流程

**Files:**
- Test: `gui/main_window.py` (运行测试)

- [ ] **Step 1: 测试基本刷新功能**

1. 启动应用程序
2. 选择一个学生筛选器（非"全部学生"）
3. 点击刷新按钮
预期: 学生筛选器重置为"全部学生"

- [ ] **Step 2: 测试搜索框清空**

1. 在搜索框输入任意文本
2. 点击刷新按钮
预期: 搜索框清空

- [ ] **Step 3: 测试状态筛选重置**

1. 选择任意状态筛选器
2. 点击刷新按钮
预期: 状态筛选器重置为"全部状态"

- [ ] **Step 4: 测试数据重新加载**

1. 观察当前数据
2. 点击刷新按钮
预期: 状态栏显示"正在刷新..."，然后显示数据更新

- [ ] **Step 5: 测试错误处理**

（模拟网络断开或数据库不可用场景）
1. 断开网络连接
2. 点击刷新按钮
预期: 显示错误对话框，状态栏显示"刷新失败"

---

### Task 6: 代码审查和清理

**Files:**
- Review: `gui/main_window.py`

- [ ] **Step 1: 检查代码一致性**

验证以下内容：
- 方法命名遵循项目规范（snake_case）
- 错误处理与其他方法一致
- 注释清晰且必要

- [ ] **Step 2: 检查是否有未使用的导入**

查看 main_window.py 顶部的导入语句，确保所有导入都被使用。

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "chore: final polish for refresh button feature"
```

---

## 自检清单

**Spec 覆盖:**
- ✅ 刷新按钮位置：状态栏右侧 (Task 1)
- ✅ 重置筛选条件 (Task 3)
- ✅ 清空搜索框 (Task 3)
- ✅ 清除缓存 (Task 3)
- ✅ 重新加载数据 (Task 3)
- ✅ 用户反馈 (Task 3)
- ✅ 错误处理 (Task 3)

**占位符扫描:**
- ✅ 无 TBD 或 TODO
- ✅ 所有步骤包含完整代码
- ✅ 无"类似Task N"引用

**类型一致性:**
- ✅ 方法名一致：on_refresh_clicked
- ✅ 组件引用一致：self.sidebar, self.refresh_btn
- ✅ 信号连接方式一致
