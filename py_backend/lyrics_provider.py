import aiohttp
import urllib.parse

class LyricsProvider:
    BASE_URL = "https://lrclib.net/api"

    async def get_lyrics(self, title, artist, album=None, duration=None):
        """
        Fetch synced lyrics from LRCLIB.
        Returns a dictionary with 'syncedLyrics', 'plainLyrics', etc. or None.
        """
        params = {
            "track_name": title,
            "artist_name": artist,
        }
        if album:
            params["album_name"] = album
        if duration:
            params["duration"] = duration

        async with aiohttp.ClientSession() as session:
            try:
                # 1. Try 'get' endpoint (precise match)
                async with session.get(f"{self.BASE_URL}/get", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("syncedLyrics"):
                            return data

                # 2. Fallback to 'search' endpoint
                async with session.get(f"{self.BASE_URL}/search", params=params) as resp:
                    if resp.status == 200:
                        results = await resp.json()
                        # Return first result with synced lyrics
                        for track in results:
                            if track.get("syncedLyrics"):
                                return track
            except Exception as e:
                print(f"Error fetching lyrics: {e}")
        
        return None

    def parse_lrc(self, lrc_text):
        """
        Parses LRC text into a list of (timestamp, text) tuples.
        Timestamp is in seconds.
        """
        lines = []
        if not lrc_text:
            return lines

        for line in lrc_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Basic LRC parsing [mm:ss.xx]Text
            try:
                if line.startswith('[') and ']' in line:
                    time_tag, text = line.split(']', 1)
                    time_tag = time_tag[1:] # Remove [
                    
                    minutes, seconds = time_tag.split(':')
                    timestamp = float(minutes) * 60 + float(seconds)
                    
                    lines.append({
                        "time": timestamp,
                        "text": text.strip()
                    })
            except Exception:
                continue
                
        return lines
