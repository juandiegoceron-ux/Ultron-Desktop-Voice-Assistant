"""
Motor de Síntesis de Voz (Text-to-Speech) con soporte multilingüe (ES/EN/FR)
y protección contra bloqueos en entornos sin tarjeta de sonido.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger("ultron.tts")


class UltronTTS:
    """Envoltura segura y multilingüe sobre pyttsx3."""

    def __init__(self, rate: int = 175, volume: float = 1.0, mute: bool = False) -> None:
        self.mute = mute
        self._lock = threading.Lock()
        self.engine = None
        self.voice_map: Dict[str, Optional[str]] = {"es": None, "en": None, "fr": None}

        if not self.mute:
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
        """Imprime y pronuncia el texto en el idioma indicado."""
        print(f"🤖 [Ultrón | {lang.upper()}]: {text}")
        if self.mute or self.engine is None:
            return

        with self._lock:
            try:
                voice_id = self.voice_map.get(lang)
                if voice_id:
                    self.engine.setProperty("voice", voice_id)
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as exc:
                logger.debug("Error al sintetizar voz: %s", exc)
