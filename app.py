import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
import threading
import time
from common import player, voice_activity, mic_status
import vc
import vad

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_BACKGROUND = (240, 240, 245) # 更柔的背景色
COLOR_PANEL_BG = (255, 255, 255) # 面板背景使用纯白，对比更清晰
COLOR_BORDER = (210, 210, 215) # 边框颜色
COLOR_TEXT_DARK = (50, 50, 50) # 深色文字
COLOR_TEXT_MEDIUM = (120, 120, 120) # 中等颜色文字 (描述等)
COLOR_TEXT_LIGHT = (255, 255, 255) # 浅色文字 (按钮等)
COLOR_PRIMARY = (0, 122, 255) # 主题色 (蓝色)
COLOR_PRIMARY_DARK = (0, 90, 200) # 主题色深色 (按下时)
COLOR_GREEN = (52, 199, 89) # 绿色 (状态激活)
COLOR_RED = (255, 59, 48) # 红色 (状态关闭/警告)
COLOR_YELLOW = (255, 204, 0) # 黄色 (播放状态)
COLOR_GREY_LIGHT = (229, 229, 234) # 浅灰色 (滑块轨道等)
COLOR_GREY_MEDIUM = (199, 199, 204) # 中灰色 (滑块手柄等)
COLOR_SELECTED_BG = (220, 235, 255) # 选中项背景 (淡蓝)
COLOR_CHECKBOX_BORDER = (180, 180, 180) # 复选框边框

PADDING = 20 # 统一边距
STATUS_HEIGHT = 45
USAGE_HEIGHT = 45
SETTINGS_WIDTH = 380 # 设置面板宽度
VOICE_LIST_ITEM_HEIGHT = 65 # 列表项高度
BUTTON_HEIGHT = 40
INPUT_HEIGHT = 30 # 用于模型按钮高度
CHECKBOX_SIZE = 18 # 复选框大小
CHECKBOX_SPACING = 10 # 复选框与标签间距
SLIDER_HEIGHT = 25 # 滑块视觉区域高度 (不含标签)
SLIDER_TRACK_HEIGHT = 6 # 滑块轨道高度
SLIDER_HANDLE_WIDTH = 16 # 滑块手柄宽度
SLIDER_HANDLE_HEIGHT = SLIDER_HEIGHT - 4 # 滑块手柄高度
SLIDER_VERTICAL_SPACING = SLIDER_HEIGHT + PADDING + 20 # 滑块之间的垂直总间距

