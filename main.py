


global tele_mode  # inserted
global packet_tele  # inserted
global R_O  # inserted
global R_I  # inserted
global W_I  # inserted
global W_F  # inserted
global toggle_key  # inserted
global R_F  # inserted
global freeze_mode  # inserted
global stop_key  # inserted
global filter_key  # inserted
global ghost_mode  # inserted
import os
import sys
import threading
import time
import ctypes
import winsound
import pydivert
import keyboard
import os
import ctypes
from colorama import init, Fore, Style
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt6.QtGui import QFont
from enum import Enum
from dataclasses import dataclass, field
init(autoreset=True)
ctypes.windll.kernel32.SetConsoleTitleW('Nguyenpc')

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False
if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, __file__, None, 1)
    sys.exit()

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False
if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, __file__, None, 1)
    sys.exit()
KEY_FILE = 'keybindings.txt'
toggle_key, stop_key, filter_key = ('1', '2', '3')

def wait_key():
    print('>> Nhấn phím bất kỳ hoặc chuột...')
    pass
    key_event = keyboard.read_event(suppress=True)
    if key_event.event_type == keyboard.KEY_DOWN:
        print(f'   -> Nhận: {key_event.name.upper()}')
        return key_event.name.lower()

def save_keys():
    with open(KEY_FILE, 'w') as f:
        f.write(f'{toggle_key}\n{stop_key}\n{filter_key}\n')

def load_keys():
    global toggle_key  # inserted
    global filter_key  # inserted
    global stop_key  # inserted
    if not os.path.exists(KEY_FILE):
        print('Thiết lập phím lần đầu:')
        print('1. Tele')
        toggle_key = wait_key()
        print('2. Freeze')
        stop_key = wait_key()
        print('3. Ghost')
        filter_key = wait_key()
        save_keys()
    return None
FILTER_O = '(udp.DstPort >= 10010 and udp.DstPort <= 10021) and udp.PayloadLength >= 45 and not udp.DstPort == 10010 and not udp.DstPort == 10021'
FILTER_I = '(udp.SrcPort >= 10011 and udp.SrcPort <= 10019) and ip and ip.Protocol == 17 and ip.Length >= 52 and ip.Length <= 1491'
FILTER_F = '(udp.PayloadLength >= 50 and udp.PayloadLength <= 300) and (udp.DstPort >= 10011 and udp.DstPort <= 10020)'
tele_mode, freeze_mode, ghost_mode = (False, False, False)
R_O, R_I, R_F = (False, False, False)
W_O, W_I, W_F = (None, None, None)
packet_tele, packet_freeze, packet_ghost = ([], [], [])
lock = threading.Lock()

class AppState(Enum):
    IDLE = 'idle'
    CAPTURING_PACKETS = 'capturing'
    WAITING_FOR_HOTKEY = 'waiting_hotkey'
    SETTING_HOTKEY = 'setting_hotkey'

@dataclass
class HotkeyConfig:
    key: str = ''
    display_name: str = ''
    is_valid: bool = False

@dataclass
class AppConfig:
    hotkey: HotkeyConfig
    audio_enabled: bool = True
    ghost_hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    freeze_hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)

@dataclass
class NetworkStats:
    packets_held_tele: int = 0
    packets_held_ghost: int = 0
    packets_held_freeze: int = 0
    packets_sent_tele: int = 0
    packets_sent_ghost: int = 0
    packets_sent_freeze: int = 0
    total_processed: int = 0
    bytes_held_tele: int = 0
    bytes_held_ghost: int = 0
    bytes_held_freeze: int = 0
    bytes_sent_tele: int = 0
    bytes_sent_ghost: int = 0
    bytes_sent_freeze: int = 0
    network_usage: float = 0.0
    ping: int = 0
    upload_speed: float = 0.0
    download_speed: float = 0.0
    cpu_percent: float = 0.0

