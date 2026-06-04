# llm-launcher vs llama.cpp-hub 横向对比与改进方案

> 调研日期:2026-06-04
> 对比对象:`D:\Myprogram\llm-launcher`(Python 桌面 GUI)与 `D:\Myprogram\llama.cpp-hub`(Java Web 壳)
> 核心结论:两者是**同生态不同形态**,不存在直接竞争,但有 8+ 项可借鉴改进点。

---

## 一、横向对比矩阵

| 维度 | llm-launcher(本项目) | llama.cpp-hub | 差异本质 |
|---|---|---|---|
| **部署形态** | Windows 桌面 GUI(单 exe / 托盘) | 浏览器侧 Web 壳(自写 Netty 路由) | 离线单机 vs 跨设备 Web 访问 |
| **UI 范式** | PySide6 6.5+ 原生窗口 + 自绘样式 | Vanilla JS(ES Module)+ 静态 HTML | 桌面精致 vs 轻量 Web |
| **进程模型** | **单 llama-server 进程 + 路由模式**多模型(`--models-dir`) | **每模型独立子进程** + 独立端口(8081 起自增) | 路由 vs 隔离(本项目更省内存,Hub 更稳) |
| **后端通信方式** | 不实现 HTTP server,纯客户端(用户自启) | 自写 Netty HTTP + WebSocket + gson | 客户端 vs 服务端 |
| **GGUF 解析** | 纯 `struct` 解析 v2/v3 header(零依赖) | mmap 前 64MB + GGUFBundle 自动识别主文件/分卷/mmproj | 轻量 vs 全功能 |
| **HF 下载** | urllib + Range 头,4 个 Qt Signal | HTTP Range 续传 + WebSocket 进度推送 | 桌面信号 vs WebSocket |
| **实时日志** | 256KB 环形缓冲(本项目推断)+ 彩色分级(error/warn/loaded) | 256KB 环形缓冲 + WebSocket 推送 + Log4j 持久化 | 本地 vs 远程可看 |
| **并发模型** | 异步 EventBus(单例 + Queue + 单 dispatch 线程) + Qt Signal 桥接 | Java 21 虚拟线程(per-task virtual thread) | 显式单 dispatch 线程 vs 平台原生 |
| **配置存储** | YAML 单文件 `config.yaml` + 点号路径 + `threading.RLock` | 10+ 个 JSON 文件,原子写,目录化 | 集中 vs 分文件 |
| **远程/集群** | 无(完全本地单机) | 主从 NodeManager 聚合多实例 | 单用户 vs 多节点 |
| **协议兼容** | 无(只做客户端) | OpenAI / Anthropic / Ollama / LM Studio 四协议 | 桌面不需 vs 统一面板定位 |
| **安全** | 本地无 CORS,API Key 走 OS Keyring(待做) | CORS `*`、HTTPS 自签、节点证书全信任、API Key 明文存 | 本地安全 vs Web 安全债 |
| **打包分发** | Nuitka 编译 + Windows 安装器 | `java -jar` 单 jar 启动 | 桌面安装 vs JVM 启动 |
| **国际化** | 待做(阶段 5 规划) | 仅英文 | 桌面 i18n 价值高 |
| **用量统计** | 无(聊天面板仅显示首字延迟/速度) | 二进制请求日志 + 用量报告 | 个人使用 vs 多用户运营 |
| **基准测试** | llama-bench 队列 + md 解析 | llama-bench 包装 + 简易塞上下文 | 相似 |
| **平台绑定** | Windows 专用(开机自启/托盘/Jobs API) | 跨平台 Java | 强 Windows 优化 |
| **启动复杂度** | 中(需先启 llama-server) | 低(自带启动) | 反向 |
| **依赖体积** | 极小(纯 Python + PySide6,Nuitka 后 ~50MB) | 较大(JDK 21 + jar + 静态资源) | 桌面友好 |
| **维护门槛** | 中(熟悉 PySide6 / Qt 即可) | 中(熟悉 Netty / 虚拟线程) | 相似 |

