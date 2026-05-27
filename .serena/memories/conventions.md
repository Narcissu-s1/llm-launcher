# 代码规范

## 命名
- 类名：PascalCase（如 `ConfigStore`、`ProcessSupervisor`）
- 函数/方法：snake_case（如 `collect_params`、`resolve`）
- 常量：UPPER_SNAKE_CASE（如 `EVENT_STATUS_CHANGED`）
- 私有成员：前缀下划线（如 `self._event_bus`）

## 类型提示
- 使用 Python 3.10+ 语法：`str | None` 而非 `Optional[str]`
- 函数签名包含返回类型

## 文档字符串
- 模块级：简短描述用途（中文）
- 类/方法：仅在逻辑非显而易见时添加

## 设计模式
- EventBus 发布-订阅模式解耦组件
- Supervisor 模式管理子进程
- 配置与 UI 分离，ConfigStore 负责持久化
- 后台操作（下载、扫描）用 threading.Thread + `call_from_thread` 回调 UI

## 文件组织
- 每个模块一个职责
- `core/` 不依赖 `ui/`，保证 GUI 重构时可零改动复用
