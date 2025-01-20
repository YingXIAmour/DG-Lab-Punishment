#ws_server.py
import asyncio
import socket
import websockets
import uuid
import json
import threading
import time
from datetime import datetime
from asgiref.timeout import timeout
from requests.packages import target
import argparse
#关闭指令
stop = False
#模式列表
mode_r = ['n-n','n-1','1-n']
mode = mode_r[0]
# 储存已连接的用户及其WebSocket连接对象
clients = dict()
# 存储消息关系（n-n模式使用）
relations = dict()
#n-1模式存储
target_id_clients = {
    'id':'',
    'client':None
}
#1-n模式存储
client_id_clients = {
    'id':'',
    'client':None
}
# 默认惩罚时长（单位：秒）
punishmentDuration = 5

# 默认发送心跳的时间间隔（单位：秒）
punishmentTime = 1

# 存储客户端和发送计时器的关系
client_timers = dict()

# 定义心跳消息模板
heartbeat_msg = {
    "type": "heartbeat",
    "clientId": "",
    "targetId": "",
    "message": "200"
}
#定义心跳计时器
heartbeat_Interval = False
#获取本地IP
def get_local_ip():
    try:
        # 创建一个UDP套接字
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 连接到一个不存在的地址，这样不会真正发送数据
        s.connect(('8.8.8.8', 80))

        # 获取本地IP地址
        local_ip = s.getsockname()

        # 关闭套接字
        s.close()
    except Exception as e:
        print(f"Error occurred: {e}")
        local_ip = None

    return local_ip[0]

async def handler_type_bind(websocket,data):
    client_Id = data.get('clientId')
    target_Id = data.get('targetId')
    send_data = data
    if mode == mode_r[0]:
        if client_Id in clients and target_Id in clients:
            if client_Id not in relations or target_Id not in relations.values():
                relations[client_Id] = target_Id
                client = clients[client_Id]
                send_data['message'] = "200"
                await websocket.send(json.dumps(send_data))
                await client.send(json.dumps(send_data))
                log('clientId:{},targetId:{} 绑定成功'.format(client_Id, target_Id))
            else:
                send_data['message'] = "400"
                await websocket.send(json.dumps(send_data))
                log('clientId:{},targetId:{} 绑定失败 原因：其中一方已被绑定过'.format(client_Id, target_Id))
                return
        else:
            send_data['message'] = "401"
            await websocket.send(json.dumps(send_data))
            log('客户端或APP连接不存在！')
            return
    elif mode == mode_r[1]:
        if target_Id in clients and target_id_clients['id'] == "":
            send_data['message'] = "200"
            await websocket.send(json.dumps(send_data))
            target_id_clients['id'] = target_Id
            target_id_clients['client'] = websocket
            for client in clients:
                await client.send(json.dumps(send_data))
            log('targetId:{} 主机连接成功'.format(target_Id))
        elif target_id_clients['id'] != "":
            send_data['message'] = "401"
            await websocket.send(json.dumps(send_data))
            log('APP已达连接上限！')
            return
        else:
            send_data['message'] = "401"
            await websocket.send(json.dumps(send_data))
            log('客户端或APP连接不存在！')
            return
    elif mode == mode_r[2]:
        if client_Id in clients and target_Id in clients and client_id_clients['id'] != "":
            client = clients[client_Id]
            send_data['message'] = "200"
            await websocket.send(json.dumps(send_data))
            await client.send(json.dumps(send_data))
            log('targetId:{} 主机连接成功'.format(target_Id))
        else:
            send_data['message'] = "401"
            await websocket.send(json.dumps(send_data))
            log('客户端或APP连接不存在！')
            return
    else:
        log("模式错误，即将断开连接")
        await on_connection_closed(websocket)

