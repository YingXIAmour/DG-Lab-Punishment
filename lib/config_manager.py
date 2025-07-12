import os
import json
import logging
from typing import Dict, Any, Optional


class ConfigManager:
    def __init__(self, base_dir: str):
        """初始化配置管理器"""
        self.base_dir = base_dir
        self.config: Dict[str, Any] = {
            "server_ip": "",
            "server_port": 1145,
            "serverMode": "",
            "clientMode": "",
            "base_dir": base_dir,
            "listening_channel_strength": ""
        }
        self.strength: Dict[str, Any] = {}
        self.start_data: Dict[str, Any] = {}
        self.logger = logging.getLogger("ConfigManager")

    def get_config_file_path(self) -> str:
        """获取配置文件路径"""
        return os.path.join(self.base_dir, "data", "config.json")

    def load_config(self, file_path: Optional[str] = None) -> bool:
        """
        加载配置文件

        Args:
            file_path: 配置文件路径，默认为 None 时使用默认路径

        Returns:
            加载成功返回 True，否则返回 False
        """
        if file_path is None:
            file_path = self.get_config_file_path()

        if not os.path.exists(file_path):
            self._create_default_config(file_path)
            self.logger.info(f"创建默认配置文件: {file_path}")

        try:
            with open(file_path, 'r') as file:
                data = json.load(file)

            # 解析服务器配置
            server_conf = data.get('conf', {}).get('server',{})
            self.config['server_ip'] = server_conf.get('ip', '') or self._get_local_ip()
            self.config["server_port"] = server_conf.get('port', 1145)
            self.config["serverMode"] = server_conf.get('mode', "n-n")

            # 解析客户端配置
            self.config["clientMode"] = data.get('conf', {}).get('client', {}).get('mode', "n-n")

            # 解析强度配置
            conf_data = data.get('conf', {})
            self.strength = conf_data.get("strength", {})

            # 解析插件配置
            self.start_data = data.get('plugins', {})
            self.logger.info("配置文件加载成功")
            return True

        except json.JSONDecodeError:
            self.logger.error("解析配置文件出错")
            return False
        except Exception as e:
            self.logger.error(f"加载配置文件时出错: {e}")
            return False

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新配置文件

        Args:
            new_config: 包含新配置的字典，应包含 server_ip, serverMode, clientMode 等字段

        Returns:
            更新成功返回 True，否则返回 False
        """
        try:
            # 先加载现有配置
            if not self.load_config():
                self.logger.error("加载现有配置失败，无法更新")
                return False

            # 合并新配置
            self.config['server_ip'] = new_config.get('server_ip', self.config['server_ip'])
            self.config["serverMode"] = new_config.get('serverMode', self.config["serverMode"])
            self.config["clientMode"] = new_config.get('clientMode', self.config["clientMode"])

            # 构建写入数据
            data_to_write = {
                'server': {
                    'ip': self.config['server_ip'],
                    'port': self.config["server_port"],
                    'mode': self.config["serverMode"]
                },
                'client': {
                    'mode': self.config["clientMode"]
                },
                'conf': {
                    "strengthAdd": self.strength_add
                },
                'plugins': self.start_data
            }

            # 写入文件
            file_path = self.get_config_file_path()
            with open(file_path, 'w') as file:
                json.dump(data_to_write, file, indent=4)

            self.logger.info("配置文件更新成功")
            return True

        except Exception as e:
            self.logger.error(f"更新配置文件时出错: {e}")
            return False

    def _create_default_config(self, file_path: str) -> None:
        """创建默认配置文件"""
        default_config = {
            'server': {
                'ip': self._get_local_ip(),
                'port': 1145,
                'mode': 'n-n'
            },
            'client': {
                'mode': 'n-n'
            },
            'conf': {
                "strengthAdd": {'A': [0, 10], 'B': [0, 10]}
            },
            'plugins': {}
        }
        with open(file_path, 'w') as file:
            json.dump(default_config, file, indent=4)

    def _get_local_ip(self) -> str:
        """获取本地IP地址"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"