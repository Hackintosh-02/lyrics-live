"""
Lyrics Live - Main Backend

Orchestrates audio capture, song identification, and lyrics sync.
Outputs JSON messages to stdout for Electron frontend.
"""

import sys
sys.argv = sys.argv or ['main']  # Fix soundcard bug

import time
import json
import asyncio
import tempfile
import numpy as np
import soundcard as sc
import scipy.io.wavfile as wav
from shazamio import Shazam
from lyrics_provider import LyricsProvider

# Audio settings
SAMPLE_RATE = 44100
BLOCK_SIZE = 4096
SHAZAM_SAMPLE_DURATION = 10  # Seconds of audio for Shazam
SHAZAM_INTERVAL = 10.0  # Seconds between identification attempts

# Sync calibration
# Adjust this value if lyrics are ahead (+) or behind (-)
SYNC_OFFSET_CORRECTION = 3.0


class LyricsApp:
    def __init__(self):
        self.shazam = Shazam()
        self.lyrics_provider = LyricsProvider()

        self.current_song = None
        self.song_start_time = 0
        self.lyrics_lines = []
        self.is_playing_lrc = False

        self.last_shazam_time = 0
        self.audio_buffer = np.array([], dtype=np.float32)

    def log(self, message: str):
        """Send status message to frontend."""
        print(json.dumps({"status": message}), flush=True)

    def get_loopback_mic(self):
        """Find system audio loopback device."""
        try:
            mics = sc.all_microphones(include_loopback=True)
            for m in mics:
                if "monitor" in m.name.lower() or "loopback" in m.name.lower():
                    self.log(f"Audio device: {m.name}")
                    return m
            return sc.default_microphone()
        except Exception as e:
            self.log(f"Audio error: {e}")
            return None

    async def identify_song(self, audio_chunk: np.ndarray) -> dict | None:
        """Send audio to Shazam for identification."""
        audio_int16 = (audio_chunk * 32767).astype(np.int16)

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav.write(tmp.name, SAMPLE_RATE, audio_int16)
                result = await self.shazam.recognize(tmp.name)
                return result
        except Exception as e:
            self.log(f"Shazam error: {e}")
            return None

    async def handle_shazam_result(self, result: dict, sample_end_time: float):
        """Process Shazam result and sync lyrics."""
        if not result or 'track' not in result:
            return

        track = result['track']
        title = track.get('title')
        artist = track.get('subtitle')

        # Get timing offset
        shazam_offset = 0
        if 'matches' in result and result['matches']:
            shazam_offset = result['matches'][0].get('offset', 0)

        self.log(f"Identified: {title} by {artist} (offset: {shazam_offset:.1f}s)")

        # Check if song changed
        if self.current_song != title:
            self.current_song = title

            # Calculate song start time
            # offset = position in song at START of our sample
            # sample_end_time = when we finished recording
            actual_position = shazam_offset + SHAZAM_SAMPLE_DURATION + SYNC_OFFSET_CORRECTION
            self.song_start_time = sample_end_time - actual_position

            self.log(f"Current position: {time.time() - self.song_start_time:.1f}s")

            # Fetch lyrics
            self.log(f"Fetching lyrics...")
            lyrics_data = await self.lyrics_provider.get_lyrics(title, artist)

            if lyrics_data and lyrics_data.get('syncedLyrics'):
                self.log("Lyrics found!")
                self.lyrics_lines = self.lyrics_provider.parse_lrc(lyrics_data['syncedLyrics'])
                self.is_playing_lrc = True

                # Send lyrics to frontend
                print(json.dumps({
                    "type": "lyrics_load",
                    "lines": self.lyrics_lines,
                    "track": title,
                    "artist": artist
                }), flush=True)
            else:
                self.log("No synced lyrics found")
                self.is_playing_lrc = False

    async def run(self):
        """Main loop."""
        self.log("Starting Lyrics Live...")

        mic = self.get_loopback_mic()
        if not mic:
            self.log("No audio device found!")
            return

        with mic.recorder(samplerate=SAMPLE_RATE) as recorder:
            while True:
                # Record audio chunk
                data = recorder.record(numframes=BLOCK_SIZE)
                mono = data.mean(axis=1).astype(np.float32)
                self.audio_buffer = np.concatenate((self.audio_buffer, mono))

                current_time = time.time()

                # Try identification when buffer is ready
                if len(self.audio_buffer) > SAMPLE_RATE * SHAZAM_SAMPLE_DURATION:
                    if current_time - self.last_shazam_time > SHAZAM_INTERVAL:
                        self.last_shazam_time = current_time
                        sample_end_time = time.time()

                        chunk = self.audio_buffer[-SAMPLE_RATE * SHAZAM_SAMPLE_DURATION:]
                        self.audio_buffer = np.array([], dtype=np.float32)

                        self.log(f"Identifying song ({SHAZAM_SAMPLE_DURATION}s sample)...")
                        result = await self.identify_song(chunk)
                        await self.handle_shazam_result(result, sample_end_time)

                # Send position updates for synced lyrics
                if self.is_playing_lrc:
                    position = current_time - self.song_start_time
                    print(json.dumps({
                        "type": "lrc_update",
                        "position": position,
                        "track": self.current_song
                    }), flush=True)

                await asyncio.sleep(0.01)


if __name__ == "__main__":
    app = LyricsApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass
