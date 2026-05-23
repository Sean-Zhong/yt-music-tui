import locale
# Keep the C locale locked down before any library initializations happen
locale.setlocale(locale.LC_NUMERIC, "C")

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, ListView, ListItem, Label, DataTable
from textual.binding import Binding

from ytmusicapi import YTMusic
from player_manager import PlaybackManager


class PlaybackBar(Label):
    """A custom interactive timeline widget that handles mouse-click scrubbing."""
    
    def on_click(self, event: events.Click) -> None:
        """Fires automatically when a user clicks anywhere inside this bar layout."""
        if not hasattr(self.app, "player") or self.app.player.player is None:
            return
            
        duration = self.app.player.cached_duration
        if duration <= 0:
            return
            
        width = self.size.width
        if width > 1:
            percentage = max(0.0, min(1.0, event.x / (width - 1)))
            target_time = percentage * duration
            
            try:
                self.app.player.player.time_pos = target_time
                self.app.player.cached_position = target_time
                self.app.update_progress_bar()
            except Exception:
                pass


class VolumeBar(Label):
    """A custom interactive vertical slider widget that handles mouse-click volume adjustment."""
    
    def on_click(self, event: events.Click) -> None:
        """Fires automatically when a user clicks anywhere inside the vertical volume bar."""
        if not hasattr(self.app, "player") or self.app.player.player is None:
            return
            
        height = self.size.height
        if height > 1:
            percentage = 1.0 - (event.y / (height - 1))
            percentage = max(0.0, min(1.0, percentage))
            target_volume = int(percentage * 100)
            
            self.app.player.set_volume(target_volume)
            self.app.update_progress_bar()


# ────────────── INTERCEPTING SUBCLASSES ──────────────

class VolumeListView(ListView):
    """A ListView that intercepts arrow keys for volume before they move the cursor."""
    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            self.app.action_volume_up()
            event.stop()
        elif event.key == "down":
            self.app.action_volume_down()
            event.stop()


class VolumeDataTable(DataTable):
    """A DataTable that intercepts arrow keys for volume before they move the cursor."""
    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            self.app.action_volume_up()
            event.stop()
        elif event.key == "down":
            self.app.action_volume_down()
            event.stop()


