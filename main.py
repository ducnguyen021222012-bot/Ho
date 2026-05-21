# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: conmeo.py
# Bytecode version: 3.13.0rc3 (3571)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

import os
import sys
import threading
import time
import ctypes
import winsound
import json
import random
import pydivert
import mouse
import keyboard
from colorama import init, Fore, Style
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox, QMainWindow, QSystemTrayIcon, QMenu, QGridLayout, QProxyStyle, QStyle, QStyleOptionButton
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QPoint, QSize, QTimer, QPointF, QThread, QEvent
from PyQt6.QtGui import QFont, QColor, QPalette, QLinearGradient, QPainter, QBrush, QPen, QIcon
from dataclasses import dataclass, field
from typing import List

init(autoreset=True)

def log_error(message):
    with open('debug.log', 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {message}\n")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    try:
        ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, __file__, None, 1)
        sys.exit()
    except Exception as e:
        log_error(f'Failed to elevate privileges: {e}')
        sys.exit(1)

HOTKEY_FILE = 'tenetest_hotkey.json'

@dataclass
class HotkeyConfig:
    key: str = ''
    is_valid: bool = False

@dataclass
class AppConfig:
    tele_hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    freeze_hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    ghost_hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)

app_config = AppConfig()

MOUSE_CANON = {
    'left': 'mouse:left', 
    'right': 'mouse:right', 
    'middle': 'mouse:middle', 
    'x': 'mouse:x1', 
    'x2': 'mouse:x2', 
    'x1': 'mouse:x1', 
    'mb4': 'mouse:x1', 
    'mb5': 'mouse:x2', 
    'xbutton4': 'mouse:x1', 
    'xbutton5': 'mouse:x2'
}

MOUSE_DISPLAY = {
    'mouse:left': 'LMB', 
    'mouse:right': 'RMB', 
    'mouse:middle': 'MMB', 
    'mouse:x1': 'MB4', 
    'mouse:x2': 'MB5'
}

