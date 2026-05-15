"""
agent/memory.py — Mémoire épisodique persistante partagée entre tous les agents.

L'agent apprend de chaque run réussi :
  - Migration : quels patterns de code ont été corrigés, en combien d'itérations
  - AutoML    : quels modèles ont gagné sur quel type de dataset

La mémoire est consultée AVANT chaque décision LLM pour enrichir le contexte.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MEMORY_PATH = Path("data/agent_memory.json")
MAX_ENTRIES = 100   # Garder les 100 derniers souvenirs par catégorie


# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURE DES SOUVENIRS
# ─────────────────────────────────────────────────────────────────────────────

def _migration_entry(
    language:        str,
    issue_codes:     List[str],
    target_version:  str,
    iterations_used: int,
    score_delta:     int,
    issues_fixed:    int,
    best_approach:   str,
) -> Dict:
    return {
        "type":           "migration",
        "language":       language,
        "issue_codes":    issue_codes,
        "target_version": target_version,
        "iterations":     iterations_used,
        "score_delta":    score_delta,
        "issues_fixed":   issues_fixed,
        "best_approach":  best_approach,
        "timestamp":      datetime.utcnow().isoformat(),
    }


def _automl_entry(
    problem_type:  str,
    n_rows:        int,
    n_features:    int,
    best_model:    str,
    best_metric:   float,
    metric_name:   str,
    dataset_hints: List[str],
) -> Dict:
    return {
        "type":          "automl",
        "problem_type":  problem_type,
        "n_rows":        n_rows,
        "n_features":    n_features,
        "best_model":    best_model,
        "best_metric":   best_metric,
        "metric_name":   metric_name,
        "dataset_hints": dataset_hints,
        "timestamp":     datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLASSE MÉMOIRE
# ─────────────────────────────────────────────────────────────────────────────

class AgentMemory:
    """
    Mémoire persistante JSON.
    Thread-safe pour un usage mono-processus (FastAPI avec un worker).
    """

    def __init__(self, path: Path = MEMORY_PATH):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load(self) -> Dict:
        if self._path.exists():
            try:
                with open(self._path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[Memory] Impossible de lire la mémoire : {e}")
        return {"migration": [], "automl": []}

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[Memory] Sauvegarde échouée : {e}")

    def _trim(self, key: str):
        if len(self._data[key]) > MAX_ENTRIES:
            self._data[key] = self._data[key][-MAX_ENTRIES:]

    # ── ÉCRITURE ─────────────────────────────────────────────────────────────

    def remember_migration(self, **kwargs):
        entry = _migration_entry(**kwargs)
        self._data["migration"].append(entry)
        self._trim("migration")
        self._save()
        logger.info(f"[Memory] Souvenir migration ajouté ({len(self._data['migration'])} total)")

    def remember_automl(self, **kwargs):
        entry = _automl_entry(**kwargs)
        self._data["automl"].append(entry)
        self._trim("automl")
        self._save()
        logger.info(f"[Memory] Souvenir AutoML ajouté ({len(self._data['automl'])} total)")

    # ── LECTURE / RECHERCHE ───────────────────────────────────────────────────

    def recall_migration(
        self,
        language:     str,
        issue_codes:  List[str],
        top_k:        int = 5,
    ) -> List[Dict]:
        """Retourne les souvenirs de migration les plus pertinents."""
        scored = []
        for m in self._data["migration"]:
            if m.get("language") != language:
                continue
            overlap = len(set(issue_codes) & set(m.get("issue_codes", [])))
            if overlap > 0:
                scored.append((overlap, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_k]]

    def recall_automl(
        self,
        problem_type: str,
        n_rows:       int,
        n_features:   int,
        top_k:        int = 3,
    ) -> List[Dict]:
        """Retourne les souvenirs AutoML les plus pertinents."""
        scored = []
        for m in self._data["automl"]:
            if m.get("problem_type") != problem_type:
                continue
            # Score de similarité basé sur la taille du dataset
            row_sim  = 1 - abs(n_rows     - m.get("n_rows", 0))     / max(n_rows, 1)
            feat_sim = 1 - abs(n_features - m.get("n_features", 0)) / max(n_features, 1)
            score    = (row_sim + feat_sim) / 2
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_k]]

    # ── FORMATAGE POUR LE PROMPT ──────────────────────────────────────────────

    def format_migration_context(self, memories: List[Dict]) -> str:
        if not memories:
            return "Aucun souvenir pertinent disponible."
        lines = ["EXPÉRIENCES PASSÉES PERTINENTES :"]
        for i, m in enumerate(memories, 1):
            lines.append(
                f"  {i}. [{m['language']}→{m['target_version']}] "
                f"Problèmes: {m['issue_codes']} | "
                f"Résolus en {m['iterations']} itération(s) | "
                f"Score +{m['score_delta']} | "
                f"Approche: {m['best_approach']}"
            )
        return "\n".join(lines)

    def format_automl_context(self, memories: List[Dict]) -> str:
        if not memories:
            return "Aucun souvenir pertinent disponible."
        lines = ["EXPÉRIENCES PASSÉES PERTINENTES :"]
        for i, m in enumerate(memories, 1):
            lines.append(
                f"  {i}. [{m['problem_type']}] "
                f"{m['n_rows']} lignes, {m['n_features']} features → "
                f"Meilleur modèle: {m['best_model']} "
                f"({m['metric_name']}={m['best_metric']:.3f})"
            )
        return "\n".join(lines)

    # ── STATS ─────────────────────────────────────────────────────────────────

    def stats(self) -> Dict:
        return {
            "migration_memories": len(self._data["migration"]),
            "automl_memories":    len(self._data["automl"]),
            "memory_path":        str(self._path),
        }


# Singleton global — une seule instance partagée par tout le backend
_memory_instance: Optional[AgentMemory] = None


def get_memory() -> AgentMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = AgentMemory()
    return _memory_instance