class YTMusicTUI(App):
    """A YouTube Music Terminal User Interface with complete control metrics."""
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("space", "toggle_playback", "Play/Pause", show=True),
        Binding("left", "seek_backward", "Seek -10s", show=True),
        Binding("right", "seek_forward", "Seek +10s", show=True),
        Binding("up", "volume_up", "Vol +5%", show=True),
        Binding("down", "volume_down", "Vol -5%", show=True),
        Binding("h", "nav_left", "Sidebar [H]", show=True),
        Binding("j", "nav_down", "Down [J]", show=True),
        Binding("k", "nav_up", "Up [K]", show=True),
        Binding("l", "nav_right", "Tracks [L]", show=True),
    ]

    CSS = """
    Screen {
        background: #121212;
    }
    #app-body {
        height: 1fr;
    }
    #sidebar {
        width: 35;
        background: #1e1e1e;
        border-right: solid #333333;
    }
    .sidebar-title {
        padding: 1 2;
        background: #262626;
        color: #ff0055;
        text-style: bold;
    }
    #main-content {
        width: 1fr;
        padding: 1 2;
    }
    #player-bar {
        height: 10;
        background: #1a1a1a;
        border-top: solid #ff0055;
        padding: 1 2;
        layout: horizontal;
    }
    #player-controls-right {
        width: 1fr;
        height: 1fr;
        layout: vertical;
    }
    #player-controls-text {
        height: 1fr;
    }
    #track-info {
        color: #ffffff;
        text-style: bold;
    }
    #player-status {
        color: #888888;
    }
    #shortcuts-legend {
        color: #555555;
        text-style: italic;
    }
    PlaybackBar {
        color: #ff0055;
        width: 1fr;
        height: 1;
    }
    VolumeBar {
        margin-right: 3;
        width: 2;
        height: 1fr;
    }
    """

    def on_mount(self) -> None:
        """Called when the app starts up and components are mounted."""
        self.ytmusic = YTMusic("browser.json")
        self.player = PlaybackManager(ui_callback=self.handle_player_event)
        
        table = self.query_one("#tracks-table", VolumeDataTable)
        table.add_columns("Title", "Artist", "Album")
        table.cursor_type = "row"
        
        self.run_worker(self.fetch_user_playlists())
        self.set_interval(0.5, self.update_progress_bar)

        self.query_one("#menu-list", VolumeListView).focus()

    def compose(self) -> ComposeResult:
        """Defines the structural blueprint of the TUI layout."""
        yield Header(show_clock=True)
        
        with Horizontal(id="app-body"):
            with Vertical(id="sidebar"):
                yield Label("📁 MY PLAYLISTS", classes="sidebar-title")
                yield VolumeListView(id="menu-list")
            
            with Container(id="main-content"):
                yield Label("Tracks", id="content-title", classes="sidebar-title")
                yield VolumeDataTable(id="tracks-table")
        
        with Horizontal(id="player-bar"):
            yield VolumeBar("", id="volume-bar-display")
            
            with Vertical(id="player-controls-right"):
                with Vertical(id="player-controls-text"):
                    yield Label("⏹ Not Playing", id="track-info")
                    yield Label("Status: Stopped | Volume: 100% | [00:00 / 00:00]", id="player-status")
                    yield Label("⌨ Controls: [←/→] Seek Track  │  [↑/↓] Volume Level", id="shortcuts-legend")
                
                yield PlaybackBar("", id="progress-bar-display")
            
        yield Footer()

    # ────────────── VIM NAVIGATION ACTIONS ──────────────

    def action_nav_left(self) -> None:
        """Shifts UI focus leftward to the Playlists Sidebar component."""
        self.query_one("#menu-list", VolumeListView).focus()

    def action_nav_right(self) -> None:
        """Shifts UI focus rightward to the Tracks Main Grid component."""
        self.query_one("#tracks-table", VolumeDataTable).focus()

    def action_nav_down(self) -> None:
        """Scrolls down inside whichever list or table component is currently active."""
        focused = self.focused
        if isinstance(focused, VolumeListView):
            focused.action_cursor_down()
        elif isinstance(focused, VolumeDataTable):
            focused.action_cursor_down()

    def action_nav_up(self) -> None:
        """Scrolls up inside whichever list or table component is currently active."""
        focused = self.focused
        if isinstance(focused, VolumeListView):
            focused.action_cursor_up()
        elif isinstance(focused, VolumeDataTable):
            focused.action_cursor_up()

    # ────────────── TIMELINE & VOLUME UPDATE CLOCK ──────────────

    def update_progress_bar(self) -> None:
        """Polls the MPV background context and updates timeline & volume assets."""
        if not hasattr(self, "player") or self.player.player is None:
            return

        progress = self.player.get_progress()
        position = progress["position"]
        duration = progress["duration"]
        current_volume = self.player.volume

        # 1. Timeline Horizontal String Formatting
        timeline_widget = self.query_one("#progress-bar-display", PlaybackBar)
        t_width = timeline_widget.size.width if timeline_widget.size.width > 0 else 60

        if duration > 0:
            if duration >= 3600:
                pos_hours, pos_rem = divmod(int(position), 3600)
                pos_min, pos_sec = divmod(pos_rem, 60)
                dur_hours, dur_rem = divmod(int(duration), 3600)
                dur_min, dur_sec = divmod(dur_rem, 60)
                timestamp_str = f"[{pos_hours:02d}:{pos_min:02d}:{pos_sec:02d} / {dur_hours:02d}:{dur_min:02d}:{dur_sec:02d}]"
            else:
                pos_min, pos_sec = divmod(int(position), 60)
                dur_min, dur_sec = divmod(int(duration), 60)
                timestamp_str = f"[{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}]"
            
            filled_length = int(round(t_width * position / float(duration)))
            filled_length = max(0, min(t_width, filled_length))
            visual_timeline = "█" * filled_length + "░" * (t_width - filled_length)
            
            state = "Paused" if self.player.is_paused else "Playing"
            self.query_one("#player-status", Label).update(
                f"Status: {state} | Volume: {current_volume}% | {timestamp_str}"
            )
            timeline_widget.update(visual_timeline)
        else:
            timeline_widget.update("░" * t_width)

        # 2. FIX: Color-Markup Driven Volume Engine Layout (Eliminates Artifact Gaps)
        vol_widget = self.query_one("#volume-bar-display", VolumeBar)
        v_height = vol_widget.size.height if vol_widget.size.height > 0 else 6
        
        vol_percentage = max(0, min(100, current_volume))
        
        # Determine exactly how many structural row slots are colored vs uncolored
        filled_lines = int(round((vol_percentage / 100.0) * v_height))
        filled_lines = max(0, min(v_height, filled_lines))
        empty_lines = v_height - filled_lines
        
        # Stack blocks down from the ceiling to the floor
        vol_lines = []
        for _ in range(empty_lines):
            vol_lines.append("[#2d2d2d]██[/]") # Premium uniform dark grey unselected slot
        for _ in range(filled_lines):
            vol_lines.append("[#00ffcc]██[/]") # Seamless bright neon cyan filled slot
                
        visual_volume = "\n".join(vol_lines)
        vol_widget.update(visual_volume)

    # ────────────── ASYNC LOADING WORKERS ──────────────

    async def fetch_user_playlists(self) -> None:
        """Background worker to fetch real account playlists cleanly."""
        try:
            playlists = self.ytmusic.get_library_playlists()
            self.populate_sidebar(playlists)
        except Exception as e:
            self.query_one("#content-title", Label).update(f"Error loading library: {e}")

    def populate_sidebar(self, playlists: list) -> None:
        """Populates the ListView component with real playlist entities."""
        menu_list = self.query_one("#menu-list", VolumeListView)
        menu_list.clear()
        
        if not playlists:
            menu_list.append(ListItem(Label("❌ No playlists found")))
            return

        for pl in playlists:
            title = pl.get('title', 'Untitled')
            item = ListItem(Label(f"🎵 {title}"))
            item.playlist_id = pl.get('playlistId')
            item.playlist_name = title
            menu_list.append(item)

    # ────────────── INTERACTION HANDLERS ──────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Fires automatically whenever you select a playlist in the sidebar."""
        playlist_id = getattr(event.item, "playlist_id", None)
        playlist_name = getattr(event.item, "playlist_name", "Unknown Playlist")
        
        if playlist_id:
            self.query_one("#content-title", Label).update(f"Loading {playlist_name}...")
            self.run_worker(self.load_playlist_tracks(playlist_id))

    async def load_playlist_tracks(self, playlist_id: str) -> None:
        """Background worker that pulls down tracks belonging to a playlist."""
        try:
            playlist_details = self.ytmusic.get_playlist(playlist_id)
            tracks = playlist_details.get('tracks', [])
            self.populate_track_table(tracks)
        except Exception as e:
            self.query_one("#content-title", Label).update(f"Error getting tracks: {e}")

    def populate_track_table(self, tracks: list) -> None:
        """Clears the table layout and safely draws the new track objects."""
        table = self.query_one("#tracks-table", VolumeDataTable)
        table.clear()
        
        self.row_to_video_id = {}
        self.query_one("#content-title", Label).update(f"Tracks ({len(tracks)} loaded)")

        for track in tracks:
            title = track.get('title', 'Unknown Title')
            album = track.get('album', {}).get('name', 'Unknown Album') if track.get('album') else 'N/A'
            artists_list = track.get('artists', [])
            artist = artists_list[0].get('name', 'Unknown Artist') if artists_list else 'Unknown'
            
            video_id = track.get('videoId')
            row_key = table.add_row(title, artist, album)
            
            if video_id:
                self.row_to_video_id[row_key] = video_id

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Fires automatically when you select a song row and hit Enter."""
        video_id = getattr(self, "row_to_video_id", {}).get(event.row_key)
        if not video_id:
            self.query_one("#track-info", Label).update("❌ Exact track ID missing.")
            return
            
        table = self.query_one("#tracks-table", VolumeDataTable)
        row_data = table.get_row(event.row_key)
        title, artist, album = row_data
            
        self.query_one("#track-info", Label).update(f"⏳ Fetching stream: {title}...")
        self.query_one("#player-status", Label).update("Status: Loading...")
        
        self.run_worker(self.play_track_worker(video_id, title, artist))

    async def play_track_worker(self, video_id: str, title: str, artist: str) -> None:
        """Bypasses web search entirely and boots up the active audio layer stream."""
        track_url = f"https://music.youtube.com/watch?v={video_id}"
        
        self.query_one("#track-info", Label).update(f"▶ Now Playing: {title} by {artist}")
        self.query_one("#player-status", Label).update(f"Status: Playing | Volume: {self.player.volume}%")
        
        self.player.play(track_url, title, artist)

    def handle_player_event(self, event_name: str) -> None:
        """Thread-safe callback triggered by background MPV events."""
        if event_name == "track_finished":
            self.call_from_thread(self.action_next_track)

    # ────────────── TIME & AUDIO ADJUSTMENT BUTTONS ──────────────

    def action_volume_up(self) -> None:
        """Fires when pressing the Up Arrow key. Boosts volume by 5%."""
        if hasattr(self, "player"):
            self.player.set_volume(self.player.volume + 5)
            self.update_progress_bar()

    def action_volume_down(self) -> None:
        """Fires when pressing the Down Arrow key. Lowers volume by 5%."""
        if hasattr(self, "player"):
            self.player.set_volume(self.player.volume - 5)
            self.update_progress_bar()

    def action_seek_forward(self) -> None:
        """Fires when pressing the Right Arrow key."""
        self.player.seek(10)
        self.update_progress_bar()

    def action_seek_backward(self) -> None:
        """Fires when pressing the Left Arrow key."""
        self.player.seek(-10)
        self.update_progress_bar()

    def action_toggle_playback(self) -> None:
        """Global action bound to 'Spacebar' key."""
        is_paused = self.player.toggle_pause()
        status_label = self.query_one("#player-status", Label)
        state = "Paused" if is_paused else "Playing"
        status_label.update(f"Status: {state} | Volume: {self.player.volume}%")

    def action_next_track(self) -> None:
        """Placeholder for advancing the playlist queue."""
        pass

    def on_unmount(self) -> None:
        """Safely cleans up the MPV core when closing down."""
        if hasattr(self, "player") and self.player is not None:
            self.player.close()

if __name__ == "__main__":
    app = YTMusicTUI()
    app.run()
