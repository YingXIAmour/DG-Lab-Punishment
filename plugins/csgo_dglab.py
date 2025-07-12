import asyncio
import io
import json
import math
import random
from aiohttp import web
import winreg
import os
import queue
name = "CSGO-受伤惩罚"
author = "RicoShot"

base_dir = None
PULSE_DATA = None
stop_event = None
mode = None
mode_r = ["1","2","3"]
def get_cs2_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 0, winreg.KEY_READ)
        path, _ = winreg.QueryValueEx(key, 'SteamPath')
        winreg.CloseKey(key)
    except:
        return None

    libpath = path + '/steamapps/libraryfolders.vdf'

    with open(libpath, 'r') as libvdf:
        library = libvdf.readlines()
        last_path = None
        found = False

        for line in library:
            pair = line.strip('\n').strip('\t')
            if pair.startswith('"path"'):
                _, v = pair.split('\t\t')
                last_path = v.strip('"').encode().decode('unicode_escape')
            elif '"730"' in pair:
                found = True
                break

        if found and os.path.exists(last_path + '\\steamapps\\common\\Counter-Strike Global Offensive\\'):
            csi_path = last_path + '\\steamapps\\common\\Counter-Strike Global Offensive\\'
            log(f"已找到 CS2 安装路径: {csi_path}")
            return csi_path


def auto_set_cfg():
    cfg = """"CS2&DGLAB"
{
 "uri" "http://127.0.0.1:3000"
 "timeout" "0.1"
 "buffer"  "0.1"
 "throttle" "0.5"
 "heartbeat" "1.0"
 "auth"
 {
   "token" "MYTOKENHERE"
 }
 "data"
 {
   "provider"            "1"
   "map"                 "1"
   "round"               "1"
   "player_id"           "1"
   "player_state"        "1"
 }
}
"""
    try:
        path = get_cs2_path() + "\\game\\csgo\\cfg"
        if os.path.exists(path):
            with open(path + "\\gamestate_integration_cs2&dglab.cfg", "w") as f:
                f.write(cfg)
        else:
            os.makedirs(path)
            with open(path + "\\gamestate_integration_cs2&dglab.cfg", "w") as f:
                f.write(cfg)
        return True
    except Exception as e:
        print(f"写入文件时发生错误: {e}")
        return False
# 当前血量
health = 100
# 双通道最大强度以及当前强度
strength = dict()
max_strength_A = 0
max_strength_B = 0
strength_A = 0
strength_B = 0
# 闪光弹强度、混烟强度
flash_strength = {
    'A':0.3,
    'B':0.3
}
smoke_strength = {
    'A':0.05,
    'B':0.05
}
# 惩罚时间
punish_time = dict()
# 自动归零
set_zero = True
# 持续输出波形模式 - 2
async def send_waveform(client_message_queue):
    while not stop_event.is_set():
        time_int = random.randint(1,10)
        pluses_int = str(random.randint(1,len(PULSE_DATA["持续输出"])))
        send_data = {
            'action':"send_pluses",
            'pluses':str(PULSE_DATA["持续输出"][pluses_int]),
            'punish_time': time_int,
            'channel':"All"
        }
        client_message_queue.put(send_data)
        await asyncio.sleep(time_int)
# 定时归零
async def set_zero_strength(client_message_queue):
    global set_zero
    while not stop_event.is_set():
        await asyncio.sleep(3)
        if set_zero is True:
            send_data = {
                'action': "set_strength",
                'strength': 0,
                "channel": "A"
            }
            client_message_queue.put(send_data)
            await asyncio.sleep(0.1)
            send_data['channel'] = "B"
            client_message_queue.put(send_data)

        else:
            set_zero = True