def load_config():
    """Loads hotkey configuration from file or creates a default one."""
    global app_config
    default_data = {'teleport_hotkey': 'v', 'freeze_hotkey': 'x', 'ghost_hotkey': 'b'}
    
    if not os.path.exists(HOTKEY_FILE):
        with open(HOTKEY_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=2)
    
    try:
        with open(HOTKEY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            app_config.tele_hotkey.key = data.get('teleport_hotkey', '')
            app_config.tele_hotkey.is_valid = bool(app_config.tele_hotkey.key)
            app_config.freeze_hotkey.key = data.get('freeze_hotkey', '')
            app_config.freeze_hotkey.is_valid = bool(app_config.freeze_hotkey.key)
            app_config.ghost_hotkey.key = data.get('ghost_hotkey', '')
            app_config.ghost_hotkey.is_valid = bool(app_config.ghost_hotkey.key)
    except json.JSONDecodeError:
        QMessageBox.warning(None, 'Lỗi cấu hình', 'Lỗi đọc file cấu hình, sẽ gán lại hotkey mặc định.')
        app_config = AppConfig(
            tele_hotkey=HotkeyConfig(key='v', is_valid=True), 
            freeze_hotkey=HotkeyConfig(key='x', is_valid=True), 
            ghost_hotkey=HotkeyConfig(key='b', is_valid=True)
        )
        save_config()

def save_config():
    """Saves hotkey configuration to file."""
    data = {
        'teleport_hotkey': app_config.tele_hotkey.key, 
        'freeze_hotkey': app_config.freeze_hotkey.key, 
        'ghost_hotkey': app_config.ghost_hotkey.key
    }
    with open(HOTKEY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

FILTER_O = '(udp.DstPort >= 10010 and udp.DstPort <= 10020) and udp.PayloadLength >= 43'
FILTER_I = '(udp.SrcPort >= 10011 and udp.SrcPort <= 10019) and ip and ip.Protocol == 17 and ip.Length >= 58 and ip.Length <= 1107 and not udp.DstPort == 53 and not udp.SrcPort == 123 and not udp.SrcPort == 1900'
FILTER_F = '(udp.DstPort>=10011 and udp.DstPort<=10020) and udp.PayloadLength>=45'

tele_mode, freeze_mode, ghost_mode = (False, False, False)
R_O, R_I, R_F = (False, False, False)
packet_tele, packet_freeze, packet_ghost = ([], [], [])
lock = threading.Lock()
running = True

class StatusSignals(QObject):
    update_overlay = pyqtSignal(bool, bool, bool)
    update_console_status = pyqtSignal()

signals = StatusSignals()

class AudioManager:
    def play_beep(self, frequency=500, duration=300):
        def beep_thread():
            try:
                winsound.Beep(frequency, duration)
            except Exception:
                pass
        threading.Thread(target=beep_thread, daemon=True).start()

    def play_toggle_on(self):
        self.play_beep(600, 120)

    def play_toggle_off(self):
        self.play_beep(400, 150)

audio_manager = AudioManager()

class CustomStyle(QProxyStyle):
    """A custom style for QPushButton with a green checkmark."""
    
    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_PushButtonLabel:
            super().drawControl(element, option, painter, widget)
            if isinstance(widget, QPushButton):
                if widget.isChecked():
                    painter.save()
                    color = QColor(Qt.GlobalColor.green)
                    pen = QPen(color, 2)
                    painter.setPen(pen)
                    w, h = (option.rect.width(), option.rect.height())
                    x_offset = w - 20
                    y_offset = h // 2
                    painter.drawLine(x_offset, y_offset, x_offset + 5, y_offset + 5)
                    painter.drawLine(x_offset + 5, y_offset + 5, x_offset + 10, y_offset - 5)
                    painter.restore()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('</> HPSTORE')
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 350, 180)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.main_frame = QFrame(self)
        self.main_frame.setStyleSheet('''
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a1a, stop:1 #2a2a2a);
                border: 2px solid #555555;
                border-radius: 10px;
            }
        ''')
        self.layout.addWidget(self.main_frame)
        
        self.main_layout = QVBoxLayout(self.main_frame)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)
        
        # Title bar
        self.title_bar = QFrame(self)
        self.title_bar.setStyleSheet('''
            QFrame {
                background-color: #3a3a3a;
                border-bottom: 1px solid #555555;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QLabel {
                color: white;
                font-weight: bold;
                padding: 5px;
            }
        ''')
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 0, 5, 0)
        
        self.title_label = QLabel('</> VANBAO VN')
        self.title_label.setFont(QFont('Arial', 10))
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()
        
        self.close_button = QPushButton('X')
        self.close_button.setStyleSheet('''
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-weight: bold;
                padding: 5px 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c42b1c;
            }
        ''')
        self.close_button.clicked.connect(self.close_app)
        self.title_layout.addWidget(self.close_button)
        self.main_layout.addWidget(self.title_bar)
        
        # Buttons frame
        buttons_frame = QFrame(self)
        buttons_frame.setStyleSheet('background-color: #3a3a3a; border: 1px solid #555555; border-radius: 5px; padding: 5px;')
        buttons_layout = QGridLayout(buttons_frame)
        buttons_layout.setSpacing(5)
        
        self.btn_tele = QPushButton('Telekill')
        self.btn_ghost = QPushButton('Ghost')
        self.btn_freeze = QPushButton('Freeze')
        
        button_style = '''
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 1px solid #6a6a6a;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
                border-color: #8a8a8a;
            }
            QPushButton:checked {
                background-color: #2e8b57;
                border-color: #3cb371;
            }
            QPushButton:checked:hover {
                background-color: #3cb371;
            }
        '''
        
        self.btn_tele.setCheckable(True)
        self.btn_ghost.setCheckable(True)
        self.btn_freeze.setCheckable(True)
        self.btn_tele.setStyleSheet(button_style)
        self.btn_ghost.setStyleSheet(button_style)
        self.btn_freeze.setStyleSheet(button_style)
        
        self.btn_tele.clicked.connect(self.toggle_tele_gui)
        self.btn_ghost.clicked.connect(self.toggle_ghost_gui)
        self.btn_freeze.clicked.connect(self.toggle_freeze_gui)
        
        buttons_layout.addWidget(self.btn_tele, 0, 0)
        buttons_layout.addWidget(self.btn_ghost, 0, 1)
        buttons_layout.addWidget(self.btn_freeze, 0, 2)
        
        hotkey_label_style = '''
            QLabel {
                color: #bbbbbb;
                font-size: 14px;
                margin-top: 10px;
            }
            QLabel:hover {
                color: #ffffff;
                text-decoration: underline;
            }
        '''
        
        self.hotkey_label_tele = QLabel('Hotkey: ...')
        self.hotkey_label_tele.setStyleSheet(hotkey_label_style)
        self.hotkey_label_tele.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hotkey_label_tele.installEventFilter(self)
        
        self.hotkey_label_ghost = QLabel('Hotkey: ...')
        self.hotkey_label_ghost.setStyleSheet(hotkey_label_style)
        self.hotkey_label_ghost.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hotkey_label_ghost.installEventFilter(self)
        
        self.hotkey_label_freeze = QLabel('Hotkey: ...')
        self.hotkey_label_freeze.setStyleSheet(hotkey_label_style)
        self.hotkey_label_freeze.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hotkey_label_freeze.installEventFilter(self)
        
        buttons_layout.addWidget(self.hotkey_label_tele, 1, 0)
        buttons_layout.addWidget(self.hotkey_label_ghost, 1, 1)
        buttons_layout.addWidget(self.hotkey_label_freeze, 1, 2)
        
        self.main_layout.addWidget(buttons_frame)
        self.main_layout.addStretch()
        
        self.setting_hotkey_type = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.finish_hotkey_setting)
        
        signals.update_overlay.connect(self.update_button_states)
        signals.update_console_status.connect(self.update_console_status_label)
        
        self.console_status_label = QLabel('Đang chờ...')
        self.console_status_label.setStyleSheet('color: #cccccc; font-size: 12px; margin-top: 12px;')
        self.console_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.console_status_label)
        
        # System tray
        self.tray_icon = QSystemTrayIcon(QIcon('icon.png'), self)
        self.tray_icon.setToolTip('Mena Fake Lag')
        tray_menu = QMenu()
        restore_action = tray_menu.addAction('Hiện/Ẩn')
        restore_action.triggered.connect(self.toggle_visibility)
        exit_action = tray_menu.addAction('Thoát')
        exit_action.triggered.connect(self.close_app)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()
        
        signals.update_overlay.emit(tele_mode, freeze_mode, ghost_mode)
        signals.update_console_status.emit()
        self.update_hotkey_labels()
    
    def eventFilter(self, watched_object, event):
        """Handle mouse clicks on the hotkey labels."""
        if event.type() == QEvent.Type.MouseButtonPress:
            if watched_object is self.hotkey_label_tele:
                self.set_hotkey('teleport')
                return True
            elif watched_object is self.hotkey_label_ghost:
                self.set_hotkey('ghost')
                return True
            elif watched_object is self.hotkey_label_freeze:
                self.set_hotkey('freeze')
                return True
        return super().eventFilter(watched_object, event)
    
    def update_hotkey_labels(self):
        """Updates the text on hotkey labels based on current config."""
        tele_key = app_config.tele_hotkey.key.upper() if app_config.tele_hotkey.key else '...'
        ghost_key = app_config.ghost_hotkey.key.upper() if app_config.ghost_hotkey.key else '...'
        freeze_key = app_config.freeze_hotkey.key.upper() if app_config.freeze_hotkey.key else '...'
        
        self.hotkey_label_tele.setText(f'Hotkey: {tele_key}')
        self.hotkey_label_ghost.setText(f'Hotkey: {ghost_key}')
        self.hotkey_label_freeze.setText(f'Hotkey: {freeze_key}')
    
    def set_hotkey(self, hotkey_type):
        """Enters a mode to capture the next key press for a hotkey."""
        self.setting_hotkey_type = hotkey_type
        if hotkey_type == 'teleport':
            self.hotkey_label_tele.setText('Hotkey: Bấm phím...')
        elif hotkey_type == 'ghost':
            self.hotkey_label_ghost.setText('Hotkey: Bấm phím...')
        elif hotkey_type == 'freeze':
            self.hotkey_label_freeze.setText('Hotkey: Bấm phím...')
        
        self.timer.start(5000)  # 5 second timeout
        self.keyboard_hook = keyboard.on_release(self.on_key_release)
    
    def on_key_release(self, event):
        """Callback for keyboard events to capture the new hotkey."""
        if not self.setting_hotkey_type:
            return
        
        key_name = event.name
        if len(key_name) > 1:
            key_name = key_name.lower()
        
        # Save the hotkey
        if self.setting_hotkey_type == 'teleport':
            app_config.tele_hotkey.key = key_name
            app_config.tele_hotkey.is_valid = True
        elif self.setting_hotkey_type == 'ghost':
            app_config.ghost_hotkey.key = key_name
            app_config.ghost_hotkey.is_valid = True
        elif self.setting_hotkey_type == 'freeze':
            app_config.freeze_hotkey.key = key_name
            app_config.freeze_hotkey.is_valid = True
        
        # Save config
        save_config()
        
        # Update UI
        self.update_hotkey_labels()
        
        # Cleanup
        keyboard.unhook(self.keyboard_hook)
        self.setting_hotkey_type = None
        self.timer.stop()
    
    def finish_hotkey_setting(self):
        """Called if a key is not pressed within the timeout."""
        if self.setting_hotkey_type:
            QMessageBox.warning(self, 'Lỗi cài đặt', 'Không có phím nào được nhấn. Vui lòng thử lại.')
            self.update_hotkey_labels()
            try:
                keyboard.unhook(self.keyboard_hook)
            except:
                pass
            self.setting_hotkey_type = None
    
    def update_button_states(self, tele_state, freeze_state, ghost_state):
        self.btn_tele.setChecked(tele_state)
        self.btn_freeze.setChecked(freeze_state)
        self.btn_ghost.setChecked(ghost_state)
    
    def update_console_status_label(self):
        status_tele = 'ON' if tele_mode else 'OFF'
        status_freeze = 'ON' if freeze_mode else 'OFF'
        status_ghost = 'ON' if ghost_mode else 'OFF'
        self.console_status_label.setText(f'Tele: {status_tele} | Freeze: {status_freeze} | Ghost: {status_ghost}')
    
    def toggle_tele_gui(self):
        toggle_tele()
    
    def toggle_ghost_gui(self):
        toggle_ghost()
    
    def toggle_freeze_gui(self):
        toggle_freeze()
    
    def close_app(self):
        stop_all()
    
    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
    
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()
    
    _dragging = False
    _drag_position = QPointF()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self._dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_position)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 250, 25)
        
        self._dragging = False
        self._drag_position = QPoint()
        self.setStyleSheet('background-color: rgba(0, 0, 0, 150); border: 1px solid #444444; border-radius: 5px;')
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.layout.setSpacing(5)
        
        self.tele_label = QLabel('Tele: OFF')
        self.freeze_label = QLabel('Freeze: OFF')
        self.ghost_label = QLabel('Ghost: OFF')
        
        default_style = 'color: #cccccc; font-weight: bold; padding: 2px 5px; border: 1px solid #555555; border-radius: 3px;'
        self.tele_label.setStyleSheet(default_style)
        self.freeze_label.setStyleSheet(default_style)
        self.ghost_label.setStyleSheet(default_style)
        
        self.layout.addWidget(self.tele_label)
        self.layout.addWidget(self.freeze_label)
        self.layout.addWidget(self.ghost_label)
        
        signals.update_overlay.connect(self.update_status)
    
    def update_status(self, tele_status, freeze_status, ghost_status):
        tele_text = f"Tele: {'ON' if tele_status else 'OFF'}"
        freeze_text = f"Freeze: {'ON' if freeze_status else 'OFF'}"
        ghost_text = f"Ghost: {'ON' if ghost_status else 'OFF'}"
        
        self.tele_label.setText(tele_text)
        self.freeze_label.setText(freeze_text)
        self.ghost_label.setText(ghost_text)
        
        active_color = '#00ff00'
        default_color = '#cccccc'
        
        active_style = f'color: {active_color}; font-weight: bold; padding: 2px 5px; border: 1px solid {active_color}; border-radius: 3px;'
        default_style = f'color: {default_color}; font-weight: bold; padding: 2px 5px; border: 1px solid #555555; border-radius: 3px;'
        
        self.tele_label.setStyleSheet(active_style if tele_status else default_style)
        self.freeze_label.setStyleSheet(active_style if freeze_status else default_style)
        self.ghost_label.setStyleSheet(active_style if ghost_status else default_style)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_position)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

