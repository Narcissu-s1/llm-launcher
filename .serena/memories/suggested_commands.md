# 常用命令

## 运行应用
```bash
python main.py
```

## 测试
```bash
pytest tests/
pytest tests/ -v  # 详细输出
```

## 依赖安装
```bash
pip install -r requirements.txt
```

## Windows 特有
- 路径使用反斜杠或原始字符串
- `os.path` 处理路径，不要硬编码分隔符
