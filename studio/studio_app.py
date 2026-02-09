from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QPlainTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from studio.studio_core import StudioCore


TOOLTIPS = {
    "Book file": "Файл книги для озвучки: .fb2 или .txt. Для .fb2 будет извлечён основной текст.",
    "Output folder": "Папка, куда сохраняются MP3: прямо сюда, без подпапок. Внутри будут только 001.mp3, 002.mp3 и т.д.",
    "Reference audio (WAV)": "Референс‑аудио (WAV) для клонирования голоса (только Base). Желательно 3–15 секунд, без шума и музыки.",
    "Reference text (TXT)": "Текст, который произносится в референс‑аудио (нужен только если выключен x‑vector only).",
    "Device": "Куда считать: cuda:0 (видеокарта) быстрее, cpu (процессор) медленнее, но стабильнее при проблемах с GPU.",
    "DType": "Точность вычислений. bf16 обычно стабильнее на новых RTX; fp16 быстрее, но иногда даёт ошибки; fp32 медленнее, но максимально совместимо.",
    "Language": "Язык текста для TTS. Для русских книг обычно Russian даже при редких английских словах.",
    "Max new tokens": "Лимит длины генерируемой последовательности. Если слишком мало — обрывы; слишком много — лишнее время/память.",
    "Temperature": "Случайность/вариативность. Ниже — ровнее и предсказуемее; выше — больше эмоций, но больше артефактов.",
    "Top-k": "Ограничение выбора следующего токена топ‑K вариантами. Меньше — стабильнее; больше — свободнее.",
    "Top-p": "Nucleus sampling: выбирает токены, пока сумма вероятностей не достигнет p. Меньше — стабильнее, больше — разнообразнее.",
    "Repetition penalty": "Штраф за повторы. Увеличение может уменьшить зацикливания, но иногда ухудшает дикцию.",
    "Speaker": "Выбор пресетного голоса (CustomVoice). Разные спикеры по-разному читают и подходят для разных языков.",
    "Instruction": "Текстовая инструкция стилю/интонации. Может улучшать или ломать чтение — использовать аккуратно.",
    "X-vector only": "Использовать только голосовую эмбеддингу из WAV. Проще и часто стабильнее. Если выключить — нужен Reference text.",
    "Split mode": "Как делить результат на файлы: по длительности, по символам, по размеру файла или не делить.",
    "Max spoken chars": "Максимум озвученных символов в одном файле (приблизительно). Удобно для одинаковых по размеру частей.",
    "Max duration (min)": "Максимальная длительность одного MP3 файла. После достижения — начинается следующий (002.mp3 и т.д.).",
    "Max file size (MB)": "Максимальный размер одного MP3. Когда превышен — следующий файл.",
    "MP3 bitrate (kbps)": "Битрейт MP3. Выше — лучше качество и больше размер. 96–160 kbps обычно ок для речи.",
    "VBR": "Переменный битрейт. Может дать лучшее качество при том же среднем размере, но файлы по весу менее предсказуемы.",
    "Skip TOC": "Пытаться вырезать оглавление/содержание из FB2 по эвристикам, чтобы оно не попадало в озвучку.",
    "Normalize whitespace": "Очистка текста: лишние пробелы/переводы строк. Обычно лучше включить для книг.",
    "Keep temp folder": "Не удалять временную папку .tmp после завершения (для диагностики). Обычно выключено.",
    "Open Model Manager": "Открыть менеджер моделей: скачать/удалить модели, проверить наличие файлов и кэша.",
}


