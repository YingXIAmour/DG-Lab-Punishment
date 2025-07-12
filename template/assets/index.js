// 轮询获取日志数据
function pollLogData() {
    setInterval(() => {
        fetch('http://127.0.0.1:8000/log') // 假设日志数据的接口地址为 /log
          .then(response => response.text())
          .then(data => {
                const logInput = document.getElementById('log');
                logInput.value = data;
                // 滚动到文本框的最底部
                logInput.scrollTop = logInput.scrollHeight;
            })
          .catch(error => {
                console.error('获取日志数据出错:', error);
            });
    }, 1000); // 每 1 秒轮询一次
}
var server = 'start';
var client = 'start';
var sever_status = document.getElementById('server_status');
var client_status = document.getElementById('client_status');
// 刷新页面数据函数
function refreshPage() {
    fetch('/active')
      .then(response => response.json())
      .then(data => {
            if (data.server === "running"){
                server_status.textContent = "运行中";
                server_status.style.color = "green";
                document.getElementById('server').textContent = "关闭服务端";
                server = 'stop';
            }
            if (data.client === "running"){
                server_status.textContent = "运行中";
                server_status.style.color = "green";
                document.getElementById('client').textContent = "关闭客户端";
                client = 'stop';
            }
            console.log('Test:', data);
        });
    fetch('/version')
      .then(response => response.json())
      .then(data => {
            document.getElementById('version').innerHTML = data.version;
        });
    fetch('/module')
      .then(response => response.json())
      .then(data => {
            if (Array.isArray(data)) {
                const moduleTable = document.getElementById('module-table');
                const tbody = moduleTable.getElementsByTagName('tbody')[0];
                tbody.innerHTML = ''; // 清空表格内容

                data.forEach(moduleName => {
                    const row = tbody.insertRow();
                    const moduleCell = row.insertCell(0);
                    const actionCell = row.insertCell(1);

                    moduleCell.textContent = moduleName;

                    // 创建启动/停止按钮
                    const startStopButton = document.createElement('button');
                    startStopButton.textContent = `启动`;
                    startStopButton.dataset.moduleName = moduleName;
                    startStopButton.dataset.isRunning = false;

                    startStopButton.addEventListener('click', () => {
                        const isRunning = startStopButton.dataset.isRunning === 'true';
                        const action = isRunning ? 'stop' : 'start';
                        const requestData = {
                            action: `${action}_module`,
                            module_name: moduleName
                        };

                        // 提交启动/停止模块请求
                        fetch('http://127.0.0.1:8000/client', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(requestData)
                        })
                          .then(response => response.json())
                          .then(result => {
                                if (result.code == 200){
                                    sweetAlert("成功！",result.message,"success");
                                    // 更新按钮状态
                                    startStopButton.dataset.isRunning =!isRunning;
                                    startStopButton.textContent = isRunning ? `启动` : `停止`;
                                }else{
                                    sweetAlert("错误！错误代码："+result.code,result.message,"error")
                                }
                                console.log('启动模块响应结果:', result);

                            })
                          .catch(error => {
                                console.error('启动模块请求出错:', error);
                            });

                        // 向 127.0.0.1:8000/config 发送请求获取配置数据
                        fetch('http://127.0.0.1:8000/config')
                          .then(response => response.json())
                          .then(configData => {
                                const serverIpInput = document.getElementById('serverIp');
                                const serverModeSelect = document.getElementById('serverMode');
                                const clientModeSelect = document.getElementById('clientMode');

                                // 设置服务端 IP 输入框的值
                                if (configData.serverIp) {
                                    serverIpInput.value = configData.serverIp;
                                }

                                // 设置服务端模式选择框的选中项
                                if (configData.serverMode) {
                                    const serverModeOptions = serverModeSelect.options;
                                    for (let i = 0; i < serverModeOptions.length; i++) {
                                        if (serverModeOptions[i].value === configData.serverMode) {
                                            serverModeOptions[i].selected = true;
                                            break;
                                        }
                                    }
                                }

                                // 设置客户端模式选择框的选中项
                                if (configData.clientMode) {
                                    const clientModeOptions = clientModeSelect.options;
                                    for (let i = 0; i < clientModeOptions.length; i++) {
                                        if (clientModeOptions[i].value === configData.clientMode) {
                                            clientModeOptions[i].selected = true;
                                            break;
                                        }
                                    }
                                }
                            })
                          .catch(error => {
                                console.error('获取配置数据出错:', error);
                            });
                    });

                    // 创建卸载按钮
                    const uninstallButton = document.createElement('button');
                    uninstallButton.textContent = '卸载';
                    uninstallButton.addEventListener('click', () => {
                        const requestData = {
                            action: 'uninstall_module',
                            module_name: moduleName
                        };
                        fetch('http://127.0.0.1:8000/client', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(requestData)
                        })
                          .then(response => response.json())
                          .then(result => {
                                console.log('卸载模块响应结果:', result);
                                // 刷新模块列表
                                refreshPage();
                            })
                          .catch(error => {
                                console.error('卸载模块请求出错:', error);
                            });
                    });

                    // 创建重置按钮
                    const resetButton = document.createElement('button');
                    resetButton.textContent = '重置';
                    resetButton.addEventListener('click', () => {
                        const requestData = {
                            action: 'reset_module',
                            module_name: moduleName
                        };
                        fetch('http://127.0.0.1:8000/client', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(requestData)
                        })
                          .then(response => response.json())
                          .then(result => {
                                console.log('重置模块响应结果:', result);
                                // 刷新模块列表
                                refreshPage();
                            })
                          .catch(error => {
                                console.error('重置模块请求出错:', error);
                            });
                    });

                    actionCell.appendChild(startStopButton);
                    actionCell.appendChild(uninstallButton);
                    actionCell.appendChild(resetButton);
                });
            } else {
                console.error('从 /module 接口返回的数据不是列表:', data);
            }
        });
}

