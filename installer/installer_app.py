from __future__ import annotations

import argparse
import importlib
import faulthandler
import sys
import traceback
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from installer.gui_stream import ensure_streams
from installer.installer_core import InstallerCore
from shared.settings_store import load_json, save_json


def run_smoke_imports() -> int:
    try:
        mod = importlib.import_module("huggingface_hub")
        ver = getattr(mod, "__version__", "unknown")
        print(f"huggingface_hub={ver}")
        return 0
    except Exception as exc:
        print(f"smoke-imports failed: {exc}")
        return 1


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


class RuntimeInstallWorker(QThread):
    sig_log = Signal(str)
    sig_stage = Signal(str, str, int, int, str)
    sig_done = Signal(bool, str)

    def __init__(self, core: InstallerCore, cache: Path, temp: Path, enable_gpu: bool):
        super().__init__()
        self.core = core
        self.cache = cache
        self.temp = temp
        self.enable_gpu = enable_gpu

    def run(self):
        try:
            self.core.setup_micromamba_env(self.cache, self.temp, self.enable_gpu, self.sig_log.emit, self.sig_stage.emit)
            self.sig_done.emit(True, "Runtime install completed")
        except Exception as exc:
            self.sig_done.emit(False, str(exc))


class VerifyWorker(QThread):
    sig_log = Signal(str)
    sig_done = Signal(bool, str)

    def __init__(self, core: InstallerCore, cache: Path, temp: Path):
        super().__init__()
        self.core = core
        self.cache = cache
        self.temp = temp

    def run(self):
        try:
            ok = self.core.verify_runtime_installation(self.cache, self.temp, self.sig_log.emit)
            self.sig_done.emit(ok, "Verified" if ok else "Verification failed")
        except Exception as exc:
            self.sig_done.emit(False, str(exc))


class ModelDownloadWorker(QThread):
    sig_log = Signal(str)
    sig_model_progress = Signal(str, int, int, str)
    sig_done = Signal(bool, str)

    def __init__(self, core: InstallerCore, model_ids: list[str], cancel_event: Event):
        super().__init__()
        self.core = core
        self.model_ids = model_ids
        self.cancel_event = cancel_event

    def run(self):
        try:
            self.core.download_selected_models(self.model_ids, self.sig_log.emit, self.sig_model_progress.emit, self.cancel_event)
            self.sig_done.emit(True, "Done")
        except Exception as exc:
            self.sig_done.emit(False, str(exc))