class Worker(QThread):
    progress = Signal(int, int, str)
    done = Signal(bool, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.fn(self.progress.emit)
            self.done.emit(True, "Completed")
        except Exception as e:
            self.done.emit(False, str(e))


class StudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qwen3TTS Studio")
        self.resize(1100, 760)

        self.core = StudioCore()
        self._ensure_runtime_config()

        root = QWidget(); main = QVBoxLayout(root)
        main.addWidget(self._build_form())
        self.progress = QProgressBar(); main.addWidget(self.progress)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); main.addWidget(self.log)
        self.setCentralWidget(root)

        self.reload_models()
        self.model_combo.currentTextChanged.connect(self.update_family_visibility)


    def _ensure_runtime_config(self):
        try:
            self.core.resolve_runtime_python()
            return
        except Exception:
            pass

        QMessageBox.information(self, "Runtime not configured", "Select Install Root prepared by Installer.")
        folder = QFileDialog.getExistingDirectory(self, "Select Install Root", str(Path.home()))
        if folder:
            self.core.set_install_root(Path(folder))

    def _with_tip(self, label: str, widget: QWidget) -> tuple[str, QWidget]:
        widget.setToolTip(TOOLTIPS.get(label, ""))
        return label, widget

    def _pick_file(self, edit: QLineEdit, filt: str):
        f, _ = QFileDialog.getOpenFileName(self, "Select file", edit.text(), filt)
        if f:
            edit.setText(f)

    def _pick_dir(self, edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Select folder", edit.text())
        if d:
            edit.setText(d)

    def _build_form(self) -> QWidget:
        wrap = QWidget(); g = QGridLayout(wrap)

        model_box = QGroupBox("Model"); mf = QFormLayout(model_box)
        self.model_combo = QComboBox(); mf.addRow(*self._with_tip("Model", self.model_combo))
        self.model_manager = QPushButton("Open Model Manager"); self.model_manager.setToolTip(TOOLTIPS["Open Model Manager"])
        self.model_manager.clicked.connect(self.reload_models)
        mf.addRow(self.model_manager)

        input_box = QGroupBox("Input"); inf = QFormLayout(input_box)
        self.book_edit = QLineEdit(); b1 = QPushButton("Browse"); b1.clicked.connect(lambda: self._pick_file(self.book_edit, "Books (*.fb2 *.txt)"))
        row1 = QWidget(); h1 = QHBoxLayout(row1); h1.addWidget(self.book_edit); h1.addWidget(b1)
        inf.addRow(*self._with_tip("Book file", row1))

        self.ref_audio = QLineEdit(); b2 = QPushButton("Browse"); b2.clicked.connect(lambda: self._pick_file(self.ref_audio, "WAV (*.wav)"))
        row2 = QWidget(); h2 = QHBoxLayout(row2); h2.addWidget(self.ref_audio); h2.addWidget(b2)
        inf.addRow(*self._with_tip("Reference audio (WAV)", row2))

        self.ref_text = QLineEdit(); b3 = QPushButton("Browse"); b3.clicked.connect(lambda: self._pick_file(self.ref_text, "TXT (*.txt)"))
        row3 = QWidget(); h3 = QHBoxLayout(row3); h3.addWidget(self.ref_text); h3.addWidget(b3)
        inf.addRow(*self._with_tip("Reference text (TXT)", row3))

        output_box = QGroupBox("Output"); of = QFormLayout(output_box)
        self.output_edit = QLineEdit(str(Path.home() / "AudioBook")); b4 = QPushButton("Browse"); b4.clicked.connect(lambda: self._pick_dir(self.output_edit))
        row4 = QWidget(); h4 = QHBoxLayout(row4); h4.addWidget(self.output_edit); h4.addWidget(b4)
        of.addRow(*self._with_tip("Output folder", row4))

        self.split_mode = QComboBox(); self.split_mode.addItems(["By audio duration", "By spoken characters", "By file size", "No splitting"])
        of.addRow(*self._with_tip("Split mode", self.split_mode))
        self.max_chars = QSpinBox(); self.max_chars.setRange(200, 20000); self.max_chars.setValue(4000)
        of.addRow(*self._with_tip("Max spoken chars", self.max_chars))
        self.max_minutes = QSpinBox(); self.max_minutes.setRange(1, 240); self.max_minutes.setValue(20)
        of.addRow(*self._with_tip("Max duration (min)", self.max_minutes))
        self.max_mb = QSpinBox(); self.max_mb.setRange(1, 500); self.max_mb.setValue(50)
        of.addRow(*self._with_tip("Max file size (MB)", self.max_mb))

        gen_box = QGroupBox("Generation parameters"); gf = QFormLayout(gen_box)
        self.device = QComboBox(); self.device.addItems(["cuda:0", "cpu"])
        self.dtype = QComboBox(); self.dtype.addItems(["bf16", "fp16", "fp32"])
        self.language = QComboBox(); self.language.addItems(["Russian", "English"])
        self.max_tokens = QSpinBox(); self.max_tokens.setRange(32, 8192); self.max_tokens.setValue(1024)
        self.temperature = QDoubleSpinBox(); self.temperature.setRange(0.1, 2.0); self.temperature.setValue(0.7)
        self.top_k = QSpinBox(); self.top_k.setRange(1, 200); self.top_k.setValue(50)
        self.top_p = QDoubleSpinBox(); self.top_p.setRange(0.1, 1.0); self.top_p.setValue(0.95)
        self.repetition_penalty = QDoubleSpinBox(); self.repetition_penalty.setRange(0.8, 2.0); self.repetition_penalty.setValue(1.1)
        self.speaker = QLineEdit(); self.instruct = QLineEdit(); self.x_vector_only = QCheckBox(); self.x_vector_only.setChecked(True)
        self.bitrate = QSpinBox(); self.bitrate.setRange(64, 320); self.bitrate.setValue(128)
        self.vbr = QCheckBox()
        self.x_vector_only.toggled.connect(lambda _: self.update_family_visibility())
        self.skip_toc = QCheckBox(); self.skip_toc.setChecked(True)
        self.normalize_ws = QCheckBox(); self.normalize_ws.setChecked(True)
        self.keep_temp = QCheckBox()

        for label, widget in [
            ("Device", self.device), ("DType", self.dtype), ("Language", self.language),
            ("Max new tokens", self.max_tokens), ("Temperature", self.temperature),
            ("Top-k", self.top_k), ("Top-p", self.top_p), ("Repetition penalty", self.repetition_penalty),
            ("Speaker", self.speaker), ("Instruction", self.instruct), ("X-vector only", self.x_vector_only),
            ("MP3 bitrate (kbps)", self.bitrate), ("VBR", self.vbr), ("Skip TOC", self.skip_toc),
            ("Normalize whitespace", self.normalize_ws), ("Keep temp folder", self.keep_temp),
        ]:
            gf.addRow(*self._with_tip(label, widget))

        ctl = QWidget(); ch = QHBoxLayout(ctl)
        self.start_btn = QPushButton("Start"); self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton("Stop"); self.stop_btn.clicked.connect(self.stop)
        ch.addWidget(self.start_btn); ch.addWidget(self.stop_btn)

        g.addWidget(model_box, 0, 0)
        g.addWidget(input_box, 0, 1)
        g.addWidget(output_box, 1, 0)
        g.addWidget(gen_box, 1, 1)
        g.addWidget(ctl, 2, 0, 1, 2)
        return wrap


    def update_family_visibility(self):
        model = self.model_combo.currentText()
        family = "VoiceDesign" if "VoiceDesign" in model else "CustomVoice" if "CustomVoice" in model else "Base"
        is_base = family == "Base"
        is_custom = family == "CustomVoice"
        is_design = family == "VoiceDesign"
        self.ref_audio.setEnabled(is_base)
        self.ref_text.setEnabled(is_base and (not self.x_vector_only.isChecked()))
        self.x_vector_only.setEnabled(is_base)
        self.speaker.setEnabled(is_custom)
        self.instruct.setEnabled(is_custom or is_design)

    def reload_models(self):
        self.model_combo.clear()
        for model in self.core.installed_models():
            self.model_combo.addItem(model)
        self.update_family_visibility()

    def start(self):
        data = {
            "book_file": self.book_edit.text(), "ref_audio": self.ref_audio.text(), "ref_text": self.ref_text.text(),
            "output_dir": self.output_edit.text(), "device": self.device.currentText(), "dtype": self.dtype.currentText(),
            "language": self.language.currentText(), "max_new_tokens": self.max_tokens.value(), "temperature": self.temperature.value(),
            "top_k": self.top_k.value(), "top_p": self.top_p.value(), "repetition_penalty": self.repetition_penalty.value(),
            "speaker": self.speaker.text(), "instruct": self.instruct.text(), "x_vector_only_mode": self.x_vector_only.isChecked(),
            "bitrate": self.bitrate.value(), "vbr": self.vbr.isChecked(), "skip_toc": self.skip_toc.isChecked(),
            "normalize_ws": self.normalize_ws.isChecked(), "keep_temp": self.keep_temp.isChecked(),
            "split_mode": self.split_mode.currentText(), "max_spoken_chars": self.max_chars.value(), "max_duration_min": self.max_minutes.value(),
            "max_file_size_mb": self.max_mb.value(),
        }
        self.core.save_settings(data)

        def run(cb):
            self.core.generate_book(self.model_combo.currentText(), data, cb)

        self.worker = Worker(run)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def stop(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.requestInterruption()
            self.log.appendPlainText("Stop requested. Will stop between chunks.")

    def on_progress(self, i: int, total: int, text: str):
        self.progress.setMaximum(max(total, 1)); self.progress.setValue(i)
        self.log.appendPlainText(f"chunk {i}/{total}: {text}")
        self.core.log(f"chunk {i}/{total}: {text}")

    def on_done(self, ok: bool, text: str):
        self.log.appendPlainText(text if ok else f"ERROR: {text}")


def main() -> int:
    app = QApplication(sys.argv)
    w = StudioWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
