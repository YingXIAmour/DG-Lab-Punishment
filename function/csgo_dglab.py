import asyncio
import io
import json
import math
import random

import qrcode
import socket
from aiohttp import web
import winreg
import os
import sys
import tkinter as tk
from PIL import Image, ImageTk
from multiprocessing import Process, Queue
from datetime import datetime
name = "CSGO-受伤惩罚"
author = "RicoShot"

base_dir = None
PULSE_DATA = None
stop_event = None
def get_cs2_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\Valve\Steam', 0, winreg.KEY_READ)
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

health = 100
max_strength_A = 0
max_strength_B = 0
strength_A = 0
strength_B = 0

async def handle_post_request(request):
    global health
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
                if now_health < health:
                    data_a = math.ceil((100 - now_health) / 100 * max_strength_A)
                    data_b = math.ceil((100 - now_health) / 100 * max_strength_B)
                    log(f"玩家生命值减少: {health} -> {now_health}")
                    # 这里多写一层判断，判断是否被烧伤
                    if data["player"]["state"]["burning"] > 0:
                        waveform_data = {"type": "pluse", "data": PULSE_DATA["烧伤"],"time":1}
                        await queue.put(waveform_data)
                    else:
                        waveform_data = {"type": "pluse", "data": PULSE_DATA["受伤"],"time":1}
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
                # 傻瓜蛋！
                if flash > 0:
                    data_a = math.ceil(max_strength_A*0.3)
                    data_b = math.ceil(max_strength_B*0.3)
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
                    waveform_data = {"type": "pluse", "data": PULSE_DATA["傻瓜蛋"],"time":3}
                    await queue.put(waveform_data)
                if smoke > 0:
                    data_a = math.ceil(max_strength_A * 0.05 + strength_A)
                    data_b = math.ceil(max_strength_B * 0.05 + strength_B)
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
                    random_int = str(random.randint(1, 5))
                    waveform_data = {"type": "pluse", "data": PULSE_DATA["烟雾弹"][random_int],"time":1}
                    await queue.put(waveform_data)
                # 血量归零以及回合结束重置强度以及血量
                if now_health == 0:
                    health = 100
                    waveform_data = {"type": "pluse", "data": PULSE_DATA["死亡"],"time":8}
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
    except Exception as e:
        log(f"处理POST请求时出错: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=500)


async def send_waveform_on_queue_change(queue, client):
    while True:
        waveform_data = await queue.get()
        types = waveform_data["type"]
        data = waveform_data["data"]
        time = waveform_data.get("time") if waveform_data.get("time") is not None else 5
        if types == "pluse":
            send_data = {'type': "clientMsg", "clientId": "", "targetId": "", "time": time,
                         'message': "A:{}".format(str(data)),"channel":"A"}
            client.handle_message(send_data)
            send_data['channel'] = "B"
            send_data['message'] = "B:{}".format(str(data))
            client.handle_message(send_data)
        elif types == "strlup":
            chose = waveform_data["chose"]
            if chose == "a":
                client.set_strength("A",data)
            if chose == "b":
                client.set_strength("B",data)
        elif types == "strlse":
            client.set_strength("A",0)
            client.set_strength("B",0)
        elif types == "strlst":
            client.set_strength("A",data)
            client.set_strength("B",data)
        else:
            log("接收到未知类型数据，请检查")

def log(msg_a):
    message = '[{}] CSGOListen: {}'.format(datetime.now().strftime('%H:%M:%S'), msg_a)
    print(message)

async def main(client,data):
    global max_strength_A,max_strength_B,strength_A,strength_B,PULSE_DATA,stop_event
    stop_event = asyncio.Event()
    conf_json = os.path.join(base_dir, "config.json")
    # 读取 PULSE_DATA 从 JSON 文件
    with open(conf_json, "r", encoding="utf-8") as file:
        config = json.load(file)
        PULSE_DATA = config["pulse_data"]

    queue = asyncio.Queue()

    app = web.Application()
    app["queue"] = queue
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
        send_waveform_on_queue_change(queue, client)
    )
    while not stop_event.is_set():
        strength = client.get_channel_strength()
        strength_A = strength['A'][0]
        max_strength_A = strength['A'][1]
        strength_B = strength['B'][0]
        max_strength_B = strength['B'][1]
        await asyncio.sleep(1)
async def stop():
    stop_event.set()
    log("监听已关闭")