class InstallerWindow(QMainWindow):
    def __init__(self, debug: bool = False):
        super().__init__()
        self.debug = debug
        self.setWindowTitle("Qwen3TTS Installer")
        self.resize(1040, 760)

        self.app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
        self.path_settings_path = self.app_dir / "installer_settings.json"
        self.path_settings = load_json(self.path_settings_path, default={})

        self.install_root = Path(self.path_settings.get("install_root") or self.app_dir)
        self.core = InstallerCore(self.install_root)
        self.model_cancel = Event()
        self.model_states: dict[str, dict] = {}
        self.runtime_verified = False

        self.stack = QStackedWidget()
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)

        root = QWidget(); lay = QVBoxLayout(root)
        lay.addWidget(self.stack, 4)
        lay.addWidget(QLabel("Status log"))
        lay.addWidget(self.log, 2)
        self.setCentralWidget(root)

        self._screen_python(); self._screen_paths(); self._screen_hw(); self._screen_components(); self._screen_models(); self._screen_done()
        self.detect_python()

        self.crash_log_path = self.core.logs_dir / "installer_runtime_page.log"
        self._fault_file = self.crash_log_path.open("a", encoding="utf-8")
        faulthandler.enable(file=self._fault_file, all_threads=True)

    def install_exception_hooks(self) -> None:
        def _excepthook(exc_type, exc, tb):
            text = "".join(traceback.format_exception(exc_type, exc, tb))
            with self.crash_log_path.open("a", encoding="utf-8") as f:
                f.write(text + "\n")
            QMessageBox.critical(self, "Fatal error", f"Unexpected error. See log:\n{self.crash_log_path}")
        sys.excepthook = _excepthook

    def append_log(self, text: str):
        if text:
            t = str(text).strip()
            if t:
                self.log.appendPlainText(t)
                self.core.log(t)
                with self.crash_log_path.open("a", encoding="utf-8") as f:
                    f.write(t + "\n")
                    f.flush()

    def _pick_dir(self, edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select folder", edit.text() or str(Path.home()))
        if folder:
            edit.setText(folder)

    def _screen_python(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.py_label = QLabel("Detecting Python 3.11+")
        self.py_folder = QLineEdit(str(self.install_root / "python"))
        btn_pick = QPushButton("Python Install Folder"); btn_pick.clicked.connect(lambda: self._pick_dir(self.py_folder))
        btn_detect = QPushButton("Detect"); btn_detect.clicked.connect(self.detect_python)
        btn_install = QPushButton("Install Python"); btn_install.clicked.connect(self.install_python)
        btn_next = QPushButton("Next"); btn_next.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        for wdg in [self.py_label, self.py_folder, btn_pick, btn_detect, btn_install, btn_next]:
            l.addWidget(wdg)
        self.stack.addWidget(w)

    def detect_python(self):
        cmd, version = self.core.detect_python()
        self.py_label.setText(f"Detected: {version} via {cmd}" if version else "Python 3.11+ not found")

    def install_python(self):
        target = Path(self.py_folder.text())
        temp = Path(self.temp_edit.text() if hasattr(self, "temp_edit") else str(self.install_root / "_tmp"))
        temp.mkdir(parents=True, exist_ok=True)
        self._run_bg(lambda cb: self.core.install_python_per_user(target, temp, cb))

    def _screen_paths(self):
        w = QWidget(); form = QFormLayout(w)
        def_install = self.path_settings.get("install_root", str(self.install_root))
        def_cache = self.path_settings.get("cache_root", str(self.install_root / "cache"))
        def_temp = self.path_settings.get("temp_root", str(self.install_root / "_tmp"))
        self.install_edit = QLineEdit(def_install)
        self.cache_edit = QLineEdit(def_cache)
        self.temp_edit = QLineEdit(def_temp)

        for edit in [self.install_edit, self.cache_edit, self.temp_edit]:
            row = QHBoxLayout(); row.addWidget(edit); b = QPushButton("Browse"); b.clicked.connect(lambda _, e=edit: self._pick_dir(e)); row.addWidget(b)
            box = QWidget(); box.setLayout(row)
            label = "Install Root" if edit is self.install_edit else "Cache Root" if edit is self.cache_edit else "Temp Root"
            form.addRow(label, box)
        next_btn = QPushButton("Next"); next_btn.clicked.connect(self._to_hw); form.addRow(next_btn)
        self.stack.addWidget(w)

    def _to_hw(self):
        self.install_root = Path(self.install_edit.text())
        cache_root = Path(self.cache_edit.text())
        temp_root = Path(self.temp_edit.text())
        for path in [self.install_root, cache_root, temp_root]:
            path.mkdir(parents=True, exist_ok=True)
        self.path_settings.update({"install_root": str(self.install_root), "cache_root": str(cache_root), "temp_root": str(temp_root)})
        save_json(self.path_settings_path, self.path_settings)

        self.core = InstallerCore(self.install_root)
        self.crash_log_path = self.core.logs_dir / "installer_runtime_page.log"
        self.stack.setCurrentIndex(2)
        self.hw_summary.setText("Click Refresh")

    def _screen_hw(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.hw_summary = QLabel(); refresh = QPushButton("Refresh"); refresh.clicked.connect(self.load_hw)
        next_btn = QPushButton("Next"); next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        l.addWidget(self.hw_summary); l.addWidget(refresh); l.addWidget(next_btn)
        self.stack.addWidget(w)

    def load_hw(self):
        hw = self.core.get_hardware()
        self.hw_summary.setText(f"CPU: {hw.cpu}\nRAM: {hw.ram_gb} GB\nGPU: {hw.gpu_name}\nVRAM: {hw.vram_gb} GB\nSuggestion: {hw.cuda_hint}")

    def _screen_components(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.cb_gpu = QCheckBox("Enable GPU acceleration if available"); self.cb_gpu.setChecked(True)
        self.install_btn = QPushButton("Install runtime")
        self.install_btn.clicked.connect(self.install_components)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_install_components)
        self.verify_btn = QPushButton("Verify / Check installation")
        self.verify_btn.clicked.connect(self.verify_components)
        self.runtime_status = QLabel("Not installed")
        self.next_btn = QPushButton("Next")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.stage_rows = {}
        grid = QGridLayout()
        for row, (sid, title) in enumerate([
            ("B1", "micromamba_bootstrap"), ("B2", "env_create_or_update"), ("B3", "cache_temp_redirects"),
            ("C1", "pip_bootstrap"), ("C2", "runtime_requirements_install"), ("C3", "smoke_imports"),
            ("E1", "write_manifest"), ("E2", "finalize"),
        ]):
            p = QProgressBar(); p.setRange(0, 100)
            lbl = QLabel("Pending")
            grid.addWidget(QLabel(title), row, 0); grid.addWidget(p, row, 1); grid.addWidget(lbl, row, 2)
            self.stage_rows[sid] = (p, lbl)
        l.addLayout(grid)
        row_btns = QHBoxLayout(); row_btns.addWidget(self.install_btn); row_btns.addWidget(self.cancel_btn); row_btns.addWidget(self.verify_btn); row_btns.addWidget(self.next_btn)
        l.addWidget(self.cb_gpu); l.addLayout(row_btns); l.addWidget(self.runtime_status)
        if self.debug:
            l.addWidget(QLabel(f"Diagnostics: install={self.install_root} cache={self.cache_edit.text()} temp={self.temp_edit.text()}"))
        self.stack.addWidget(w)

    def _set_stage(self, stage_id: str, status: str, current: int, total: int, message: str):
        if stage_id not in self.stage_rows:
            return
        bar, lbl = self.stage_rows[stage_id]
        bar.setMaximum(max(total, 1)); bar.setValue(current)
        lbl.setText(f"{status}: {message}" if message else status)

    def _set_runtime_busy(self, busy: bool):
        self.install_btn.setEnabled(not busy)
        self.verify_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        if busy:
            self.next_btn.setEnabled(False)

    def install_components(self):
        cache = Path(self.cache_edit.text()); temp = Path(self.temp_edit.text())
        self.runtime_verified = False
        self.runtime_status.setText("Installing...")
        self._set_runtime_busy(True)
        faulthandler.dump_traceback_later(60, repeat=True, file=self._fault_file)

        self.runtime_worker = RuntimeInstallWorker(self.core, cache, temp, self.cb_gpu.isChecked())
        self.runtime_worker.sig_log.connect(self.append_log, Qt.QueuedConnection)
        self.runtime_worker.sig_stage.connect(self._set_stage, Qt.QueuedConnection)
        self.runtime_worker.sig_done.connect(self._on_runtime_done, Qt.QueuedConnection)
        self.runtime_worker.start()

    def cancel_install_components(self):
        self.core.request_cancel()
        self.runtime_status.setText("Cancelling...")

    def _on_runtime_done(self, ok: bool, text: str):
        faulthandler.cancel_dump_traceback_later()
        self._set_runtime_busy(False)
        if ok:
            self.runtime_verified = True
            self.runtime_status.setText("Installed")
            self.next_btn.setEnabled(True)
            self.append_log(text)
        else:
            self.runtime_status.setText("Cancelled by user" if "Cancelled" in text else "Install failed")
            self.append_log(f"ERROR: {text}")
            QMessageBox.critical(self, "Runtime install error", f"{text}\n\nLog: {self.crash_log_path}")

    def verify_components(self):
        cache = Path(self.cache_edit.text()); temp = Path(self.temp_edit.text())
        self.runtime_status.setText("Verifying...")
        self._set_runtime_busy(True)
        self.verify_worker = VerifyWorker(self.core, cache, temp)
        self.verify_worker.sig_log.connect(self.append_log, Qt.QueuedConnection)
        self.verify_worker.sig_done.connect(self._on_verify_done, Qt.QueuedConnection)
        self.verify_worker.start()

    def _on_verify_done(self, ok: bool, text: str):
        self._set_runtime_busy(False)
        self.runtime_verified = ok
        self.runtime_status.setText("Verified" if ok else "Verification failed")
        self.next_btn.setEnabled(ok)
        if not ok:
            QMessageBox.warning(self, "Verification", f"Verification failed. Re-run Install.\n\nLog: {self.crash_log_path}")

    def _screen_models(self):
        w = QWidget(); l = QVBoxLayout(w)
        self.model_overall = QProgressBar(); self.model_overall.setRange(0, 100); self.model_overall.setFormat("Overall %p%")
        self.model_list = QListWidget()
        self.model_detail = QLabel("No models selected")
        load_btn = QPushButton("Load models from Hugging Face"); load_btn.clicked.connect(self.load_models)
        self.dl_btn = QPushButton("Download selected"); self.dl_btn.clicked.connect(self.download_models)
        self.skip_btn = QPushButton("Skip for now"); self.skip_btn.clicked.connect(self.on_right_button)
        l.addWidget(load_btn); l.addWidget(self.model_list); l.addWidget(self.model_overall); l.addWidget(self.model_detail)
        r = QHBoxLayout(); r.addWidget(self.dl_btn); r.addWidget(self.skip_btn); l.addLayout(r)
        self.stack.addWidget(w)

    def _selected_models(self) -> list[str]:
        return [self.model_list.item(i).text() for i in range(self.model_list.count()) if self.model_list.item(i).checkState() == Qt.Checked]

    def _missing_selected_models(self) -> list[str]:
        return [mid for mid in self._selected_models() if self.model_states.get(mid, {}).get("status") not in {"Installed"}]

    def _has_failed_selected(self) -> bool:
        return any(self.model_states.get(mid, {}).get("status") == "Failed" for mid in self._selected_models())

    def _is_downloading(self) -> bool:
        return hasattr(self, "model_worker") and self.model_worker.isRunning()

    def refresh_model_buttons(self):
        downloading = self._is_downloading()
        selected = self._selected_models()
        missing = self._missing_selected_models()
        all_selected_installed = bool(selected) and len(missing) == 0

        self.dl_btn.setEnabled((not downloading) and bool(selected) and bool(missing))
        self.model_list.setEnabled(not downloading)

        if downloading:
            self.skip_btn.setText("Cancel downloads")
            self.skip_btn.setEnabled(True)
        else:
            if all_selected_installed and not self._has_failed_selected():
                self.skip_btn.setText("Continue")
            elif not selected:
                self.skip_btn.setText("Skip for now")
            elif self._has_failed_selected():
                self.skip_btn.setText("Skip for now")
            elif missing:
                self.skip_btn.setText("Skip for now")
            else:
                self.skip_btn.setText("Continue")
            self.skip_btn.setEnabled(True)

    def on_right_button(self):
        if self._is_downloading():
            self.model_cancel.set()
            self.skip_btn.setEnabled(False)
            self.model_detail.setText("Cancelling downloads...")
            return
        if self.skip_btn.text() == "Continue" or self.skip_btn.text() == "Skip for now":
            self.stack.setCurrentIndex(5)

    def load_models(self):
        self.model_list.clear(); self.model_states.clear()
        installed = set(self.core.installed_model_ids())
        for model in self.core.get_models():
            item = QListWidgetItem(model); item.setCheckState(Qt.Unchecked)
            self.model_list.addItem(item)
            state = "Installed" if model in installed else "NotInstalled"
            self.model_states[model] = {"status": state, "bytes_done": 0, "bytes_total": 1, "error_message": ""}
        self.model_list.itemChanged.connect(lambda *_: self.refresh_model_buttons())
        self.model_detail.setText("Models loaded")
        self._update_overall_model_progress()
        self.refresh_model_buttons()

    def _update_overall_model_progress(self):
        selected = self._selected_models()
        if not selected:
            self.model_overall.setValue(0)
            return
        total_bytes = sum(max(int(self.model_states.get(mid, {}).get("bytes_total", 1)), 1) for mid in selected)
        done_bytes = sum(int(self.model_states.get(mid, {}).get("bytes_done", 0)) for mid in selected)
        percent = int((done_bytes * 100) / total_bytes) if total_bytes else 0
        self.model_overall.setValue(max(0, min(percent, 100)))

    def _on_model_progress(self, model_id: str, current: int, total: int, message: str):
        st = self.model_states.setdefault(model_id, {"status": "NotInstalled", "bytes_done": 0, "bytes_total": 1, "error_message": ""})
        st["bytes_done"] = max(int(current), 0)
        st["bytes_total"] = max(int(total), 1)
        if message == "Done":
            st["status"] = "Installed"
            st["bytes_done"] = st["bytes_total"]
        elif "Cancelled" in message:
            st["status"] = "Cancelled"
        elif "ERROR" in message:
            st["status"] = "Failed"; st["error_message"] = message
        else:
            st["status"] = "Downloading"
        self._update_overall_model_progress()
        self.model_detail.setText(f"{model_id}: {st['status']} ({st['bytes_done']} / {st['bytes_total']} bytes)")
        self.refresh_model_buttons()

    def download_models(self):
        models = self._missing_selected_models()
        if not models:
            QMessageBox.information(self, "Models", "Select at least one missing model")
            return
        self.model_cancel.clear()
        self.model_detail.setText("Downloading selected models...")
        self.refresh_model_buttons()

        self.model_worker = ModelDownloadWorker(self.core, models, self.model_cancel)
        self.model_worker.sig_log.connect(self.append_log, Qt.QueuedConnection)
        self.model_worker.sig_model_progress.connect(self._on_model_progress, Qt.QueuedConnection)
        self.model_worker.sig_done.connect(self._on_models_done, Qt.QueuedConnection)
        self.model_worker.start()

    def _on_models_done(self, ok: bool, text: str):
        if self.model_cancel.is_set():
            for mid in self._selected_models():
                if self.model_states.get(mid, {}).get("status") == "Downloading":
                    self.model_states[mid]["status"] = "Cancelled"
            self.model_detail.setText("Downloads cancelled")
        elif ok:
            self.model_detail.setText("Downloads finished")
        else:
            self.model_detail.setText(f"Download error: {text}")
        self.append_log(text if ok else f"ERROR: {text}")
        self.refresh_model_buttons()

    def _screen_done(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(QLabel("Installation complete. You can now launch Studio."))
        btn_exit = QPushButton("Exit"); btn_exit.clicked.connect(self.close)
        l.addWidget(btn_exit)
        self.stack.addWidget(w)

    def _run_bg(self, fn):
        self.worker = Worker(fn)
        self.worker.progress.connect(self.append_log, Qt.QueuedConnection)
        self.worker.done.connect(self._on_done, Qt.QueuedConnection)
        self.worker.start()

    def _on_done(self, ok: bool, text: str):
        self.append_log(text if ok else f"ERROR: {text}")
        if not ok:
            QMessageBox.critical(self, "Error", text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--smoke-imports", action="store_true")
    args = parser.parse_args()
    if args.smoke_imports:
        return run_smoke_imports()
    stream = ensure_streams()
    app = QApplication(sys.argv)
    win = InstallerWindow(debug=args.debug)
    win.install_exception_hooks()
    stream.set_callback(lambda msg: win.append_log(msg) if hasattr(win, "append_log") else None)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
