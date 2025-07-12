import asyncio
import os
import sys
import time
from typing import Optional
import http_server
import threading
import queue
import atexit
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from lib.module_manager import ModuleManager
from lib.config_manager import ConfigManager
from lib.logger import Logger
import json
from wsdglab import ws_server,ws_client,ws_qrcode

# 版本信息
ver = "V3.0"
init = False
# 程序运行标志
running = True
# 配置
conf = {
    "server_ip": "",
    "server_port": 1145,
    "serverMode": "",
    "clientMode": "",
    "base_dir": "",
    "listening_channel_strength": ""
}
server = None
client = None
http_server_ao = None
# 线程
thread_all: dict[str, Optional[threading.Thread]] = {
    'server': None,
    'client': None,
    'http_server': None,
    'receive': None,
    'receive_client': None,
    'http_logger_update':None
}
# 获取当前APP终端强度及强度软上限
strengthApp = {
    'App_A': [0, 100],
    'App_B': [0, 100],
    'A': [0, 100],
    'B': [0, 100]
}
# 强度递增变量
strengthAdd = {
    'A': [0, 10],
    'B': [0, 10]
}
ico_file_path = ""
# 日志级别常量
LOG_SUCCESS = "SUCCESS"
LOG_INFO = "INFO"
LOG_WARNING = "WARNING"
LOG_ERROR = "ERROR"
LOG_DEBUG = "DEBUG"
# 颜色常量
COLOR_GREEN = "\033[32m"
COLOR_WHITE = "\033[37m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_RESET = "\033[0m"

message_queue = None
client_message_queue = None
library_manager = None
module_manager = None
logger = None

def start_server(ip, port, mode):
    global server
    # 使用 asyncio.run() 来运行主协程
    server = ws_server.WebSocketServer(host=ws_server.get_local_ip(), port=1145, mode="n-n",
                                       message_queue=message_queue)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        # 在这里可以添加进一步的清理资源、关闭进程等操作
        ws_server.stop = True
        ws_server.log("用户手动关闭服务器，服务器已关闭")
        return


def start_client():
    global client
    if thread_all['server'] is not None:
        uri = "ws://{}:1145".format(ws_client.get_local_ip())
    elif thread_all['server'] is None:
        uri = "ws://dglab.yingxiya.com:1145"
    else:
        uri = "ws://{}:1145".format(ws_client.get_local_ip())
    client = ws_client.WebSocketClient(uri, config_manager.config["clientMode"], message_queue)
    http_server_ao.update(tmp_client=client)
    client.start_receive_thread()
    time.sleep(1)
    client.save_qrcode(file_path=os.path.join(config_manager.base_dir,"template","img","qrcode.png"))
def stop_client_safely():
    """安全地关闭客户端"""
    global client
    if client and hasattr(client, 'close_safely'):
        try:
            client.close_safely(timeout=5)
            logger.log(LOG_INFO,"客户端已安全关闭")
        except Exception as e:
            logger.log(LOG_ERROR,f"关闭客户端时出错: {e}")
    else:
        logger.log(LOG_INFO,"客户端未运行或已关闭")
# 启动http服务器
def start_http_server():
    global http_server_ao
    start_data_http = {
        "module": module_manager.get_imported_modules().keys(),
        "ver": ver,
        "base_dir": config_manager.base_dir,  # 使用配置管理器的base_dir
        "config": config_manager.config  # 使用配置管理器的config
    }
    http_server_ao = http_server.HTTPServerModule(client, start_data_http, message_queue)
    http_server_ao.start()


# 启动线程
def start_server_threading(ip=ws_server.get_local_ip(), port=1145, mode='n-n'):
    """服务端"""
    thread_all['server'] = threading.Thread(target=start_server, args=(ip, port, mode))
    thread_all['server'].start()


def start_client_in_thread():
    """客户端"""
    thread_all['client'] = threading.Thread(target=start_client)
    thread_all['client'].start()


# 定义循环接收消息的函数--和客户端通信
def receive_client_messages():
    while True:
        try:
            # 从消息队列中获取消息，设置超时时间为 1 秒
            message = client_message_queue.get(timeout=1)
            try:
                # 尝试将 JSON 字符串解析为 Python 对象
                data = message

                if data['action'] == "strength_add":  # 强度增加
                    client.add_or_reduce_strength(data['channel'], data['strength'], "ADD")
                    logger.log(LOG_INFO, "通道{}，强度增加：{}".format(data['channel'], data['strength']))
                elif data['action'] == "strength_down":  # 强度减少
                    client.add_or_reduce_strength(data['channel'], data['strength'], "REDUCE")
                    logger.log(LOG_INFO, "通道{}，强度减少：{}".format(data['channel'], data['strength']))
                elif data['action'] == "set_strength":  # 设置强度
                    client.set_strength(data['channel'], data['strength'])
                    logger.log(LOG_INFO, "通道{}，强度设置为{}".format(data['channel'], data['strength']))
                elif data['action'] == "send_pluses":  # 发送波形
                    client.send_pluses_message(data['pluses'], data['punish_time'], data['channel'])
                    logger.log(LOG_INFO, "通道：{}，发送波形，惩罚时间：{}".format(data['channel'], data['punish_time']))
                elif data['action'] == "get_strength":
                    data['queue'].put(client.get_channel_strength())
                elif data['action'] == "logger":
                    logger.log(data['log_level'], data['message'])
                else:
                    continue
            except Exception as e:
                logger.log(LOG_WARNING, f"异常消息: {message}")
            # 标记消息处理完成
            client_message_queue.task_done()
        except queue.Empty:
            # 若队列为空，继续等待
            continue


# 定义循环接收消息的函数
def receive_messages():
    global client,server
    while True:
        try:
            # 从消息队列中获取消息，设置超时时间为 1 秒
            message = message_queue.get(timeout=1)
            try:
                # 尝试将 JSON 字符串解析为 Python 对象
                data = message
                send_data = {
                    'code': 100,
                    'message': ""
                }
                # 在这里可以根据解析后的数据进行具体的处理逻辑
                # 重载主程序配置文件
                if data['action'] == "reload_main_config":
                    # 调用配置管理器的load_config
                    conf_file_path = config_manager.get_config_file_path()
                    config_manager.load_config(conf_file_path)
                    logger.log(LOG_SUCCESS, "重载配置文件成功")
                    send_data['code'] = 200
                    send_data['message'] = "成功！"
                    data['queue'].put(json.dumps(send_data))
                elif data['action'] == "set_main_config":
                    # 调用配置管理器的update_config
                    conf_file_path = config_manager.get_config_file_path()
                    new_config_data = {
                        "serverMode": data['serverMode'],
                        'clientMode': data['clientMode'],
                        'server_ip': data['server_ip']
                    }
                    config_manager.update_config(new_config_data)
                    logger.log(LOG_SUCCESS, "更新配置文件成功")
                    config_manager.load_config(conf_file_path)
                    send_data['code'] = 200
                    send_data['message'] = "成功！"
                    data['queue'].put(send_data)
                elif data['action'] == "active":
                    send_data = {
                        'server': "",
                        'client': "",
                        'app_client':""
                    }
                    if server is not None:
                        send_data['server'] = "running"
                    if client is not None:
                        send_data['client'] = "running"
                        if client.get_bind() is True:
                            send_data['app_client'] = "true"
                    data['queue'].put(send_data)
                # 日志
                elif data['action'] == "logger":
                    logger.log(data['log_level'], data['message'])
                # 启动模块
                elif data['action'] == "start_module":
                    if client is not None:
                        module_name = data['module_name']
                        module_manager.start_module_in_thread(module_name)
                        send_data['code'] = 200
                        send_data['message'] = "启动成功！"
                    else:
                        send_data['code'] = 400
                        send_data['message'] = "客户端未启动"
                    data['queue'].put(send_data)
                # 关闭模块
                elif data['action'] == "stop_module":
                    if client is not None:
                        module_name = data['module_name']
                        module_manager.stop_module_in_thread(module_name)
                        send_data['code'] = 200
                        send_data['message'] = "关闭成功！"
                    else:
                        send_data['code'] = 400
                        send_data['message'] = "客户端未启动"
                    data['queue'].put(send_data)
                # 服务器-启动 or 关闭
                elif data['action'] == "server":
                    if data['saso'] == "start":
                        if server is None:
                            start_server_threading()
                            send_data['code'] = 200
                            send_data['message'] = "启动成功！"
                        else:
                            send_data['code'] = 400
                            send_data['message'] = "服务器已启动"
                        data['queue'].put(send_data)
                    elif data['saso'] == "stop":
                        if server is not None:
                            try:
                                asyncio.run(server.stop())
                            except Exception as e:
                                logger.log(LOG_WARNING,f"服务端关闭异常")

                            thread_all["server"].join(0.5)
                            thread_all['server'] = None
                            server = None
                            send_data['code'] = 200
                            send_data['message'] = "关闭成功！"
                        else:
                            send_data['code'] = 400
                            send_data['message'] = "服务端未启动"
                        data['queue'].put(send_data)
                # 客户端- 开启 or 关闭
                elif data['action'] == "client":
                    if data['saso'] == "start":
                        if client is None:
                            start_client_in_thread()
                            send_data['code'] = 200
                            send_data['message'] = "启动成功！"
                        else:
                            send_data['code'] = 400
                            send_data['message'] = "服务器已启动"
                        data['queue'].put(send_data)
                    elif data['saso'] == "stop":
                        if client is not None:
                            try:
                                client.close_safely()
                            except Exception as e:
                                logger.log(LOG_WARNING,f"客户端关闭异常")

                            thread_all["client"].join(0.5)
                            thread_all['client'] = None
                            client = None
                            send_data['code'] = 200
                            send_data['message'] = "关闭成功！"
                        else:
                            send_data['code'] = 400
                            send_data['message'] = "服务端未启动"
                        data['queue'].put(send_data)
                else:
                    continue
            except Exception as e:
                logger.log(LOG_WARNING, f"异常消息: {message}")
            # 标记消息处理完成
            message_queue.task_done()
        except queue.Empty:
            # 若队列为空，继续等待
            continue


def initialization():
    """程序初始化"""
    global conf, ico_file_path,message_queue,client_message_queue,library_manager,module_manager,logger,config_manager,server
    # 获取程序运行目录
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # 创建必要的目录
    for dir_name in ["lib", "data", "conf", "temp", "log"]:
        dir_path = os.path.join(base_dir, dir_name)
        os.makedirs(dir_path, exist_ok=True)

    message_queue = queue.Queue()
    client_message_queue = queue.Queue()

    # 初始化配置管理器
    config_manager = ConfigManager(base_dir)
    # 加载配置
    conf_file_path = config_manager.get_config_file_path()
    config_manager.load_config(conf_file_path)

    # 初始化模块管理器
    module_manager = ModuleManager(config_manager, client_message_queue)
    logger = Logger(config_manager.config)

    # 导入模块
    logger.log(LOG_INFO, "开始导入模块...")
    module_manager.import_modules()

    # 加载图标文件
    ico_file_path = os.path.join(base_dir, "data", "DG-LAB.ico")

    # 功能模块配置文件目录
    conf_file = os.path.join(base_dir, "conf")
    for modules_name, module in module_manager.get_imported_modules().items():
        module.base_dir = os.path.join(conf_file, modules_name)
        thread_all.update({modules_name: None})

    # 启动接收消息队列
    thread_all["receive"] = threading.Thread(target=receive_messages)
    thread_all["receive"].start()
    thread_all["receive_client"] = threading.Thread(target=receive_client_messages)
    thread_all["receive_client"].start()

    # 启动http监听
    start_http_server()
    time.sleep(0.05)
    thread_all["http_logger_update"] = threading.Thread(target=http_logger_update)
    thread_all["http_logger_update"].start()


    # 注册程序退出清理函数
    atexit.register(cleanup)

def create_window():
    app = QApplication(sys.argv)

    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("郊狼惩罚姬")
    window.resize(1024, 768)

    # 设置图标
    if os.name == 'nt' and os.path.exists(ico_file_path):
        from PyQt5.QtGui import QIcon
        window.setWindowIcon(QIcon(ico_file_path))

    # 创建浏览器视图
    browser = QWebEngineView()
    browser.load(QUrl("http://127.0.0.1:8000"))
    window.setCentralWidget(browser)

    # 关闭事件处理
    def on_closing():
        logger.log(LOG_INFO, "窗口关闭事件触发，开始清理...")
        cleanup()
        sys.exit()

    window.show()
    app.aboutToQuit.connect(on_closing)
    sys.exit(app.exec_())

def cleanup():
    """程序清理函数，用于关闭所有线程和资源"""
    global running
    if not running:
        return

    running = False
    logger.log(LOG_INFO, "程序开始清理资源...")

    # 停止所有模块
    for module_name in module_manager.get_imported_modules().keys():
        if module_name in thread_all and thread_all[module_name] is not None:
            try:
                module_manager.stop_module_in_thread(module_name)
            except Exception as e:
                logger.log(LOG_WARNING, f"停止模块 {module_name} 时出错: {e}")

    # 停止客户端线程
    if thread_all['client'] is not None and client is not None:
        try:
            # 使用线程安全的方式在客户端的事件循环中执行关闭操作
            client.running = False  # 标记客户端停止运行

            # 创建一个事件用于等待关闭完成
            close_event = threading.Event()

            def close_client_in_loop():
                try:
                    # 在客户端的事件循环中执行关闭操作
                    future = asyncio.run_coroutine_threadsafe(client.close(), client.loop)
                    future.result()  # 等待关闭完成
                except Exception as e:
                    logger.log(LOG_WARNING, f"关闭客户端时出错: {e}")
                finally:
                    close_event.set()  # 标记关闭完成

            # 在客户端的事件循环中调度关闭操作
            client.loop.call_soon_threadsafe(close_client_in_loop)

            # 等待关闭完成，设置超时
            close_event.wait(timeout=2.0)

            # 等待客户端线程结束（守护线程会自动终止）
            logger.log(LOG_INFO, "客户端已停止")
        except Exception as e:
            logger.log(LOG_WARNING, f"停止客户端线程时出错: {e}")

    # 停止服务器线程
    if thread_all['server'] is not None:
        try:
            ws_server.stop = True
            thread_all['server'].join(1.0)
        except Exception as e:
            logger.log(LOG_WARNING, f"停止服务器线程时出错: {e}")

    # 停止HTTP服务器
    if http_server_ao is not None:
        try:
            http_server_ao.stop_server()
        except Exception as e:
            logger.log(LOG_WARNING, f"停止HTTP服务器时出错: {e}")

    # 等待消息队列处理完成（手动实现带超时的等待）
    def wait_for_queue(queue_obj, timeout):
        """带超时的队列等待实现"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if queue_obj.unfinished_tasks == 0:
                return True
            time.sleep(0.1)
        return False

    try:
        if not wait_for_queue(message_queue, 1.0):
            logger.log(LOG_WARNING, "消息队列未在超时时间内处理完毕")
        if not wait_for_queue(client_message_queue, 1.0):
            logger.log(LOG_WARNING, "客户端消息队列未在超时时间内处理完毕")
    except Exception as e:
        logger.log(LOG_WARNING, f"等待消息队列处理时出错: {e}")

    # 延迟确保资源释放
    logger.log(LOG_INFO, "等待资源完全释放...")
    for i in range(3, 0, -1):
        logger.log(LOG_INFO, f"倒计时 {i} 秒...")
        time.sleep(1)

    logger.log(LOG_INFO, "资源清理完成，程序退出")
    # 确保所有线程终止
    import os
    os._exit(0)

def http_logger_update():
    while True:
        http_server_ao.update(logger=logger.get_logger_content())
        time.sleep(1)

def hide_console():
    """隐藏 Windows 命令行窗口"""
    if os.name == "nt":  # 仅在 Windows 系统上执行
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # 获取当前窗口句柄
            hwnd = kernel32.GetConsoleWindow()
            if hwnd != 0:
                # 隐藏窗口
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
        except:
            pass  # 忽略错误，避免影响程序运行

if __name__ == "__main__":
    local_version = "1.0"  # 假设的本地版本号
    version_url = "https://example.com/version.json"  # 假设的版本信息 URL
    update_package_url = "https://example.com/update_package.zip"  # 假设的更新包下载 URL

    """try:
        # 调用 update.exe 并传递参数
        subprocess.run([
            "./update.exe",
            "--local-version", local_version,
            "--version-url", version_url,
            "--update-package-url", update_package_url
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"更新检查过程中出错: {e}")"""
    # 程序初始化
    initialization()
    # 隐藏命令行窗口
    hide_console()
    # 创建窗口
    create_window()