# UI 重构 (PySide6) 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将项目 UI 从 `customtkinter` 迁移至 `PySide6`，实现现代化 SaaS 风格设计。

**架构：** 组件化设计，样式与逻辑分离。使用 QSS 管理深色主题视觉。

**技术栈：** PySide6, QSS, Python.

---

## 待修改/新建文件
- `requirements.txt`: 添加 PySide6 依赖
- `gui/styles/palette.py`: [新建] 颜色常量
- `gui/styles/theme.qss`: [新建] 全局样式表
- `gui/components/common.py`: [新建] 通用原子组件 (Badge, Button)
- `gui/components/sidebar.py`: [新建] 侧边栏组件
- `gui/components/data_table.py`: [新建] 表格组件
- `gui/components/drawer.py`: [新建] 预览抽屉
- `gui/components/batch_popup.py`: [新建] 批量编辑弹窗
- `gui/main_window.py`: [重构] 主窗口逻辑绑定

---

## 任务列表

### 任务 1：环境与样式基础设施
- [x] **步骤 1：更新依赖项**
  修改 `requirements.txt`，添加 `PySide6>=6.0.0`。
- [x] **步骤 2：创建样式常量 `gui/styles/palette.py`**
  定义深色模式下的颜色、字体和边距。
- [x] **步骤 3：编写核心 QSS `gui/styles/theme.qss`**
  实现全局控件的基本样式（窗口背景、卡片样式、圆角）。

### 任务 2：开发原子组件
- [x] **步骤 1：编写 `gui/components/common.py`**
  实现可复用的 `Badge` (用于显示状态) 和现代化的 `PrimaryButton`。
- [x] **步骤 2：编写 `gui/components/sidebar.py`**
  构建侧边栏布局，包括统计卡片区和折叠式过滤器。

### 任务 3：开发核心展示组件
- [x] **步骤 1：编写 `gui/components/data_table.py`**
  基于 `QTableWidget` 或 `QTreeView` 实现现代化表格，支持 Hover 效果和 Badge 渲染。
- [x] **步骤 2：编写 `gui/components/drawer.py`**
  实现从右侧滑出的预览面板，并添加 `QPropertyAnimation` 动画。

### 任务 4：重构主窗口并集成
- [ ] **步骤 1：重构 `gui/main_window.py`**
  将原有 `customtkinter` 逻辑迁移至 PySide6。保留所有数据加载、筛选、批量操作的业务代码，但将其绑定到新组件的信号上。
- [ ] **步骤 2：实现批量编辑弹窗 `gui/components/batch_popup.py`**
  使用 PySide6 重写原有弹出层逻辑。

### 任务 5：验证与打磨
- [ ] **步骤 1：自适应测试**
  验证窗口缩放时布局是否自适应。
- [ ] **步骤 2：视觉修正**
  调整内边距和颜色对比度，确保符合 SaaS 高级感要求。
- [ ] **步骤 3：功能闭环验证**
  确保“拉取邮件 -> 列表展示 -> 双击预览 -> 批量修改 -> 附件下载”全流程畅通。

---
## 自检清单
1. 规格覆盖度：已包含所有 UI 模块和交互动画。
2. 禁止占位符：所有步骤均明确了文件路径和职责。
3. 类型一致性：统一使用 PySide6 命名空间。
