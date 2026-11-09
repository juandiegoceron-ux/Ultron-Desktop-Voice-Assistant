"""
Suite de pruebas unitarias e integración para validar los 6 pilares de Ultrón v3.0:
1. Configuración y personalización para Juan Diego Cerón Duque.
2. Detección de Wake-Word ("Ultrón" / "Hey Ultrón").
3. Detección inteligente de idioma (Inglés de entrada -> Español de respuesta).
4. Habilidades restauradas (notas JSON, chistes, renombrado, fecha/hora).
5. Telemetría del sistema en tiempo real y detección de procesos pesados por voz.
6. Visión Multimodal de Escritorio integrada en el asistente.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ultron.assistant import UltronAssistant
from ultron.config import UltronConfig
from ultron.strings import detect_language
from ultron.wakeword import WakeWordDetector


class TestUltronAssistant(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        base = Path(self.tmp_dir.name)
        self.config = UltronConfig(
            assistant_name="Ultrón",
            user_name="Juan Diego",
            name_file=base / "assistant_name.txt",
            notes_file=base / "notes.json",
            screenshots_dir=base / "screenshots",
        )
        self.assistant = UltronAssistant(
            config=self.config,
            text_mode=True,
            mute=True,
            force_spanish_reply=True,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_wake_word_detection_and_command_extraction(self) -> None:
        detector = WakeWordDetector(
            wake_words=["ultron", "ultrón", "hey ultron", "oye ultrón"],
            enabled=True,
        )
        m1 = detector.check_transcript("Hey Ultron, what time is it?")
        self.assertTrue(m1.triggered)
        self.assertEqual(m1.wake_word, "hey ultron")
        self.assertEqual(m1.remaining_command, "what time is it?")

        m2 = detector.check_transcript("Ultrón, abre mi portafolio")
        self.assertTrue(m2.triggered)
        self.assertEqual(m2.remaining_command, "abre mi portafolio")

        m3 = detector.check_transcript("what time is it?")
        self.assertFalse(m3.triggered)

    def test_language_detection_no_collision(self) -> None:
        self.assertEqual(detect_language("What time is it right now?"), "en")
        self.assertEqual(detect_language("¿Qué hora es en este momento?"), "es")
        self.assertEqual(detect_language("Quelle heure est-il ?"), "fr")

    def test_english_input_forces_spanish_reply(self) -> None:
        response = self.assistant.process_command("What time is it?")
        self.assertIn("La hora actual es", response)

    def test_notes_save_and_list(self) -> None:
        save_resp = self.assistant.process_command("Take a note: Review NutriCoach Pro PR")
        self.assertIn("Nota guardada correctamente", save_resp)

        list_resp = self.assistant.process_command("Read my notes")
        self.assertIn("Tienes 1 notas registradas", list_resp)
        self.assertIn("review nutricoach pro pr", list_resp)

    def test_assistant_rename_persistence(self) -> None:
        resp = self.assistant.process_command("Change your name to Ultrón Prime")
        self.assertIn("Ultrón Prime", resp)
        self.assertEqual(self.config.load_assistant_name(), "Ultrón Prime")

    def test_tell_joke_restored(self) -> None:
        joke = self.assistant.process_command("Tell me a joke")
        self.assertTrue(len(joke) > 5)

    def test_system_telemetry_voice_routing(self) -> None:
        resp = self.assistant.process_command("How is my PC running?")
        self.assertIn("Diagnóstico de sistemas completado, Juan Diego", resp)
        self.assertIn("CPU al", resp)
        self.assertIn("Memoria RAM al", resp)

    def test_top_processes_voice_routing(self) -> None:
        resp = self.assistant.process_command("What is eating my RAM?")
        self.assertIn("procesos con mayor consumo de memoria RAM, Juan Diego", resp)

    def test_multimodal_vision_voice_routing(self) -> None:
        resp = self.assistant.process_command("Look at my screen and debug this error")
        self.assertTrue(len(resp) > 20)
        # Verifica que la captura se haya guardado en el directorio de screenshots
        saved_pngs = list(self.config.screenshots_dir.glob("*.png"))
        self.assertGreaterEqual(len(saved_pngs), 1)


if __name__ == "__main__":
    unittest.main()
