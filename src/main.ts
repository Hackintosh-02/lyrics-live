/**
 * Electron Main Process
 *
 * Creates the transparent overlay window and spawns the Python backend.
 * Handles IPC between Python and renderer.
 */

import { app, BrowserWindow, screen, ipcMain, globalShortcut } from 'electron';
import * as path from 'path';
import * as child_process from 'child_process';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: child_process.ChildProcess | null = null;
let isInteractive = true; // Start in interactive mode for positioning

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 800,
    height: 200,
    x: Math.floor((width - 800) / 2),
    y: height - 250,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: true,
    minWidth: 300,
    minHeight: 100,
    maxHeight: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  // Start in interactive mode so user can position
  mainWindow.setIgnoreMouseEvents(false);
  mainWindow.loadFile(path.join(__dirname, '../index.html'));

  // Notify renderer of initial mode
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow?.webContents.send('mode-change', { interactive: true });
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Global shortcuts
  // Ctrl+Shift+L: Toggle interactive mode (resize/move vs click-through)
  globalShortcut.register('CommandOrControl+Shift+L', () => {
    if (!mainWindow) return;

    isInteractive = !isInteractive;

    if (isInteractive) {
      mainWindow.setIgnoreMouseEvents(false);
      mainWindow.webContents.send('mode-change', { interactive: true });
    } else {
      mainWindow.setIgnoreMouseEvents(true, { forward: true });
      mainWindow.webContents.send('mode-change', { interactive: false });
    }
  });

  // Ctrl+Shift+H: Hide/show overlay
  globalShortcut.register('CommandOrControl+Shift+H', () => {
    if (!mainWindow) return;

    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
    }
  });
}

function startPythonBackend() {
  const pythonPath = path.join(__dirname, '../venv/bin/python');
  const scriptPath = path.join(__dirname, '../py_backend/main.py');

  console.log(`Starting Python: ${scriptPath}`);

  pythonProcess = child_process.spawn(pythonPath, [scriptPath]);

  // Buffer for handling partial JSON lines
  let buffer = '';

  pythonProcess.stdout?.on('data', (data) => {
    buffer += data.toString();

    // Process complete lines
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        console.log(`Python: ${trimmed}`);
        mainWindow?.webContents.send('lyrics-update', trimmed);
      }
    }
  });

  pythonProcess.stderr?.on('data', (data) => {
    console.error(`Python error: ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python exited with code ${code}`);
  });
}

app.on('ready', () => {
  createWindow();
  startPythonBackend();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