class HotkeyListener(QThread):
    def __init__(self, window_instance):
        super().__init__()
        self.window = window_instance
        self._tele_pressed_prev = False
        self._ghost_pressed_prev = False
        self._freeze_pressed_prev = False
    
    def run(self):
        while running:
            try:
                if app_config.tele_hotkey.is_valid:
                    current_tele_state = keyboard.is_pressed(app_config.tele_hotkey.key)
                    if current_tele_state and not self._tele_pressed_prev:
                        toggle_tele()
                    self._tele_pressed_prev = current_tele_state
                
                if app_config.freeze_hotkey.is_valid:
                    current_freeze_state = keyboard.is_pressed(app_config.freeze_hotkey.key)
                    if current_freeze_state and not self._freeze_pressed_prev:
                        toggle_freeze()
                    self._freeze_pressed_prev = current_freeze_state
                
                if app_config.ghost_hotkey.is_valid:
                    current_ghost_state = keyboard.is_pressed(app_config.ghost_hotkey.key)
                    if current_ghost_state and not self._ghost_pressed_prev:
                        toggle_ghost()
                    self._ghost_pressed_prev = current_ghost_state
                
                time.sleep(0.01)  # 10ms delay to reduce CPU usage
            except Exception as e:
                log_error(f'Error in hotkey listener: {e}')
                time.sleep(0.1)

