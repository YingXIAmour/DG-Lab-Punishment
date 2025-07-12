import asyncio
import websockets
import threading
import time
import json
import socket
from datetime import datetime
import traceback

# 从本地导入ws_qrcode，若无法导入则使用简单的二维码生成函数
try:
    from wsdglab import ws_qrcode
except ImportError:
    class ws_qrcode:
        @staticmethod
        def generate_qrcode(data):
            print(f"生成二维码数据: {data}")
            return None

mode_type = ['n-n', 'n-1', '1-n']


class WebSocketClient:
    def __init__(self, inputuri, inputmode, message_queue=None):
        self.uri = inputuri
        self.websocket = None
        self.mode = inputmode
        self.feedback = {
            'A': 0,
            'B': 0
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
            self.channel = dict()

        self.channel = {
            'A': [0, 100],
            'B': [0, 100]
        }
        # 存储二维码
        self.img = None
        self.thread = None
        asyncio.set_event_loop(self.loop)
        self.close_event = asyncio.Event()  # 使用 asyncio.Event 作为关闭标志
        self.message_queue = message_queue
        self.running = True  # 添加运行标志
        self.auto_reconnect = False  # 禁用自动重连
        self.break_received = False  # 标记是否收到break消息
        self.all_tasks = set()  # 跟踪所有异步任务
        self.is_receiving = False  # 标记是否正在接收消息
        self._lock = asyncio.Lock()  # 用于同步关键操作的锁
        self._reconnecting = False  # 标记是否正在重连

        # 新增：待连接状态标志
        self.pending_connection = False

        # 存储最近的clientId，用于重连后恢复绑定
        self._last_client_id = None

    def run_coroutine_safely(self, coro):
        """安全地在事件循环线程中运行协程"""
        if not self.loop or self.loop.is_closed():
            self.log("事件循环已关闭，无法运行协程")
            return asyncio.Future()  # 返回一个已完成的future

        # 总是使用call_soon_threadsafe，避免直接调用run_until_complete
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future

    def close_safely(self):
        """安全地关闭客户端（从任何线程调用）"""
        if not self.running:
            self.log("客户端已经关闭")
            return

        future = self.run_coroutine_safely(self.close())

        try:
            # 等待关闭操作完成，设置合理的超时时间
            future.result(timeout=5)  # 等待最多5秒
            self.log("客户端已安全关闭")
        except asyncio.TimeoutError:
            self.log("关闭操作超时，客户端可能未完全关闭")
        except Exception as e:
            self.log(f"关闭客户端时出错: {e}")

    async def close(self):
        """安全关闭客户端"""
        async with self._lock:
            if not self.running:
                self.log("客户端已经关闭")
                return

            self.log("开始关闭客户端...")
            self.running = False
            self.close_event.set()  # 设置关闭标志
            self.pending_connection = False  # 重置待连接状态

            # 取消所有跟踪的任务，但保留接收任务最后取消
            tasks_to_cancel = [task for task in self.all_tasks if task.get_name() != "receive_messages"]
            for task in tasks_to_cancel:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=1)
                    except Exception as e:
                        self.log(f"取消任务时出错: {e}")

            # 向服务器发送关闭通知
            if self.websocket and not self.is_websocket_closed():
                try:
                    close_msg = {
                        'type': 'close',
                        'clientId': self._last_client_id or '',
                        'message': 'Client shutting down',
                        'timestamp': int(time.time() * 1000)  # 添加时间戳确保消息唯一性
                    }

                    for attempt in range(3):
                        try:
                            await asyncio.wait_for(self.websocket.send(json.dumps(close_msg)), timeout=1)
                            self.log("已向服务器发送关闭通知")

                            # 等待服务器确认（新增逻辑）
                            try:
                                response = await asyncio.wait_for(self.websocket.recv(), timeout=2)
                                response_data = json.loads(response)
                                if response_data.get('type') == 'close_ack' and response_data.get(
                                        'clientId') == self._last_client_id:
                                    self.log("收到服务器关闭确认")
                                    break
                            except asyncio.TimeoutError:
                                self.log("未收到服务器关闭确认，继续尝试发送关闭通知")
                        except Exception as e:
                            self.log(f"发送关闭通知尝试 {attempt + 1}/3 失败: {e}")
                            if attempt == 2:
                                self.log("发送关闭通知失败，将强制关闭连接")
                except Exception as e:
                    self.log(f"发送关闭通知时出错: {e}")

            # 取消接收消息任务
            if self.receive_task and not self.receive_task.done():
                self.receive_task.cancel()
                try:
                    await asyncio.wait_for(self.receive_task, timeout=2)
                except Exception as e:
                    self.log(f"取消接收任务时出错: {e}")

            # 关闭websocket连接
            if self.websocket:
                try:
                    if not self.is_websocket_closed():
                        # 增加超时处理，避免长时间等待
                        await asyncio.wait_for(
                            self.websocket.close(code=1000, reason='Client shutdown'),
                            timeout=2
                        )
                        self.log("WebSocket连接已关闭")
                    else:
                        self.log("WebSocket连接已经关闭")
                except Exception as e:
                    self.log(f"关闭WebSocket连接时出错: {e}")

            # 停止并关闭事件循环
            await self._stop_and_close_event_loop()

            self.log('客户端已完全关闭')

    async def _cancel_all_tasks(self):
        """取消所有跟踪的异步任务"""
        if not self.all_tasks:
            self.log("没有需要取消的任务")
            return

        self.log(f"正在取消 {len(self.all_tasks)} 个任务...")
        for task in list(self.all_tasks):
            if not task.done():
                try:
                    task.cancel()
                    # 等待任务完成取消
                    await asyncio.wait_for(task, timeout=1)
                except asyncio.TimeoutError:
                    self.log(f"任务取消超时: {task.get_name()}")
                except asyncio.CancelledError:
                    self.log(f"任务已取消: {task.get_name()}")
                except Exception as e:
                    self.log(f"取消任务时出错: {e}")

        # 清除任务列表
        self.all_tasks.clear()

    async def _stop_and_close_event_loop(self):
        """安全地停止和关闭事件循环"""
        if not self.loop or self.loop.is_closed():
            self.log("事件循环已经关闭")
            return

        # 创建事件用于同步
        loop_stopped = threading.Event()

        # 定义在事件循环中执行的回调
        def stop_loop_and_notify():
            try:
                # 停止事件循环
                if self.loop.is_running():
                    # 检查是否还有任务在运行
                    tasks = asyncio.all_tasks(loop=self.loop)
                    active_tasks = [t for t in tasks if not t.done()]

                    if active_tasks:
                        self.log(f"发现 {len(active_tasks)} 个未完成的任务，正在取消...")
                        for task in active_tasks:
                            task.cancel()

                    self.loop.stop()
                    self.log("事件循环已停止")
                else:
                    self.log("事件循环未运行")
            finally:
                # 通知主线程事件循环已停止
                loop_stopped.set()

        # 在事件循环中安排回调执行
        self.loop.call_soon_threadsafe(stop_loop_and_notify)

        # 等待事件循环停止，最多等待5秒
        loop_stopped.wait(timeout=5)

        # 再次检查事件循环状态
        if self.loop.is_running():
            self.log("事件循环仍在运行，尝试强制终止...")
            # 再次尝试停止事件循环
            self.loop.call_soon_threadsafe(stop_loop_and_notify)
            # 再等待2秒
            loop_stopped.wait(timeout=2)

            if self.loop.is_running():
                self.log("无法安全停止事件循环，设置线程为守护模式")
                if self.thread and self.thread.is_alive():
                    self.thread.daemon = True
            else:
                self.log("事件循环已停止")
        else:
            self.log("事件循环已停止")

        # 关闭事件循环
        if not self.loop.is_closed():
            try:
                self.loop.close()
                self.log("事件循环已关闭")
            except Exception as e:
                self.log(f"关闭事件循环时出错: {e}")
        else:
            self.log("事件循环已关闭")

    def is_websocket_closed(self):
        """检查WebSocket连接是否已关闭，处理不同版本库的兼容性问题"""
        if not self.websocket:
            return True

        try:
            # 优先使用标准的closed属性
            if hasattr(self.websocket, 'closed'):
                return self.websocket.closed

            # 检查低版本库的_connection属性
            if hasattr(self.websocket, '_connection') and hasattr(self.websocket._connection, 'closed'):
                return self.websocket._connection.closed

            # 检查legacy属性
            if hasattr(self.websocket, 'state') and self.websocket.state == websockets.protocol.State.CLOSED:
                return True

        except Exception:
            return True

        return False

    def save_qrcode(self, file_path):
        """
        生成二维码
        :param file_path:绝对路径
        :return:
        """
        if self.img:
            try:
                self.img.save(file_path)
                return True
            except Exception as e:
                self.log(f"保存二维码时出错: {e}")
        return False

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
            self.log(f"接收消息线程出现异常: {e}\n{traceback.format_exc()}")
        finally:
            self.log("接收消息线程已退出")

    def start_receive_thread(self):
        self.thread = threading.Thread(target=self._receive_messages_helper, daemon=False)
        self.thread.start()
        self.log("客户端正在连接：{}".format(self.uri))

    async def ensure_receiving(self):
        """确保有一个活跃的接收任务"""
        async with self._lock:
            if not self.is_receiving and self.websocket and not self.is_websocket_closed() and self.running:
                self.log("启动新的接收任务")
                self.receive_task = asyncio.create_task(self.receive_messages())
                self.receive_task.set_name("receive_messages")
                self.all_tasks.add(self.receive_task)
                self.is_receiving = True

    async def receive_messages(self):
        """接收并处理来自服务器的消息"""
        self.is_receiving = True

        task = asyncio.current_task()
        if task:
            task.set_name("receive_messages")
            self.all_tasks.add(task)

        self.log("开始接收消息...")

        while self.running and not self.close_event.is_set():
            try:
                # 确保在任何时候只有一个接收任务在运行
                if task != self.receive_task:
                    self.log("检测到其他接收任务正在运行，退出当前接收任务")
                    break

                # 接受信息，设置较短的超时时间以便快速响应关闭请求
                async with self._lock:
                    if not self.websocket or self.is_websocket_closed():
                        self.log("WebSocket连接已关闭，退出接收任务")
                        break

                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1)

                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    self.log("收到非JSON格式消息")
                    continue

                msg_type = data.get('type')
                if msg_type == 'bind' and data.get('targetId') == '':
                    if self.mode == "1-n":
                        self.clientId = data.get('clientId')
                    else:
                        self.clients['clientId'] = data.get('clientId')
                    # 保存最近的clientId用于重连
                    self._last_client_id = data.get('clientId')
                    qr_data = f"https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#{self.uri}/{data.get('clientId')}"
                    self.img = ws_qrcode.generate_qrcode(qr_data)
                    self.log("二维码已创建")
                    self.pending_connection = True  # 设置为待连接状态
                elif msg_type == 'bind' and data.get('targetId') != '':
                    if self.mode == "1-n":
                        count = len(self.targetId) + 1
                        self.targetId[count] = data.get('targetId')
                    else:
                        self.clients['targetId'] = data.get('targetId')
                    self.bind = True
                    self.pending_connection = False  # 连接成功，取消待连接状态
                    self.log(f"APP已连接，targetId: {data.get('targetId')}")
                elif msg_type == 'msg' and 'strength' in data.get('message'):
                    try:
                        if self.mode == mode_type[0]:
                            strength = data.get('message')
                            strength = strength.split('-')[1].split('+')
                            self.channel['A'] = [int(strength[0]), int(strength[2])]
                            self.channel['B'] = [int(strength[1]), int(strength[3])]
                        elif self.mode == mode_type[1]:
                            strength = data.get('message')
                            strength = strength.split('-')[1].split('+')
                            target_id = data.get("targetId")
                            if target_id not in self.channel:
                                self.channel[target_id] = {'A': [0, 100], 'B': [0, 100]}
                            self.channel[target_id]['A'] = [int(strength[0]), int(strength[2])]
                            self.channel[target_id]['B'] = [int(strength[1]), int(strength[3])]
                    except (IndexError, ValueError) as e:
                        self.log(f"解析强度消息时出错: {e}")
                elif msg_type == "msg" and "feedback" in data.get("message"):
                    try:
                        temp = data.get("message")
                        temp_channel_mode = int(temp.split("-")[1])
                        if temp_channel_mode in [0, 1, 2, 3, 4]:
                            self.feedback['A'] = temp_channel_mode
                        elif temp_channel_mode in [5, 6, 7, 8, 9]:
                            self.feedback['B'] = temp_channel_mode - 5
                    except (IndexError, ValueError) as e:
                        self.log(f"解析反馈消息时出错: {e}")
                elif msg_type == 'heartbeat':
                    self.log('收到心跳包')
                elif msg_type == 'break':
                    self.log(f"收到断开通知: {data.get('message')}")
                    if self.mode == "n-n":
                        self.clients['targetId'] = ''
                    elif self.mode == "1-n":
                        target_id = data.get('targetId')
                        for key, tid in list(self.targetId.items()):
                            if tid == target_id:
                                self.targetId.pop(key)
                    self.bind = False
                    self.break_received = True  # 设置break标志
                    self.pending_connection = True  # 设置为待连接状态
                    self.log("保持待连接状态，等待新的APP连接...")
                    # 不自动重连，保持连接等待新的APP连接
                elif msg_type == 'close':
                    self.log("接收到关闭指令，正在关闭...")
                    await self.close()
                    return
                else:
                    self.log(f"收到未知类型消息: {msg_type}")
            except asyncio.TimeoutError:
                # 超时继续循环，检查关闭标志
                continue
            except websockets.exceptions.ConnectionClosedOK:
                self.log("与服务端的WebSocket连接已正常关闭")
                break
            except websockets.exceptions.ConnectionClosedError:
                self.log("与服务端的WebSocket连接异常关闭")
                break
            except websockets.exceptions.ConcurrencyError:
                self.log("检测到并发接收消息，退出当前接收任务")
                break
            except asyncio.CancelledError:
                self.log("接收消息任务已取消")
                break
            except Exception as e:
                self.log(f"接收消息出现异常: {e}\n{traceback.format_exc()}")
                break

        self.log("接收消息循环已退出")
        self.is_receiving = False

        # 从任务列表中移除自己
        if task and task in self.all_tasks:
            self.all_tasks.remove(task)

        # 如果这是主接收任务，重置引用
        if task == self.receive_task:
            self.receive_task = None

        # 只有在连接意外关闭时才尝试重新连接
        if self.running and not self.close_event.is_set() and not self.pending_connection:
            self.log("接收任务退出，尝试重新连接...")
            asyncio.create_task(self.reconnect())

    async def _handle_connection_loss(self):
        """处理连接丢失，但不自动重连"""
        self.channel = {
            'A': [0, 100],
            'B': [0, 100]
        }
        self.bind = False
        # 不自动重连，等待break消息触发

    async def reconnect(self):
        """尝试重新连接到服务器并重建绑定关系"""
        async with self._lock:
            if not self.running or self.close_event.is_set():
                return False

            # 设置重连标志，防止重复重连
            self._reconnecting = True

            task = asyncio.current_task()
            if task:
                task.set_name("reconnect")
                self.all_tasks.add(task)

            consecutive_failures = 0
            max_consecutive_failures = 5

            self.log("开始尝试重新连接...")

            # 保存当前的clientId（可能需要重新绑定）
            current_client_id = self._last_client_id

            # 确保现有连接已关闭
            if self.websocket and not self.is_websocket_closed():
                try:
                    self.log("关闭现有WebSocket连接...")
                    await self.websocket.close(code=1000, reason='Reconnecting')
                except Exception as e:
                    self.log(f"关闭现有连接时出错: {e}")

            # 取消当前接收任务（如果存在）
            if self.receive_task and not self.receive_task.done():
                self.log("取消当前接收任务...")
                self.receive_task.cancel()
                try:
                    await asyncio.wait_for(self.receive_task, timeout=2)
                except asyncio.TimeoutError:
                    self.log("接收任务取消超时")
                except Exception as e:
                    self.log(f"等待接收任务取消时出错: {e}")
                finally:
                    self.receive_task = None

            self.is_receiving = False
            # 重置绑定状态（服务器可能已清除绑定关系）
            self.bind = False
            self.clients['targetId'] = ''
            if self.mode == "1-n":
                self.targetId.clear()

            while self.running and not self.close_event.is_set():
                try:
                    self.log(f"尝试连接到 {self.uri}...")
                    self.websocket = await websockets.connect(self.uri)
                    self.log("重新连接成功")

                    # 启动新的接收任务
                    await self.ensure_receiving()

                    # 重新连接后需要重新绑定
                    if current_client_id:
                        self.log(f"尝试使用clientId {current_client_id} 重新绑定到服务器...")
                        # 发送绑定请求
                        bind_data = {
                            "type": "bind",
                            "clientId": current_client_id,
                            "targetId": "",  # 留空让服务器分配或重新绑定
                            "message": "reconnect"
                        }
                        await self.websocket.send(json.dumps(bind_data))
                    else:
                        self.log("等待服务器发送新的绑定信息...")

                    # 重置重连标志
                    self._reconnecting = False

                    return True
                except (websockets.exceptions.ConnectionClosedError, OSError) as e:
                    consecutive_failures += 1
                    self.log(f"连接失败 ({consecutive_failures}/{max_consecutive_failures}): {e}")
                    if consecutive_failures >= max_consecutive_failures:
                        self.log('重连次数上限，程序退出')
                        # 重置重连标志
                        self._reconnecting = False
                        return False
                    await asyncio.sleep(2)  # 等待2秒后重试
                except Exception as e:
                    consecutive_failures += 1
                    self.log(f"连接异常 ({consecutive_failures}/{max_consecutive_failures}): {e}")
                    if consecutive_failures >= max_consecutive_failures:
                        self.log('重连次数上限，程序退出')
                        # 重置重连标志
                        self._reconnecting = False
                        return False
                    await asyncio.sleep(2)  # 等待2秒后重试

            # 重置重连标志
            self._reconnecting = False

            # 从任务列表中移除自己
            if task and task in self.all_tasks:
                self.all_tasks.remove(task)

            return False

    async def connect_and_receive(self):
        """连接到服务器并开始接收消息"""
        task = asyncio.current_task()
        if task:
            task.set_name("connect_and_receive")
            self.all_tasks.add(task)

        try:
            self.log(f"尝试连接到WebSocket服务器: {self.uri}")
            self.websocket = await websockets.connect(self.uri)
            self.log("已连接到服务端，开始接收消息...")

            # 启动接收消息任务
            await self.ensure_receiving()

            # 等待接收任务完成（可能由于连接关闭或其他原因）
            if self.receive_task:
                await self.receive_task
        except websockets.exceptions.ConnectionClosedError:
            self.log("初始连接失败，尝试重新连接...")
            await self.reconnect()
        except Exception as e:
            self.log(f"初始连接出现异常: {e}\n{traceback.format_exc()}")
            if not self.close_event.is_set():
                await self.reconnect()
        finally:
            # 从任务列表中移除自己
            if task and task in self.all_tasks:
                self.all_tasks.remove(task)

    def log(self, msg):
        """日志记录函数"""
        message = f'Client: {msg}'
        if self.message_queue:
            try:
                self.message_queue.put({
                    'action': 'logger',
                    'log_level': 'INFO',
                    'message': message
                })
            except Exception:
                pass  # 消息队列可能不可用

    def send_message(self, message):
        try:
            asyncio.run_coroutine_threadsafe(self.websocket.send(message), self.loop).result()
        except websockets.ConnectionClosedError:
            self.log("与服务端的连接已关闭，无法发送消息")
            if not self.pending_connection:  # 只有在非待连接状态下才尝试重连
                self.log("尝试重新连接...")
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
            if self.pending_connection:
                self.log("处于待连接状态，等待新的APP连接...")
            else:
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
                if self.pending_connection:
                    self.log("处于待连接状态，等待新的APP连接...")
                else:
                    self.log('参数不全，可能是未连接到 app 终端或未提交该参数!')
                return
            elif send_data_l['channel'] not in self.channel:
                self.log('无该通道')
                return
            if send_data_l.get('strength') is not None and send_data_l['type'] in [1, 2, 3]:
                new_strength = send_data_l['strength'] + self.channel[send_data_l['channel']][0] if send_data_l[
                                                                                                        'type'] == 3 else \
                send_data_l['strength']
                if send_data_l['strength'] > self.channel[send_data_l['channel']][1] or new_strength > \
                        self.channel[send_data_l['channel']][1]:
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

    def add_or_reduce_strength(self, channel, strength, option):
        """
        强度增加/降低
        :param option:
        :param channel:
        :param strength:
        :return:
        """
        if self.bind is False:
            if self.pending_connection:
                self.log("处于待连接状态，等待新的APP连接...")
            else:
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
            if new_strength > self.channel[channel][1]:
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

    def set_strength(self, channel, strength, send_client="All", percent=True):
        """
        设置强度
        :param channel:通道
        :param strength:强度or百分比
        :return:
        """
        if self.bind is False:
            if self.pending_connection:
                self.log("处于待连接状态，等待新的APP连接...")
            else:
                self.log("APP未连接")
            return
        if channel not in self.channel:
            self.log('无该通道')
            return
        send_data = {
            'type': 3,
            'clientId': "",
            'targetId': "",
            'message': "set channel",
            'channel': 1 if channel == "A" else 2,
            'strength': strength,  # if percent is not True else self.channel[send_client][channel]*strength,
            'mode': send_client
        }
        if self.mode == "n-n":
            send_data['clientId'] = self.clients['clientId']
            send_data['targetId'] = self.clients['targetId']
        elif self.mode == "1-n":
            send_data['clientId'] = self.clientId

        if strength > self.channel[channel][1]:
            self.log("超出APP软终端上线！")
            return
        self.send_message(json.dumps(send_data))
        return

    def send_pluses_message(self, pluses, punish_time, channel="All"):
        """
        :param punish_time: 惩罚时间
        :param channel:通道
        :param pluses: 波形（转义后的）
        :return:
        """
        if self.bind is False:
            if self.pending_connection:
                self.log("处于待连接状态，等待新的APP连接...")
            else:
                self.log("APP未连接")
            return
        send_data = {
            'type': "clientMsg",
            'clientId': "",
            'targetId': "",
            'message': "{}:{}",
            'time': punish_time,
            "channel": ""
        }
        if self.mode == "n-n":
            send_data['clientId'] = self.clients['clientId']
            send_data['targetId'] = self.clients['targetId']
        elif self.mode == "1-n":
            send_data['clientId'] = self.clientId
        if channel == "All":
            send_data['channel'] = "A"
            send_data["message"] = "{}:{}".format("A", pluses)
            self.send_message(json.dumps(send_data))
            send_data['channel'] = "B"
            send_data["message"] = "{}:{}".format("B", pluses)
            self.send_message(json.dumps(send_data))
        else:
            send_data["message"] = "{}:{}".format(channel, pluses)
            self.send_message(json.dumps(send_data))
        return

    def get_bind(self):
        return self.bind


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


# 主函数示例
if __name__ == "__main__":
    def get_local_ip():
        """获取本地IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            print(f"获取本地IP失败: {e}")
            return "127.0.0.1"


    uri = "ws://{}:1145".format(get_local_ip())
    print(f"连接到WebSocket服务器: {uri}")
    client = WebSocketClient(uri, "n-n")
    client.start_receive_thread()

    try:
        while True:
            time.sleep(1)  # 主线程持续运行
    except KeyboardInterrupt:
        print("\n用户中断，正在关闭客户端...")
        # 使用安全关闭方法
        client.close_safely()
        # 等待事件循环线程结束
        if client.thread and client.thread.is_alive():
            client.thread.join(timeout=5)
            if client.thread.is_alive():
                print("事件循环线程未在超时时间内结束，将强制退出")
        print("客户端已关闭")