async def handler_type_123(websocket,data):
    client_Id = data.get('clientId')
    target_Id = data.get('targetId')
    message = data.get('message')
    send_data = data
    if relations.get(client_Id) != target_Id and mode == mode_r[0]:
        send_data['type'] = "bind"
        send_data['message'] = "402"
        await websocket.send(json.dumps(send_data))
        log('client_Id:{} 错误：未绑定APP！')
        return
    elif client_id_clients['id'] == "" and mode == mode_r[2]:
        send_data['type'] = "bind"
        send_data['message'] = "402"
        await websocket.send(json.dumps(send_data))
        log('client_Id:{} 错误：客户端不存在！')
        return
    elif target_id_clients['id'] == "" and mode == mode_r[1]:
        send_data['type'] = "error"
        send_data['message'] = "403 - no app client"
        await websocket.send(json.dumps(send_data))
        log('无APP连接！')
    if target_Id in clients:
        send_type = data.get('type') - 1
        send_channel = data.get('channel') if 'channel' in data else 1
        send_strength = data.get('strength') if 'strength' in data else 1  # if data['type'] >= 3 else 1
        msg = "strength-{}+{}+{}".format(send_channel, send_type, send_strength)
        send_data['type'] = "msg"
        send_data['message'] = msg
        # 发送消息

        if mode == mode_r[2] and data.get('mode') == "All":
            for clientId, client in clients.items():
                if client_Id == clientId:
                    continue
                else:
                    await client.send(json.dumps(send_data))
        else:
            client = clients.get(target_Id)
            await client.send(json.dumps(send_data))

async def handler_type_4(websocket,data): #理论：应该是客户端连接到app的反向操作,具体实现方法没怎么看懂
    client_Id = data.get('clientId')
    target_Id = data.get('targetId')
    messages = data.get('message')
    send_data = data
    if relations.get(client_Id) != target_Id and mode == mode_r[0]:
        send_data['type'] = "bind"
        send_data['message'] = "402"
        await websocket.send(json.dumps(send_data))
        return
    elif client_id_clients['id'] == "" and mode == mode_r[2]:
        send_data['type'] = "bind"
        send_data['message'] = "402"
        await websocket.send(json.dumps(send_data))
        return
    elif target_id_clients['id'] == "" and mode == mode_r[1]:
        send_data['type'] = "error"
        send_data['message'] = "403"
        await websocket.send(json.dumps(send_data))
        return
    if target_Id in clients:
        client = clients.get(target_Id)
        send_data = {
            'type': 'bind',
            'clientId': client_Id,
            'targetId': target_Id,
            'message': message
        }
        await client.send(json.dumps(send_data))
