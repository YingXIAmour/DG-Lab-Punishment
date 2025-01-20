import asyncio
import websockets
import threading
import time
import json
import socket
from datetime import datetime
import os
import psutil

from wsdglab import ws_qrcode
mode_type = ['n-n','n-1','1-n']
class WebSocketClient:
    def __init__(self, inputuri, inputmode):
        self.uri = inputuri
        self.websocket = None
        self.receive_task = None
        self.mode = inputmode
        self.feedback = {
            'A':0,
            'B':0
        }
        self.loop = asyncio.new_event_loop()
        self.clients = {
            'clientId': '',
            'targetId': ''
        }
        self.bind = False
        if self.mode == "1-n":
            self.clientId = ""
            self.targetId = dict()
        self.channel = {
            'A': [0, 100],
            'B': [0, 100]
        }
        #存储二维码
        self.img = None
        self.thread = None
        asyncio.set_event_loop(self.loop)
        self.close_event = asyncio.Event()  # 使用 asyncio.Event 作为关闭标志

    async def close(self):
        self.uri = None
        self.close_event.set()  # 设置关闭事件
        if self.receive_task:
            self.receive_task.cancel()  # 取消接收任务
        if self.websocket:
            await self.websocket.close()  # 关闭 websocket 连接
        self.loop.stop()  # 停止事件循环
        self.loop.close()
        self.log('数据清除完毕')

    def save_qrcode(self,file_path):
        """
        生成二维码
        :param file_path:绝对路径
        :return:
        """
        try:
            self.img.save(file_path)
        except:
            return False
        return True

    def get_channel_strength(self):
        """
        获取通道强度
        :return:
        """
        return self.channel

    def get_feedback(self):
        """
        获取手机端的FEEDBACK模式
        :return:
        """
        return self.feedback

    def get_target_id(self, uid=""):
        if self.mode == "1-n" and uid in self.targetId:
            return self.targetId[uid]
        elif self.mode == "n-n":
            return self.clients['targetId']
        else:
            return "Error Not targetId"

    def _receive_messages_helper(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.connect_and_receive())
        except Exception as e:
            self.log(f"接收消息线程出现异常: {e}")

    def start_receive_thread(self):
        self.thread = threading.Thread(target=self._receive_messages_helper)
        self.thread.start()
        self.log("客户端正在连接：{}".format(self.uri))

    async def receive_messages(self):
        while not self.close_event.is_set():  # 使用 close_event 作为关闭标志
            try:
                # 接受信息 3s 后超时重新接收
                message = await asyncio.wait_for(self.websocket.recv(), timeout=3)
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                type = data.get('type')
                if type == 'bind' and data.get('targetId') == '':
                    if self.mode == "1-n":
                        self.clientId = data.get('clientId')
                    else:
                        self.clients['clientId'] = data.get('clientId')
                    self.img = ws_qrcode.generate_qrcode(
                        f"https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#{self.uri}/{data.get('clientId')}")
                    self.log("二维码已创建")
                elif type == 'bind' and data.get('targetId')!= '':
                    if self.mode == "1-n":
                        count = len(self.targetId) + 1
                        self.targetId[count] = data.get('targetId')
                    else:
                        self.clients['targetId'] = data.get('targetId')
                        self.log("APP已连接")
                    self.bind = True
                elif type == 'msg' and 'strength' in data.get('message'):
                    strength = data.get('message')
                    strength = strength.split('-')[1].split('+')
                    self.channel['A'] = [int(strength[0]), int(strength[2])]
                    self.channel['B'] = [int(strength[1]), int(strength[3])]
                elif type == "msg" and "feedback" in data.get("message"):
                    temp = data.get("message")
                    temp_channel_mode = int(temp.split("-")[1])
                    if temp_channel_mode in [0,1,2,3,4]:
                        self.feedback['A'] = temp_channel_mode
                    elif temp_channel_mode in [5,6,7,8,9]:
                        self.feedback['B'] = temp_channel_mode - 5
                    else:
                        pass
                elif type == 'heartbeat':
                    self.log('收到心跳包')
                elif type == 'close':
                    self.log("接收到关闭指令，正在关闭...")
                    return False
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed:
                self.log("与服务端的 WebSocket 连接已关闭，尝试重新连接...")
                if await self.reconnect():
                    continue
                else:
                    break
            except asyncio.CancelledError:  # 处理 CancelledError
                self.log("接收消息任务已取消")
                break
            except Exception as e:
                self.log(f"接收消息出现异常: {e}")
                break
        await self.websocket.close()
        return

    async def reconnect(self):
        consecutive_failures = 0
        max_consecutive_failures = 5
        while not self.close_event.is_set():  # 使用 close_event 作为关闭标志
            try:
                self.websocket = await websockets.connect(self.uri)
                self.log("重新连接成功，继续接收消息...")
                return True
            except websockets.exceptions.ConnectionClosedError:
                self.log("无法连接到服务器,正在尝试重新连接...")
                consecutive_failures += 1
                if consecutive_failures == max_consecutive_failures:
                    self.log('重连次数上限，程序退出')
                    return False
            except Exception as e:
                self.log(f"重新连接出现异常: {e}")
                consecutive_failures += 1
                if consecutive_failures == max_consecutive_failures:
                    self.log('重连次数上限，程序退出')
                    return False
        return False

    async def connect_and_receive(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            self.log("已连接到服务端，开始接收消息...")
            self.receive_task = asyncio.create_task(self.receive_messages())
            await self.receive_task
        except websockets.ConnectionClosedError:
            self.log("初始连接失败，尝试重新连接...")
            await self.reconnect()
        except Exception as e:
            self.log(f"初始连接出现其他异常: {e}")
            await self.reconnect()

    def send_message(self, message):
        try:
            asyncio.run_coroutine_threadsafe(self.websocket.send(message), self.loop).result()
        except websockets.ConnectionClosedError:
            self.log("与服务端的连接已关闭，无法发送消息，尝试重新连接...")
            asyncio.run_coroutine_threadsafe(self.reconnect(), self.loop)
        except Exception as e:
            self.log(f"发送消息出现异常: {e}")

    def handle_message(self, data):
        """
        直接提交数据
        :param data:json数据
        :return:
        """
        if self.bind is False:
            self.log("APP未连接")
            return
        try:
            send_data_l = data
            if self.mode == "n-n":
                send_data_l['clientId'] = self.clients['clientId']
                send_data_l['targetId'] = self.clients['targetId']
            elif self.mode == "1-n":
                send_data_l['clientId'] = self.clientId
            if send_data_l['clientId'] == '' or send_data_l['targetId'] == '':
                self.log('参数不全，可能是未连接到 app 终端或未提交该参数!')
                return
            elif send_data_l['channel'] not in self.channel:
                self.log('无该通道')
                return
            if send_data_l.get('strength') is not None and send_data_l['type'] in [1, 2, 3]:
                new_strength = send_data_l['strength'] + self.channel[send_data_l['channel']][0] if send_data_l['type'] == 3 else send_data_l['strength']
                if send_data_l['strength'] > self.channel[send_data_l['channel']][1] or new_strength > self.channel[send_data_l['channel']][1]:
                    self.log('超出 APP 终端软上限！')
                else:
                    if send_data_l['channel'] == 'A':
                        send_data_l['channel'] = 1
                    elif send_data_l['channel'] == 'B':
                        send_data_l['channel'] = 2
                    else:
                        send_data_l['channel'] = 1
                    self.send_message(json.dumps(send_data_l))
                    return
            elif send_data_l['type'] == 'clientMsg':
                self.send_message(json.dumps(send_data_l))
            else:
                self.send_message(json.dumps(send_data_l))
        except json.JSONDecodeError:
            self.log('解析数据出错')
    def add_or_reduce_strength(self,channel,strength,option):
        """
        强度增加/降低
        :param option:
        :param channel:
        :param strength:
        :return:
        """
        if self.bind is False:
            self.log("APP未连接")
            return
        if channel not in self.channel:
            self.log('无该通道')
            return

        send_data = {
            'type': 1 if option == "ADD" else 2,
            'clientId': "",
            'targetId': "",
            'message': "set channel",
            'channel': 1,
            'strength': 0
        }
        if self.mode == "n-n":
            send_data['clientId'] = self.clients['clientId']
            send_data['targetId'] = self.clients['targetId']
        elif self.mode == "1-n":
            send_data['clientId'] = self.clientId

        if channel == 'A':
            send_data['channel'] = 1
        elif channel == 'B':
            send_data['channel'] = 2
        else:
            send_data['channel'] = 1
        if option == "ADD":
            new_strength = strength + self.channel[channel][0]
            if new_strength >> self.channel[channel][1]:
                new_strength = self.channel[channel][1]
        elif option == "REDUCE":
            new_strength = self.channel[channel][0] - strength
            if new_strength < 0:
                new_strength = 0
        else:
            self.log("不存在该操作")
            return
        send_data['strength'] = new_strength
        self.send_message(json.dumps(send_data))
        return
    def set_strength(self,channel,strength):
        """
        设置强度
        :param channel:通道
        :param strength:强度
        :return:
        """
        if self.bind is False:
            self.log("APP未连接")
            return
        if channel not in self.channel:
            self.log('无该通道')
            return
        send_data = {
            'type':3,
            'clientId':"",
            'targetId':"",
            'message':"set channel",
            'channel':1,
            'strength':strength
        }
        if self.mode == "n-n":
            send_data['clientId'] = self.clients['clientId']
            send_data['targetId'] = self.clients['targetId']
        elif self.mode == "1-n":
            send_data['clientId'] = self.clientId

        if channel == 'A':
            send_data['channel'] = 1
        elif channel == 'B':
            send_data['channel'] = 2
        else:
            send_data['channel'] = 1
        if strength >> self.channel[channel][1]:
            self.log("超出APP软终端上线！")
            return

        self.send_message(json.dumps(send_data))
        return
    def send_pluses_message(self,pluses,punish_time,channel = "All"):
        """
        :param punish_time: 惩罚时间
        :param channel:通道
        :param pluses: 波形（转义后的）
        :return:
        """
        if self.bind is False:
            self.log("APP未连接")
            return
        send_data = {
            'type': "clientMsg",
            'clientId': "",
            'targetId': "",
            'message': "{}:{}",
            'time':punish_time
        }
        if self.mode == "n-n":
            send_data['clientId'] = self.clients['clientId']
            send_data['targetId'] = self.clients['targetId']
        elif self.mode == "1-n":
            send_data['clientId'] = self.clientId

        if channel == "All":
            send_data["message"].format("A",pluses)
            self.send_message(send_data)
            send_data["message"].format("B",pluses)
            self.send_message(send_data)
        else:
            send_data["message"].format(channel, pluses)
            self.send_message(send_data)
        return

    @staticmethod
    def log(msg_a):
        message = '[{}] Client: {}'.format(datetime.now().strftime('%H:%M:%S'), msg_a)
        print(message)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception as e:
        print(f"Error occurred: {e}")
        local_ip = None
    return local_ip

if __name__ == "__main__":
    uri = "ws://{}:1145".format(get_local_ip())
    client = WebSocketClient(uri, "n-n")
    client.start_receive_thread()

    # 提升优先级至高优先
    current_process = psutil.Process(os.getpid())
    current_process.nice(psutil.HIGH_PRIORITY_CLASS)
    try:
        while True:
            time.sleep(1)  # 主线程持续运行
    except KeyboardInterrupt:
        asyncio.run_coroutine_threadsafe(client.close(), client.loop)  # 关闭客户端
        client.thread.join()  # 等待线程结束