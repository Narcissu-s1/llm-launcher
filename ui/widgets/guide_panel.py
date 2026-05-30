from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt


def _section(title: str, rows: list[tuple[str, str, str]]) -> QFrame:
    """生成一个参数分组卡片。rows: (参数名+命令行标志, 默认值, 说明)"""
    card = QFrame()
    card.setStyleSheet(
        "QFrame { background:#ffffff; border:1px solid #e8eef2; border-radius:6px; }"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 10, 14, 4)
    layout.setSpacing(0)

    hdr = QLabel(title.upper())
    hdr.setStyleSheet(
        "font-size:10px;font-weight:700;color:#718096;letter-spacing:0.5px;"
        "border:none;padding-bottom:8px;"
    )
    layout.addWidget(hdr)

    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background:#e8eef2;border:none;")
    layout.addWidget(sep)

    for i, (param, default, desc) in enumerate(rows):
        row = QFrame()
        row.setStyleSheet(
            "QFrame{border:none;background:" +
            ("#f8fafb" if i % 2 == 0 else "#ffffff") + ";}"
        )
        rl = QVBoxLayout(row)
        rl.setContentsMargins(0, 8, 0, 8)
        rl.setSpacing(3)

        # 第一行：参数名 + 默认值标签
        top = QFrame()
        top.setStyleSheet("border:none;background:transparent;")
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(2)

        name_lbl = QLabel(param)
        name_lbl.setStyleSheet(
            "font-family:'DM Mono',Consolas,monospace;font-size:12px;"
            "font-weight:600;color:#3182ce;border:none;background:transparent;"
        )
        name_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        top_layout.addWidget(name_lbl)

        if default:
            def_lbl = QLabel(f"默认：{default}")
            def_lbl.setStyleSheet(
                "font-size:11px;color:#a0aec0;font-family:'DM Mono',Consolas,monospace;"
                "border:none;background:transparent;"
            )
            top_layout.addWidget(def_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            "font-size:12px;color:#4a5568;border:none;background:transparent;"
        )
        desc_lbl.setWordWrap(True)

        rl.addWidget(top)
        rl.addWidget(desc_lbl)
        layout.addWidget(row)

    # 底部间距
    bottom = QFrame()
    bottom.setFixedHeight(4)
    bottom.setStyleSheet("border:none;")
    layout.addWidget(bottom)

    return card


