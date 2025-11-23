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
let currentTrack = '';
let currentArtist = '';
const VISIBLE_LINES = 5; // Show 5 lines at a time (2 before, current, 2 after)

// Handle lyrics updates from Python backend
ipcRenderer.on('lyrics-update', (_event: any, data: string) => {
  try {
    const parsed = JSON.parse(data);

    if (parsed.type === 'lyrics_load') {
      // New song with synced lyrics
      isKaraokeMode = true;
      currentLyrics = parsed.lines.filter((l: LyricLine) => l.text.trim()); // Filter empty lines
      currentTrack = parsed.track;
      currentArtist = parsed.artist;
      renderVisibleLyrics(-1); // Initial render
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

function renderVisibleLyrics(activeIndex: number) {
  if (!lyricsContainer) return;

  lyricsContainer.classList.remove('waiting');
  lyricsContainer.className = 'karaoke-mode';

  // Calculate visible range (sliding window around active line)
  const halfWindow = Math.floor(VISIBLE_LINES / 2);
  let startIdx = Math.max(0, activeIndex - halfWindow);
  let endIdx = Math.min(currentLyrics.length - 1, activeIndex + halfWindow);

  // If at the beginning, show more lines after
  if (activeIndex < halfWindow) {
    endIdx = Math.min(currentLyrics.length - 1, VISIBLE_LINES - 1);
  }
  // If at the end, show more lines before
  if (activeIndex > currentLyrics.length - halfWindow - 1) {
    startIdx = Math.max(0, currentLyrics.length - VISIBLE_LINES);
  }

  let html = `<div class="song-info">${currentTrack} - ${currentArtist}</div>`;
  html += `<div class="lyrics-scroll">`;

  for (let i = startIdx; i <= endIdx; i++) {
    const line = currentLyrics[i];
    if (!line) continue;

    let className = 'line';
    if (i === activeIndex) {
      className += ' active';
    } else if (i < activeIndex) {
      className += ' past';
    }

    html += `<div class="${className}">${line.text}</div>`;
  }

  html += `</div>`;
  lyricsContainer.innerHTML = html;
}

let lastActiveIndex = -1;

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

  // Only re-render if active line changed
  if (activeIndex !== lastActiveIndex && activeIndex !== -1) {
    lastActiveIndex = activeIndex;
    renderVisibleLyrics(activeIndex);
  }
}

function showStatus(text: string) {
  if (!lyricsContainer) return;

  lyricsContainer.className = 'waiting';
  lyricsContainer.textContent = text;
}
