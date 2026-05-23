import locale
locale.setlocale(locale.LC_NUMERIC, "C")
from ytmusicapi import YTMusic

print("Connecting to YouTube Music...")
yt = YTMusic("browser.json")

try:
    playlists = yt.get_library_playlists()
    print(f"\n✅ SUCCESS! Found {len(playlists)} playlists:")
    for p in playlists:
        print(f" - {p['title']} (ID: {p['playlistId']})")
except Exception as e:
    print(f"\n❌ API Error: {e}")