class StatusSignals(QObject):
    update_status = pyqtSignal(str, str)
    update_packet_count = pyqtSignal(int, str)
    update_hotkey = pyqtSignal(str)
    update_ghost_hotkey = pyqtSignal(str)
    update_freeze_hotkey = pyqtSignal(str)
    update_button_state = pyqtSignal(bool, str)
    update_overlay_status = pyqtSignal(dict)
    update_network_stats = pyqtSignal(object)
    update_signal_wave = pyqtSignal(float, float, float)
    update = pyqtSignal(bool, bool, bool)
    console = pyqtSignal()
signals = StatusSignals()

class AudioManager:
    def __init__(self, config):
        self.config = config

    def play_beep(self, frequency=500, duration=300):
        if not self.config.audio_enabled:
            pass  # postinserted
        return None

    def play_toggle_on(self):
        self.play_beep(600, 120)

    def play_toggle_off(self):
        self.play_beep(400, 150)

class MockWindow:
    def __init__(self):
        self.signals = StatusSignals()
        self.app_config = AppConfig(hotkey=HotkeyConfig(), ghost_hotkey=HotkeyConfig(), freeze_hotkey=HotkeyConfig(), audio_enabled=True)
        self.audio_manager = AudioManager(self.app_config)
        self.network_stats = NetworkStats()
        self.session_packets_sent_tele = 0
        self.session_bytes_sent_tele = 0

    def update_button_state(self, is_on, mode_name):
        signals.update.emit(tele_mode, freeze_mode, ghost_mode)
        signals.console.emit()
window = MockWindow()

class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.7)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(1)
        self.labels = {}
        for name in ['TELE', 'FREEZE', 'GHOST']:
            label = QLabel(f'{name}: OFF')
            label.setFont(QFont('Arial', 8, QFont.Weight.Normal))
            label.setStyleSheet('color: red; background-color: rgba(0,0,0,60); padding: 1px;')
            self.layout.addWidget(label)
            self.labels[name] = label
        self.move(10, 10)
        self._dragging = False
        self._drag_position = QPoint()
        signals.update.connect(self.update_status)

    def update_status(self, t, f, g):
        self.labels['TELE'].setText(f"TELE: {('ON' if t else 'OFF')}")
        self.labels['FREEZE'].setText(f"FREEZE: {('ON' if f else 'OFF')}")
        self.labels['GHOST'].setText(f"GHOST: {('ON' if g else 'OFF')}")
        for name, val in zip(['TELE', 'FREEZE', 'GHOST'], [t, f, g]):
            color = 'lime' if val else 'red'
            self.labels[name].setStyleSheet(f'color: {color}; background-color: rgba(0,0,0,60); padding: 1px;')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.pos()
        return None

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_position)
        return None

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
        return None

def print_status():
    sys.stdout.write('[H')
    sys.stdout.write('[J')

    def s(x):
        return f'{Fore.GREEN}[ON]{Style.RESET_ALL}' if x else f'{Fore.RED}[OFF]{Style.RESET_ALL}'
    max_len = len('Telekill Infinite  [ON]')
    sys.stdout.write(f"Freeze Enemy       {s(freeze_mode):<{max_len - len('Freeze Enemy       ')}}\n")
    sys.stdout.write(f"Ghost Hack         {s(ghost_mode):<{max_len - len('Ghost Hack         ')}}\n")
    sys.stdout.write(f"Telekill Infinite  {s(tele_mode):<{max_len - len('Telekill Infinite  ')}}\n")
    sys.stdout.flush()
signals.console.connect(print_status)

def send_packets(lst, f):
    try:
        with pydivert.WinDivert(f, layer=pydivert.Layer.NETWORK) as s:
            for pkt in lst:
                try:
                    s.send(pydivert.Packet(pkt.raw, pkt.interface, pkt.direction))
        except:
            continue
    except Exception as e:
        return None