async def handler_type_client_msg(websocket,data):# 发送波形
    client_Id = data.get('clientId')
    target_Id = data.get('targetId')
    message = data.get('message')
    send_data = data
    if relations.get(client_Id) != target_Id and mode == mode_r[0]:
        send_data['type'] = "bind"
        send_data['message'] = "402"
        await websocket.send(json.dumps(send_data))
        log('client_Id:{} 错误：未绑定APP！')
        return
    elif client_id_clients['id'] == "" and mode == mode_r[2]:
        send_data['type'] = "bind"
        send_data['message'] = "402"
        await websocket.send(json.dumps(send_data))
        log('client_Id:{} 错误：客户端不存在！')
        return
    elif target_id_clients['id'] == "" and mode == mode_r[1]:
        send_data['type'] = "error"
        send_data['message'] = "403"
        await websocket.send(json.dumps(send_data))
        log('无APP连接！')
        return
    if data.get('channel') is None:
        send_data['type'] = "error"
        send_data['message'] = "406 - channel is empty"
        await websocket.send(json.dumps(send_data))
    if target_Id in clients:
        send_time = data.get('time', punishmentDuration)
        #target = clients.get(target_Id)
        send_data['type'] = "msg"
        send_data['message'] = 'pulse-{}'.format(message)

        total_Sends = punishmentTime * send_time
        time_Space = 1 / punishmentTime
        channel = data['channel']
        if mode == mode_r[0] or mode == mode_r[1]:
             timer_Id_a = '{}-{}'.format(target_Id, data.get('channel'))
             task_name = '{}-{}'.format(target_Id, data.get('channel'))
        else:
            timer_Id_a = '{}-{}'.format(client_Id, data.get('channel'))
            task_name = '{}-{}'.format(client_Id, data.get('channel'))
        task_channel = {
            'A': '',
            'B': ''
        }
        if timer_Id_a in client_timers:
            log('通道{}覆盖消息发送中，总消息数：{}持续时间：{}'.format(channel, total_Sends,
                                                                      send_time))
            #await websocket.send('当前通道{}有正在发送的消息，覆盖之前的消息'.format(data['channel']))
            timer_Id = client_timers[timer_Id_a]
            # 清除计时器
            timer_Id.cancel()
            try:
                await  timer_Id
            except asyncio.CancelledError:
                log('通道{}任务关闭，消息重新覆盖'.format(timer_Id_a))
            client_timers.pop(timer_Id_a)
            clear_Data = {
                'type': 'msg',
                'clientId': client_Id,
                'targetId': target_Id,
                'message': 'clear-1'
            }
            if data['channel'] == "A":
                clear_Data = {
                    'type': 'msg',
                    'clientId': client_Id,
                    'targetId': target_Id,
                    'message': 'clear-1'
                }
            elif data['channel'] == "B":
                clear_Data = {
                    'type': 'msg',
                    'clientId': client_Id,
                    'targetId': target_Id,
                    'message': 'clear-2'
                }

            # 延迟发送信息
            await asyncio.sleep(0.150)
            if mode == mode_r[2] and data.get('mode') == "All":
                for target__id,target in clients.items():
                    if target__id == client_Id:
                        continue
                    else:
                        await target.send(json.dumps(clear_Data))
                        task_channel[task_name] = asyncio.create_task(delay_send_msg(client_Id, websocket, target, send_data, total_Sends, time_Space, data['channel'],timer_Id_a))
            else:
                target = clients.get(target_Id)
                task_channel[task_name] = asyncio.create_task(
                    delay_send_msg(client_Id, websocket, target, send_data, total_Sends, time_Space, data['channel'],timer_Id_a))
            log('通道{}消息发送中，总消息数：{}持续时间：{}'.format(data['channel'], total_Sends,
                                                                 send_time))
        else:
            # 直接发送信息
            if mode == mode_r[2] and data.get(target_Id) == "All":
                for target__id, target in clients.items():
                    if target__id == client_Id:
                        continue
                    else:
                        task_channel[task_name] = asyncio.create_task(
                            delay_send_msg(client_Id, websocket, target, send_data, total_Sends, time_Space,
                                           data['channel'],timer_Id_a))
            else:
                target = clients.get(target_Id)
                task_channel[task_name] = asyncio.create_task(
                    delay_send_msg(client_Id, websocket, target, send_data, total_Sends, time_Space, data['channel'],timer_Id_a))
            log('通道{}消息发送中，总消息数：{}持续时间：{}'.format(data['channel'], total_Sends,
                                                                 send_time))
    else:
        log('未找到匹配的客户端，clientId:{}'.format(client_Id))
        send_data['message'] = "404"
        await websocket.send(json.dumps(send_data))

#传入类型
type_handlers = {
    'bind': handler_type_bind,
    1:handler_type_123,
    2:handler_type_123,
    3:handler_type_123,
    4:handler_type_4,
    'clientMsg': handler_type_client_msg
}
#主程序
async def server_main(websocket):
    global heartbeat_Interval
    # 生成标识符
    client_id = str(uuid.uuid4())
    log(f'新的 WebSocket 连接已建立，标识符为:{client_id}')

    # 将客户端标识符和WebSocket连接对象存入字典
    clients[client_id] = websocket
    if mode == mode_r[2] and client_id_clients['id'] == "": #1-n模式：优先进行客户端处理，后续才是APP连接
        client_id_clients['id'] = client_id
        client_id_clients['client'] = websocket
    # 构造绑定消息
    msg = {
        "type": "bind",
        "clientId": client_id,
        "message": "targetId",
        "targetId": ""
    }
    if mode == mode_r[1]:
        msg['targetId'] = target_id_clients['id']
        msg["message"] = "OK"

    # 将字典转换成JSON字符串并发送
    await websocket.send(json.dumps(msg))
    try:
        # 启动心跳计时器
        if not heartbeat_Interval:
            loop = asyncio.get_event_loop()
            # 启动心跳线程
            heartbeat_thread = threading.Thread(target=start_heartbeat_thread, args=(loop,), daemon=True)
            heartbeat_thread.start()
            heartbeat_Interval = True
        # 开始接收消息
        async for message in websocket:
            #log(f'收到消息:{message}')
            data = None
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                # 如果消息不是有效的JSON，则发送错误响应
                response = {
                    'type': 'msg',
                    'clientId': '',
                    'targetId': '',
                    'message': '403'
                }
                await websocket.send(json.dumps(response))
                log('发现数据非json格式')

            if data.get('clientId') not in clients and clients.get(data.get('targetId')) != websocket:
                response = {
                    'type': 'msg',
                    'clientId': '',
                    'targetId': '',
                    'message': '404'
                }
                await websocket.send(json.dumps(response))
                log("非法提交")
                return
            if 'type' in data and 'clientId' in data and 'message' in data and 'targetId' in data:
                a_type = data['type']

                if a_type in type_handlers:
                    await type_handlers[a_type](websocket,data)
                else:
                    client_Id = data.get('clientId')
                    target_Id = data.get('targetId')
                    if relations.get(client_Id) != target_Id and mode == mode_r[0]:
                        send_data = {
                            'type': 'bind',
                            'clientId': client_Id,
                            'targetId': target_Id,
                            'message': '402'
                        }
                        await websocket.send(json.dumps(send_data))
                        return
                    if client_Id in clients:
                        client = clients.get(client_Id)
                        send_data = {
                            'type': a_type,
                            'clientId': client_Id,
                            'targetId': target_Id,
                            'message': data['message']
                        }
                        await client.send(json.dumps(send_data))
                    else:
                        send_data = {
                            'type': 'msg',
                            'clientId': client_Id,
                            'targetId': target_Id,
                            'message': '404'
                        }
                        await websocket.send(json.dumps(send_data))



    except websockets.exceptions.ConnectionClosedError:
        await on_connection_closed(websocket)
    except websockets.ConnectionClosed as e:
        await on_connection_closed(websocket)
        # 在这里处理接收到的有效JSON消息
        # ...（根据data内容执行相应逻辑）
    except websockets.exceptions.InvalidURI:
        #await on_connection_closed(websocket)
        log("The provided URI is invalid.")
        # 示例：简单回显收到的消息
    finally:
        for value in clients.values():
            if value == websocket:
                await on_connection_closed(websocket)
                break
        #await websocket.close()