---

## 二、互补分析

### 2.1 llm-launcher 已做好、llama.cpp-hub 没有的

| 能力 | llm-launcher 实现 | 价值 |
|---|---|---|
| **core/ui 严格解耦** | `core/` 零 PySide6 依赖,`ui/bridge.py` 唯一耦合点 | 易于测试与重用(本项目 `tests/` 体系完整) |
| **GGUF 零依赖解析** | 纯 `struct` 解 v2/v3 header,含量化推断、mmproj 探测 | 启动快、无原生依赖 |
| **Windows 深度优化** | 开机自启 / 托盘 / Jobs API 兜底 / psutil | Hub 在 Windows 上是普通 jar,做不到这层 |
| **零额外二进制依赖** | 纯 Python + Nuitka | 用户无需先装 JDK/JRE |
| **配置语义化** | YAML + 点号路径(如 `models.llama3.path`),RLock 保护 | 比 Hub 的 10+ JSON 文件易读 |
| **EventBus 异步** | 单例 + Queue + 单一 dispatch 线程,避免双消费 | Hub 旧版有重复 `_dispatch_loop` 线程安全 bug(commit `ced1c9a` 修复过) |

### 2.2 llama.cpp-hub 已有、llm-launcher 没有的

| 能力 | Hub 实现 | 本项目是否要补 |
|---|---|---|
| **多协议 API 兼容层** | OpenAI/Anthropic/Ollama/LM Studio | 见 3.1 |
| **远程节点主从** | NodeManager + 节点证书 | **不做**(见第四章) |
| **用量统计 / 报告** | 二进制请求日志 | 见 3.3 |
| **HTTPS 自签** | 内嵌证书生成 | **不做**(本地单机) |
| **GGUF Bundle 自动识别** | 主文件/分卷/mmproj 关联 | 见 3.7 |
| **日志 WebSocket 推送** | 远程查看 | **不做**(Web 方向不做) |
| **Log4j 持久化** | 结构化日志 | 见 3.9(配置原子写可借鉴) |
| **MCP 集成** | 8075 Netty | **不做**(作者自嘲"用处不大") |

### 2.3 两边都浅、可联合强化的

| 方向 | 当前状态 | 联合强化路径 |
|---|---|---|
| **GGUF 能力自动检测** | Hub 浅、launcher 无 | 启发式推断 embedding/rerank/tools/vision/audio(见 3.7) |
| **HF 搜索/爬取** | Hub 走 API,launcher 走 API | 站点爬取补漏(见 3.6) |
| **基准输出可视化** | 都只解析 | 共享图表格式 / 跨平台 JSON 报告 |
| **错误诊断** | Hub 自带诊断(部分),launcher 阶段 5 计划 | 借鉴 Hub 的"启动失败原因提示"模板 |
| **多套采样预设** | launcher 已有"预设"概念 | 强化为可导入导出 JSON 预设包(见 3.8) |
| **配置原子写** | Hub 10 个 JSON 都原子写 | launcher YAML 写盘未确认原子(见 3.9) |
| **在线更新** | 都没有 | 借鉴 Hub 的 GitHub Release 检查(见 3.5) |

---

## 三、可借鉴改进方向(按必要性 × 实施成本反比排序)

### 方向 1:多协议 API 兼容层(高必要性 × 中成本)

