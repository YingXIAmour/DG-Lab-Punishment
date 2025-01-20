import sys
import json
import platform
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
    QTreeWidgetItem, QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton
)
from PyQt5.QtGui import QIcon
# 定义操作类型与对应值的映射字典
ws_type = {
    '强度减少': 1,
    '强度增加': 2,
    '强度设置固定值': 3,
    '设置波形/信息': 'clientMsg'
}

class KeyBindingGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.file_path = '../data/key_bindings.json'
        self.existing_data = self.load_json_file()
        self.load_data()

    @staticmethod
    def start():
        app = QApplication(sys.argv)
        gui = KeyBindingGUI()
        gui.show()
        app.exec_()  # 不再使用 sys.exit，避免影响外部的Tkinter主循环

    def initUI(self):
        self.setWindowTitle("郊狼 按键绑定配置")
        self.setGeometry(100, 100, 1368, 621)
        self.setWindowIcon(QIcon('../data/DG-LAB.ico'))

        main_layout = QVBoxLayout()

        # 设置列表
        self.table = QTreeWidget()
        self.table.setColumnCount(6)
        self.table.setHeaderLabels(['ID', '按键', '通道', '操作类型', '强度值', '波形行/信息'])
        self.table.itemDoubleClicked.connect(self.select_row)

        main_layout.addWidget(self.table, 2)

        # Right side layout
        right_layout = QVBoxLayout()

        key_id = QLabel("ID：")
        self.key_id_entry = QLineEdit()
        right_layout.addWidget(key_id)
        right_layout.addWidget(self.key_id_entry)

        # Key input
        key_label = QLabel("按键:")
        self.key_entry = QLineEdit()
        right_layout.addWidget(key_label)
        right_layout.addWidget(self.key_entry)

        # Message input
        message_label = QLabel("波形行:")
        self.message_entry = QTextEdit()
        right_layout.addWidget(message_label)
        right_layout.addWidget(self.message_entry)

        # Strength input
        strength_label = QLabel("值 (非必须):")
        self.strength_entry = QLineEdit()
        right_layout.addWidget(strength_label)
        right_layout.addWidget(self.strength_entry)

        # Type input
        type_label = QLabel("类型:")
        self.type_combobox = QComboBox()
        self.type_combobox.addItems(['强度减少', '强度增加', '强度设置固定值', '设置波形/信息'])
        right_layout.addWidget(type_label)
        right_layout.addWidget(self.type_combobox)

        # Channel input
        channel_label = QLabel("通道:")
        self.channel_combobox = QComboBox()
        self.channel_combobox.addItems(['A', 'B'])
        right_layout.addWidget(channel_label)
        right_layout.addWidget(self.channel_combobox)

        # Submit button
        self.submit_button = QPushButton("添加")
        self.submit_button.clicked.connect(self.submit_data)
        right_layout.addWidget(self.submit_button)

        # Load, Save, Delete buttons
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("加 载")
        self.load_button.clicked.connect(self.load_data)
        button_layout.addWidget(self.load_button)

        self.save_button = QPushButton("保 存")
        self.save_button.clicked.connect(self.save_selected_row)
        button_layout.addWidget(self.save_button)

        self.delete_button = QPushButton("删 除")
        self.delete_button.clicked.connect(self.delete_selected_row)
        button_layout.addWidget(self.delete_button)

        # 新增的显示图片按钮
        self.show_image_button = QPushButton("显示二维码图片")
        self.show_image_button.clicked.connect(self.show_image)
        button_layout.addWidget(self.show_image_button)

        right_layout.addLayout(button_layout)

        main_layout.addLayout(right_layout, 1)
        self.setLayout(main_layout)

    def submit_data(self):
        # 获取数据
        key_id = self.key_id_entry.text()
        key = self.key_entry.text()
        message = self.message_entry.toPlainText()
        strength = self.strength_entry.text()
        type_value_str = self.type_combobox.currentText()
        channel = self.channel_combobox.currentText()

        # 判断type_value_str是否为1、2、3并转换为int类型
        type_value = type_value_str

        data_dict = {
            "type": type_value,
            "message": message,
            "channel": channel,
            "clientId": "",
            "targetId": ""
        }
        if strength:
            data_dict["strength"] = int(strength)

        new_data = {'id': int(key_id), 'key': key, 'data': data_dict}

        self.existing_data.append(new_data)

        self.save_json_file(self.existing_data)
        self.load_data()

    def load_data(self):
        self.existing_data = self.load_json_file()
        data = self.existing_data
        self.table.clear()
        for item in data:
            data_str = item['data']
            for key, value in ws_type.items():
                if data_str['type'] == value:
                    data_str['type'] = key
                    break
            tree_item = QTreeWidgetItem([str(item['id']), item['key'], data_str['channel'], data_str['type'],
                                         str(data_str.get('strength') if data_str.get('strength') else ''),
                                         data_str['message']])
            self.table.addTopLevelItem(tree_item)

    def select_row(self, item, column):
        selected_item = self.table.currentItem()
        if selected_item:
            key_id = selected_item.text(0)
            key = selected_item.text(1)
            channel = selected_item.text(2)
            type_value = selected_item.text(3)
            strength = selected_item.text(4)
            message = selected_item.text(5)

            self.key_id_entry.setText(key_id)
            self.key_entry.setText(key)
            self.message_entry.setPlainText(message)
            self.strength_entry.setText(str(strength))
            self.channel_combobox.setCurrentText(channel)

    def save_selected_row(self):
        selected_item = self.table.currentItem()
        if selected_item:
            key_id = self.key_id_entry.text()
            key = self.key_entry.text()
            new_message = self.message_entry.toPlainText()
            new_strength = self.strength_entry.text()
            new_type_str = self.type_combobox.currentText()
            new_type = new_type_str
            new_channel = self.channel_combobox.currentText()

            data_dict = {'type': new_type, 'message': new_message, 'strength': int(new_strength) if new_strength!= '' else '',
                         'channel': new_channel,
                         'clientId': '', 'targetId': ''}

            i = 0
            for item in self.existing_data:
                if item['id'] == int(key_id):
                    self.existing_data[i]['key'] = key
                    self.existing_data[i]['data'] = data_dict
                    break
                else:
                    i += 1
            self.save_json_file(self.existing_data)
            self.load_data()

    def delete_selected_row(self):
        selected_item = self.table.currentItem()
        if selected_item:
            key_id = selected_item.text(0)

            existing_data = self.load_json_file()
            new_data = [item for item in existing_data if item['id']!= key_id]

            self.save_json_file(new_data)
            self.load_data()

    def load_json_file(self):
        try:
            with open(self.file_path, 'r') as file:
                data_list = json.load(file)
                # 获取ws_type字典的所有键值对，方便后续查找对应关系
                ws_type_items = ws_type.items()

                data_list = [
                    {**item, 'data': {
                        **item['data'],
                        # 查找ws_type中值与当前item['data']['type']相等的键，将其赋值给'type'字段
                        'type': next((k for k, v in ws_type_items if v == item['data']['type']), item['data']['type'])
                    }}
                    if 'data' in item and 'type' in item['data']
                    else item
                    for item in data_list
                ]
                return data_list
        except FileNotFoundError:
            return []

    def save_json_file(self, data):
        """
        将给定的数据保存为JSON格式到指定文件路径中，同时对数据里满足条件的部分做特定处理。
        参数:
        - data: 要保存的数据，期望是一个可序列化为JSON格式的Python对象（比如列表、字典等）。
        """
        try:
            with open(self.file_path, 'w') as file:
                # 检查传入的数据是否是列表类型，若不是则无法按预期处理每个元素，这里可以根据实际需求调整数据类型要求
                if isinstance(data, list):
                    data_list = data
                    # 使用列表推导式来处理data_list中的每个item
                    new_data_list = []
                    for item in data_list:
                        # 先确保item['data']和'type'字段存在，并且'type'的值在ws_type字典的键中，再进行处理
                        if (
                                isinstance(item, dict) and
                                'data' in item and
                                isinstance(item['data'], dict) and
                                'type' in item['data'] and
                                item['data']['type'] in ws_type
                        ):
                            updated_data = {**item['data'], 'type': ws_type[item['data']['type']]}  # 先复制原'data'字典内容
                            updated_item = {**item, 'data': updated_data}  # 复制原item字典内容
                            new_data_list.append(updated_item)
                        else:
                            new_data_list.append(item)  # 如果不满足条件，直接添加原item到新列表
                    data_list = new_data_list
                    json.dump(data_list, file, indent=4)
                    return
                else:
                    print("传入的数据格式不符合预期，期望是列表类型，无法进行保存操作。")
        except FileNotFoundError:
            print(f"指定的文件路径 {self.file_path} 不存在，无法保存文件。")
        except TypeError as e:
            print(f"数据序列化出现类型错误: {e}，可能是数据结构不符合JSON序列化要求。")
        except Exception as e:
            print(f"保存文件时出现其他未知错误: {e}")

    def show_image(self):
        system = platform.system()
        image_path = "../data/qrcode.png"
        try:
            if system == "Windows":
                # 在Windows上使用默认图片查看器打开图片，这里使用start命令
                subprocess.run(['start', '', image_path], shell=True)
            elif system == "Linux":
                # 在Linux上常见的使用xdg-open来调用默认应用打开图片
                subprocess.run(['xdg-open', image_path])
            elif system == "Darwin":
                # 在macOS上使用open命令调用默认应用打开图片
                subprocess.run(['open', image_path])
            else:
                print(f"不支持的操作系统: {system}")
        except FileNotFoundError:
            print("图片文件未找到，请检查路径是否正确。")
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = KeyBindingGUI()
    ex.show()
    sys.exit(app.exec_())