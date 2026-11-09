"""
Motor de Síntesis de Voz (Text-to-Speech) con soporte multilingüe (ES/EN/FR).
En Windows utiliza `SAPI.SpVoice` nativo por llamada para evitar bloqueos de audio
cuando se alterna con el micrófono (`PyAudio`), y `pyttsx3` como motor multiplataforma.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Dict, Optional

logger = logging.getLogger("ultron.tts")


class UltronTTS:
    """Envoltura segura y multilingüe para síntesis de voz en Windows, Linux y macOS."""

    def __init__(self, rate: int = 175, volume: float = 1.0, mute: bool = False) -> None:
        self.mute = mute
        self.rate = rate
        self.volume = volume
        self._lock = threading.Lock()
        self.engine = None
        self.voice_map: Dict[str, Optional[str]] = {"es": None, "en": None, "fr": None}

        if not self.mute and sys.platform != "win32":
            self._init_engine(rate, volume)

    def _init_engine(self, rate: int, volume: float) -> None:
        try:
            import pyttsx3

            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", rate)
            self.engine.setProperty("volume", volume)

            voices = self.engine.getProperty("voices") or []
            for voice in voices:
                v_meta = f"{getattr(voice, 'languages', '')} {getattr(voice, 'name', '')} {getattr(voice, 'id', '')}".lower()
                if any(k in v_meta for k in ("es", "spanish", "español", "mexico", "colombia", "latam")):
                    self.voice_map["es"] = voice.id
                if any(k in v_meta for k in ("en-us", "en_us", "english")):
                    self.voice_map["en"] = voice.id
                if any(k in v_meta for k in ("fr-fr", "fr_fr", "french", "français")):
                    self.voice_map["fr"] = voice.id
        except Exception as exc:
            logger.warning("TTS local no disponible (%s). Usando salida por consola.", exc)
            self.engine = None

    def speak(self, text: str, lang: str = "es") -> None:
        """Imprime y pronuncia el texto en el idioma indicado sin bloquear el micrófono."""
        print(f"🤖 [Ultrón | {lang.upper()}]: {text}")
        if self.mute:
            return

        with self._lock:
            if sys.platform == "win32":
                if self._speak_windows_sapi(text, lang):
                    return

            if self.engine is None:
                self._init_engine(self.rate, self.volume)

            if self.engine is not None:
                try:
                    voice_id = self.voice_map.get(lang)
                    if voice_id:
                        self.engine.setProperty("voice", voice_id)
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as exc:
                    logger.debug("Error al sintetizar voz con pyttsx3: %s", exc)

    @staticmethod
    def _speak_windows_sapi(text: str, lang: str = "es") -> bool:
        """Usa el motor COM SAPI.SpVoice nativo de Windows para evitar conflictos con PyAudio."""
        try:
            import pythoncom  # type: ignore[import-not-found]
            import win32com.client  # type: ignore[import-not-found]

            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = 1
            speaker.Volume = 100

            lang_keywords = {
                "es": ("spanish", "español", "es-", "sabina", "helena", "pablo", "raul", "dalia"),
                "en": ("english", "en-", "david", "zira", "mark"),
                "fr": ("french", "français", "fr-", "hortense", "paul"),
            }.get(lang, ("spanish", "español", "es-"))

            for v in speaker.GetVoices():
                desc = v.GetDescription().lower()
                if any(k in desc for k in lang_keywords):
                    speaker.Voice = v
                    break

            speaker.Speak(text)
            return True
        except Exception as exc:
            logger.debug("Fallback de SAPI.SpVoice a pyttsx3: %s", exc)
            return False
