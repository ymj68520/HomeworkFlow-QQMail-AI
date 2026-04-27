# 状态栏刷新按钮设计文档

**日期:** 2026-04-27
**作者:** Claude
**状态:** 已批准

---

## 概述

在主窗口状态栏最右侧添加一个刷新按钮，点击后从数据库重新获取数据并刷新UI展示内容，同时重置所有筛选条件和搜索状态。

---

## 功能需求

### 核心功能

1. **刷新按钮位置**: 状态栏最右侧，使用 `addPermanentWidget()` 实现永久显示
2. **刷新行为**:
   - 重置所有筛选条件（学生、作业、状态）
   - 清空搜索框
   - 清除数据缓存
   - 从数据库重新加载数据（force_refresh=True）
   - 回到第一页
3. **用户反馈**: 刷新过程中显示"正在刷新..."，完成后显示"刷新完成"

---

## 组件设计

### UI 组件

**刷新按钮 (QPushButton)**

属性:
- 文本: "刷新"
- 尺寸: 80x24 像素
- 光标: 指向手势 (PointingHandCursor)
- 样式类: 无特殊类名，使用默认 QPushButton 样式

**布局方式**

```python
refresh_btn = QPushButton("刷新")
refresh_btn.setFixedSize(80, 24)
refresh_btn.setCursor(Qt.PointingHandCursor)
self.statusBar().addPermanentWidget(refresh_btn)
```

---

## 实现细节

### 方法: `on_refresh_clicked()`

```python
def on_refresh_clicked(self):
    """处理刷新按钮点击事件"""
    try:
        # 显示加载状态
        self.statusBar().showMessage("正在刷新...")
        QApplication.processEvents()

        # 重置筛选条件
        self.sidebar.student_filter.setCurrentIndex(0)
        self.sidebar.assignment_filter.setCurrentIndex(0)
        self.sidebar.status_filter.setCurrentIndex(0)

        # 清空搜索框
        self.sidebar.search_input.clear()

        # 清除缓存
        hybrid_data_loader.invalidate_cache()

        # 重新加载数据
        self.load_data(page=1, force_refresh=True)

        # 显示完成状态
        self.statusBar().showMessage("刷新完成")
    except Exception as e:
        QMessageBox.critical(self, "错误", f"刷新失败: {str(e)}")
        self.statusBar().showMessage("刷新失败")
```

### 信号连接

在 `setup_connections()` 方法中添加:

```python
self.refresh_btn.clicked.connect(self.on_refresh_clicked)
```

---

## 样式处理

刷新按钮使用现有主题样式系统的默认 QPushButton 样式，无需额外定义。

当前主题中 QPushButton 默认样式:
```css
QPushButton {
    border-radius: 6px;
    font-weight: 500;
}
```

如需自定义，可添加 `#RefreshButton` 样式类并在 theme.qss 中定义。

---

## 错误处理

1. **数据库连接失败**: 显示错误对话框，状态栏显示"刷新失败"
2. **网络异常**: 捕获异常并显示用户友好的错误信息
3. **缓存清除失败**: 不影响刷新流程继续执行

---

## 测试要点

1. 点击刷新按钮后，所有筛选条件应重置为"全部"
2. 搜索框应被清空
3. 数据应从数据库重新加载
4. 应回到第一页
5. 状态栏应显示正确的状态信息
6. 刷新失败时应显示错误提示

---

## 后续扩展

1. 可考虑添加刷新动画图标
2. 可支持键盘快捷键 (F5 或 Ctrl+R)
3. 可添加自动刷新间隔设置
