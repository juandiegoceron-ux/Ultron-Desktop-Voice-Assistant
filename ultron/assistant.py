"""
Orquestador Principal de Ultrón (`UltronAssistant` v3.1).
Integra:
1. Limpieza automática del prefijo "Ultrón" / "Hey Ultrón" incluso en modo `--no-wake`.
2. Lanzador universal de aplicaciones de Windows (`Spotify`, `VS Code`, `Calculadora`, `WhatsApp`, `Discord`, etc.) y proyectos de Juan Diego.
3. Búsqueda directa en YouTube y Google, y control de volumen/ventanas de Windows.
4. Telemetría en tiempo real y Visión Multimodal de Escritorio.
5. Cerebro de IA Generativa con 3 niveles (Gemini API -> Ollama -> Cloud IA Gratuito Zero-Config).
"""

from __future__ import annotations

import logging
import re
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
    """Núcleo operativo de Ultrón v3.1."""

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

    def _strip_wake_prefix(self, text: str) -> str:
        """
        Elimina invocaciones como 'ultrón', 'hey ultrón', 'oye ultrón' al inicio de la frase
        incluso cuando se ejecuta con `--no-wake`.
        """
        cleaned = text.strip()
        pattern = r"^\s*(?:hey\s+|oye\s+|hola\s+)?(?:ultr[oó]n|mult[oó]n)\b[\s,.:;!?-]*(.*)$"
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return cleaned

    def process_command(self, raw_query: str, detected_lang: Optional[str] = None) -> str:
        """
        Enruta una orden (en español, inglés o francés) hacia la habilidad correspondiente
        o hacia el cerebro generativo (LLM).
        """
        stripped = self._strip_wake_prefix(raw_query)
        query = stripped.lower().strip("¿?¡!., ")
        in_lang = detected_lang or detect_language(raw_query, default_lang=self.config.default_lang)
        out_lang = self.reply_lang(in_lang)

        # 0. Si el usuario solo dijo "Ultrón", "Hola Ultrón" o "¿Me escuchas?"
        if not query or query in (
            "hola",
            "hello",
            "hi",
            "hey",
            "buenas",
            "buenos días",
            "buenas tardes",
            "buenas noches",
            "me escuchas",
            "estás ahí",
            "estas ahi",
            "are you there",
            "can you hear me",
        ):
            return self.skills.acknowledge_presence(lang=out_lang)

        # 1. Salida / Modo offline
        if query in ("salir", "desconectar", "offline", "exit", "repos", "apágate", "apagate", "hasta luego"):
            msg = tr(out_lang, "offline", user=self.config.user_name)
            self.tts.speak(msg, lang=out_lang)
            return "EXIT"

        # 2. Visión Multimodal de Escritorio (Opción C: Debug, UX Audit, Biomedical/PID, General)
        vision_triggers = (
            "mira mi pantalla",
            "analiza mi pantalla",
            "qué hay en mi pantalla",
            "que hay en mi pantalla",
            "qué ves en mi pantalla",
            "corrige este error en pantalla",
            "audita el diseño",
            "analiza esta gráfica",
            "analiza esta grafica",
            "look at my screen",
            "analyze my screen",
            "what is on my screen",
            "what's on my screen",
            "debug my screen",
            "debug this error",
            "audit the ux",
            "analyze this pid",
        )
        if any(trigger in query for trigger in vision_triggers):
            return self.skills.analyze_screen(query=stripped, lang=out_lang)

        # 3. Telemetría: Top Procesos devoradores de RAM o CPU (Opción B)
        top_proc_triggers = (
            "qué consume mi ram",
            "que consume mi ram",
            "qué está consumiendo ram",
            "qué consume mi cpu",
            "procesos más pesados",
            "procesos mas pesados",
            "top processes",
            "what is eating my ram",
            "what's eating my ram",
            "what is using my ram",
            "what is using my cpu",
            "heavy processes",
        )
        if any(trigger in query for trigger in top_proc_triggers):
            sort_metric = "cpu" if "cpu" in query or "procesador" in query else "memory"
            return self.skills.top_processes(sort_by=sort_metric, lang=out_lang)

        # 4. Telemetría y Diagnóstico Completo del Sistema (Opción B)
        telemetry_triggers = (
            "estado del sistema",
            "diagnóstico del sistema",
            "diagnostico del sistema",
            "diagnóstico",
            "diagnostico",
            "analiza mi sistema",
            "analizar mi sistema",
            "analiza el sistema",
            "analiza mi pc",
            "analiza mi computador",
            "revisa mi sistema",
            "revisa mi pc",
            "telemetría",
            "telemetria",
            "cómo está mi pc",
            "como esta mi pc",
            "cómo va mi pc",
            "rendimiento del sistema",
            "uso de cpu",
            "uso de ram",
            "cuánta ram",
            "cuanta ram",
            "estado de la batería",
            "how is my pc running",
            "analyze my system",
            "analyze my pc",
            "check my system",
            "system status",
            "system health",
            "system diagnostics",
            "system telemetry",
            "cpu usage",
            "ram usage",
            "memory usage",
            "battery status",
        )
        if any(trigger in query for trigger in telemetry_triggers):
            return self.skills.system_telemetry(lang=out_lang)

        # 5. Control de Volumen y Ventanas del Escritorio
        if any(w in query for w in ("sube el volumen", "subir volumen", "volume up", "louder")):
            return self.skills.desktop_control("volume_up", lang=out_lang)
        if any(w in query for w in ("baja el volumen", "bajar volumen", "volume down", "quieter")):
            return self.skills.desktop_control("volume_down", lang=out_lang)
        if any(w in query for w in ("silencia", "mute", "quitar sonido")):
            return self.skills.desktop_control("volume_mute", lang=out_lang)
        if any(w in query for w in ("minimiza todo", "muestra el escritorio", "minimize all", "show desktop")):
            return self.skills.desktop_control("minimize_all", lang=out_lang)
        if any(w in query for w in ("cambia de ventana", "cambiar ventana", "switch window")):
            return self.skills.desktop_control("switch_window", lang=out_lang)

        # 6. Hora
        if any(w in query for w in ("qué hora", "que hora", "dime la hora", "la hora", "what time", "current time", "heure")):
            return self.skills.tell_time(lang=out_lang)

        # 7. Fecha
        if any(w in query for w in ("qué fecha", "que fecha", "qué día es hoy", "que dia es hoy", "what date", "today's date", "what day is today")):
            return self.skills.tell_date(lang=out_lang)

        # 8. Búsquedas directas o compuestas en YouTube ("abre youtube y busca música", "busca en youtube...", "pon en youtube...")
        if "youtube" in query:
            yt_compound = re.search(
                r"(?:busca|buscar|pon|poner|reproduce|reproducir|escuchar|search|play|for)\s+(?:en\s+youtube\s+)?(.+)$",
                query,
            )
            if yt_compound:
                term = yt_compound.group(1).replace("en youtube", "").strip()
                if term and term != "youtube":
                    return self.skills.search_youtube(term, lang=out_lang)

        # 9. Búsquedas directas o compuestas en Google ("abre google y busca...", "busca en google...")
        if "google" in query:
            gg_compound = re.search(
                r"(?:busca|buscar|investiga|investigar|googlea|search|for)\s+(?:en\s+google\s+)?(.+)$",
                query,
            )
            if gg_compound:
                term = gg_compound.group(1).replace("en google", "").strip()
                if term and term != "google":
                    return self.skills.search_google(term, lang=out_lang)

        # 10. Lanzador Universal: "abre <app/sitio/proyecto>" o "open <app/sitio/proyecto>"
        open_match = re.match(
            r"^(?:abre|abrir|ábreme|abreme|ejecuta|lanza|open|launch|start|ouvre)\s+(?:el\s+|la\s+|mi\s+|my\s+|the\s+)?(.+)$",
            query,
        )
        if open_match:
            target_to_open = open_match.group(1).strip()
            return self.skills.open_any_target(target_to_open, lang=out_lang)

        # 10. Wikipedia
        if "wikipedia" in query:
            return self.skills.search_wikipedia(query, lang=out_lang)

        # 11. Chistes
        if any(w in query for w in ("chiste", "joke", "blague", "hazme reír", "tell me a joke")):
            return self.skills.tell_joke(lang=out_lang)

        # 12. Notas persistentes
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

        # 13. Cambio de nombre del asistente
        if any(
            w in query
            for w in ("cambia tu nombre a", "cambiar nombre a", "change your name to", "llámate")
        ):
            for prefix in ("cambia tu nombre a", "cambiar nombre a", "change your name to", "llámate"):
                if prefix in query:
                    new_name = query.split(prefix, 1)[1].strip()
                    if new_name:
                        return self.skills.change_name(new_name.title(), lang=out_lang)

        # 14. Captura de pantalla simple
        if any(w in query for w in ("captura", "screenshot", "pantallazo", "capture")):
            return self.skills.take_screenshot(lang=out_lang)

        # 15. Música
        if any(w in query for w in ("música", "musica", "music", "musique", "spotify")):
            return self.skills.play_music(query, lang=out_lang)

        # 16. Control de energía del sistema
        if any(w in query for w in ("apagar sistema", "shutdown system", "extinction")):
            return self.skills.system_power("shutdown", lang=out_lang)

        if any(w in query for w in ("reiniciar sistema", "restart system", "redémarrage")):
            return self.skills.system_power("restart", lang=out_lang)

        # 17. Cerebro de IA Generativa (Gemini -> Ollama -> Cloud IA Gratuito)
        answer = self.brain.ask(
            prompt=stripped,
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
