from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget, QCheckBox

from installer.uninstall_core import uninstall_from_manifest


class UninstallWindow(QMainWindow):
    def __init__(self, manifest_path: Path | None = None, dry_run_default: bool = True):
        super().__init__()
        self.setWindowTitle("Qwen3TTS Uninstaller")
        self.resize(900, 600)

        root = QWidget(); lay = QVBoxLayout(root)
        row = QHBoxLayout()
        self.path_edit = QLineEdit(str(manifest_path or Path.cwd() / "install_manifest.json"))
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.browse)
        row.addWidget(QLabel("Manifest")); row.addWidget(self.path_edit); row.addWidget(btn_browse)
        lay.addLayout(row)

        self.cb_dry = QCheckBox("Dry run (no deletion)"); self.cb_dry.setChecked(dry_run_default)
        lay.addWidget(self.cb_dry)

        row2 = QHBoxLayout()
        btn_preview = QPushButton("Preview")
        btn_preview.clicked.connect(self.preview)
        btn_uninstall = QPushButton("Uninstall")
        btn_uninstall.clicked.connect(self.uninstall)
        row2.addWidget(btn_preview); row2.addWidget(btn_uninstall)
        lay.addLayout(row2)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        lay.addWidget(self.log)
        self.setCentralWidget(root)

    def browse(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select manifest", self.path_edit.text(), "JSON (*.json)")
        if f:
            self.path_edit.setText(f)

    def _run(self, dry: bool):
        mp = Path(self.path_edit.text())
        if not mp.exists():
            QMessageBox.critical(self, "Error", f"Manifest not found: {mp}")
            return
        logs = uninstall_from_manifest(mp, dry_run=dry)
        self.log.clear()
        for lvl, msg in logs:
            self.log.appendPlainText(f"[{lvl}] {msg}")

    def preview(self):
        self._run(True)

    def uninstall(self):
        if QMessageBox.question(self, "Confirm", "Proceed with uninstall?") != QMessageBox.StandardButton.Yes:
            return
        self._run(self.cb_dry.isChecked())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    w = UninstallWindow(Path(args.manifest) if args.manifest else None, dry_run_default=args.dry_run)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
