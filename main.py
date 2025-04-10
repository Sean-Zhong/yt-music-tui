import time
from ytmusicapi import YTMusic, OAuthCredentials

if __name__ == "__main__":

    ytmusic = YTMusic("oauth.json", oauth_credentials=OAuthCredentials(client_id="637615654138-v42buto442sse8r5e8pcmd6fu6aaccpk.apps.googleusercontent.com", client_secret="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"))

    user_playlists = ytmusic.get_library_playlists()

    print(user_playlists)

    print("Test")