- **价值一句话**:让本项目"启动一次模型,任何 OpenAI 客户端都能用",把桌面 GUI 升级成统一面板。
- **来源**:Hub 的 `org.mark.llamacpp.server` 包,内嵌 4 协议路由。
- **必要性**:**高**。本地用户常在 Cherry Studio / LM Studio / Cline / Cursor 间切换,直接连 8080 即可。
- **实施成本**:**M**。需要新增 `core/api_server/` 模块(零 PySide6 依赖),用 `aiohttp` 或 `starlette` 起 8090 端口。
- **优先级评分**:8/10。
- **涉及文件**:新增 `core/api_server/router.py` / `openai_handler.py` / `ollama_handler.py`;`ui/control_panel.py` 增加"启用 API 兼容"开关。
- **实施方案**(伪代码):
  ```python
  # core/api_server/router.py
  from starlette.applications import Starlette
  from starlette.routing import Route, Mount
  from .openai_handler import handle_chat_completions
  from .ollama_handler import handle_generate

  def build_app(upstream_url: str) -> Starlette:
      routes = [
          Route("/v1/chat/completions", handle_chat_completions(upstream_url), methods=["POST"]),
          Route("/v1/models", list_models, methods=["GET"]),
          Route("/api/generate", handle_generate(upstream_url), methods=["POST"]),
      ]
      return Starlette(routes=routes)
  ```
  - 透明转发:把 `/v1/chat/completions` 透明转发到本地 `llama-server` 的 `/v1/chat/completions`,**不做协议转换**(避免歧义);只做"统一入口"和"用量埋点"。
- **风险/副作用**:
  - 端口冲突(默认 8090,可配置)
  - 与上游 llama-server 协议版本耦合(需在 README 标注支持版本)
  - 不能替代真正的协议转换器
- **验证标准**:
  - 用 `curl http://localhost:8090/v1/chat/completions -d {...}` 成功
  - Cherry Studio 配 base_url=`http://localhost:8090/v1` 能正常对话
  - Ollama 客户端配 `http://localhost:8090` 能列出 `/api/tags`

### 方向 2:在线更新(高必要性 × 小成本)

- **价值一句话**:用户在桌面 GUI 内一键升级,免去"去 GitHub 翻 release"。
- **来源**:Hub 暂未实现,但可借鉴同类工具的 GitHub Release API 调用。
- **必要性**:**高**。Nuitka 打包后用户最痛的就是"怎么更新"。
- **实施成本**:**S**。10 行代码 + 一个 Signal。
- **优先级评分**:9/10。
- **涉及文件**:`core/updater.py`(新增),`ui/app.py`(启动时检查),`ui/control_panel.py`(显示更新提示)。
- **实施方案**:
  ```python
  # core/updater.py
  import urllib.request, json
  from packaging.version import Version

  def check_update(repo: str, current: str) -> tuple[bool, str, str]:
      url = f"https://api.github.com/repos/{repo}/releases/latest"
      with urllib.request.urlopen(url, timeout=5) as r:
          data = json.load(r)
      latest = data["tag_name"].lstrip("v")
      if Version(latest) > Version(current):
          return True, latest, data["html_url"]
      return False, latest, ""
  ```
  - 启动时后台检查,不阻塞 UI
  - 检测到新版本在状态栏显示"有新版本 v1.2.3 → [查看]",点击跳浏览器
  - 不自动下载(避免损坏用户本地数据)
- **风险/副作用**:
  - GitHub API 限流(未鉴权 60/h/ IP)
  - 需网络,首次启动应允许跳过
- **验证标准**:
  - 修改本地 `__version__` 后启动,5 秒内状态栏出现更新提示
  - 断网情况下不报错,只是没有提示

### 方向 3:配置原子写(中必要性 × 小成本)

- **价值一句话**:写到一半断电/进程被杀,配置文件不会损坏成空文件。
- **来源**:Hub 全部 JSON 写都走原子写(`*.tmp` → `os.replace`)。
- **必要性**:**中**。YAML 损坏后用户最痛的是"启动报错但不知道哪里坏了"。
- **实施成本**:**S**。3 行代码改 `core/config.py` 的 `save()`。
- **优先级评分**:7/10。
- **涉及文件**:`core/config.py` 的 `save()`。
- **实施方案**:
  ```python
  # core/config.py
  import os, tempfile

  def save(self) -> None:
      data = yaml.safe_dump(self._to_dict(), allow_unicode=True, sort_keys=False)
      path = self.path
      dir_ = os.path.dirname(path) or "."
      with tempfile.NamedTemporaryFile("w", dir=dir_, encoding="utf-8",
                                        prefix=".config.", suffix=".tmp",
                                        delete=False) as f:
          f.write(data)
          tmp = f.name
      try:
          os.replace(tmp, path)  # POSIX 原子;Windows 同卷下也是原子
      except Exception:
          os.unlink(tmp)
          raise
  ```
  - 同时加 `backup_corrupt()`:启动时若 `yaml.safe_load` 失败,把坏文件改名 `config.yaml.broken-20260604-1530` 再用默认值启动。
