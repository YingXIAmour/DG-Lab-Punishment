import http.server
import socketserver
import time
import threading
import json
import os
import sys
from main import strength_heartbeat


class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global base_dir
        if self.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            template = os.path.join(base_dir, "template")
            # 读取 index.html 文件内容并发送
            with open(template + '/index.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/channel_strength':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            template = os.path.join(base_dir, "template")
            # 读取 index.html 文件内容并发送
            with open(template + '/channel_strength.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/data':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            # 这里模拟后台逻辑处理，返回当前强度数据
            strength = client.get_channel_strength()
            current_strength = {
                'a_channel': strength['A'][0],
                'a_channel_max': strength['A'][1],
                'b_channel': strength['B'][0],
                'b_channel_max': strength['B'][1]
            }
            current_strength = json.dumps(current_strength)
            self.wfile.write(current_strength.encode())
        elif self.path == "/version":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            return_ver = json.dumps({"version":ver})
            self.wfile.write(return_ver.encode())
        elif self.path == "/module":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            return_module = json.dumps(list(imported_modules))
            self.wfile.write(return_module.encode())
    def log_message(self, format, *args):
        # 重写 log_message 方法，使其不输出访问记录
        pass


client = None
base_dir = None
server_event = threading.Event()
imported_modules = dict()
ver = None
def run_server(tmp_client,data):
    global client,imported_modules,ver,base_dir
    global server_event
    PORT = 8000
    client = tmp_client
    base_dir = data["base_dir"]
    imported_modules = data["module"]
    ver = data['ver']
    httpd = socketserver.TCPServer(("", PORT), MyHandler)
    print(f"HTTP 服务器已于 {PORT} 端口启动")
    server_event.set()  # 标记服务器已启动
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def stop_server():
    global server_event
    server_event.wait()  # 等待服务器启动
    httpd = server_event.httpd  # 假设 httpd 存储在 server_event 中，实际可能需要修改
    httpd.shutdown()


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    time.sleep(5)  # 等待服务器启动，可根据实际情况调整时间
    stop_server()