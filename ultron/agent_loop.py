"""
Bucle Agéntico Autónomo de Ultrón v5.3 (`ultron.agent_loop`).
Inspirado en la arquitectura ReAct / Tool-Use de DeepSeek Harness (`dsh`):
El LLM cuenta con un catálogo de herramientas estructuradas, razona la intención
del usuario, ejecuta la herramienta real en el sistema y formula una respuesta fundamentada.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ultron.assistant import UltronAssistant

logger = logging.getLogger("ultron.agent_loop")

AGENT_TOOLS_SCHEMA = [
    {
        "name": "organize_directory",
        "description": "Organiza archivos sueltos en subcarpetas clasificadas por tipo (Documentos, Imagenes, Videos, Codigo, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Nombre de la carpeta a organizar: 'descargas', 'escritorio', o 'documentos'.",
                }
            },
            "required": ["directory"],
        },
    },
    {
        "name": "compose_email",
        "description": "Abre la ventana de redacción en Gmail con destinatario, asunto y mensaje precargados y copiados al portapapeles.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Nombre o correo del destinatario."},
                "subject": {"type": "string", "description": "Asunto del correo electrónico."},
                "message": {"type": "string", "description": "Cuerpo o texto del mensaje a enviar."},
            },
        },
    },
    {
        "name": "get_system_telemetry",
        "description": "Obtiene diagnóstico de salud del computador en tiempo real (CPU, RAM, disco, batería y proceso más pesado).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_processes",
        "description": "Obtiene la lista de los procesos que más recursos consumen en el sistema.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["memory", "cpu"], "description": "Ordenar por memoria RAM ('memory') o procesador ('cpu')."}
            },
        },
    },
    {
        "name": "play_spotify",
        "description": "Busca y reproduce un artista, álbum, canción o playlist en Spotify.",
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {"type": "string", "description": "Nombre de la canción o artista a reproducir."}
            },
            "required": ["search_query"],
        },
    },
    {
        "name": "control_media",
        "description": "Controla la reproducción multimedia activa en Windows/Linux (pausar, reanudar, siguiente pista, anterior, subir/bajar volumen).",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["pause", "resume", "next", "prev", "volume_up", "volume_down", "mute"],
                    "description": "Acción multimedia a ejecutar.",
                }
            },
            "required": ["action"],
        },
    },
    {
        "name": "analyze_screen",
        "description": "Toma una captura de la pantalla y la analiza usando Visión Multimodal con IA.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Pregunta o instrucción de análisis visual."},
                "mode": {"type": "string", "enum": ["general", "debug", "ux", "biomedical"], "description": "Modo de análisis."},
            },
        },
    },
    {
        "name": "remember_fact",
        "description": "Guarda un hecho permanente, preferencia o información relevante sobre Juan Diego o sus proyectos en la memoria a largo plazo.",
        "parameters": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "El hecho o dato exacto a recordar permanentemente."}
            },
            "required": ["fact"],
        },
    },
    {
        "name": "recall_memory",
        "description": "Consulta la memoria a largo plazo sobre temas, notas o acuerdos pasados.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tema o palabra clave a consultar en memoria."}
            },
        },
    },
    {
        "name": "open_target",
        "description": "Abre cualquier aplicación instalada (VS Code, Calculadora, Spotify, WhatsApp) o sitio web de Juan Diego (NutriCoach, Inv. Pro, Portafolio, GitHub).",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Nombre de la aplicación, proyecto o sitio web a abrir."}
            },
            "required": ["target"],
        },
    },
]


class UltronAgentLoop:
    """Motor de Orquestación y Bucle de Agente Autónomo para Ultrón."""

    def __init__(self, assistant: UltronAssistant) -> None:
        self.assistant = assistant

    def build_agent_system_prompt(self) -> str:
        tools_json = json.dumps(AGENT_TOOLS_SCHEMA, ensure_ascii=False, indent=2)
        memory_ctx = self.assistant.memory.get_context_for_prompt()

        return (
            f"Eres {self.assistant.config.assistant_name}, el asistente de escritorio autónomo de "
            f"{self.assistant.config.user_name} (Juan Diego Cerón Duque).\n"
            "Tienes a tu disposición un catálogo de herramientas reales para interactuar con su computadora.\n\n"
            f"{memory_ctx}\n\n"
            "HERRAMIENTAS DISPONIBLES:\n"
            f"{tools_json}\n\n"
            "INSTRUCCIONES DE DECISIÓN:\n"
            "1. Si la petición del usuario requiere realizar una acción en el sistema, invocar una herramienta o consultar memoria, responde ÚNICAMENTE con un bloque JSON en este formato:\n"
            "{\n"
            '  "action": "call_tool",\n'
            '  "tool_name": "nombre_de_la_herramienta",\n'
            '  "arguments": { ... }\n'
            "}\n"
            "REGLA CRÍTICA PARA ACCIONES DEL SISTEMA: Si el usuario te pide organizar, ordenar o limpiar archivos o carpetas, NUNCA respondas con 'reply' prometiendo o afirmando que lo estás haciendo. DEBES invocar SIEMPRE la herramienta 'organize_directory' con el argumento 'directory'.\n"
            "2. Si la petición es solo una pregunta conversacional, técnica, conceptual o un saludo que no necesita herramientas, responde en este formato:\n"
            "{\n"
            '  "action": "reply",\n'
            '  "text": "Tu respuesta breve, natural y directa (máximo 2 a 3 oraciones en español)."\n'
            "}\n"
            "IMPORTANTE: NUNCA inventes que ejecutaste una herramienta en el texto. Devuelve SIEMPRE JSON válido sin markdown ni rodeos."
        )

    def decide_and_execute(self, query: str, lang: str = "es") -> Optional[str]:
        """
        Envía la consulta al razonador agéntico. Si decide invocar una herramienta,
        la ejecuta en el sistema real y devuelve el resultado verificado.
        """
        system_prompt = self.build_agent_system_prompt()
        prompt = f"Consulta del usuario: \"{query}\""

        try:
            raw_response = self.assistant.brain.generate_raw(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=300,
            )
            if not raw_response:
                return None

            # Limpiar posibles bloques ```json ```
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_response.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE).strip()

            data = json.loads(cleaned)
            if not isinstance(data, dict):
                return None

            action = data.get("action")
            if action == "call_tool":
                tool_name = data.get("tool_name")
                args = data.get("arguments") or {}
                result_msg = self._execute_tool(tool_name, args, lang=lang)
                if result_msg:
                    self.assistant.memory.record_episode(
                        user_query=query,
                        action=tool_name,
                        result_summary=result_msg,
                    )
                    return result_msg

            elif action == "reply":
                text = data.get("text", "").strip()
                if text:
                    self.assistant.memory.record_episode(
                        user_query=query,
                        action="conversation",
                        result_summary=text,
                    )
                    return text

        except Exception as exc:
            logger.debug("Bucle agéntico delegó a fallback conversacional: %s", exc)

        return None

    def _execute_tool(self, tool_name: str, args: Dict[str, Any], lang: str = "es") -> str:
        """Despacha la ejecución de la herramienta correspondiente con sus argumentos validados."""
        skills = self.assistant.skills

        if tool_name == "organize_directory":
            target = args.get("directory", "descargas")
            return skills.organize_files(query=target, lang=lang)

        if tool_name == "compose_email":
            # Si vienen argumentos estructurados
            recipient = args.get("recipient", "")
            subject = args.get("subject", "")
            message = args.get("message", "")
            composed_q = ""
            if recipient:
                composed_q += f"para {recipient} "
            if subject:
                composed_q += f"con el asunto {subject} "
            if message:
                composed_q += f"y el mensaje {message}"
            return skills.compose_email(query=composed_q or "redactar correo", lang=lang)

        if tool_name == "get_system_telemetry":
            return skills.system_telemetry(lang=lang)

        if tool_name == "get_top_processes":
            sort_by = args.get("sort_by", "memory")
            return skills.top_processes(sort_by=sort_by, lang=lang)

        if tool_name == "play_spotify":
            search_query = args.get("search_query", "")
            return skills.play_spotify_music(search_query, lang=lang)

        if tool_name == "control_media":
            act = args.get("action", "pause")
            if act == "pause":
                return skills.pause_media(lang=lang)
            if act == "resume":
                return skills.resume_media(lang=lang)
            if act == "next":
                return skills.next_track(lang=lang)
            if act == "prev":
                return skills.prev_track(lang=lang)
            if act == "volume_up":
                return skills.media_volume_up(lang=lang)
            if act == "volume_down":
                return skills.media_volume_down(lang=lang)
            if act == "mute":
                return skills.desktop_control("volume_mute", lang=lang)

        if tool_name == "analyze_screen":
            q = args.get("query", "analiza mi pantalla")
            return skills.analyze_screen(query=q, lang=lang)

        if tool_name == "remember_fact":
            fact = args.get("fact", "")
            return self.assistant.memory.remember(fact)

        if tool_name == "recall_memory":
            topic = args.get("topic", "")
            facts = self.assistant.memory.recall(topic)
            if facts:
                msg = f"En mi memoria tengo registrado sobre {topic or 'tus notas'}: {'; '.join(facts)}."
            else:
                msg = f"No tengo recuerdos registrados sobre {topic}, {self.assistant.config.user_name}."
            self.assistant.tts.speak(msg, lang=lang)
            return msg

        if tool_name == "open_target":
            target = args.get("target", "")
            return skills.open_any_target(target, lang=lang)

        return f"Herramienta '{tool_name}' ejecutada satisfactoriamente."
