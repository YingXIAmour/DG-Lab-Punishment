import http.server
import socketserver
import time
import threading
import json
import os
import sys
import queue
# 日志级别常量
LOG_SUCCESS = "SUCCESS"
LOG_INFO = "INFO"
LOG_WARNING = "WARNING"
LOG_ERROR = "ERROR"
base_dir = ""
class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global base_dir
        if self.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            template = os.path.join(base_dir, "template")
            # 读取 index.html 文件内容并发送
            with open(template + '/index1.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/channel_strength':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()

            template = os.path.join(base_dir, "template")
            # 读取 index.html 文件内容并发送
            with open(template + '/channel_strength.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/channel_strength_1':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()

            template = os.path.join(base_dir, "template")
            # 读取 index.html 文件内容并发送
            with open(template + '/channel.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/chat':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()

            template = os.path.join(base_dir, "template")
            # 读取 index.html 文件内容并发送
            with open(template + '/chat.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/data':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            # 这里模拟后台逻辑处理，返回当前强度数据
            if self.server.client is None or self.server.client == "":
                strength = {
                    "A":[0,100],
                    "B":[0,100]
                }
            else:
                strength = self.server.client.get_channel_strength()
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
            return_ver = json.dumps({"version": self.server.ver})
            self.wfile.write(return_ver.encode())
        elif self.path == "/config":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

            return_ver = json.dumps(self.server.main_config)
            self.wfile.write(return_ver.encode())
        elif self.path == "/module":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            return_module = json.dumps(list(self.server.imported_modules))
            self.wfile.write(return_module.encode())
        elif self.path == "/log":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(self.server.logger.encode())
        elif self.path == "/active":
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            return_queue = queue.Queue()
            send_data = {
                'action':"active",
                'queue':return_queue
            }
            self.server.message_queue.put(send_data)
            try:
                return_data = return_queue.get(timeout=2)

                response = json.dumps(return_data)

            except:
                response = json.dumps({"server": "1", "client": "1"})

            self.wfile.write(response.encode())
            #self.wfile.write(self.server.logger.encode())
        elif self.path == "/DG-LAB.ico":
            self.send_response(200)
            self.send_header('Content-type', 'image/x-icon')
            self.end_headers()
            icon_path = os.path.join(base_dir, "template", "DG-LAB.ico")
            if os.path.exists(icon_path):
                with open(icon_path, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                self.send_error(404, "Icon not found")
        elif self.path.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            # 处理图片请求
            image_path = os.path.join(base_dir, "template/img",self.path.lstrip("/"))
            if os.path.exists(image_path):
                # 根据文件扩展名设置 Content-type
                if image_path.endswith('.png'):
                    content_type = 'image/png'
                elif image_path.endswith(('.jpg', '.jpeg')):
                    content_type = 'image/jpeg'
                elif image_path.endswith('.gif'):
                    content_type = 'image/gif'

                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                with open(image_path, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                self.send_error(404, "Image not found")
        elif self.path.endswith(('.css','.js')):
            temp_path = os.path.join(base_dir,"template",self.path.lstrip("/"))
            if os.path.exists(temp_path):
                if temp_path.endswith(".css"):
                    content_type = 'text/css'
                elif temp_path.endswith('.js'):
                    content_type = 'text/javascript'
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                with open(temp_path, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                self.send_error(404, "Css or js not found")
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')

        if self.path == "/client":
            # 处理 /client 路径的 POST 请求
            post_params = json.loads(post_data)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            return_queue = queue.Queue()
            post_params['queue'] = return_queue
            self.server.message_queue.put(post_params)
            try:
                return_data = return_queue.get(timeout=2)

                response = json.dumps({"code": return_data['code'], "message": return_data['message']})

            except:
                response = json.dumps({"code": 404, "message": "与服务器通信超时"})

            self.wfile.write(response.encode())

        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        # 重写 log_message 方法，使其不输出访问记录
        pass


class HTTPServerModule:
    def __init__(self, tmp_client, data,message_queue):
        global base_dir
        self.client = tmp_client
        base_dir = data["base_dir"]
        self.imported_modules = data["module"]
        self.ver = data['ver']
        self.main_config = data['config']
        self.PORT = 8000
        self.httpd = None
        self.server_event = threading.Event()
        self.server_thread = None
        self.message_queue = message_queue

    def run_server(self):
        self.httpd = socketserver.TCPServer(("", self.PORT), MyHandler)
        self.httpd.message_queue = self.message_queue
        self.httpd.client = self.client
        self.httpd.main_config = self.main_config
        self.httpd.imported_modules = self.imported_modules
        self.httpd.ver = self.ver
        self.httpd.logger = ""
        send_data = {
            'action':"logger",
            'log_level':LOG_SUCCESS,
            "message":"HTTP 服务器已于8000端口启动"
        }
        self.message_queue.put(send_data)
        self.server_event.set()  # 标记服务器已启动
        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    def update(self,tmp_client = "",module = "",logger = ""):#
        if tmp_client != "":
            self.client = tmp_client
            self.httpd.client = self.client
        if module != "":
            self.imported_modules = module
        if logger != "":
            self.httpd.logger = logger

    def start(self):
        self.server_thread = threading.Thread(target=self.run_server)
        self.server_thread.start()

    def stop_server(self):
        self.server_event.wait()  # 等待服务器启动
        if self.httpd:
            self.httpd.shutdown()


if __name__ == "__main__":
    # 模拟客户端和数据
    tmp_client = None
    data = {
        "base_dir": ".",
        "module": {},
        "ver": "1.0"
    }
    server_module = HTTPServerModule(tmp_client, data)
    server_module.start()
    time.sleep(5)  # 等待服务器启动，可根据实际情况调整时间
    server_module.stop_server()
