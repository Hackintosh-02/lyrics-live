"""
Song Identifier Module

Uses Shazam (via shazamio) to identify songs from audio samples.
Returns song title, artist, and timing offset for sync.
"""

import tempfile
import numpy as np
import scipy.io.wavfile as wav
from shazamio import Shazam

SAMPLE_RATE = 44100


class SongIdentifier:
    """Identifies songs using Shazam's audio fingerprinting."""

    def __init__(self):
        self.shazam = Shazam()

    async def identify(self, audio_chunk: np.ndarray) -> dict | None:
        """
        Identify a song from an audio chunk.

        Args:
            audio_chunk: Mono float32 audio data

        Returns:
            dict with 'title', 'artist', 'offset' or None if not identified
        """
        # Convert float32 to int16 for WAV file
        audio_int16 = (audio_chunk * 32767).astype(np.int16)

        try:
            # Save to temp WAV file (shazamio needs a file path)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                wav.write(tmp.name, SAMPLE_RATE, audio_int16)
                result = await self.shazam.recognize(tmp.name)

            if not result or 'track' not in result:
                return None

            track = result['track']

            # Get timing offset from matches
            # This tells us where in the song our sample was captured
            offset = 0
            if 'matches' in result and result['matches']:
                offset = result['matches'][0].get('offset', 0)

            return {
                'title': track.get('title'),
                'artist': track.get('subtitle'),
                'offset': offset,
                'raw': result  # Keep raw result for debugging
            }

        except Exception as e:
            print(f"Shazam error: {e}")
            return None
