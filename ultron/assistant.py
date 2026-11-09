"""
Orquestador Principal de Ultrón (`UltronAssistant`).
Integra las 4 mejoras clave:
1. IA Generativa (Gemini / Ollama) con respuesta siempre en Español cuando Juan Diego practica Inglés.
2. Detección de Wake-Word ("Ultrón" / "Hey Ultrón").
3. Reconocimiento de voz offline con `faster-whisper` y fallback híbrido.
4. Enrutador modular de habilidades con manejo robusto de errores.
"""

from __future__ import annotations

import logging
from typing import Optional

from ultron.config import UltronConfig
from ultron.llm import UltronBrain
from ultron.skills import UltronSkills
from ultron.strings import detect_language, tr
from ultron.stt import UltronSTT
from ultron.tts import UltronTTS
from ultron.wakeword import WakeWordDetector

logger = logging.getLogger("ultron.assistant")


class UltronAssistant:
    """Núcleo operativo de Ultrón."""

    def __init__(
        self,
        config: Optional[UltronConfig] = None,
        text_mode: bool = False,
        mute: bool = False,
        force_spanish_reply: bool = True,
    ) -> None:
        self.config = config or UltronConfig()
        self.force_spanish_reply = force_spanish_reply
        self.tts = UltronTTS(mute=mute)
        self.stt = UltronSTT(self.config, text_mode=text_mode)
        self.wake_detector = WakeWordDetector(
            wake_words=self.config.wake_words,
            enabled=self.config.wake_word_enabled,
        )
        self.skills = UltronSkills(self.config, self.tts)
        self.brain = UltronBrain(self.config)

    def reply_lang(self, detected_lang: str) -> str:
        """
        Determina el idioma de respuesta.
        Por preferencia de Juan Diego, aunque él hable en inglés para practicar,
        Ultrón le responde siempre en español.
        """
        if self.force_spanish_reply:
            return "es"
        return detected_lang

    def process_command(self, raw_query: str, detected_lang: Optional[str] = None) -> str:
        """
        Enruta una orden (en español, inglés o francés) hacia la habilidad correspondiente
        o hacia el cerebro generativo (LLM) si es una pregunta abierta.
        """
        query = raw_query.strip().lower()
        in_lang = detected_lang or detect_language(query, default_lang=self.config.default_lang)
        out_lang = self.reply_lang(in_lang)

        # 1. Salida / Modo offline
        if any(w in query for w in ("salir", "desconectar", "offline", "exit", "repos", "apágate")):
            msg = tr(out_lang, "offline", user=self.config.user_name)
            self.tts.speak(msg, lang=out_lang)
            return "EXIT"

        # 2. Hora
        if any(w in query for w in ("qué hora", "que hora", "dime la hora", "what time", "current time", "heure")):
            return self.skills.tell_time(lang=out_lang)

        # 3. Fecha
        if any(w in query for w in ("qué fecha", "que fecha", "qué día es hoy", "what date", "today's date", "date")):
            return self.skills.tell_date(lang=out_lang)

        # 4. Proyectos personales de Juan Diego y sitios web
        for shortcut_key in self.config.personal_shortcuts:
            if shortcut_key in query and any(
                verb in query for verb in ("abre", "abrir", "open", "ouvre", "muéstrame", "show", "ir a")
            ):
                return self.skills.open_website_or_project(shortcut_key, lang=out_lang)

        # 5. Wikipedia
        if "wikipedia" in query:
            return self.skills.search_wikipedia(query, lang=out_lang)

        # 6. Chistes (función restaurada)
        if any(w in query for w in ("chiste", "joke", "blague", "hazme reír", "tell me a joke")):
            return self.skills.tell_joke(lang=out_lang)

        # 7. Notas persistentes (función restaurada y mejorada)
        if any(
            w in query
            for w in ("lee mis notas", "leer notas", "mis notas", "read my notes", "show notes", "list notes")
        ):
            return self.skills.list_notes(lang=out_lang)

        if any(w in query for w in ("guarda una nota", "anota", "nueva nota", "take a note", "save note", "note:")):
            note_body = (
                query.replace("guarda una nota", "")
                .replace("nueva nota", "")
                .replace("anota", "")
                .replace("take a note", "")
                .replace("save note", "")
                .replace("note:", "")
                .strip(" :,-")
            )
            if not note_body:
                self.tts.speak(tr(out_lang, "note_asked"), lang=out_lang)
                follow_up = self.stt.listen(lang_hint=in_lang)
                note_body = follow_up.text if follow_up else ""
            if note_body:
                return self.skills.save_note(note_body, lang=out_lang)

        # 8. Cambio de nombre del asistente (función restaurada)
        if any(
            w in query
            for w in ("cambia tu nombre a", "cambiar nombre a", "change your name to", "llámate")
        ):
            for prefix in ("cambia tu nombre a", "cambiar nombre a", "change your name to", "llámate"):
                if prefix in query:
                    new_name = query.split(prefix, 1)[1].strip()
                    if new_name:
                        return self.skills.change_name(new_name.title(), lang=out_lang)

        # 9. Captura de pantalla
        if any(w in query for w in ("captura", "screenshot", "pantallazo", "capture")):
            return self.skills.take_screenshot(lang=out_lang)

        # 10. Música
        if any(w in query for w in ("música", "musica", "music", "musique")):
            return self.skills.play_music(query, lang=out_lang)

        # 11. Control de energía del sistema
        if any(w in query for w in ("apagar sistema", "shutdown system", "extinction")):
            return self.skills.system_power("shutdown", lang=out_lang)

        if any(w in query for w in ("reiniciar sistema", "restart system", "redémarrage")):
            return self.skills.system_power("restart", lang=out_lang)

        # 12. Cerebro de IA Generativa (Gemini / Ollama) para conversación libre y práctica de inglés
        answer = self.brain.ask(
            prompt=raw_query,
            input_lang=in_lang,
            force_spanish_reply=self.force_spanish_reply,
        )
        self.tts.speak(answer, lang=out_lang)
        return answer

    def run_forever(self) -> None:
        """Bucle principal de escucha activa con soporte de Wake-Word."""
        self.skills.greet(lang="es" if self.force_spanish_reply else self.config.default_lang)

        while True:
            try:
                if self.wake_detector.enabled:
                    primary_ww = self.config.wake_words[0] if self.config.wake_words else "ultrón"
                    print(f"⚡ {tr('es', 'wake_waiting', wake_word=primary_ww)}")

                heard = self.stt.listen(lang_hint=self.config.default_lang)
                if not heard or not heard.text:
                    continue

                match = self.wake_detector.check_transcript(heard.text)
                if not match.triggered:
                    continue

                command_text = match.remaining_command
                if not command_text:
                    # El usuario solo dijo "Ultrón": confirmamos y escuchamos la orden
                    self.tts.speak(tr("es", "wake_detected", user=self.config.user_name), lang="es")
                    follow_up = self.stt.listen(lang_hint=heard.language)
                    if not follow_up or not follow_up.text:
                        continue
                    command_text = follow_up.text
                    heard = follow_up

                result = self.process_command(command_text, detected_lang=heard.language)
                if result == "EXIT":
                    break
            except KeyboardInterrupt:
                print("\n👋 Sesión finalizada por teclado.")
                break