#连接关闭操作
async def on_connection_closed(websocket):
    client_Id = ''
    for key, value in clients.items():
        if value == websocket:
            # 拿到断开的客户端id
            client_Id = key
            break  # 找到后退出循环
    if client_Id.strip() == '':
        return
    log('WebSocket 连接已关闭 断开的client id:{}'.format(client_Id))
    if (client_Id in relations.keys() or client_Id in relations.values()) and mode == mode_r[0]:
        keys_to_remove = []
        for key, value in relations.copy().items():
            if key == client_Id:
                appId = relations.get(key)
                appClient = clients.get(appId)
                send_data = {
                    'type': 'break',
                    'clientId': client_Id,
                    'targetId': appId,
                    'message': '209'
                }
                await appClient.send(json.dumps(send_data))
                await appClient.close(code=1000, reason='Close Connencent')
                keys_to_remove.append(key)
                log('对方掉线，关闭{}'.format(appId))
            elif value == client_Id:
                webClient = clients.get(key)
                send_data = {
                    'type': 'break',
                    'clientId': key,
                    'targetId': client_Id,
                    'message': '209'
                }
                await webClient.send(json.dumps(send_data))
                await webClient.close(code=1000, reason='Close Connencent')
                keys_to_remove.append(key)
                log('对方掉线，关闭{}'.format(client_Id))
        for key in keys_to_remove:
            del relations[key]
            clients.pop(key)
    elif mode == mode_r[2]:
        if client_Id == client_id_clients['id']:
            for key,ws in clients.copy().items():
                if key != client_Id:
                    send_data = {
                        'type': 'break',
                        'clientId': client_Id,
                        'targetId': key,
                        'message': '209'
                    }
                    await ws.send(json.dumps(send_data))
                    await ws.close(code=1000, reason='Close Connencent')
                    clients.pop(key)
            clients.pop(client_Id)
        else:
            webClient = clients.get(client_id_clients['id'])
            send_data = {
                'type': 'break',
                'clientId': client_id_clients['id'],
                'targetId': client_Id,
                'message': '209'
            }
            await webClient.send(json.dumps(send_data))
            clients.pop(client_Id)
    else:
        clients.pop(client_Id)
    log("已清除{},当前len：{}".format(client_Id,len(clients)))

async def server_closed():
    log('WebSocket Server正在关闭')
    client_Id = ''
    for client_Id,client in clients.copy().items():
        await client.close()
        log('断开的client id:{}'.format(client_Id))
    log('WebSocket Server关闭')
async def closed_client(client_uuid):
    client = clients.get(client_uuid)
    await on_connection_closed(client)