def toggle_tele():
    global tele_mode  # inserted
    global app_state  # inserted
    app_state = AppState.IDLE
    if tele_mode:
        with lock:
            tele_mode = False
            to_send = list(packet_tele)
            packet_tele.clear()
        window.update_button_state(False, 'Teleport')
        window.audio_manager.play_toggle_off()

        def send_burst_packets(packets):
            try:
                sent_count = 0
                bytes_sent = 0
                with pydivert.WinDivert(FILTER_O, layer=pydivert.Layer.NETWORK) as sender:
                    chunk_size = 6
                    delay = 0.044
                        chunk = packets[i:i + chunk_size]
                        for pkt in chunk:
                            try:
                                pkt_rebuilt = pydivert.Packet(pkt.raw, pkt.interface, pkt.direction)
                                sender.send(pkt_rebuilt)
                                sent_count += 1
                                bytes_sent += len(pkt.raw)
                        else:  # inserted
                            time.sleep(delay)
                        window.session_packets_sent_tele = sent_count
                        window.session_bytes_sent_tele = bytes_sent
                        window.network_stats.packets_sent_tele = sent_count
                        window.network_stats.bytes_sent_tele = bytes_sent
                        window.network_stats.total_processed += sent_count
                    except Exception as e:
                        continue
            except Exception as e:
                return None
        if to_send:
            threading.Thread(target=lambda: send_burst_packets(to_send), daemon=True).start()
    signals.update.emit(tele_mode, freeze_mode, ghost_mode)
    signals.console.emit()

def toggle_freeze():
    global freeze_mode  # inserted
    global W_I  # inserted
    global R_I  # inserted
    if freeze_mode:
        freeze_mode = R_I = False
        W_I.close()
        packets = []
        with lock:
            packets = list(packet_freeze)
            packet_freeze.clear()
        threading.Thread(target=send_packets, args=(packets, FILTER_I), daemon=True).start()
        winsound.Beep(400, 150)
    signals.update.emit(tele_mode, freeze_mode, ghost_mode)
    signals.console.emit()
    except:
        pass  # postinserted
    pass

def toggle_ghost():
    global ghost_mode  # inserted
    global R_F  # inserted
    global W_F  # inserted
    if ghost_mode:
        ghost_mode = R_F = False
        W_F.close()
        packets = []
        with lock:
            packets = list(packet_ghost)
            packet_ghost.clear()
        threading.Thread(target=send_packets, args=(packets, FILTER_F), daemon=True).start()
        winsound.Beep(400, 150)
    signals.update.emit(tele_mode, freeze_mode, ghost_mode)
    signals.console.emit()
    except:
        pass  # postinserted
    pass

def stop_all():
    global R_I  # inserted
    global R_F  # inserted
    global R_O  # inserted
    R_O = R_I = R_F = False
    toggle_tele() if tele_mode else None
    if freeze_mode:
        toggle_freeze()
    if ghost_mode:
        toggle_ghost()
    keyboard.unhook_all()
    app.quit()

def divert(filter_str, flag_ref, packet_list, cond_ref):
    h = None
        except Exception as e:
            h = None
            time.sleep(0.1)
if __name__ == '__main__':
    load_keys()
    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.show()
    keyboard.on_press(lambda e: {toggle_key: toggle_tele, stop_key: toggle_freeze, filter_key: toggle_ghost, 'f10': stop_all}.get(e.name.lower(), lambda: None)())
    R_O = True
    threading.Thread(target=divert, args=(FILTER_O, lambda: R_O, packet_tele, lambda: tele_mode), daemon=True).start()
    threading.Thread(target=divert, args=(FILTER_I, lambda: R_I, packet_freeze, lambda: freeze_mode), daemon=True).start()
    threading.Thread(target=divert, args=(FILTER_F, lambda: R_F, packet_ghost, lambda: ghost_mode), daemon=True).start()
    status_timer = QTimer()
    status_timer.setInterval(1000)
    status_timer.timeout.connect(print_status)
    status_timer.start()
    print_status()
    sys.exit(app.exec())