- **风险/副作用**:
  - Windows 跨卷 `os.replace` 可能失败(本项目配置固定在 exe 同目录,通常同卷)
- **验证标准**:
  - 测试中 `kill -9` 模拟断电,配置文件不损坏
  - 故意写坏 YAML,启动后能自动备份并用默认配置启动

### 方向 4:GGUF 能力自动检测(高必要性 × 中成本)

- **价值一句话**:用户在聊天面板看到的是"Q4_K_M, 7B 文本",而不是"Q4_K_M"——并能自动判断是否支持 embedding/rerank/vision。
- **来源**:Hub 的 GGUFBundle 启发式主文件识别。
- **必要性**:**高**。模型库越来越大,人工标注不可持续。
- **实施成本**:**M**。在 `core/model_resolver.py` 增加能力推断表。
- **优先级评分**:8/10。
- **涉及文件**:`core/model_resolver.py`,`ui/widgets/model_library_panel.py`。
- **实施方案**:
  ```python
  # core/model_resolver.py
  def detect_capabilities(meta: dict) -> set[str]:
      caps = {"text"}
      arch = meta.get("general.architecture", "")
      # 1. 量化与规模已从 general.* 读出
      # 2. embedding/rerank:文件名含 "embed"/"bge"/"e5"/"gte"/"rerank"
      name = meta.get("name", "").lower()
      if any(k in name for k in ("embed", "bge-", "e5-", "gte-", "rerank")):
          caps.add("embedding" if "rerank" not in name else "rerank")
      # 3. vision:同目录有 mmproj,或文件名含 "vision"/"vl"/"llava"
      if "mmproj" in name or any(k in name for k in ("-vl-", "llava", "vision")):
          caps.add("vision")
      # 4. tools:文件名含 "tool"/"functionary"/"hermes"
      if any(k in name for k in ("tool", "functionary", "hermes")):
          caps.add("tools")
      # 5. audio:文件名含 "whisper"/"audio"
      if any(k in name for k in ("whisper", "audio")):
          caps.add("audio")
      return caps
  ```
  - 推断结果缓存到 `config.yaml` 的 `models.<id>.capabilities`,避免每次启动重新扫。
- **风险/副作用**:
  - 启发式有误判(例如 "Qwen2.5-7B-Instruct" 不含关键词,正确归类为 text)
  - 误判后果:用户启错模式(embedding 跑 chat),UI 需明确提示
- **验证标准**:
  - 给 5 个已知模型(bge-m3 / Qwen2.5-VL / Qwen2.5-Instruct / Qwen2.5-Coder / whisper.cpp)跑解析,能力集合 100% 正确
  - UI 在聊天面板显示能力标签 (text / +vision / +tools / embedding)

### 方向 5:用量统计(中必要性 × 中成本)