async def handle_post_request(request):
    global health,set_zero
    queue = request.app["queue"]  # 从app中获取queue
    """处理cs数据请求请求"""
    try:
        data = await request.json()
        if not data:
            return web.json_response(
                {"status": "error", "message": "请求体为空"}, status=400
            )
        if "player" in data and "map" in data:
            if data["provider"]["steamid"] == data["player"]["steamid"]:
                now_health = data["player"]["state"]["health"]
                flash = data["player"]["state"]["flashed"]
                smoke = data["player"]["state"]["smoked"]
                # 血量减少（调整强度，发送波形）
                if now_health < health and now_health != 0:
                    data_a = math.ceil((100 - now_health) / 100 * max_strength_A)
                    data_b = math.ceil((100 - now_health) / 100 * max_strength_B)
                    log(f"玩家生命值减少: {health} -> {now_health}")
                    if mode == mode_r[0]:
                        # 这里多写一层判断，判断是否被烧伤
                        if data["player"]["state"]["burning"] > 0:
                            waveform_data = {"type": "pluse", "data": PULSE_DATA["烧伤"], "time": punish_time['烧伤']}
                            await queue.put(waveform_data)
                        else:
                            waveform_data = {"type": "pluse", "data": PULSE_DATA["受伤"], "time": punish_time['受伤']}
                            await queue.put(waveform_data)

                    # 强度
                    waveform_data = {
                        "type": "strlup",
                        "data": data_a,
                        "chose": "a",
                    }
                    await queue.put(waveform_data)
                    waveform_data = {
                        "type": "strlup",
                        "data": data_b,
                        "chose": "b",
                    }
                    await queue.put(waveform_data)
                    health = now_health
                    set_zero = False
                # 傻瓜蛋！
                if flash > 0:
                    data_a = math.ceil(max_strength_A*flash_strength['A'])
                    data_b = math.ceil(max_strength_B*flash_strength['B'])
                    waveform_data = {
                        "type": "strlup",
                        "data": data_a,
                        "chose": "a",
                    }
                    await queue.put(waveform_data)
                    waveform_data = {
                        "type": "strlup",
                        "data": data_b,
                        "chose": "b",
                    }
                    await queue.put(waveform_data)
                    set_zero = False
                    health = now_health
                    if mode == mode_r[0]:
                        waveform_data = {"type": "pluse", "data": PULSE_DATA["傻瓜蛋"],"time":punish_time['闪光弹']}
                        await queue.put(waveform_data)

                if smoke > 0:
                    data_a = math.ceil(max_strength_A * smoke_strength['A'] + strength_A)
                    data_b = math.ceil(max_strength_B * smoke_strength['B'] + strength_B)
                    waveform_data = {
                        "type": "strlup",
                        "data": data_a,
                        "chose": "a",
                    }
                    await queue.put(waveform_data)
                    waveform_data = {
                        "type": "strlup",
                        "data": data_b,
                        "chose": "b",
                    }
                    await queue.put(waveform_data)
                    set_zero = False
                    if mode == mode_r[0]:
                        random_int = str(random.randint(1, len(PULSE_DATA["烟雾弹"])))
                        waveform_data = {"type": "pluse", "data": PULSE_DATA["烟雾弹"][random_int],"time":punish_time['烟雾弹']}
                        await queue.put(waveform_data)

                # 血量归零以及回合结束重置强度以及血量
                if now_health == 0:
                    health = 100
                    # 强度
                    waveform_data = {
                        "type": "strlup",
                        "data": max_strength_A,
                        "chose": "a",
                    }
                    await queue.put(waveform_data)
                    waveform_data = {
                        "type": "strlup",
                        "data": max_strength_B,
                        "chose": "b",
                    }
                    await queue.put(waveform_data)
                    if mode == mode_r[0]:
                        waveform_data = {"type": "pluse", "data": PULSE_DATA["死亡"],"time":3}
                        await queue.put(waveform_data)

                    await asyncio.sleep(5)
                    waveform_data = {"type": "strlse", "data": 100}
                    await queue.put(waveform_data)
                if "round" in data :
                    if data["round"]["phase"] == "over":
                        waveform_data = {"type": "strlse", "data": 100}
                        await queue.put(waveform_data)
                # 游戏结束重置强度
                if data["map"]["phase"] == "gameover":
                    waveform_data = {"type": "strlse", "data": 100}
                    await queue.put(waveform_data)
                return web.json_response({"status": "success", "message": "数据已接收"})
            else:
                # 处理不包含player和map的情况
                return web.json_response(
                    {"status": "error", "message": "请求数据缺少player或map字段"},
                    status=400
                )
    except Exception as e:
        log(f"处理POST请求时出错: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def send_waveform_on_queue_change(in_queue, client_message_queue):
    while not stop_event.is_set():
        waveform_data = await in_queue.get()
        types = waveform_data["type"]
        data = waveform_data["data"]
        time = waveform_data.get("time") if waveform_data.get("time") is not None else 5
        if types == "pluse":
            send_data = {
                'action':"send_pluses",
                'pluses':str(data),
                'punish_time':time,
                "channel":"All"
            }
            client_message_queue.put(send_data)
        elif types == "strlup":
            chose = waveform_data["chose"]
            send_data = {
                'action':"set_strength",
                'strength':data,
                'channel':""
            }
            if chose == "a":
                send_data['channel'] = "A"
                client_message_queue.put(send_data)
            if chose == "b":
                send_data['channel'] = "B"
                client_message_queue.put(send_data)
        elif types == "strlse":
            send_data = {
                'action': "set_strength",
                'strength': 0,
                'channel': "A"
            }
            client_message_queue.put(send_data)
            send_data['channel'] = "B"
            client_message_queue.put(send_data)
        elif types == "strlst":
            send_data = {
                'action': "set_strength",
                'strength': data,
                'channel': "A"
            }
            client_message_queue.put(send_data)
            send_data['channel'] = "B"
            client_message_queue.put(send_data)
        else:
            log("接收到未知类型数据，请检查")

def log(msg_a):
    message = 'CSGO: {}'.format(msg_a)
    send_data = {
        'action':"logger",
        'log_level':"INFO",
        'message':message
    }
    msg_queue.put(send_data)
msg_queue = None
async def main(client_message_queue,data):
    global max_strength_A,max_strength_B,strength_A,strength_B,PULSE_DATA,stop_event,mode,msg_queue,flash_strength,smoke_strength,punish_time
    msg_queue = client_message_queue
    stop_event = asyncio.Event()
    conf_json = os.path.join(base_dir, data["Config"]+".json")
    mode = data["Mode"]
    # 读取 PULSE_DATA 从 JSON 文件
    with open(conf_json, "r", encoding="utf-8") as file:
        config = json.load(file)
        PULSE_DATA = config["pulse_data"]
        flash_strength = config["闪光弹强度"]
        smoke_strength = config["烟雾弹强度"]
        punish_time = config['punish_time']
    in_queue = asyncio.Queue()

    app = web.Application()
    app["queue"] = in_queue
    app.router.add_post("/", handle_post_request)

    if auto_set_cfg():
        log("自动导入cfg成功")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 3000)
    await site.start()
    log("HTTP服务器已启动，监听端口 3000")

    # 启动监视队列的任务
    queue_monitor_task = asyncio.create_task(
        send_waveform_on_queue_change(in_queue, client_message_queue)
    )
    tasks = [queue_monitor_task]
    if config['SetZero'] is True:
        set_zero_task = asyncio.create_task(
            set_zero_strength(client_message_queue)
        )
        tasks.append(set_zero_task)
    if mode == mode_r[1]:
        set_wave_task = asyncio.create_task(
            send_waveform(client_message_queue)
        )
        tasks.append(set_wave_task)

    strength_queue = queue.Queue()
    try:
        while not stop_event.is_set():
            send_data = {
                'action': "get_strength",
                'queue': strength_queue
            }
            client_message_queue.put(send_data)
            strength = strength_queue.get(timeout=1)
            strength_A = strength['A'][0]
            max_strength_A = strength['A'][1]
            strength_B = strength['B'][0]
            max_strength_B = strength['B'][1]
            strength_queue.task_done()
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        log("主任务已取消")
    finally:
        # 优雅关闭服务器
        log("正在关闭HTTP服务器...")
        stop_event.set()  # 通知所有任务停止

        # 等待所有任务完成
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # 停止服务器
        if site:
            await site.stop()
        if runner:
            await runner.cleanup()

        log("HTTP服务器已关闭")
async def stop():
    if stop_event:
        stop_event.set()
        log("监听已关闭")