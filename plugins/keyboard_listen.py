import time

import keyboard
import json
import os
import sys
import random
from datetime import datetime
name = "按键惩罚"
author = "影曦Amour"
stop_listen = False
MODE_TYPE = ["CONFIG","RANDOM"]
base_dir = None
thread = None
class KeyBindingHandler:
    def __init__(self, message_queue,mode = "CONFIG",key_count = 4):
        self.message_queue = message_queue
        self.listener_running = False
        self.channel_strength = {
            "A":[0,100],
            "B":[0,100]
        }
        if mode == MODE_TYPE[0]:#CONFIG-配置文件模式
            self.load_and_bind_key_bindings()
        elif mode == MODE_TYPE[1]:#RANDOM-随机按键模式
            self.random_bind_key_bindings(key_count)
        else:
            raise ValueError("模式错误！按键启动已暂停")
    def get_channel_strength(self,strength):
        self.channel_strength = strength
    #配置文件模式加载按键
    def load_and_bind_key_bindings(self):
        """
        从配置文件加载键绑定信息，并进行热键绑定
        """
        json_file_path = os.path.join(base_dir, "key_bindings.json")
         # 可根据实际情况修改文件路径
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as file:
                data_list = json.loads(file.read())
                if isinstance(data_list, list):
                    for item in data_list:
                        if isinstance(item, dict):
                            hotkey_str = item.get('key')
                            data = item.get('data')
                            self.bind_hotkey(hotkey_str, data)
    #随机按键模式加载按键
    def random_bind_key_bindings(self,key_count):
        data = {
            'type':"clientMsg",
            "message":"",
            "punish_time":0,
            "channel":"",
            "strength":0
        }
        all_characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"
        type = ['clientMsg',1,2,3]
        channel = "AB"
        for i in range(key_count):
            send_type = random.choice(type)
            send_channel = random.choice(channel)

            send_strength = random.randint(0,self.channel_strength[send_channel][1])

            random_character = random.choice(all_characters)

            key = all_characters.replace(random_character, '', 1)
            send_data = data
            send_data['type'] = send_type
            send_data['message'] = self.ai_wave_data(random.randint(6, 12))
            send_data['punish_time'] = random.randint(1, 5)
            send_data['channel'] = send_channel
            send_data['strength'] = send_strength
            self.bind_hotkey(key,send_data)
    def bind_hotkey(self, hotkey_str, data):
        """
        使用keyboard库的add_hotkey方法绑定单个热键，当热键触发时调用client.handle_message并传递对应数据
        """
        if data['type'] == "clientMsg":
            send_data = {
                'action':"send_pluses",
                'pluses':data['message'],
                'punish_time':data['punish_time'],
                'channel':data['channel']
            }
            keyboard.add_hotkey(hotkey_str, lambda: self.message_queue.put(send_data))
        elif data['type'] == 1:
            send_data = {
                'action':"strength_add",
                'channel':data['channel'],
                'strength':data['strength']
            }
            keyboard.add_hotkey(hotkey_str, lambda: self.message_queue.put(send_data))
        elif data['type'] == 2:
            send_data = {
                'action':"strength_down",
                'channel':data['channel'],
                'strength':data['strength']
            }
            keyboard.add_hotkey(hotkey_str, lambda: self.message_queue.put(send_data))
        elif data['type'] == 3:
            send_data = {
                'action':"set_strength",
                'channel':data['channel'],
                'strength':data['strength']
            }
            keyboard.add_hotkey(hotkey_str, lambda: self.message_queue.put(send_data))
        else:
            send_data = {
                'action':"logger",
                'message':"[Keyboard_listen] 发现无效类型数据"
            }
            self.message_queue.put(send_data)
    def start_listening(self):
        """
        启动键盘监听
        """
        keyboard.hook(self._keyboard_event_handler)

    @staticmethod
    def stop_listening():
        """
        停止键盘监听
        """
        keyboard.unhook_all()

    def _keyboard_event_handler(self, event):
        """
        键盘事件处理函数，目前为空实现，可根据需要添加额外的键盘事件处理逻辑
        """
        pass

    def convert_wave_to_hex_list_str(self, wave_data):
        """
        根据第二篇文档的波形转换规则，将输入的波形数据转换为符合第一篇文档要求的十六进制字符串列表格式（如 A:["hex_str_1","hex_str_2",...]）
        wave_data格式为[(freq, strength),...]，每个元素为一个包含频率和强度的元组
        """
        hex_str_list = []
        result = ''
        for freq, strength in wave_data:
            # 对频率进行转换
            converted_freq = self.convert_wave_frequency(freq)
            # 构建单个波形数据的字节形式（频率和强度各4个字节重复，符合文档要求）
            freq_bytes = bytes([converted_freq] * 4)
            strength_bytes = bytes([strength] * 4)
            # 拼接频率和强度字节数据并转换为十六进制字符串
            hex_str = (freq_bytes + strength_bytes).hex().upper()
            hex_str_list.append(hex_str)
        result = result + "".join(hex_str_list)
        return result
        # return f'A:["{"","".join(hex_str_list)}"]'

    @staticmethod
    def convert_wave_frequency(input_freq):
        """
        根据第二篇文档给定的算法将输入的波形频率值转换为符合协议要求的波形频率值
        """
        if 10 <= input_freq <= 100:
            return input_freq
        elif 101 <= input_freq <= 600:
            return (input_freq - 100) // 5 + 100
        elif 601 <= input_freq <= 1000:
            return (input_freq - 600) // 10 + 200
        return 10

    @staticmethod
    def wave_data_list(hex_str):
        grouped_list = [hex_str[i:i + 16] for i in range(0, len(hex_str), 16)]
        return grouped_list  # 返回分组后的列表，方便后续可能的使用（这里暂时没用到返回值）

    def ai_wave_data(self,int_rand):
        wave_data = []
        for i in range(int_rand):
            wave_data.append((random.randint(10,240),random.randint(0,100)))
        hex_list_str_wave_data = str(self.wave_data_list(self.convert_wave_to_hex_list_str(wave_data)))
        return hex_list_str_wave_data
def main(message_queue,data):
    global thread
    try:
        thread = KeyBindingHandler(message_queue,data["keyboardMode"],data["keyboard_key_count"])
        send_data = {
            'action': "logger",
            'log_level': "SUCCESS",
            'message': "[Keyboard_listen] 按键监听已启动"
        }
        message_queue.put(send_data)
        thread.start_listening()

        while not stop_listen:
            pass
    except:
        pass
def stop():
    global stop_listen
    stop_listen = True
    time.sleep(0.5)
    thread.stop_listening()