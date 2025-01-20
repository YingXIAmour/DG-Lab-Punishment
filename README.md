## 郊狼惩罚姬

![主程序页面](/image.png)

### 说明

郊狼按键惩罚的升级版，将功能进行模块化，以达到多种方式使用

### 已知BUG

1. 建议不要尝试导入一些奇怪的库，程序没有可能会报错（后续解决一下这个问题）

### 食用方法
1. 下载构建好的版本
2. 解压全部文件 - 一定要全部解压，否则程序报错！
3. 启动服务端和客户端就可以打开功能面板启用你想要玩的功能了！

>注意：
> 1. 在设计的时候服务端确实是可以通过修改/data/config.json中的ip来自定义IP的，以此可以实现公网监听，也就不需要保持同一局域网下进行扫码
> 2. 如果只是自己用的话请不要动/data/config.json的字符，程序会检测当前局域网IP自动启动，只需要保持同一局域网即可

### 未来开发功能

- [ ] 服务端模式 (n-n，1-n(还未开发完)，n-1（未开发)
- 该功能可以实现一对多或者多对一的模式，你想要享受被十个人同时控制嘛喵（）

### 配置文件  config.json
   ```json
   {
    "server":{
        "ip": "",
        "port": 1145,
        "mode": "n-n"
    },
    "client": {
        "mode": "n-n"
    },
    "conf": {
        "strengthAdd": {
            "A": [1,10],
            "B": [1,10]
        },
        "listening_channel_strength": "HTTP"
    },
    "function": {
        "keyboard_listen": {
            "keyboardMode": "CONFIG",
            "keyboard_key_count": 4
        },
        "csgo_dglab": {
            "Test": ""
        }
    }
}
   ```
   #### **server项**
   1. ip：如果不需要公网请留空
   2. port：端口，一般不用动 
   3. mode：启动模式（n-n:一对一模式 1-n：一对多模式，只支持一个客户端连接 n-1：多对一模式，多客户端对单一APP操作）

   #### **client项**
   mode：启动模式，和上述一样

   #### **conf项-此项为主程序配置项**
   strengthAdd：记录累加值(暂时无用)
   listening_channel_strength：强度监听模式（HTTP：网页模式，Windows：程序模式(弹出窗口捕获强度))

   #### **function项-模块配置**
   记录模块的配置文档，加模块后要在这加入配置，即便模块不需要也需要加
### 强度监听
- HTTP模式启动后可访问你的本地IP:8000/channel_strength来查看强度变化，如
   ```
  http://127.0.0.1/channel_strength
  ```
  理论上可以用obs直接捕获该网页）
### 开发文档
- 鼓励大家多多开发）
- [开发文档](./docx/function.md) - 还没写，咕咕咕
### 参考文档

- [郊狼情趣脉冲主机V3](https://github.com/DG-LAB-OPENSOURCE/DG-LAB-OPENSOURCE/blob/main/coyote/v3/README_V3.md)
- [郊狼 SOCKET 控制-控制端开源](https://github.com/DG-LAB-OPENSOURCE/DG-LAB-OPENSOURCE/blob/main/socket/README.md)

> 有BUG可以提交到issues或者在bilibili视频底下评论
