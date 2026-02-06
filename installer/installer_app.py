from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from installer.installer_core import InstallerCore


class Worker(QThread):
    log_sig = Signal(str)
    done_sig = Signal()

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        self.fn(self.log_sig.emit)
        self.done_sig.emit()


class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qwen3TTS Installer")
        self.resize(900, 650)
        self.core: InstallerCore | None = None
        self.models: list = []

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.pages = [self._page_paths(), self._page_hw(), self._page_components(), self._page_models(), self._page_done()]
        for p in self.pages:
            self.stack.addWidget(p)

    def _next(self):
        idx = self.stack.currentIndex()
        self.stack.setCurrentIndex(min(idx + 1, self.stack.count() - 1))

    def _page_paths(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        self.install_edit = QLineEdit(str(Path.cwd() / "runtime"))
        self.cache_edit = QLineEdit(str(Path.cwd() / "runtime" / "cache"))
        self.temp_edit = QLineEdit(str(Path.cwd() / "runtime" / "_tmp"))

        def add_row(lbl, edit):
            btn = QPushButton("Browse")
            btn.clicked.connect(lambda: self._pick_dir(edit))
            box = QHBoxLayout()
            box.addWidget(edit)
            box.addWidget(btn)
            c = QWidget(); c.setLayout(box)
            form.addRow(lbl, c)

        add_row("Install Root", self.install_edit)
        add_row("Cache Root", self.cache_edit)
        add_row("Temp Root", self.temp_edit)
        lay.addLayout(form)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self._init_core)
        lay.addWidget(next_btn)
        return w

    def _page_hw(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.hw_lbl = QLabel("Hardware not detected yet")
        lay.addWidget(self.hw_lbl)
        btn = QPushButton("Next")
        btn.clicked.connect(self._next)
        lay.addWidget(btn)
        return w

    def _page_components(self):
        w = QWidget(); lay = QVBoxLayout(w)
        self.cb_env = QCheckBox("Create/repair embedded Python environment"); self.cb_env.setChecked(True)
        self.cb_pkg = QCheckBox("Install/repair packages"); self.cb_pkg.setChecked(True)
        self.cb_gpu = QCheckBox("Enable GPU acceleration (if available)"); self.cb_gpu.setChecked(True)
        self.cb_mp3 = QCheckBox("Install MP3 encoder support"); self.cb_mp3.setChecked(True)
        self.cb_flash = QCheckBox("Optional: attempt flash-attn")
        for cb in [self.cb_env, self.cb_pkg, self.cb_gpu, self.cb_mp3, self.cb_flash]:
            lay.addWidget(cb)
        self.inst_log = QTextEdit(); self.inst_log.setReadOnly(True)
        lay.addWidget(self.inst_log)
        run_btn = QPushButton("Install")
        run_btn.clicked.connect(self._run_install)
        lay.addWidget(run_btn)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self._load_models)
        lay.addWidget(next_btn)
        return w

    def _page_models(self):
        w = QWidget(); lay = QVBoxLayout(w)
        self.model_list = QListWidget()
        self.model_list.setSelectionMode(QListWidget.MultiSelection)
        lay.addWidget(self.model_list)
        self.model_log = QTextEdit(); self.model_log.setReadOnly(True)
        lay.addWidget(self.model_log)
        dl = QPushButton("Download")
        dl.clicked.connect(self._download_selected)
        lay.addWidget(dl)
        skip = QPushButton("Skip for now")
        skip.clicked.connect(self._next)
        lay.addWidget(skip)
        return w

    def _page_done(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Done. You can now launch Studio."))
        btn = QPushButton("Launch Studio")
        btn.clicked.connect(lambda: QMessageBox.information(self, "Info", "Build Studio executable and launch it."))
        lay.addWidget(btn)
        return w

    def _pick_dir(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text())
        if path:
            edit.setText(path)

    def _init_core(self):
        self.core = InstallerCore(Path(self.install_edit.text()), Path(self.cache_edit.text()), Path(self.temp_edit.text()))
        hw = self.core.detect_hw()
        self.hw_lbl.setText(f"CPU: {hw.cpu}\nRAM: {hw.ram_gb} GB\nGPU: {hw.gpu}\nVRAM: {hw.vram_gb} GB")
        if hw.vram_gb and hw.vram_gb < 10:
            QMessageBox.warning(self, "VRAM warning", "1.7B models may be too heavy; consider 0.6B.")
        self._next()

    def _run_install(self):
        if not self.core:
            return

        def task(log):
            self.core.install_env(use_gpu=self.cb_gpu.isChecked(), use_flash=self.cb_flash.isChecked(), progress=log)

        self.worker = Worker(task)
        self.worker.log_sig.connect(self.inst_log.append)
        self.worker.start()

    def _load_models(self):
        if not self.core:
            return
        self.models = self.core.list_models()
        self.model_list.clear()
        for m in self.models:
            item = QListWidgetItem(f"{m.family} | {m.size_hint} | {m.repo_id}")
            item.setData(32, m.repo_id)
            self.model_list.addItem(item)
        self._next()

    def _download_selected(self):
        if not self.core:
            return
        repos = [it.data(32) for it in self.model_list.selectedItems()]
        if not repos:
            return

        def task(log):
            self.core.download_models(repos, progress=log)

        self.worker = Worker(task)
        self.worker.log_sig.connect(self.model_log.append)
        self.worker.done_sig.connect(self._next)
        self.worker.start()


def main() -> int:
    app = QApplication(sys.argv)
    w = InstallerWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
