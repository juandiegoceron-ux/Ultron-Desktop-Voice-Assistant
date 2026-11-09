"""
Cerebro de IA Generativa de Ultrón (3 Niveles de Respaldo con Reintentos Automáticos):
1. Google Gemini (`google-genai`) si `GEMINI_API_KEY` está configurada.
2. Ollama Local (`http://localhost:11434`) si está corriendo en la máquina.
3. Motor Cloud IA Gratuito Zero-Config (`Pollinations AI`) con reintentos automáticos
   para que jamás falle por límites de tasa temporales.
"""

from __future__ import annotations

import logging
import random
import time
import urllib.parse
from typing import Optional

import requests

from ultron.config import UltronConfig
from ultron.strings import tr

logger = logging.getLogger("ultron.llm")


def build_system_prompt(
    config: UltronConfig,
    response_lang: str = "es",
    input_lang: str = "es",
) -> str:
    """
    Construye el prompt de sistema personalizado para Juan Diego Cerón Duque.
    Activa el modo tutor de inglés únicamente cuando Juan Diego habla en inglés (`input_lang == "en"`).
    """
    lang_instruction = (
        "Responde SIEMPRE en español claro, conciso y natural (incluso si el usuario te habla en inglés)."
        if response_lang == "es"
        else "Respond concisely and naturally in the requested language."
    )
    english_coach_clause = (
        "- Juan Diego acaba de hablarte en INGLÉS para practicar su fluidez: primero responde a su consulta en español, "
        "y al final añade una sola línea breve felicitándolo o dándole un consejo natural si hubo algún detalle gramatical en su inglés.\n"
        if input_lang == "en"
        else "- Juan Diego te está hablando en español: NO le des correcciones de ortografía ni de mayúsculas porque su texto proviene de un micrófono de voz.\n"
    )
    return (
        f"Eres {config.assistant_name}, el asistente de escritorio con inteligencia artificial personal de "
        f"{config.user_name} (Juan Diego Cerón Duque, @juandiegoceron-ux).\n"
        "Contexto sobre tu creador y usuario principal:\n"
        "- Estudiante de Ingeniería Biomédica y Desarrollador Full Stack & Mobile en Colombia.\n"
        "- Especialista en React, TypeScript, Three.js/WebGL, Flutter, Supabase, PostgreSQL y sistemas de control PID en Arduino.\n"
        "- Creador de proyectos de alto impacto como NutriCoach Pro, Inventario Web Pro (INV. PRO) y controladores PID Bola-Viga.\n"
        "- Filosofía de trabajo: 'El buen diseño es invisible; el buen código también.'\n"
        "- Tienes personalidad estilo Jarvis/Ultrón: leal, brillante, directo, ingenioso y enfocado en ingeniería de primer nivel.\n"
        f"{english_coach_clause}"
        f"{lang_instruction}\n"
        "IMPORTANTE: Mantén tus respuestas breves (máximo 2 a 3 oraciones fluidas, sin bloques de markdown ni asteriscos) "
        "porque serán leídas en voz alta por el altavoz de su computadora."
    )


