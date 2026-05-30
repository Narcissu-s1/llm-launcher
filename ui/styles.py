"""
中央样式常量模块 - LLM Launcher UI 优化
所有 QSS 定义集中于此，便于统一管理和维护
"""

# ============================================================================
# 配色方案
# ============================================================================
COLORS = {
    # 主色系
    "primary": "#3182ce",
    "primary_hover": "#2c5282",
    "primary_light": "#63b3ed",
    "primary_bg": "#ebf8ff",

    # 背景
    "bg_main": "#f0f4f8",
    "bg_card": "#ffffff",
    "bg_hover": "#edf2f7",

    # 边框
    "border": "#e2e8f0",
    "border_hover": "#90cdf4",

    # 文字
    "text_primary": "#2d3748",
    "text_secondary": "#718096",
    "text_muted": "#a0aec0",

    # 状态色
    "status_running": "#38a169",
    "status_starting": "#d69e2e",
    "status_stopped": "#718096",
    "status_error": "#e53e3e",
}

# ============================================================================
# QSS 样式字符串
# ============================================================================
LIGHT_THEME = f"""
/* === 全局基础 === */
QWidget {{
    font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
    font-size: 13px;
    color: {COLORS["text_primary"]};
}}

/* === 主窗口背景 === */
QMainWindow {{
    background: {COLORS["bg_main"]};
}}

/* === 按钮层级 === */
/* Primary: 启动/确认等主要操作 */
QPushButton#btnPrimary {{
    background: {COLORS["primary"]};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 14px;
}}
QPushButton#btnPrimary:hover {{
    background: {COLORS["primary_hover"]};
}}
QPushButton#btnPrimary:pressed {{
    background: {COLORS["primary_hover"]};
    border-radius: 6px;
}}
QPushButton#btnPrimary:disabled {{
    background: {COLORS["text_muted"]};
}}

/* Stop: 停止操作 */
QPushButton#btnStop {{
    background: {COLORS["status_error"]};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 14px;
}}
QPushButton#btnStop:hover {{
    background: #c53030;
}}
QPushButton#btnStop:pressed {{
    background: #c53030;
}}

/* Default: 一般按钮 */
QPushButton {{
    background: {COLORS["bg_card"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    background: {COLORS["primary_bg"]};
    border-color: {COLORS["border_hover"]};
}}
QPushButton:pressed {{
    background: {COLORS["bg_hover"]};
}}

/* === GroupBox === */
QGroupBox {{
    font-size: 12px;
    font-weight: 600;
    color: {COLORS["text_secondary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 10px 12px 8px;
    margin-top: 8px;
    background: {COLORS["bg_card"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}

/* === 可折叠组 === */
_CollapsibleGroup {{
    background: {COLORS["bg_card"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 8px;
}}

/* === 输入控件 === */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {COLORS["bg_card"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS["text_primary"]};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {COLORS["primary"]};
    background: {COLORS["bg_main"]};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: {COLORS["bg_main"]};
    border-color: {COLORS["border"]};
    color: {COLORS["text_muted"]};
}}

/* === 复选框禁用状态 === */
QCheckBox:disabled {{
    color: {COLORS["text_muted"]};
}}

/* === TabWidget === */
QTabWidget::pane {{
    border: 1px solid {COLORS["border"]};
    border-radius: 0 0 8px 8px;
    background: {COLORS["bg_card"]};
    top: -1px;
}}
QTabBar::tab {{
    background: {COLORS["bg_main"]};
    color: {COLORS["text_secondary"]};
    padding: 8px 18px;
    border: 1px solid {COLORS["border"]};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {COLORS["bg_card"]};
    color: {COLORS["primary"]};
    font-weight: 600;
    border-color: {COLORS["border"]};
    border-bottom-color: {COLORS["bg_card"]};
}}
QTabBar::tab:hover:!selected {{
    background: {COLORS["primary_bg"]};
}}

/* === 滚动条 === */
QScrollBar:vertical {{
    background: {COLORS["bg_main"]};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS["text_muted"]};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:hover {{
    background: {COLORS["text_secondary"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* === 状态卡片 === */
QFrame#statusLine {{
    background: {COLORS["text_muted"]};
}}

/* === 分隔线 === */
QFrame[frameShape="4"] {{
    color: {COLORS["border"]};
}}

/* === 面板间距 === */
QWidget#leftPanel {{
    background: {COLORS["bg_main"]};
}}

/* === TextEdit / LogPanel === */
QTextEdit {{
    background: {COLORS["bg_card"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 8px;
    font-family: "DM Mono", "Consolas", monospace;
    font-size: 12px;
}}

/* === 进度条 === */
QProgressBar {{
    background: {COLORS["bg_main"]};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {COLORS["primary"]};
    border-radius: 4px;
}}
"""

# ============================================================================
# 监控卡片样式（单独提取，用于动态应用）
# ============================================================================
STAT_CARD_QSS = f"""
QFrame#statCard {{
    background: {COLORS["bg_card"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    padding: 10px 8px 10px 8px;
}}
"""

# ============================================================================
# 状态线样式模板
# ============================================================================
def get_status_line_qss(color: str) -> str:
    """生成状态线颜色样式"""
    return f"""
    QFrame#statusLine {{
        background: {color};
    }}
    """


# ============================================================================
# 按钮样式ID
# ============================================================================
BTN_PRIMARY_ID = "btnPrimary"
BTN_STOP_ID = "btnStop"