// 页面加载完成后刷新数据
window.onload = () => {
    refreshPage();
    pollLogData();
};

// 选项卡切换功能
const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.panel');

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const targetPanelId = tab.dataset.panel;
        const targetPanel = document.getElementById(targetPanelId);

        // 移除所有选项卡和面板的激活状态
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => {
            p.classList.remove('active', 'prev', 'next');
            if (p.id === targetPanelId) {
                p.classList.add('active');
            } else if (Array.from(panels).indexOf(p) < Array.from(panels).indexOf(targetPanel)) {
                p.classList.add('prev');
            } else {
                p.classList.add('next');
            }
        });

        // 添加当前选项卡的激活状态
        tab.classList.add('active');
    });
});

// 获取按钮元素
const button1 = document.getElementById('button1');
const button2 = document.getElementById('button2');
const button_server = document.getElementById('server');
const button_client = document.getElementById('client');


button_server.addEventListener('click', () => {
    const data = {
        action: 'server',
        saso: server
    };
    fetch('http://127.0.0.1:8000/client', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(result => {
            if (result.code === 200){
                if (server === 'start'){
                    server_status.textContent = "运行中";
                    server_status.style.color = "green";
                    button_server.textContent = "关闭服务端";
                    server = 'stop';
                } else if (server === 'stop'){
                    server_status.textContent = "未运行";
                    server_status.style.color = "red";
                    button_server.textContent = "启动服务端";
                    server = 'start';
                }
            }else if (result.code === 400){
                sweetAlert("错误！错误代码："+result.code,result.message,"error")
            }

            console.log('响应结果:', result);
        })
      .catch(error => {
            console.error('请求出错:', error);
        });
});
button_client.addEventListener('click', () => {
    const data = {
        action: 'client',
        saso: client
    };
    fetch('http://127.0.0.1:8000/client', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(result => {
            if (result.code === 200){
                if (client === 'start'){
                    client_status.textContent = "运行中";
                    client_status.style.color = "green";
                    button_client.textContent = "关闭客户端";
                    client = 'stop';
                } else if (client === 'stop'){
                    client_status.textContent = "未运行";
                    client_status.style.color = "red";
                    button_client.textContent = "启动客户端";
                    client = 'start';
                }
            }else if (result.code === 400){
                sweetAlert("错误！错误代码："+result.code,result.message,"error")
            }
            console.log('响应结果:', result);
        })
      .catch(error => {
            console.error('请求出错:', error);
        });
});
// 重载配置文件按钮点击事件
button1.addEventListener('click', () => {
    const data = {
        action: 'reload_main_config'
    };
    fetch('http://127.0.0.1:8000/client', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(result => {
            console.log('响应结果:', result);
        })
      .catch(error => {
            console.error('请求出错:', error);
        });
});

// 保存按钮点击事件
button2.addEventListener('click', () => {
    const serverIp = document.getElementById('serverIp').value;
    const serverMode = document.getElementById('serverMode').value;
    const clientMode = document.getElementById('clientMode').value;
    const data = {
        action: 'set_main_config',
        server_ip: serverIp,
        serverMode: serverMode,
        clientMode: clientMode
    };
    fetch('http://127.0.0.1:8000/client', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
      .then(response => response.json())
      .then(result => {
            console.log('响应结果:', result);
        })
      .catch(error => {
            console.error('请求出错:', error);
        });
});