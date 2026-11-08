# core/speech.py
import asyncio
import itertools
import os
import queue
import re
import tempfile
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import edge_tts
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

VOICE = "en-US-AvaMultilingualNeural"
FIRST_CHUNK_MIN = 40  
LATER_CHUNK_MIN = 150
        
def _chunks(text):
    """Splits text into clips: a short first one, then longer ones."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    chunks, current, minimum = [], "", FIRST_CHUNK_MIN
    for s in sentences:
        current = f"{current} {s}".strip()
        if len(current) >= minimum:
            chunks.append(current)
            current, minimum = "", LATER_CHUNK_MIN
    if current:
        if chunks and len(current) < 25:        # don't leave a trailing clip
            chunks[-1] += " " + current
        else:
            chunks.append(current)
    return chunks


def _synth(text, path):
    asyncio.run(edge_tts.Communicate(text, VOICE).save(path))


class Speaker(QObject):
    """Speaks text in chunks. Create it ONCE, after QGuiApplication exists."""

    _file_ready = pyqtSignal(str)       # worker thread -> main thread: a clip is ready to play
    textReady = pyqtSignal(str)         # fires when the audio for a reply starts (or if speech fails)

    @property
    def generation(self):
        return self._generation

    def __init__(self):
        super().__init__()
        self._dir = tempfile.mkdtemp(prefix="ava_tts_")
        self._pool = ThreadPoolExecutor(max_workers=3)  
        self._order_q = queue.Queue() 
        self._counter = itertools.count(1)
        self._generation = 0  
        self._show = {}
        self._playlist = deque()
        self._busy = False
        self._current = None

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._file_ready.connect(self._enqueue)

        threading.Thread(target=self._feeder, daemon=True).start()

    # ---------- public ----------
    def speak(self, text, show_text=None, generation=None):
        """Queue text to be spoken. If `generation` is given and out of date, the reply belongs
        to a turn that was already interrupted, so it's ignored."""
        if generation is not None and generation != self._generation:
            return
        gen = self._generation
        chunks = _chunks(text)
        if not chunks:
            if show_text:
                self.textReady.emit(show_text)
            return
        for i, chunk in enumerate(chunks):
            path = os.path.join(self._dir, f"speech_{next(self._counter)}.mp3")
            if i == 0 and show_text:
                self._show[path] = show_text
            self._order_q.put((gen, self._pool.submit(_synth, chunk, path), path))

    def stop(self, flush_text=True):
        """Cut off speech and clear everything queued. Call from the UI thread.
        flush_text=False cuts the old reply's text instead of showing it, interrupting it."""
        self._generation += 1
        while True:
            try:
                _, fut, _ = self._order_q.get_nowait()
            except queue.Empty:
                break
            fut.cancel()
        if flush_text:
            for text in list(self._show.values()):
                self.textReady.emit(text)
        self._show.clear()
        self._player.stop()
        self._player.setSource(QUrl()) # let the file be deleted
        for path in [self._current, *self._playlist]:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass
        self._playlist.clear()
        self._current = None
        self._busy = False

    # ---------- worker thread: waits for chunks in speaking order ----------
    def _feeder(self):
        while True:
            gen, fut, path = self._order_q.get()
            if fut.cancelled():
                continue
            try:
                fut.result(timeout=20)
            except Exception as e:
                print("[TTS] failed:", e)
                text = self._show.pop(path, None)   # speech failed: show the text anyway
                if text:
                    self.textReady.emit(text)
                continue
            if gen == self._generation:
                self._file_ready.emit(path)
            else:
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ---------- main thread: playback ----------
    def _enqueue(self, path):
        self._playlist.append(path)
        if not self._busy:
            self._play_next()

    def _play_next(self):
        if not self._playlist:
            self._busy = False
            return
        self._busy = True
        self._current = self._playlist.popleft()
        text = self._show.pop(self._current, None)
        self._player.setSource(QUrl.fromLocalFile(self._current))
        self._player.play()
        if text:
            self.textReady.emit(text)               # the text appears as the voice begins

    def _on_status(self, status):
        finished = (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia)
        if status in finished:
            done, self._current = self._current, None
            self._player.setSource(QUrl())          # release the file
            if done:
                try:
                    os.remove(done)                 # delete the mp3 once it's played
                except OSError:
                    pass
            self._play_next()