- **价值一句话**:聊天面板显示"今日已用 12.3k tokens,首字延迟 280ms,生成 42.5 tok/s",可选导出 CSV。
- **来源**:Hub 的二进制请求日志 + 用量报告。
- **必要性**:**中**。个人单机用户也想知道"这个月烧了多少 token 等价"。
- **实施成本**:**M**。`core/api_server`(方向 1)顺手做埋点;若不启用 API 层,可在 `llama-server` 启动时加 `--log-verbosity` + 解析日志估算。
- **优先级评分**:6/10。
- **涉及文件**:新增 `core/usage/recorder.py`,`ui/widgets/monitor_panel.py`。
- **实施方案**:
  ```python
  # core/usage/recorder.py
  from dataclasses import dataclass, asdict
  from pathlib import Path
  import json, time, threading

  @dataclass
  class UsageRecord:
      ts: float
      model: str
      prompt_tokens: int
      completion_tokens: int
      first_token_ms: int
      total_ms: int
      tok_per_sec: float

  class UsageRecorder:
      def __init__(self, path: Path):
          self.path = path
          self._lock = threading.Lock()

      def record(self, r: UsageRecord) -> None:
          with self._lock:
              with self.path.open("a", encoding="utf-8") as f:
                  f.write(json.dumps(asdict(r)) + "\n")

      def today_summary(self) -> dict:
          # 读 JSONL,过滤今天,聚合
          ...
  ```
  - 与 EventBus 解耦:`api_server` 在响应时 `bus.publish("usage.recorded", record)`,监听器落盘。
- **风险/副作用**:
  - 磁盘增长(可按天滚动,默认保留 90 天)
  - 精度依赖 `llama-server` 返回的 `usage` 字段(老版本可能没有)
- **验证标准**:
  - 启用 API 兼容层后,聊 10 轮,在 monitor_panel 看到累计 token 与平均速度
  - 导出 CSV 用 Excel 打开正常

### 方向 6:HF 搜索/爬取增强(低必要性 × 中成本)

- **价值一句话**:Hub 走 HF API,本项目也是;但 HF 站点的 trending / by-downloads 列表能补 API 没有的发现能力。
- **必要性**:**低**。API 已经够用,爬取仅锦上添花。
- **实施成本**:**M**。需 HTML 解析,加缓存与去重。
- **优先级评分**:4/10。
- **涉及文件**:`core/hf_downloader.py` 增加 `search_website()`;`ui/widgets/download_panel.py` 增加 tab。
- **实施方案**(伪代码):
  ```python
  def search_website(query: str) -> list[ModelInfo]:
      url = f"https://huggingface.co/models?search={quote(query)}&sort=downloads"
      html = urllib.request.urlopen(url, timeout=10).read().decode()
      # 简单正则提取 <article ...> 卡片中的 name/likes/downloads
      cards = re.findall(r'<article.*?</article>', html, re.S)
      return [_parse_card(c) for c in cards[:20]]
  ```
- **风险/副作用**:
  - HF 改版后解析失效(需加 try/except 降级到 API)
  - 反爬(暂未限流,但要注意)
- **验证标准**:
  - 搜索 "qwen2.5" 能在 downloads 排序下看到前 20 个模型
  - 解析失败时优雅降级到 API 搜索

### 方向 7:配置预设导入/导出(中必要性 × 小成本)

- **价值一句话**:用户 A 调好的"代码补全 Q4 + temp 0.2 + repeat_penalty 1.1"打包成 `preset.code.yaml` 发给用户 B,B 一键导入。
- **必要性**:**中**。本项目已有"预设"概念(见 `core/config.py` 预设段),但导入导出未做。
- **实施成本**:**S**。新增 `core/config_preset.py`。
- **优先级评分**:7/10。
- **涉及文件**:新增 `core/config_preset.py`,`ui/control_panel.py` 增加"导入/导出预设"按钮。
- **实施方案**:
  ```python
  # core/config_preset.py
  def export_preset(cfg: Config, name: str) -> str:
      return yaml.safe_dump({
          "name": name,
          "version": 1,
          "params": cfg.get("presets." + name, {}),
      }, allow_unicode=True)

  def import_preset(cfg: Config, yaml_text: str) -> None:
      data = yaml.safe_load(yaml_text)
      assert data.get("version") == 1
      cfg.set(f"presets.{data['name']}", data["params"])
      cfg.save()
  ```
- **风险/副作用**:
  - 预设与当前模型不匹配(temp 0.2 用于 7B,用在 70B 不好),导入时应提示"目标模型:?"
