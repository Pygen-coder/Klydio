import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedLayout, QSpacerItem, QSizePolicy,
    QLabel, QPushButton, QSlider, QComboBox, QCheckBox, QFileDialog, QFrame,
    QGroupBox,QGraphicsDropShadowEffect,QApplication,QToolButton,QGraphicsOpacityEffect
)
from PyQt5.QtGui import QIcon, QPixmap, QFont,QTransform,QColor
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve,pyqtProperty,QTimer,QEvent
import vlc


class VLCPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setStyleSheet("background-color: #1e1e1e;")
        self.instance = vlc.Instance('--no-video-title-show', '--no-spu')

        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()   

        self.mediaplayer = self.instance.media_player_new()

        self.fade_anim = None  # Keep reference to fade animation

        self.wrapper = QWidget(self)
        self.wrapper.setStyleSheet("background-color: transparent;")

        self.video_frame = QFrame(self.wrapper)
        self.video_frame.setStyleSheet("background-color: transparent;")
        self.video_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        placeholder_layout = QVBoxLayout(self.video_frame)
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.setAlignment(Qt.AlignCenter)

        self.placeholder_main = QLabel("Such emptiness 😢", self.video_frame)
        self.placeholder_main.setStyleSheet("color: #888; font-size: 32px; font-weight: bold;")
        self.placeholder_main.setAlignment(Qt.AlignCenter)

        self.placeholder_sub = QLabel("Play a video", self.video_frame)
        self.placeholder_sub.setStyleSheet("color: #666; font-size: 18px;")
        self.placeholder_sub.setAlignment(Qt.AlignCenter)

        placeholder_layout.addWidget(self.placeholder_main)
        placeholder_layout.addWidget(self.placeholder_sub)

        self.overlay = QWidget(self.wrapper)
        self.overlay.setFixedHeight(50)
        self.overlay.setAttribute(Qt.WA_StyledBackground, True)
        self.overlay.setStyleSheet("background-color: #2e2e2e; border-radius: 25px;")
        self.overlay.hide()

        overlay_layout = QHBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(15, 0, 15, 0)
        overlay_layout.setSpacing(10)

        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(QIcon("icons/pause.svg"))
        self.play_pause_btn.setIconSize(QSize(24, 24))
        self.play_pause_btn.setFixedSize(36, 36)
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setFlat(True)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        overlay_layout.addWidget(self.play_pause_btn)

        self.timestamp = QLabel("00:00 / 00:00")
        self.timestamp.setStyleSheet("color: #ccc; font-size: 14px;")
        self.timestamp.setFixedWidth(100)
        overlay_layout.addWidget(self.timestamp)

        self.progress_bar = QSlider(Qt.Horizontal)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.sliderMoved.connect(self.set_position)
        self.progress_bar.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #444;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00aaff;
                border: none;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #00aaff;
                border-radius: 3px;
            }
        """)
        overlay_layout.addWidget(self.progress_bar)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #444;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffaa00;
                border: none;
                width: 10px;
                margin: -4px 0;
                border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: #ffaa00;
                border-radius: 3px;
            }
        """)
        overlay_layout.addWidget(self.volume_slider)

        wrapper_layout = QVBoxLayout(self.wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(self.video_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.wrapper)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_progress)

        self.hide_timer = QTimer(self)
        self.hide_timer.setInterval(3000)
        self.hide_timer.timeout.connect(self.hide_controls)

        # Mouse tracking + event filter
        self.setMouseTracking(True)
        self.wrapper.setMouseTracking(True)
        self.video_frame.setMouseTracking(True)
        self.overlay.setMouseTracking(True)

        self.installEventFilter(self)
        self.wrapper.installEventFilter(self)
        self.video_frame.installEventFilter(self)
        self.overlay.installEventFilter(self)

        

    def play_file(self, filepath):
        if os.path.exists(filepath):
            media = self.instance.media_new(filepath)
            self.mediaplayer.set_media(media)
            self.mediaplayer.video_set_spu(-1)  # Disable subtitle rendering


            def start_playback():
                win_id = self.video_frame.winId()
                if sys.platform.startswith('linux'):
                    self.mediaplayer.set_xwindow(win_id)
                elif sys.platform == "win32":
                    self.mediaplayer.set_hwnd(win_id)
                elif sys.platform == "darwin":
                    self.mediaplayer.set_nsobject(int(win_id))

                self.placeholder_main.hide()
                self.placeholder_sub.hide()

                self.mediaplayer.play()
                self.timer.start()
                self.show_controls()

            QTimer.singleShot(100, start_playback)

    def toggle_play_pause(self):
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.play_pause_btn.setIcon(QIcon("icons/play.svg"))
        else:
            self.mediaplayer.play()
            self.play_pause_btn.setIcon(QIcon("icons/pause.svg"))
        self.show_controls()

    def set_position(self, position):
        if self.mediaplayer.get_length() > 0:
            self.mediaplayer.set_position(position / 1000.0)

    def update_progress(self):
        length = self.mediaplayer.get_length()
        if length > 0:
            pos = self.mediaplayer.get_position()
            self.progress_bar.setValue(int(pos * 1000))
            current = int(pos * length)
            self.timestamp.setText(f"{self._format_time(current)} / {self._format_time(length)}")

    def set_volume(self, value):
        self.mediaplayer.audio_set_volume(value)

    def _format_time(self, ms):
        seconds = ms // 1000
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def show_controls(self):
        self.update_overlay_position()

        if self.fade_anim:
            self.fade_anim.stop()

        if not self.overlay.isVisible():
            self.overlay.setVisible(True)

        self.overlay.raise_()

        effect = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(effect)

        self.fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self.fade_anim.setDuration(300)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        self.hide_timer.start()

    def hide_controls(self):
        self.hide_timer.stop()

        effect = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(effect)

        self.fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self.fade_anim.setDuration(300)
        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)

        def on_fade_done():
            self.overlay.setVisible(False)
            self.overlay.setGraphicsEffect(None)

        self.fade_anim.finished.connect(on_fade_done)
        self.fade_anim.start()

    def update_overlay_position(self):
        width = int(self.wrapper.width() * 0.75)
        self.overlay.resize(width, 50)
        x = (self.wrapper.width() - width) // 2
        y = self.wrapper.height() - 80
        self.overlay.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_overlay_position()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.toggle_play_pause()
        elif event.key() == Qt.Key_Right:
            self.skip_forward(5)
        elif event.key() == Qt.Key_Left:
            self.skip_backward(5)
        super().keyPressEvent(event)

    def skip_forward(self, seconds):
        pos = self.mediaplayer.get_time() + (seconds * 1000)
        self.mediaplayer.set_time(pos)

    def skip_backward(self, seconds):
        pos = max(0, self.mediaplayer.get_time() - (seconds * 1000))
        self.mediaplayer.set_time(pos)

    def eventFilter(self, source, event):
        if event.type() == QEvent.MouseMove:
            self.show_controls()
            self.hide_timer.start()
        return super().eventFilter(source, event)





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

        # Apply drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 150))  # Semi-transparent black
        self.setGraphicsEffect(shadow)

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

        # Add Player page with VLC widget
        self.vlc_player = VLCPlayer()
        self.pages.addWidget(self.vlc_player)
        self.page_widgets["Player"] = self.vlc_player


        # Finally add to pages
        self.pages.addWidget(home_page_container)
        self.page_widgets["Home"] = home_page_container



        # Placeholder pages for others
        for _, _, label in self.menu_buttons:
            if label == "Player":
                self.vlc_player = VLCPlayer()
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
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F:
            if not hasattr(self, 'is_fullscreen'):
                self.is_fullscreen = False

            if not self.is_fullscreen:
                # Maximize window if not already maximized
                if not self.isMaximized():
                    self.showMaximized()

                # Hide sidebar and topbar
                self.top_bar.hide()
                self.sidebar_frame.hide()

                # Expand the player
                self.pages.setContentsMargins(0, 0, 0, 0)
                self.vlc_player.wrapper.layout().setContentsMargins(0, 0, 0, 0)
                self.is_fullscreen = True
            else:
                # Restore sidebar and topbar
                self.top_bar.show()
                self.sidebar_frame.show()

                # Restore margins
                self.pages.setContentsMargins(0, 0, 0, 0)
                self.vlc_player.wrapper.layout().setContentsMargins(0, 0, 0, 0)

                self.is_fullscreen = False

        elif event.key() == Qt.Key_Escape:
            if hasattr(self, 'is_fullscreen') and self.is_fullscreen:
                # Restore everything if Esc pressed
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
    sys.exit(app.exec_())
