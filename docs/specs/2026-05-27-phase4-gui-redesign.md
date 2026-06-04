# 第四阶段设计文档：正式 GUI 重构

**日期**：2026-05-27  
**框架**：PySide6  
**策略**：全量重写 UI 层，core/ 零改动

---

## 1. 架构

### 目录结构

```
ui/
  app.py                    # QMainWindow，组装布局，替换 LlamaLauncherApp
  control_panel.py          # 左侧控制面板 QWidget
  log_panel.py              # 右侧日志面板 QWidget
  confirm_dialog.py         # QDialog 二次确认
  widgets/
    param_groups.py         # 参数分组（QGroupBox + QFormLayout）
    monitor_panel.py        # 运行时监控
    model_library_panel.py  # 模型库
    download_panel.py       # 远程下载
    chat_panel.py           # API 测试聊天
    tray_icon.py            # 新增：系统托盘
```

### 层间通信

- `core/` 层零改动，EventBus 保持不变
- 后台线程（下载、监控、日志）通过 `QThread` + Qt 信号槽与 UI 通信，替换 Textual 的 `call_from_thread`
- 每个后台任务封装为 `QThread` 子类，通过 `pyqtSignal` / `Signal` 发射结果

### 布局

左右分栏，比例 2:3：
- 左：`QTabWidget`（控制面板 / 模型库 / 下载 / 聊天）
- 右：上下分栏，日志占 70%，监控占 30%（`QSplitter` 垂直分割，固定比例）
- 顶部：状态栏（服务状态 + 端口 + 运行时长）

---

## 2. 系统集成

### 托盘（`widgets/tray_icon.py`）

- `QSystemTrayIcon` + `QMenu`
- 右键菜单：显示窗口 / 启动服务 / 停止服务 / 退出
- 图标颜色反映服务状态：绿（运行中）/ 灰（已停止）/ 红（错误）
- 订阅 `EVENT_STATUS_CHANGED` 更新图标
- 关闭窗口 → 最小化到托盘；托盘"退出" → 真正退出

### 开机自启

- 写入注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- 用标准库 `winreg` 实现，无第三方依赖
- UI 提供 `QCheckBox`，状态持久化到 `config.yaml`（`app.autostart`）

### 打包（PyInstaller `--onedir`）

- 提供 `build.bat`，输出 `dist/llm-launcher/`
- 包含：PySide6 插件、`config.yaml`、图标资源
- 用户分发时压缩整个目录

---

## 3. UI 体验

### 原生文件对话框

替换现有 TUI 自制的 `FileBrowser` / `DirPicker`：

| 原 TUI 组件 | 替换为 |
|---|---|
| `FileBrowser` | `QFileDialog.getOpenFileName` |
| `DirPicker` | `QFileDialog.getExistingDirectory` |
| `JsonFileBrowser` | `QFileDialog.getOpenFileName`（filter: `*.json`）|

### 主题跟随系统

- `QApplication.styleHints().colorScheme()` 检测（Qt 6.5+）
- 两套 QSS 样式表（`assets/theme_light.qss` / `assets/theme_dark.qss`）
- 监听 `colorSchemeChanged` 信号，运行时动态切换

### 窗口大小记忆

- 关闭时 `geometry()` 序列化到 `config.yaml`（`app.window_geometry`，base64）
- 启动时 `restoreGeometry()` 恢复；首次启动默认 1200×800

---

## 4. 视觉设计

**风格**：极简主义 · 冷白实验室（Minimal Lab）

### 色彩系统

```
背景        #f8fafb
内容区      #ffffff
分割线      #e8eef2
面板底色    淡蓝 #e8f4fd / 淡绿 #e8f8f2
强调蓝      #2d7dd2
强调绿      #1a9e6e
警告红      #e53e3e
文字主色    #1a202c
文字次色    #718096
```

### 字体

- UI 文字：DM Sans（Google Fonts，随应用打包）
- 数值 / 日志：DM Mono

### 控件规范

- 圆角：`4px`（统一）
- 按钮：outline 风格，激活态填充强调色
- 无多余阴影，无渐变背景
- 输入框：`1px` 边框，focus 时边框变强调蓝

### 状态指示

窗口左侧边栏 `3px` 竖线：
- 运行中 → `#1a9e6e`（绿）
- 已停止 → `#cbd5e0`（灰）
- 错误 → `#e53e3e`（红）

---

## 5. 验收标准

- 所有第一至三阶段功能在 PySide6 GUI 下正常运行
- 托盘模式可用（最小化到托盘、状态图标更新）
- 开机自启开关有效
- 可用 PyInstaller 打包为 `dist/llm-launcher/` 目录并在无 Python 环境的机器运行
- 主题跟随系统自动切换
- 窗口尺寸关闭后恢复

---

## 6. 不在范围内

- 第五阶段功能（首次引导、错误诊断、国际化）
- Linux / macOS 适配
- 自动更新机制
