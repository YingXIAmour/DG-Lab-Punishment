import subprocess
import time
import http_server
import importlib.util
import platform
import os
import sys
import json
import webbrowser
import threading
import asyncio
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from datetime import datetime
from wsdglab import ws_server, ws_client
from gui import channel_sus_gui,function_gui
from function import csgo_dglab, keyboard_listen
from threading import Thread
from typing import Optional
# 版本信息
ver = "V2.0.0"
#图形化窗口
root = None
channel_gui = None
function_gui_root = None
#配置
conf = {
    "server_ip":"",
    "server_port":1145,
    "serverMode":"",
    "clientMode":"",
    "base_dir":"",
    "listening_channel_strength":""
}
client = None
http_server_ao = None
#获取导入的模块
imported_modules = dict()
#线程
thread_all: dict[str, Optional[Thread]] = {
    'server':None,
    'client':None,
    'channel_windows':None,
    'channel_windows_count':None,
    'function_windows':None,
    'strength_add':None
}
# 模块初始化数据
start_data = dict()

error_count = 0
# 获取当前APP终端强度及强度软上限
strengthApp = {
    'A':[0,100],
    'B':[0,100]
}
# 强度递增变量
strengthAdd = {
    'A':[0,10],
    'B':[0,10]
}
ico_file_path = ""
# 日志
def log(msg):
    message = "[{}] {}".format(datetime.now().strftime('%H:%M:%S'),msg)
    print(message)
# 底层模块导入
def import_modules_from_directory(directory):
    temp_imported_modules = dict()
    for temp_root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                module_name = file[:-3]  # 去掉.py 后缀得到模块名
                module_path = os.path.join(temp_root, file)
                try:
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    if spec:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        temp_imported_modules.update({module_name:module})
                except Exception as e:  # 捕获所有可能的异常
                    log(f"加载模块出错 {module_path}: {e}")
    return temp_imported_modules
#加载配置文件
def load_config(file_path):
    global strengthAdd,conf,start_data
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            file_content = file.read()
            try:
                data  = json.loads(file_content)
                conf['server_ip'] = data['server']['ip'] if data['server']['ip'] != '' else ws_server.get_local_ip()
                conf["server_port"] = data['server']['port'] if data['server']['port'] != '' else 1145
                strengthAdd = data['conf']["strengthAdd"]
                conf["serverMode"] = data['server']['mode'] if data['server']['mode'] != "" else "n-n"
                conf["clientMode"] = data['client']['mode'] if data['client']['mode'] != "" else "n-n"
                conf["listening_channel_strength"] = data['conf']["listening_channel_strength"]
                for module in imported_modules.keys():
                    temp = data['function'].get(module)
                    start_data.update({module:temp})
                return True
            except json.JSONDecodeError:
                log(f"解析配置文件出错")
                return False

#启动服务端
def start_server(ip,port,mode):
    # 使用 asyncio.run() 来运行主协程
    try:
        asyncio.run(ws_server.main(ip, port, mode))
    except KeyboardInterrupt:
        # 在这里可以添加进一步的清理资源、关闭进程等操作
        ws_server.stop = True
        ws_server.log("用户手动关闭服务器，服务器已关闭")
        return
#启动客户端
def start_client():
    global client
    client_ws = root.nametowidget('client_ws')
    uri = "ws://{}:1145".format(ws_client.get_local_ip()) if client_ws.get() == "" else client_ws.get()
    client = ws_client.WebSocketClient(uri, conf['clientMode'])
    client.start_receive_thread()
    if conf['listening_channel_strength'] == "Windows":
        start_channel_gui_in_thread()
    time.sleep(1)
    strength_heartbeat()
#启动通道强度显示GUI
def create_channel_gui():
    global channel_gui
    channel_gui = channel_sus_gui.ChannelWindows(ico_file_path)
    channel_gui.start()
