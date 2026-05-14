import sys
import os
import json
import re
import pathlib
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QSlider, QToolButton, QMenu, QFrame, QStackedWidget, QFileDialog, QInputDialog,
    QSizePolicy, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QEvent, QPoint

from PyQt6.QtGui import QFont, QPalette, QColor

from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaPlayer

from PyQt6.QtMultimediaWidgets import QVideoWidget


class VideoTracker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Tracker")
        self.setGeometry(100, 100, 1280, 720)
        self.setStyleSheet(self.get_dark_stylesheet())

        # Data
        self.data_dir = pathlib.Path.home() / ".video_tracker"
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "data.json"
        self.load_data()

        # Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)

        # State
        self.series_list = self.data.get("series", [])
        self.progress = self.data.get("progress", {})
        self.settings = self.data.get("settings", {"volume": 80, "booster": 100})
        self.current_series = None
        self.current_series_name = None
        self.episodes = []
        self.current_episode_index = 0
        self.current_episode_path = None
        self.user_seeking = False
        self.is_fullscreen = False

        # Timers
        self.activity_timer = QTimer(self)
        self.activity_timer.setSingleShot(True)
        self.activity_timer.timeout.connect(self.hide_hud)

        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save_progress)
        self.save_timer.start(10000)

        # UI Setup
        self.stacked = QStackedWidget()
        self.setCentralWidget(self.stacked)

        self.setup_home_page()
        self.setup_player_page()

        # Connect player signals
        self.player.positionChanged.connect(self.update_timeline)
        self.player.durationChanged.connect(self.update_duration)
        self.player.playbackStateChanged.connect(self.update_play_button)
        self.player.mediaStatusChanged.connect(self.on_media_status)

        # Event filter for video clicks
        self.video_widget.installEventFilter(self)

        # Initial state
        if self.series_list:
            last_name = self.data.get("last_series")
            if last_name and any(s["name"] == last_name for s in self.series_list):
                self.switch_series(last_name)
            else:
                self.switch_series(self.series_list[0]["name"])
        else:
            self.stacked.setCurrentIndex(0)

        self.showFullScreen()
        self.is_fullscreen = True

    def get_dark_stylesheet(self):
        return """
            QMainWindow { background-color: #0d0d0d; color: #ffffff; }
            QWidget { background-color: #0d0d0d; color: #ffffff; }
            QLabel { color: #ffffff; }
            QPushButton { 
                background-color: #1a1a1a; 
                color: #ffffff; 
                border: 1px solid #333;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #2a2a2a; }
            QPushButton:pressed { background-color: #3a3a3a; }
            QSlider::groove:horizontal { 
                background: #333; 
                height: 6px; 
                border-radius: 3px;
            }
            QSlider::handle:horizontal { 
                background: #00b4d8;
                width: 16px; 
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QToolButton { 
                background: transparent;
                color: #ffffff;
                font-size: 28px;
                border: none;
            }
            QToolButton:hover { color: #00b4d8; }
            QMenu { background-color: #1a1a1a; color: #fff; border: 1px solid #333; }
            QMenu::item:selected { background-color: #00b4d8; color: #000; }
        """

    def load_data(self):
        if self.data_file.exists():
            with open(self.data_file, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {"series": [], "progress": {}, "settings": {"volume": 80, "booster": 100}, "last_series": None}

    def save_data(self):
        self.data["series"] = self.series_list
        self.data["progress"] = self.progress
        self.data["settings"] = self.settings
        if self.current_series_name:
            self.data["last_series"] = self.current_series_name
        with open(self.data_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def setup_home_page(self):
        self.home_page = QWidget()
        layout = QVBoxLayout(self.home_page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(30)

        title = QLabel("🎥 Video Tracker")
        title.setFont(QFont("Arial", 52, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("Custom TV Show Player • Progress Saved • No Bloat")
        sub.setFont(QFont("Arial", 16))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        self.add_btn = QPushButton("📁 Add Series Folder & Start Watching")
        self.add_btn.setMinimumSize(380, 70)
        self.add_btn.setFont(QFont("Arial", 18))
        self.add_btn.clicked.connect(self.add_first_series)
        layout.addWidget(self.add_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("Supports MP4, MKV, AVI • Auto-detects episodes • Burger menu for series")
        hint.setFont(QFont("Arial", 12))
        hint.setStyleSheet("color: #888;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.stacked.addWidget(self.home_page)

    def setup_player_page(self):
        self.player_page = QWidget()
        self.player_layout = QVBoxLayout(self.player_page)
        self.player_layout.setContentsMargins(0, 0, 0, 0)
        self.player_layout.setSpacing(0)

        # Top bar
        self.top_bar = QWidget()
        self.top_bar.setFixedHeight(50)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(15, 5, 15, 5)

        self.burger_btn = QToolButton()
        self.burger_btn.setText("☰")
        self.burger_btn.setFixedSize(50, 40)
        self.burger_btn.clicked.connect(self.show_burger_menu)
        top_layout.addWidget(self.burger_btn)

        self.series_label = QLabel("No Series Selected")
        self.series_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        top_layout.addWidget(self.series_label, 1)

        # Optional full screen toggle button
        fs_btn = QPushButton("⛶")
        fs_btn.setFixedSize(40, 40)
        fs_btn.clicked.connect(self.toggle_fullscreen)
        top_layout.addWidget(fs_btn)

        self.player_layout.addWidget(self.top_bar)

        # Video container (for overlay HUD)
        self.video_container = QFrame()
        self.video_container.setLayout(QVBoxLayout())
        self.video_container.layout().setContentsMargins(0, 0, 0, 0)
        self.video_container.layout().addWidget(self.video_widget, 1)
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.player_layout.addWidget(self.video_container, 1)

        # HUD (child of video_container for overlay)
        self.hud = QWidget(self.video_container)
        self.hud.setStyleSheet("background-color: rgba(20, 20, 20, 220); border-radius: 10px;")
        self.hud_layout = QHBoxLayout(self.hud)
        self.hud_layout.setContentsMargins(15, 8, 15, 8)
        self.hud_layout.setSpacing(12)

        # Time labels
        self.current_time = QLabel("00:00")
        self.current_time.setFont(QFont("Arial", 11))
        self.hud_layout.addWidget(self.current_time)

        # Timeline slider
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setMinimumHeight(24)
        self.timeline.sliderMoved.connect(self.seek_to_position)
        self.timeline.sliderPressed.connect(lambda: setattr(self, "user_seeking", True))
        self.timeline.sliderReleased.connect(lambda: setattr(self, "user_seeking", False))
        self.hud_layout.addWidget(self.timeline, 3)

        self.total_time = QLabel("00:00")
        self.total_time.setFont(QFont("Arial", 11))
        self.hud_layout.addWidget(self.total_time)

        # Play/Pause
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(50, 40)
        self.play_btn.clicked.connect(self.toggle_play)
        self.hud_layout.addWidget(self.play_btn)

        # Skip Intro
        self.skip_btn = QPushButton("Skip Intro (30s)")
        self.skip_btn.setFixedWidth(140)
        self.skip_btn.clicked.connect(self.skip_intro)
        self.skip_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.skip_btn.customContextMenuRequested.connect(self.set_intro_skip)
        self.hud_layout.addWidget(self.skip_btn)

        # Next Episode
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setFixedWidth(80)
        self.next_btn.clicked.connect(self.play_next_episode)
        self.hud_layout.addWidget(self.next_btn)

        # Volume button (opens popout)
        self.vol_btn = QPushButton("🔊")
        self.vol_btn.setFixedSize(50, 40)
        self.vol_btn.clicked.connect(self.toggle_volume_popup)
        self.hud_layout.addWidget(self.vol_btn)

        self.player_layout.addWidget(self.hud)  # temporary bottom; will overlay in resize

        self.stacked.addWidget(self.player_page)

        # Initial HUD position
        QTimer.singleShot(100, self.reposition_hud)

    def reposition_hud(self):
        if hasattr(self, "hud") and self.hud.isVisible():
            w = self.video_container.width() - 40
            h = 70
            x = 20
            y = self.video_container.height() - h - 25
            self.hud.setGeometry(x, y, w, h)
            self.hud.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.stacked.currentIndex() == 1:
            self.reposition_hud()

    def show_hud(self):
        if hasattr(self, "hud"):
            self.hud.show()
            self.reposition_hud()
            self.activity_timer.start(3000)

    def hide_hud(self):
        if hasattr(self, "hud") and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.hud.hide()

    def mouseMoveEvent(self, event):
        self.show_hud()
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.video_widget and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self.toggle_play()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_fullscreen()
        elif event.key() in (Qt.Key.Key_Space, Qt.Key.Key_K):
            self.toggle_play()
        elif event.key() == Qt.Key.Key_Left:
            self.seek_relative(-5000)
        elif event.key() == Qt.Key.Key_Right:
            self.seek_relative(5000)
        elif event.key() == Qt.Key.Key_J:
            self.seek_relative(-10000)
        elif event.key() == Qt.Key.Key_L:
            self.seek_relative(10000)
        else:
            super().keyPressEvent(event)

    def seek_relative(self, ms):
        if self.player.duration() > 0:
            new_pos = max(0, min(self.player.position() + ms, self.player.duration()))
            self.player.setPosition(new_pos)

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            self.is_fullscreen = True

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.show_hud()
        else:
            self.player.play()

    def update_play_button(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸")
        else:
            self.play_btn.setText("▶")

    def update_timeline(self, position):
        if not self.user_seeking and self.timeline.maximum() > 0:
            self.timeline.setValue(position)
        self.current_time.setText(self.format_time(position))
        # Auto save rough position
        if position % 5000 < 100:  # every ~5s
            self.save_progress()

    def update_duration(self, duration):
        self.timeline.setRange(0, duration)
        self.total_time.setText(self.format_time(duration))

    def seek_to_position(self, position):
        self.player.setPosition(position)

    def format_time(self, ms):
        if ms < 0:
            ms = 0
        s = int(ms / 1000)
        h = s // 3600
        m = (s % 3600) // 60
        s = s % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.save_progress()
            QTimer.singleShot(200, self.play_next_episode)

    def play_next_episode(self):
        if self.current_episode_index + 1 < len(self.episodes):
            self.current_episode_index += 1
            self.load_episode(self.current_episode_index)
            if self.current_series:
                self.current_series["last_played_episode"] = self.episodes[self.current_episode_index]
                self.save_data()
        else:
            self.player.stop()
            self.show_hud()
            # Optional: QMessageBox.information(self, "Series Complete", "You've finished this series!")

    def load_episode(self, index):
        if not self.episodes or index >= len(self.episodes):
            return
        path = self.episodes[index]
        self.current_episode_path = path
        self.current_episode_index = index
        self.player.setSource(QUrl.fromLocalFile(path))

        # Resume position
        pos_data = self.progress.get(path, {})
        resume_pos = pos_data.get("position", 0)
        if resume_pos > 5:
            QTimer.singleShot(150, lambda: self.player.setPosition(int(resume_pos * 1000)))

        self.player.play()
        self.series_label.setText(f"{self.current_series_name} • E{index+1}/{len(self.episodes)}")
        self.skip_btn.setText(f"Skip Intro ({self.get_intro_skip()}s)")
        self.show_hud()

    def skip_intro(self):
        if self.player.duration() > 0:
            skip_ms = self.get_intro_skip() * 1000
            new_pos = min(self.player.position() + skip_ms, self.player.duration() - 1000)
            self.player.setPosition(new_pos)

    def set_intro_skip(self):
        current = self.get_intro_skip()
        new_val, ok = QInputDialog.getInt(
            self, "Set Intro Skip", "Seconds:", current, 0, 600, 1
        )
        if ok and self.current_series:
            self.current_series["intro_skip"] = new_val
            self.skip_btn.setText(f"Skip Intro ({new_val}s)")
            self.save_data()

    def get_intro_skip(self):
        if self.current_series:
            return self.current_series.get("intro_skip", 30)
        return 30

    def toggle_volume_popup(self):
        if not hasattr(self, "volume_popup") or not self.volume_popup.isVisible():
            self.volume_popup = QWidget(self, Qt.WindowType.Popup)
            self.volume_popup.setStyleSheet("background-color: #1a1a1a; border: 2px solid #00b4d8; border-radius: 10px;")
            popup_layout = QVBoxLayout(self.volume_popup)
            popup_layout.setContentsMargins(15, 12, 15, 12)

            # Volume
            vol_label = QLabel("Volume")
            popup_layout.addWidget(vol_label)
            self.vol_slider = QSlider(Qt.Orientation.Horizontal)
            self.vol_slider.setRange(0, 100)
            self.vol_slider.setValue(self.settings.get("volume", 80))
            self.vol_slider.valueChanged.connect(self.update_volume)
            popup_layout.addWidget(self.vol_slider)

            # Booster
            boost_label = QLabel("Booster (0-600%)")
            popup_layout.addWidget(boost_label)
            self.boost_slider = QSlider(Qt.Orientation.Horizontal)
            self.boost_slider.setRange(0, 600)
            self.boost_slider.setSingleStep(10)
            self.boost_slider.setValue(self.settings.get("booster", 100))
            self.boost_slider.valueChanged.connect(self.update_volume)
            popup_layout.addWidget(self.boost_slider)

            # Close hint
            hint = QLabel("Click outside to close")
            hint.setStyleSheet("color: #888; font-size: 10px;")
            popup_layout.addWidget(hint)

            self.volume_popup.resize(280, 160)
            # Position near volume button
            btn_pos = self.vol_btn.mapToGlobal(QPoint(0, 0))
            self.volume_popup.move(btn_pos.x() - 200, btn_pos.y() - 180)
            self.volume_popup.show()
            self.update_volume()  # apply current
        else:
            self.volume_popup.close()

    def update_volume(self):
        if not hasattr(self, "vol_slider") or not hasattr(self, "boost_slider"):
            return
        vol = self.vol_slider.value() / 100.0
        boost = self.boost_slider.value() / 100.0
        effective = min(1.0, vol * boost)
        self.audio_output.setVolume(effective)
        self.settings["volume"] = self.vol_slider.value()
        self.settings["booster"] = self.boost_slider.value()
        self.save_data()

    def show_burger_menu(self):
        menu = QMenu(self)
        series_sub = menu.addMenu("📺 Switch Series")
        for s in self.series_list:
            act = series_sub.addAction(s["name"])
            act.triggered.connect(lambda checked=False, n=s["name"]: self.switch_series(n))

        menu.addSeparator()
        menu.addAction("➕ Add Series Folder", self.add_series)
        if self.current_series:
            menu.addAction("🗑 Remove Current Series", self.remove_current_series)
        menu.addSeparator()
        menu.addAction("⚙ Settings (coming soon)", lambda: None)
        menu.addAction("❌ Quit", self.close)

        pos = self.burger_btn.mapToGlobal(self.burger_btn.rect().bottomLeft())
        menu.exec(pos)

    def add_series(self):
        folder = QFileDialog.getExistingDirectory(self, "Select TV Series Folder")
        if not folder:
            return
        name = os.path.basename(folder.rstrip(os.sep))
        if any(s.get("path") == folder for s in self.series_list):
            return
        new_s = {
            "name": name,
            "path": folder,
            "intro_skip": 30,
            "last_played_episode": None
        }
        self.series_list.append(new_s)
        self.save_data()
        self.switch_series(name)

    def add_first_series(self):
        self.add_series()

    def remove_current_series(self):
        if not self.current_series:
            return
        self.series_list = [s for s in self.series_list if s["name"] != self.current_series_name]
        self.save_data()
        if self.series_list:
            self.switch_series(self.series_list[0]["name"])
        else:
            self.stacked.setCurrentIndex(0)
            self.current_series = None
            self.current_series_name = None

    def switch_series(self, name):
        self.current_series = next((s for s in self.series_list if s["name"] == name), None)
        if not self.current_series:
            return
        self.current_series_name = name
        self.series_label.setText(name)

        # Scan episodes
        self.episodes = self.scan_series(self.current_series["path"])
        if not self.episodes:
            return

        # Find last played or first
        last = self.current_series.get("last_played_episode")
        if last and last in self.episodes:
            self.current_episode_index = self.episodes.index(last)
        else:
            self.current_episode_index = 0

        self.stacked.setCurrentIndex(1)
        self.load_episode(self.current_episode_index)
        self.reposition_hud()
        self.show_hud()

    def scan_series(self, path):
        episodes = []
        valid_ext = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv")
        for root, dirs, files in os.walk(path):
            for f in sorted(files):
                if f.lower().endswith(valid_ext):
                    full_path = os.path.join(root, f)
                    episodes.append(full_path)

        def parse_key(fpath):
            name = os.path.basename(fpath).lower()
            match = re.search(r"[sS](\d+)[eE](\d+)", name)
            if match:
                return (int(match.group(1)), int(match.group(2)), name)
            nums = re.findall(r"\d+", name)
            if nums:
                return (0, int(nums[-1]), name)
            return (999, 999, name)

        episodes.sort(key=parse_key)
        return episodes

    def save_progress(self):
        if self.current_episode_path and self.player.duration() > 0:
            pos_sec = self.player.position() / 1000.0
            if self.current_episode_path not in self.progress:
                self.progress[self.current_episode_path] = {}
            self.progress[self.current_episode_path]["position"] = round(pos_sec, 1)
            # Mark watched if near end
            if pos_sec > (self.player.duration() / 1000.0) * 0.85:
                self.progress[self.current_episode_path]["watched"] = True
            self.save_data()

    def closeEvent(self, event):
        self.save_progress()
        self.save_data()
        self.player.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoTracker()
    sys.exit(app.exec())
