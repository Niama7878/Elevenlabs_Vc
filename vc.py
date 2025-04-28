import os
import requests
from dotenv import load_dotenv
from common import player, mic_status
import json
from pydub import AudioSegment
import io
from typing import Optional

load_dotenv() 
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

headers = {
    "xi-api-key": ELEVENLABS_API_KEY,
}  

vc_data = {
    "model_id": "eleven_multilingual_sts_v2", # eleven_english_sts_v2
    "file_format": "pcm_s16le_16",
    "voice_settings": {
        "stabiity": 0.5, 
        "similality_boost": 0.75,
        "style": 0,
        "use_speaker_boost": False
    }, # 0.0 - 1.0
    "remove_background_noise": False
}

CHANNELS = 1
RATE = 24000
SAMPLE_WIDTH = 2 # s16le
FRAME_SIZE = 1024 

buffer = b""
voice_id = ""

def elevenlabs_vc(pcm_bytes: bytes):
    """发送语音转换请求到 Elevenlabs 并处理收到的音频"""
    global buffer
    try:
        url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}/stream?output_format=pcm_24000"
        files = {
            "audio": ('audio.pcm', pcm_bytes, 'audio/pcm')
        }
        vc_backup = vc_data.copy()
        vc_backup['voice_settings'] = json.dumps(vc_backup['voice_settings'])
        response = requests.post(url, headers=headers, data=vc_backup, files=files, stream=True)

        if response.status_code == 200:
            for chunk in response.iter_content(chunk_size=1024): # 流式输出
                if not chunk:
                    continue

                buffer += chunk
                
                while len(buffer) >= FRAME_SIZE: 
                    frame = buffer[:FRAME_SIZE]
                    buffer = buffer[FRAME_SIZE:]
                    
                    audio = AudioSegment.from_raw(
                        io.BytesIO(frame),
                        sample_width=SAMPLE_WIDTH,
                        frame_rate=RATE,
                        channels=CHANNELS
                    )

                    wav_io = io.BytesIO()
                    audio.export(wav_io, format="wav")
                    audio_bytes = wav_io.getvalue()

                    player.add_audio(audio_bytes) 
        else:
            data = response.json()
            print(f"ElevenLabs 语音转换请求失败: {response.status_code} {data}")
    except Exception as e:
        print(f"ElevenLabs 语音转换请求错误: {e}")

    mic_status(True)

def get_usage() -> Optional[tuple[int, int]]:
    """获取 Elevenlabs 积分使用情况"""
    try:
        url = "https://api.elevenlabs.io/v1/user/subscription"
        response = requests.get(url, headers=headers)
        data = response.json()

        if response.status_code == 200:
            count = data['character_count']
            limit = data['character_limit']
            return count, limit
        else:
            print(f"ElevenLabs 获取积分使用情况失败: {response.status_code} {data}")
    except Exception as e:
        print(f"ElevenLabs 获取积分使用情况错误: {e}")

    return None

def get_voices() -> Optional[dict]:
    """获取 ElevenLabs 以添加的语音模型"""
    try:
        url = "https://api.us.elevenlabs.io/v2/voices?voice_type=community"
        response = requests.get(url, headers=headers)
        data = response.json()

        if response.status_code == 200:
            return data
        else:
            print(f"ElevenLabs 获取以添加的语音模型失败: {response.status_code} {data}")
    except Exception as e:
        print(f"ElevenLabs 获取以添加的语音模型错误: {e}")
              
    return None