class VcDisplay:
    def __init__(self, width=1000, height=750, font_path="YeZiGongChangTangYingHei-2.ttf"):
        """初始化配置"""
        self.width = width
        self.height = height
        self.font_path = font_path

        self.running = True
        self.clock = pygame.time.Clock()

        self.voices = []
        self.usage_count = 0
        self.usage_limit = 0
        self.selected_voice_id = vc.voice_id
        self.voice_list_scroll_offset = 0

        self.voice_rects = {} # 存储声音列表项的 Rect
        self.model_id_rects = {} # 存储模型选择按钮的 Rect
        self.checkbox_rects = {} # 存储复选框的 Rect 和关联 key
        self.update_vad_button_rect = None
        self.vad_button_pressed = False

        self.sliders = {} # 存储滑块数据
        self.active_slider_key = None # 当前正在拖动的滑块 key

        self._init_sliders() 
        self._init_checkboxes() 

        threading.Thread(target=self.update_data, daemon=True).start()
        threading.Thread(target=self._pygame_loop, daemon=True).start()

    def _init_sliders(self):
        """初始化设置面板中的滑块数据字典"""
        self.sliders.clear()
        settings_x = self.width - SETTINGS_WIDTH - PADDING
        slider_width = SETTINGS_WIDTH - PADDING * 2 - 60 # 滑块轨道宽度

        slider_definitions = {
            "stabiity": {"label": "稳定性", "min": 0.0, "max": 1.0, "format": "{:.2f}", "is_int": False, "group": "vc"},
            "similality_boost": {"label": "相似度", "min": 0.0, "max": 1.0, "format": "{:.2f}", "is_int": False, "group": "vc"},
            "style": {"label": "风格夸张", "min": 0.0, "max": 1.0, "format": "{:.2f}", "is_int": False, "group": "vc"},
            "silence_duration_ms": {"label": "静音时长 (ms)", "min": 100, "max": 1000, "format": "{:d}", "is_int": True, "group": "vad"},
            "threshold": {"label": "激活阈值", "min": 0.1, "max": 1.0, "format": "{:.2f}", "is_int": False, "group": "vad"},
        }

        vc_settings = vc.vc_data.get("voice_settings", {})
        vad_settings = vad.session_update.get("session", {}).get("turn_detection", {})

        current_y_vc_slider_start = PADDING + 110 + INPUT_HEIGHT + PADDING # 模型按钮下方开始
        current_y_vad_slider_start = PADDING + 420 # VAD 滑块起始 Y (估算)

        for key, info in slider_definitions.items(): # 为每个滑块创建数据字典
            if info["group"] == "vc":
                initial_val = vc_settings.get(key, (info['min'] + info['max']) / 2)
                current_y = current_y_vc_slider_start
                current_y_vc_slider_start += SLIDER_VERTICAL_SPACING
            else: # VAD
                initial_val = vad_settings.get(key, (info['min'] + info['max']) / 2)
                current_y = current_y_vad_slider_start
                current_y_vad_slider_start += SLIDER_VERTICAL_SPACING

            track_y = current_y + SLIDER_VERTICAL_SPACING // 2 - SLIDER_TRACK_HEIGHT // 2 - 10 # 轨道 Y 坐标微调
            track_rect = pygame.Rect(settings_x + PADDING, track_y, slider_width, SLIDER_TRACK_HEIGHT)
            slider_rect = pygame.Rect(settings_x + PADDING, current_y, slider_width, SLIDER_VERTICAL_SPACING) # 整体占位

            slider_data = {
                "key": key,
                "label": info["label"],
                "rect": slider_rect,          
                "track_rect": track_rect,     
                "handle_rect": pygame.Rect(0, 0, SLIDER_HANDLE_WIDTH, SLIDER_HANDLE_HEIGHT), 
                "min_val": info["min"],
                "max_val": info["max"],
                "value": initial_val,
                "format": info["format"],
                "is_int": info["is_int"],
                "dragging": False,
                "group": info["group"]
            }
            self._update_slider_handle_pos(slider_data) # 计算初始手柄位置
            self.sliders[key] = slider_data

    def _init_checkboxes(self):
        """初始化复选框的状态"""
        self.checkbox_states = {
            "use_speaker_boost": vc.vc_data.get("voice_settings", {}).get("use_speaker_boost", False),
            "remove_background_noise": vc.vc_data.get("remove_background_noise", False),
        }

    def _update_slider_handle_pos(self, slider_data: dict):
        """根据滑块当前值计算其手柄位置"""
        track_rect = slider_data["track_rect"]
        min_val = slider_data["min_val"]
        max_val = slider_data["max_val"]
        value = slider_data["value"]

        value_range = max_val - min_val
        ratio = (value - min_val) / value_range if value_range != 0 else 0

        handle_center_x = track_rect.left + ratio * track_rect.width
        handle_rect = slider_data["handle_rect"]
        handle_rect.centery = track_rect.centery
        handle_rect.centerx = handle_center_x
       
        handle_rect.left = max(track_rect.left - SLIDER_HANDLE_WIDTH // 2 + SLIDER_TRACK_HEIGHT // 2, handle_rect.left)
        handle_rect.right = min(track_rect.right + SLIDER_HANDLE_WIDTH // 2 - SLIDER_TRACK_HEIGHT // 2, handle_rect.right)

    def _draw_slider(self, slider_data: dict):
        """绘制单个滑块"""
        label = slider_data["label"]
        track_rect = slider_data["track_rect"]
        handle_rect = slider_data["handle_rect"]
        value = slider_data["value"]
        value_format = slider_data["format"]
        dragging = slider_data["dragging"]

        label_surface = self.font_small.render(label, True, COLOR_TEXT_DARK)
        label_rect = label_surface.get_rect(topleft=(track_rect.left, track_rect.top - 22)) 
        self.screen.blit(label_surface, label_rect)

        pygame.draw.rect(self.screen, COLOR_GREY_LIGHT, track_rect, border_radius=SLIDER_TRACK_HEIGHT // 2) # 绘制轨道

        handle_color = COLOR_PRIMARY_DARK if dragging else COLOR_PRIMARY 
        pygame.draw.rect(self.screen, handle_color, handle_rect, border_radius=3) # 绘制手柄

        value_text = value_format.format(value) # 绘制当前值
        value_surface = self.font_small.render(value_text, True, COLOR_TEXT_MEDIUM)
        value_rect = value_surface.get_rect(centery=label_rect.centery, left=track_rect.right + 15) # 值显示在标签右侧
        self.screen.blit(value_surface, value_rect)

    def _draw_checkbox(self, key: str, label: str, x: int, y: int) -> int:
        """绘制单个复选框和标签，返回绘制的高度"""
        is_checked = self.checkbox_states.get(key, False)
        checkbox_rect = pygame.Rect(x, y, CHECKBOX_SIZE, CHECKBOX_SIZE)
        self.checkbox_rects[key] = checkbox_rect # 存储 Rect 用于点击检测

        pygame.draw.rect(self.screen, COLOR_CHECKBOX_BORDER, checkbox_rect, 1, border_radius=3) # 绘制边框

        if is_checked: # 绘制勾号 (使用主题色)
            tick_points = [
                (checkbox_rect.left + 4, checkbox_rect.centery),
                (checkbox_rect.centerx - 1, checkbox_rect.bottom - 5),
                (checkbox_rect.right - 4, checkbox_rect.top + 5)
            ]
            pygame.draw.lines(self.screen, COLOR_PRIMARY, False, tick_points, 2)

        label_surface = self.font_small.render(label, True, COLOR_TEXT_DARK)
        label_rect = label_surface.get_rect(left=checkbox_rect.right + CHECKBOX_SPACING, centery=checkbox_rect.centery)
        self.screen.blit(label_surface, label_rect)

        return CHECKBOX_SIZE # 返回绘制区域的高度

    def _handle_slider_event(self, slider_data: dict, event: pygame.event.Event, mouse_pos: tuple[int, int]) -> bool:
        """处理单个滑块的事件"""
        key = slider_data["key"]
        handle_rect = slider_data["handle_rect"]
        track_rect = slider_data["track_rect"]
        min_val = slider_data["min_val"]
        max_val = slider_data["max_val"]
        is_int = slider_data["is_int"]
        handled = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            click_check_rect = handle_rect.inflate(20, 20) 
            if click_check_rect.collidepoint(mouse_pos) or track_rect.collidepoint(mouse_pos): # 点击轨道也触发
                slider_data["dragging"] = True
                self.active_slider_key = key
    
                if track_rect.collidepoint(mouse_pos): # 轨道点击时更新值 
                    mouse_x, _ = mouse_pos
                    ratio = (mouse_x - track_rect.left) / track_rect.width
                    ratio = max(0.0, min(1.0, ratio))
                    
                    new_value = min_val + ratio * (max_val - min_val)
                    if is_int:
                        new_value = int(round(new_value))
                    else:
                        new_value = round(new_value, 2) # 保留两位小数
                
                    slider_data["value"] = new_value
                    self._update_slider_handle_pos(slider_data)

                    if slider_data["group"] == "vc":
                        vc.vc_data.setdefault("voice_settings", {})[key] = new_value
                    elif slider_data["group"] == "vad":
                        vad.session_update.setdefault("session", {}).setdefault("turn_detection", {})[key] = new_value

                handled = True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if slider_data["dragging"] and self.active_slider_key == key:
                slider_data["dragging"] = False
                self.active_slider_key = None
                current_value = slider_data["value"]

                if slider_data["group"] == "vc":
                    vc.vc_data.setdefault("voice_settings", {})[key] = current_value
                elif slider_data["group"] == "vad":
                    vad.session_update.setdefault("session", {}).setdefault("turn_detection", {})[key] = current_value

                handled = True

        elif event.type == pygame.MOUSEMOTION:
            if slider_data["dragging"] and self.active_slider_key == key:
                mouse_x, _ = mouse_pos
                ratio = (mouse_x - track_rect.left) / track_rect.width
                ratio = max(0.0, min(1.0, ratio))
                new_value = min_val + ratio * (max_val - min_val)

                if is_int:
                    new_value = int(round(new_value))
                else:
                    new_value = round(new_value, 2)

                if slider_data["value"] != new_value: # 值发生变化时才更新，避免不必要的计算
                    slider_data["value"] = new_value # 更新数据字典中的值
                    self._update_slider_handle_pos(slider_data) # 更新手柄位置

                    if slider_data["group"] == "vc":
                        vc.vc_data.setdefault("voice_settings", {})[key] = new_value
                    elif slider_data["group"] == "vad":
                        vad.session_update.setdefault("session", {}).setdefault("turn_detection", {})[key] = new_value
                handled = True

        return handled

    def update_data(self):
        """定时更新声音列表和用量数据"""
        while self.running:
            voices_data = vc.get_voices()
            if voices_data:
                new_voices = voices_data.get('voices', [])
                
                if self.voices != new_voices:
                    self.voices = new_voices
                    current_voice_ids = {v.get('voice_id') for v in self.voices}
                    if not self.selected_voice_id or self.selected_voice_id not in current_voice_ids:
                        self.selected_voice_id = self.voices[0].get('voice_id') if self.voices else ""
                        vc.voice_id = self.selected_voice_id 

            usage_data = vc.get_usage()
            if usage_data:
                self.usage_count, self.usage_limit = usage_data

            time.sleep(30) 

    def _draw_text(self, text: str, font: pygame.font.Font, color: tuple[int, int, int],
                   x: int | float, y: int, surface: pygame.surface.Surface=None,
                   center_x: bool=False, center_y: bool=False,
                   max_width: int=None, max_lines: int=None) -> int:
        """绘制文本 (支持自动换行和行数限制)"""
        if surface is None:
            surface = self.screen

        if max_width:
            words = text.split(' ')
            lines = []
            current_line = ""
            for word in words: 
                word_width = font.size(word)[0] # 检查单词本身是否超宽
                if word_width > max_width:
                    temp_word_line = ""
                    for char in word: # 如果单词本身就超宽，尝试逐字分割
                        if font.size(temp_word_line + char)[0] <= max_width:
                            temp_word_line += char
                        else:
                            lines.append(temp_word_line)
                            temp_word_line = char
                    word = temp_word_line # 剩余部分作为下一个词处理

                test_line = current_line + word + " "
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line.strip())
                    current_line = word + " "
            lines.append(current_line.strip())

            if max_lines is not None and len(lines) > max_lines:
                lines = lines[:max_lines]
                if len(lines) > 0:
                    last_line = lines[-1]
                    if len(last_line) > 3:
                        while font.size(last_line + "...")[0] > max_width and len(last_line) > 0:
                            last_line = last_line[:-1]
                        lines[-1] = last_line + "..."
                    else:
                         lines[-1] = "..."

            line_height = font.get_linesize()
            total_height = len(lines) * line_height
            start_y = y
            if center_y:
                start_y = y - total_height // 2 # 垂直居中

            for i, line in enumerate(lines):
                text_surface = font.render(line, True, color)
                text_rect = text_surface.get_rect()
                line_y = start_y + i * line_height
                if center_x:
                    text_rect.centerx = x
                else:
                    text_rect.left = x # 默认左对齐
                text_rect.top = line_y
                surface.blit(text_surface, text_rect)

            return total_height # 返回实际绘制高度
        else:
            text_surface = font.render(text, True, color)
            text_rect = text_surface.get_rect()
            if center_x and center_y:
                text_rect.center = (x, y)
           
            elif center_x:
                text_rect.centerx = x
                text_rect.top = y
            elif center_y:
                text_rect.centery = y
                text_rect.left = x
            else:
                text_rect.topleft = (x, y)
            surface.blit(text_surface, text_rect)
            return text_rect.height # 返回单行高度

    def _draw_status_indicators(self, x: int, y: int, height: int):
        """绘制状态指示灯"""
        indicator_size = height - PADDING * 1.8 # 指示灯大小
        indicator_radius = indicator_size // 2
        spacing = PADDING * 3
        current_x = x

        voice_active = voice_activity() # 语音活动
        color = COLOR_GREEN if voice_active else COLOR_GREY_MEDIUM # 未激活时用灰色
        pygame.draw.circle(self.screen, color, (int(current_x + indicator_radius), int(y + height / 2)), int(indicator_radius))
        text_x = current_x + indicator_size + PADDING // 2
        text_width = self._draw_text("语音活动", self.font_small, COLOR_TEXT_DARK, text_x, y + height // 2, center_y=True)
        current_x = text_x + text_width + spacing

        mic_on = mic_status() # 麦克风
        color = COLOR_GREEN if mic_on else COLOR_RED # 保持红绿区分
        pygame.draw.circle(self.screen, color, (int(current_x + indicator_radius), int(y + height / 2)), int(indicator_radius))
        text_x = current_x + indicator_size + PADDING // 2
        text_width = self._draw_text("麦克风", self.font_small, COLOR_TEXT_DARK, text_x, y + height // 2, center_y=True)
        current_x = text_x + text_width + spacing

        player_playing = player.is_playing # 播放中
        color = COLOR_YELLOW if player_playing else COLOR_GREY_MEDIUM # 未激活时用灰色
        pygame.draw.circle(self.screen, color, (int(current_x + indicator_radius), int(y + height / 2)), int(indicator_radius))
        text_x = current_x + indicator_size + PADDING // 2
        self._draw_text("播放中", self.font_small, COLOR_TEXT_DARK, text_x, y + height // 2, center_y=True)

    def _draw_usage_info(self, x: int, y: int, width: int, height: int):
        """绘制用量信息"""
        panel_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, panel_rect, border_radius=8) # 使用面板背景色
        pygame.draw.rect(self.screen, COLOR_BORDER, panel_rect, 1, border_radius=8) # 统一边框色

        progress = 0
        if self.usage_limit > 0:
            progress = min(1.0, self.usage_count / self.usage_limit)
            
        progress_bar_width = width - PADDING * 2
        progress_bar_height = 8
        progress_bar_x = x + PADDING
        progress_bar_y = y + height - PADDING - progress_bar_height

        pygame.draw.rect(self.screen, COLOR_GREY_LIGHT, (progress_bar_x, progress_bar_y, progress_bar_width, progress_bar_height), border_radius=4)
        pygame.draw.rect(self.screen, COLOR_PRIMARY, (progress_bar_x, progress_bar_y, int(progress_bar_width * progress), progress_bar_height), border_radius=4)

        text = f"用量: {self.usage_count} / {self.usage_limit} 字符" # 显示文本
        self._draw_text(text, self.font_medium, COLOR_TEXT_DARK, x + width // 2, progress_bar_y - PADDING - 10, center_x=True, center_y=True)

    def _draw_settings_panel(self, x: int, y: int, width: int, height: int):
        """绘制设置面板"""
        panel_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, panel_rect, border_radius=8) # 面板背景
        pygame.draw.rect(self.screen, COLOR_BORDER, panel_rect, 1, border_radius=8) # 边框

        current_y = y + PADDING
        current_y += self._draw_text("语音转换 (VC) 设置", self.font_large, COLOR_TEXT_DARK, x + width // 2, current_y + 5, center_x=True) + PADDING
        current_y += self._draw_text("模型:", self.font_medium, COLOR_TEXT_DARK, x + PADDING, current_y + 5) + PADDING // 2

        model_options = ["eleven_multilingual_sts_v2", "eleven_english_sts_v2"]
        option_width = (width - PADDING * 3) // len(model_options)
        option_x = x + PADDING
        self.model_id_rects.clear()
        model_button_y = current_y

        for i, model in enumerate(model_options):
            model_rect = pygame.Rect(option_x, model_button_y, option_width, INPUT_HEIGHT + 5)
            self.model_id_rects[model] = model_rect
            is_selected = (vc.vc_data.get("model_id") == model)
            bg_color = COLOR_PRIMARY if is_selected else COLOR_WHITE
            text_color = COLOR_TEXT_LIGHT if is_selected else COLOR_TEXT_DARK
            border_color = COLOR_PRIMARY if is_selected else COLOR_BORDER # 边框颜色也变化

            pygame.draw.rect(self.screen, bg_color, model_rect, border_radius=5)
            pygame.draw.rect(self.screen, border_color, model_rect, 1, border_radius=5) # 统一边框风格

            display_name = model.split('_')[1].upper() if '_' in model else model # 显示简称大写
            self._draw_text(display_name, self.font_small, text_color, model_rect.centerx, model_rect.centery, center_x=True, center_y=True)
            option_x += option_width + PADDING

        current_y = model_button_y + INPUT_HEIGHT + 5 + PADDING * 1.5 # 更新 Y
        checkbox_start_y = current_y
        checkbox_height1 = self._draw_checkbox("use_speaker_boost", "启用 Speaker Boost", x + PADDING, checkbox_start_y)
        checkbox_height2 = self._draw_checkbox("remove_background_noise", "移除背景噪音", x + PADDING + (width // 2) , checkbox_start_y) # 并排放置
        current_y = checkbox_start_y + max(checkbox_height1, checkbox_height2) + PADDING * 1.5 # 更新 Y 到复选框下方

        last_vc_slider_bottom = current_y
        for key, slider_data in self.sliders.items():
            if slider_data["group"] == "vc":
                slider_data['rect'].top = current_y # 动态调整滑块的 Y 坐标
                slider_data['track_rect'].top = current_y + SLIDER_VERTICAL_SPACING // 2 - SLIDER_TRACK_HEIGHT // 2 - 10
                self._update_slider_handle_pos(slider_data) # 更新手柄位置
                self._draw_slider(slider_data)
                current_y += SLIDER_VERTICAL_SPACING # 更新 Y 坐标以绘制下一个滑块
                last_vc_slider_bottom = slider_data['rect'].bottom + 5 # 记录最后一个VC滑块的底部

        vad_start_y = last_vc_slider_bottom + PADDING # VAD 区域从 VC 设置下方开始，留出间距
        current_y = vad_start_y
        current_y += self._draw_text("语音活动检测 (VAD) 设置", self.font_large, COLOR_TEXT_DARK, x + width // 2, current_y + 5, center_x=True) + PADDING

        last_vad_slider_bottom = current_y
        for key, slider_data in self.sliders.items():
            if slider_data["group"] == "vad":
                slider_data['rect'].top = current_y
                slider_data['track_rect'].top = current_y + SLIDER_VERTICAL_SPACING // 2 - SLIDER_TRACK_HEIGHT // 2 - 10
                self._update_slider_handle_pos(slider_data)
                self._draw_slider(slider_data)
                current_y += SLIDER_VERTICAL_SPACING
                last_vad_slider_bottom = slider_data['rect'].bottom + 5 # 记录底部

        button_y = last_vad_slider_bottom + PADDING # 按钮 Y 坐标
        button_y = min(button_y, panel_rect.bottom - BUTTON_HEIGHT - PADDING)  # 确保按钮不超出面板底部

        self.update_vad_button_rect = pygame.Rect(x + PADDING, button_y, width - PADDING * 2, BUTTON_HEIGHT)
        button_bg_color = COLOR_PRIMARY_DARK if self.vad_button_pressed else COLOR_PRIMARY
        pygame.draw.rect(self.screen, button_bg_color, self.update_vad_button_rect, border_radius=8)
        pygame.draw.rect(self.screen, COLOR_PRIMARY_DARK, self.update_vad_button_rect, 1, border_radius=8) # 边框
        self._draw_text("应用 VAD 设置", self.font_medium, COLOR_TEXT_LIGHT, self.update_vad_button_rect.centerx, self.update_vad_button_rect.centery, center_x=True, center_y=True)

    def _draw_voice_list(self, x: int, y: int, width: int, height: int):
        """绘制声音列表"""
        list_area_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, COLOR_PANEL_BG, list_area_rect, border_radius=8) # 背景
        pygame.draw.rect(self.screen, COLOR_BORDER, list_area_rect, 1, border_radius=8) # 边框
       
        list_content_height = len(self.voices) * VOICE_LIST_ITEM_HEIGHT
        list_surface = pygame.Surface((width, list_content_height)) # 创建一个独立的 Surface 用于绘制列表内容，便于滚动
        list_surface.fill(COLOR_PANEL_BG) # 填充背景

        current_item_y = 0
        self.voice_rects.clear() # 清空上一帧的 Rect

        for voice in self.voices:
            voice_id = voice.get('voice_id')
            name = voice.get('name', '未知名称') # 提供默认值
            description = voice.get('description', '无描述') 
            if not description: description = "无描述" 

            item_surface_rect = pygame.Rect(0, current_item_y, width, VOICE_LIST_ITEM_HEIGHT)

            is_selected = (voice_id == self.selected_voice_id)
            bg_color = COLOR_SELECTED_BG if is_selected else COLOR_PANEL_BG

            if is_selected:
                pygame.draw.rect(list_surface, bg_color, item_surface_rect.inflate(-2, -2), border_radius=6) # 圆角矩形

            if current_item_y > 0: # 不在第一项顶部绘制
                 pygame.draw.line(list_surface, COLOR_BORDER, (PADDING, current_item_y), (width - PADDING, current_item_y))
            
            name_y = current_item_y + PADDING * 0.8
            self._draw_text(name, self.font_medium, COLOR_TEXT_DARK, PADDING, name_y, surface=list_surface) # 绘制名称 

            desc_y = name_y + self.font_medium.get_linesize() + 2 # 描述与名称间距缩小
            remaining_height = item_surface_rect.height - (desc_y - current_item_y) - (PADDING * 0.8)
           
            allowed_lines = max(1, remaining_height // self.font_small.get_linesize()) # 保证至少一行
            self._draw_text(description, self.font_small, COLOR_TEXT_MEDIUM, PADDING, desc_y,
                            surface=list_surface, max_width=width - PADDING * 2, max_lines=allowed_lines)

            screen_rect_y = y + current_item_y - self.voice_list_scroll_offset
            screen_rect = pygame.Rect(x, screen_rect_y, width, VOICE_LIST_ITEM_HEIGHT)
            
            self.voice_rects[voice_id] = screen_rect 
            current_item_y += VOICE_LIST_ITEM_HEIGHT

        visible_area = pygame.Rect(0, self.voice_list_scroll_offset, width, height) # 只绘制可见部分
        original_clip = self.screen.get_clip()
        self.screen.set_clip(list_area_rect)
        self.screen.blit(list_surface, (x, y), visible_area)
        self.screen.set_clip(original_clip) # 恢复 clip

        if list_content_height > height:
            scrollbar_width = 10 # 滚动条宽度
            scrollbar_area_rect = pygame.Rect(x + width - scrollbar_width - 4, y + 4, scrollbar_width, height - 8) # 滚动条区域
            visible_ratio = height / list_content_height

            thumb_height = max(25, int(scrollbar_area_rect.height * visible_ratio)) # 滚动条滑块最小高度
            scrollable_dist = list_content_height - height
            thumb_y_ratio = self.voice_list_scroll_offset / scrollable_dist if scrollable_dist > 0 else 0
            thumb_y = int(scrollbar_area_rect.y + thumb_y_ratio * (scrollbar_area_rect.height - thumb_height))
            thumb_rect = pygame.Rect(scrollbar_area_rect.x, thumb_y, scrollbar_width, thumb_height)

            pygame.draw.rect(self.screen, COLOR_GREY_MEDIUM, thumb_rect, border_radius=scrollbar_width // 2) 

    def _handle_click(self, pos: tuple[int, int]):
        """处理鼠标左键点击事件"""
        clicked_on_interactive_element = False
        
        for model, rect in self.model_id_rects.items(): # 检查模型按钮点击
            if rect.collidepoint(pos):
                if vc.vc_data.get("model_id") != model:
                    vc.vc_data["model_id"] = model
                clicked_on_interactive_element = True
                break # 处理完一个就退出

        if not clicked_on_interactive_element: # 检查复选框点击
            for key, rect in self.checkbox_rects.items():
                click_rect = rect.inflate(CHECKBOX_SPACING, CHECKBOX_SPACING)
                if click_rect.collidepoint(pos):
                    self.checkbox_states[key] = not self.checkbox_states[key] # 切换状态
            
                    if key == "use_speaker_boost":
                        vc.vc_data.setdefault("voice_settings", {})[key] = self.checkbox_states[key]
                    elif key == "remove_background_noise":
                        vc.vc_data[key] = self.checkbox_states[key]
                    clicked_on_interactive_element = True
                    break
        
        if not clicked_on_interactive_element: # 检查声音列表项点击
            list_area_rect = pygame.Rect(PADDING, STATUS_HEIGHT + USAGE_HEIGHT + PADDING * 2,
                                          self.width - SETTINGS_WIDTH - PADDING * 3,
                                          self.height - (STATUS_HEIGHT + USAGE_HEIGHT + PADDING * 3))
            if list_area_rect.collidepoint(pos): # 确保点击在列表区域内
                for voice_id, rect in self.voice_rects.items():
                     if rect.collidepoint(pos) and list_area_rect.colliderect(rect):
                        if self.selected_voice_id != voice_id:
                            self.selected_voice_id = voice_id
                            vc.voice_id = voice_id 
                        clicked_on_interactive_element = True
                        break
        
        if not clicked_on_interactive_element: # 检查 VAD 更新按钮点击
            if self.update_vad_button_rect and self.update_vad_button_rect.collidepoint(pos):
                vad.update_vad() 
                self.vad_button_pressed = True # 设置按钮按下状态（用于视觉反馈）
                pygame.time.set_timer(pygame.USEREVENT + 1, 150, True) # 150ms 后触发一次自定义事件
                clicked_on_interactive_element = True

        if not clicked_on_interactive_element: # 检查滑块点击 (开始拖动)
            event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'button': 1, 'pos': pos})
            for slider_data in self.sliders.values():
                if self._handle_slider_event(slider_data, event, pos):
                    clicked_on_interactive_element = True
                    break # 一次只激活一个滑块

    def _handle_mouse_motion(self, pos: tuple[int, int]):
        """处理鼠标移动事件 (主要用于滑块拖动)"""
        if self.active_slider_key: # 只有当有滑块被激活时才处理
             slider_data = self.sliders.get(self.active_slider_key)
             if slider_data:
                event = pygame.event.Event(pygame.MOUSEMOTION, {'pos': pos, 'rel': pygame.mouse.get_rel(), 'buttons': pygame.mouse.get_pressed()})
                self._handle_slider_event(slider_data, event, pos)

    def _handle_mouse_up(self, pos: tuple[int, int]):
        """处理鼠标按键释放事件"""
        if self.active_slider_key: # 处理滑块拖动结束
            slider_data = self.sliders.get(self.active_slider_key)
            if slider_data:
                event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'button': 1, 'pos': pos})
                self._handle_slider_event(slider_data, event, pos) # 这会设置 dragging=False 并 finalise

    def _handle_scroll(self, event: pygame.event.Event):
        """处理鼠标滚轮事件 (用于声音列表滚动)"""
        list_area_rect = pygame.Rect(PADDING, STATUS_HEIGHT + USAGE_HEIGHT + PADDING * 2,
                                     self.width - SETTINGS_WIDTH - PADDING * 3,
                                     self.height - (STATUS_HEIGHT + USAGE_HEIGHT + PADDING * 3))
       
        list_content_height = len(self.voices) * VOICE_LIST_ITEM_HEIGHT
        list_view_height = list_area_rect.height

        if list_area_rect.collidepoint(pygame.mouse.get_pos()) and list_content_height > list_view_height:
            scroll_speed_multiplier = 1.5 # 调整滚动速度
            scroll_amount = int(VOICE_LIST_ITEM_HEIGHT * scroll_speed_multiplier) # 按列表项高度倍数滚动

            if event.y > 0: # 向上滚动
                self.voice_list_scroll_offset -= scroll_amount
            elif event.y < 0: # 向下滚动
                self.voice_list_scroll_offset += scroll_amount

            self.voice_list_scroll_offset = max(0, self.voice_list_scroll_offset) # 限制滚动范围
            max_scroll = list_content_height - list_view_height
            self.voice_list_scroll_offset = min(self.voice_list_scroll_offset, max_scroll if max_scroll > 0 else 0)

    def _pygame_loop(self):
        """Pygame 主事件和绘图循环"""
        pygame.init()

        self.screen = pygame.display.set_mode((self.width, self.height))
        self.font_small = pygame.font.Font(self.font_path, 15) 
        self.font_medium = pygame.font.Font(self.font_path, 17)
        self.font_large = pygame.font.Font(self.font_path, 20)
      
        pygame.display.set_caption("Elevenlabs 实时语音转换控制面板")
        icon = pygame.image.load("icon.png")
        pygame.display.set_icon(icon)
     
        while self.running:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: 
                        self._handle_click(mouse_pos)

                elif event.type == pygame.MOUSEMOTION:
                    self._handle_mouse_motion(mouse_pos)

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1: 
                        self._handle_mouse_up(mouse_pos)

                elif event.type == pygame.MOUSEWHEEL: 
                    self._handle_scroll(event)

                elif event.type == pygame.USEREVENT + 1: # 自定义事件，用于按钮状态恢复
                    self.vad_button_pressed = False

            self.screen.fill(COLOR_BACKGROUND) 

            status_x = PADDING
            status_y = PADDING
            self._draw_status_indicators(status_x, status_y, STATUS_HEIGHT)

            usage_x = PADDING
            usage_y = status_y + STATUS_HEIGHT + PADDING
            left_panel_width = self.width - SETTINGS_WIDTH - PADDING * 3
            self._draw_usage_info(usage_x, usage_y, left_panel_width, USAGE_HEIGHT)

            list_x = PADDING
            list_y = usage_y + USAGE_HEIGHT + PADDING
            list_width = left_panel_width
            list_height = self.height - list_y - PADDING 
            self._draw_voice_list(list_x, list_y, list_width, list_height)

            settings_x = self.width - SETTINGS_WIDTH - PADDING
            settings_y = PADDING
            settings_height = self.height - PADDING * 2 
            self._draw_settings_panel(settings_x, settings_y, SETTINGS_WIDTH, settings_height)

            pygame.display.flip()

            self.clock.tick(60) 
            time.sleep(0.01) 

        pygame.quit()

display = VcDisplay()