import tkinter as tk
from tkinter import ttk

class ChannelWindows:
    def __init__(self,ico_file):
        self.root = tk.Tk()
        self.root.title = ""
        self.root.iconbitmap(ico_file)
        #self.root.overrideredirect(True)
        self.root.geometry("280x50")
        self.root.attributes('-alpha', 0.9)
        self.root.wm_attributes("-topmost", True)
        screen_width = self.root.winfo_screenwidth()
        # 计算窗口位置
        x = screen_width - 330  # x 轴往左 50（窗口宽度为 300）
        y = 100  # y 轴往下 100
        self.root.geometry(f"+{x}+{y}")
        self.start_x = 0
        self.start_y = 0
        self.offset_x = 0
        self.offset_y = 0
        self.root.bind('<Button-1>', self.click_window)
        self.root.bind('<B1-Motion>', self.drag_window)

        self.strength_A_text = tk.Label(self.root,text="通道A强度：")
        self.strength_A_text.grid(row=0,column=0,sticky="w")
        #进度条A-A强度
        self.progressbar_A = ttk.Progressbar(self.root, orient='horizontal', length=200, mode='determinate')
        self.progressbar_A.grid(row=0,column=1)

        self.strength_B_text = tk.Label(self.root, text="通道B强度：")
        self.strength_B_text.grid(row=1, column=0, sticky="w")
        #进度条B-B强度
        self.progressbar_B = ttk.Progressbar(self.root,orient="horizontal",length=200,mode="determinate")
        self.progressbar_B.grid(row=1,column=1)
        self.root.grid_columnconfigure(1, weight=1)
    def start(self):
        self.root.mainloop()
    def click_window(self, event):
        self.start_x = event.x
        self.start_y = event.y

    def drag_window(self, event):
        x = self.root.winfo_pointerx() - self.start_x
        y = self.root.winfo_pointery() - self.start_y
        self.root.geometry(f"+{x}+{y}")

    def update_progress(self,channel,value,value_max):
        if channel == "A":
            self.strength_A_text.config(text="通道A强度："+str(value))
            new_value = round(value / value_max * 100)
            self.progressbar_A['value'] = new_value
        elif channel == "B":
            self.strength_B_text.config(text="通道B强度："+str(value))
            new_value = round(value / value_max * 100)
            self.progressbar_B['value'] = new_value

    def close(self):
        self.root.destroy()
