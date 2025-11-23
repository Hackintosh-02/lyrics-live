# Lyrics Live

Real-time system-wide lyrics overlay that displays synced karaoke-style lyrics for any audio playing on your computer.

![Lyrics Live Demo](demo.gif)

## Features

- **Universal Audio Detection** - Works with YouTube, Spotify, local MP3s, or any audio source
- **Shazam Integration** - Automatically identifies songs using audio fingerprinting
- **Synced Lyrics** - Fetches timestamped lyrics from LRCLIB
- **Karaoke Display** - Highlights current line as the song plays
- **Transparent Overlay** - Always-on-top, click-through window
- **Resizable** - Adjust size and position to your preference

## How It Works

```
┌─────────────────────────────────────────────────┐
│  System Audio (YouTube/Spotify/etc)             │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Audio Capture (PulseAudio Loopback)            │
└─────────────────┬───────────────────────────────┘
                  │ 10s sample
                  ▼
┌─────────────────────────────────────────────────┐
│  Shazam API → Song title + timing offset        │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  LRCLIB API → Synced lyrics                     │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  Electron Overlay → Karaoke display             │
└─────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Node.js 18+
- Python 3.10+
- Linux with PulseAudio (for audio loopback)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Hackintosh-02/lyrics-live.git
   cd lyrics-live
   ```

2. **Install Node dependencies**
   ```bash
   npm install
   ```

3. **Set up Python virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r py_backend/requirements.txt
   ```

4. **Build TypeScript**
   ```bash
   npm run build
   ```

5. **Run the app**
   ```bash
   npm start
   ```

## Usage

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+L` | Toggle resize/move mode |
| `Ctrl+Shift+H` | Hide/show overlay |

### Getting Started

1. Start the app with `npm start`
2. Play any music on your computer
3. Wait ~10 seconds for song identification
4. Lyrics will appear and sync automatically!

### Adjusting Position

1. Press `Ctrl+Shift+L` to enter resize mode
2. Drag the purple bar to move
3. Drag edges to resize
4. Press `Ctrl+Shift+L` again to lock

## Configuration

Edit `py_backend/main.py` to adjust:

```python
SYNC_OFFSET_CORRECTION = 3.0  # Adjust if lyrics are ahead/behind
SHAZAM_SAMPLE_DURATION = 10   # Seconds of audio for identification
```

## APIs Used

| Service | API Key | Cost |
|---------|---------|------|
| Shazam (shazamio) | Not required | Free |
| LRCLIB | Not required | Free |

## Tech Stack

- **Frontend**: Electron + TypeScript
- **Backend**: Python (asyncio)
- **Audio**: soundcard + PulseAudio
- **Song ID**: shazamio (Shazam)
- **Lyrics**: LRCLIB

## Limitations

- Linux only (requires PulseAudio loopback)
- Needs ~10 seconds to identify a song
- Some songs may not have synced lyrics

## Contributing

Pull requests welcome! Feel free to open issues for bugs or feature requests.

## Credits

This project was vibe-coded with assistance from:
- **Claude** (Anthropic) - Architecture and implementation
- **Gemini** (Google) - Initial prototyping

## License

MIT