_SECTIONS = [
    ("基础参数", [
        ("上下文长度  -c",
         "32768",
         "模型单次可处理的最大 token 数。选项：2048 / 4096 / 8192 / 16384 / 32768；路由模式下额外支持 65536 / 131072 / 262144（256K）。Agent 场景建议至少 32K：system prompt + 工具定义 + 多轮对话可快速消耗上下文。"),
        ("GPU 层数  --n-gpu-layers",
         "-1（全部）",
         "将模型前 N 层卸载到 GPU 显存。-1 = 全部卸载（推荐）；0 = 纯 CPU；1~N = 混合，适合显存不足时分担部分层。切换模型后上限自动按 block_count 更新。"),
        ("并发数  -np",
         "1",
         "同时处理的请求槽位数。选项：1 / 2 / 4 / 8。每个 slot 独占一份 KV Cache，会等比增加显存占用。单用户 Agent 场景设 1 即可。"),
        ("端口  --port",
         "8080",
         "HTTP 服务监听端口。若被其他程序占用，启动时会提示冲突，换一个未占用的端口即可。"),
        ("监听地址  --host",
         "127.0.0.1",
         "127.0.0.1 = 仅本机访问（安全）；0.0.0.0 = 允许局域网内其他设备访问（需注意防火墙与安全风险）。"),
        ("Jinja 模板  --jinja",
         "开启（llama-server 默认）",
         "Tool Calling 必须开启。工具调用的消息格式（role=tool / tool_use / tool_result）依赖 Jinja 模板才能正确拼接成 prompt，关闭后工具调用会完全失败。"),
        ("上下文滑动  --context-shift",
         "开启（默认勾选）",
         "长对话保护：上下文填满时滑动窗口而非截断，保留最近的对话内容。Agent 多轮场景必须开启，配合 --keep 使用。"),
        ("保护前缀  --keep <n>",
         "0",
         "配合 --context-shift，保护开头 N 个 token 不被滑走（通常是 system prompt + 工具定义）。建议值 = system prompt tokens + 工具定义 tokens，约 1000~5000。"),
        ("轮询级别  --poll <0-100>",
         "50",
         "控制服务端等待新请求时的 CPU 轮询比例。0 = 纯睡眠（低 CPU 占用，延迟略高）；100 = 纯忙等（最低延迟，高 CPU 占用）；50 = 平衡默认值。低延迟场景可调高，后台运行可调低。"),
    ]),
    ("KV Cache 与显存", [
        ("KV-K 量化  -ctk\nKV-V 量化  -ctv",
         "f16",
         "对 KV Cache 的 Key / Value 张量进行量化以节省显存。f16 = 全精度；q8_0 ≈ 节省 50%，精度损失极小（推荐长上下文场景）；q4_0 ≈ 节省 75% 但精度下降明显。"),
        ("统一 KV 池  -kvu",
         "开启（默认勾选）",
         "多个并发 slot 共享同一 KV 池，提升多并发下的显存利用率。多用户场景配合 -ctk q8_0 可显著降低显存占用。"),
        ("KV 不放 GPU  --no-kv-offload",
         "关闭",
         "强制 KV Cache 保留在 CPU 内存，适合 GPU 显存极度紧张时牺牲速度换稳定性。"),
        ("Flash Attention  -fa",
         "auto",
         "分块计算注意力，减少显存读写次数，长上下文时速度提升显著。auto = 由 llama.cpp 自动判断；on = 强制开启；off = 强制关闭。部分模型架构（MLA、某些 GQA 变体）有兼容性问题时设为 off。"),
        ("Prompt Cache  --cache-prompt",
         "开启（默认勾选）",
         "缓存 system prompt 的 KV 状态，下次相同前缀时跳过重算。Agent 场景每轮共享相同 system prompt + 工具定义，开启后首 token 延迟大幅降低。"),
        ("空闲 Slot 复活  --cache-idle-slots",
         "开启（默认勾选）",
         "空闲的 slot 保留 KV 缓存而非立即清空，再次使用时可复用，减少重新填充开销。"),
        ("Cache RAM 上限  --cache-ram",
         "8192 MiB",
         "KV Cache 在 CPU 内存中的最大占用量（MiB）。超出后旧缓存会被逐出。"),
    ]),
    ("推理速度", [
        ("线程数  -t",
         "-1（自动）",
         "CPU 推理线程数。-1 = 自动使用物理核心数。GPU 推理时影响较小；纯 CPU 推理时设为物理核心数（非超线程数）通常最优。"),
        ("Prompt 线程  -tb",
         "-1（同 -t）",
         "Prompt 预填充（prefill）阶段的线程数，独立于解码阶段线程数。-1 = 与 -t 相同。"),
        ("逻辑批大小  -b",
         "2048",
         "一次 prefill 处理的最大 token 批量（逻辑层）。较大值加快 prompt 处理速度，但占用更多内存。"),
        ("物理批大小  -ub",
         "512",
         "GPU 内核实际计算的批量大小，须 ≤ -b。较小值降低显存峰值，较大值提升吞吐量。"),
        ("HTTP 线程  --threads-http",
         "-1（自动）",
         "处理 HTTP 请求的线程数。高并发（-np > 4）时可适当提高，-1 = 自动。"),
        ("跳过预热  --no-warmup",
         "关闭",
         "跳过启动时的预热推理，加快启动速度，但首次实际请求可能稍慢（需 JIT 编译/缓存初始化）。"),
    ]),
    ("采样参数", [
        ("温度  --temp",
         "0.60，范围 0.0 ~ 2.0",
         "控制输出随机性。0 = 贪心解码（完全确定性）；0.6 = Agent 推荐值，减少格式错误；> 1.0 = 更随机发散。代码生成推荐 0.1~0.3，创意写作推荐 0.8~1.0。"),
        ("Top-K  --top-k",
         "40",
         "每步只从概率最高的 K 个候选 token 中采样。40 为常用值；0 = 关闭（不限制候选数量）。"),
        ("Top-P  --top-p",
         "0.90，范围 0.0 ~ 1.0",
         "核采样（Nucleus Sampling）：从累计概率达 P 的最小候选集合中采样。0.90 = 覆盖概率最高的 90% 候选，比 0.95 更保守。"),
        ("Min-P  --min-p",
         "0.05，范围 0.0 ~ 1.0",
         "过滤概率低于「最高 token 概率 × Min-P」的候选，有效减少低质输出。0.05 为推荐值，可与 Top-P 联合使用。"),
        ("重复惩罚  --repeat-penalty",
         "1.10，范围 0.5 ~ 2.0",
         "对已出现的 token 施加惩罚以抑制重复。1.0 = 不惩罚；1.1 = 推荐值，防止生成重复内容；1.3+ 会导致输出刻意回避已用词汇。"),
        ("随机种子  -s",
         "-1（随机）",
         "固定随机种子以复现相同输出。-1 = 每次使用随机种子，结果不可复现。"),
        ("最大生成长度  -n",
         "-1（无限）",
         "单次生成的最大 token 数。-1 = 不限制（受上下文长度约束）；正数 = 硬截断，适合控制输出长度或成本。"),
        ("忽略 EOS  --ignore-eos",
         "关闭",
         "忽略模型输出的终止符（EOS token），强制继续生成直到达到最大长度。调试或测试场景使用，正常对话不建议开启。"),
    ]),
    ("思考 / 推理模式", [
        ("思考模式  -rea",
         "auto，选项：auto / on / off",
         "控制模型的链式思考（Chain-of-Thought）行为。auto = 模型自行决定；on = 强制开启 CoT；off = 禁用思考过程。适用于 DeepSeek-R1 等支持思考模式的模型。"),
        ("思考格式  --reasoning-format",
         "none，选项：none / deepseek / deepseek-legacy",
         "思考内容的输出格式。deepseek = 使用 <think>...</think> 标签包裹思考过程；none = 不在响应中输出思考内容。"),
        ("思考预算  --reasoning-budget",
         "-1（不限），0 = 不思考",
         "限制思考阶段最多生成的 token 数，用于控制推理成本和响应速度。-1 = 不限制；0 = 禁止思考（同 -rea off）；正数 = token 上限。"),
    ]),
    ("多模态", [
        ("视觉编码器放 GPU  --mmproj-offload",
         "开启",
         "将 mmproj 视觉投影模型卸载到 GPU 加速图像编码。显存不足时关闭可回退到 CPU，但速度会明显下降。"),
        ("最小视觉 Token  --image-min-tokens\n最大视觉 Token  --image-max-tokens",
         "不限制",
         "图像编码后映射到的 token 数量范围。较小值加快处理但损失图像细节；较大值精度更高但消耗更多上下文长度和计算资源。"),
    ]),
    ("安全与访问控制", [
        ("API Key  --api-key",
         "空（无鉴权）",
         "设置后，客户端请求须携带 Authorization: Bearer <key> 请求头。仅本机访问（127.0.0.1）时可留空；局域网访问时强烈建议设置以防止未授权使用。"),
        ("超时秒数  --timeout",
         "1200 秒（默认）",
         "单次请求的最长处理时间。超时后服务端强制断开连接。Agent 复杂推理或工具调用链可能耗时较长，建议设为 1200 秒以上。"),
        ("Prometheus 监控  --metrics",
         "关闭",
         "暴露 /metrics 端点，供 Prometheus 抓取延迟、吞吐量、KV Cache 命中率等指标，用于生产环境监控。"),
        ("Slots 端点  --slots",
         "关闭",
         "暴露 /slots 端点，可实时查看各并发槽位的当前状态（空闲 / 处理中 / 等待）。"),
        ("WUI 工具  --tools all",
         "关闭",
         "启用 llama-server 内置 Web 工具界面，在浏览器中提供交互式聊天与工具页面。勾选左侧面板「启动WUI工具」启用。"),
    ]),
    ("路由模式（多模型）", [
        ("模型目录  --models-dir",
         "空（关闭）",
         "勾选左侧面板「路由模式」后选择模型目录，服务器自动扫描目录中的 GGUF 文件。请求中指定 \"model\" 字段路由到对应模型，/v1/models 列出所有可用模型。上下文长度选项自动扩展至 256K。"),
    ]),
    ("待实现参数", [
        ("输出格式约束  --grammar / --json-schema",
         "—",
         "约束模型输出必须符合指定的 GBNF 语法或 JSON Schema，确保结构化输出。需文本输入区 UI 支持，计划在后续版本实现。"),
        ("推理预算提示  --reasoning-budget-message",
         "—",
         "思考预算用完时自动注入给模型的提示语，引导模型基于已有思考作出总结回答。"),
    ]),
]


class GuidePanel(QWidget):
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

        title = QLabel("参数指南")
        title.setStyleSheet(
            "font-size:15px;font-weight:700;color:#2d3748;padding-bottom:2px;border:none;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "基于项目需求文档整理。高级参数分组默认折叠，勾选后才会传入命令行；"
            "未勾选的分组使用 llama.cpp 内置默认值。"
        )
        subtitle.setStyleSheet("font-size:12px;color:#718096;border:none;padding-bottom:4px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        for sec_title, rows in _SECTIONS:
            layout.addWidget(_section(sec_title, rows))

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
