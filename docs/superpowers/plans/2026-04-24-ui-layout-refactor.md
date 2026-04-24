# UI 布局重构实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 重构主窗口左侧面板，引入可折叠的滚动区域，解决按钮在低分辨率下被遮挡的问题。

**架构：**
1. 在 `gui/main_window.py` 中引入 `CollapsibleFrame` 组件。
2. 将 `MainWindow.left_panel` 更改为 `CTkScrollableFrame`。
3. 将筛选、统计和批量操作包装进 `CollapsibleFrame`。

**技术栈：** Python, CustomTkinter

---

### 文件结构
- `gui/main_window.py`: 修改 UI 布局逻辑，增加 `CollapsibleFrame` 类。

---

### 任务 1：实现 CollapsibleFrame 组件

**文件：**
- 修改：`gui/main_window.py`

- [ ] **步骤 1：在 `MainWindow` 类之前定义 `CollapsibleFrame` 类**

```python
class CollapsibleFrame(ctk.CTkFrame):
    """可折叠的框架组件"""
    def __init__(self, master, title, is_expanded=True, **kwargs):
        super().__init__(master, **kwargs)
        
        self.is_expanded = is_expanded
        self.title = title
        
        # 标题栏按钮
        self.header_btn = ctk.CTkButton(
            self, 
            text=f"{'▼' if self.is_expanded else '▶'} {self.title}",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray70", "gray30"),
            anchor="w",
            font=("Arial", 14, "bold"),
            command=self.toggle
        )
        self.header_btn.pack(fill="x", padx=2, pady=2)
        
        # 内容区域
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        if self.is_expanded:
            self.content_frame.pack(fill="x", padx=5, pady=5)

    def toggle(self):
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.is_expanded = False
            self.header_btn.configure(text=f"▶ {self.title}")
        else:
            self.content_frame.pack(fill="x", padx=5, pady=5)
            self.is_expanded = True
            self.header_btn.configure(text=f"▼ {self.title}")
```

- [ ] **步骤 2：Commit**

```bash
git add gui/main_window.py
git commit -m "feat(gui): add CollapsibleFrame component"
```

---

### 任务 2：重构左侧面板容器

**文件：**
- 修改：`gui/main_window.py`

- [ ] **步骤 1：修改 `setup_ui` 方法，将 `left_panel` 更改为 `CTkScrollableFrame`**

```python
# 找到这一行：
# left_panel = ctk.CTkFrame(main_container, width=300)
# 修改为：
left_panel = ctk.CTkScrollableFrame(main_container, width=300, label_text="")
```

- [ ] **步骤 2：在 `create_left_panel` 中使用 `CollapsibleFrame` 包装内容**

需要重写 `create_left_panel` 的逻辑，将原有控件放入三个 section 中。

```python
    def create_left_panel(self, parent):
        """创建左侧筛选面板（重构为可折叠滚动模式）"""
        
        # 1. 筛选条件区块
        self.filter_section = CollapsibleFrame(parent, title="筛选条件", is_expanded=True)
        self.filter_section.pack(fill="x", padx=5, pady=5)
        self._setup_filter_content(self.filter_section.content_frame)

        # 2. 统计信息区块
        self.stats_section = CollapsibleFrame(parent, title="统计信息", is_expanded=False)
        self.stats_section.pack(fill="x", padx=5, pady=5)
        self._setup_stats_content(self.stats_section.content_frame)

        # 3. 批量操作区块
        self.batch_section = CollapsibleFrame(parent, title="批量操作", is_expanded=True)
        self.batch_section.pack(fill="x", padx=5, pady=5)
        self._setup_batch_content(self.batch_section.content_frame)

        # 状态栏保持在底部
        self.status_label = ctk.CTkLabel(
            self,  # 移出滚动区域，改绑到 self
            text="状态: 就绪",
            anchor="w"
        )
        self.status_label.pack(side="bottom", fill="x", padx=10, pady=10)
```

- [ ] **步骤 3：Commit**

```bash
git add gui/main_window.py
git commit -m "refactor(gui): use scrollable and collapsible sections for left panel"
```

---

### 任务 3：拆分内容填充逻辑并优化按钮布局

**文件：**
- 修改：`gui/main_window.py`

- [ ] **步骤 1：实现 `_setup_filter_content`** (将原有搜索、下拉框逻辑移入)

- [ ] **步骤 2：实现 `_setup_stats_content`** (将原有统计标签逻辑移入)

- [ ] **步骤 3：实现 `_setup_batch_content` 并优化按钮为并排布局**

```python
    def _setup_batch_content(self, parent):
        self.selected_label = ctk.CTkLabel(parent, text="已选择: 0 项")
        self.selected_label.pack(pady=5)

        btns_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btns_frame.pack(fill="x")

        # 第一行并排
        ctk.CTkButton(btns_frame, text="批量下载", command=self.on_batch_download, width=130).grid(row=0, column=0, padx=2, pady=2)
        ctk.CTkButton(btns_frame, text="批量回复", command=self.on_batch_reply, width=130).grid(row=0, column=1, padx=2, pady=2)
        
        # 第二行并排
        ctk.CTkButton(btns_frame, text="批量删除", command=self.on_batch_delete, width=130).grid(row=1, column=0, padx=2, pady=2)
        ctk.CTkButton(btns_frame, text="导出Excel", command=self.on_export_excel, width=130).grid(row=1, column=1, padx=2, pady=2)
```

- [ ] **步骤 4：Commit**

```bash
git add gui/main_window.py
git commit -m "feat(gui): optimize batch operation button layout"
```

---

### 任务 4：验证与调整

- [ ] **步骤 1：运行程序检查布局**
- [ ] **步骤 2：测试展开/折叠功能**
- [ ] **步骤 3：测试滚动功能（通过缩小窗口高度）**