async def main(ip,port,model,):
    global mode
    #parser = argparse.ArgumentParser(description='WebSocket服务器启动参数说明')
    #parser.add_argument('-i', '--ip', type=str, help='服务器绑定的IP地址', required=False, default=get_local_ip())
    #parser.add_argument('-p', '--port', type=int, help='服务器监听的端口号', required=False, default=1145)
    #parser.add_argument('-m', '--mode', type=str, help='服务器模式', required=False, default=mode_r[0])
    #args = parser.parse_args()
    #ip = args.ip if args.ip.strip() != "" else get_local_ip()
    #port = args.port if str(args.port).strip() != "" else 1145
    #mode = args.mode if args.mode.strip() != "" else mode_r[0]
    mode = model
    # 使用 asyncio.run() 时，不需要手动获取事件循环
    if mode == mode_r[0]:
        log("服务器模式：n-n")
    elif mode == mode_r[1]:
        log("服务器模式：n-1")
        #clients[server_client_id] = ""
    elif mode == mode_r[2]:
        log("服务器模式1-n")
    else:
        log("服务器模式错误！")
        return
    async with websockets.serve(server_main, host=ip, port=port):
        log('服务器在{}上运行'.format(ip))
        log('连接信息：ws://{}:{}'.format(ip, port))
        while not stop:
            await asyncio.sleep(1)
        await server_closed()
        log('服务器正在关闭...')
        return
        #await asyncio.Future()  # 这将让服务器一直运行


# 启动心跳发送线程的函数
def start_heartbeat_thread(loop):
    asyncio.run_coroutine_threadsafe(send_heartbeat(), loop)
#心跳包
async def send_heartbeat():
    while not stop:
        if clients:  # 如果clients字典不为空
            log('绑定关系：{} 客户端连接数：{} 发送心跳消息'.format(len(relations),len(clients)))
            for client_id, client in clients.items():
                heartbeat_msg['clientId'] = client_id
                heartbeat_msg['targetId'] = relations.get(client_id, '')
                try:
                    await asyncio.wait_for(client.send(json.dumps(heartbeat_msg)),timeout=3)# 假设client对象有一个异步的send方法
                except asyncio.TimeoutError:
                    log('心跳包发送超时！客户端连接异常：{}'.format(client_id))
                    await on_connection_closed(client)
                except Exception as e:
                    log(f'发送心跳包出现其他异常: {e}')
                    # 可以在这里根据具体情况决定是否也调用on_connection_closed等处理逻辑
                    await on_connection_closed(client)
        await asyncio.sleep(30)  # 每半分钟发送一次心跳消息
#日志
def log(msg):
    message = '[{}] Server: {}'.format(datetime.now().strftime('%H:%M:%S'),msg)
    print(message)

async def delay_send_msg(client_id, client, target, send_data, total_sends, time_space, channel,timer_Id):
    global client_timers
    # 立即发送一次通道的消息
    await target.send(json.dumps(send_data))
    total_sends -= 1

    # 如果还有消息需要发送，则设置一个定时任务
    if total_sends > 0:
        async def send_messages():
            nonlocal total_sends
            while total_sends > 0:
                await target.send(json.dumps(send_data))
                total_sends -= 1
                await asyncio.sleep(time_space)
            # 发送完毕，通知客户端
            await client.send('发送完毕')
            #log('信息发送完毕')
            # 删除对应的定时器（在Python中不需要显式删除，因为任务完成后会自动结束）
            del client_timers[timer_Id]
            #if timer_Id in client_timers:
                #log('删除失败')
            #else:
                #log('信息发送完毕 已删除任务{}'.format(timer_Id))
        # 创建并启动定时任务
        try:
            timer_task = asyncio.create_task(send_messages())
            #log('任务创建成功：{}通道'.format(channel))
        except Exception in e:
            log('报错')
            return
        # 存储clientId、channel和timer_task的映射
        client_timers[timer_Id] = timer_task
        await timer_task
    else:
        # 如果没有剩余消息要发送，直接通知客户端发送完毕
        await client.send("发送完毕")
        #log('信息发送完毕')
if __name__ == '__main__':

    # 使用 asyncio.run() 来运行主协程
    try:
        asyncio.run(main("10.11.82.219",1145,"n-n"))
    except KeyboardInterrupt:
        # 在这里可以添加进一步的清理资源、关闭进程等操作
        stop = True
        log("用户手动关闭服务器，服务器已关闭")