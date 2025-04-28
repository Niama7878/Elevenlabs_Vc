import os
from dotenv import load_dotenv
import json
import base64
import threading
import pyaudio
from common import player, voice_activity, mic_status
import websocket
import time
from vc import elevenlabs_vc
from collections import deque

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 

OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-mini-realtime-preview-2024-12-17"
HEADERS = [
    "Authorization: Bearer " + OPENAI_API_KEY,
    "OpenAI-Beta: realtime=v1"
]
ws_global = None 

session_update = {
    "type": "session.update",
    "session": {
        "turn_detection": {
            "type": "server_vad", 
            "create_response": False,
            "silence_duration_ms": 500, # 100 - 1000
            "threshold": 0.5 # 0.1 - 1.0
        },
    }
} 

CHANNELS = 2
RATE = 16000
CHUNK = 1024 

chunks = []
buffer = deque(maxlen=int(0.5 * RATE / CHUNK)) # 缓冲音频数据

def on_message(ws, message):
    """处理 WebSocket 收到的消息"""
    data = json.loads(message)  
    event_type = data.get("type") 
   
    if event_type == "input_audio_buffer.speech_started":
        voice_activity(True) 

    elif event_type == "input_audio_buffer.speech_stopped":
        voice_activity(False) 
        mic_status(False) 

        merged_audio = b"".join(chunks) # 合并音频片段
        elevenlabs_vc(merged_audio)
        chunks.clear()  
        
def on_open(ws):
    """WebSocket 打开触发"""
    try:
        ws_global.send(json.dumps(session_update)) 
        threading.Thread(target=audio_stream, daemon=True).start()
    except Exception as e:
        print(f"OpenAI WebSocket 初始化配置错误: {e}")

def connect_ws():
    """建立 WebSocket 连接""" 
    global ws_global
    try:
        ws_global = websocket.WebSocketApp(
            OPENAI_WS_URL,
            header=HEADERS,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
        )
        threading.Thread(target=ws_global.run_forever, daemon=True).start()
    except Exception as e:
        print(f"OpenAI WebSocket 连接失败: {e}")

def on_close(ws, close_status_code, close_msg):
    """WebSocket 断开触发"""
    print(f"OpenAI WebSocket 关闭信息: {close_status_code}, {close_msg}")
    connect_ws() # 重新连接

def on_error(ws, error):
    """WebSocket 错误触发"""
    print(f"OpenAI WebSocket 错误: {error}")

def send_audio(pcm16_audio: bytes):
    """发送音频数据到 WebSocket 服务器"""
    try:
        base64_audio = base64.b64encode(pcm16_audio).decode()
        data = {
            "type": "input_audio_buffer.append",
            "audio": base64_audio
        }
        ws_global.send(json.dumps(data))
    except Exception as e:
        print(f"发送音频数据到 OpenAI WebSocket 失败: {e}")

def audio_stream():
    """监听麦克风音频，根据语音状态进行录制"""
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=CHANNELS, rate=RATE,
                        input=True, input_device_index=audio.get_default_input_device_info()['index'], frames_per_buffer=CHUNK)
    while True:
        if mic_status() and not player.is_playing: # 麦克风启用和无音频播放
            pcm_data = stream.read(CHUNK, exception_on_overflow=False)
            send_audio(pcm_data)
            
            if voice_activity():
                if buffer:
                    chunks.extend(buffer) 
                    buffer.clear()
                chunks.append(pcm_data)
            else:
                buffer.append(pcm_data) 
                
        time.sleep(0.01)

def update_vad():
    """发送更新的 vad 参数到 WebSocket 服务器"""
    try:
        ws_global.send(json.dumps(session_update))
    except Exception as e:
        print(f"发送更新的 vad 参数到 OpenAI WebSocket 失败: {e}")

connect_ws()