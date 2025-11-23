/**
 * Renderer Process
 *
 * Handles lyrics display and karaoke-style highlighting.
 * Receives messages from main process via IPC.
 */

import { ipcRenderer } from 'electron';

const lyricsContainer = document.getElementById('lyrics-container');
const modeIndicator = document.getElementById('mode-indicator');

interface LyricLine {
  time: number;
  text: string;
}

let currentLyrics: LyricLine[] = [];
let isKaraokeMode = false;

// Handle lyrics updates from Python backend
ipcRenderer.on('lyrics-update', (_event: any, data: string) => {
  try {
    const parsed = JSON.parse(data);

    if (parsed.type === 'lyrics_load') {
      // New song with synced lyrics
      isKaraokeMode = true;
      currentLyrics = parsed.lines;
      renderLyrics(parsed.track, parsed.artist);
    }
    else if (parsed.type === 'lrc_update') {
      // Position update - highlight current line
      if (isKaraokeMode) {
        updateHighlight(parsed.position);
      }
    }
    else if (parsed.status) {
      // Status message
      if (!isKaraokeMode) {
        showStatus(parsed.status);
      }
    }
  } catch (e) {
    console.error("Parse error:", data);
  }
});

// Handle mode changes
ipcRenderer.on('mode-change', (_event: any, data: { interactive: boolean }) => {
  if (data.interactive) {
    document.body.classList.add('interactive');
    showModeIndicator('Resize Mode - Drag to move/resize');
  } else {
    document.body.classList.remove('interactive');
    showModeIndicator('Locked - Click-through enabled');
  }
});

function showModeIndicator(text: string) {
  if (!modeIndicator) return;

  modeIndicator.textContent = text;
  modeIndicator.style.display = 'block';
  modeIndicator.style.animation = 'none';
  modeIndicator.offsetHeight; // Trigger reflow
  modeIndicator.style.animation = 'fadeOut 2s forwards';

  setTimeout(() => {
    modeIndicator.style.display = 'none';
  }, 2000);
}

function renderLyrics(track: string, artist: string) {
  if (!lyricsContainer) return;

  lyricsContainer.classList.remove('waiting');

  let html = `<div class="song-info">${track} - ${artist}</div>`;
  html += `<div class="lyrics-scroll">`;

  currentLyrics.forEach((line, index) => {
    if (line.text.trim()) {
      html += `<div class="line" id="line-${index}">${line.text}</div>`;
    }
  });

  html += `</div>`;
  lyricsContainer.innerHTML = html;
  lyricsContainer.className = 'karaoke-mode';
}

function updateHighlight(position: number) {
  if (!lyricsContainer) return;

  // Find active line based on position
  let activeIndex = -1;
  for (let i = 0; i < currentLyrics.length; i++) {
    if (position >= currentLyrics[i].time) {
      activeIndex = i;
    } else {
      break;
    }
  }

  if (activeIndex !== -1) {
    const lines = document.querySelectorAll('.line');
    lines.forEach((el, idx) => {
      if (idx === activeIndex) {
        el.classList.add('active');
        el.classList.remove('past');
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else if (idx < activeIndex) {
        el.classList.add('past');
        el.classList.remove('active');
      } else {
        el.classList.remove('active', 'past');
      }
    });
  }
}

function showStatus(text: string) {
  if (!lyricsContainer) return;

  lyricsContainer.className = 'waiting';
  lyricsContainer.textContent = text;
}
