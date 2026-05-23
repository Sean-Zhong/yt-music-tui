import locale
import ctypes
import os

class PlaybackManager:
    def __init__(self, ui_callback=None):
        """
        Manages the underlying MPV player instance.
        :param ui_callback: A thread-safe function to pass events back to the Textual UI.
        """
        self.ui_callback = ui_callback
        self.player = None
        self.current_track = None

    def _ensure_mpv_initialized(self):
        """Lazy-loads and configures MPV only when playback is explicitly requested."""
        if self.player is not None:
            return

        # 1. Permanently solve the locale segmentation fault bug here
        try:
            import locale
            locale.setlocale(locale.LC_NUMERIC, "C")
        except Exception:
            try:
                libc = ctypes.CDLL(None)
                libc.setlocale(1, b"C")
            except Exception:
                pass

        # 2. Lazy import of mpv to prevent early initialization crashes
        import mpv
        
        # 3. Spin up MPV with video disabled and yt-dlp streaming enabled
        self.player = mpv.MPV(ytdl=True, video=False)

        # 4. Attach a property observer to monitor when a song finishes playing
        @self.player.property_observer('idle-active')
        def observe_idle(name, is_idle):
            # 'idle-active' is True when MPV stops playing or has no file loaded
            if is_idle and self.ui_callback and self.current_track:
                # Fire the callback to let the TUI know it's time for the next song
                self.ui_callback("track_finished")

    def play(self, url: str, title: str = "Unknown Track", artist: str = "Unknown Artist"):
        """Plays a track URL and tracks the active metadata."""
        self._ensure_mpv_initialized()
        self.current_track = {"title": title, "artist": artist, "url": url}
        self.player.play(url)

    def toggle_pause(self) -> bool:
        """Toggles pause state. Returns True if paused, False if playing."""
        if self.player:
            self.player.pause = not self.player.pause
            return self.player.pause
        return False

    def stop(self):
        """Stops playback entirely."""
        if self.player:
            self.player.stop()
            self.current_track = None

    def set_volume(self, volume: int):
        """Sets volume level (0-130)."""
        if self.player:
            # Clamp volume between 0 and 130
            self.player.volume = max(0, min(130, volume))

    @property
    def volume(self) -> int:
        """Returns current volume level."""
        return int(self.player.volume) if self.player else 100

    @property
    def is_paused(self) -> bool:
        """Returns whether the player is currently paused."""
        return self.player.pause if self.player else False

    def get_progress(self) -> dict:
        """Returns time elapsed, total duration, and a float percentage (0.0 to 1.0)."""
        if not self.player or self.player.idle_active:
            return {"position": 0, "duration": 0, "percentage": 0.0}

        # MPV properties might return None momentarily while loading a stream
        position = self.player.time_pos or 0
        duration = self.player.duration or 0
        percentage = (position / duration) if duration > 0 else 0.0

        return {
            "position": position,
            "duration": duration,
            "percentage": percentage
        }

    def close(self):
        """Gracefully tears down the MPV engine on application exit."""
        if self.player:
            self.player.terminate()
            self.player = None
