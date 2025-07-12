// assets/main.js
// 轮询获取日志数据
function pollLogData() {
    setInterval(() => {
        fetch('http://127.0.0.1:8000/log')
            .then(response => response.text())
            .then(data => {
                const logInput = document.getElementById('log');
                if (logInput.value !== data) {
                    logInput.value = data;
                    // 滚动到文本框的最底部
                    logInput.scrollTop = logInput.scrollHeight;
                }
            })
            .catch(error => {
                console.error('获取日志数据出错:', error);
                document.getElementById('log_indicator').innerHTML =
                    '<i class="fa fa-exclamation-circle text-red-500 mr-1"></i>日志连接断开';
                showCustomModal({
                    icon: 'error',
                    title: '连接错误',
                    text: '无法获取日志数据，请检查服务器连接'
                });
            });
        fetch('http://127.0.0.1:8000/active')
            .then(response => response.json())
            .then(data => {
                if (data.app_client === "true"){
                    updateStatus(app_client, "已连接", "text-green-500");
                } else {
                    updateStatus(app_client, "未连接", "text-danger");
                }
            })
            .catch(error => {
                console.error('获取APP数据出错:', error);
            });
    }, 1000); // 每 1 秒轮询一次
}

// 全局状态变量
let server = 'start';
let client = 'start';
let app_client = document.getElementById('app_status');
let serverStatus = document.getElementById('server_status');
let clientStatus = document.getElementById('client_status');

