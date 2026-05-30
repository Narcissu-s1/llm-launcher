# core/model_resolver.py
"""搜索 llama-server.exe 的路径解析器"""

import os
import shutil


class ModelResolver:
    """搜索 llama-server 可执行文件

    搜索优先级：
    1. config.yaml 中指定的 llama.cpp 目录
    2. 当前工作目录
    3. 同级 bin/ 子目录
    4. PATH 环境变量

    config_path 应为 llama.cpp 目录（包含 llama-server.exe 及相关 dll），
    而非可执行文件本身。设为目录是为了确保所有依赖 dll 也在搜索范围内。
    """

    _EXE_NAMES = ["llama-server.exe", "llama-server"]

    def __init__(self, config_path: str = "", search_dirs: list[str] | None = None):
        """初始化解析器

        Args:
            config_path: 用户在配置中指定的 llama.cpp 目录（可为空）
            search_dirs: 额外的搜索目录列表
        """
        self._config_path = config_path
        self._search_dirs = search_dirs or []

    def resolve(self) -> str:
        """查找 llama-server 可执行文件

        Returns:
            llama-server 的完整路径（在 llama.cpp 目录下）

        Raises:
            FileNotFoundError: 所有搜索路径均未找到
        """
        # 优先级 1：配置中指定的 llama.cpp 目录
        if self._config_path and os.path.isdir(self._config_path):
            result = self._find_in_dir(self._config_path)
            if result:
                return result

        # 优先级 2-3：当前目录和额外搜索目录
        search_dirs = [os.getcwd()] + self._search_dirs
        bin_dirs = []
        for d in search_dirs:
            bin_subdir = os.path.join(d, "bin")
            if os.path.isdir(bin_subdir):
                bin_dirs.append(bin_subdir)

        all_dirs = search_dirs + bin_dirs
        for directory in all_dirs:
            result = self._find_in_dir(directory)
            if result:
                return result

        # 优先级 4：PATH 环境变量
        for name in self._EXE_NAMES:
            found = shutil.which(name)
            if found:
                return found

        # 给出有意义的错误信息
        if self._config_path and not os.path.isdir(self._config_path):
            raise FileNotFoundError(
                f"llama.cpp 目录不存在: {self._config_path}\n"
                f"请在设置中指定正确的 llama.cpp 目录"
            )
        raise FileNotFoundError(
            "llama-server.exe 未找到，请在设置中指定 llama.cpp 所在目录"
        )

    def _find_in_dir(self, directory: str) -> str | None:
        """在指定目录中搜索 llama-server"""
        for name in self._EXE_NAMES:
            full_path = os.path.join(directory, name)
            if os.path.isfile(full_path):
                return full_path
        return None
