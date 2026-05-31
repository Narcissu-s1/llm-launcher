import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
root = Path(__file__).resolve().parents[2]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))