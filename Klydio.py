import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedLayout, QSpacerItem, QSizePolicy,
    QLabel, QPushButton, QSlider, QComboBox, QCheckBox, QFileDialog, QFrame,
    QGroupBox,QGraphicsDropShadowEffect,QApplication,QToolButton,QGraphicsOpacityEffect
)
from PyQt5.QtGui import QIcon, QPixmap, QFont,QTransform,QColor
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve,pyqtProperty,QTimer,QEvent,pyqtSignal

class MouseTrackingFrame(QFrame):
    mouse_moved = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(MouseTrackingFrame, self).__init__(*args, **kwargs)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        self.mouse_moved.emit()
        super().mouseMoveEvent(event)

from mpv import MPV

class MPVPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setStyleSheet("background-color: #1e1e1e;")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        # Main wrapper
        self.wrapper = QWidget(self)
        self.wrapper.setStyleSheet("background-color: transparent;")

        # Video area
        self.video_frame = QWidget(self.wrapper)
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setAlignment(Qt.AlignCenter)

        # Placeholder
        self.placeholder = QLabel("No video loaded")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color: #888; font-size: 24px;")
        video_layout.addWidget(self.placeholder)


        # Buffering Spinner
        self.buffering = QLabel(self.video_frame)
        self.buffering.setPixmap(QPixmap("icons/spinner.gif"))  # <- use a real spinner.gif
        self.buffering.setAlignment(Qt.AlignCenter)
        self.buffering.hide()

        # Overlay controls
        self.overlay = QWidget(self.wrapper)
        self.overlay.setFixedHeight(50)
        self.overlay.setStyleSheet("background-color: #2e2e2e; border-radius: 10px;")
        self.overlay.hide()

        overlay_layout = QHBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(10, 0, 10, 0)
        overlay_layout.setSpacing(10)

        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(QIcon("icons/play.svg"))
        self.play_pause_btn.setIconSize(QSize(24, 24))
        self.play_pause_btn.setFixedSize(36, 36)
        self.play_pause_btn.setFlat(True)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        overlay_layout.addWidget(self.play_pause_btn)

        self.timestamp = QLabel("00:00 / 00:00")
        self.timestamp.setStyleSheet("color: #ccc; font-size: 14px;")
        overlay_layout.addWidget(self.timestamp)

        self.progress_bar = QSlider(Qt.Horizontal)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.sliderMoved.connect(self.set_position)
        overlay_layout.addWidget(self.progress_bar)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        overlay_layout.addWidget(self.volume_slider)

        # Opacity effect for overlay
        self.overlay_opacity = QGraphicsOpacityEffect()
        self.overlay.setGraphicsEffect(self.overlay_opacity)
        self.overlay.setMouseTracking(True)
        self.overlay.installEventFilter(self)
        self._hovering_overlay = False



        self.fade_anim = QPropertyAnimation(self.overlay_opacity, b"opacity")
        self.fade_anim.setDuration(300)
 
        slider_style = """
        QSlider::groove:horizontal {
            height: 6px;
            background: #444;
            border-radius: 3px;
        }

        QSlider::handle:horizontal {
            background: #00aaff;
            border: none;
            height: 16px;
            width: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }

        QSlider::sub-page:horizontal {
            background: #00aaff;
            border-radius: 3px;
        }

        QSlider::add-page:horizontal {
            background: #333;
            border-radius: 3px;
        }
        """

        self.progress_bar.setStyleSheet(slider_style)
        self.volume_slider.setStyleSheet(slider_style)

        self.overlay_visible = True  # Track current visibility state
        self.video_loaded = False





        # Layouts
        wrapper_layout = QVBoxLayout(self.wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(self.video_frame)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.wrapper)

        # MPV instance
        self.mpv = MPV(
            wid=str(int(self.video_frame.winId())),
            input_default_bindings=True,
            input_vo_keyboard=True,
            osc=False
        )

        # --- Connect MPV events ---
        self.mpv.event_callback('file-loaded')(self.on_file_loaded)
        self.mpv.observe_property('pause', self.on_pause_change)
        self.mpv.observe_property('time-pos', self.on_time_pos_change)
        self.mpv.observe_property('duration', self.on_duration_change)

        # State
        self.playing = False
        self.paused = False
        self.current_time = 0
        self.total_time = 0

        # Timers
        self.cursor_timer = QTimer(self)
        self.cursor_timer.setInterval(300)
        self.cursor_timer.timeout.connect(self.check_cursor_visibility)
        self.cursor_timer.start()

        self.cursor_hide_timer = QTimer(self)
        self.cursor_hide_timer.setInterval(3000)
        self.cursor_hide_timer.setSingleShot(True)
        self.cursor_hide_timer.timeout.connect(self.hide_cursor)

        # Mouse tracking
        self.video_frame.setMouseTracking(True)
        self.video_frame.installEventFilter(self)

    def eventFilter(self, source, event):
        if source == self.video_frame and event.type() == QEvent.MouseMove:
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            self.cursor_hide_timer.start()
        elif source == self.overlay:
            if event.type() == QEvent.Enter:
                self._hovering_overlay = True
                self.cursor_hide_timer.stop()
            elif event.type() == QEvent.Leave:
                self._hovering_overlay = False
                self.cursor_hide_timer.start()
        return super().eventFilter(source, event)


    def hide_cursor(self):
        if self._hovering_overlay:
            return  # Don't hide if hovering over controls

        QApplication.setOverrideCursor(Qt.BlankCursor)


    def check_cursor_visibility(self):
        cursor = QApplication.overrideCursor()
        is_cursor_visible = cursor is None or cursor.shape() != Qt.BlankCursor

        if is_cursor_visible and not self.overlay_visible:
            self.fade_overlay_in()
            self.overlay_visible = True
        elif not is_cursor_visible and self.overlay_visible:
            self.fade_overlay_out()
            self.overlay_visible = False


    def fade_overlay_in(self):
        if self.overlay_visible or not self.video_loaded:
            return  # Already shown, or no video — skip

        self.overlay.show()
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.overlay_opacity.opacity())
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.finished.disconnect() if self.fade_anim.receivers(self.fade_anim.finished) > 0 else None
        self.fade_anim.finished.connect(lambda: setattr(self, 'overlay_visible', True))
        self.fade_anim.start()


    def fade_overlay_out(self):
        if not self.overlay_visible:
            return  # Already hidden, skip
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.overlay_opacity.opacity())
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.finished.disconnect() if self.fade_anim.receivers(self.fade_anim.finished) > 0 else None
        self.fade_anim.finished.connect(self._hide_overlay)

        self.fade_anim.start()

    def _hide_overlay(self):
        self.overlay.hide()
        self.overlay_visible = False



    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize(self.wrapper.width() - 100, 50)
        self.overlay.move(
            (self.wrapper.width() - self.overlay.width()) // 2,
            self.wrapper.height() - 80
        )
        self.buffering.move(
            (self.video_frame.width() - self.buffering.width()) // 2,
            (self.video_frame.height() - self.buffering.height()) // 2
        )

    def play_file(self, filepath):
        self.mpv.play(filepath)
        self.buffering.show()
        self.placeholder.hide()

    def on_file_loaded(self, event):
        self.playing = True
        self.paused = False
        self.video_loaded = True  # <-- add this
        self.buffering.hide()
        self.update_play_pause_icon()


    def on_pause_change(self, name, value):
        self.paused = value
        self.update_play_pause_icon()

    def on_time_pos_change(self, name, value):
        if self.playing and value is not None:
            self.current_time = value
            self.update_timestamp()

    def on_duration_change(self, name, value):
        if self.playing and value is not None:
            self.total_time = value
            self.update_timestamp()
    
    def set_active(self, active):
        if active:
            self.cursor_timer.start()
            self.cursor_hide_timer.start()
        else:
            self.cursor_timer.stop()
            self.cursor_hide_timer.stop()
            QApplication.setOverrideCursor(Qt.ArrowCursor)
            self.fade_overlay_in()
        if not active:
            self.video_loaded = False
            self.overlay_visible = False
            self.overlay.hide()
            QApplication.setOverrideCursor(Qt.ArrowCursor)




    def update_timestamp(self):
        if self.total_time > 0:
            self.timestamp.setText(f"{self._format_time(self.current_time)} / {self._format_time(self.total_time)}")
            self.progress_bar.setValue(int((self.current_time / self.total_time) * 1000))
        else:
            self.timestamp.setText("00:00 / 00:00")
            self.progress_bar.setValue(0)

    def toggle_play_pause(self):
        if self.playing:
            self.mpv.command('cycle', 'pause')

    def update_play_pause_icon(self):
        if self.paused:
            self.play_pause_btn.setIcon(QIcon("icons/play.svg"))
        else:
            self.play_pause_btn.setIcon(QIcon("icons/pause.svg"))

    def set_position(self, value):
        if self.playing and self.total_time > 0:
            self.mpv.seek((value / 1000.0) * self.total_time, reference='absolute')

    def set_volume(self, value):
        self.mpv.volume = value

    def _format_time(self, seconds):
        seconds = int(seconds)
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def keyPressEvent(self, event):
        if not self.playing:
            return

        if event.key() == Qt.Key_Space:
            self.toggle_play_pause()

        elif event.key() == Qt.Key_Left:
            self.mpv.command('seek', -5)

        elif event.key() == Qt.Key_Right:
            self.mpv.command('seek', 5)

        elif event.key() == Qt.Key_Up:
            volume = self.mpv.volume or 50
            volume = min(volume + 5, 100)
            self.mpv.volume = volume
            self.volume_slider.setValue(int(volume))

        elif event.key() == Qt.Key_Down:
            volume = self.mpv.volume or 50
            volume = max(volume - 5, 0)
            self.mpv.volume = volume
            self.volume_slider.setValue(int(volume))


