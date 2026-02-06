from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from shared.settings_store import SettingsStore
from studio.studio_core import StudioCore

TOOLTIPS = {
    "Book file": "Файл книги для озвучки: .fb2 или .txt. Для .fb2 будет извлечён основной текст.",
    "Chunk length (chars)": "Целевая длина текстового куска. Меньше — стабильнее и меньше артефактов, но больше файлов/стыков.",
    "Device": "Куда считать: cuda:0 (видеокарта) быстрее, cpu (процессор) медленнее, но стабильнее при проблемах с GPU.",
    "DType": "Точность вычислений. bf16 обычно стабильнее на новых RTX; fp16 быстрее, но иногда даёт ошибки; fp32 медленнее, но максимально совместимо.",
    "Instruction": "Текстовая инструкция стилю/интонации. Может улучшать или ломать чтение — использовать аккуратно.",
    "Keep temp folder": "Не удалять временную папку .tmp после завершения (для диагностики). Обычно выключено.",
    "Language": "Язык текста для TTS. Для русских книг обычно Russian даже при редких английских словах.",
    "Max chunk length (chars)": "Жёсткий максимум длины куска. Если текст длиннее — будет принудительно резаться.",
    "Max duration (min)": "Максимальная длительность одного MP3 файла. После достижения — начинается следующий (002.mp3 и т.д.).",
    "Max file size (MB)": "Максимальный размер одного MP3. Когда превышен — следующий файл.",
    "Max new tokens": "Лимит длины генерируемой последовательности. Если слишком мало — обрывы; слишком много — лишнее время/память.",
    "Max spoken chars": "Максимум озвученных символов в одном файле (приблизительно). Удобно для одинаковых по размеру частей.",
    "Model": "Выбор установленной модели Qwen3‑TTS. Разные модели отличаются качеством, скоростью и требованиями к VRAM.",
    "MP3 bitrate (kbps)": "Битрейт MP3. Выше — лучше качество и больше размер. 96–160 kbps обычно ок для речи.",
    "Normalize whitespace": "Очистка текста: лишние пробелы/переводы строк. Обычно лучше включить для книг.",
    "Open Model Manager": "Открыть менеджер моделей: скачать/удалить модели, проверить наличие файлов и кэша.",
    "Output folder": "Папка, куда сохраняются MP3: прямо сюда, без подпапок. Внутри будут только 001.mp3, 002.mp3 и т.д.",
    "Reference audio (WAV)": "Референс‑аудио (WAV) для клонирования голоса (только Base). Желательно 3–15 секунд, без шума и музыки.",
    "Reference text (TXT)": "Текст, который произносится в референс‑аудио (нужен только если выключен x‑vector only).",
    "Repetition penalty": "Штраф за повторы. Увеличение может уменьшить зацикливания, но иногда ухудшает дикцию.",
    "Speaker": "Выбор пресетного голоса (CustomVoice). Разные спикеры по-разному читают и подходят для разных языков.",
    "Split mode": "Как делить результат на файлы: по длительности, по символам, по размеру файла или не делить.",
    "Temperature": "Случайность/вариативность. Ниже — ровнее и предсказуемее; выше — больше эмоций, но больше артефактов.",
    "Top-k": "Ограничение выбора следующего токена топ‑K вариантами. Меньше — стабильнее; больше — свободнее.",
    "Top-p": "Nucleus sampling: выбирает токены, пока сумма вероятностей не достигнет p. Меньше — стабильнее, больше — разнообразнее.",
    "VBR": "Переменный битрейт. Может дать лучшее качество при том же среднем размере, но файлы по весу менее предсказуемы.",
    "X-vector only": "Использовать только голосовую эмбеддингу из WAV. Проще и часто стабильнее. Если выключить — нужен Reference text.",
}


class GenWorker(QThread):
    msg = Signal(str)
    prog = Signal(int, int)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        self.fn(self.msg.emit, self.prog.emit)


class StudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qwen3TTS Studio")
        self.resize(1100, 760)
        base = Path.cwd() / "runtime"
        self.core = StudioCore(base, base / "cache", base / "_tmp")
        self.settings = SettingsStore(base / "studio_settings.json")
        self.cancelled = False
        self._build_ui()
        self._load_settings()
        self._load_models()

    def _build_ui(self):
        c = QWidget(); self.setCentralWidget(c)
        lay = QVBoxLayout(c)
        grid = QGridLayout()

        self.model_combo = QComboBox(); self.model_combo.setToolTip(TOOLTIPS["Model"])
        self.family_combo = QComboBox(); self.family_combo.addItems(["Base", "CustomVoice", "VoiceDesign"])
        self.family_combo.setToolTip("Режим модели: Base (клонирование по референсу), CustomVoice (пресетные голоса), VoiceDesign (голос по текстовому описанию).")
        self.model_mgr_btn = QPushButton("Open Model Manager"); self.model_mgr_btn.setToolTip(TOOLTIPS["Open Model Manager"])
        self.model_mgr_btn.clicked.connect(self._load_models)

        self.book_edit = QLineEdit(); self.book_edit.setToolTip(TOOLTIPS["Book file"])
        self.ref_audio_edit = QLineEdit(); self.ref_audio_edit.setToolTip(TOOLTIPS["Reference audio (WAV)"])
        self.ref_text_edit = QLineEdit(); self.ref_text_edit.setToolTip(TOOLTIPS["Reference text (TXT)"])
        self.output_edit = QLineEdit(); self.output_edit.setToolTip(TOOLTIPS["Output folder"])

        self.split_combo = QComboBox(); self.split_combo.addItems(["By duration", "By spoken characters", "By file size", "No splitting"])
        self.split_combo.setToolTip(TOOLTIPS["Split mode"])
        self.chunk_chars = QLineEdit("1200"); self.chunk_chars.setToolTip(TOOLTIPS["Chunk length (chars)"])
        self.max_chunk_chars = QLineEdit("1600"); self.max_chunk_chars.setToolTip(TOOLTIPS["Max chunk length (chars)"])

        self.device_combo = QComboBox(); self.device_combo.addItems(["cuda:0", "cpu"]); self.device_combo.setToolTip(TOOLTIPS["Device"])
        self.dtype_combo = QComboBox(); self.dtype_combo.addItems(["bf16", "fp16", "fp32"]); self.dtype_combo.setToolTip(TOOLTIPS["DType"])
        self.temp_edit = QLineEdit("0.7"); self.temp_edit.setToolTip(TOOLTIPS["Temperature"])
        self.topk_edit = QLineEdit("50"); self.topk_edit.setToolTip(TOOLTIPS["Top-k"])
        self.topp_edit = QLineEdit("0.95"); self.topp_edit.setToolTip(TOOLTIPS["Top-p"])
        self.rep_edit = QLineEdit("1.1"); self.rep_edit.setToolTip(TOOLTIPS["Repetition penalty"])
        self.max_new_tokens = QLineEdit("2048"); self.max_new_tokens.setToolTip(TOOLTIPS["Max new tokens"])
        self.speaker_edit = QLineEdit("default"); self.speaker_edit.setToolTip(TOOLTIPS["Speaker"])
        self.instruct_edit = QLineEdit(); self.instruct_edit.setToolTip(TOOLTIPS["Instruction"])
        self.xvector = QCheckBox("X-vector only"); self.xvector.setChecked(True); self.xvector.setToolTip(TOOLTIPS["X-vector only"])
        self.keep_temp = QCheckBox("Keep temp folder"); self.keep_temp.setToolTip(TOOLTIPS["Keep temp folder"])
        self.norm_ws = QCheckBox("Normalize whitespace"); self.norm_ws.setChecked(True); self.norm_ws.setToolTip(TOOLTIPS["Normalize whitespace"])
        self.skip_toc = QCheckBox("Skip TOC"); self.skip_toc.setChecked(True); self.skip_toc.setToolTip("Пытаться вырезать оглавление/содержание из FB2 по эвристикам, чтобы оно не попадало в озвучку.")
        self.bitrate = QLineEdit("128"); self.bitrate.setToolTip(TOOLTIPS["MP3 bitrate (kbps)"])
        self.vbr = QCheckBox("VBR"); self.vbr.setToolTip(TOOLTIPS["VBR"])

        rows = [
            ("Model", self.model_combo), ("Family / Mode", self.family_combo), ("Book file", self._picker(self.book_edit)),
            ("Reference audio (WAV)", self._picker(self.ref_audio_edit)), ("Reference text (TXT)", self._picker(self.ref_text_edit)),
            ("Output folder", self._picker(self.output_edit, True)), ("Split mode", self.split_combo),
            ("Chunk length (chars)", self.chunk_chars), ("Max chunk length (chars)", self.max_chunk_chars),
            ("Device", self.device_combo), ("DType", self.dtype_combo), ("Temperature", self.temp_edit),
            ("Top-k", self.topk_edit), ("Top-p", self.topp_edit), ("Repetition penalty", self.rep_edit),
            ("Max new tokens", self.max_new_tokens), ("Speaker", self.speaker_edit), ("Instruction", self.instruct_edit),
            ("MP3 bitrate (kbps)", self.bitrate),
        ]
        r = 0
        for label, widget in rows:
            grid.addWidget(QLabel(label), r, 0)
            grid.addWidget(widget, r, 1)
            r += 1
        for cb in [self.xvector, self.keep_temp, self.norm_ws, self.skip_toc, self.vbr]:
            grid.addWidget(cb, r, 1); r += 1

        lay.addLayout(grid)
        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(lambda: setattr(self, "cancelled", True))
        ctrl.addWidget(self.start_btn); ctrl.addWidget(self.stop_btn); ctrl.addWidget(self.model_mgr_btn)
        lay.addLayout(ctrl)

        self.progress = QProgressBar(); lay.addWidget(self.progress)
        self.log = QTextEdit(); self.log.setReadOnly(True); lay.addWidget(self.log)

    def _picker(self, edit: QLineEdit, directory: bool = False):
        box = QWidget(); h = QHBoxLayout(box); h.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("...")
        btn.clicked.connect(lambda: self._browse(edit, directory))
        h.addWidget(edit); h.addWidget(btn)
        return box

    def _browse(self, edit: QLineEdit, directory: bool = False):
        p = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text()) if directory else QFileDialog.getOpenFileName(self, "Choose file", edit.text())[0]
        if p:
            edit.setText(p)

    def _load_models(self):
        items = self.core.list_installed_models()
        self.model_combo.clear()
        for m in items:
            if m.installed:
                self.model_combo.addItem(f"{m.repo_id} ({m.family}/{m.size_hint})", m.repo_id)

    def _start(self):
        if not self.model_combo.currentData() or not self.book_edit.text() or not self.output_edit.text():
            QMessageBox.warning(self, "Missing", "Model, book file, and output folder are required.")
            return
        self.cancelled = False
        output = Path(self.output_edit.text())
        output.mkdir(parents=True, exist_ok=True)
        params = {
            "family": self.family_combo.currentText(), "device": self.device_combo.currentText(), "dtype": self.dtype_combo.currentText(),
            "temperature": float(self.temp_edit.text()), "top_k": int(self.topk_edit.text()), "top_p": float(self.topp_edit.text()),
            "repetition_penalty": float(self.rep_edit.text()), "max_new_tokens": int(self.max_new_tokens.text()),
            "speaker": self.speaker_edit.text(), "instruct": self.instruct_edit.text(), "x_vector_only_mode": self.xvector.isChecked(),
            "ref_audio": self.ref_audio_edit.text(), "ref_text": self.ref_text_edit.text(), "keep_temp": self.keep_temp.isChecked(),
            "normalize_ws": self.norm_ws.isChecked(), "skip_toc": self.skip_toc.isChecked(), "chunk_chars": int(self.chunk_chars.text()),
            "max_chunk_chars": int(self.max_chunk_chars.text()), "bitrate": int(self.bitrate.text()), "vbr": self.vbr.isChecked(),
        }

        def task(log_emit, prog_emit):
            self.core.generate_book(
                model_id=self.model_combo.currentData(),
                input_book=Path(self.book_edit.text()),
                output_dir=Path(self.output_edit.text()),
                ffmpeg_bin="ffmpeg",
                params=params,
                progress=lambda msg, i, n: (log_emit(msg), prog_emit(i, n)),
                cancelled=lambda: self.cancelled,
            )
            self._save_settings()

        self.worker = GenWorker(task)
        self.worker.msg.connect(self.log.append)
        self.worker.prog.connect(lambda i, n: self.progress.setValue(int(i / max(n, 1) * 100)))
        self.worker.start()

    def _load_settings(self):
        s = self.settings.load()
        self.ref_audio_edit.setText(s.get("ref_audio", ""))
        self.ref_text_edit.setText(s.get("ref_text", ""))
        self.output_edit.setText(s.get("output", ""))

    def _save_settings(self):
        self.settings.save({
            "ref_audio": self.ref_audio_edit.text(),
            "ref_text": self.ref_text_edit.text(),
            "output": self.output_edit.text(),
            "model": self.model_combo.currentData(),
            "chunk_chars": self.chunk_chars.text(),
            "max_chunk_chars": self.max_chunk_chars.text(),
            "device": self.device_combo.currentText(),
            "dtype": self.dtype_combo.currentText(),
            "temperature": self.temp_edit.text(),
            "top_k": self.topk_edit.text(),
            "top_p": self.topp_edit.text(),
            "repetition_penalty": self.rep_edit.text(),
            "max_new_tokens": self.max_new_tokens.text(),
            "speaker": self.speaker_edit.text(),
            "instruct": self.instruct_edit.text(),
            "x_vector_only_mode": self.xvector.isChecked(),
            "keep_temp": self.keep_temp.isChecked(),
            "normalize_ws": self.norm_ws.isChecked(),
            "skip_toc": self.skip_toc.isChecked(),
            "bitrate": self.bitrate.text(),
            "vbr": self.vbr.isChecked(),
        })


def main() -> int:
    app = QApplication(sys.argv)
    w = StudioWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
