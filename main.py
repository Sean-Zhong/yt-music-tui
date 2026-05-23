import locale
# Keep the C locale locked down before any library initializations happen
locale.setlocale(locale.LC_NUMERIC, "C")

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, ListView, ListItem, Label, DataTable
from textual.binding import Binding

from ytmusicapi import YTMusic
from player_manager import PlaybackManager

class YTMusicTUI(App):
    """A YouTube Music Terminal User Interface."""
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("space", "toggle_playback", "Play/Pause", show=True),
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
        height: 5;
        background: #1a1a1a;
        border-top: solid #ff0055;
        padding: 1 2;
    }
    #track-info {
        color: #ffffff;
        text-style: bold;
    }
    #player-status {
        color: #888888;
    }
    """

    def on_mount(self) -> None:
        """Called when the app starts up and components are mounted."""
        self.ytmusic = YTMusic("browser.json")
        self.player = PlaybackManager(ui_callback=self.handle_player_event)
        
        table = self.query_one(DataTable)
        table.add_columns("Title", "Artist", "Album")
        table.cursor_type = "row"
        
        # Run explicitly in a background thread worker to protect the session
        self.run_worker(self.fetch_user_playlists, thread=True)

    def compose(self) -> ComposeResult:
        """Defines the structural blueprint of the TUI layout."""
        yield Header(show_clock=True)
        
        with Horizontal(id="app-body"):
            with Vertical(id="sidebar"):
                yield Label("📁 MY PLAYLISTS", classes="sidebar-title")
                yield ListView(id="menu-list")
            
            with Container(id="main-content"):
                yield Label("Tracks", id="content-title", classes="sidebar-title")
                yield DataTable()
        
        with Vertical(id="player-bar"):
            yield Label("⏹ Not Playing", id="track-info")
            yield Label("Status: Stopped | Volume: 100%", id="player-status")
            
        yield Footer()

    # ────────────── THREADED LOADING WORKERS ──────────────

    def fetch_user_playlists(self) -> None:
        """Background thread worker to fetch real account playlists cleanly."""
        try:
            playlists = self.ytmusic.get_library_playlists()
            # Safely pass the data array back to the main UI thread
            self.call_from_thread(self.populate_sidebar, playlists)
        except Exception as e:
            self.call_from_thread(self.query_one("#content-title", Label).update, f"Error: {e}")

    def populate_sidebar(self, playlists: list) -> None:
        """Populates the ListView component with real playlist entities."""
        menu_list = self.query_one("#menu-list", ListView)
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
            # FIX: Wrap in a lambda so the argument is passed safely to the thread core
            self.run_worker(lambda: self.load_playlist_tracks(playlist_id), thread=True)

    def load_playlist_tracks(self, playlist_id: str) -> None:
        """Background thread worker that pulls down tracks belonging to a playlist."""
        try:
            playlist_details = self.ytmusic.get_playlist(playlist_id)
            tracks = playlist_details.get('tracks', [])
            self.call_from_thread(self.populate_track_table, tracks)
        except Exception as e:
            self.call_from_thread(self.query_one("#content-title", Label).update, f"Error: {e}")

    def populate_track_table(self, tracks: list) -> None:
        """Clears the table layout and safely draws the new track objects."""
        table = self.query_one(DataTable)
        table.clear()
        
        # Initialize a dictionary to map Textual UI row keys to their exact YouTube video IDs
        self.row_to_video_id = {}
        
        self.query_one("#content-title", Label).update(f"Tracks ({len(tracks)} loaded)")

        for track in tracks:
            title = track.get('title', 'Unknown Title')
            album = track.get('album', {}).get('name', 'Unknown Album') if track.get('album') else 'N/A'
            artists_list = track.get('artists', [])
            artist = artists_list[0].get('name', 'Unknown Artist') if artists_list else 'Unknown'
            
            # Extract the pristine video ID attached to this playlist track
            video_id = track.get('videoId')
            
            # Add the row to the TUI screen and catch its unique row UI handle
            row_key = table.add_row(title, artist, album)
            
            # Link the UI row handle directly to the exact YouTube audio ID
            if video_id:
                self.row_to_video_id[row_key] = video_id

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Fires automatically when you select a song row and hit Enter."""
        table = self.query_one(DataTable)
        row_data = table.get_row(event.row_key)
        title, artist, album = row_data
        
        # Look up the exact, un-scrambled video ID for this chosen row
        video_id = getattr(self, "row_to_video_id", {}).get(event.row_key)
        
        if not video_id:
            self.query_one("#track-info", Label).update("❌ Exact track ID missing.")
            return
            
        self.query_one("#track-info", Label).update(f"⏳ Fetching stream: {title}...")
        self.query_one("#player-status", Label).update("Status: Loading...")
        
        # Pass the exact video ID straight to the background playback worker
        self.run_worker(lambda: self.play_track_worker(video_id, title, artist), thread=True)

    def play_track_worker(self, video_id: str, title: str, artist: str) -> None:
        """Bypasses web search entirely and boots up the exact audio layer stream."""
        # Clean, direct routing using the targeted ID token
        track_url = f"https://music.youtube.com/watch?v={video_id}"
        
        self.call_from_thread(self.query_one("#track-info", Label).update, f"▶ Now Playing: {title} by {artist}")
        self.call_from_thread(self.query_one("#player-status", Label).update, f"Status: Playing | Volume: {self.player.volume}%")
        
        self.player.play(track_url, title, artist)


    def handle_player_event(self, event_name: str) -> None:
        """Thread-safe callback triggered by background MPV events."""
        if event_name == "track_finished":
            self.call_from_thread(self.action_next_track)

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
