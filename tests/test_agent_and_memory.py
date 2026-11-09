"""
Pruebas Unitarias para el Bucle Agéntico Autónomo, Memoria Persistente y Organizador de Archivos de Ultrón v5.3.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ultron.agent_loop import AGENT_TOOLS_SCHEMA, UltronAgentLoop
from ultron.assistant import UltronAssistant
from ultron.config import UltronConfig
from ultron.jarvis_pro import FileOrganizerEngine
from ultron.memory import UltronMemory


class TestUltronMemory(unittest.TestCase):
    """Pruebas del sistema de memoria permanente y episódica (Opción B)."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.config = UltronConfig()
        self.config.notes_file = Path(self.test_dir) / "notes.json"
        self.config.memory_file = Path(self.test_dir) / "memory.json"
        self.memory = UltronMemory(self.config)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_remember_and_recall_facts(self) -> None:
        res1 = self.memory.remember("Mi profesor de control se llama Carlos y la entrega es el viernes")
        self.assertIn("guardado en mi memoria permanente", res1.lower())

        # Intentar recordar duplicado
        res_dup = self.memory.remember("Mi profesor de control se llama Carlos y la entrega es el viernes")
        self.assertIn("ya tenía registrado", res_dup.lower())

        # Recall por palabra clave
        matched = self.memory.recall("profesor")
        self.assertEqual(len(matched), 1)
        self.assertIn("Carlos", matched[0])

        # Summary
        summary = self.memory.summary()
        self.assertIn("1 hechos guardados", summary)

    def test_record_episode_sliding_window(self) -> None:
        for i in range(35):
            self.memory.record_episode(
                user_query=f"Comando número {i}",
                action="test_action",
                result_summary=f"Resultado {i}",
            )

        episodes = self.memory._state["episodes"]
        self.assertLessEqual(len(episodes), 30)
        self.assertEqual(episodes[-1]["query"], "Comando número 34")

    def test_get_context_for_prompt(self) -> None:
        self.memory.remember("Proyecto NutriCoach usa Supabase y Tailwind")
        self.memory.record_episode("organiza descargas", "organize_directory", "10 archivos organizados")

        prompt_ctx = self.memory.get_context_for_prompt()
        self.assertIn("NutriCoach", prompt_ctx)
        self.assertIn("organiza descargas", prompt_ctx)

    def test_forget_fact(self) -> None:
        self.memory.remember("Eliminar este recordatorio temporal")
        self.assertEqual(len(self.memory._state["facts"]), 1)

        forget_res = self.memory.forget("temporal")
        self.assertIn("eliminado 1 recuerdo", forget_res.lower())
        self.assertEqual(len(self.memory._state["facts"]), 0)


