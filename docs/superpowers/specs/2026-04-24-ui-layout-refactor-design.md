# UI 布局重构设计规格书 - 可折叠滚动侧边栏

## 1. 目标
解决当前 UI 在低分辨率或非全屏状态下，左侧面板底部按钮（特别是批量操作按钮）被遮挡的问题。通过引入可滚动的容器和可折叠的区块，提高界面的适应性和操作效率。

## 2. 方案概述
将原有的固定高度 `left_panel` 重构为 `CTkScrollableFrame`，并将其中的内容划分为三个独立的、可折叠的区块（Sections）。

### 2.1 结构设计
- **父级容器：** 使用 `customtkinter.CTkScrollableFrame` 替代 `CTkFrame`。
- **折叠区块 (CollapsibleSection)：**
    - **Header:** 一个可点击的按钮或标签，用于切换展开/收起状态。
    - **Content Frame:** 存放具体的业务控件，切换状态时通过 `pack`/`pack_forget` 或动态调整高度来控制显示。
- **区块划分：**
    1. **筛选条件 (Filters):** 默认展开。
    2. **统计信息 (Statistics):** 默认折叠。
    3. **批量操作 (Batch Operations):** 默认展开。

### 2.2 视觉优化
- **指示图标：** 在 Header 处显示 `▼` (展开) 或 `▶` (折叠) 图标。
- **按钮紧凑布局：** 批量操作区块内的按钮将采用两列并排布局，以进一步节省垂直空间。

## 3. 技术实现细节

### 3.1 核心类/组件
- **`CollapsibleFrame(ctk.CTkFrame)`:**
    - 属性：`is_expanded` (bool), `title` (str), `header_btn`, `content_frame`。
    - 方法：`toggle()`。

### 3.2 界面调整 (MainWindow 类)
- 修改 `setup_ui` 方法，初始化 `left_panel` 为 `CTkScrollableFrame`。
- 重构 `create_left_panel` 方法，将控件分发到对应的 `CollapsibleFrame` 中。
- 修改 `batch_frame` 内的按钮布局，使用 `grid(row=x, column=y)` 实现并排。

## 4. 逻辑与交互
- **自动滚动：** 当区块展开导致高度超过窗口时，`CTkScrollableFrame` 的滚动条应自动生效。
- **状态持久化：** （可选）记录用户上次的展开/折叠状态，暂定不实现以保持简单。

## 5. 验收标准
1. 在 1400x900 分辨率下，所有按钮可见。
2. 窗口高度缩小到 600px 时，左侧出现滚动条。
3. 点击各区块标题可以正常展开和折叠。
4. 批量操作按钮在侧边栏底部，即使在小窗口下也可通过滚动触达。
