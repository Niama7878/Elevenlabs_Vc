from play import AudioPlayer
from typing import Optional

player = AudioPlayer() 
voice = False 
mic = True 

def voice_activity(status: bool=None) -> Optional[bool]:
    """返回或修改语音状态"""
    global voice
    if isinstance(status, bool):
        voice = status
    else:
        return voice

def mic_status(status: bool=None) -> Optional[bool]:
    """返回或修改麦克风状态"""
    global mic
    if isinstance(status, bool):
        mic = status
    else:
       return mic