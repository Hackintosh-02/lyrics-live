"""
Lyrics Provider Module

Fetches synced lyrics from LRCLIB (free, no API key required).
Parses LRC format timestamps for karaoke-style display.
"""

import re
import aiohttp

LRCLIB_API = "https://lrclib.net/api"


class LyricsProvider:
    """Fetches and parses synced lyrics from LRCLIB."""

    async def get_lyrics(self, title: str, artist: str) -> dict | None:
        """
        Fetch lyrics for a song.

        Args:
            title: Song title
            artist: Artist name

        Returns:
            dict with 'syncedLyrics', 'plainLyrics' or None
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Try exact match first
                params = {
                    "track_name": title,
                    "artist_name": artist
                }
                async with session.get(f"{LRCLIB_API}/get", params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()

                # Fallback to search
                async with session.get(f"{LRCLIB_API}/search", params={"q": f"{title} {artist}"}) as resp:
                    if resp.status == 200:
                        results = await resp.json()
                        if results:
                            # Return first result with synced lyrics
                            for r in results:
                                if r.get('syncedLyrics'):
                                    return r
                            return results[0] if results else None

        except Exception as e:
            print(f"LRCLIB error: {e}")

        return None

    def parse_lrc(self, lrc_text: str) -> list[dict]:
        """
        Parse LRC format into list of timed lines.

        LRC format: [mm:ss.xx]Lyrics text here

        Returns:
            List of {'time': float, 'text': str}
        """
        lines = []
        pattern = r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)'

        for line in lrc_text.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                ms_str = match.group(3)
                # Handle both .xx and .xxx formats
                if len(ms_str) == 2:
                    ms = int(ms_str) * 10
                else:
                    ms = int(ms_str)

                time_sec = minutes * 60 + seconds + ms / 1000
                text = match.group(4).strip()

                lines.append({
                    'time': time_sec,
                    'text': text
                })

        return lines
