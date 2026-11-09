"""
Habilidades (Skills) de Automatización de Escritorio de Ultrón (Paso 4).
Incluye manejo tipado de excepciones, restauración de funciones huérfanas
(chistes, notas persistentes, cambio de nombre) y accesos rápidos a los
proyectos de Juan Diego Cerón Duque (NutriCoach Pro, INV. PRO, Portafolio, GitHub).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import random
import subprocess
import sys
import webbrowser as wb
from pathlib import Path
from typing import Dict, List

import pyjokes
import wikipedia

from ultron.config import UltronConfig
from ultron.strings import tr
from ultron.tts import UltronTTS

logger = logging.getLogger("ultron.skills")


class UltronSkills:
    """Conjunto de habilidades locales ejecutables por Ultrón."""

    def __init__(self, config: UltronConfig, tts: UltronTTS) -> None:
        self.config = config
        self.tts = tts
        self.config.ensure_dirs()

    def greet(self, lang: str = "es") -> str:
        """Saluda a Juan Diego según la hora del día."""
        hour = datetime.datetime.now().hour
        if 4 <= hour < 12:
            period_key = "morning"
        elif 12 <= hour < 18:
            period_key = "afternoon"
        elif 18 <= hour < 24:
            period_key = "evening"
        else:
            period_key = "night"

        welcome_msg = tr(lang, "welcome", user=self.config.user_name)
        period_msg = tr(lang, period_key)
        service_msg = tr(lang, "service", assistant=self.config.load_assistant_name())
        full_greeting = f"{welcome_msg} {period_msg} {service_msg}"
        self.tts.speak(full_greeting, lang=lang)
        return full_greeting

    def tell_time(self, lang: str = "es") -> str:
        """Informa la hora actual."""
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        msg = tr(lang, "time", time=now_str)
        self.tts.speak(msg, lang=lang)
        return msg

    def tell_date(self, lang: str = "es") -> str:
        """Informa la fecha actual."""
        now = datetime.datetime.now()
        date_str = f"{now.day} de {now.strftime('%B')} de {now.year}" if lang == "es" else now.strftime("%d %B %Y")
        msg = tr(lang, "date", date=date_str)
        self.tts.speak(msg, lang=lang)
        return msg

    def search_wikipedia(self, query: str, lang: str = "es") -> str:
        """Busca un resumen en Wikipedia con manejo explícito de excepciones."""
        clean_q = (
            query.replace("wikipedia", "")
            .replace("busca en", "")
            .replace("buscar en", "")
            .replace("search on", "")
            .replace("search", "")
            .strip()
        )
        if not clean_q:
            msg = tr(lang, "no_result")
            self.tts.speak(msg, lang=lang)
            return msg

        self.tts.speak(tr(lang, "wiki_search"), lang=lang)
        try:
            wikipedia.set_lang(lang if lang in ("es", "en", "fr") else "es")
            summary = wikipedia.summary(clean_q, sentences=2)
            self.tts.speak(summary, lang=lang)
            return summary
        except wikipedia.exceptions.DisambiguationError as exc:
            options = ", ".join(exc.options[:3])
            msg = (
                f"Hay varios resultados para '{clean_q}', por ejemplo: {options}."
                if lang == "es"
                else f"Multiple results found for '{clean_q}', such as: {options}."
            )
            self.tts.speak(msg, lang=lang)
            return msg
        except (wikipedia.exceptions.PageError, wikipedia.exceptions.WikipediaException) as exc:
            logger.debug("Wikipedia error: %s", exc)
            msg = tr(lang, "no_result")
            self.tts.speak(msg, lang=lang)
            return msg

    def tell_joke(self, lang: str = "es") -> str:
        """Cuenta un chiste para programadores (función restaurada de pyjokes)."""
        joke_lang = lang if lang in ("es", "en") else "es"
        try:
            joke = pyjokes.get_joke(language=joke_lang, category="neutral")
        except Exception:
            joke = pyjokes.get_joke(language="en", category="neutral")
        self.tts.speak(joke, lang=joke_lang)
        return joke

    def save_note(self, content: str, lang: str = "es") -> str:
        """Guarda una nota con marca de tiempo en formato JSON."""
        clean_note = content.strip()
        notes = self._load_notes_list()
        entry = {
            "id": len(notes) + 1,
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "content": clean_note,
        }
        notes.append(entry)
        self.config.ensure_dirs()
        self.config.notes_file.write_text(
            json.dumps(notes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        msg = tr(lang, "note_saved", note=clean_note)
        self.tts.speak(msg, lang=lang)
        return msg

    def list_notes(self, lang: str = "es") -> str:
        """Lee las notas guardadas por el usuario."""
        notes = self._load_notes_list()
        if not notes:
            msg = tr(lang, "notes_empty")
            self.tts.speak(msg, lang=lang)
            return msg

        header = tr(lang, "notes_header", count=len(notes))
        items = "; ".join(f"{n['id']}: {n['content']}" for n in notes[-5:])
        full_msg = f"{header} {items}"
        self.tts.speak(full_msg, lang=lang)
        return full_msg

    def _load_notes_list(self) -> List[Dict[str, object]]:
        if not self.config.notes_file.exists():
            return []
        try:
            data = json.loads(self.config.notes_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def change_name(self, new_name: str, lang: str = "es") -> str:
        """Cambia y persiste el nombre del asistente (función restaurada)."""
        clean_name = new_name.strip() or "Ultrón"
        self.config.save_assistant_name(clean_name)
        msg = tr(lang, "name_set", name=clean_name)
        self.tts.speak(msg, lang=lang)
        return msg

    def take_screenshot(self, lang: str = "es") -> str:
        """Toma una captura de pantalla con timestamp."""
        self.config.ensure_dirs()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.config.screenshots_dir / f"ultron_capture_{ts}.png"
        try:
            import pyautogui

            pyautogui.screenshot().save(str(path))
            msg = tr(lang, "screenshot", path=path)
        except Exception as exc:
            logger.warning("No se pudo capturar pantalla (entorno headless): %s", exc)
            msg = f"No fue posible tomar la captura en este entorno gráfico ({exc})."
        self.tts.speak(msg, lang=lang)
        return msg

    def play_music(self, query: str, lang: str = "es") -> str:
        """Reproduce música del directorio ~/Music."""
        music_dir = Path.home() / "Music"
        if not music_dir.exists():
            msg = tr(lang, "error_music")
            self.tts.speak(msg, lang=lang)
            return msg

        songs = [f for f in music_dir.iterdir() if f.is_file()]
        clean_q = (
            query.replace("reproduce música", "")
            .replace("reproducir música", "")
            .replace("play music", "")
            .replace("joue de la musique", "")
            .strip()
        )
        if clean_q:
            songs = [s for s in songs if clean_q in s.name.lower()]

        if not songs:
            msg = tr(lang, "no_song")
            self.tts.speak(msg, lang=lang)
            return msg

        chosen = random.choice(songs)
        self._open_media_file(chosen)
        msg = tr(lang, "playing", song=chosen.name)
        self.tts.speak(msg, lang=lang)
        return msg

    def open_website_or_project(self, target_key: str, lang: str = "es") -> str:
        """Abre un sitio web o uno de los proyectos de Juan Diego Cerón Duque."""
        url = self.config.personal_shortcuts.get(target_key.lower(), target_key)
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        wb.open(url)
        msg = tr(lang, "opening_site", site=target_key)
        self.tts.speak(msg, lang=lang)
        return msg

    def system_power(self, action: str, lang: str = "es", dry_run: bool = False) -> str:
        """Ejecuta apagado o reinicio del sistema de forma segura."""
        if action == "shutdown":
            msg = tr(lang, "shutdown", user=self.config.user_name)
            cmd = ["systemctl", "poweroff"] if sys.platform != "win32" else ["shutdown", "/s", "/f", "/t", "1"]
        else:
            msg = tr(lang, "restart")
            cmd = ["systemctl", "reboot"] if sys.platform != "win32" else ["shutdown", "/r", "/f", "/t", "1"]

        self.tts.speak(msg, lang=lang)
        if not dry_run:
            subprocess.run(cmd, check=False)
        return msg

    @staticmethod
    def _open_media_file(path: Path) -> None:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