class SpinningLogo(QLabel):
    def __init__(self, icon_path, size=28, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setScaledContents(True)
        self.original_pixmap = QPixmap(icon_path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(self.original_pixmap)
        self._angle = 0

        self.anim = QPropertyAnimation(self, b"angle")
        self.anim.setDuration(500)
        self.anim.setStartValue(0)
        self.anim.setEndValue(360)
        self.anim.setLoopCount(1)

    def enterEvent(self, event):
        self.anim.start()

    def get_angle(self):
        return self._angle

    def set_angle(self, value):
        self._angle = value
        transform = QTransform().rotate(value)
        rotated_pixmap = self.original_pixmap.transformed(transform, Qt.SmoothTransformation)
        self.setPixmap(rotated_pixmap)

    angle = pyqtProperty(float, fget=get_angle, fset=set_angle)


class TopBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet("background-color: #2a2a2a;")



        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        # App logo
        self.logo = SpinningLogo("icons/App.png", size=28)
        self.layout.addWidget(self.logo)

        # App title
        self.title = QLabel("Klydio")
        self.title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        self.layout.addWidget(self.title)

        # Spacer
        self.layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

            # Minimize button
        self.minimize_btn = self.create_icon_button("icons/minimize.svg")
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #ffc107; /* Yellow */
            }
        """)
        self.minimize_btn.clicked.connect(self.parent().showMinimized)
        self.layout.addWidget(self.minimize_btn)

        # Maximize / Restore button
        self.maximize_btn = self.create_icon_button("icons/maximize.svg")
        self.maximize_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #008adf; /* Cyan / Blue */
            }
        """)
        self.maximize_btn.clicked.connect(self.toggle_maximize_restore)
        self.layout.addWidget(self.maximize_btn)

        # Close button
        self.close_btn = self.create_icon_button("icons/close.svg")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #f44336; /* Red */
            }
        """)
        self.close_btn.clicked.connect(self.parent().close)
        self.layout.addWidget(self.close_btn)

        self.drag_pos = None

    def create_icon_button(self, icon_path):
        btn = QPushButton()
        btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(24, 24))
        btn.setFixedSize(36, 36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        return btn

    def toggle_maximize_restore(self):
        if self.parent().isMaximized():
            self.parent().showNormal()
            self.maximize_btn.setIcon(QIcon("icons/maximize.svg"))
        else:
            self.parent().showMaximized()
            self.maximize_btn.setIcon(QIcon("icons/maximize.svg"))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.parent().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.parent().isMaximized():
            self.parent().move(event.globalPos() - self.drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        self.toggle_maximize_restore()




class HomeScreen(QWidget): 
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("Klydio")
        self.setGeometry(100, 100, 1280, 720)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")
        self.sidebar_expanded = False
        self.selected_button = None

        


        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.top_bar = TopBar(self)
        layout.addWidget(self.top_bar)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        layout.addLayout(main_layout)

        # Sidebar
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setFixedWidth(60)
        self.sidebar_frame.setStyleSheet("background-color: #2a2a2a;")
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(12)
        self.sidebar_layout.setAlignment(Qt.AlignTop)

        self.toggle_button = self.create_sidebar_button("icons/menu.svg", "Menu")
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        self.sidebar_layout.addWidget(self.toggle_button)
        self.sidebar_layout.addSpacing(10)

        self.menu_buttons = []
        menu_items = [
            ("icons/home.png", "Home"),
            ("icons/video.png", "Video"),
            ("icons/music.png", "Music")
        ]

        for icon_path, label in menu_items:
            btn = self.create_sidebar_button(icon_path, label)
            btn.clicked.connect(lambda _, b=btn: self.select_menu(b))
            self.sidebar_layout.addWidget(btn)
            self.menu_buttons.append((btn, icon_path, label))

        # Add a separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: gray;")
        self.sidebar_layout.addWidget(line)

        self.sidebar_layout.addSpacing(20)

        # Add Player button
        self.player_button = self.create_sidebar_button("icons/App.png", "Player")
        self.player_button.clicked.connect(lambda _, b=self.player_button: self.select_menu(b))
        self.sidebar_layout.addWidget(self.player_button)
        self.menu_buttons.append((self.player_button, "icons/App.png", "Player"))



        self.sidebar_layout.addStretch()

        self.bottom_button = self.create_sidebar_button("icons/settings.svg", "Settings")
        self.bottom_button.clicked.connect(lambda _, b=self.bottom_button: self.select_menu(b))
        self.bottom_button.label_text = "Settings"
        self.sidebar_layout.addWidget(self.bottom_button)
        self.menu_buttons.append((self.bottom_button, "icons/settings.svg", "Settings"))

        main_layout.addWidget(self.sidebar_frame)

        # Content and page manager
        self.pages = QStackedLayout()
        self.page_widgets = {}

        # Home Page
        home_page_container = QWidget()
        home_page_stack = QStackedLayout(home_page_container)
        home_page_stack.setContentsMargins(0, 0, 0, 0)

        # Base home page (main layout)
        home_page = QWidget()
        home_page_layout = QVBoxLayout(home_page)
        home_page_layout.setContentsMargins(0, 0, 0, 0)
        home_page_layout.setSpacing(0)

        # Content section (perfectly centered vertically)
        center_content = QWidget()
        self.content_layout = QVBoxLayout(center_content)
        self.content_layout.setAlignment(Qt.AlignCenter)

        # Expand the space around center_content
        content_wrapper = QWidget()
        content_wrapper_layout = QVBoxLayout(content_wrapper)
        content_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        content_wrapper_layout.setSpacing(0)
        content_wrapper_layout.addStretch(4)
        content_wrapper_layout.addWidget(center_content)
        content_wrapper_layout.addStretch(5)  # Change this value to adjust how far down it sits

        # Add to main home layout
        home_page_layout.addWidget(content_wrapper, stretch=1)

        home_page_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Footer
        footer = self.create_footer("Home", "icons/home.png")
        home_page_layout.addWidget(footer, alignment=Qt.AlignRight)

        # Overlay layer for bottom-right button
        overlay = QWidget()
        overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(0, 0, 15, 15)
        overlay_layout.setAlignment(Qt.AlignBottom | Qt.AlignRight)

        home_btn = QPushButton("  Home")
        home_btn.setIcon(QIcon("icons/home.png"))
        home_btn.setIconSize(QSize(24, 24))
        home_btn.setFixedSize(110, 40)
        home_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        overlay_layout.addWidget(home_btn)

        # Container to hold both: home_page and floating overlay
        combined_widget = QWidget()
        combined_layout = QStackedLayout(combined_widget)
        combined_layout.setContentsMargins(0, 0, 0, 0)
        combined_layout.addWidget(home_page)
        combined_layout.addWidget(overlay)

        # Add to the stack
        home_page_stack.addWidget(combined_widget)

        # Now add real content to self.content_layout (unchanged)
        side_image_label = QLabel()
        pixmap = QPixmap("icons/Pro.png").scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        side_image_label.setPixmap(pixmap)
        side_image_label.setAlignment(Qt.AlignCenter)

        logo = SpinningLogo("icons/App.png", size=130)
        logo.setAlignment(Qt.AlignVCenter)

        title_texts = QVBoxLayout()
        title = QLabel("Klydio")
        title.setFont(QFont("Segoe UI", 48, QFont.Bold))
        title.setAlignment(Qt.AlignLeft)

        subtitle = QLabel("Let's play")
        subtitle.setStyleSheet("color: #aaa; font-size: 28px;")
        subtitle.setAlignment(Qt.AlignLeft)

        title_texts.addWidget(title)
        title_texts.addWidget(subtitle)

        logo_and_text_layout = QHBoxLayout()
        logo_and_text_layout.setAlignment(Qt.AlignLeft)
        logo_and_text_layout.addWidget(logo)
        logo_and_text_layout.addSpacing(10)
        logo_and_text_layout.addLayout(title_texts)

        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignCenter)
        top_layout.addLayout(logo_and_text_layout)
        top_layout.addSpacing(30)
        top_layout.addWidget(side_image_label)

        self.content_layout.addLayout(top_layout)
        self.content_layout.addSpacing(30)

        open_button = QPushButton("  Open file(s)")
        open_button.setIcon(QIcon("icons/folder.svg"))
        open_button.setIconSize(QSize(30, 30))
        open_button.setFixedWidth(160)
        open_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 18px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        open_button.clicked.connect(self.open_files)
        self.content_layout.addWidget(open_button)


        # Finally add to pages
        self.pages.addWidget(home_page_container)
        self.page_widgets["Home"] = home_page_container


        # Placeholder pages for others
        for _, _, label in self.menu_buttons:
            if label == "Player":
                self.vlc_player = MPVPlayer()
                self.pages.addWidget(self.vlc_player)
                self.page_widgets[label] = self.vlc_player
            elif label != "Home":
                # keep the existing placeholder for other pages
                page = QWidget()
                layout = QVBoxLayout(page)
                layout.addStretch()
                center_label = QLabel(f"{label} Page")
                center_label.setAlignment(Qt.AlignCenter)
                center_label.setStyleSheet("font-size: 24px;")
                layout.addWidget(center_label)
                layout.addStretch()

                footer = self.create_footer(label, f"icons/{label.lower()}.png")
                layout.addWidget(footer)

                self.pages.addWidget(page)
                self.page_widgets[label] = page





        main_layout.addLayout(self.pages)

        # Set default selected page
        if self.menu_buttons:
            self.select_menu(self.menu_buttons[0][0])

    def create_sidebar_button(self, icon_path, label_text):
        text = f"     {label_text}" if self.sidebar_expanded else ""
        btn = QPushButton(text)
        btn.setToolTip(label_text)
        btn.setFocusPolicy(Qt.NoFocus)
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
        else:
            print(f"Missing icon: {icon_path}")
        btn.setIconSize(QSize(24, 24))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        btn.setStyleSheet(self.get_button_style(self.sidebar_expanded, selected=False))
        return btn
    
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_F:
                self.toggle_fullscreen()
                return True
            elif key == Qt.Key_Escape and getattr(self, 'is_fullscreen', False):
                self.exit_fullscreen()
                return True
        return super().eventFilter(obj, event)

    def toggle_fullscreen(self):
        if not hasattr(self, 'is_fullscreen'):
            self.is_fullscreen = False

        if not self.is_fullscreen:
            if not self.isMaximized():
                self.showMaximized()
            self.top_bar.hide()
            self.sidebar_frame.hide()
            self.pages.setContentsMargins(0, 0, 0, 0)
            self.vlc_player.wrapper.layout().setContentsMargins(0, 0, 0, 0)
            self.is_fullscreen = True
        else:
            self.exit_fullscreen()

    def exit_fullscreen(self):
        self.top_bar.show()
        self.sidebar_frame.show()
        self.pages.setContentsMargins(0, 0, 0, 0)
        self.vlc_player.wrapper.layout().setContentsMargins(0, 0, 0, 0)
        self.is_fullscreen = False




    
    def create_footer(self, label, icon_path):
        footer = QHBoxLayout()
        footer.addStretch()

        icon_label = QLabel()
        icon_pixmap = QPixmap(icon_path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)

        text_label = QLabel(label)
        text_label.setStyleSheet("font-size: 14px; color: #ccc;")

        footer.addWidget(icon_label)
        footer.addSpacing(5)
        footer.addWidget(text_label)
        footer.setAlignment(Qt.AlignRight | Qt.AlignBottom)

        wrapper = QWidget()
        wrapper.setLayout(footer)
        return wrapper


    def get_button_style(self, expanded=True, selected=False):
        padding = "padding-left: 20px;" if expanded else "padding-left: 0px;"
        align = "text-align: left;" if expanded else "text-align: center;"
        border = "border-left: 4px solid #00aaff;" if selected else "border-left: none;"
        bg_color = "#555" if selected else "transparent"
        hover_color = "#666" if selected else "#444"

        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                {padding}
                border-radius: 8px;
                {align}
                {border}
                outline: none;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:focus {{
                outline: none;
                border: none;
            }}
        """

    def select_menu(self, button):
        if self.selected_button:
            self.selected_button.setStyleSheet(
                self.get_button_style(self.sidebar_expanded, selected=False)
            )
        self.selected_button = button
        button.setStyleSheet(
            self.get_button_style(self.sidebar_expanded, selected=True)
        )

        label = button.toolTip()
        if label in self.page_widgets:
            widget = self.page_widgets[label]
            index = self.pages.indexOf(widget)
            self.pages.setCurrentIndex(index)

            # Activate/deactivate MPVPlayer mouse logic
            if isinstance(widget, MPVPlayer):
                widget.set_active(True)
            else:
                self.vlc_player.set_active(False)




    def toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        new_width = 300 if self.sidebar_expanded else 60

        animation = QPropertyAnimation(self.sidebar_frame, b"minimumWidth")
        animation.setDuration(100)
        animation.setStartValue(self.sidebar_frame.width())
        animation.setEndValue(new_width)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        animation.start()
        self.animation = animation

        self.toggle_button.setText("     Menu" if self.sidebar_expanded else "")
        self.bottom_button.setText("     Settings" if self.sidebar_expanded else "")
        self.bottom_button.setStyleSheet(
            self.get_button_style(self.sidebar_expanded, selected=False)
        )
        self.toggle_button.setStyleSheet(
            self.get_button_style(self.sidebar_expanded, selected=False)
        )

        for btn, _, label in self.menu_buttons:
            btn.setText(f"     {label}" if self.sidebar_expanded else "")
            btn.setToolTip(label)
            is_selected = btn == self.selected_button
            btn.setStyleSheet(
                self.get_button_style(self.sidebar_expanded, selected=is_selected)
            )

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Video Files", "", "Video Files (*.mp4 *.avi *.mkv *.mov)")
        if files:
            self.select_menu(self.player_button)  # Navigate to Player tab
            self.vlc_player.play_file(files[0])  # Play the first selected file














if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = HomeScreen()
    window.show()
    app.installEventFilter(window)
    sys.exit(app.exec_())
