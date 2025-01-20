import tkinter as tk
from tkinter import ttk


class TableWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("表格操作窗口")

        # 创建表格样式的文本框（Treeview组件）
        self.tree = ttk.Treeview(self.root, columns=("ID", "TargetId"), show="headings")
        self.tree.heading("ID", text="ID")
        self.tree.heading("TargetId", text="TargetId")
        self.tree.pack(pady=10)

        # 创建添加按钮和删除按钮
        self.add_button = tk.Button(self.root, text="添加", command=self.add_row)
        self.add_button.pack(side=tk.LEFT, padx=10, pady=10)
        self.delete_button = tk.Button(self.root, text="断开连接", command=self.delete_row)
        self.delete_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.row_id = 1  # 用于自动分配ID

    def start(self):
        self.root.mainloop()

    def add_row(self):
        """添加一行数据到表格"""
        self.tree.insert("", tk.END, values=(self.row_id, ""))
        self.row_id += 1

    def delete_row(self, value=None, by="ID"):
        """
        根据指定的方式删除表格中的行
        :param value: 要删除行对应的ID或者TargetId的值（如果不传入此参数，则按默认选中行删除）
        :param by: 删除的依据，可选值为"ID"、"TargetId"，默认是"ID"。如果不传入此参数，也按默认选中行删除
        """
        if value is None:
            # 如果没有传入参数，按照原来的方式删除选中的行
            selected_item = self.tree.selection()
            if selected_item:
                for item in selected_item:
                    self.tree.delete(item)
            return

        if by == "ID":
            for item in self.tree.get_children():
                item_id = self.tree.item(item)["values"][0]
                if item_id == value:
                    self.tree.delete(item)
        elif by == "TargetId":
            for item in self.tree.get_children():
                item_target_id = self.tree.item(item)["values"][1]
                if item_target_id == value:
                    self.tree.delete(item)
if __name__ == "__main__":
    table_win = TableWindow()
    table_win.start()