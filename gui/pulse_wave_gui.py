import tkinter as tk
import tkinter.font as tkFont
import tkinter.messagebox as messagebox
import random
import sys
import os
def resource_path(relative_path):
    """获取资源的绝对路径，用于读取嵌入的文件"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath("..")
    return os.path.join(base_path, relative_path)

class WaveDataInputAndConversion:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("郊狼 波形生成器")
        self.root.iconbitmap(resource_path("../DG-LAB.ico"))
        self.root.resizable(False, False)
        # 统一字体设置
        self.my_font = tkFont.Font(family="Arial", size=12)

        # 用于存储用户输入的波形数据，格式为[(freq, strength),...]
        self.wave_data_user = []

        # 初始化界面组件
        self.init_widgets()

    def init_widgets(self):
        # 标签和文本框用于输入频率
        label_freq = tk.Label(self.root, text="频率:", font=self.my_font)
        label_freq.grid(row=0, column=0, padx=5, pady=5)
        self.entry_freq = tk.Entry(self.root, font=self.my_font)
        self.entry_freq.insert(0, "请输入频率")
        self.entry_freq.bind("<FocusIn>", lambda event: self.entry_freq.delete('0', 'end') if self.entry_freq.get() == "请输入频率" else None)
        self.entry_freq.grid(row=0, column=1, padx=5, pady=5)

        # 标签和文本框用于输入强度
        label_strength = tk.Label(self.root, text="强度:", font=self.my_font)
        label_strength.grid(row=1, column=0, padx=5, pady=5)
        self.entry_strength = tk.Entry(self.root, font=self.my_font)
        self.entry_strength.insert(0, "请输入强度")
        self.entry_strength.bind("<FocusIn>", lambda event: self.entry_strength.delete('0', 'end') if self.entry_strength.get() == "请输入强度" else None)
        self.entry_strength.grid(row=1, column=1, padx=5, pady=5)

        # 列表框用于展示已添加的波形数据，添加背景颜色和边框使其更美观
        self.listbox_data = tk.Listbox(self.root, bg="lightgray", bd=2, font=self.my_font)
        self.listbox_data.grid(row=2, column=0, rowspan=5, sticky="ns", padx=5, pady=5)

        # 按钮用于添加数据到wave_data_user列表
        button_add = tk.Button(self.root, text="添加数据", font=self.my_font, command=self.add_data)
        button_add.grid(row=2, column=1, padx=5, pady=5)

        # 按钮用于删除选中的数据
        button_delete = tk.Button(self.root, text="删除选中数据", font=self.my_font, command=self.delete_selected_data)
        button_delete.grid(row=3, column=1, padx=5, pady=5)

        # 按钮用于修改选中的数据
        button_modify = tk.Button(self.root, text="修改选中数据", font=self.my_font, command=self.modify_selected_data)
        button_modify.grid(row=4, column=1, padx=5, pady=5)

        # 按钮用于进行转换并展示结果
        button_convert = tk.Button(self.root, text="转换并展示", font=self.my_font, command=self.convert_and_display)
        button_convert.grid(row=5, column=1, padx=5, pady=5)

        # 按钮用于进行转换并展示结果
        button_convert = tk.Button(self.root, text="随机生成波形", font=self.my_font, command=self.ai_wave_data)
        button_convert.grid(row=6, column=1, padx=5, pady=5)
        # 文本框用于显示转换后的结果
        self.result_text_widget = tk.Text(self.root, height=10, width=50, font=self.my_font)
        self.result_text_widget.grid(row=7, column=0, columnspan=2, padx=5, pady=5)
    def ai_wave_data(self):
        wave_data = []
        for i in range(12):
            wave_data.append((random.randint(10,240),random.randint(0,100)))
        hex_list_str_wave_data = str(self.wave_data_list(self.convert_wave_to_hex_list_str(wave_data)))
        self.result_text_widget.delete(1.0, tk.END)
        self.result_text_widget.insert(tk.END, hex_list_str_wave_data)
    def add_data(self):
        freq_text = self.entry_freq.get()
        strength_text = self.entry_strength.get()
        try:
            freq = int(freq_text)
            strength = int(strength_text)
            if 10 <= freq <= 240 and 0 <= strength <= 100:
                self.wave_data_user.append((freq, strength))
                self.update_listbox()
                self.entry_freq.delete(0, tk.END)
                self.entry_strength.delete(0, tk.END)
            else:
                messagebox.showwarning("输入范围错误", "频率需在10 - 240之间，强度需在0 - 100之间，请重新输入！")
        except ValueError:
            messagebox.showwarning("输入类型错误", "请输入整数类型的频率和强度值")

    def update_listbox(self):
        self.listbox_data.delete(0, tk.END)
        for data in self.wave_data_user:
            self.listbox_data.insert(tk.END, f"({data[0]}, {data[1]})")

    def delete_selected_data(self):
        selected_index = self.listbox_data.curselection()
        if selected_index:
            index = selected_index[0]
            del self.wave_data_user[index]
            self.update_listbox()

    def modify_selected_data(self):
        selected_index = self.listbox_data.curselection()
        if selected_index:
            index = selected_index[0]
            freq_text = self.entry_freq.get()
            strength_text = self.entry_strength.get()
            try:
                freq = int(freq_text)
                strength = int(strength_text)
                self.wave_data_user[index] = (freq, strength)
                self.update_listbox()
                self.entry_freq.delete(0, tk.END)
                self.entry_strength.delete(0, tk.END)
            except ValueError:
                messagebox.showwarning("输入类型错误", "请输入整数类型的频率和强度值")

    def convert_and_display(self):
        if self.wave_data_user:
            hex_list_str_wave_data = str(self.wave_data_list(self.convert_wave_to_hex_list_str(self.wave_data_user)))
            self.result_text_widget.delete(1.0, tk.END)
            self.result_text_widget.insert(tk.END, hex_list_str_wave_data)
        else:
            print("请先添加数据")

    def show_grouped_result(self):
        if self.wave_data_user:
            hex_list_str_wave_data = self.convert_wave_to_hex_list_str(self.wave_data_user)
            grouped_list = self.wave_data_list(hex_list_str_wave_data)
            # 可以在这里添加代码将grouped_list展示在界面上，比如弹出新窗口展示等，目前只是在控制台打印
        else:
            print("请先添加数据")

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

    def convert_wave_frequency(self, input_freq):
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

    def wave_data_list(self, hex_str):
        grouped_list = [hex_str[i:i + 16] for i in range(0, len(hex_str), 16)]
        return grouped_list  # 返回分组后的列表，方便后续可能的使用（这里暂时没用到返回值）

    def run(self):
        self.root.mainloop()
if __name__ == "__main__":
    app = WaveDataInputAndConversion()
    app.run()