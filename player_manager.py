import locale
import ctypes
import os

class PlaybackManager:
    def __init__(self, ui_callback=None):
        """Manages the underlying MPV player instance with asynchronous caching."""
        self.ui_callback = ui_callback
        self.player = None
        self.current_track = None
        
        # Local high-speed primitive caches to completely eliminate lock contention
        self.cached_position = 0.0
        self.cached_duration = 0.0
        self.cached_volume = 100
        self.cached_paused = False       # FIX: Thread-isolated pause memory register
        self.cached_idle = True          # FIX: Thread-isolated idle memory register

    def _ensure_mpv_initialized(self):
        """Lazy-loads and configures MPV only when playback is explicitly requested."""
        if self.player is not None:
            return

        try:
            import locale
            locale.setlocale(locale.LC_NUMERIC, "C")
        except Exception:
            pass

        import mpv
        
        # Force strict single-file unthrottled audio protocol parameters
        self.player = mpv.MPV(
            ytdl=True, 
            video=False,
            ytdl_format="bestaudio[ext=m4a]/140/bestaudio",
            cache="yes",                     
            cache_pause=True,                
            demuxer_max_bytes=104857600,     # 100MB buffer allocation
            demuxer_readahead_secs=60,       # 60-second read-ahead cache
            cache_secs=15                    
        )

        # FIX: Push-driven observer caches state without knocking on the C-engine's door
        @self.player.property_observer('idle-active')
        def observe_idle(name, is_idle):
            if is_idle is not None:
                self.cached_idle = bool(is_idle)
            if is_idle and self.ui_callback and self.current_track:
                self.ui_callback("track_finished")

        @self.player.property_observer('duration')
        def observe_duration(name, value):
            if value is not None:
                self.cached_duration = float(value)

        @self.player.property_observer('time-pos')
        def observe_time(name, value):
            if value is not None:
                self.cached_position = float(value)

        @self.player.property_observer('volume')
        def observe_volume(name, value):
            if value is not None:
                self.cached_volume = int(value)

        # FIX: Push-driven observer for pause state avoids cross-thread bottlenecks
        @self.player.property_observer('pause')
        def observe_pause(name, value):
            if value is not None:
                self.cached_paused = bool(value)

    def play(self, url: str, title: str = "Unknown Track", artist: str = "Unknown Artist"):
        """Plays a track URL and resets the timeline cache variables safely."""
        self._ensure_mpv_initialized()
        self.cached_position = 0.0
        self.cached_duration = 0.0
        self.cached_idle = False
        self.current_track = {"title": title, "artist": artist, "url": url}
        self.player.play(url)

    def toggle_pause(self) -> bool:
        """Toggles pause state safely using local state references."""
        if self.player:
            target_state = not self.cached_paused
            self.player.pause = target_state
            self.cached_paused = target_state
            return target_state
        return False

    def stop(self):
        """Stops playback entirely."""
        if self.player:
            self.player.stop()
            self.current_track = None
            self.cached_position = 0.0
            self.cached_duration = 0.0
            self.cached_idle = True

    def seek(self, seconds: int):
        """Seeks forward or backward using the safely cached time values."""
        if self.player and not self.cached_idle:
            try:
                new_pos = max(0, min(self.cached_duration, self.cached_position + seconds))
                self.player.time_pos = new_pos
                self.cached_position = new_pos
            except Exception:
                pass

    def set_volume(self, volume: int):
        """Sets volume level safely."""
        self._ensure_mpv_initialized()
        if self.player:
            target = max(0, min(130, volume))
            self.player.volume = target
            self.cached_volume = target

    @property
    def volume(self) -> int:
        """Returns current volume level straight from local cache thread memory."""
        return self.cached_volume

    @property
    def is_paused(self) -> bool:
        """Returns whether the player is currently paused using the local cache registry."""
        return self.cached_paused

    def get_progress(self) -> dict:
        """Returns time coordinates instantly from the local Python cache."""
        if not self.player or self.cached_idle:
            return {"position": 0, "duration": 0, "percentage": 0.0}

        percentage = (self.cached_position / self.cached_duration) if self.cached_duration > 0 else 0.0
        return {
            "position": self.cached_position,
            "duration": self.cached_duration,
            "percentage": percentage
        }

    def close(self):
        """Gracefully tears down the MPV engine on application exit."""
        if self.player:
            self.player.terminate()
            self.player = None
