# VideoTracker

A fully custom Python TV show video player built from scratch with PyQt6. No VLC or external media player interfaces - pure custom code with QtMultimedia backend.

## Features
- **Automatic Episode Detection & Ordering**: Scans folders for video files, parses SxxExx or numbered episodes, sorts seasons/episodes intelligently.
- **Progress Saving**: Remembers playback position per episode across sessions. Auto-resumes where you left off.
- **Multiple Series Support**: Add multiple TV show folders. Switch via burger menu. Saves layout/config.
- **Custom Fullscreen HUD**: Video timeline with seek, play/pause, intro skip button (right-click to customize seconds). Auto-hides after 3s inactivity.
- **Volume Controls**: Pop-out panel with standard volume (0-100%) + additional booster (0-600%).
- **Intuitive Controls**:
  - Left/Right arrows: ±5 seconds
  - J/L: ±10 seconds
  - Space/K or click video: Play/Pause
  - Esc: Toggle fullscreen
- **Smart Playback**: Auto-plays next episode when one ends. Burger menu for series selection.
- **Modern Dark UI**: Clean, overlay HUD, responsive.

## Installation

```bash
pip install -r requirements.txt
python main.py
```

**Requirements**: Python 3.10+, PyQt6 (includes QtMultimedia for video playback). Works on Windows, macOS, Linux (may need GStreamer or platform codecs for some video formats).

## Usage
1. Run the app - starts in fullscreen.
2. Click the big button to add your first series folder (e.g., a folder containing `S01E01.mkv`, `S01E02.mkv`... or season subfolders).
3. The app auto-detects and orders episodes.
4. Use burger menu (☰ top left) to switch series, add more, or quit.
5. Enjoy with custom controls and persistent progress!

## Data Storage
- Config and progress saved to `~/.video_tracker/data.json`
- Safe, human-readable JSON.

## Notes
- Volume booster >100% is UI-supported; actual output caps at 100% due to Qt backend limits (use system volume mixer for extra loudness if needed).
- For best compatibility, use common formats like MP4/MKV with H.264/AAC.
- This is a complete, self-contained single-file app.

Built with ❤️ for TV binge-watchers who want a lightweight, custom tracker without bloated media center software.