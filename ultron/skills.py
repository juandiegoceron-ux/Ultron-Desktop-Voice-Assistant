"""
Habilidades (Skills) de Automatización de Escritorio de Ultrón v3.1.
Incluye:
- Lanzador Universal de Aplicaciones de Windows (Spotify, VS Code, Calculadora, WhatsApp, Discord, Office, etc.) y sitios web.
- Búsqueda directa por voz en YouTube y Google.
- Control de ventanas y volumen del sistema (Subir/Bajar volumen, Silenciar, Minimizar todo, Cambiar ventana).
- Telemetría de hardware y procesos en tiempo real (`UltronTelemetry`).
- Visión Multimodal de Escritorio (`UltronVision`: Debug, UX Audit, Biomedical/PID, General).
- Funciones de notas JSON persistentes, chistes, cambio de nombre, Wikipedia y música.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import random
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser as wb
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pyjokes
import wikipedia

from ultron.config import UltronConfig
from ultron.strings import tr
from ultron.telemetry import UltronTelemetry
from ultron.tts import UltronTTS
from ultron.vision import UltronVision

logger = logging.getLogger("ultron.skills")

# Mapa de aplicaciones nativas de Windows / URI schemes y su respaldo web
WINDOWS_APPS_MAP: Dict[str, Tuple[str, Optional[str]]] = {
    "spotify": ("spotify:", "https://open.spotify.com"),
    "whatsapp": ("whatsapp:", "https://web.whatsapp.com"),
    "discord": ("discord:", "https://discord.com/app"),
    "calculadora": ("calc.exe", None),
    "calculator": ("calc.exe", None),
    "bloc de notas": ("notepad.exe", None),
    "notepad": ("notepad.exe", None),
    "paint": ("mspaint.exe", None),
    "explorador": ("explorer.exe", None),
    "explorer": ("explorer.exe", None),
    "administrador de tareas": ("taskmgr.exe", None),
    "task manager": ("taskmgr.exe", None),
    "configuración": ("ms-settings:", None),
    "configuracion": ("ms-settings:", None),
    "settings": ("ms-settings:", None),
    "vscode": ("code", "https://vscode.dev"),
    "visual studio code": ("code", "https://vscode.dev"),
    "cmd": ("cmd.exe", None),
    "terminal": ("wt.exe", None),
    "word": ("winword", None),
    "excel": ("excel", None),
    "powerpoint": ("powerpnt", None),
}

POPULAR_WEBSITES_MAP: Dict[str, str] = {
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "gemini": "https://gemini.google.com",
    "netflix": "https://www.netflix.com",
    "gmail": "https://mail.google.com",
    "correo": "https://mail.google.com",
    "supabase": "https://supabase.com/dashboard",
    "vercel": "https://vercel.com/dashboard",
    "figma": "https://www.figma.com",
    "canva": "https://www.canva.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "tiktok": "https://www.tiktok.com",
    "amazon": "https://www.amazon.com",
    "mercadolibre": "https://www.mercadolibre.com.co",
}


class UltronSkills:
    """Conjunto de habilidades locales, de telemetría y visión multimodal ejecutables por Ultrón."""

    def __init__(self, config: UltronConfig, tts: UltronTTS) -> None:
        self.config = config
        self.tts = tts
        self.config.ensure_dirs()
        self.telemetry = UltronTelemetry(user_name=self.config.user_name)
        self.vision = UltronVision(config=self.config)

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

    def acknowledge_presence(self, lang: str = "es") -> str:
        """Responde cuando Juan Diego dice solo 'Ultrón' o 'Hola Ultrón'."""
        msg = (
            f"Aquí estoy, {self.config.user_name}. Te escucho fuerte y claro. "
            "¿Qué aplicación abrimos, qué analizamos en tu pantalla o qué consulta tienes?"
        )
        self.tts.speak(msg, lang=lang)
        return msg

    def tell_time(self, lang: str = "es") -> str:
        """Informa la hora actual."""
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        msg = tr(lang, "time", time=now_str)
        self.tts.speak(msg, lang=lang)
        return msg

    def tell_date(self, lang: str = "es") -> str:
        """Informa la fecha actual."""
        now = datetime.datetime.now()
        date_str = (
            f"{now.day} de {now.strftime('%B')} de {now.year}"
            if lang == "es"
            else now.strftime("%d %B %Y")
        )
        msg = tr(lang, "date", date=date_str)
        self.tts.speak(msg, lang=lang)
        return msg

    def system_telemetry(self, lang: str = "es") -> str:
        """Ejecuta un diagnóstico completo de hardware y sistema operativo."""
        report_voice = self.telemetry.format_voice_report(lang=lang, include_processes=True)
        self.tts.speak(report_voice, lang=lang)
        return report_voice

    def top_processes(self, sort_by: str = "memory", lang: str = "es") -> str:
        """Informa cuáles son los procesos que más memoria RAM o CPU están consumiendo."""
        report_voice = self.telemetry.format_top_processes_voice(
            limit=3, sort_by=sort_by, lang=lang
        )
        self.tts.speak(report_voice, lang=lang)
        return report_voice

    def analyze_screen(
        self,
        query: str = "¿Qué hay en mi pantalla?",
        mode: Optional[str] = None,
        lang: str = "es",
    ) -> str:
        """Captura la pantalla activa y la analiza con Visión Multimodal."""
        result = self.vision.analyze_screen(user_query=query, mode=mode, lang=lang)
        self.tts.speak(result.analysis, lang=lang)
        return result.analysis

    def open_any_target(self, raw_target: str, lang: str = "es") -> str:
        """
        Abre proyectos personales de Juan Diego, aplicaciones nativas de Windows (Spotify, Calculadora,
        VS Code, WhatsApp, etc.) o cualquier sitio web.
        """
        target = raw_target.strip().lower().strip(".,!?¿¡")
        if not target:
            msg = f"Dime qué aplicación o página quieres que abra, {self.config.user_name}."
            self.tts.speak(msg, lang=lang)
            return msg

        # 1. Proyectos personales de Juan Diego y accesos rápidos configurados
        for key, url in self.config.personal_shortcuts.items():
            if key in target:
                wb.open(url)
                msg = tr(lang, "opening_site", site=key.capitalize())
                self.tts.speak(msg, lang=lang)
                return msg

        # 2. Aplicaciones nativas de Windows / URI protocols (Spotify, Calculadora, VS Code, etc.)
        for app_name, (win_cmd, web_fallback) in WINDOWS_APPS_MAP.items():
            if app_name in target:
                launched = self._launch_native_app(win_cmd, web_fallback)
                msg = f"Abriendo {app_name.capitalize()}, {self.config.user_name}." if launched else f"Abriendo {app_name.capitalize()} en el navegador."
                self.tts.speak(msg, lang=lang)
                return msg

        # 3. Sitios web populares (ChatGPT, Claude, Figma, Supabase, Vercel, Netflix, etc.)
        for site_name, site_url in POPULAR_WEBSITES_MAP.items():
            if site_name in target:
                wb.open(site_url)
                msg = tr(lang, "opening_site", site=site_name.capitalize())
                self.tts.speak(msg, lang=lang)
                return msg

        # 4. Si menciona un dominio (.com, .co, .org, .io, .ai) o una marca general, abrirla o buscarla
        clean_word = target.split()[0]
        if "." in clean_word:
            url = clean_word if clean_word.startswith(("http://", "https://")) else f"https://{clean_word}"
        else:
            url = f"https://www.{clean_word}.com"
        wb.open(url)
        msg = tr(lang, "opening_site", site=target)
        self.tts.speak(msg, lang=lang)
        return msg

    @staticmethod
    def _launch_native_app(win_cmd: str, web_fallback: Optional[str]) -> bool:
        """Intenta lanzar una aplicación o protocolo URI en Windows/Linux/macOS; usa web_fallback si falla."""
        try:
            if sys.platform == "win32":
                if win_cmd.endswith(":") or win_cmd.endswith(".exe"):
                    os.startfile(win_cmd)  # type: ignore[attr-defined]
                    return True
                resolved = shutil.which(win_cmd)
                if resolved:
                    subprocess.Popen([resolved])
                    return True
                os.startfile(win_cmd)  # type: ignore[attr-defined]
                return True
            else:
                resolved = shutil.which(win_cmd.replace(".exe", ""))
                if resolved:
                    subprocess.Popen([resolved])
                    return True
        except Exception as exc:
            logger.debug("No se pudo abrir app nativa '%s' (%s).", win_cmd, exc)

        if web_fallback:
            wb.open(web_fallback)
        return False

    def search_youtube(self, search_query: str, lang: str = "es") -> str:
        """Busca o reproduce directamente un tema o video en YouTube."""
        clean_q = search_query.strip()
        if not clean_q:
            wb.open("https://www.youtube.com")
            msg = "Abriendo YouTube."
        else:
            encoded = urllib.parse.quote_plus(clean_q)
            wb.open(f"https://www.youtube.com/results?search_query={encoded}")
            msg = f"Buscando '{clean_q}' en YouTube, {self.config.user_name}."
        self.tts.speak(msg, lang=lang)
        return msg

    def search_google(self, search_query: str, lang: str = "es") -> str:
        """Realiza una búsqueda directa en Google en una pestaña del navegador."""
        clean_q = search_query.strip()
        if not clean_q:
            wb.open("https://www.google.com")
            msg = "Abriendo Google."
        else:
            encoded = urllib.parse.quote_plus(clean_q)
            wb.open(f"https://www.google.com/search?q={encoded}")
            msg = f"Buscando '{clean_q}' en Google, {self.config.user_name}."
        self.tts.speak(msg, lang=lang)
        return msg

    def desktop_control(self, action: str, lang: str = "es") -> str:
        """Controla el volumen del sistema y las ventanas activas mediante PyAutoGUI."""
        try:
            import pyautogui

            if action == "volume_up":
                for _ in range(5):
                    pyautogui.press("volumeup")
                msg = "Subiendo el volumen del sistema."
            elif action == "volume_down":
                for _ in range(5):
                    pyautogui.press("volumedown")
                msg = "Bajando el volumen del sistema."
            elif action == "volume_mute":
                pyautogui.press("volumemute")
                msg = "Audio del sistema alternado."
            elif action == "minimize_all":
                pyautogui.hotkey("win", "d")
                msg = "Mostrando el escritorio."
            elif action == "switch_window":
                pyautogui.hotkey("alt", "tab")
                msg = "Cambiando de ventana activa."
            else:
                msg = "Acción de escritorio completada."
        except Exception as exc:
            logger.debug("Control de escritorio no disponible: %s", exc)
            msg = f"No pude ejecutar el atajo de teclado en este entorno ({exc})."

        self.tts.speak(msg, lang=lang)
        return msg

    def open_website_or_project(self, target_key: str, lang: str = "es") -> str:
        """Compatibilidad directa para abrir un proyecto o URL."""
        return self.open_any_target(target_key, lang=lang)

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
        """Cuenta un chiste para programadores."""
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
        """Cambia y persiste el nombre del asistente."""
        clean_name = new_name.strip() or "Ultrón"
        self.config.save_assistant_name(clean_name)
        msg = tr(lang, "name_set", name=clean_name)
        self.tts.speak(msg, lang=lang)
        return msg

    def take_screenshot(self, lang: str = "es") -> str:
        """Toma una captura de pantalla tolerante a fallos usando el pipeline de UltronVision."""
        capture = self.vision.capture_screen()
        msg = tr(lang, "screenshot", path=capture.file_path)
        self.tts.speak(msg, lang=lang)
        return msg

    def play_music(self, query: str, lang: str = "es") -> str:
        """Reproduce música del directorio ~/Music o abre Spotify/YouTube si no hay archivos locales."""
        music_dir = Path.home() / "Music"
        songs = [f for f in music_dir.iterdir() if f.is_file() and f.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a")] if music_dir.exists() else []

        clean_q = (
            query.replace("reproduce música", "")
            .replace("reproducir música", "")
            .replace("pon música", "")
            .replace("play music", "")
            .replace("joue de la musique", "")
            .strip()
        )
        if clean_q and songs:
            songs = [s for s in songs if clean_q in s.name.lower()]

        if songs:
            chosen = random.choice(songs)
            self._open_media_file(chosen)
            msg = tr(lang, "playing", song=chosen.name)
            self.tts.speak(msg, lang=lang)
            return msg

        # Si no hay archivos MP3 locales en ~/Music, abrir Spotify o YouTube con la canción pedida
        if clean_q:
            return self.search_youtube(clean_q, lang=lang)
        return self.open_any_target("spotify", lang=lang)

    def system_power(self, action: str, lang: str = "es", dry_run: bool = False) -> str:
        """Ejecuta apagado o reinicio del sistema de forma segura."""
        if action == "shutdown":
            msg = tr(lang, "shutdown", user=self.config.user_name)
            cmd = (
                ["systemctl", "poweroff"]
                if sys.platform != "win32"
                else ["shutdown", "/s", "/f", "/t", "1"]
            )
        else:
            msg = tr(lang, "restart")
            cmd = (
                ["systemctl", "reboot"]
                if sys.platform != "win32"
                else ["shutdown", "/r", "/f", "/t", "1"]
            )

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
