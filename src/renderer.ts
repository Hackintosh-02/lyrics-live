/**
 * Renderer Process
 *
 * Handles lyrics display with multiple UI states:
 * - Loading: Startup/waiting for song detection
 * - No Lyrics: Song found but no synced lyrics available
 * - Karaoke: Displaying synced lyrics
 */

import { ipcRenderer } from 'electron';

const lyricsArea = document.getElementById('lyrics-area');
const debugLog = document.getElementById('debug-log');
const modeIndicator = document.getElementById('mode-indicator');
const closeBtn = document.getElementById('close-btn');

interface LyricLine {
  time: number;
  text: string;
}

// State
let currentLyrics: LyricLine[] = [];
let currentTrack = '';
let currentArtist = '';
let lastActiveIndex = -1;
let uiState: 'loading' | 'no-lyrics' | 'karaoke' = 'loading';
const VISIBLE_LINES = 5;
const MAX_LOG_LINES = 3;
let logLines: string[] = [];

// Close button
if (closeBtn) {
  closeBtn.addEventListener('click', () => {
    ipcRenderer.send('close-app');
  });
}

// Show initial loading UI
showLoadingUI();

// Handle messages from Python backend
ipcRenderer.on('lyrics-update', (_event: any, data: string) => {
  try {
    const parsed = JSON.parse(data);

    if (parsed.type === 'lyrics_load') {
      // New song with lyrics
      currentLyrics = parsed.lines.filter((l: LyricLine) => l.text.trim());
      currentTrack = parsed.track;
      currentArtist = parsed.artist;
      lastActiveIndex = -1;

      if (currentLyrics.length > 0) {
        uiState = 'karaoke';
        renderKaraoke(-1);
        addLog(`Now playing: ${currentTrack}`, true);
      } else {
        uiState = 'no-lyrics';
        showNoLyricsUI();
        addLog(`No synced lyrics for: ${currentTrack}`);
      }
    }
    else if (parsed.type === 'lrc_update') {
      if (uiState === 'karaoke') {
        updateKaraoke(parsed.position);
      }
    }
    else if (parsed.status) {
      // Status/log message
      addLog(parsed.status, parsed.status.includes('Identified') || parsed.status.includes('Lyrics found'));

      // If we get "No synced lyrics" status
      if (parsed.status.includes('No synced lyrics')) {
        uiState = 'no-lyrics';
        showNoLyricsUI();
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
    showModeIndicator('Resize Mode');
  } else {
    document.body.classList.remove('interactive');
    showModeIndicator('Locked');
  }
});

function showModeIndicator(text: string) {
  if (!modeIndicator) return;
  modeIndicator.textContent = text;
  modeIndicator.style.display = 'block';
  modeIndicator.style.animation = 'none';
  modeIndicator.offsetHeight;
  modeIndicator.style.animation = 'fadeOut 1.5s forwards';
  setTimeout(() => {
    modeIndicator.style.display = 'none';
  }, 1500);
}

function addLog(message: string, highlight = false) {
  // Clean up message
  let cleanMsg = message;
  if (cleanMsg.startsWith('Mic:')) cleanMsg = '🎤 ' + cleanMsg;
  else if (cleanMsg.includes('Identifying')) cleanMsg = '🔍 ' + cleanMsg;
  else if (cleanMsg.includes('Identified')) cleanMsg = '✓ ' + cleanMsg;
  else if (cleanMsg.includes('Lyrics found')) cleanMsg = '📝 ' + cleanMsg;
  else if (cleanMsg.includes('Fetching')) cleanMsg = '⏳ ' + cleanMsg;

  logLines.push(highlight ? `<span class="log-line highlight">${cleanMsg}</span>` : `<span class="log-line">${cleanMsg}</span>`);

  // Keep only last N lines
  if (logLines.length > MAX_LOG_LINES) {
    logLines.shift();
  }

  if (debugLog) {
    debugLog.innerHTML = logLines.join('<br>');
  }
}

function showLoadingUI() {
  if (!lyricsArea) return;

  lyricsArea.innerHTML = `
    <div class="loading-container">
      <div class="loading-logo">♪ ♫ ♪</div>
      <div class="loading-text">Listening<span class="loading-dots">...</span></div>
      <div class="loading-sub">Play some music to get started</div>
    </div>
  `;
}

function showNoLyricsUI() {
  if (!lyricsArea) return;

  lyricsArea.innerHTML = `
    <div class="no-lyrics-container">
      <div class="no-lyrics-icon">♪</div>
      <div class="no-lyrics-text">No synced lyrics available</div>
      ${currentTrack ? `<div class="no-lyrics-song">${currentTrack} - ${currentArtist}</div>` : ''}
    </div>
  `;
}

function renderKaraoke(activeIndex: number) {
  if (!lyricsArea) return;

  // Calculate visible window
  const halfWindow = Math.floor(VISIBLE_LINES / 2);
  let startIdx = Math.max(0, activeIndex - halfWindow);
  let endIdx = Math.min(currentLyrics.length - 1, activeIndex + halfWindow);

  // Adjust window at boundaries
  if (activeIndex < halfWindow) {
    endIdx = Math.min(currentLyrics.length - 1, VISIBLE_LINES - 1);
  }
  if (activeIndex > currentLyrics.length - halfWindow - 1) {
    startIdx = Math.max(0, currentLyrics.length - VISIBLE_LINES);
  }

  // Handle initial state (no active line yet)
  if (activeIndex < 0) {
    startIdx = 0;
    endIdx = Math.min(currentLyrics.length - 1, VISIBLE_LINES - 1);
  }

  let html = `<div class="karaoke-container">`;
  html += `<div class="song-header">${currentTrack} — ${currentArtist}</div>`;
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

  html += `</div></div>`;
  lyricsArea.innerHTML = html;
}

function updateKaraoke(position: number) {
  // Find active line
  let activeIndex = -1;
  for (let i = 0; i < currentLyrics.length; i++) {
    if (position >= currentLyrics[i].time) {
      activeIndex = i;
    } else {
      break;
    }
  }

  // Only re-render if changed
  if (activeIndex !== lastActiveIndex) {
    lastActiveIndex = activeIndex;
    renderKaraoke(activeIndex);
  }
}
