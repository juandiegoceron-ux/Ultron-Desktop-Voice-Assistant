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

from ultron.agent_loop import UltronAgentLoop
from ultron.config import UltronConfig
from ultron.llm import UltronBrain
from ultron.memory import UltronMemory
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
        self.tts = UltronTTS(config=self.config, mute=mute)
        self.stt = UltronSTT(self.config, text_mode=text_mode)
        self.wake_detector = WakeWordDetector(
            wake_words=self.config.wake_words,
            enabled=self.config.wake_word_enabled,
        )
        self.skills = UltronSkills(self.config, self.tts)
        self.brain = UltronBrain(self.config)
        self.memory = UltronMemory(self.config)
        self.agent = UltronAgentLoop(self)
        self._last_skill_context: str = ""

    def _is_email_intent(self, query: str) -> bool:
        """Determina si la orden del usuario solicita abrir Gmail, redactar, dictar o preparar un correo electrónico."""
        # 1. Nombres clave de correo
        email_nouns = ("correo", "email", "mail", "gmail")
        has_email_noun = any(n in query for n in email_nouns)

        # 2. Verbos de acción (imperativos, infinitivos, subjuntivos y en inglés)
        action_verbs = (
            "redacta", "redactar", "redáctame", "redactame",
            "escribe", "escribir", "escríbeme", "escribeme", "escribas", "escriba",
            "envía", "envia", "enviar", "envíame", "enviame", "envíes", "envies",
            "manda", "mandar", "mándame", "mandame", "mandes",
            "abre", "abrir", "ábreme", "abreme", "abras", "abres",
            "nuevo", "nueva", "crea", "crear", "prepara", "preparar",
            "compose", "write", "send", "open", "draft",
        )
        has_action_verb = any(v in query for v in action_verbs)

        if has_email_noun and has_action_verb:
            return True

        # 3. Frases completas directas
        if any(
            p in query
            for p in (
                "enviar un correo", "enviar correo", "mandar un correo", "mandar correo",
                "redactar un correo", "redactar correo", "redacta un correo", "redacta correo",
                "escribir un correo", "escribir correo", "escribe un correo", "escribe correo",
                "envía un correo", "envia un correo", "manda un correo",
                "send email", "write email", "compose email", "open gmail",
                "abrir gmail", "abre gmail", "abrir el correo", "abre el correo",
                "abrir mi correo", "abre mi correo", "redacta un gmail", "redacta en gmail",
            )
        ):
            return True

        # 4. Estructura de destinatario y contenido ("va dirigido a ... y el mensaje debe decir ...")
        if re.search(r"\b(?:va\s+dirigido\s+a|dirigido\s+a)\b", query) and re.search(
            r"\b(?:mensaje|cuerpo|asunto|debe\s+decir|que\s+diga)\b", query
        ):
            return True

        # 5. Si el contexto inmediato previo fue redacción de correo
        if getattr(self, "_last_skill_context", "") == "compose_email":
            if any(w in query for w in ("dirigido a", "para ", "el mensaje", "asunto", "que diga", "destinatario")):
                return True

        return False

    def _is_organize_intent(self, query: str) -> bool:
        """
        Determina si la orden del usuario solicita organizar, ordenar, clasificar o limpiar
        archivos o carpetas (Descargas, Escritorio, Documentos o cualquier ruta explícita).
        """
        q = query.lower().strip()

        # 1. Si contiene una ruta explícita entre comillas o con letra de unidad/ruta
        has_explicit_path = bool(
            re.search(r'["\'][^"\']+["\']', query)
            or re.search(r'[a-zA-Z]:[\\/]', query)
            or re.search(r'(?:carpeta|directorio|ruta)\s*[:]', query, re.IGNORECASE)
        )

        # 2. Verbos de acción de organización
        action_verbs = (
            "organiza", "organizar", "organizo", "organízame", "organizame", "organices", "organice",
            "ordena", "ordenar", "ordeno", "ordéname", "ordename", "ordenes", "ordene",
            "limpia", "limpiar", "limpio", "límpiame", "limpiame", "limpies", "limpie",
            "clasifica", "clasificar", "clasifico", "clasifícame", "clasificame", "clasifiques", "clasifique",
            "acomoda", "acomodar", "acomodo", "acomódame", "acomodame",
            "organize", "clean", "sort", "tidy",
        )
        has_verb = any(re.search(rf"\b{v}\b", q) for v in action_verbs)

        if has_verb and has_explicit_path:
            return True

        # 3. Sustantivos de destino (carpetas estándar o palabras clave de archivos)
        target_nouns = (
            "carpeta", "carpetas", "directorio", "directorios", "archivos", "ficheros",
            "descarga", "descargas", "downloads", "download",
            "escritorio", "desktop",
            "documento", "documentos", "documents", "document",
            "foto", "fotos", "imagen", "imagenes", "imágenes", "pictures", "images",
            "musica", "música", "music",
            "video", "videos", "vídeos",
            "scans", "scan",
        )
        has_noun = any(n in q for n in target_nouns)

        if has_verb and has_noun:
            return True

        # 4. Frases directas comunes
        direct_phrases = (
            "organiza mi", "organiza mis", "organizar mi", "organizar mis",
            "ordena mi", "ordena mis", "ordenar mi", "ordenar mis",
            "limpia mi", "limpia mis", "limpiar mi", "limpiar mis",
            "clasifica mi", "clasifica mis", "clasificar mi", "clasificar mis",
            "organize my", "clean my", "sort my",
        )
        if any(p in q for p in direct_phrases):
            return True

        return False

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
        Elimina invocaciones como 'ultrón', 'hey ultrón', 'oye ultrón', y homófonos
        comunes de transcripción fonética ('el trono', 'al trono', 'a una ultron', 'el tron')
        al inicio de la frase incluso cuando se ejecuta con `--no-wake`.
        """
        cleaned = text.strip()
        pattern = (
            r"^\s*(?:hey\s+|oye\s+|hola\s+|ok\s+|a\s+una\s+|a\s+un\s+|al\s+|el\s+)?"
            r"(?:ultr[oó]n|mult[oó]n|trono|tron|trozo|oultron|oltron|el\s+trono|al\s+trono)"
            r"\b[\s,.:;!?-]*(.*)$"
        )
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

        # 1. Identidad de Ultrón ("¿qué eres tú?", "¿quién eres?", "preséntate")
        if any(
            w in query
            for w in (
                "qué eres tú",
                "que eres tu",
                "quién eres",
                "quien eres",
                "preséntate",
                "presentate",
                "who are you",
                "what are you",
            )
        ):
            msg = (
                f"Soy {self.config.load_assistant_name()}, tu asistente de escritorio con inteligencia artificial, "
                f"telemetría en tiempo real y visión multimodal, diseñado a medida para ti, {self.config.user_name}."
            )
            self.tts.speak(msg, lang=out_lang)
            return msg

        # 1.5 Salida / Modo offline
        if query in ("salir", "desconectar", "offline", "exit", "repos", "apágate", "apagate", "hasta luego"):
            msg = tr(out_lang, "offline", user=self.config.user_name)
            self.tts.speak(msg, lang=out_lang)
            return "EXIT"

        # 1.8 Memoria Episódica y Semántica a Largo Plazo (Opción B)
        # Recordar un hecho explícito ("recuerda que...", "guarda en memoria que...")
        remember_match = re.match(
            r"^(?:recuerda\s+que|recuerda|guarda\s+en\s+memoria\s+que|guarda\s+en\s+tu\s+memoria\s+que|memoriza\s+que|memoriza|remember\s+that|remember)\s*[:,-]?\s*(.+)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if remember_match:
            fact = remember_match.group(1).strip()
            if fact:
                msg = self.memory.remember(fact)
                self.tts.speak(msg, lang=out_lang)
                return msg

        # Consultar o recuperar de memoria ("qué recuerdas de...", "recuerdas algo de...", "qué tienes en memoria de...")
        recall_match = re.match(
            r"^(?:qu[eé]\s+recuerdas\s+de|qu[eé]\s+recuerdas\s+sobre|recuerdas\s+algo\s+de|recuerdas\s+algo\s+sobre|qu[eé]\s+tienes\s+en\s+memoria\s+de|qu[eé]\s+tienes\s+en\s+memoria\s+sobre|consulta\s+tu\s+memoria\s+sobre|what\s+do\s+you\s+remember\s+about)\s*[:,-]?\s*(.+)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if recall_match:
            topic = recall_match.group(1).strip("¿?¡! ")
            facts = self.memory.recall(topic)
            if facts:
                msg = f"En mi memoria tengo registrado sobre {topic}: {'; '.join(facts)}."
            else:
                msg = f"No tengo recuerdos registrados sobre {topic}, {self.config.user_name}."
            self.tts.speak(msg, lang=out_lang)
            return msg

        # Resumen de memoria activa / perfil
        if any(w in query for w in (
            "resumen de memoria", "resumen de tu memoria", "qué recuerdas", "que recuerdas",
            "qué tienes en memoria", "que tienes en memoria", "mi perfil", "qué sabes de mí", "que sabes de mi",
            "memory summary", "what do you remember"
        )):
            msg = self.memory.summary()
            self.tts.speak(msg, lang=out_lang)
            return msg

        # Olvidar un hecho ("olvida que...", "borra de tu memoria...")
        forget_match = re.match(
            r"^(?:olvida\s+que|olvida|borra\s+de\s+tu\s+memoria\s+que|borra\s+de\s+tu\s+memoria|elimina\s+de\s+tu\s+memoria|forget\s+that|forget)\s*[:,-]?\s*(.+)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if forget_match:
            fact = forget_match.group(1).strip()
            if fact:
                msg = self.memory.forget(fact)
                self.tts.speak(msg, lang=out_lang)
                return msg

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

        # 2.5 Jarvis Pro: Organizador Inteligente de Archivos por Voz o Rutas Explícitas
        if self._is_organize_intent(stripped):
            return self.skills.organize_files(query=stripped, lang=out_lang)

        # 2.6 Jarvis Pro: Edición In-Place de Portapapeles / Texto Seleccionado
        has_clipboard_kw = any(
            w in query
            for w in (
                "texto copiado",
                "portapapeles",
                "lo que copié",
                "lo que copie",
                "texto seleccionado",
                "copied text",
                "clipboard",
            )
        )
        has_action_kw = any(
            w in query
            for w in (
                "mejora",
                "mejor en",
                "mejorar",
                "corrige",
                "corregir",
                "traduce",
                "traducir",
                "formal",
                "refactoriza",
                "refactorizar",
                "resume",
                "resumir",
                "edita",
                "editar",
                "limpia",
                "limpiar",
                "arregla",
                "arreglar",
                "improve",
                "translate",
                "edit",
                "clean",
            )
        )
        if (has_clipboard_kw and has_action_kw) or any(
            trigger in query
            for trigger in (
                "mejora este texto",
                "corrige este texto",
                "edita este texto",
                "traduce este texto",
                "refactoriza este código",
            )
        ):
            return self.skills.edit_clipboard_text(instruction=stripped, lang=out_lang)

        # 2.7 Jarvis Pro: Dictado Inteligente con Auto-Corrección ("dicta ...", "escribe esto ...")
        dictate_match = re.match(
            r"^(?:dicta|dictar|modo dictado|escribe esto|pega esto|dictate)\s*[:,-]?\s*(.+)$",
            stripped,
            flags=re.IGNORECASE,
        )
        if dictate_match:
            raw_dictation = dictate_match.group(1).strip()
            if raw_dictation:
                return self.skills.smart_dictate(raw_text=raw_dictation, lang=out_lang)


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

        # 7.5 Google Calendar ("¿tienes acceso a mi google calendar?", "revisa mi calendario", "mi agenda")
        if any(w in query for w in ("google calendar", "mi calendario", "mi agenda")) and not query.startswith(("abre ", "abrir ", "open ")):
            self.skills.open_any_target("google calendar", lang=out_lang)
            msg = (
                f"Te acabo de abrir Google Calendar en tu navegador, {self.config.user_name}. "
                "Una vez esté en pantalla, dime 'Ultrón, mira mi pantalla' para leer tu agenda con Visión Multimodal, "
                "o dime 'anota ...' para guardar un recordatorio local."
            )
            self.tts.speak(msg, lang=out_lang)
            return msg

        # 7.8 Envío y Redacción de Correo Electrónico ("redacta un correo en gmail", "escribe un correo a...", etc.)
        if self._is_email_intent(query):
            self._last_skill_context = "compose_email"
            return self.skills.compose_email(query=stripped, lang=out_lang)

        # 7.9 Explicación Instantánea Local de Control PID (Biomédica / Automatización)
        if any(
            w in query
            for w in (
                "qué sabes del pid",
                "que sabes del pid",
                "qué es un pid",
                "que es un pid",
                "controlador pid",
                "control pid",
            )
        ) or query in ("pid", "el pid"):
            return self.skills.explain_pid(lang=out_lang)

        # 7.8 Controles multimedia universales del sistema (Pausa, Reanudar, Siguiente, Anterior, Volumen)
        if any(w in query for w in (
            "pausa la música", "pausar la música", "pausa la musica", "pausar la musica",
            "pausa música", "pausar musica", "pausa spotify", "para la música", "para la musica",
            "detén la música", "deten la musica", "pause music", "stop music",
        )) or query in ("pausa", "pausar", "pause"):
            return self.skills.pause_media(lang=out_lang)

        if any(w in query for w in (
            "reanuda la música", "reanudar la música", "reanuda la musica", "reanudar la musica",
            "continúa la música", "continua la musica", "resume music",
        )) or query in ("reanudar", "reanuda", "resume"):
            return self.skills.resume_media(lang=out_lang)

        if any(w in query for w in (
            "siguiente canción", "siguiente cancion", "pasa la canción", "pasa la cancion",
            "pasa de canción", "pasa de cancion", "cambia la canción", "cambia la cancion",
            "cambia de canción", "cambia de cancion", "next song", "next track", "skip",
        )) or query in ("siguiente", "next", "skip"):
            return self.skills.next_track(lang=out_lang)

        if any(w in query for w in (
            "canción anterior", "cancion anterior", "anterior canción", "anterior cancion",
            "canción previa", "cancion previa", "prev track", "previous track",
        )) or query in ("anterior", "previous"):
            return self.skills.prev_track(lang=out_lang)

        if any(w in query for w in (
            "sube el volumen", "aumenta el volumen", "más volumen", "mas volumen", "subir volumen", "volume up",
        )):
            return self.skills.media_volume_up(lang=out_lang)

        if any(w in query for w in (
            "baja el volumen", "disminuye el volumen", "menos volumen", "bajar volumen", "volume down",
        )):
            return self.skills.media_volume_down(lang=out_lang)

        # 8. Spotify y Reproducción Musical Directa
        # "abre spotify y reproduce música", "reproduce música en spotify", "pon música en spotify", "pon música", "reproduce a ryan castro en spotify"
        is_bare_spotify_open = query in ("abre spotify", "abrir spotify", "open spotify", "spotify")
        is_music_word = any(w in query for w in ("música", "musica", "music", "canción", "cancion", "playlist", "temas"))
        has_play_verb = any(w in query for w in ("reproduce", "reproducir", "pon", "poner", "play", "dale play", "toca", "tocar", "escuchar", "escucha"))

        if not is_bare_spotify_open and ("spotify" in query or (is_music_word and has_play_verb)):
            return self.skills.play_spotify_music(query, lang=out_lang)

        # 8.5 Búsquedas directas o compuestas en YouTube ("abre youtube y busca música", "busca en youtube...", "pon en youtube...")
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
                prompt_msg = tr(out_lang, "note_asked")
                if self.tts.mute or self.stt.text_mode:
                    return prompt_msg
                self.tts.speak(prompt_msg, lang=out_lang)
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

        # 16.5 Bucle Agéntico Autónomo ReAct / Tool-Use (Inspirado en DeepSeek Harness)
        # Si la orden no coincidió con una regla previa, el agente razona si requiere
        # herramientas del sistema (organizar carpetas, redactar correos, telemetría, multimedia, memoria, etc.)
        agent_reply = self.agent.decide_and_execute(query=stripped, lang=out_lang)
        if agent_reply:
            return agent_reply

        # 17. Cerebro de IA Generativa (Gemini -> Ollama -> Cloud IA Gratuito)
        mem_ctx = self.memory.get_context_for_prompt()
        answer = self.brain.ask(
            prompt=stripped,
            input_lang=in_lang,
            force_spanish_reply=self.force_spanish_reply,
            memory_context=mem_ctx,
        )
        self.tts.speak(answer, lang=out_lang)
        self.memory.record_episode(user_query=stripped, action="conversation", result_summary=answer)
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