# 打开功能GUI
def start_function_gui():
    global function_gui_root
    send_data = {
        "modules":imported_modules,
        "thread_all":thread_all,
        "start_data":start_data
    }
    function_gui_root = function_gui.GUI()
    function_gui_root.client = client
    function_gui_root.modules = send_data['modules']
    function_gui_root.thread_all = send_data['thread_all']
    function_gui_root.start_data = send_data['start_data']
    function_gui_root.create_gui()

#开始监听
def listing_strength():
    global strengthApp
    while True:
        try:
            strengthApp = client.get_channel_strength()
            channel_gui.update_progress("A", strengthApp['A'][0], strengthApp['A'][1])
            channel_gui.update_progress("B", strengthApp['B'][0], strengthApp['B'][1])
        except:
            break
        time.sleep(1)

def start_http_server():
    global http_server_ao
    start_data_http = {
        "module":imported_modules.keys(),
        "ver":ver,
        "base_dir":conf["base_dir"]
    }
    http_server_ao = http_server.run_server(client,start_data_http)

def strength_heartbeat():
    global thread_all
    if conf['listening_channel_strength'] == "Windows":
        thread_all['channel_windows_count'] = threading.Thread(target=listing_strength)
        thread_all['channel_windows_count'].start()
    elif conf['listening_channel_strength'] == "HTTP":
        thread_all['channel_windows_count'] = threading.Thread(target=start_http_server())
        thread_all['channel_windows_count'].start()
    else:
        messagebox.showerror("错误","强度实时监测模式错误，已关闭实时监测")
        return
#启动线程
def start_server_threading(ip = 'localhost',port = 1145,mode = 'n-n'):
    """服务端"""
    global thread_all
    ws_server.stop = False
    thread_all['server'] = threading.Thread(target=start_server,args=(ip,port,mode))
    thread_all['server'].start()

    btn_start_server = root.nametowidget('start_server_btn')
    btn_close_server = root.nametowidget('close_server_btn')
    btn_start_server.grid_forget()
    btn_close_server.grid(row=1, column=0)
def start_client_in_thread():
    """客户端"""
    global thread_all
    thread_all['client'] = threading.Thread(target=start_client)
    thread_all['client'].start()
    btn = root.nametowidget('start_client_btn')
    client_ws = root.nametowidget('client_ws')
    btn_close_client = root.nametowidget('close_client_btn')
    btn.grid_forget()
    btn_close_client.grid(row=2, column=0)
    client_ws.config(state=tk.DISABLED)
def start_function_gui_in_thread():
    """功能页面"""
    global thread_all
    if client is None:
        messagebox.showerror("错误","客户端未启动")
        return
    elif thread_all['function_windows'] is not None:
        if function_gui_root.get_is_hidden():
            function_gui_root.show_window()
            return
    else:
        thread_all['function_windows'] = threading.Thread(target=start_function_gui)
        thread_all['function_windows'].start()
def start_strength_add_in_thread():
    global thread_all

    thread_all['strength_add'] = threading.Thread(target=strength_add)
    thread_all['strength_add'].start()
def start_channel_gui_in_thread():
    global thread_all
    thread_all['channel_windows'] = threading.Thread(target=create_channel_gui)
    thread_all['channel_windows'].start()
def strength_add():
    messagebox.showwarning("提示","该功能暂未开发")
    return
    # btn_start = root.nametowidget('start_strength_add')
    # btn_stop = root.nametowidget('stop_strength_add')

