import requests
import zipfile
import os
import shutil
import sys
import psutil
import tkinter as tk
from tkinter import messagebox


class Updater:
    def __init__(self, local_version=None, version_url=None, update_package_url=None):
        self.LOCAL_VERSION = local_version if local_version else "1.0"
        self.VERSION_URL = version_url if version_url else "https://example.com/version.json"
        self.UPDATE_PACKAGE_URL = update_package_url if update_package_url else "https://example.com/update_package.zip"
        self.UPDATE_PACKAGE_PATH = "update_package.zip"

    def get_web_version(self):
        try:
            response = requests.get(self.VERSION_URL)
            response.raise_for_status()
            data = response.json()
            return data.get("version")
        except requests.RequestException as e:
            print(f"请求版本信息时出错: {e}")
        except ValueError as e:
            print(f"解析版本信息时出错: {e}")
        return None

    def download_update_package(self):
        try:
            response = requests.get(self.UPDATE_PACKAGE_URL, stream=True)
            response.raise_for_status()
            with open(self.UPDATE_PACKAGE_PATH, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
            print("更新包下载完成")
            return True
        except requests.RequestException as e:
            print(f"下载更新包时出错: {e}")
        return False

    def extract_update_package(self):
        try:
            with zipfile.ZipFile(self.UPDATE_PACKAGE_PATH, 'r') as zip_ref:
                zip_ref.extractall('.')
            print("更新包解压完成，文件已覆盖")
            os.remove(self.UPDATE_PACKAGE_PATH)
            return True
        except zipfile.BadZipFile as e:
            print(f"解压更新包时出错: {e}")
        except Exception as e:
            print(f"解压更新包时出现未知错误: {e}")
        return False

    def check_and_update(self):
        web_version = self.get_web_version()
        if web_version is None:
            return
        if web_version > self.LOCAL_VERSION:
            root = tk.Tk()
            root.withdraw()
            result = messagebox.askyesno("更新提示", f"发现新版本: {web_version}，是否更新？")
            if result:
                self.close_main_exe()
                if self.download_update_package():
                    self.extract_update_package()
        else:
            print("当前已是最新版本，无需更新")

    def close_main_exe(self):
        main_exe_name = "main.exe"
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] == main_exe_name:
                try:
                    proc.terminate()
                    proc.wait()
                    print(f"{main_exe_name} 已关闭")
                except psutil.NoSuchProcess:
                    print(f"{main_exe_name} 进程不存在")
                except psutil.AccessDenied:
                    print(f"无法关闭 {main_exe_name} 进程，权限不足")


if __name__ == "__main__":
    local_version = None
    version_url = None
    update_package_url = None

    for i, arg in enumerate(sys.argv):
        if arg == "--local-version" and i + 1 < len(sys.argv):
            local_version = sys.argv[i + 1]
        elif arg == "--version-url" and i + 1 < len(sys.argv):
            version_url = sys.argv[i + 1]
        elif arg == "--update-package-url" and i + 1 < len(sys.argv):
            update_package_url = sys.argv[i + 1]

    updater = Updater(local_version, version_url, update_package_url)
    updater.check_and_update()