def send_packets(lst, f):
    try:
        with pydivert.WinDivert(f, layer=pydivert.Layer.NETWORK) as s:
            for pkt in lst:
                try:
                    s.send(pydivert.Packet(pkt.raw, pkt.interface, pkt.direction))
                except Exception as e:
                    log_error(f'Error sending packet: {e}')
    except Exception as e:
        log_error(f'Error in send_packets: {e}')

def toggle_tele():
    global R_O, tele_mode
    
    if tele_mode:
        # Turn off
        with lock:
            tele_mode = False
            R_O = False
            to_send = list(packet_tele)
            packet_tele.clear()
        
        audio_manager.play_toggle_off()
        
        def send_bursts(to_send, burst_size=1, delay_between_burst=0.001):
            try:
                with pydivert.WinDivert(FILTER_O, layer=pydivert.Layer.NETWORK) as sender:
                    for i in range(0, len(to_send), burst_size):
                        burst = to_send[i:i + burst_size]
                        for pkt in burst:
                            try:
                                pkt_rebuilt = pydivert.Packet(pkt.raw, pkt.interface, pkt.direction)
                                sender.send(pkt_rebuilt)
                                time.sleep(0.005)
                            except Exception as e:
                                log_error(f'Error sending burst packet: {e}')
                        time.sleep(delay_between_burst)
            except Exception as e:
                log_error(f'Error in send_bursts: {e}')
        
        if to_send:
            threading.Thread(target=lambda: send_bursts(to_send), daemon=True).start()
    else:
        # Turn on
        tele_mode = True
        R_O = True
        audio_manager.play_toggle_on()
    
    signals.update_overlay.emit(tele_mode, freeze_mode, ghost_mode)
    signals.update_console_status.emit()

