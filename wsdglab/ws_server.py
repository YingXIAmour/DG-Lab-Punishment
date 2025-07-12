import asyncio
import socket
import websockets
import uuid
import json
import threading
from datetime import datetime
from typing import Dict, Optional, Set, Union

# 服务器核心配置
SERVER_MODES = ['n-n', 'n-1', '1-n']  # 支持的连接模式
DEFAULT_MODE = 'n-n'  # 默认模式
HEARTBEAT_INTERVAL = 30  # 心跳间隔(秒)
PUNISHMENT_DURATION = 5  # 默认惩罚时长(秒)
PULSE_FREQUENCY = 1  # 脉冲消息频率(次/秒)
MAX_SEND_RETRIES = 3  # 最大发送重试次数
SOCKET_TIMEOUT = 2  # 套接字操作超时时间(秒)


class WebSocketServer:
    """WebSocket服务器核心类"""

    def __init__(self, host: str = "127.0.0.1", port: int = 1145, mode: str = DEFAULT_MODE, message_queue=None):
        self.host = host
        self.port = port
        self.mode = mode
        self.message_queue = message_queue
        self.stop_event = asyncio.Event()
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}  # 客户端ID到WebSocket的映射
        self.relations: Dict[str, str] = {}  # n-n模式下的客户端关联关系
        self.target_client: Dict[str, Optional[websockets.WebSocketServerProtocol]] = {
            'id': '',
            'client': None
        }  # n-1模式目标客户端
        self.main_client: Dict[str, Optional[websockets.WebSocketServerProtocol]] = {
            'id': '',
            'client': None
        }  # 1-n模式主客户端
        self.client_timers: Dict[str, asyncio.Task] = {}  # 活跃的定时发送任务
        self.heartbeat_task: Optional[asyncio.Task] = None  # 心跳任务
        self.server: Optional[asyncio.AbstractServer] = None  # WebSocket服务器实例

        # 验证模式有效性
        if self.mode not in SERVER_MODES:
            raise ValueError(f"无效的服务器模式: {self.mode}，支持的模式: {', '.join(SERVER_MODES)}")

    def log(self, message: str) -> None:
        """日志系统"""
        log_msg = f"Server: {message}"

        # 输出到控制台
        #print(log_msg)

        # 发送到消息队列(如果存在)
        if self.message_queue:
            try:
                self.message_queue.put({
                    'action': 'logger',
                    'log_level': "INFO",
                    'message': log_msg
                })
            except Exception as e:
                print(f"日志队列写入失败: {e}")

    async def safe_send(self, websocket: websockets.WebSocketServerProtocol, data: str, client_id: str) -> bool:
        """安全发送消息，带重试机制"""
        for attempt in range(MAX_SEND_RETRIES):
            try:
                await asyncio.wait_for(websocket.send(data), timeout=SOCKET_TIMEOUT)
                return True
            except asyncio.TimeoutError:
                self.log(f"消息发送超时(尝试 {attempt + 1}/{MAX_SEND_RETRIES}): client={client_id}")
            except websockets.exceptions.ConnectionClosed:
                self.log(f"客户端已关闭，无法发送: client={client_id}")
                return False
            except Exception as e:
                self.log(f"发送消息异常(尝试 {attempt + 1}/{MAX_SEND_RETRIES}): {e}, client={client_id}")

        self.log(f"消息发送失败: client={client_id}")
        return False

    async def handle_bind(self, websocket: websockets.WebSocketServerProtocol, data: dict) -> None:
        """处理绑定请求"""
        client_id = data.get('clientId')
        target_id = data.get('targetId')
        send_data = data.copy()

        if self.mode == 'n-n':  # n-n模式: 双向绑定
            if not all([client_id in self.clients, target_id in self.clients]):
                send_data['message'] = "401"  # 客户端不存在
                await self.safe_send(websocket, json.dumps(send_data), client_id)
                self.log(f"n-n绑定失败: 客户端不存在 (client={client_id}, target={target_id})")
                return

            # 检查是否已绑定
            if client_id in self.relations or target_id in self.relations.values():
                send_data['message'] = "400"  # 已绑定
                await self.safe_send(websocket, json.dumps(send_data), client_id)
                self.log(f"n-n绑定失败: 已存在绑定关系 (client={client_id}, target={target_id})")
                return

            # 建立绑定关系
            self.relations[client_id] = target_id
            send_data['message'] = "200"  # 绑定成功
            # 通知双方
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            await self.safe_send(self.clients[target_id], json.dumps(send_data), target_id)
            self.log(f"n-n绑定成功: {client_id} <-> {target_id}")

        elif self.mode == 'n-1':  # n-1模式: 多客户端绑定到一个目标
            if target_id in self.clients and self.target_client['id'] == "":
                self.target_client['id'] = target_id
                self.target_client['client'] = websocket
                send_data['message'] = "200"
                await self.safe_send(websocket, json.dumps(send_data), client_id)
                # 通知所有客户端目标已绑定
                for cid, client in self.clients.items():
                    if cid != target_id:
                        await self.safe_send(client, json.dumps(send_data), cid)
                self.log(f"n-1模式目标绑定成功: target={target_id}")
            elif self.target_client['id'] != "":
                send_data['message'] = "401"  # 目标已绑定
                await self.safe_send(websocket, json.dumps(send_data), client_id)
                self.log(f"n-1模式绑定失败: 目标{self.target_client['id']}已绑定")
            else:
                send_data['message'] = "401"  # 目标不存在
                await self.safe_send(websocket, json.dumps(send_data), client_id)
                self.log(f"n-1模式绑定失败: 目标{target_id}不存在")

        elif self.mode == '1-n':  # 1-n模式: 一个主客户端绑定多个目标
            if client_id in self.clients and target_id in self.clients and self.main_client['id'] != "":
                send_data['message'] = "200"
                await self.safe_send(websocket, json.dumps(send_data), client_id)
                await self.safe_send(self.clients[target_id], json.dumps(send_data), target_id)
                self.log(f"1-n模式绑定成功: client={client_id} -> target={target_id}")
            else:
                send_data['message'] = "401"  # 客户端不存在
                await self.safe_send(websocket, json.dumps(send_data), client_id)
                self.log(f"1-n模式绑定失败: 客户端不存在")

    async def handle_control_message(self, websocket: websockets.WebSocketServerProtocol, data: dict) -> None:
        """处理类型1-3的控制消息(强度/通道调整)"""
        client_id = data.get('clientId')
        target_id = data.get('targetId')
        send_data = data.copy()

        # 权限校验
        if self.mode == 'n-n' and self.relations.get(client_id) != target_id:
            send_data['type'] = "bind"
            send_data['message'] = "402"  # 未绑定
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            self.log(f'消息发送失败(未绑定): client={client_id} -> target={target_id}')
            return

        if self.mode == '1-n' and self.main_client['id'] == "":
            send_data['type'] = "bind"
            send_data['message'] = "402"  # 主客户端不存在
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            self.log(f'消息发送失败(无主客户端): client={client_id}')
            return

        if self.mode == 'n-1' and self.target_client['id'] == "":
            send_data['type'] = "error"
            send_data['message'] = "403 - 无目标客户端"
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            self.log(f'消息发送失败(无目标客户端): client={client_id}')
            return

        # 构造消息并发送
        if target_id in self.clients:
            send_type = data.get('type') - 1
            send_channel = data.get('channel', 1)
            send_strength = data.get('strength', 1)
            send_data['type'] = "msg"
            send_data['message'] = f"strength-{send_channel}+{send_type}+{send_strength}"

            # 1-n模式广播(All)
            if self.mode == '1-n' and data.get('mode') == "All":
                for cid, client in self.clients.items():
                    if cid != client_id:
                        await self.safe_send(client, json.dumps(send_data), cid)
                self.log(f'1-n模式广播: client={client_id}, 通道={send_channel}')
            else:
                await self.safe_send(self.clients[target_id], json.dumps(send_data), target_id)
                self.log(f'消息发送: client={client_id} -> target={target_id}, 通道={send_channel}')

    async def handle_reverse_message(self, websocket: websockets.WebSocketServerProtocol, data: dict) -> None:
        """处理类型4消息(客户端到目标的反向通信)"""
        client_id = data.get('clientId')
        target_id = data.get('targetId')
        send_data = {
            'type': 'bind',
            'clientId': client_id,
            'targetId': target_id,
            'message': data.get('message')
        }

        # 权限校验
        if self.mode == 'n-n' and self.relations.get(client_id) != target_id:
            send_data['message'] = "402"  # 未绑定
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            return

        if self.mode == '1-n' and self.main_client['id'] == "":
            send_data['message'] = "402"  # 无主客户端
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            return

        # 发送消息
        if target_id in self.clients:
            await self.safe_send(self.clients[target_id], json.dumps(send_data), target_id)
            self.log(f'反向消息: client={client_id} -> target={target_id}')

    async def handle_waveform_message(self, websocket: websockets.WebSocketServerProtocol, data: dict) -> None:
        """处理波形消息(脉冲序列)"""
        client_id = data.get('clientId')
        target_id = data.get('targetId')
        send_data = data.copy()

        # 权限校验
        if self.mode == 'n-n' and self.relations.get(client_id) != target_id:
            send_data['type'] = "bind"
            send_data['message'] = "402"  # 未绑定
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            self.log(f'波形发送失败(未绑定): client={client_id} -> target={target_id}')
            return

        # 通道校验
        if 'channel' not in data:
            send_data['type'] = "error"
            send_data['message'] = "406 - 缺少通道信息"
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            return

        if target_id not in self.clients:
            send_data['message'] = "404 - 目标不存在"
            await self.safe_send(websocket, json.dumps(send_data), client_id)
            self.log(f'波形发送失败: target={target_id}不存在')
            return

        # 构造波形消息
        send_time = data.get('time', PUNISHMENT_DURATION)
        send_data['type'] = "msg"
        send_data['message'] = f'pulse-{data.get("message")}'
        total_sends = PULSE_FREQUENCY * send_time
        time_space = 1 / PULSE_FREQUENCY
        channel = data['channel']

        # 生成定时器ID(确保唯一)
        timer_id = f'{target_id}-{channel}' if self.mode in ['n-n', 'n-1'] else f'{client_id}-{channel}'

        # 处理已有任务(覆盖旧任务)
        if timer_id in self.client_timers:
            self.log(f'通道{channel}存在任务，正在覆盖: {timer_id}')
            # 取消旧任务
            old_task = self.client_timers[timer_id]
            old_task.cancel()
            try:
                await old_task
            except asyncio.CancelledError:
                self.log(f'旧任务已取消: {timer_id}')
            self.client_timers.pop(timer_id)

            # 发送清除指令
            clear_msg = {
                'type': 'msg',
                'clientId': client_id,
                'targetId': target_id,
                'message': f'clear-{"1" if channel == "A" else "2"}'
            }
            await asyncio.sleep(0.15)  # 延迟确保旧任务已停止
            await self.safe_send(self.clients[target_id], json.dumps(clear_msg), target_id)

        # 创建新任务并发送波形
        task = asyncio.create_task(
            self.delay_send_msg(
                client_id, websocket, self.clients[target_id],
                send_data, total_sends, time_space, channel, timer_id
            )
        )
        self.client_timers[timer_id] = task
        self.log(f'波形任务启动: {timer_id}, 总次数={total_sends}, 持续={send_time}秒')

    async def delay_send_msg(self, client_id: str, sender: websockets.WebSocketServerProtocol,
                             target_websocket: websockets.WebSocketServerProtocol, send_data: dict,
                             total_sends: int, time_space: float, channel: str, timer_id: str) -> None:
        """延迟发送消息，实现脉冲序列"""
        try:
            # 从send_data中获取target_id
            target_id = send_data.get('targetId')

            if not target_id:
                self.log(f'错误: 缺少target_id参数, client={client_id}')
                return

            self.log(f'准备发送脉冲消息: client={client_id} -> target={target_id}, 通道={channel}')

            # 立即发送第一次
            await self.safe_send(target_websocket, json.dumps(send_data), target_id)
            total_sends -= 1

            # 循环发送剩余消息
            while total_sends > 0 and not self.stop_event.is_set():
                await asyncio.sleep(time_space)
                await self.safe_send(target_websocket, json.dumps(send_data), target_id)
                total_sends -= 1

            self.log(f'脉冲消息发送完成: client={client_id} -> target={target_id}, 通道={channel}')

            # 发送完成确认
            if sender:
                try:
                    await self.safe_send(sender, json.dumps({"type": "status", "message": "send_complete"}), client_id)
                except Exception as e:
                    self.log(f'发送完成确认失败: {e}')

        except asyncio.CancelledError:
            self.log(f'定时器任务已取消: {timer_id}')
        except Exception as e:
            self.log(f'定时器任务执行错误: {timer_id}, 错误: {e}')
        finally:
            # 移除定时器引用
            self.client_timers.pop(timer_id, None)
            self.log(f'定时器任务已完成: {timer_id}')

    async def send_heartbeat(self) -> None:
        """发送心跳包，维护连接活跃状态"""
        self.log(f"心跳机制启动，间隔: {HEARTBEAT_INTERVAL}秒")

        heartbeat_msg = {
            "type": "heartbeat",
            "clientId": "",
            "targetId": "",
            "message": "200"
        }

        while not self.stop_event.is_set():
            try:
                if self.clients:  # 只有当有客户端连接时才发送心跳
                    self.log(f'发送心跳包，当前连接数: {len(self.clients)}')
                    for client_id, client in list(self.clients.items()):
                        heartbeat_msg['clientId'] = client_id
                        heartbeat_msg['targetId'] = self.relations.get(client_id, '')

                        try:
                            await asyncio.wait_for(
                                client.send(json.dumps(heartbeat_msg)),
                                timeout=SOCKET_TIMEOUT
                            )
                        except asyncio.TimeoutError:
                            self.log(f'心跳包发送超时，关闭连接: {client_id}')
                            await self.close_client(client_id)
                        except websockets.exceptions.ConnectionClosed:
                            self.log(f'客户端已关闭，跳过心跳: {client_id}')
                            await self.close_client(client_id)
                        except Exception as e:
                            self.log(f'发送心跳包时出错: {e}, client={client_id}')
                            await self.close_client(client_id)
            except Exception as e:
                self.log(f'心跳机制运行错误: {e}')

            # 等待下一个心跳周期
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def handle_app_disconnect(self, app_id: str) -> None:
        """处理APP端断开连接的优雅方式"""
        self.log(f'处理APP端断开连接: {app_id}')

        # 查找所有与该APP关联的客户端
        clients_to_notify = []
        for client_id, target_id in self.relations.items():
            if target_id == app_id:
                clients_to_notify.append(client_id)

        # 向所有关联客户端发送断开通知，但不断开连接
        for client_id in clients_to_notify:
            if client_id in self.clients:
                break_msg = {
                    'type': 'break',
                    'clientId': app_id,
                    'targetId': client_id,
                    'message': '209 - APP disconnected'
                }
                await self.safe_send(self.clients[client_id], json.dumps(break_msg), client_id)
                self.log(f'通知客户端 {client_id} APP {app_id} 已断开连接')

        # 从关系中移除与该APP相关的所有绑定
        self.relations = {k: v for k, v in self.relations.items() if v != app_id}

        # 特殊处理n-1模式
        if self.mode == 'n-1' and self.target_client['id'] == app_id:
            self.target_client['id'] = ''
            self.target_client['client'] = None
            self.log('n-1模式目标客户端已重置')

        # 不关闭客户端连接，让它们保持待连接状态
        self.log(f'APP {app_id} 断开处理完成，客户端保持连接状态')

    async def close_client(self, client_id: str, is_app: bool = False) -> None:
        """关闭指定客户端连接并清理资源
        is_app: 标识是否是APP端断开
        """
        if client_id not in self.clients:
            return

        self.log(f'开始关闭客户端: {client_id}')

        try:
            # 获取客户端连接
            websocket = self.clients[client_id]

            # 关闭关联的定时器任务
            for timer_id in list(self.client_timers.keys()):
                if timer_id.startswith(client_id) or timer_id.endswith(client_id):
                    task = self.client_timers[timer_id]
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    self.client_timers.pop(timer_id)
                    self.log(f'取消关联的定时器任务: {timer_id}')

            if is_app:
                # 处理APP端断开，通知客户端但不断开连接
                await self.handle_app_disconnect(client_id)
            else:
                # 处理普通客户端断开
                if self.mode == 'n-n':  # n-n模式
                    # 查找关联的客户端
                    for key, value in list(self.relations.items()):
                        if key == client_id or value == client_id:
                            peer_id = value if key == client_id else key
                            if peer_id in self.clients:
                                # 通知对方连接已断开
                                break_msg = {
                                    'type': 'break',
                                    'clientId': client_id,
                                    'targetId': peer_id,
                                    'message': '209 - Peer disconnected'
                                }
                                await self.safe_send(self.clients[peer_id], json.dumps(break_msg), peer_id)

                            # 移除绑定关系
                            self.relations.pop(key, None)

                elif self.mode == '1-n':  # 1-n模式
                    if client_id == self.main_client['id']:
                        # 主客户端断开，关闭所有关联客户端
                        self.log(f'主客户端断开，关闭所有关联客户端: {client_id}')
                        for cid in list(self.clients.keys()):
                            if cid != client_id:
                                break_msg = {
                                    'type': 'break',
                                    'clientId': client_id,
                                    'targetId': cid,
                                    'message': '209 - Master disconnected'
                                }
                                await self.safe_send(self.clients[cid], json.dumps(break_msg), cid)

                                # 关闭客户端连接
                                try:
                                    if not getattr(websocket, 'closed', True):
                                        await websocket.close(code=1000, reason='Master disconnected')
                                except Exception as e:
                                    self.log(f'关闭关联客户端时出错: {e}')

                                self.clients.pop(cid, None)

                        # 重置主客户端
                        self.main_client['id'] = ""
                        self.main_client['client'] = None
                    else:
                        # 普通客户端断开，通知主客户端
                        if self.main_client['id'] in self.clients:
                            break_msg = {
                                'type': 'break',
                                'clientId': client_id,
                                'targetId': self.main_client['id'],
                                'message': '209 - Client disconnected'
                            }
                            await self.safe_send(self.clients[self.main_client['id']], json.dumps(break_msg),
                                                 self.main_client['id'])

                elif self.mode == 'n-1':  # n-1模式
                    if client_id == self.target_client['id']:
                        # 目标客户端断开，重置目标客户端
                        self.target_client['id'] = ""
                        self.target_client['client'] = None
                        self.log(f'n-1模式目标客户端已断开: {client_id}')

                # 关闭客户端连接
                if not is_app:  # 仅非APP客户端才关闭连接
                    try:
                        if not getattr(websocket, 'closed', True):
                            await websocket.close(code=1000, reason='Server closing')
                    except Exception as e:
                        self.log(f'关闭客户端连接时出错: {e}, client={client_id}')

            # 移除客户端
            if not is_app:  # 仅非APP客户端才从clients中移除
                self.clients.pop(client_id, None)
                self.log(f'客户端已移除: {client_id}, 当前连接数: {len(self.clients)}')

        except Exception as e:
            self.log(f'处理客户端关闭时发生错误: {e}')

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """处理单个WebSocket客户端连接"""
        # 生成唯一客户端ID
        client_id = str(uuid.uuid4())
        self.log(f'新连接建立: client={client_id}')

        # 存储客户端连接
        self.clients[client_id] = websocket

        # 1-n模式下，首个连接作为主客户端
        if self.mode == '1-n' and self.main_client['id'] == "":
            self.main_client['id'] = client_id
            self.main_client['client'] = websocket
            self.log(f'1-n模式主客户端已设置: client={client_id}')

        # 发送初始绑定消息
        bind_msg = {
            "type": "bind",
            "clientId": client_id,
            "message": "targetId",
            "targetId": ""
        }
        if self.mode == 'n-1':  # n-1模式下，提供已绑定的目标ID
            bind_msg['targetId'] = self.target_client['id']
            bind_msg['message'] = "OK"

        await self.safe_send(websocket, json.dumps(bind_msg), client_id)

        # 消息处理器映射
        message_handlers = {
            'bind': self.handle_bind,
            1: self.handle_control_message,
            2: self.handle_control_message,
            3: self.handle_control_message,
            4: self.handle_reverse_message,
            'clientMsg': self.handle_waveform_message,
            'close': self.handle_client_close  # 新增关闭消息处理
        }

        try:
            # 启动心跳机制(如果尚未启动)
            if not self.heartbeat_task or self.heartbeat_task.done():
                self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
                self.log("心跳机制已启动")

            # 接收并处理消息
            async for message in websocket:
                try:
                    data = json.loads(message)
                    # 处理关闭通知（新增逻辑）
                    if data.get('type') == 'close':
                        client_id = data.get('clientId')
                        if client_id and client_id in self.clients:
                            # 发送关闭确认
                            ack_msg = {
                                'type': 'close_ack',
                                'clientId': client_id,
                                'timestamp': int(1000)
                            }
                            await self.clients[client_id].send(json.dumps(ack_msg))

                            # 关闭客户端连接
                            await self.close_client(client_id)
                        return  # 退出处理循环

                except json.JSONDecodeError:
                    self.log(f'收到非JSON格式消息: {message}')
                    error_msg = {
                        'type': 'error',
                        'message': '400 - Invalid JSON'
                    }
                    await self.safe_send(websocket, json.dumps(error_msg), client_id)
                    continue



                # 验证消息基本格式
                if not all(key in data for key in ['type', 'clientId', 'message', 'targetId']):
                    self.log(f'收到格式不完整的消息: {data}')
                    error_msg = {
                        'type': 'error',
                        'message': '400 - Incomplete message'
                    }
                    await self.safe_send(websocket, json.dumps(error_msg), client_id)
                    continue

                # 验证客户端ID
                if data.get('clientId') not in self.clients and self.clients.get(data.get('targetId')) != websocket:
                    self.log(f'收到非法消息: 未知客户端ID: {data.get("clientId")}')
                    error_msg = {
                        'type': 'error',
                        'message': '404 - Unknown client'
                    }
                    await self.safe_send(websocket, json.dumps(error_msg), client_id)
                    continue

                # 处理消息类型
                msg_type = data.get('type')
                if msg_type in message_handlers:
                    await message_handlers[msg_type](websocket, data)
                elif msg_type == 'app_disconnect':  # 新增: APP端主动断开通知
                    await self.close_client(client_id, is_app=True)
                else:
                    # 未知消息类型，转发或返回错误
                    if self.mode == 'n-n' and self.relations.get(client_id) != data.get('targetId'):
                        error_msg = {
                            'type': 'bind',
                            'message': '402 - Not bound'
                        }
                        await self.safe_send(websocket, json.dumps(error_msg), client_id)
                        continue

                    if data.get('targetId') in self.clients:
                        # 转发消息
                        await self.safe_send(
                            self.clients[data.get('targetId')],
                            json.dumps(data),
                            data.get('targetId')
                        )
                        self.log(f'转发消息: {msg_type} from {client_id} to {data.get("targetId")}')
                    else:
                        # 目标不存在
                        error_msg = {
                            'type': 'error',
                            'message': '404 - Target not found'
                        }
                        await self.safe_send(websocket, json.dumps(error_msg), client_id)

        except websockets.exceptions.ConnectionClosedOK:
            self.log(f'连接正常关闭: client={client_id}')
        except websockets.exceptions.ConnectionClosedError as e:
            # 判断是否是APP端断开
            is_app = client_id in self.relations.values()
            self.log(f'连接异常关闭: client={client_id}, 原因: {e}, is_app={is_app}')
            await self.close_client(client_id, is_app=is_app)
        except Exception as e:
            self.log(f'处理连接时发生意外错误: client={client_id}, 错误: {e}')
        finally:
            # 清理资源
            if client_id in self.clients:  # 确保只在需要时移除
                await self.close_client(client_id)  # 确保调用close_client
                self.log(f'客户端已清理: {client_id}')

    async def start(self) -> None:
        """启动WebSocket服务器"""
        self.log(f"服务器启动，模式: {self.mode}，地址: ws://{self.host}:{self.port}")

        # 创建服务器
        self.server = await websockets.serve(
            self.handle_client,
            host=self.host,
            port=self.port,
            max_size=2 ** 20  # 1MB
        )

        # 运行服务器直到停止
        try:
            await self.server.wait_closed()
        except asyncio.CancelledError:
            self.log('服务器任务被取消')
        finally:
            # 清理资源并关闭服务器
            await self.stop()

    async def handle_client_close(self, websocket: websockets.WebSocketServerProtocol, data: dict) -> None:
        """处理客户端主动关闭请求"""
        client_id = data.get('clientId')
        self.log(f'收到客户端关闭请求: {client_id}')
        await self.close_client(client_id)

    async def stop(self) -> None:
        """停止WebSocket服务器并清理资源"""
        self.log('开始关闭服务器...')

        # 设置停止标志
        self.stop_event.set()

        # 向所有客户端发送关闭通知
        if self.clients:
            close_msg = {
                'type': 'close',
                'clientId': '',
                'message': 'Server shutting down'
            }
            for client_id, client in list(self.clients.items()):
                try:
                    await self.safe_send(client, json.dumps(close_msg), client_id)
                except Exception as e:
                    self.log(f'向客户端 {client_id} 发送关闭通知失败: {e}')

        # 关闭所有客户端连接
        if len(self.clients) != 0:
            for client_id in list(self.clients.keys()):
                await self.close_client(client_id)

        # 取消心跳任务
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
            self.log('取消心跳任务')

        # 关闭服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            self.log('WebSocket服务器已关闭')

        # 重置所有状态
        self.relations.clear()
        self.target_client['id'] = ''
        self.target_client['client'] = None
        self.main_client['id'] = ''
        self.main_client['client'] = None

        self.log('服务器已完全关闭')


def get_local_ip() -> str:
    """获取本地IP地址"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))  # 不实际发送数据
            return s.getsockname()[0]
    except Exception as e:
        print(f"获取本地IP失败: {e}")
        return "127.0.0.1"


if __name__ == "__main__":
    """程序入口点"""
    try:
        # 获取本地IP并启动服务器
        local_ip = get_local_ip()
        print(f"启动WebSocket服务器: ws://{local_ip}:1145")
        print(f"支持的模式: {', '.join(SERVER_MODES)}")

        # 创建并启动服务器
        server = WebSocketServer(host=local_ip, port=1145, mode=DEFAULT_MODE)
        asyncio.run(server.start())

    except KeyboardInterrupt:
        # 处理用户中断
        print("\n接收到中断信号，正在关闭服务器...")
        # 注意：在实际应用中，应通过适当的方式通知服务器停止
        print("服务器已关闭")
    except Exception as e:
        print(f"服务器启动失败: {e}")