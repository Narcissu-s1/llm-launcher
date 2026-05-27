# 技术栈

## 语言
- Python 3.10+（使用 `X | Y` 联合类型语法）

## 核心依赖
- **textual** >= 0.40.0 — TUI 框架（当前 UI 层，计划第五阶段替换为桌面 GUI）
- **psutil** >= 5.9.0 — 系统/进程监控
- **pyyaml** >= 6.0 — YAML 配置文件解析
- **pytest** >= 8.0.0 — 测试框架

## 标准库用法
- `urllib.request` — HTTP 下载（不用 requests），支持 SSL context 注入
- `ssl` — 跳过证书验证时创建自定义 context
- `threading` — 下载/扫描后台线程

## 外部工具
- **llama.cpp** — LLM 推理后端，项目管理其 llama-server 进程

## 配置格式
- `config.yaml` — YAML 格式，包含 model、server、app、presets 四个顶级键

## 运行环境
- Windows（主要目标平台）
- 需要本地安装 llama.cpp 并配置路径

## 已知 Textual 限制（影响功能决策）
- `Slider` 控件在 Textual 8.2.7 已移除，改用 Input
- `RadioSet` 显示异常，改用多个 Checkbox 手动互斥
- 无系统托盘 API，托盘功能推迟到第五阶段 GUI 重构