class TestUltronAgentLoop(unittest.TestCase):
    """Pruebas del Bucle Agéntico Autónomo inspirado en DeepSeek Harness (Opción A)."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.config = UltronConfig()
        self.config.notes_file = Path(self.test_dir) / "notes.json"
        self.config.memory_file = Path(self.test_dir) / "memory.json"
        self.assistant = UltronAssistant(self.config, text_mode=True, mute=True)
        self.agent = self.assistant.agent

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tools_schema_validity(self) -> None:
        tool_names = [t["name"] for t in AGENT_TOOLS_SCHEMA]
        self.assertIn("organize_directory", tool_names)
        self.assertIn("compose_email", tool_names)
        self.assertIn("get_system_telemetry", tool_names)
        self.assertIn("play_spotify", tool_names)
        self.assertIn("remember_fact", tool_names)

    def test_agent_tool_dispatch_organize_directory(self) -> None:
        # Simular que el LLM responde con la invocación estructurada de una herramienta
        llm_tool_response = json.dumps({
            "action": "call_tool",
            "tool_name": "organize_directory",
            "arguments": {"directory": "escritorio"}
        })

        with patch.object(self.assistant.brain, "generate_raw", return_value=llm_tool_response):
            with patch.object(self.assistant.skills, "organize_files", return_value="Escritorio organizado con éxito.") as mock_org:
                reply = self.agent.decide_and_execute("Por favor limpia los archivos que tengo regados en el escritorio")
                self.assertEqual(reply, "Escritorio organizado con éxito.")
                mock_org.assert_called_once_with(query="escritorio", lang="es")

        # Verificar que la acción quedó registrada en la memoria episódica
        episodes = self.assistant.memory._state["episodes"]
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["action"], "organize_directory")

    def test_agent_tool_dispatch_play_spotify(self) -> None:
        llm_tool_response = json.dumps({
            "action": "call_tool",
            "tool_name": "play_spotify",
            "arguments": {"search_query": "Dua Lipa"}
        })

        with patch.object(self.assistant.brain, "generate_raw", return_value=llm_tool_response):
            with patch.object(self.assistant.skills, "play_spotify_music", return_value="Buscando 'Dua Lipa' en Spotify.") as mock_spot:
                reply = self.agent.decide_and_execute("pon a Dua Lipa")
                self.assertEqual(reply, "Buscando 'Dua Lipa' en Spotify.")
                mock_spot.assert_called_once_with("Dua Lipa", lang="es")

    def test_agent_conversational_reply(self) -> None:
        llm_reply_response = json.dumps({
            "action": "reply",
            "text": "Hola Juan Diego, tus sistemas están operando con normalidad."
        })

        with patch.object(self.assistant.brain, "generate_raw", return_value=llm_reply_response):
            reply = self.agent.decide_and_execute("hola qué tal")
            self.assertEqual(reply, "Hola Juan Diego, tus sistemas están operando con normalidad.")


class TestDesktopResolution(unittest.TestCase):
    """Pruebas de la resolución inteligente de carpetas en Windows con OneDrive (Bugfix del Escritorio)."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.home = Path(self.test_dir)
        # Crear estructura simulada de Windows 11 con OneDrive
        self.onedrive_desktop = self.home / "OneDrive" / "Desktop"
        self.onedrive_desktop.mkdir(parents=True, exist_ok=True)
        # La carpeta de OneDrive está vacía (como le ocurrió a Juan Diego)

        # La carpeta física real del usuario contiene archivos sueltos
        self.local_desktop = self.home / "Desktop"
        self.local_desktop.mkdir(parents=True, exist_ok=True)
        (self.local_desktop / "tesis_final.pdf").write_text("dummy", encoding="utf-8")
        (self.local_desktop / "datos_pid.csv").write_text("dummy", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_resolve_target_prefers_desktop_with_loose_files(self) -> None:
        with patch("pathlib.Path.home", return_value=self.home):
            resolved = FileOrganizerEngine.resolve_target_directory("organiza mi escritorio")
            # Debe haber seleccionado el escritorio local porque es el que contiene archivos sueltos
            self.assertEqual(resolved.resolve(), self.local_desktop.resolve())


class TestMemoryVoiceIntegration(unittest.TestCase):
    """Pruebas de la integración de memoria en UltronAssistant.process_command."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.config = UltronConfig()
        self.config.notes_file = Path(self.test_dir) / "notes.json"
        self.config.memory_file = Path(self.test_dir) / "memory.json"
        self.assistant = UltronAssistant(self.config, text_mode=True, mute=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_voice_remember_and_recall_flow(self) -> None:
        # 1. Ultrón recuerda
        resp1 = self.assistant.process_command("Ultrón, recuerda que el proyecto NutriCoach se despliega en Vercel")
        self.assertIn("guardado en mi memoria", resp1.lower())

        # 2. Ultrón recupera
        resp2 = self.assistant.process_command("Ultrón, ¿qué recuerdas de NutriCoach?")
        self.assertIn("NutriCoach se despliega en Vercel", resp2)

        # 3. Ultrón resume memoria
        resp3 = self.assistant.process_command("Ultrón, resumen de memoria")
        self.assertIn("1 hechos guardados", resp3)

        # 4. Ultrón olvida
        resp4 = self.assistant.process_command("Ultrón, olvida NutriCoach")
        self.assertIn("eliminado 1 recuerdo", resp4.lower())


class TestSecurityProtections(unittest.TestCase):
    """Pruebas de las defensas de seguridad y prevención de fugas."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp()
        self.config = UltronConfig()
        self.config.notes_file = Path(self.test_dir) / "notes.json"
        self.config.memory_file = Path(self.test_dir) / "memory.json"
        self.config.screenshots_dir = Path(self.test_dir) / "screenshots"
        self.assistant = UltronAssistant(self.config, text_mode=True, mute=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_skills_url_protocol_sanitization(self) -> None:
        with patch.object(self.assistant.skills, "search_google", return_value="Buscando en Google") as mock_search:
            res1 = self.assistant.skills.open_any_target("javascript:alert(1)")
            self.assertEqual(res1, "Buscando en Google")
            mock_search.assert_called_with("javascript:alert(1)", lang="es")

            res2 = self.assistant.skills.open_any_target("file:///etc/passwd")
            self.assertEqual(res2, "Buscando en Google")

    def test_file_organizer_blocks_root_and_system_paths(self) -> None:
        self.assertFalse(FileOrganizerEngine.is_safe_directory(Path("/")))
        self.assertFalse(FileOrganizerEngine.is_safe_directory(Path("C:\\")))
        self.assertFalse(FileOrganizerEngine.is_safe_directory(Path("/etc")))
        self.assertFalse(FileOrganizerEngine.is_safe_directory(Path("C:\\Windows\\System32")))

    def test_screenshot_pruning_policy(self) -> None:
        from ultron.vision import _prune_old_screenshots

        screenshots_dir = self.config.screenshots_dir
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        for i in range(25):
            p = screenshots_dir / f"ultron_vision_20261109_{i:04d}_000000.png"
            p.write_bytes(b"dummy_png")

        self.assertEqual(len(list(screenshots_dir.glob("ultron_vision_*.png"))), 25)

        _prune_old_screenshots(screenshots_dir, max_keep=15)
        remaining = list(screenshots_dir.glob("ultron_vision_*.png"))
        self.assertEqual(len(remaining), 15)


if __name__ == "__main__":
    unittest.main()
