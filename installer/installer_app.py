from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
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
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from installer.installer_core import InstallerCore


class Worker(QThread):
    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.fn(self.progress.emit)
            self.done.emit(True, "Done")
        except Exception as e:
            self.done.emit(False, str(e))


class InstallerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qwen3TTS Installer")
        self.resize(980, 680)

        self.install_root = Path.cwd()
        self.core = InstallerCore(self.install_root)

        self.stack = QStackedWidget()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.addWidget(self.stack, 3)
        lay.addWidget(QLabel("Status log"))
        lay.addWidget(self.log, 2)
        self.setCentralWidget(root)

        self._screen_python()
        self._screen_paths()
        self._screen_hw()
        self._screen_components()
        self._screen_models()
        self._screen_done()

    def append_log(self, text: str):
        self.log.appendPlainText(text)
        self.core.log(text)

    def _pick_dir(self, edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select folder", edit.text() or str(Path.home()))
        if folder:
            edit.setText(folder)

    def _screen_python(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.py_label = QLabel("Detecting Python 3.11+")
        self.py_folder = QLineEdit(str(self.install_root / "python"))
        btn_pick = QPushButton("Python Install Folder")
        btn_pick.clicked.connect(lambda: self._pick_dir(self.py_folder))
        btn_detect = QPushButton("Detect")
        btn_detect.clicked.connect(self.detect_python)
        btn_install = QPushButton("Install Python")
        btn_install.clicked.connect(self.install_python)
        btn_next = QPushButton("Next")
        btn_next.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        l.addWidget(self.py_label); l.addWidget(self.py_folder); l.addWidget(btn_pick)
        l.addWidget(btn_detect); l.addWidget(btn_install); l.addWidget(btn_next)
        self.stack.addWidget(w)
        self.detect_python()

    def detect_python(self):
        cmd, version = self.core.detect_python()
        self.py_label.setText(f"Detected: {version} via {cmd}" if version else "Python 3.11+ not found")

    def install_python(self):
        target = Path(self.py_folder.text())
        temp = Path(self.temp_edit.text() if hasattr(self, "temp_edit") else str(self.install_root / "_tmp"))
        temp.mkdir(parents=True, exist_ok=True)

        def run(cb):
            self.core.install_python_per_user(target, temp, cb)

        self._run_bg(run)

    def _screen_paths(self):
        w = QWidget(); form = QFormLayout(w)
        self.install_edit = QLineEdit(str(self.install_root))
        self.cache_edit = QLineEdit(str(self.install_root / "cache"))
        self.temp_edit = QLineEdit(str(self.install_root / "_tmp"))
        for edit in [self.install_edit, self.cache_edit, self.temp_edit]:
            row = QHBoxLayout(); row.addWidget(edit)
            b = QPushButton("Browse")
            b.clicked.connect(lambda _, e=edit: self._pick_dir(e))
            row.addWidget(b)
            box = QWidget(); box.setLayout(row)
            label = "Install Root" if edit is self.install_edit else "Cache Root" if edit is self.cache_edit else "Temp Root"
            form.addRow(label, box)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(self._to_hw)
        form.addRow(next_btn)
        self.stack.addWidget(w)

    def _to_hw(self):
        self.install_root = Path(self.install_edit.text())
        self.core = InstallerCore(self.install_root)
        self.stack.setCurrentIndex(2)
        self.hw_summary.setText("Click Refresh")

    def _screen_hw(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.hw_summary = QLabel()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.load_hw)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        l.addWidget(self.hw_summary); l.addWidget(refresh); l.addWidget(next_btn)
        self.stack.addWidget(w)

    def load_hw(self):
        hw = self.core.get_hardware()
        warn = "\nWarning: 1.7B may be too heavy on VRAM" if hw.vram_gb and hw.vram_gb < 10 else ""
        if hw.gpu_vendor == "NVIDIA" and hw.vram_source == "wmi" and abs(hw.vram_gb - 4.0) < 0.2 and "RTX" in hw.gpu_name.upper():
            warn += "\nWarning: WMI may cap VRAM at 4GB; switching to nvidia-smi/NVML/DXGI is recommended."
        self.hw_summary.setText(
            f"CPU: {hw.cpu}\n"
            f"RAM: {hw.ram_gb} GB\n"
            f"GPU: {hw.gpu_name} (index {hw.gpu_index})\n"
            f"VRAM: {hw.vram_gb} GB ({hw.vram_bytes} bytes)\n"
            f"VRAM Source: {hw.vram_source}\n"
            f"Suggestion: {hw.cuda_hint}{warn}"
        )
        self.append_log(
            f"Hardware detection: GPU={hw.gpu_name}, vendor={hw.gpu_vendor}, "
            f"VRAM={hw.vram_gb} GB, source={hw.vram_source}, index={hw.gpu_index}"
        )

    def _screen_components(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.cb_env = QCheckBox("Create/repair embedded Python environment"); self.cb_env.setChecked(True)
        self.cb_pkg = QCheckBox("Install/repair packages"); self.cb_pkg.setChecked(True)
        self.cb_gpu = QCheckBox("Enable GPU acceleration if available"); self.cb_gpu.setChecked(True)
        self.cb_mp3 = QCheckBox("Install MP3 encoder support"); self.cb_mp3.setChecked(True)
        self.cb_flash = QCheckBox("Attempt flash-attn (optional)")
        install_btn = QPushButton("Install")
        install_btn.clicked.connect(self.install_components)
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        for c in [self.cb_env, self.cb_pkg, self.cb_gpu, self.cb_mp3, self.cb_flash, install_btn, next_btn]:
            l.addWidget(c)
        self.stack.addWidget(w)

    def install_components(self):
        cache = Path(self.cache_edit.text())
        temp = Path(self.temp_edit.text())

        def run(cb):
            env = self.core.setup_micromamba_env(cache, temp, self.cb_gpu.isChecked(), cb)
            cb(f"Environment ready: {env}")

        self._run_bg(run)

    def _screen_models(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.model_list = QListWidget()
        load_btn = QPushButton("Load models from Hugging Face")
        load_btn.clicked.connect(self.load_models)
        dl_btn = QPushButton("Download selected")
        dl_btn.clicked.connect(self.download_models)
        skip_btn = QPushButton("Skip for now")
        skip_btn.clicked.connect(lambda: self.stack.setCurrentIndex(5))
        l.addWidget(load_btn); l.addWidget(self.model_list); l.addWidget(dl_btn); l.addWidget(skip_btn)
        self.stack.addWidget(w)

    def load_models(self):
        self.model_list.clear()
        for model in self.core.get_models():
            item = QListWidgetItem(model)
            item.setCheckState(Qt.Unchecked)
            self.model_list.addItem(item)

    def download_models(self):
        models = [self.model_list.item(i).text() for i in range(self.model_list.count()) if self.model_list.item(i).checkState() == Qt.Checked]
        if not models:
            QMessageBox.information(self, "Models", "Select at least one model")
            return

        def run(cb):
            self.core.download_selected_models(models, cb)

        self._run_bg(run)

    def _screen_done(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("Installation complete. You can now launch Studio."))
        self.stack.addWidget(w)

    def _run_bg(self, fn):
        self.worker = Worker(fn)
        self.worker.progress.connect(self.append_log)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_done(self, ok: bool, text: str):
        if ok:
            self.append_log(text)
        else:
            self.append_log(f"ERROR: {text}")
            QMessageBox.critical(self, "Error", text)


def main() -> int:
    app = QApplication(sys.argv)
    win = InstallerWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
