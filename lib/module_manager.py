import os
import json
import importlib.util
import threading
import asyncio
from typing import Dict, Optional, Any, List
from .logger import Logger

LOG_SUCCESS = "SUCCESS"
LOG_INFO = "INFO"
LOG_WARNING = "WARNING"
LOG_ERROR = "ERROR"
LOG_DEBUG = "DEBUG"

class ModuleManager:
    def __init__(self, config_manager, message_queue):
        self.config_manager = config_manager  # 使用配置管理器
        self.imported_modules: Dict[str, Any] = {}
        self.start_data: Dict[str, Any] = {}
        self.thread_all: Dict[str, Optional[threading.Thread]] = {}
        self.client_message_queue = message_queue
        self.logger = Logger(config_manager.config)
        # 从配置管理器获取start_data
        self.start_data = self.config_manager.start_data

    def import_modules(self):
        """导入所有模块（仅保留导入逻辑）"""
        function_file = os.path.join(self.config_manager.base_dir, "plugins")

        # 遍历目录下的所有模块文件
        for root, dirs, files in os.walk(function_file):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    module_name = file[:-3]
                    module_path = os.path.join(root, file)

                    try:
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        if spec:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)

                            if hasattr(module, 'main') and callable(module.main):
                                self.imported_modules[module_name] = module
                                self.log(LOG_SUCCESS,f"成功导入模块 {module_name}")
                            else:
                                self.log(LOG_WARNING,"模块 {module_name} 无main函数")
                        else:
                            self.log(LOG_WARNING,f"无法创建模块规范: {module_name}")

                    except Exception as e:
                        self.log(LOG_ERROR,f"导入模块 {module_name} 失败: {str(e)}")

    def get_imported_modules(self) -> Dict[str, Any]:
        """获取已导入的模块"""
        return self.imported_modules

    def start_module_in_thread(self, module_name: str):
        """在单独的线程中启动模块"""
        module = self.imported_modules[module_name]

        def target():
            if hasattr(module, 'main'):
                main_func = getattr(module, 'main')
                if asyncio.iscoroutinefunction(main_func):
                    async def async_target():
                        await main_func(self.client_message_queue, self.start_data[module_name])

                    asyncio.run(async_target())
                else:
                    main_func(self.client_message_queue, self.start_data[module_name])
            else:
                self.log(LOG_WARNING, f"模块 {module.__name__} 没有启动函数！")

        self.thread_all[module_name] = threading.Thread(target=target)
        self.thread_all[module_name].start()

    def stop_module_in_thread(self, module_name: str):
        """停止在单独线程中运行的模块"""
        module = self.imported_modules[module_name]

        if hasattr(module, 'stop'):
            stop_func = getattr(module, 'stop')
            if asyncio.iscoroutinefunction(stop_func):
                async def async_target():
                    await stop_func()

                asyncio.run(async_target())
            else:
                stop_func()
        else:
            self.log(LOG_WARNING, f"模块 {module.__name__} 没有关闭函数！")

        if self.thread_all[module_name] is not None:
            self.thread_all[module_name].join(0.5)
            self.thread_all[module_name] = None

    def log(self, level: str, msg: str):
        """记录日志"""
        self.logger.log(level, msg)