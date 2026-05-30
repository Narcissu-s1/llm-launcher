"""使用指南面板：精简的操作步骤指引，嵌入软件右侧 Tab 页"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt

_STEPS = [
    ("1  选择模型", [
        ("在左侧「模型文件」栏点击「浏览」", "选择本地 .gguf 格式的模型文件"),
        ("（可选）mmproj 文件", "视觉模型需要，留空会自动检测同目录下的 mmproj"),
        ("（可选）llama.cpp 目录", "留空则自动搜索 PATH；首次使用需指定 llama-server.exe 所在目录"),
    ]),
    ("2  调整参数", [
        ("上下文长度", "默认 32768，显存不足时可降低"),
        ("GPU 层数", "默认 -1（全部卸载到 GPU），显存不够可设小值或 0（纯 CPU）"),
        ("并发数", "单用户设 1 即可，多人共用可设 2/4/8"),
        ("端口 / 监听地址", "默认 8080 + 仅本机，局域网共享改为 0.0.0.0"),
        ("高级参数（可选）", "折叠面板中的 KV Cache、采样、推理等参数通常无需修改"),
    ]),
    ("3  启动服务", [
        ("点击「启动」按钮", "日志面板会实时显示 llama-server 输出"),
        ("等待状态变绿", "左侧状态线变绿 = 服务就绪，浏览器会自动打开 Web UI"),
        ("如需停止", "点击「停止」按钮，进程会优雅终止（3 秒后强杀）"),
    ]),
    ("4  使用模型", [
        ("Web UI 聊天", "浏览器自动打开的页面可直接对话"),
        ("内置聊天面板", "软件右侧「聊天」Tab 可直接测试，无需浏览器"),
        ("API 调用", "兼容 OpenAI API 格式：http://127.0.0.1:8080/v1/chat/completions"),
    ]),
    ("5  路由模式（多模型）", [
        ("启用路由模式", "勾选左侧面板「路由模式」→ 选择模型文件所在的上一级目录"),
        ("启动与使用", "服务器自动扫描目录中的 GGUF 模型，通过 /v1/models 列出，请求中指定 model 字段路由"),
        ("上下文扩展", "路由模式下上下文长度选项自动扩展至 64K / 128K / 256K"),
    ]),
    ("6  搜索与下载", [
        ("搜索模型", "「下载」Tab 输入关键词 → 选择数据源 → 点击「搜索」，返回下载量前 50 的仓库"),
        ("选择仓库", "双击搜索结果自动填入仓库 ID → 点击「扫描」获取文件列表 → 勾选文件下载"),
        ("支持的数据源", "HuggingFace / HF 镜像 / ModelScope，搜索由数据源下拉框切换"),
    ]),
    ("7  进阶功能", [
        ("模型库", "「模型库」Tab 可扫描指定目录，一键切换模型"),
        ("预设管理", "左侧面板底部可保存/载入/导出参数预设"),
        ("WUI 工具", "勾选「启动WUI工具」启用 llama-server 内置 Web 工具界面（--tools all）"),
        ("运行时监控", "下方监控面板显示 GPU 占用、内存、活跃请求数"),
        ("性能测试", "「Bench」Tab 可对模型进行基准测试，支持多模型对比 prompt/生成速度"),
    ]),
]

_BENCH_STEPS = [
    ("1  添加测试模型", "从模型库下拉选择 → 点击「添加到列表」，可添加多个模型对比"),
    ("2  配置测试参数", "选择输入长度、生成长度、GPU 层数等；ngl 用逗号分隔可测多组（如 0,99）"),
    ("3  运行并查看结果", "点击「运行」→ 实时输出日志 → md 格式自动解析为汇总表格（t/s prompt / t/s gen）"),
]

_TIPS = [
    ("显存不足？", "依次尝试：降低上下文长度 → 减少 GPU 层数 → KV 量化 q8_0 → 关闭 Flash Attention"),
    ("输出重复？", "增大重复惩罚（默认 1.10）或启用 DRY 采样"),
    ("长对话截断？", "开启「上下文滑动」选项，或增大上下文长度"),
    ("局域网访问？", "监听地址改为 0.0.0.0，建议同时设置 API Key"),
    ("多模型服务？", "勾选「路由模式」选择模型目录，支持按 model 字段路由到不同模型"),
    ("搜索模型？", "「下载」Tab 输入关键词搜索 HuggingFace / ModelScope，双击结果自动填入"),
    ("开机自启？", "勾选左下角「开机自启」复选框"),
]


def _make_section(title: str, steps: list[tuple[str, str]], index: int) -> QFrame:
    """生成一个步骤卡片"""
    card = QFrame()
    card.setStyleSheet(
        "QFrame { background:#ffffff; border:1px solid #e8eef2; border-radius:6px; }"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 8)
    layout.setSpacing(0)

    # 标题行
    hdr = QLabel(title)
    hdr.setStyleSheet(
        "font-size:14px; font-weight:700; color:#1a202c; border:none; padding-bottom:8px;"
    )
    layout.addWidget(hdr)

    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background:#e8eef2; border:none;")
    layout.addWidget(sep)

    for i, (action, detail) in enumerate(steps):
        row = QFrame()
        row.setStyleSheet(
            "QFrame{border:none;background:"
            + ("#f8fafb" if i % 2 == 0 else "#ffffff") + ";}"
        )
        rl = QVBoxLayout(row)
        rl.setContentsMargins(0, 7, 0, 7)
        rl.setSpacing(2)

        act_lbl = QLabel(f"  {action}")
        act_lbl.setStyleSheet(
            "font-size:13px; font-weight:600; color:#2d3748; border:none; background:transparent;"
        )
        rl.addWidget(act_lbl)

        det_lbl = QLabel(f"     {detail}")
        det_lbl.setStyleSheet(
            "font-size:12px; color:#718096; border:none; background:transparent;"
        )
        det_lbl.setWordWrap(True)
        rl.addWidget(det_lbl)

        layout.addWidget(row)

    bot = QFrame()
    bot.setFixedHeight(4)
    bot.setStyleSheet("border:none;")
    layout.addWidget(bot)

    return card


def _make_tips(tips: list[tuple[str, str]]) -> QFrame:
    """生成常见问题卡片"""
    card = QFrame()
    card.setStyleSheet(
        "QFrame { background:#fffbeb; border:1px solid #f6e05e; border-radius:6px; }"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 8)
    layout.setSpacing(0)

    hdr = QLabel("常见问题速查")
    hdr.setStyleSheet(
        "font-size:14px; font-weight:700; color:#975a16; border:none; padding-bottom:8px;"
    )
    layout.addWidget(hdr)

    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background:#f6e05e; border:none;")
    layout.addWidget(sep)

    for i, (q, a) in enumerate(tips):
        row = QFrame()
        row.setStyleSheet(
            "QFrame{border:none;background:"
            + ("#fffcf0" if i % 2 == 0 else "#fffbeb") + ";}"
        )
        rl = QVBoxLayout(row)
        rl.setContentsMargins(0, 7, 0, 7)
        rl.setSpacing(2)

        q_lbl = QLabel(f"  Q: {q}")
        q_lbl.setStyleSheet(
            "font-size:13px; font-weight:600; color:#975a16; border:none; background:transparent;"
        )
        rl.addWidget(q_lbl)

        a_lbl = QLabel(f"     {a}")
        a_lbl.setStyleSheet(
            "font-size:12px; color:#744210; border:none; background:transparent;"
        )
        a_lbl.setWordWrap(True)
        rl.addWidget(a_lbl)

        layout.addWidget(row)

    bot = QFrame()
    bot.setFixedHeight(4)
    bot.setStyleSheet("border:none;")
    layout.addWidget(bot)

    return card


class UsageGuidePanel(QWidget):
    """使用指南面板：精简的分步操作指引"""

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        title = QLabel("使用指南")
        title.setStyleSheet(
            "font-size:15px; font-weight:700; color:#1a202c; padding-bottom:2px; border:none;"
        )
        layout.addWidget(title)

        subtitle = QLabel("快速上手 LLM Launcher 的 5 个步骤")
        subtitle.setStyleSheet("font-size:12px; color:#718096; border:none; padding-bottom:4px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        for i, (sec_title, steps) in enumerate(_STEPS):
            layout.addWidget(_make_section(sec_title, steps, i))

        # Bench 专用卡片
        bench_card = _make_section("性能测试 (Bench)", _BENCH_STEPS, len(_STEPS))
        bench_card.setStyleSheet(
            "QFrame { background:#f0fff4; border:1px solid #9ae6b4; border-radius:6px; }"
        )
        layout.addWidget(bench_card)

        layout.addWidget(_make_tips(_TIPS))

        # 底部链接
        footer = QLabel(
            '<span style="color:#718096;font-size:11px;">'
            '详细参数说明请切换到「参数指南」Tab · '
            '<a href="https://github.com/ggml-org/llama.cpp" style="color:#2d7dd2;">llama.cpp 官方文档</a>'
            '</span>'
        )
        footer.setOpenExternalLinks(True)
        footer.setStyleSheet("border:none; padding-top:4px;")
        layout.addWidget(footer)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
