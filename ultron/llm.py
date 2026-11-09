"""
Cerebro de IA Generativa de Ultrón (Paso 1 de la hoja de ruta).
Soporta Google Gemini (`google-genai`) y modelos locales vía Ollama (`http://localhost:11434`),
con un System Prompt personalizado para Juan Diego Cerón Duque.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from ultron.config import UltronConfig
from ultron.strings import tr

logger = logging.getLogger("ultron.llm")


def build_system_prompt(config: UltronConfig, response_lang: str = "es") -> str:
    """
    Construye el prompt de sistema personalizado para Juan Diego Cerón Duque.
    """
    lang_instruction = (
        "Responde SIEMPRE en español claro, conciso y natural (incluso si el usuario te habla en inglés para practicar)."
        if response_lang == "es"
        else "Respond concisely and naturally in the requested language."
    )
    return (
        f"Eres {config.assistant_name}, el asistente de escritorio con inteligencia artificial personal de "
        f"{config.user_name} (Juan Diego Cerón Duque, @juandiegoceron-ux).\n"
        "Contexto sobre tu creador y usuario principal:\n"
        "- Estudiante de Ingeniería Biomédica y Desarrollador Full Stack & Mobile en Colombia.\n"
        "- Especialista en React, TypeScript, Three.js/WebGL, Flutter, Supabase, PostgreSQL y sistemas de control PID en Arduino.\n"
        "- Creador de proyectos de alto impacto como NutriCoach Pro, Inventario Web Pro (INV. PRO) y controladores PID Bola-Viga.\n"
        "- Filosofía de trabajo: 'El buen diseño es invisible; el buen código también.'\n"
        "- Juan Diego suele hablarte en inglés para practicar su fluidez; comprende perfectamente su inglés, "
        "y si notas una oportunidad breve y amigable de mejora gramatical en su frase en inglés, puedes dársela en una línea corta "
        "después de responder a su consulta en español.\n"
        f"{lang_instruction}\n"
        "Mantén tus respuestas breves (máximo 2-3 oraciones) porque serán leídas en voz alta por un motor Text-to-Speech."
    )


class UltronBrain:
    """Cliente unificado de IA Generativa (Gemini API + Ollama Local)."""

    def __init__(self, config: UltronConfig) -> None:
        self.config = config

    def ask(self, prompt: str, input_lang: str = "es", force_spanish_reply: bool = True) -> str:
        """
        Envía una consulta abierta al LLM configurado (Gemini u Ollama).
        Por preferencia de Juan Diego, responde en español incluso cuando él practica en inglés.
        """
        reply_lang = "es" if force_spanish_reply else input_lang
        system_prompt = build_system_prompt(self.config, response_lang=reply_lang)

        if self.config.llm_provider == "gemini" and self.config.gemini_api_key:
            reply = self._ask_gemini(prompt, system_prompt)
            if reply:
                return reply

        if self.config.llm_provider == "ollama" or not self.config.gemini_api_key:
            reply = self._ask_ollama(prompt, system_prompt)
            if reply:
                return reply

        return tr(reply_lang, "llm_fallback_unavailable")

    def _ask_gemini(self, prompt: str, system_prompt: str) -> Optional[str]:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.config.gemini_api_key)
            response = client.models.generate_content(
                model=self.config.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.6,
                    max_output_tokens=250,
                ),
            )
            if response and response.text:
                return response.text.strip()
        except Exception as exc:
            logger.warning("Error consultando Google Gemini: %s", exc)
        return None

    def _ask_ollama(self, prompt: str, system_prompt: str) -> Optional[str]:
        try:
            url = f"{self.config.ollama_base_url.rstrip('/')}/api/generate"
            payload = {
                "model": self.config.ollama_model,
                "system": system_prompt,
                "prompt": prompt,
                "stream": False,
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("response", "").strip()
                if answer:
                    return answer
        except requests.RequestException as exc:
            logger.debug("Ollama local no accesible (%s).", exc)
        return None
