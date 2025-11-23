import sys
sys.argv = sys.argv or ['main']  # Fix soundcard bug with empty argv
import time
import json
import asyncio
import tempfile
import numpy as np
import soundcard as sc
import scipy.io.wavfile as wav
from shazamio import Shazam
from lyrics_provider import LyricsProvider
from faster_whisper import WhisperModel

# Configuration
SAMPLE_RATE = 44100 # Higher quality for music identification
BLOCK_SIZE = 4096
SHAZAM_SAMPLE_DURATION = 10  # 10 seconds for reliable Shazam identification
SHAZAM_INTERVAL = 10.0  # Wait 10 seconds between Shazam attempts
WHISPER_MODEL_SIZE = "tiny"

# Sync calibration settings
# IMPORTANT: Adjust SYNC_OFFSET_CORRECTION to fix timing
# Positive = lyrics appear EARLIER, Negative = lyrics appear LATER
SYNC_OFFSET_CORRECTION = 2.0  # Extra seconds to add to compensate for delays
CALIBRATION_SAMPLES = 5
DRIFT_CORRECTION_RATE = 1.0  # Immediate correction

class LyricsApp:
    def __init__(self):
        self.shazam = Shazam()
        self.lyrics_provider = LyricsProvider()
        self.whisper_model = None

        self.current_song = None
        self.song_start_time = 0  # System time when song started (estimated)
        self.lyrics_lines = []
        self.is_playing_lrc = False

        self.last_shazam_time = 0
        self.audio_buffer = np.array([], dtype=np.float32)

        # Whisper buffer
        self.whisper_buffer = np.array([], dtype=np.float32)
        self.last_transcription_time = 0

        # Sync calibration - stores recent offset measurements
        self.offset_history = []  # List of (measured_offset, timestamp, shazam_processing_time)
        self.sync_drift = 0  # Accumulated drift correction

    def load_whisper(self):
        if not self.whisper_model:
            print(json.dumps({"status": "Loading Whisper model..."}), flush=True)
            try:
                self.whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
                print(json.dumps({"status": "Whisper model loaded"}), flush=True)
            except Exception as e:
                print(json.dumps({"error": f"Whisper load failed: {e}"}), flush=True)

    async def identify_song(self, audio_chunk):
        # Shazam expects bytes (WAV/PCM) or file path.
        # We need to convert float32 numpy array to int16 bytes.
        audio_int16 = (audio_chunk * 32767).astype(np.int16)

        # Check if audio has actual content (not silence)
        audio_level = np.abs(audio_int16).mean()
        print(json.dumps({"status": f"Audio level: {audio_level:.0f}"}), flush=True)

        if audio_level < 100:
            print(json.dumps({"status": "Audio too quiet - is music playing?"}), flush=True)
            return None

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                wav.write(tmp_path, SAMPLE_RATE, audio_int16)

            out = await self.shazam.recognize(tmp_path)
            return out
        except Exception as e:
            print(json.dumps({"error": f"Shazam error: {e}"}), flush=True)
            return None
        finally:
            # Clean up temp file
            if tmp_path:
                try:
                    import os
                    os.unlink(tmp_path)
                except:
                    pass

    async def run(self):
        print(json.dumps({"status": "Starting Hybrid Backend..."}), flush=True)
        
        # Audio Setup
        mic = self.get_loopback_mic()
        if not mic:
            return

        # Main Loop
        with mic.recorder(samplerate=SAMPLE_RATE) as recorder:
            while True:
                # 1. Record Audio
                data = recorder.record(numframes=BLOCK_SIZE)
                mono_data = data.mean(axis=1)
                
                # Update buffers
                self.audio_buffer = np.concatenate((self.audio_buffer, mono_data))
                self.whisper_buffer = np.concatenate((self.whisper_buffer, mono_data))
                
                current_time = time.time()

                # 2. Try Identification (if buffer big enough and interval passed)
                if len(self.audio_buffer) > SAMPLE_RATE * SHAZAM_SAMPLE_DURATION:
                    if current_time - self.last_shazam_time > SHAZAM_INTERVAL:
                        self.last_shazam_time = current_time

                        # Record the exact moment the sample ends (NOW)
                        sample_end_time = time.time()

                        # Run identification in background
                        # We take the last N seconds
                        chunk = self.audio_buffer[-SAMPLE_RATE*SHAZAM_SAMPLE_DURATION:]

                        # Reset buffer to avoid growing forever
                        self.audio_buffer = np.array([], dtype=np.float32)

                        print(json.dumps({"status": f"Identifying song ({SHAZAM_SAMPLE_DURATION}s sample)..."}), flush=True)

                        # Time the Shazam API call
                        shazam_start = time.time()
                        result = await self.identify_song(chunk)
                        shazam_duration = time.time() - shazam_start

                        await self.handle_shazam_result(result, sample_end_time, shazam_duration)

                # 3. Broadcast State
                if self.is_playing_lrc:
                    # Calculate current song position
                    position = current_time - self.song_start_time
                    print(json.dumps({
                        "type": "lrc_update",
                        "position": position,
                        "track": self.current_song
                    }), flush=True)
                # Whisper fallback disabled for now (code kept for future use)
                # else:
                #     self.load_whisper()
                #     await self.process_whisper(current_time)

                await asyncio.sleep(0.01)

    async def handle_shazam_result(self, result, sample_end_time, shazam_duration):
        """
        Handle Shazam result with precise timing calibration.

        Args:
            result: Shazam API response
            sample_end_time: Timestamp when audio sample capture ended
            shazam_duration: How long the Shazam API call took
        """
        if not result:
            print(json.dumps({"status": "Shazam returned None"}), flush=True)
            return

        if 'track' not in result:
            print(json.dumps({"status": "Shazam: No track found in result"}), flush=True)
            return

        track = result['track']
        title = track.get('title')
        artist = track.get('subtitle')

        # Get Shazam offset (position in song where sample matched)
        shazam_offset = 0
        if 'matches' in result and result['matches']:
            shazam_offset = result['matches'][0].get('offset', 0)

        print(json.dumps({"status": f"Identified: {title} | offset={shazam_offset:.1f}s | api_time={shazam_duration:.2f}s"}), flush=True)

        # Check if song changed
        is_new_song = (self.current_song != title)

        if is_new_song:
            # New song - reset calibration
            self.current_song = title
            self.offset_history = []
            self.sync_drift = 0

        # Calculate the precise song position at the moment sample ended
        # Shazam offset = where in the song the END of our sample was
        # (Actually it's roughly the middle, but we'll calibrate)

        # Record this measurement for calibration
        self.offset_history.append({
            'shazam_offset': shazam_offset,
            'sample_end_time': sample_end_time,
            'api_duration': shazam_duration
        })

        # Keep only recent measurements
        if len(self.offset_history) > CALIBRATION_SAMPLES:
            self.offset_history.pop(0)

        # Calculate song_start_time
        # Shazam offset = position in song where our sample STARTS matching
        # At sample_end_time, we were at: shazam_offset + SHAZAM_SAMPLE_DURATION
        # Plus add SYNC_OFFSET_CORRECTION to compensate for system delays

        actual_position_at_sample_end = shazam_offset + SHAZAM_SAMPLE_DURATION + SYNC_OFFSET_CORRECTION
        new_song_start_time = sample_end_time - actual_position_at_sample_end

        if is_new_song:
            # First detection - use calculated value directly
            self.song_start_time = new_song_start_time
        else:
            # Recalibration - smoothly adjust to avoid jarring jumps
            # Calculate what our current estimate says the position should be
            current_time = time.time()
            our_estimated_position = current_time - self.song_start_time
            shazam_estimated_position = current_time - new_song_start_time

            drift = shazam_estimated_position - our_estimated_position

            # Only correct if drift is significant (> 0.5s)
            if abs(drift) > 0.5:
                # Apply gradual correction
                correction = drift * DRIFT_CORRECTION_RATE
                self.song_start_time -= correction
                self.sync_drift += correction

                print(json.dumps({
                    "status": f"Sync correction: drift={drift:.2f}s, applied={correction:.2f}s, total_drift={self.sync_drift:.2f}s"
                }), flush=True)

        # Show current calculated position
        current_time = time.time()
        current_position = current_time - self.song_start_time
        print(json.dumps({"status": f"Current position: {current_position:.1f}s"}), flush=True)

        if is_new_song:
            # Fetch Lyrics for new song
            print(json.dumps({"status": f"Fetching lyrics for {title}..."}), flush=True)
            lyrics_data = await self.lyrics_provider.get_lyrics(title, artist)
            
            if lyrics_data and lyrics_data.get('syncedLyrics'):
                print(json.dumps({"status": "Lyrics found!"}), flush=True)
                self.lyrics_lines = self.lyrics_provider.parse_lrc(lyrics_data['syncedLyrics'])
                self.is_playing_lrc = True
                
                # Send full lyrics to frontend once
                print(json.dumps({
                    "type": "lyrics_load",
                    "lines": self.lyrics_lines,
                    "track": title,
                    "artist": artist
                }), flush=True)
            else:
                print(json.dumps({"status": "No synced lyrics found. Using Whisper."}), flush=True)
                self.is_playing_lrc = False

    async def process_whisper(self, current_time):
        # Transcribe every 3 seconds
        if current_time - self.last_transcription_time > 3.0:
            if len(self.whisper_buffer) > 0:
                # Run blocking whisper in executor to avoid blocking loop
                loop = asyncio.get_running_loop()
                segments = await loop.run_in_executor(None, self.transcribe_sync, self.whisper_buffer)
                
                for seg in segments:
                    print(json.dumps({
                        "type": "whisper",
                        "text": seg['text'],
                        "start": seg['start'],
                        "end": seg['end']
                    }), flush=True)
                
                self.whisper_buffer = np.array([], dtype=np.float32)
                self.last_transcription_time = current_time

    def transcribe_sync(self, audio):
        try:
            segments, _ = self.whisper_model.transcribe(audio, beam_size=1, language="en")
            return [{"text": s.text, "start": s.start, "end": s.end} for s in segments]
        except Exception:
            return []

    def get_loopback_mic(self):
        try:
            mics = sc.all_microphones(include_loopback=True)
            for m in mics:
                if "monitor" in m.name.lower() or "loopback" in m.name.lower():
                    print(json.dumps({"status": f"Mic: {m.name}"}), flush=True)
                    return m
            return sc.default_microphone()
        except Exception as e:
            print(json.dumps({"error": f"Mic error: {e}"}), flush=True)
            return None

if __name__ == "__main__":
    app = LyricsApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        pass