#设置强度
def set_strength(data):
    if client is not None:
        strength_A = data.get('A') if data.get('A').strip() != '' or data.get('A') is not None else '0'
        send_data_A = {
            'type': 3,
            'message': 'set channel',
            'channel': 'A',
            'strength': int(strength_A),
            'clientId': '' if conf["clientMode"] == "n-n" else "All",
            'targetId': '' if conf["clientMode"] == "n-n" else "Test"
        }

        client.handle_message(send_data_A)

        strength_B = data.get('B') if data.get('B') != '' or data.get('B') is not None else '0'
        send_data_B = {
            'type': 3,
            'message': 'set channel',
            'channel': 'B',
            'strength': int(strength_B),
            'clientId': '' if conf["clientMode"] == "n-n" else "All",
            'targetId': '' if conf["clientMode"] == "n-n" else "Test"
        }
        client.handle_message(send_data_B)
    else:
        messagebox.showwarning("错误","客户端未启动！")
        return
def initialization():
    """
    程序初始化
    :return:
    """
    global conf,imported_modules,thread_all,ico_file_path,modules_name
    #获取程序运行目录
    if getattr(sys, 'frozen', False):
        conf["base_dir"] = os.path.dirname(sys.executable)
    else:
        conf["base_dir"] = os.path.dirname(os.path.abspath(__file__))
    # 开始导入function下模块
    function_file = os.path.join(conf["base_dir"],"function")
    imported_modules = import_modules_from_directory(function_file)
    # 获取配置文件
    conf_file_path = os.path.join(conf["base_dir"], "data", "config.json")
    load_config(conf_file_path)
    # 加载图标文件
    ico_file_path = os.path.join(conf["base_dir"], "data", "DG-LAB.ico")
    # 功能模块配置文件目录
    conf_file = os.path.join(conf["base_dir"],"conf")
    for modules_name,module in imported_modules.items():
        module.base_dir = os.path.join(conf_file,modules_name)
        thread_all.update({modules_name:None})


def install_module():
    log("已安装模块如下：")
    for module_name,module in imported_modules.items():
        log("{} 模块，作者：{}".format(module_name,module.author))