- **验证标准**:
  - 导出预设 → 重新导入 → 在 UI 预设下拉框能看到
  - 导入非法 YAML 时友好报错

### 方向 8:错误诊断与一键报告(中必要性 × 中成本)

- **价值一句话**:`llama-server` 启动失败时,UI 显示"可能原因:1. 端口占用 2. 模型文件损坏 3. CUDA 不匹配 [复制诊断报告]",点 [复制] 即可贴到 issue。
- **来源**:Hub 在 Netty 路由里给每个错误返回带原因的 JSON。
- **必要性**:**中**(本项目阶段 5 计划已包含)。
- **实施成本**:**M**。`core/process_manager.py` 的 `start()` 已捕获 stderr,只需加模式匹配。
- **优先级评分**:7/10。
- **涉及文件**:`core/process_manager.py`,`ui/control_panel.py`。
- **实施方案**:
  ```python
  # core/process_manager.py
  ERROR_PATTERNS = [
      (r"Address already in use", "端口被占用,关闭占用进程或修改端口"),
      (r"failed to load model", "模型文件损坏或路径错误"),
      (r"CUDA error", "CUDA 不匹配,确认显卡驱动与 llama.cpp 版本"),
      (r"main: model metadata", "GGUF 头损坏,重新下载"),
  ]

  def diagnose(stderr_tail: str) -> list[str]:
      hints = []
      for pat, hint in ERROR_PATTERNS:
          if re.search(pat, stderr_tail, re.I):
              hints.append(hint)
      return hints
  ```
- **验证标准**:
  - 故意把端口占用,启动失败时弹出"端口被占用"提示
  - 点 [复制诊断报告] 粘贴到剪贴板内容含:时间、配置摘要、stderr 后 50 行、已识别原因

### 方向 9:Web 管理面板(低必要性 × 大成本)

- **价值一句话**:从其他设备访问 `http://<desktop-ip>:8090` 看模型状态(只读)。
- **必要性**:**低**。个人单机场景下需求弱,且增加攻击面。
- **实施成本**:**L**。需要 starlette + 鉴权(HTTP Basic / Token)+ 防火墙提示。
- **优先级评分**:3/10。
- **建议**:**见第四章,不做**。

---

## 四、不建议引入的方向(避免过度设计)

| 方向 | 不建议理由 |
|---|---|
| **Spring/Java 风格依赖注入** | 本项目阶段 1-4 已经是 `core/ui` 严格分层 + bridge 单点耦合,DI 容器是 Java 习惯在 Python 项目中不必要。`threading.RLock` + 显式 `__init__` 已经够用。 |
| **浏览器侧 ES Module 风格** | 违反"桌面应用"定位;PySide6 的 QWebEngineView 也可以嵌 Web,但 GUI 已经够用。 |
| **远程节点主从** | 单用户单机场景无需求;且会引入证书 / 网络 / 鉴权三层复杂度。Hub 自己也吐槽节点证书全信任是债。 |
| **HTTPS 自签证书** | 本地单机 127.0.0.1 通信不需要 HTTPS;TLS 只握手开销就是浪费。如果未来做 Web 访问(方向 9),再统一考虑用 Let's Encrypt 内网方案。 |
| **MCP(Model Context Protocol)集成** | Hub 作者自嘲"用处不大";本项目核心是"启模型",不在 LLM 工具调用链上,MCP 是给 Agent 用的。 |
| **Spring Cloud / 集群调度** | 进程级 + 端口自增是 Hub 在多用户场景的妥协,本项目单用户,单进程 + 路由模式已足够。 |
| **微服务化拆分** | `core/` 已经是模块化目录,没必要再拆包;一个 Python 进程启动也比 Java 微服务快一个数量级。 |
| **复杂 ORM / 数据库** | 配置用 YAML 即可,用量统计用 JSONL,真要查询用 pandas 读 CSV 就行,SQLite/Postgres 是杀鸡用牛刀。 |
| **WebSocket 实时日志** | 本项目 Qt Signal 已经实时;WebSocket 是给"远程"用的,本项目不做远程。 |
| **插件系统 / 扩展点** | 桌面 GUI 用户群体小,插件生态养不起来;不如把核心模块 API 化(已有 `ui/bridge.py`)让二次开发者直接 import。 |

