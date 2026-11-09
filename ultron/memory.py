"""
Memoria Episódica y de Largo Plazo para Ultrón v5.3 (`ultron.memory`).
Permite recordar hechos, preferencias, avances de proyectos de Juan Diego
y retener el historial reciente entre sesiones en formato persistente JSON.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.config import UltronConfig

logger = logging.getLogger("ultron.memory")


class UltronMemory:
    """Gestiona la memoria episódica y semántica a largo plazo de Ultrón."""

    def __init__(self, config: Optional[UltronConfig] = None) -> None:
        self.config = config or UltronConfig()
        self.config.ensure_dirs()
        self.memory_file: Path = getattr(self.config, "memory_file", self.config.notes_file.parent / "memory.json")
        self._state: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.memory_file.exists():
            try:
                data = json.loads(self.memory_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data.setdefault("profile", {})
                    data.setdefault("facts", [])
                    data.setdefault("episodes", [])
                    return data
            except Exception as exc:
                logger.warning("No se pudo cargar memory.json (%s). Creando nueva memoria.", exc)

        return {
            "profile": {
                "user_name": self.config.user_name,
                "role": "Ingeniero Biomédico y Desarrollador Full Stack & Mobile en Colombia",
                "core_projects": [
                    "NutriCoach Pro (Next.js, React, Tailwind, Supabase)",
                    "INV. PRO (Inventario Web Pro, PostgreSQL)",
                    "Controlador PID Bola-Viga en Arduino",
                ],
            },
            "facts": [],
            "episodes": [],
        }

    def _save(self) -> None:
        try:
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            self.memory_file.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("Error al persistir memoria de Ultrón: %s", exc)

    def remember(self, fact: str, category: str = "general") -> str:
        """Almacena un hecho o preferencia explícita en la memoria permanente."""
        clean = fact.strip("¿?¡!., \t\n\r")
        if not clean:
            return "No recibí ningún dato para recordar."

        # Evitar duplicados exactos
        for f in self._state["facts"]:
            if f.get("fact", "").lower() == clean.lower():
                return f"Ya tenía registrado en memoria que: '{clean}', {self.config.user_name}."

        entry = {
            "id": len(self._state["facts"]) + 1,
            "fact": clean,
            "category": category,
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        self._state["facts"].append(entry)
        self._save()
        return f"Entendido, {self.config.user_name}. He guardado en mi memoria permanente: '{clean}'."

    def recall(self, query: str = "", limit: int = 5) -> List[str]:
        """Recupera hechos relevantes coincidentes por palabras clave o los más recientes."""
        q_words = [w.lower() for w in query.split() if len(w) > 3] if query else []
        facts = self._state.get("facts", [])
        if not facts:
            return []

        if not q_words:
            # Retornar los últimos 'limit' hechos guardados
            return [f["fact"] for f in facts[-limit:]]

        matched = []
        for f in facts:
            fact_text = f.get("fact", "").lower()
            if any(w in fact_text for w in q_words):
                matched.append(f["fact"])

        return matched[:limit] if matched else [f["fact"] for f in facts[-limit:]]

    def record_episode(self, user_query: str, action: str, result_summary: str) -> None:
        """Registra una interacción episódica para retención de contexto entre comandos."""
        if not user_query:
            return
        episodes = self._state.setdefault("episodes", [])
        entry = {
            "query": user_query.strip(),
            "action": action,
            "summary": result_summary.strip()[:200],
            "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        }
        episodes.append(entry)
        # Mantener solo los últimos 30 episodios para no sobrecargar almacenamiento
        if len(episodes) > 30:
            self._state["episodes"] = episodes[-30:]
        self._save()

    def get_context_for_prompt(self) -> str:
        """Sintetiza hechos clave y contexto reciente para inyectar en el LLM."""
        facts = [f["fact"] for f in self._state.get("facts", [])[-6:]]
        recent_episodes = [
            f"- A las {e.get('timestamp')}: orden '{e.get('query')}' -> {e.get('summary')}"
            for e in self._state.get("episodes", [])[-4:]
        ]

        facts_block = "\n".join(f"- {f}" for f in facts) if facts else "Ninguno registrado aún."
        episodes_block = "\n".join(recent_episodes) if recent_episodes else "Ninguna interacción previa reciente."

        return (
            "MEMORIA PERMANENTE Y CONTEXTO RECIENTE DE JUAN DIEGO:\n"
            f"{facts_block}\n\n"
            "ÚLTIMAS ACCIONES EJECUTADAS EN ESTA SESIÓN:\n"
            f"{episodes_block}"
        )

    def forget(self, query: str) -> str:
        """Elimina un hecho de la memoria que coincida con la consulta."""
        q_clean = query.lower().strip()
        facts = self._state.get("facts", [])
        remaining = [f for f in facts if q_clean not in f.get("fact", "").lower()]
        deleted = len(facts) - len(remaining)
        if deleted > 0:
            self._state["facts"] = remaining
            self._save()
            return f"He eliminado {deleted} recuerdo(s) de mi memoria permanente, {self.config.user_name}."
        return f"No encontré ningún recuerdo coincidente con '{query}' para borrar."

    def summary(self) -> str:
        """Devuelve un resumen hablado de la memoria activa."""
        facts_cnt = len(self._state.get("facts", []))
        episodes_cnt = len(self._state.get("episodes", []))
        if facts_cnt == 0:
            return (
                f"Mi memoria permanente está activa pero no tengo hechos específicos guardados aún, {self.config.user_name}. "
                "Puedes decirme 'Ultrón, recuerda que...' para registrar información clave."
            )
        latest = self._state["facts"][-1]["fact"]
        return (
            f"Tengo {facts_cnt} hechos guardados en mi memoria permanente y registro de {episodes_cnt} acciones recientes, {self.config.user_name}. "
            f"El último hecho registrado es: '{latest}'."
        )
