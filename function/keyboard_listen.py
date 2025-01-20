import time

import keyboard
import json
import os
import sys
import random
name = "按键惩罚"
author = "影曦Amour"
stop_listen = False
MODE_TYPE = ["CONFIG","RANDOM"]
base_dir = None
thread = None
class KeyBindingHandler:
    def __init__(self, client,mode = "CONFIG",key_count = 4):
        self.client = client
        self.listener_running = False
        if mode == MODE_TYPE[0]:#CONFIG-配置文件模式
            self.load_and_bind_key_bindings()
        elif mode == MODE_TYPE[1]:#RANDOM-随机按键模式
            self.random_bind_key_bindings(key_count)
        else:
            raise ValueError("模式错误！按键启动已暂停")
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
            'clientId':"",
            'targetId':"",
            "message":"",
            "time":0
        }
        all_characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789"
        channel = "AB"
        for i in range(key_count):
            random_character = random.choice(all_characters)
            send_channel = random.choice(channel)
            key = all_characters.replace(random_character, '', 1)
            send_data = data
            send_data['message'] = send_channel + ":" + self.ai_wave_data(random.randint(6, 12))
            sned_data['time'] = random.randint(1, 5)
            self.bind_hotkey(key,send_data)
    def bind_hotkey(self, hotkey_str, data):
        """
        使用keyboard库的add_hotkey方法绑定单个热键，当热键触发时调用client.handle_message并传递对应数据
        """
        keyboard.add_hotkey(hotkey_str, lambda: self.client.handle_message(data))
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
def main(client,data):
    global thread
    try:
        thread = KeyBindingHandler(client,data["keyboardMode"],data["keyboard_key_count"])
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