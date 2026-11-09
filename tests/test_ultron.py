"""
Suite de pruebas unitarias para validar los 4 pilares de Ultrón:
1. Configuración y personalización para Juan Diego Cerón Duque.
2. Detección de Wake-Word ("Ultrón" / "Hey Ultrón").
3. Detección inteligente de idioma (Inglés de entrada -> Español de respuesta).
4. Habilidades restauradas (notas JSON, chistes, renombrado, fecha/hora).
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
        # Oración con wake-word en inglés
        m1 = detector.check_transcript("Hey Ultron, what time is it?")
        self.assertTrue(m1.triggered)
        self.assertEqual(m1.wake_word, "hey ultron")
        self.assertEqual(m1.remaining_command, "what time is it?")

        # Oración con wake-word en español
        m2 = detector.check_transcript("Ultrón, abre mi portafolio")
        self.assertTrue(m2.triggered)
        self.assertEqual(m2.remaining_command, "abre mi portafolio")

        # Oración sin wake-word debe ser ignorada
        m3 = detector.check_transcript("what time is it?")
        self.assertFalse(m3.triggered)

    def test_language_detection_no_collision(self) -> None:
        self.assertEqual(detect_language("What time is it right now?"), "en")
        self.assertEqual(detect_language("¿Qué hora es en este momento?"), "es")
        self.assertEqual(detect_language("Quelle heure est-il ?"), "fr")

    def test_english_input_forces_spanish_reply(self) -> None:
        # Juan Diego pregunta la hora en inglés para practicar, Ultrón responde en español
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


if __name__ == "__main__":
    unittest.main()
