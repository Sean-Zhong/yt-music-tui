import time
import mpv
from ytmusicapi import YTMusic, OAuthCredentials

def test_playback():
    print("Authenticating with YTMusic...")
    ytmusic = YTMusic("browser.json")

    search_query = "Rick Astley Never Gonna Give You Up"
    print(f"Searching for: '{search_query}'...")
    
    # Search for songs matching the query
    search_results = ytmusic.search(search_query, filter="songs")
    
    if not search_results:
        print("Could not find the song.")
        return

    # Grab the first result
    first_track = search_results[0]
    video_id = first_track.get('videoId')
    song_title = first_track.get('title')
    artist = first_track.get('artists', [{'name': 'Unknown'}])[0]['name']

    if not video_id:
        print("Could not find a valid video ID for the track.")
        return

    track_url = f"https://music.youtube.com/watch?v={video_id}"
    print(f"\n▶ Now Playing: {song_title} by {artist}")
    print(f"URL: {track_url}\n")

    import locale
    locale.setlocale(locale.LC_NUMERIC, "C")

    # Initialize MPV
    player = mpv.MPV(ytdl=True, video=False)

    # Start playback
    player.play(track_url)
    
    try:
        player.wait_for_playback()
    except KeyboardInterrupt:
        print("\nPlayback stopped by user.")
    finally:
        player.terminate()    # Initialize MPV
    # ytdl=True tells MPV to use yt-dlp to extract the raw audio stream
    # video=False disables the video window since this is a TUI audio player
    player = mpv.MPV(ytdl=True, video=False)

    # Start playback
    player.play(track_url)
    
    try:
        # Block the script and wait for the track to finish playing
        player.wait_for_playback()
    except KeyboardInterrupt:
        print("\nPlayback stopped by user.")
    finally:
        # Clean up the player when done
        player.terminate()

if __name__ == "__main__":
    test_playback()
