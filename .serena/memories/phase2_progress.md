# 阶段二进度

> 进度跟踪以需求文档 `llm-launcher-需求文档.html` 为准。

## 整体状态：完成（~95%）

| 模块 | 进度 | 状态 |
|------|------|------|
| 2.1 高级参数 | 28/28 | ✅ 完成 |
| 2.2 运行时监控 | 4/4 | ✅ 完成 |
| 2.3 预设管理 | 4/4 | ✅ 完成 |
| 2.4 API 测试面板 | 2/2 | ✅ 完成（ChatPanel） |

## 阶段三进度（部分完成）

| 模块 | 状态 |
|------|------|
| 3.1 多模型管理 | ✅ ModelLibraryPanel，扫描本地 GGUF |
| 3.2 远程模型下载 | ✅ DownloadPanel，支持 HF/HF镜像/ModelScope，扫描→勾选→下载 |
| 3.3 自动化 | ❌ 未开始 |
| 3.4 托盘模式 | ⏸ 推迟到第五阶段 GUI 重构 |

## 关键实现细节

### 下载器（core/hf_downloader.py）
- `HFDownloader.scan()` 单独线程查询文件列表，返回 `list[RemoteFile]`
- `HFDownloader.start()` 接收用户选中的 `list[RemoteFile]` 开始下载
- ModelScope API: `GET /api/v1/models/{repo_id}/repo/files?Recursive=true`，响应 `Data.Files[].Path/Size`
- HF API: `GET /api/models/{repo_id}`，响应 `siblings[].rfilename/size`
- 下载 URL: HF `{endpoint}/{repo_id}/resolve/main/{path}`，MS `/models/{repo_id}/resolve/master/{path}`

### 下载面板（ui/widgets/download_panel.py）
- DataTable 列 key 用 `add_columns()` 返回值，不用字符串列名（避免 CellDoesNotExist）
- 文件默认全不选（☐），点击行切换 ☐/☑

### Textual 注意事项
- 后台线程 UI 更新必须用 `call_from_thread`
- `RadioSet` 有显示 bug，改用多 Checkbox 手动互斥（`_SOURCE_IDS` 元组 + `on_checkbox_changed`）
- `_safe_int()` / `_safe_float()` 辅助函数用于输入验证

## 下一步
阶段三剩余：3.3 自动化（开机自启、崩溃重启）