// 刷新页面数据函数
function refreshPage() {
    // 获取服务端和客户端状态
    fetch('/active')
        .then(response => response.json())
        .then(data => {
            if (data.server === "running") {
                updateStatus(serverStatus, "运行中", "text-green-500");
                document.getElementById('server').innerHTML = '<i class="fa fa-stop mr-2"></i>关闭服务端';
                server = 'stop';
            } else {
                updateStatus(serverStatus, "未运行", "text-danger");
                document.getElementById('server').innerHTML = '<i class="fa fa-play mr-2"></i>启动服务端';
                server = 'start';
            }

            if (data.client === "running") {
                if (data.app_client === "true"){
                    updateStatus(app_client, "已连接", "text-green-500");
                }
                updateStatus(clientStatus, "运行中", "text-green-500");
                document.getElementById('client').innerHTML = '<i class="fa fa-stop mr-2"></i>关闭客户端';
                client = 'stop';
            } else {
                updateStatus(app_client, "未连接", "text-danger");
                updateStatus(clientStatus, "未运行", "text-danger");
                document.getElementById('client').innerHTML = '<i class="fa fa-play mr-2"></i>启动客户端';
                client = 'start';
            }
            console.log('状态数据:', data);
        })
        .catch(error => {
            console.error('获取状态数据出错:', error);
            updateStatus(serverStatus, "连接失败", "text-danger");
            updateStatus(clientStatus, "连接失败", "text-danger");
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法获取服务状态，请检查服务器连接'
            });
        });

    // 获取版本信息
    fetch('/version')
        .then(response => response.json())
        .then(data => {
            const version = data.version || '未知';
            document.getElementById('version').textContent = version;
            document.getElementById('footer_version').textContent = version;
        })
        .catch(error => {
            console.error('获取版本数据出错:', error);
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法获取版本信息，请检查服务器连接'
            });
        });

    // 获取模块列表
    fetch('/module')
        .then(response => response.json())
        .then(data => {
            if (Array.isArray(data)) {
                const tbody = document.getElementById('module-tbody');
                tbody.innerHTML = ''; // 清空表格内容

                if (data.length === 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="3" class="px-6 py-4 text-center text-neutral-500">
                                没有安装任何模块
                            </td>
                        </tr>
                    `;
                    return;
                }

                data.forEach(moduleName => {
                    const row = tbody.insertRow();
                    row.className = 'hover:bg-gray-50 transition-colors';

                    // 模块名称单元格
                    const moduleCell = row.insertCell(0);
                    moduleCell.className = 'px-6 py-4 whitespace-nowrap text-sm font-medium text-neutral-800';
                    moduleCell.textContent = moduleName;

                    // 状态单元格
                    const statusCell = row.insertCell(1);
                    statusCell.className = 'px-6 py-4 whitespace-nowrap text-sm text-neutral-500';
                    statusCell.innerHTML = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">未启动</span>';

                    // 操作单元格
                    const actionCell = row.insertCell(2);
                    actionCell.className = 'px-6 py-4 whitespace-nowrap text-sm font-medium';

                    // 创建启动/停止按钮
                    const startStopButton = document.createElement('button');
                    startStopButton.innerHTML = '<i class="fa fa-play mr-1"></i>启动';
                    startStopButton.dataset.moduleName = moduleName;
                    startStopButton.dataset.isRunning = false;
                    startStopButton.className = 'inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 mr-2 transition-all duration-200';

                    startStopButton.addEventListener('click', () => {
                        const isRunning = startStopButton.dataset.isRunning === 'true';
                        const action = isRunning ? 'stop' : 'start';
                        const icon = isRunning ? 'fa-play' : 'fa-stop';
                        const bgColor = isRunning ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700';
                        const text = isRunning ? '启动' : '停止';
                        const statusText = isRunning ? '未启动' : '运行中';
                        const statusClass = isRunning ? 'bg-gray-100 text-gray-800' : 'bg-green-100 text-green-800';

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
                            if (result.code === 200) {
                                showCustomModal({
                                    icon: 'success',
                                    title: '成功',
                                    text: result.message,
                                    showConfirmButton: false,
                                    timer: 1500,
                                    onConfirm: () => setTimeout(hideCustomModal, 1500)
                                });

                                // 更新按钮状态
                                startStopButton.dataset.isRunning = !isRunning;
                                startStopButton.innerHTML = `<i class="fa ${icon} mr-1"></i>${text}`;
                                startStopButton.className = `inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded shadow-sm text-white ${bgColor} focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 mr-2 transition-all duration-200`;

                                // 更新状态标签
                                statusCell.innerHTML = `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusClass}">${statusText}</span>`;
                            } else {
                                showCustomModal({
                                    icon: 'error',
                                    title: `错误代码：${result.code}`,
                                    text: result.message
                                });
                            }
                            console.log('模块操作响应:', result);
                        })
                        .catch(error => {
                            console.error('模块操作请求出错:', error);
                            showCustomModal({
                                icon: 'error',
                                title: '请求失败',
                                text: '无法连接到服务器'
                            });
                        });
                    });

                    // 创建卸载按钮
                    const uninstallButton = document.createElement('button');
                    uninstallButton.innerHTML = '<i class="fa fa-trash mr-1"></i>卸载';
                    uninstallButton.className = 'inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 mr-2 transition-all duration-200';
                    uninstallButton.addEventListener('click', () => {
                        showCustomModal({
                            icon: 'warning',
                            title: '确认卸载?',
                            text: `您确定要卸载模块 "${moduleName}" 吗？`,
                            showCancelButton: true,
                            confirmButtonText: '是的，卸载它!',
                            cancelButtonText: '取消',
                            onConfirm: () => {
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
                                    if (result.code === 200) {
                                        showCustomModal({
                                            icon: 'success',
                                            title: '已卸载!',
                                            text: result.message,
                                            onConfirm: () => {
                                                // 刷新模块列表
                                                refreshPage();
                                            }
                                        });
                                    } else {
                                        showCustomModal({
                                            icon: 'error',
                                            title: '卸载失败',
                                            text: result.message
                                        });
                                    }
                                })
                                .catch(error => {
                                    console.error('卸载模块请求出错:', error);
                                    showCustomModal({
                                        icon: 'error',
                                        title: '请求失败',
                                        text: '无法连接到服务器'
                                    });
                                });
                            }
                        });
                    });

                    // 创建重置按钮
                    const resetButton = document.createElement('button');
                    resetButton.innerHTML = '<i class="fa fa-refresh mr-1"></i>重置';
                    resetButton.className = 'inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded shadow-sm text-white bg-yellow-600 hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 transition-all duration-200';
                    resetButton.addEventListener('click', () => {
                        showCustomModal({
                            icon: 'warning',
                            title: '确认重置?',
                            text: `您确定要重置模块 "${moduleName}" 吗？这将恢复默认设置。`,
                            showCancelButton: true,
                            confirmButtonText: '是的，重置它!',
                            cancelButtonText: '取消',
                            onConfirm: () => {
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
                                    if (result.code === 200) {
                                        showCustomModal({
                                            icon: 'success',
                                            title: '已重置!',
                                            text: result.message,
                                            onConfirm: () => {
                                                // 刷新模块列表
                                                refreshPage();
                                            }
                                        });
                                    } else {
                                        showCustomModal({
                                            icon: 'error',
                                            title: '重置失败',
                                            text: result.message
                                        });
                                    }
                                })
                                .catch(error => {
                                    console.error('重置模块请求出错:', error);
                                    showCustomModal({
                                        icon: 'error',
                                        title: '请求失败',
                                        text: '无法连接到服务器'
                                    });
                                });
                            }
                        });
                    });

                    actionCell.appendChild(startStopButton);
                    actionCell.appendChild(uninstallButton);
                    actionCell.appendChild(resetButton);
                });
            } else {
                console.error('从 /module 接口返回的数据不是列表:', data);
                document.getElementById('module-tbody').innerHTML = `
                    <tr>
                        <td colspan="3" class="px-6 py-4 text-center text-neutral-500">
                            获取模块列表失败
                        </td>
                    </tr>
                `;
                showCustomModal({
                    icon: 'error',
                    title: '数据错误',
                    text: '获取模块列表失败，请检查服务器响应'
                });
            }
        })
        .catch(error => {
            console.error('获取模块数据出错:', error);
            document.getElementById('module-tbody').innerHTML = `
                <tr>
                    <td colspan="3" class="px-6 py-4 text-center text-neutral-500">
                        无法连接到服务器
                    </td>
                </tr>
            `;
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法获取模块列表，请检查服务器连接'
            });
        });
}

