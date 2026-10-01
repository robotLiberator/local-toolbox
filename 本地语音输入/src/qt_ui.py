"""Antialiased, per-pixel transparent desktop UI for the local recognizer."""
import math
import queue
import time
import threading
from types import SimpleNamespace

import pyperclip
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QPlainTextEdit, QWidget, QSystemTrayIcon

from app import DictationApp, HOTKEY, ROOT, build_recognizers, keyboard
from local_cleanup import LocalCleaner, load_enabled
from speech_gate import SpeechGate
from paths import user_file, VERSION
import terminology


class Surface(QWidget):
    scheduled = Signal(int, object)

    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('本地语音输入')
        self.scheduled.connect(lambda delay, fn: QTimer.singleShot(delay, fn))

    def after(self, delay, fn):
        self.scheduled.emit(delay, fn)

    def title(self, title):
        self.setWindowTitle(title)

    def paintEvent(self, event):
        self.owner.paint(QPainter(self))

    def event_info(self, event):
        local, global_ = event.position(), event.globalPosition()
        return SimpleNamespace(x=int(local.x()), y=int(local.y()), x_root=int(global_.x()), y_root=int(global_.y()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.on_press(self.event_info(event))
        elif event.button() == Qt.MouseButton.RightButton:
            self.owner.right_click()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.owner.on_drag(self.event_info(event))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.on_release(self.event_info(event))


class Flag:
    def __init__(self):
        self.value = True

    def get(self):
        return self.value


class SmoothDictationApp(DictationApp):
    def __init__(self):
        self.application = QApplication.instance() or QApplication([])
        self.events = queue.Queue()
        self.audio_queue = queue.Queue()
        self.session = None
        self.recognition_lock = threading.Lock()
        self.recording = self.processing = self.expanded = False
        self.input_stream = None
        self.target_window = self.last_external_window = 0
        self.last_result = ''
        self.last_raw_result = ''
        self.last_cleaned_result = ''
        self.cleanup_status = ''
        self.position_path = user_file('position.json')
        self.press_info = None
        self.dragging = False
        self.bubble_ox = self.bubble_oy = 0
        self.card_y = 5
        self.copy_bounds = (212,117,246,147)
        self.close_bounds = (252,117,283,147)
        self.wave_target = self.wave_level = self.copied_until = 0.0
        self.mouse_hook = self.mouse_hook_callback = None
        self.mouse_hook_thread_id = 0
        self.auto_paste = Flag()
        self.cleanup_stutters = Flag()
        self.smart_cleanup = Flag()
        self.smart_cleanup.value = load_enabled()
        self.terminology_enabled = Flag()
        self.terminology_enabled.value = terminology.load_enabled()
        self.cleaner = LocalCleaner()
        self.bubble_x, self.bubble_y = self.load_position()
        self.online, self.offline, self.punctuation = build_recognizers()
        self.speech_gate = SpeechGate()
        self.root = Surface(self)
        self.text = QPlainTextEdit(self.root)
        self.text.setFont(QFont('Microsoft YaHei UI', 11))
        self.text.setStyleSheet('QPlainTextEdit { background: #fff0ba; color: #49463f; border: none; padding: 0; }')
        self.text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.menu = QMenu(self.root)
        self.menu.addAction('查看上次结果', self.show_cleaned_result)
        self.menu.addAction('复制上次结果', self.copy_result)
        action = self.menu.addAction('直接输入到原光标')
        action.setCheckable(True)
        action.setChecked(True)
        action.toggled.connect(lambda value: setattr(self.auto_paste, 'value', value))
        cleanup_action = self.menu.addAction('轻量口吃去重')
        cleanup_action.setCheckable(True)
        cleanup_action.setChecked(True)
        cleanup_action.toggled.connect(lambda value: setattr(self.cleanup_stutters, 'value', value))
        smart_action = self.menu.addAction('智能口语整理（本地）')
        smart_action.setCheckable(True)
        smart_action.setChecked(self.smart_cleanup.get())
        def change_cleanup(value):
            self.smart_cleanup.value = value
            self.cleanup_changed()
        smart_action.toggled.connect(change_cleanup)
        terms_action = self.menu.addAction('计算机／AI 术语纠错（本地）')
        terms_action.setCheckable(True)
        terms_action.setChecked(self.terminology_enabled.get())
        def change_terms(value):
            self.terminology_enabled.value = value
            terminology.save_enabled(value)
        terms_action.toggled.connect(change_terms)
        self.menu.addAction('编辑个人术语词表', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(terminology.dictionary_file()))))
        self.menu.addAction('查看识别原文', self.show_raw_result)
        self.menu.addSeparator()
        self.menu.addAction('本地语音输入 ' + VERSION).setEnabled(False)
        self.menu.addAction('退出', self.quit_app)
        self.menu.addAction('取消本次录音 / 整理', lambda: self.cancel_recording())
        icon = QPixmap(64, 64)
        icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#fff0b5'))
        painter.drawEllipse(QRectF(2, 2, 60, 60))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor('#514b41'), 3))
        painter.drawRoundedRect(QRectF(26, 14, 12, 24), 6, 6)
        painter.drawArc(QRectF(20, 24, 24, 24), 180 * 16, 180 * 16)
        painter.drawLine(32, 48, 32, 54)
        painter.end()
        self.tray = QSystemTrayIcon(QIcon(icon), self.root)
        self.tray.setToolTip('本地语音输入：左键小球开始／结束，右键小球取消')
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        self.hotkeys = keyboard.GlobalHotKeys({HOTKEY: lambda: self.events.put(('toggle', None))})
        self.hotkeys.start()
        self.start_mouse_hook()
        self.collapse()
        self.root.show()
        self.root.after(50,self.drain_events)
        self.root.after(50,self.animate_waveform)
        self.root.after(100,self.track_external_window)
        if self.smart_cleanup.get():
            self.cleaner.warm_up()

    def work_area(self):
        application = QApplication.instance()
        if application:
            point = QPoint(getattr(self,'bubble_x',0)+32, getattr(self,'bubble_y',0)+32)
            screen = application.screenAt(point) if hasattr(self,'bubble_x') else application.primaryScreen()
            rect = (screen or application.primaryScreen()).availableGeometry()
            return rect.left(), rect.top(), rect.x()+rect.width(), rect.y()+rect.height()
        return super().work_area()

    def right_click(self):
        if self.recording or self.processing:
            self.cancel_recording()
        else:
            # A right click also dismisses a completed note, without deleting it.
            self.collapse()

    def place_widget(self):
        if self.expanded:
            left,top,right,bottom = self.work_area()
            self.bubble_ox = 240 if self.bubble_x >= (left+right)//2 else 0
            self.bubble_oy = 162 if self.bubble_y >= (top+bottom)//2 else 0
            self.card_y = 5 if self.bubble_oy else 73
            controls_y = self.card_y+112
            self.copy_bounds = (212,controls_y,246,controls_y+30)
            self.close_bounds = (252,controls_y,283,controls_y+30)
            self.root.setGeometry(self.bubble_x-self.bubble_ox,self.bubble_y-self.bubble_oy,304,226)
            self.text.setGeometry(23,self.card_y+17,252,91)
        else:
            self.bubble_ox = self.bubble_oy = 0
            self.root.setGeometry(self.bubble_x,self.bubble_y,64,64)
        self.root.update()

    def collapse(self):
        if self.recording or self.processing:
            return
        self.expanded = False
        self.text.hide()
        self.place_widget()
        self.draw_widget()

    def expand(self):
        if not self.last_result or self.recording or self.processing:
            return
        self.expanded = True
        self.place_widget()
        self.text.show()
        self.root.raise_()
        self.draw_widget()

    def show_text(self,value):
        self.last_result = value
        self.text.setPlainText(value)
        self.expand()

    def copy_result(self):
        value = self.text.toPlainText().strip() if self.expanded else self.last_result
        if value:
            pyperclip.copy(value)
            self.copied_until = time.monotonic()+1.5
            self.draw_widget()

    def drain_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind,payload = event[:2]
                if len(event) == 3 and (event[2] is not self.session or event[2].cancelled.is_set()):
                    continue
                if kind == 'level': self.wave_target = float(payload)
                elif kind == 'cancel': self.cancel_recording(payload)
                elif kind == 'toggle': self.toggle()
                elif kind == 'final': self.finish(str(payload))
                elif kind == 'transcript': self.finish_transcript(payload)
                elif kind == 'error':
                    self.processing = False
                    self.show_text(f'识别失败：{payload}')
                elif kind == 'hook_error': self.root.title(f'本地语音输入 - 侧键失败 {payload}')
                elif kind == 'hook_ready': self.root.title('本地语音输入 - 侧键就绪')
        except queue.Empty:
            pass
        self.root.after(50,self.drain_events)

    def draw_widget(self):
        self.root.update()

    def paint(self,p):
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        ink = QColor('#514b41')
        def pen(width=2):
            p.setPen(QPen(ink,width,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
        def line(x1,y1,x2,y2): p.drawLine(QPointF(x1,y1),QPointF(x2,y2))
        if self.expanded:
            y = self.card_y
            tail_x = 259 if self.bubble_ox else 45
            shape = QPainterPath()
            shape.addRoundedRect(QRectF(8,y,284,148),15,15)
            tail = QPainterPath()
            tail.moveTo(tail_x-13,y+146 if self.bubble_oy else y+2)
            tail.lineTo(tail_x,y+159 if self.bubble_oy else y-11)
            tail.lineTo(tail_x+11,y+146 if self.bubble_oy else y+2)
            tail.closeSubpath()
            shape = shape.united(tail)
            p.setPen(Qt.PenStyle.NoPen)
            for spread in range(7,0,-1):
                p.setBrush(QColor(81,67,38,3))
                p.drawRoundedRect(QRectF(8-spread/2,y+3-spread/2,284+spread,148+spread),15+spread/2,15+spread/2)
            p.fillPath(shape,QColor('#fff0ba'))
            pen(1.7)
            cy = self.copy_bounds[1]
            if time.monotonic()<self.copied_until:
                line(220,cy+15,226,cy+21);line(226,cy+21,239,cy+6)
            else:
                p.drawRoundedRect(QRectF(218,cy+5,14,14),1.5,1.5)
                p.setBrush(QColor('#fff0ba'))
                p.drawRoundedRect(QRectF(223,cy+10,14,14),1.5,1.5)
            pen()
            cy = self.close_bounds[1]
            line(260,cy+7,275,cy+22);line(275,cy+7,260,cy+22)
        ox,oy = self.bubble_ox,self.bubble_oy
        p.setPen(Qt.PenStyle.NoPen)
        for spread in range(7,0,-1):
            p.setBrush(QColor(81,67,38,4))
            p.drawEllipse(QRectF(ox+5-spread/2,oy+8-spread/2,52+spread,52+spread))
        color = '#ffd5bf' if self.recording else '#e6d7f7' if self.processing else '#fff0b5'
        p.setBrush(QColor(color));p.drawEllipse(QRectF(ox+5,oy+5,52,52))
        cx,cy=ox+31,oy+31
        pen(2.3)
        if self.recording:
            for i in range(5):
                h=3+self.wave_level*(15 if i==2 else 11 if i in (1,3) else 6)+2*(1+math.sin(time.monotonic()*7+i))
                x=cx+(i-2)*5;line(x,cy-h,x,cy+h)
        elif self.processing:
            p.setPen(Qt.PenStyle.NoPen)
            phase=int(time.monotonic()*12)%10
            for i in range(10):
                angle=i*math.tau/10
                x,y=cx+13*math.sin(angle),cy-13*math.cos(angle)
                p.setBrush(ink if (i-phase)%10<3 else QColor('#b9a7cc'))
                p.drawEllipse(QPointF(x,y),1.7,1.7)
        else:
            p.drawRoundedRect(QRectF(cx-5,cy-12,10,19),5,5)
            path=QPainterPath();path.moveTo(cx-10,cy-2);path.cubicTo(cx-10,cy+17,cx+10,cy+17,cx+10,cy-2)
            p.drawPath(path);line(cx,cy+12,cx,cy+18);line(cx-4,cy+18,cx+4,cy+18)
        p.end()

    def quit_app(self):
        if self.session:
            self.session.cancelled.set()
            self.session.audio_queue.put(None)
        self.cleaner.close()
        if self.input_stream:
            self.recording=False
            self.input_stream.stop();self.input_stream.close()
        self.hotkeys.stop()
        self.tray.hide()
        import ctypes
        if self.mouse_hook: ctypes.windll.user32.UnhookWindowsHookEx(self.mouse_hook)
        if self.mouse_hook_thread_id: ctypes.windll.user32.PostThreadMessageW(self.mouse_hook_thread_id,0x0012,0,0)
        self.application.quit()

    def run(self):
        self.application.exec()