def toggle_freeze():
    global freeze_mode, R_I
    
    if freeze_mode:
        # Turn off
        freeze_mode = R_I = False
        packets = []
        with lock:
            packets = list(packet_freeze)
            packet_freeze.clear()
        
        threading.Thread(target=send_packets, args=(packets, FILTER_I), daemon=True).start()
        audio_manager.play_toggle_off()
    else:
        # Turn on
        freeze_mode = True
        R_I = True
        audio_manager.play_toggle_on()
    
    signals.update_overlay.emit(tele_mode, freeze_mode, ghost_mode)
    signals.update_console_status.emit()

def toggle_ghost():
    global ghost_mode, R_F
    
    if ghost_mode:
        # Turn off
        ghost_mode = R_F = False
        packets = []
        with lock:
            packets = list(packet_ghost)
            packet_ghost.clear()
        
        threading.Thread(target=send_packets, args=(packets, FILTER_F), daemon=True).start()
        audio_manager.play_toggle_off()
    else:
        # Turn on
        ghost_mode = True
        R_F = True
        audio_manager.play_toggle_on()
    
    signals.update_overlay.emit(tele_mode, freeze_mode, ghost_mode)
    signals.update_console_status.emit()

def stop_all():
    global running, R_I, R_F, R_O
    
    running = False
    R_O = R_I = R_F = False
    
    if tele_mode:
        toggle_tele()
    if freeze_mode:
        toggle_freeze()
    if ghost_mode:
        toggle_ghost()
    
    keyboard.unhook_all()
    
    try:
        QApplication.instance().quit()
    except:
        pass
    
    os._exit(0)