// 更新状态显示的辅助函数
function updateStatus(element, text, colorClass) {
    element.textContent = text;
    element.className = colorClass;
}

// 初始化选项卡滑块
function initTabSlider() {
    const tabs = document.querySelectorAll('.tab-btn');
    const slider = document.querySelector('.tab-slider');

    // 设置初始滑块位置和宽度
    const activeTab = document.querySelector('.tab-btn.tab-active');
    if (activeTab) {
        slider.style.width = `${activeTab.offsetWidth}px`;
        slider.style.left = `${activeTab.offsetLeft}px`;
    }

    // 选项卡点击事件
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // 移除所有选项卡的活动状态
            tabs.forEach(t => t.classList.remove('tab-active'));

            // 添加当前选项卡的活动状态
            tab.classList.add('tab-active');

            // 更新滑块位置和宽度
            slider.style.width = `${tab.offsetWidth}px`;
            slider.style.left = `${tab.offsetLeft}px`;

            // 显示对应面板
            const targetPanelId = tab.dataset.panel;
            const panels = document.querySelectorAll('.panel');

            panels.forEach(panel => {
                panel.classList.remove('panel-active', 'animate-fade-in');
                // 强制回流
                void panel.offsetWidth;
                panel.classList.add('hidden');
            });

            const targetPanel = document.getElementById(targetPanelId);
            targetPanel.classList.remove('hidden');
            // 强制回流
            void targetPanel.offsetWidth;
            targetPanel.classList.add('panel-active', 'animate-fade-in');
        });
    });

    // 窗口大小变化时重新计算滑块位置
    window.addEventListener('resize', () => {
        const activeTab = document.querySelector('.tab-btn.tab-active');
        if (activeTab) {
            slider.style.width = `${activeTab.offsetWidth}px`;
            slider.style.left = `${activeTab.offsetLeft}px`;
        }
    });
}

