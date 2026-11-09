"""
Motor de Reconocimiento de Voz (Speech-to-Text) Híbrido Optimizado:
1. Calibración única de ruido ambiental al inicio (evita cortar las primeras palabras al hablar).
2. Reconocimiento de alta precisión bilingüe (Español Colombia `es-CO` e Inglés `en-US`) vía Google Speech API
   (0 MB de consumo de RAM extra, ideal para laptops con alta carga de memoria).
3. Fallback 100% Offline con `faster-whisper` enriquecido con `initial_prompt` de vocabulario de Ultrón.
4. Modo interactivo por teclado (`text_mode`) para desarrollo o entornos sin micrófono.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Optional

from ultron.config import UltronConfig
from ultron.strings import detect_language, tr

logger = logging.getLogger("ultron.stt")

ULTRON_WHISPER_PROMPT = (
    "Ultrón, Hey Ultrón, Oye Ultrón, Juan Diego, NutriCoach, invpro, portafolio, GitHub, "
    "¿qué hora es?, ¿qué fecha es hoy?, diagnóstico del sistema, telemetría, ¿qué consume mi RAM?, "
    "mira mi pantalla, analiza mi pantalla, cuéntame un chiste, guarda una nota, lee mis notas, "
    "What time is it?, How is my PC running?, What is eating my RAM?, Look at my screen, Open my portfolio."
)


@dataclass
class TranscriptionResult:
    """Resultado estructurado de una transcripción de voz o entrada de texto."""

    text: str
    language: str
    engine: str


class UltronSTT:
    """Gestor de entrada de voz y texto de baja latencia para Ultrón."""

    def __init__(self, config: UltronConfig, text_mode: bool = False) -> None:
        self.config = config
        self.text_mode = text_mode
        self._whisper_model = None
        self._whisper_attempted = False
        self._recognizer = None
        self._calibrated = False

    def _get_recognizer(self) -> object:
        if self._recognizer is None:
            import speech_recognition as sr

            r = sr.Recognizer()
            r.pause_threshold = 0.8
            r.non_speaking_duration = 0.4
            r.dynamic_energy_threshold = True
            self._recognizer = r
        return self._recognizer

    def _init_whisper(self) -> None:
        """Inicializa faster-whisper de forma perezosa solo cuando se necesita."""
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
                "faster-whisper no disponible (%s). Se usará SpeechRecognition.",
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

        recognizer = self._get_recognizer()

        try:
            with sr.Microphone() as source:
                if not self._calibrated:
                    print("🎛️ Calibrando micrófono para el ruido ambiente (1 segundo)...")
                    recognizer.adjust_for_ambient_noise(source, duration=0.8)  # type: ignore[attr-defined]
                    self._calibrated = True
                print(f"🎙️ {tr(target_lang, 'listening')} (Habla ahora)")
                audio = recognizer.listen(source, timeout=6, phrase_time_limit=10)  # type: ignore[attr-defined]
        except sr.WaitTimeoutError:
            return None
        except OSError as exc:
            logger.warning("No se detectó micrófono activo (%s). Activando modo texto.", exc)
            self.text_mode = True
            return self.listen(lang_hint=target_lang)

        print(f"⚙️ {tr(target_lang, 'recognizing')}")

        # Modo 1 (Híbrido inteligente): Reconocimiento de alta precisión (es-CO / en-US) sin consumir RAM
        if self.config.stt_engine != "whisper_offline":
            result = self._transcribe_with_google(recognizer, audio, target_lang)
            if result:
                print(f"🗣️ [{self.config.user_name} | {result.language.upper()}]: {result.text}")
                return result

        # Modo 2 (Offline faster-whisper a 16kHz o fallback automático si no hay internet)
        if not self._whisper_attempted:
            self._whisper_attempted = True
            self._init_whisper()

        if self._whisper_model is not None:
            result = self._transcribe_with_whisper(audio, target_lang)
            if result:
                print(f"🗣️ [{self.config.user_name} | {result.language.upper()}]: {result.text}")
                return result

        print("⚠️ No alcancé a entender con claridad. Intenta hablar un poco más cerca del micrófono.")
        return None

    def _transcribe_with_whisper(
        self, audio: object, default_lang: str
    ) -> Optional[TranscriptionResult]:
        try:
            # Convertir a 16kHz mono para que faster-whisper no distorsione frecuencias de micrófonos de 48kHz
            wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)  # type: ignore[attr-defined]
            wav_stream = io.BytesIO(wav_bytes)
            segments, info = self._whisper_model.transcribe(  # type: ignore[union-attr]
                wav_stream,
                beam_size=5,
                vad_filter=True,
                initial_prompt=ULTRON_WHISPER_PROMPT,
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
                logger.debug("Google Speech API sin conexión: %s", exc)
                break
        return None