def divert(filter_str, flag_ref, packet_list, cond_ref):
    h = None
    
    while running:
        try:
            if not flag_ref():
                if h:
                    try:
                        h.close()
                    except:
                        pass
                    h = None
                time.sleep(0.001)
                continue
            
            if h is None:
                try:
                    h = pydivert.WinDivert(filter_str, layer=pydivert.Layer.NETWORK)
                    h.open()
                except Exception as e:
                    log_error(f'Error opening WinDivert handle for {filter_str}: {e}')
                    h = None
                    time.sleep(0.001)
                    continue
            
            # Receive packet
            try:
                packet = h.recv()
                if packet:
                    with lock:
                        packet_list.append(packet)
                    
                    # If condition is true, don't send immediately
                    if cond_ref():
                        continue
                    
                    # Send packet
                    h.send(packet)
            except Exception as e:
                log_error(f'Error processing packet for {filter_str}: {e}')
                
        except Exception as e:
            log_error(f'Error in divert loop for {filter_str}: {e}')
            if h:
                try:
                    h.close()
                except:
                    pass
                h = None
            time.sleep(0.001)
    
    # Cleanup
    if h:
        try:
            h.close()
        except:
            pass

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        
        # Set dark theme palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(60, 60, 60))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        app.setPalette(palette)
        
        # Load configuration
        load_config()
        
        # Create windows
        window = MainWindow()
        window.show()
        
        overlay = OverlayWindow()
        overlay.show()
        
        # Start packet diversion threads
        threading.Thread(target=divert, args=(FILTER_O, lambda: R_O, packet_tele, lambda: tele_mode), daemon=True).start()
        threading.Thread(target=divert, args=(FILTER_I, lambda: R_I, packet_freeze, lambda: freeze_mode), daemon=True).start()
        threading.Thread(target=divert, args=(FILTER_F, lambda: R_F, packet_ghost, lambda: ghost_mode), daemon=True).start()
        
        # Start hotkey listener
        hotkey_listener_thread = HotkeyListener(window)
        hotkey_listener_thread.start()
        
        # Global hotkey to exit
        keyboard.add_hotkey('f10', stop_all, suppress=True)
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        log_error(f'Unhandled exception in main thread: {e}')
        try:
            msg_box = QMessageBox()
            msg_box.setWindowTitle('Lỗi khởi chạy')
            msg_box.setText(f'Có lỗi đã xảy ra: {e}\n\nChi tiết đã được ghi vào debug.log. Vui lòng đảm bảo đã cài đặt đầy đủ các thư viện: pip install pydivert keyboard colorama PyQt6')
            msg_box.exec()
        except:
            pass
        sys.exit(1)