// 设置事件监听器
function setupEventListeners() {
    // 服务端按钮点击事件
    const serverButton = document.getElementById('server');
    serverButton.addEventListener('click', () => {
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
            if (result.code === 200) {
                if (server === 'start') {
                    updateStatus(serverStatus, "运行中", "text-green-500");
                    serverButton.innerHTML = '<i class="fa fa-stop mr-2"></i>关闭服务端';
                    server = 'stop';
                } else if (server === 'stop') {
                    updateStatus(serverStatus, "未运行", "text-danger");
                    serverButton.innerHTML = '<i class="fa fa-play mr-2"></i>启动服务端';
                    server = 'start';
                }
            } else if (result.code === 400) {
                showCustomModal({
                    icon: 'error',
                    title: `错误代码：${result.code}`,
                    text: result.message
                });
            }
            console.log('服务端操作响应:', result);
        })
        .catch(error => {
            console.error('服务端操作请求出错:', error);
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法连接到服务器'
            });
        });
    });

    // 客户端按钮点击事件
    const clientButton = document.getElementById('client');
    clientButton.addEventListener('click', () => {
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
            if (result.code === 200) {
                if (client === 'start') {
                    updateStatus(clientStatus, "运行中", "text-green-500");
                    clientButton.innerHTML = '<i class="fa fa-stop mr-2"></i>关闭客户端';
                    client = 'stop';
                } else if (client === 'stop') {
                    updateStatus(clientStatus, "未运行", "text-danger");
                    clientButton.innerHTML = '<i class="fa fa-play mr-2"></i>启动客户端';
                    client = 'start';
                }
            } else if (result.code === 400) {
                showCustomModal({
                    icon: 'error',
                    title: `错误代码：${result.code}`,
                    text: result.message
                });
            }
            console.log('客户端操作响应:', result);
        })
        .catch(error => {
            console.error('客户端操作请求出错:', error);
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法连接到服务器'
            });
        });
    });

    // 重载配置文件按钮点击事件
    const reloadButton = document.getElementById('button1');
    reloadButton.addEventListener('click', () => {
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
            console.log('重载配置响应:', result);
            if (result.code === 200) {
                showCustomModal({
                    icon: 'success',
                    title: '成功',
                    text: result.message,
                    showConfirmButton: false,
                    timer: 1500,
                    onConfirm: () => setTimeout(hideCustomModal, 1500)
                });

                // 重新加载配置数据
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
                            serverModeSelect.value = configData.serverMode;
                        }

                        // 设置客户端模式选择框的选中项
                        if (configData.clientMode) {
                            clientModeSelect.value = configData.clientMode;
                        }
                    })
                    .catch(error => {
                        console.error('获取配置数据出错:', error);
                        showCustomModal({
                            icon: 'error',
                            title: '请求失败',
                            text: '无法获取配置数据，请检查服务器连接'
                        });
                    });
            } else {
                showCustomModal({
                    icon: 'error',
                    title: `错误代码：${result.code}`,
                    text: result.message
                });
            }
        })
        .catch(error => {
            console.error('重载配置请求出错:', error);
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法连接到服务器'
            });
        });
    });

    // 保存配置按钮点击事件
    const saveButton = document.getElementById('button2');
    saveButton.addEventListener('click', () => {
        const serverIp = document.getElementById('serverIp').value;
        const serverMode = document.getElementById('serverMode').value;
        const clientMode = document.getElementById('clientMode').value;

        const data = {
            action: 'save_main_config',
            server_ip: serverIp,
            server_mode: serverMode,
            client_mode: clientMode
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
            console.log('保存配置响应:', result);
            if (result.code === 200) {
                showCustomModal({
                    icon: 'success',
                    title: '成功',
                    text: result.message,
                    showConfirmButton: false,
                    timer: 1500,
                    onConfirm: () => setTimeout(hideCustomModal, 1500)
                });
            } else {
                showCustomModal({
                    icon: 'error',
                    title: `错误代码：${result.code}`,
                    text: result.message
                });
            }
        })
        .catch(error => {
            console.error('保存配置请求出错:', error);
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法连接到服务器'
            });
        });
    });

    // 清空日志按钮点击事件
    const clearLogButton = document.getElementById('clear_log');
    clearLogButton.addEventListener('click', () => {
        showCustomModal({
            icon: 'warning',
            title: '确认清空日志?',
            text: '这将清除所有日志记录，且无法恢复。',
            showCancelButton: true,
            confirmButtonText: '是的，清空它!',
            cancelButtonText: '取消',
            onConfirm: () => {
                const data = {
                    action: 'clear_log'
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
                    console.log('清空日志响应:', result);
                    if (result.code === 200) {
                        document.getElementById('log').value = '';
                        showCustomModal({
                            icon: 'success',
                            title: '已清空!',
                            text: '日志已成功清空。'
                        });
                    } else {
                        showCustomModal({
                            icon: 'error',
                            title: '清空失败',
                            text: result.message
                        });
                    }
                })
                .catch(error => {
                    console.error('清空日志请求出错:', error);
                    showCustomModal({
                        icon: 'error',
                        title: '请求失败',
                        text: '无法连接到服务器'
                    });
                });
            }
        });
    });

    // 滚动时调整顶部导航栏样式
    window.addEventListener('scroll', () => {
        const header = document.querySelector('.app-header');
        if (window.scrollY > 10) {
            header.classList.add('shadow');
        } else {
            header.classList.remove('shadow');
        }
    });
}