---

## 五、推荐路线图(3-5-3)

### 5.1 立即可做(本迭代,工作量 ≤ 1 周)

| 序号 | 方向 | 工作量 | 预期收益 |
|---|---|---|---|
| 1 | **方向 2:在线更新** | 0.5d | 用户最痛的"Nuitka 打包后怎么升级"一次性解决 |
| 2 | **方向 3:配置原子写** | 0.5d | 杜绝配置损坏事故 |
| 3 | **方向 7:预设导入导出** | 1d | 用户分享调参经验,社区传播 |

合计 **2 天**。

### 5.2 下一阶段(阶段 5 前后,1-2 周)

| 序号 | 方向 | 工作量 | 预期收益 |
|---|---|---|---|
| 4 | **方向 4:GGUF 能力自动检测** | 2d | 模型库管理自动化,UI 体验质变 |
| 5 | **方向 8:错误诊断与一键报告** | 2d | 降低 issue 沟通成本 |
| 6 | **方向 1:多协议 API 兼容层** | 3d | "统一面板"价值落地,接 Cherry Studio/Cline |
| 7 | **方向 5:用量统计** | 1d | 与方向 1 共享埋点,边际成本低 |
| 8 | **阶段 5 国际化** | 2d | 已规划,直接做 |

合计 **2 周**。

### 5.3 远期(2 个月后,按需启动)

| 序号 | 方向 | 工作量 | 预期收益 |
|---|---|---|---|
| 9 | **方向 6:HF 搜索/爬取** | 3d | 仅在 API 不够用时启动 |
| 10 | **方向 9:Web 管理面板** | 1 周 | 仅当用户明确要求"手机/平板查看"时启动 |
| 11 | **可观测性 + Crash 上报**(无埋点) | 1 周 | Sentry 替代品,自建,只记 stacktrace 不记 prompt |

合计 **3 周**(按需)。

---

## 六、关键参考链接

- **llama.cpp-hub GitHub**:https://github.com/IIIIIllllIIIIIlllll/llama.cpp-hub
- **llama.cpp 官方**:https://github.com/ggerganov/llama.cpp
- **llama-server HTTP API**:https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md
- **HF Hub API**:https://huggingface.co/docs/hub/api
- **GGUF 规范**:https://github.com/ggerganov/ggml/blob/master/docs/gguf.md
- **本项目根目录**:`D:\Myprogram\llm-launcher`
- **本项目核心模块**:
  - 业务核心(零 UI 依赖):`D:\Myprogram\llm-launcher\core\`
    - `config.py` / `process_manager.py` / `model_resolver.py` / `model_library.py` / `hf_downloader.py` / `events.py` / `log_watcher.py`
  - 桌面 UI:`D:\Myprogram\llm-launcher\ui\`
    - `app.py` / `bridge.py` / `control_panel.py` / `log_panel.py` / `styles.py` / `widgets/`
  - 测试:`D:\Myprogram\llm-launcher\tests\`
- **本项目阶段记录**:`C:\Users\PC\.claude\projects\D--Myprogram-llm-launcher\memory\phase2_progress.md`

---

### 附:本报告未做的事

1. **未做"双项目合并"建议**。两者形态不同(桌面 vs Web),合并会让两边用户都不满,保持独立、互相借鉴即可。
2. **未做"重写为 Java"建议**。Python 桌面在 Windows 体验、Nuitka 打包、社区生态上仍优于 Java 桌面(Swing/JavaFX 在 Windows 上 UI 渲染差)。
3. **未做"用 llama.cpp-hub 替代本项目"建议**。本项目的零依赖、core/ui 解耦、配置语义化、Windows 深度优化都是 Hub 没有的资产。