#启动GUI
def start_server_and_gui():
    global  root,error_count,conf
    root = tk.Tk()

    root.title("郊狼惩罚姬")

    # 设置窗口图标，注意图标文件路径要正确，这里假设图标文件和脚本在同一目录下
    root.iconbitmap(ico_file_path)
    root.geometry("800x400")
    root.resizable(False, False)

    def show_image():
        system = platform.system()
        image_path = "data/qrcode.png"
        qrcode_path = os.path.join(conf["base_dir"],image_path)
        if client is not None:
            client.save_qrcode(qrcode_path)
        else:
            messagebox.showwarning("错误","客户端未启动！")
            return
        try:
            if system == "Windows":
                # 在Windows上使用默认图片查看器打开图片，这里使用start命令
                subprocess.run(['start', '', image_path], shell=True)
            elif system == "Linux":
                # 在Linux上常见的使用xdg-open来调用默认应用打开图片
                subprocess.run(['xdg-open', image_path])
            elif system == "Darwin":
                # 在macOS上使用open命令调用默认应用打开图片
                subprocess.run(['open', image_path])
            else:
                print(f"不支持的操作系统: {system}")
        except FileNotFoundError:
            print("图片文件未找到，请检查路径是否正确。")

    def get_strength_text():
        data = {
            'A':strength_A.get(),
            'B':strength_B.get()
        }
        return data
    def thread_close(close_type):
        global thread_all,error_count,client,channel_gui
        # 客户端如果在运行关闭客户端
        if thread_all["client"] is not None and close_type == 'Client':
            try:
                asyncio.run(client.close())
            except RuntimeError:
                error_count += 1
            thread_all["client"].join(0.5)
            thread_all['client'] = None
            btn_close_client.grid_forget()
            btn.grid(row=2, column=0)
            client_ws.config(state=tk.NORMAL)
            client = None

        # 服务端如果在运行关闭服务端
        if thread_all["server"] is not None and close_type == 'Server':
            ws_server.stop = True
            thread_all["server"].join(0.5)
            thread_all['server'] = None
            btn_close_server.grid_forget()
            btn_start_server.grid(row=1, column=0)
    # 创建强度调整框架
    frame = tk.Frame(root,bd=4,relief=tk.RIDGE)
    frame.grid(row=1, column=1, rowspan=3,columnspan=2,padx=10, pady=10, sticky="nsew")
    frame.config(bg="lightblue")
    my_font = tkfont.Font(size=12)
    # 创建功能页面标签
    label = tk.Label(root, text="郊狼惩罚姬\nV2.0",font=my_font)
    #创建客户端连接信息标签
    label_client_font = tkfont.Font(size=10)
    label_client = tk.Label(root,text="客户端连接地址：",font=label_client_font)
    # 创建文本输入框
    client_ws = tk.Entry(root,name='client_ws')
    # 创建启动服务端按钮&关闭服务端按钮并调整大小
    btn_start_server = tk.Button(root, text="启动服务端", command=lambda: start_server_threading(conf['server_ip'],conf["server_port"],conf["serverMode"]), width=20, height=1,name='start_server_btn')
    btn_close_server = tk.Button(root, text="关闭服务端",
                                 command=lambda: thread_close('Server'), width=20, height=1,
                                 name='close_server_btn')
    # 创建启动客户端按钮并调整大小
    btn = tk.Button(root, text="启动客户端", command=start_client_in_thread, width=20, height=1,name='start_client_btn')
    btn_close_client = tk.Button(root, text="关闭客户端", command=lambda: thread_close('Client'), width=20, height=1,
                    name='close_client_btn')
    # 创建按键监听启动按钮
    btn_module_install = tk.Button(root, text="检查已安装模块",
                                       width=20, height=1,command=install_module)
    # 创建显示二维码连接图片按钮并调整大小
    btn_image_button = tk.Button(root, text="显示二维码", command=show_image, width=20, height=1)
    # 创建打开配置按钮并调整大小
    btn_start_function_gui = tk.Button(root, text="功能面板", width=20, height=1,command=start_function_gui_in_thread)
    # 创建打开波形生成器按钮并调整大小
    btn_start_wave_data_gui = tk.Button(root, text="待更新", width=20, height=1)
    # 创建作者标签并放在底部居中
    writer = tk.Label(root, text="By 影曦Amout")
    # 创建超链接标签并放在底部居中
    link_label = tk.Label(root, text="Github", fg="blue", cursor="hand2")
    # 创建监听输入框 - 日志
    text_widget = tk.Text(root,width=45, height=100)
    # 创建强度累增框架
    frame_add = tk.Frame(root, bd=4, relief=tk.RIDGE)
    frame_add.grid(row=4, column=1, rowspan=3, columnspan=2, padx=10, pady=10, sticky="nsew")
    frame_add.config(bg="lightblue")
    # 创建框架内容
    text_add = tk.Label(frame_add,text="强度累加机",bg="lightblue")
    text_add_A = tk.Label(frame_add,text="通道A累加值：",bg="lightblue")
    text_add_A_count = tk.Label(frame_add,text="循环秒数：",bg="lightblue")
    text_add_B = tk.Label(frame_add, text="通道B累加值：",bg="lightblue")
    text_add_B_count = tk.Label(frame_add, text="循环秒数：",bg="lightblue")
    label_add_A = tk.Entry(frame_add, width=8)
    label_add_B = tk.Entry(frame_add, width=8)
    label_add_A_count = tk.Entry(frame_add, width=4)
    label_add_B_count = tk.Entry(frame_add, width=4)
    button_add_start = tk.Button(frame_add,text="启动强度累加机",width=16,height=1,name="start_strength_add",command=start_strength_add_in_thread)
    button_add_start.config(state=tk.DISABLED)
    button_add_stop = tk.Button(frame_add, text="关闭强度累加机", width=16, height=1, name="stop_strength_add")
    button_add_set = tk.Button(frame_add,text="更新累加值",width=16,height=1)
    button_add_set.config(state=tk.DISABLED)
    # 框架UI构建
    text_add.grid(row=0,column=1,columnspan=2)

    text_add_A.grid(row=1,column=0)
    label_add_A.grid(row=1,column=1)
    text_add_A_count.grid(row=1,column=2)
    label_add_A_count.grid(row=1,column=3)

    text_add_B.grid(row=2, column=0)
    label_add_B.grid(row=2, column=1)
    text_add_B_count.grid(row=2, column=2)
    label_add_B_count.grid(row=2, column=3)

    button_add_start.grid(row=3,column=0,columnspan=2)
    button_add_set.grid(row=3,column=2,columnspan=2)
    # 创建强度A值输入框
    strength_A = tk.Entry(frame)
    # 创建强度B值输入框
    strength_B = tk.Entry(frame)
    # 创建强度值设定按钮
    btn_set_strength = tk.Button(frame, text="设置初始强度", command=lambda: set_strength(get_strength_text()), width=32, height=1)
    # 创建标签
    strength_label = tk.Label(frame,text="郊狼通道强度值设置",bg="lightblue")
    strength_A_label = tk.Label(frame,text="通道A强度值：",bg="lightblue")
    strength_B_label = tk.Label(frame,text="通道B强度值：",bg="lightblue")
    #界面UI
    label.grid(row=0, column=0, sticky='nw')

    label_client.grid(row=0, column=1)
    client_ws.grid(row=0, column=2)

    btn_start_server.grid(row=1, column=0)
    #btn_close_server.grid(row=1, column=0)

    btn.grid(row=2, column=0)
    #btn_close_client.grid(row=2, column=0)

    btn_module_install.grid(row=3, column=0)
    #btn_keyboard_listening_stop.grid(row=3,column=0)

    btn_image_button.grid(row=4, column=0)
    btn_start_function_gui.grid(row=5, column=0)
    btn_start_wave_data_gui.grid(row=6, column=0)
    writer.grid(row=10, column=0, columnspan=2, sticky='sw')
    link_label.grid(row=10, column=2, sticky='se')
    link_label.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/YingXIAmout/DG-Lab-Punishment"))

    strength_label.grid(row=0,column=0,columnspan=2)
    strength_A_label.grid(row=1,column=0)
    strength_B_label.grid(row=2,column=0)
    strength_A.grid(row=1, column=1)
    strength_B.grid(row=2, column=1)
    frame.grid_columnconfigure(1,weight=1)

    btn_set_strength.grid(row=3, column=0,columnspan=2)
    #text_widget_text.grid(row=0,column=3)
    text_widget.grid(row=0, column=3, rowspan=11)
    # 设置行和列的权重，使按钮在窗口大小变化时能自动调整位置并保持居中
    for i in range(9):
        root.grid_rowconfigure(i, weight=1)
    for j in range(5):
        root.grid_columnconfigure(j, weight=1)

    root.protocol("WM_DELETE_WINDOW", on_close_window)  # 绑定窗口关闭事件处理函数

    console_redirector = ConsoleRedirector(text_widget)
    sys.stdout = console_redirector
    root.mainloop()

#窗口关闭操作
def on_close_window():
    global thread_all,error_count
    # 销毁窗口
    if root:
        root.destroy()
    sys.stdout = None
    for thread in thread_all.copy().keys():
        if thread_all[thread] is not None:
            if thread == "channel_windows_count":
                if conf['listening_channel_strength'] == "HTTP":
                    http_server_ao.stop_server()
            thread_all[thread].join(0.1)
            thread_all[thread] = None
    os._exit(0)


class ConsoleRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.insert(tk.END,string)
        self.text_widget.see(tk.END)  # 自动滚动到最新内容处
if __name__ == "__main__":
    # 程序初始化
    initialization()
    try:
        start_server_and_gui()
    except KeyboardInterrupt:
        log("程序被用户手动中断，正在进行清理操作...")
        # 在这里可以添加进一步的清理资源、关闭进程等操作
        if root:
            root.destroy()