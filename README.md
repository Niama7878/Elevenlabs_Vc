# Elevenlabs Vc

## 描述

本应用程序提供了一个图形用户界面（GUI），用于使用 ElevenLabs 的 Speech-to-Speech API 和 OpenAI 的语音活动检测（VAD）进行实时语音转换。它会捕捉麦克风的音频输入，使用 OpenAI 检测语音片段，将检测到的语音发送到 ElevenLabs 以转换为选定的声音，并近乎实时地播放转换后的音频。

## 功能特性

* **实时语音转换：** 捕捉麦克风输入，并使用 ElevenLabs Speech-to-Speech 进行转换。
* **声音选择：** 从您的 ElevenLabs 账户获取并显示可用的自定义声音供选择 。
* **OpenAI VAD 集成：** 使用 OpenAI 的实时 API 进行精确的语音活动检测，以便在转换前分割语音片段 
* **可调参数：**
    * **ElevenLabs VC：** 稳定性、相似度、风格夸张、启用 Speaker Boost、移除背景噪音。
    * **OpenAI VAD：** 静音时长 (ms)、激活阈值。
    * **转换模型：** 可在 `eleven_multilingual_sts_v2` 和 `eleven_english_sts_v2` 之间选择。
* **GUI 控件：** 使用 Pygame 构建的直观界面，用于选择声音、调整设置和监控状态。
* **状态指示器：** 提供语音活动、麦克风状态和音频播放的视觉反馈。
* **用量监控：** 显示您当前的 ElevenLabs 字符使用量和限制。
* **异步播放：** 使用单独的线程进行流畅的音频播放，不阻塞主应用程序。

## 文件结构概述

* `app.py`: 包含 Pygame GUI 逻辑、事件处理和显示更新的主应用程序文件。
* `vc.py`: 处理与 ElevenLabs API 的交互，用于语音转换、获取声音和用量数据。
* `vad.py`: 管理通过 WebSocket 与 OpenAI 实时 VAD 服务的连接、麦克风音频流以及触发语音转换。
* `play.py`: 包含用于异步音频播放的 `AudioPlayer` 类。
* `common.py`: 存储共享的应用程序状态（如麦克风状态、语音活动状态、音频播放器实例。
* `main.py`: 用于启动并保持应用程序运行的简单脚本。
* `.env`: 用于存储 API 密钥的配置文件（需要您自行填写）。
* `icon.ico`/`icon.png`: 应用程序图标。
* `YeZiGongChangTangYingHei-2.ttf`: GUI 中使用的字体文件。
* `vc.zip`/`vc.exe` (解压后在 `dist` 文件夹中): 预打包的可执行版本。

## 环境要求

* 此项目开发使用 Python 3.12.8
* 必需的 Python 库：
    * `python-dotenv`
    * `pydub`
    * `PyAudio` (在某些系统上可能需要 PortAudio 开发库)
    * `websocket-client`
    * `requests`
    * `pygame`
* `ffmpeg` ( `pydub` 进行音频处理所需，请确保已安装并在系统 PATH 中)
* ElevenLabs API 密钥
* OpenAI API 密钥

## 配置

1.  在项目的根目录（如果使用可执行文件，则在 `dist` 文件夹中）找到一个名为 `.env` 的文件。
2.  将您的 API 密钥添加到 `.env` 文件中，格式如下：

    ```dotenv
    ELEVENLABS_API_KEY=YOUR_ELEVENLABS_API_KEY
    OPENAI_API_KEY=YOUR_OPENAI_API_KEY
    ```

## 使用方法

### 选项 1: 从源代码运行

1.  **克隆仓库或下载源代码。**
2.  **安装依赖:**
    ```bash
    pip install python-dotenv pydub PyAudio websocket-client requests pygame
    ```
    *(请记得根据需要安装 `ffmpeg` 和 `portaudio`)*
3.  **配置:** 按照 **配置** 部分的说明填写 `.env` 文件。
4.  **运行应用程序:**
    ```bash
    python main.py
    ```

### 选项 2: 使用打包的可执行文件 (`vc.exe`)

1.  **下载 [`vc.zip`](https://github.com/Niama7878/Elevenlabs_Vc/raw/main/vc.zip)** 并解压缩其内容。这应该会创建一个文件夹（可能名为 `vc` 或类似名称），其中包含 `vc.exe` 和其他必要文件。
2.  **配置:** 填写 `.env` 文件（如 **配置** 部分所述）。
3.  **运行:** 双击 `vc.exe` 启动应用程序。

## 工作原理

1.  应用程序启动，初始化 Pygame 用于 GUI (`app.py`)，并建立到 OpenAI VAD 服务的 WebSocket 连接 (`vad.py`)。
2.  它从 ElevenLabs 获取您的自定义声音和用量数据 (`vc.py`)。
3.  GUI (`app.py`) 显示声音列表、设置滑块、复选框和状态指示器。
4.  当您说话时，PyAudio 会捕获麦克风输入 (`vad.py`)。
5.  原始音频通过 WebSocket 流式传输到 OpenAI 进行 VAD。
6.  OpenAI 发回指示语音开始和结束的事件。
7.  当语音停止时（`input_audio_buffer.speech_stopped` 事件），录制的音频块将使用选定的声音 ID 和设置发送到 ElevenLabs Speech-to-Speech API (`vc.py`, 由 `vad.py` 触发)。
8.  ElevenLabs 以 PCM 格式流式传回转换后的音频。
9.  接收到的音频块被添加到播放队列中 (`vc.py` 使用 `common.player`)。
10. 一个单独的线程 (`play.py`) 从队列中播放音频，而不会中断主应用程序流程。
11. GUI 交互（选择声音、更改设置）会更新用于 VAD 和 VC 请求的相关配置。