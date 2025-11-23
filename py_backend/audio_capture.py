"""
Audio Capture Module

Captures system audio using PulseAudio loopback device.
This allows us to record any audio playing on the system
(YouTube, Spotify, local files, etc.)
"""

import sys
sys.argv = sys.argv or ['audio_capture']  # Fix soundcard argv bug

import numpy as np
import soundcard as sc

# Audio settings
SAMPLE_RATE = 44100
BLOCK_SIZE = 4096


def get_loopback_device():
    """
    Find the system audio loopback device.
    On Linux (PulseAudio), this is usually called "Monitor of..."
    """
    try:
        mics = sc.all_microphones(include_loopback=True)
        for mic in mics:
            # Look for loopback/monitor device
            if "monitor" in mic.name.lower() or "loopback" in mic.name.lower():
                return mic
        # Fallback to default
        return sc.default_microphone()
    except Exception as e:
        print(f"Error finding audio device: {e}")
        return None


class AudioCapture:
    """Captures system audio into a buffer for processing."""

    def __init__(self, sample_rate=SAMPLE_RATE, block_size=BLOCK_SIZE):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.device = None
        self.recorder = None
        self.buffer = np.array([], dtype=np.float32)

    def start(self):
        """Initialize the audio capture device."""
        self.device = get_loopback_device()
        if not self.device:
            raise RuntimeError("No audio loopback device found")
        return self.device.name

    def read_chunk(self):
        """Read a chunk of audio data."""
        if not self.recorder:
            self.recorder = self.device.recorder(samplerate=self.sample_rate)
            self.recorder.__enter__()

        data = self.recorder.record(numframes=self.block_size)
        # Convert stereo to mono
        mono = data.mean(axis=1).astype(np.float32)
        return mono

    def add_to_buffer(self, chunk):
        """Add audio chunk to buffer."""
        self.buffer = np.concatenate((self.buffer, chunk))

    def get_buffer(self, seconds):
        """Get last N seconds from buffer."""
        samples = int(seconds * self.sample_rate)
        if len(self.buffer) >= samples:
            return self.buffer[-samples:]
        return self.buffer

    def clear_buffer(self):
        """Clear the audio buffer."""
        self.buffer = np.array([], dtype=np.float32)

    def stop(self):
        """Stop recording."""
        if self.recorder:
            self.recorder.__exit__(None, None, None)
            self.recorder = None
