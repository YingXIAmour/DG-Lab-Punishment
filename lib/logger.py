import os
import datetime
from typing import Dict


class Logger:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = ""
        # 日志级别常量
        self.LOG_SUCCESS = "SUCCESS"
        self.LOG_INFO = "INFO"
        self.LOG_WARNING = "WARNING"
        self.LOG_ERROR = "ERROR"
        self.LOG_DEBUG = "DEBUG"
        # 颜色常量
        self.COLOR_GREEN = "\033[32m"
        self.COLOR_WHITE = "\033[37m"
        self.COLOR_YELLOW = "\033[33m"
        self.COLOR_RED = "\033[31m"
        self.COLOR_RESET = "\033[0m"

    def log(self, level: str, msg: str):
        """记录日志并输出到控制台"""
        # 获取当前时间并格式化为绿色
        time_str = f"{self.COLOR_GREEN}{datetime.datetime.now().strftime('%H:%M:%S')}{self.COLOR_RESET}"

        # 根据日志级别设置颜色
        if level == self.LOG_SUCCESS:
            level_str = f"{self.COLOR_GREEN}{level}{self.COLOR_RESET}"
        elif level == self.LOG_INFO:
            level_str = f"{self.COLOR_WHITE}{level}{self.COLOR_RESET}"
        elif level == self.LOG_WARNING:
            level_str = f"{self.COLOR_YELLOW}{level}{self.COLOR_RESET}"
        elif level == self.LOG_ERROR:
            level_str = f"{self.COLOR_RED}{level}{self.COLOR_RESET}"
        elif level == self.LOG_DEBUG:
            level_str = f"{self.COLOR_YELLOW}{level}{self.COLOR_YELLOW}"
        else:
            level_str = level  # 未知级别不设置颜色

        # 消息统一使用白色
        msg_str = f"{self.COLOR_WHITE}{msg}{self.COLOR_RESET}"

        # 构建完整消息
        message = f"[{time_str}] [{level_str}] {msg_str}"
        message_log = "[{}] [{}] {}".format(datetime.datetime.now().strftime('%H:%M:%S'), level, msg)

        # 写入内存日志
        self.logger += message_log + "\n"

        # 打印到控制台
        print(message)

        # 如果初始化完成，写入日志文件
        if self.config['base_dir'] != "":
            file_p = f"log-{datetime.datetime.now().strftime('%Y-%m-%d')}.txt"
            file_path = os.path.join(self.config['base_dir'], "log\\", file_p)

            # 确保日志文件存在
            if not os.path.exists(file_path):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('')

            # 尝试读取现有日志
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_logs = f.read()
            except UnicodeDecodeError:
                # 如果UTF-8解码失败，尝试其他编码
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        existing_logs = f.read()
                except:
                    # 如果还是失败，清空文件
                    existing_logs = ''

            # 写入新日志
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(existing_logs + message_log + "\n")

    def get_logger_content(self) -> str:
        """获取日志内容"""
        return self.logger