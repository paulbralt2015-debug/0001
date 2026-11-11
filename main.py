import os, sys, locale, tempfile
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
os.environ["PATH"] = str(BASE) + os.pathsep + os.environ.get("PATH", "")
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(str(BASE))

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)
locale.setlocale(locale.LC_NUMERIC, "C")
import mpv
from ac3.pipeline import render

MODES = {"Stéréo (LoRo)": "loro", "Stéréo Dolby Surround (LtRt)": "ltrt", "5.1": "5.1", "Mono": "mono"}
DRCS = {"Compression standard": "dynrng", "Compression forte": "compr", "Aucune": "none"}


class Worker(QThread):
    progress, done, failed = Signal(int), Signal(str), Signal(str)
    def __init__(self, path, out, kw):
        super().__init__(); self.path, self.out, self.kw = path, out, kw
    def run(self):
        try: self.done.emit(render(self.path, self.out, progress=self.progress.emit, **self.kw))
        except Exception as e: self.failed.emit(str(e))


class Win(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lecteur Dolby Digital (décodeur AC-3 intégré)"); self.resize(1050, 680)
        self.path = self.key = self.ext_id = self.orig_aid = None; self.n = 0
        self.video = QWidget(); self.video.setStyleSheet("background:black"); self.video.setAttribute(Qt.WA_NativeWindow)
        self.p = mpv.MPV(wid=str(int(self.video.winId())), input_default_bindings=False, keep_open="yes", ytdl=False)
        bo, bp = QPushButton("Ouvrir…"), QPushButton("Lecture / Pause")
        self.chk = QCheckBox("Décodeur Dolby Digital")
        self.mode, self.drc = QComboBox(), QComboBox()
        self.mode.addItems(MODES); self.drc.addItems(DRCS)
        self.dn = QCheckBox("Dialnorm"); self.dn.setChecked(True)
        self.tgt = QSpinBox(); self.tgt.setRange(-40, -10); self.tgt.setValue(-27); self.tgt.setSuffix(" dBFS")
        self.bar, self.lbl = QProgressBar(), QLabel(""); self.bar.setVisible(False)
        self.seek = QSlider(Qt.Horizontal); self.seek.setRange(0, 1000)
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(80); self.vol.setMaximumWidth(110)
        r1, r2 = QHBoxLayout(), QHBoxLayout()
        for w in (bo, bp, self.chk, self.mode, self.drc, self.dn, self.tgt): r1.addWidget(w)
        for w in (self.bar, self.lbl, QLabel("Vol."), self.vol): r2.addWidget(w)
        lay = QVBoxLayout(self)
        for x in (self.video, self.seek): lay.addWidget(x, 1 if x is self.video else 0)
        lay.addLayout(r1); lay.addLayout(r2)
        bo.clicked.connect(self.open_file)
        bp.clicked.connect(lambda: setattr(self.p, "pause", not self.p.pause))
        self.chk.toggled.connect(self.refresh)
        for w in (self.mode, self.drc): w.currentIndexChanged.connect(self.refresh)
        self.dn.toggled.connect(self.refresh); self.tgt.editingFinished.connect(self.refresh)
        self.seek.sliderMoved.connect(lambda v: self.p.duration and self.p.seek(v / 1000 * self.p.duration, "absolute"))
        self.vol.valueChanged.connect(lambda v: setattr(self.p, "volume", v)); self.p.volume = 80
        t = QTimer(self); t.timeout.connect(self.tick); t.start(250)

    def open_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Ouvrir une vidéo")
        if not f: return
        self.path, self.key, self.ext_id = f, None, None
        self.chk.blockSignals(True); self.chk.setChecked(False); self.chk.blockSignals(False)
        self.p.play(f); self.p.wait_until_playing()
        tr = [t for t in self.p.track_list if t["type"] == "audio"]
        self.orig_aid = tr[0]["id"] if tr else None

    def opts(self):
        return dict(mode=MODES[self.mode.currentText()], drc=DRCS[self.drc.currentText()],
                    dialnorm=self.dn.isChecked(), target=float(self.tgt.value()))

    def refresh(self, *_):
        if not self.path: return
        if not self.chk.isChecked():
            if self.orig_aid is not None: self.p.aid = self.orig_aid
            return
        kw = self.opts(); key = tuple(sorted(kw.items()))
        if key == self.key: return
        if hasattr(self, "w") and self.w.isRunning(): return
        self.pending = key; self.n += 1
        out = str(Path(tempfile.gettempdir()) / f"ac3_{os.getpid()}_{self.n}.wav")
        self.bar.setValue(0); self.bar.setVisible(True); self.lbl.setText("Décodage Dolby Digital…")
        self.w = Worker(self.path, out, kw)
        self.w.progress.connect(self.bar.setValue); self.w.done.connect(self.ready); self.w.failed.connect(self.fail)
        self.w.start()

    def ready(self, out):
        self.key = self.pending
        old = self.ext_id
        self.p.command("audio-add", out, "select")
        ext = [t["id"] for t in self.p.track_list if t["type"] == "audio" and t.get("external")]
        self.ext_id = ext[-1] if ext else None
        if old is not None:
            try: self.p.command("audio-remove", old)
            except Exception: pass
        self.bar.setVisible(False); self.lbl.setText("Décodeur AC-3 actif")

    def fail(self, msg):
        self.bar.setVisible(False); self.lbl.setText("Erreur : " + msg)
        self.chk.blockSignals(True); self.chk.setChecked(False); self.chk.blockSignals(False)

    def tick(self):
        d, t = self.p.duration, self.p.time_pos
        if d and t is not None and not self.seek.isSliderDown(): self.seek.setValue(int(t / d * 1000))

    def closeEvent(self, e):
        self.p.terminate(); super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv); w = Win(); w.show(); sys.exit(app.exec())