class UltronBrain:
    """Cliente unificado de IA Generativa (Gemini API + Ollama Local + Zero-Config Cloud con Reintento)."""

    def __init__(self, config: UltronConfig) -> None:
        self.config = config

    def ask(self, prompt: str, input_lang: str = "es", force_spanish_reply: bool = True) -> str:
        """
        Envía una consulta abierta al LLM disponible.
        Por preferencia de Juan Diego, responde en español incluso cuando él practica en inglés.
        """
        reply_lang = "es" if force_spanish_reply else input_lang
        system_prompt = build_system_prompt(
            self.config, response_lang=reply_lang, input_lang=input_lang
        )

        # 1. Intentar con Google Gemini si el usuario configuró su GEMINI_API_KEY real
        if self.config.llm_provider == "gemini" and self.config.gemini_api_key:
            reply = self._ask_gemini(prompt, system_prompt)
            if reply:
                return self._clean_for_tts(reply)

        # 2. Intentar con Ollama local si está activo en localhost:11434
        if self.config.llm_provider == "ollama" or not self.config.gemini_api_key:
            reply = self._ask_ollama(prompt, system_prompt)
            if reply:
                return self._clean_for_tts(reply)

        # 3. Motor Cloud IA Gratuito Zero-Config con reintentos automáticos
        reply = self._ask_free_cloud_llm(prompt, system_prompt)
        if reply:
            return self._clean_for_tts(reply)

        return tr(reply_lang, "llm_fallback_unavailable")

    def generate_raw(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 400,
    ) -> Optional[str]:
        """
        Genera una respuesta directa del LLM sin preámbulos de conversación para
        edición in-place de texto, enrutamiento de herramientas o formateo estructurado.
        """
        # 1. Gemini
        if self.config.llm_provider == "gemini" and self.config.gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.config.gemini_api_key)
                response = client.models.generate_content(
                    model=self.config.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as exc:
                logger.debug("Gemini generate_raw failed: %s", exc)

        # 2. Ollama
        if self.config.llm_provider == "ollama" or not self.config.gemini_api_key:
            try:
                url = f"{self.config.ollama_base_url.rstrip('/')}/api/generate"
                payload = {
                    "model": self.config.ollama_model,
                    "system": system_prompt,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature},
                }
                resp = requests.post(url, json=payload, timeout=4)
                if resp.status_code == 200:
                    answer = resp.json().get("response", "").strip()
                    if answer:
                        return answer
            except Exception as exc:
                logger.debug("Ollama generate_raw failed: %s", exc)

        # 3. Cloud LLM Fallback
        return self._ask_free_cloud_llm(prompt, system_prompt)

    @staticmethod
    def _clean_for_tts(text: str) -> str:
        """Limpia símbolos de markdown (`**`, `#`, backticks) para que la voz de Windows lea con naturalidad."""
        cleaned = (
            text.replace("**", "")
            .replace("__", "")
            .replace("`", "")
            .replace("###", "")
            .replace("##", "")
        )
        return " ".join(cleaned.split()).strip()

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
            resp = requests.post(url, json=payload, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("response", "").strip()
                if answer:
                    return answer
        except requests.RequestException as exc:
            logger.debug("Ollama local no accesible (%s).", exc)
        return None

    def _ask_free_cloud_llm(self, prompt: str, system_prompt: str) -> Optional[str]:
        """
        Motor LLM gratuito sin configuración con hasta 2 reintentos y doble endpoint
        para evitar fallos por saturación momentánea.
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "UltronDesktopAssistant/3.2",
        }
        for attempt in range(2):
            try:
                payload = {
                    "model": "openai",
                    "seed": random.randint(1, 999999),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.6,
                }
                resp = requests.post(
                    "https://text.pollinations.ai/openai",
                    json=payload,
                    headers=headers,
                    timeout=14,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or []
                    if choices:
                        content = choices[0].get("message", {}).get("content", "").strip()
                        if content:
                            return content
            except Exception as exc:
                logger.debug("Intento %d fallido en endpoint primario: %s", attempt + 1, exc)

            try:
                encoded_q = urllib.parse.quote(prompt)
                encoded_sys = urllib.parse.quote(system_prompt)
                url = f"https://text.pollinations.ai/{encoded_q}?model=openai&seed={random.randint(1, 99999)}&system={encoded_sys}"
                resp2 = requests.get(url, headers=headers, timeout=14)
                if resp2.status_code == 200 and resp2.text.strip():
                    return resp2.text.strip()
            except Exception as exc:
                logger.debug("Intento %d fallido en endpoint secundario: %s", attempt + 1, exc)

            if attempt == 0:
                time.sleep(0.8)

        return None
