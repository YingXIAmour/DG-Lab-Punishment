import queue
import tkinter as tk
from tkinter import messagebox
import threading
import asyncio



class GUI:
    def __init__(self):
        self.client = None
        self.modules = dict()
        self.start_data = dict()
        self.thread_all = dict()
        self.root = None
        self.is_hidden = False
        self.button = dict()
        self.button_grid = dict()
        self.message_queue = None
        self.grid_count = {
            "now": [1, 0],
            "max": [10, 10]
        }
    def get_is_hidden(self):
        return self.is_hidden
    def create_gui(self):
        self.root = tk.Tk()
        self.root.title("功能页面")
        self.root.wm_attributes('-toolwindow', True)
        label = tk.Label(self.root, text="功能列表")
        label.grid(row=0, column=0)
        for module_name, module in self.modules.items():
            button_start_name = 'start-{}'.format(module_name)
            button_stop_name = "stop-{}".format(module_name)

            def button_callback(temp_module=module, temp_module_name=module_name, bt_start_name=button_start_name, bt_stop_name=button_stop_name):
                return_queue = queue.Queue()
                send_data = {
                    "action":"start_module",
                    'module_name':temp_module_name,
                    'queue':return_queue

                }
                self.message_queue.put(send_data)
                try:
                    message = return_queue.get(timeout=2)
                    if message['code'] != 200:
                        messagebox.showwarning("错误","启动失败。原因：{}".format(message['message']))
                        return
                    else:
                        # self.start_module_in_thread(temp_module, temp_module_name)
                        self.button[bt_start_name].grid_forget()
                        grid_row = self.button_grid[bt_start_name]["row"]
                        grid_column = self.button_grid[bt_start_name]["column"]
                        self.button[bt_stop_name].grid(row=grid_row, column=grid_column)
                except:
                    messagebox.showerror("错误！","主程序未响应")


            def stop_button_callback(temp_module=module, temp_module_name=module_name, bt_start_name=button_start_name,
                                  bt_stop_name=button_stop_name):
                return_queue = queue.Queue()
                send_data = {
                    "action": "stop_module",
                    'module_name': temp_module_name,
                    'queue': return_queue
                }
                self.message_queue.put(send_data)
                try:
                    message = return_queue.get(timeout=2)
                    if message['code'] != 200:
                        messagebox.showwarning("错误","关闭失败。原因：{}".format(message['message']))
                        return
                    else:
                        self.button[bt_stop_name].grid_forget()
                        grid_row = self.button_grid[bt_stop_name]["row"]
                        grid_column = self.button_grid[bt_stop_name]["column"]
                        self.button[bt_start_name].grid(row=grid_row, column=grid_column)
                except:
                    messagebox.showerror("错误！","主程序未响应")



            self.button.update({button_start_name: None, button_stop_name: None})
            self.button[button_start_name] = tk.Button(self.root, text="启动 {}".format(module.name), command=button_callback, name=button_start_name,
                                                width=20, height=1)
            self.button[button_stop_name] = tk.Button(self.root, text="关闭 {}".format(module.name), command=stop_button_callback,
                                               name=button_stop_name, width=20, height=1)
            if self.grid_count["now"][0] <= self.grid_count["max"][0]:
                row = self.grid_count["now"][0] + 1
                self.grid_count["now"][0] += 1
                column = self.grid_count["now"][1]
            else:
                row = 1
                self.grid_count["now"][0] = 1
                column = self.grid_count["now"][1] + 1
                self.grid_count["now"][1] += 1
            self.button[button_start_name].grid(row=row, column=column)
            self.button_grid.update({button_start_name: {"row": row, "column": column}})
            self.button_grid.update({button_stop_name: {"row": row, "column": column}})
        weight = (self.grid_count['now'][1] + 1) * 150
        height = (self.grid_count['now'][0]) * 40 if self.grid_count['now'][1] == 0 else 1000
        size = "{}x{}".format(str(weight), str(height))
        self.root.geometry(size)
        row_count = self.grid_count['now'][0] if self.grid_count['now'][1] == 0 else 10
        column_count = self.grid_count['now'][1]
        # 设置行和列的权重，使按钮在窗口大小变化时能自动调整位置并保持居中
        if row_count > 1:
            for i in range(row_count):
                self.root.grid_rowconfigure(i, weight=1)
        if column_count > 0:
            for j in range(column_count):
                self.root.grid_columnconfigure(j, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        if not self.is_hidden:
            self.root.withdraw()
            self.is_hidden = True

    def show_window(self):
        if self.is_hidden:
            self.root.deiconify()
            self.is_hidden = False

    def stop(self):
        for module_name, module in self.modules.items():
            if self.thread_all[module_name] is not None:
                self.stop_module_in_thread(module, module_name)
        self.root.destroy()

def main(tmp_client, data):
    gui = GUI()
    gui.client = tmp_client
    gui.modules = data['modules']
    gui.thread_all = data['thread_all']
    gui.start_data = data['start_data']
    gui.create_gui()