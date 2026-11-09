"""
Motor de Reconocimiento de Voz (Speech-to-Text) Híbrido:
1. Offline primario con `faster-whisper` (Paso 3 de la hoja de ruta) con detección automática de idioma.
2. Fallback online con `SpeechRecognition` (Google Speech API).
3. Modo interactivo por teclado (`text_mode`) para desarrollo o entornos sin micrófono.
"""

from __future__ import annotations

import io
import logging
import tempfile
from dataclasses import dataclass
from typing import Optional

from ultron.config import UltronConfig
from ultron.strings import detect_language, tr

logger = logging.getLogger("ultron.stt")


@dataclass
class TranscriptionResult:
    """Resultado estructurado de una transcripción de voz o entrada de texto."""

    text: str
    language: str
    engine: str


class UltronSTT:
    """Gestor de entrada de voz y texto para Ultrón."""

    def __init__(self, config: UltronConfig, text_mode: bool = False) -> None:
        self.config = config
        self.text_mode = text_mode
        self._whisper_model = None
        self._whisper_attempted = False

    def _init_whisper(self) -> None:
        """Inicializa faster-whisper de forma perezosa y segura."""
        try:
            from faster_whisper import WhisperModel

            self._whisper_model = WhisperModel(
                self.config.whisper_model,
                device="cpu",
                compute_type="int8",
            )
            logger.info(
                "Modelo faster-whisper ('%s') cargado correctamente en modo offline.",
                self.config.whisper_model,
            )
        except Exception as exc:
            logger.info(
                "faster-whisper no disponible (%s). Se usará SpeechRecognition como fallback.",
                exc,
            )
            self._whisper_model = None

    def listen(self, lang_hint: Optional[str] = None) -> Optional[TranscriptionResult]:
        """
        Escucha una orden del usuario por micrófono o consola y devuelve el texto y el idioma detectado.
        """
        target_lang = lang_hint or self.config.default_lang

        if self.text_mode:
            try:
                raw = input(f"\n🎙️ [{self.config.user_name}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return TranscriptionResult(text="exit", language=target_lang, engine="text")
            if not raw:
                return None
            detected = detect_language(raw, default_lang=target_lang)
            return TranscriptionResult(text=raw.lower(), language=detected, engine="text")

        try:
            import speech_recognition as sr
        except ImportError:
            logger.warning("SpeechRecognition no instalado; cambiando a modo texto.")
            self.text_mode = True
            return self.listen(lang_hint=target_lang)

        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 1.0

        try:
            with sr.Microphone() as source:
                print(f"🎙️ {tr(target_lang, 'listening')}")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=12)
        except sr.WaitTimeoutError:
            return None
        except OSError as exc:
            logger.warning("No se detectó micrófono activo (%s). Activando modo texto.", exc)
            self.text_mode = True
            return self.listen(lang_hint=target_lang)

        print(f"⚙️ {tr(target_lang, 'recognizing')}")

        # 1. Intentar con faster-whisper (100% offline y detección nativa de idioma)
        if self.config.stt_engine == "whisper" and not self._whisper_attempted:
            self._whisper_attempted = True
            self._init_whisper()

        if self._whisper_model is not None:
            result = self._transcribe_with_whisper(audio, target_lang)
            if result:
                return result

        # 2. Fallback a Google Web Speech API respetando prioridad de idiomas de Juan Diego (ES -> EN -> FR)
        return self._transcribe_with_google(recognizer, audio, target_lang)

    def _transcribe_with_whisper(
        self, audio: object, default_lang: str
    ) -> Optional[TranscriptionResult]:
        try:
            wav_bytes = audio.get_wav_data()  # type: ignore[attr-defined]
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_wav:
                tmp_wav.write(wav_bytes)
                tmp_wav.flush()
                segments, info = self._whisper_model.transcribe(  # type: ignore[union-attr]
                    tmp_wav.name,
                    beam_size=3,
                    vad_filter=True,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()

            if not text:
                return None

            lang_code = getattr(info, "language", default_lang) or default_lang
            if lang_code not in ("es", "en", "fr"):
                lang_code = detect_language(text, default_lang=default_lang)

            return TranscriptionResult(
                text=text.lower(),
                language=lang_code,
                engine="faster-whisper",
            )
        except Exception as exc:
            logger.debug("Fallo en transcripción faster-whisper: %s", exc)
            return None

    def _transcribe_with_google(
        self, recognizer: object, audio: object, default_lang: str
    ) -> Optional[TranscriptionResult]:
        import speech_recognition as sr

        lang_BCP47 = {
            "es": "es-CO",
            "en": "en-US",
            "fr": "fr-FR",
        }
        ordered_langs = [default_lang] + [
            code for code in ("es", "en", "fr") if code != default_lang
        ]

        for code in ordered_langs:
            bcp = lang_BCP47.get(code, "es-CO")
            try:
                query = recognizer.recognize_google(audio, language=bcp)  # type: ignore[attr-defined]
                if query:
                    detected = detect_language(query, default_lang=code)
                    return TranscriptionResult(
                        text=query.lower(),
                        language=detected,
                        engine=f"google ({bcp})",
                    )
            except sr.UnknownValueError:
                continue
            except sr.RequestError as exc:
                logger.error("Servicio de reconocimiento de Google no disponible: %s", exc)
                break
        return None
