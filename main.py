#!/usr/bin/env python3
"""
Punto de entrada principal de Ultrón - Asistente de Voz Personalizado para Juan Diego Cerón Duque.
"""

from __future__ import annotations

import argparse
import logging

from ultron.assistant import UltronAssistant
from ultron.config import UltronConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ultrón: Asistente de Voz de Escritorio con IA Generativa, Whisper Offline y Wake-Word."
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
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
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

    if args.command:
        assistant.process_command(args.command)
        return

    assistant.run_forever()


if __name__ == "__main__":
    main()
