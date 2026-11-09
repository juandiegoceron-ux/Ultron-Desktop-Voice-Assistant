#!/usr/bin/env python3
"""
Punto de entrada principal de Ultrón v3.0 - Asistente de Voz, Telemetría y Visión Multimodal
Personalizado para Juan Diego Cerón Duque (@juandiegoceron-ux).
"""

from __future__ import annotations

import argparse
import logging

from ultron.assistant import UltronAssistant
from ultron.config import UltronConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ultrón v3.0: Asistente de Voz de Escritorio con IA Generativa, "
            "Telemetría en Tiempo Real, Visión Multimodal, Whisper Offline y Wake-Word."
        )
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Ejecuta Ultrón en modo interactivo por consola (sin requerir micrófono).",
    )
    parser.add_argument(
        "--no-wake",
        action="store_true",
        help="Desactiva la palabra de activación ('Ultrón') para procesar cada frase directamente.",
    )
    parser.add_argument(
        "--mute",
        action="store_true",
        help="Desactiva la síntesis de voz por altavoz (solo salida en pantalla).",
    )
    parser.add_argument(
        "--command",
        type=str,
        default="",
        help="Ejecuta un único comando directo y termina.",
    )
    parser.add_argument(
        "--telemetry",
        action="store_true",
        help="Ejecuta un diagnóstico completo de hardware y procesos en tiempo real y termina.",
    )
    parser.add_argument(
        "--vision",
        type=str,
        default="",
        help="Captura la pantalla activa y la analiza con Visión Multimodal según tu consulta.",
    )
    parser.add_argument(
        "--vision-mode",
        type=str,
        default=None,
        choices=["general", "debug", "ux_audit", "biomedical_pid"],
        help="Modo especializado opcional para el análisis visual (--vision).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    for noisy_logger in ("comtypes", "httpx", "httpx2", "httpcore", "httpcore2", "huggingface_hub", "urllib3"):
        logging.getLogger(noisy_logger).setLevel(logging.ERROR)

    args = parse_args()
    config = UltronConfig()

    if args.no_wake:
        config.wake_word_enabled = False

    assistant = UltronAssistant(
        config=config,
        text_mode=args.text,
        mute=args.mute,
        force_spanish_reply=True,
    )

    if args.telemetry:
        assistant.skills.system_telemetry(lang="es")
        return

    if args.vision:
        assistant.skills.analyze_screen(query=args.vision, mode=args.vision_mode, lang="es")
        return

    if args.command:
        assistant.process_command(args.command)
        return

    assistant.run_forever()


if __name__ == "__main__":
    main()