// 自定义弹窗显示函数
function showCustomModal(options) {
    const modal = document.getElementById('custom-modal');
    const titleEl = document.getElementById('modal-title');
    const messageEl = document.getElementById('modal-message');
    const iconEl = document.getElementById('modal-icon');
    const confirmBtn = document.getElementById('modal-confirm');
    const cancelBtn = document.getElementById('modal-cancel');

    // 设置标题和内容
    titleEl.textContent = options.title || '提示';
    messageEl.textContent = options.text || '';

    // 设置图标
    if (options.icon === 'success') {
        iconEl.innerHTML = '<i class="fa fa-check-circle text-green-500 text-2xl"></i>';
    } else if (options.icon === 'error') {
        iconEl.innerHTML = '<i class="fa fa-exclamation-circle text-red-500 text-2xl"></i>';
    } else if (options.icon === 'warning') {
        iconEl.innerHTML = '<i class="fa fa-exclamation-triangle text-yellow-500 text-2xl"></i>';
    } else if (options.icon === 'info') {
        iconEl.innerHTML = '<i class="fa fa-info-circle text-blue-500 text-2xl"></i>';
    }

    // 设置按钮
    confirmBtn.textContent = options.confirmButtonText || '确定';
    cancelBtn.textContent = options.cancelButtonText || '取消';
    cancelBtn.classList.toggle('hidden', !options.showCancelButton);

    // 显示弹窗
    modal.classList.remove('opacity-0', 'pointer-events-none');
    modal.querySelector('div').classList.remove('scale-95');
    modal.querySelector('div').classList.add('scale-100');

    // 确认按钮回调
    confirmBtn.onclick = function() {
        hideCustomModal();
        if (options.onConfirm) options.onConfirm();
    };

    // 取消按钮回调
    cancelBtn.onclick = function() {
        hideCustomModal();
        if (options.onCancel) options.onCancel();
    };

    // 点击背景关闭
    modal.onclick = function(e) {
        if (e.target === modal && options.clickOutsideToClose !== false) {
            hideCustomModal();
            if (options.onCancel) options.onCancel();
        }
    };

    // 自动关闭（如果设置了timer）
    if (options.timer && options.timer > 0) {
        setTimeout(() => {
            hideCustomModal();
            if (options.onConfirm) options.onConfirm();
        }, options.timer);
    }
}

function hideCustomModal() {
    const modal = document.getElementById('custom-modal');
    modal.querySelector('div').classList.remove('scale-100');
    modal.querySelector('div').classList.add('scale-95');

    setTimeout(() => {
        modal.classList.add('opacity-0', 'pointer-events-none');
    }, 300);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    refreshPage();
    pollLogData();
    initTabSlider();
    setupEventListeners();

    // 二维码自动刷新功能
    const img = document.getElementById('qrcode-image');
    const refreshInterval = 1000;
    let currentBlobUrl = null;

    // 初始加载
    refreshImage();

    // 定时刷新
    setInterval(refreshImage, refreshInterval);

    function refreshImage() {
        const xhr = new XMLHttpRequest();
        xhr.open('GET', 'qrcode.png', true);
        xhr.responseType = 'blob';

        // 添加请求头禁用缓存
        xhr.setRequestHeader('Cache-Control', 'no-cache');

        xhr.onload = function() {
            if (xhr.status === 200) {
                // 释放之前的Blob URL
                if (currentBlobUrl) {
                    URL.revokeObjectURL(currentBlobUrl);
                }

                // 创建新的Blob URL并更新图片
                currentBlobUrl = URL.createObjectURL(xhr.response);
                img.src = currentBlobUrl;
            }
        };

        xhr.onerror = function() {
            console.error('图片加载失败');
            showCustomModal({
                icon: 'error',
                title: '加载失败',
                text: '二维码图片加载失败，请检查路径'
            });
        };

        xhr.send();
    }

    // 加载初始配置
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
                serverModeSelect.value = configData.serverMode;
            }

            // 设置客户端模式选择框的选中项
            if (configData.clientMode) {
                clientModeSelect.value = configData.clientMode;
            }
        })
        .catch(error => {
            console.error('获取配置数据出错:', error);
            showCustomModal({
                icon: 'error',
                title: '请求失败',
                text: '无法获取配置信息，请检查服务器连接'
            });
        });
});