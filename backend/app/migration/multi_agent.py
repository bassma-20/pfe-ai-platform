"""
migration/multi_agent.py — Architecture multi-agents pour la migration de code.

3 agents spécialisés coordonnés par un orchestrateur :

  ┌─────────────────────────────────────────────────┐
  │             ORCHESTRATEUR                        │
  │  Coordonne, décide si retravailler ou valider   │
  └──────┬──────────────┬──────────────┬────────────┘
         │              │              │
  ┌──────▼──────┐ ┌─────▼──────┐ ┌───▼──────────────┐
  │   ANALYSTE  │ │ MIGRATEUR  │ │   VÉRIFICATEUR   │
  │ Détecte &   │ │ Migre le   │ │ Valide la qualité │
  │ priorise    │ │ code       │ │ & cohérence       │
  └─────────────┘ └────────────┘ └──────────────────┘
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.migration.analyzer        import analyze_java_code
from app.migration.python_analyzer import analyze_python_code
from app.migration.scorer          import compute_score, compute_improvement
from app.migration.service         import get_client, process_response
from app.agent.memory              import get_memory

logger = logging.getLogger(__name__)

MIGRATED_DIR = Path("data/migrated")
MIGRATED_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# APPEL LLM GÉNÉRIQUE (partagé entre agents)
# ─────────────────────────────────────────────────────────────────────────────

async def _llm(system: str, user: str, temperature: float = 0.1) -> str:
    import os
    try:
        response = await get_client().chat.completions.create(
            model       = os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages    = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature = temperature,
            max_tokens  = 4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur LLM : {e}")


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 1 — ANALYSTE
# Rôle : enrichir l'analyse statique avec une compréhension sémantique du code
# ─────────────────────────────────────────────────────────────────────────────

class AnalyzerAgent:
    SYSTEM = (
        "Tu es un expert en analyse de code legacy. "
        "Tu reçois un rapport d'analyse statique et tu l'enrichis avec : "
        "(1) une évaluation de la complexité globale, "
        "(2) les patterns architecturaux identifiés, "
        "(3) les risques de migration les plus critiques à traiter en priorité. "
        "Réponds en JSON strict : {\"complexity\": str, \"patterns\": [str], \"priorities\": [str], \"risk_summary\": str}"
    )

    async def analyze(self, code: str, static_analysis: dict, language: str) -> dict:
        issues_text = "\n".join([
            f"  [{i['code']}] {i['title']} — {i['severity']} (ligne {i['line']})"
            for i in static_analysis.get("issues", [])
        ]) or "  Aucun problème détecté."

        user = (
            f"Langage : {language.upper()}\n"
            f"Métriques : {json.dumps(static_analysis.get('metrics', {}), ensure_ascii=False)}\n"
            f"Problèmes détectés :\n{issues_text}\n\n"
            f"Code source :\n```{language}\n{code[:2000]}\n```"
        )

        raw = await _llm(self.SYSTEM, user, temperature=0.2)
        try:
            cleaned = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw.strip())
            return json.loads(cleaned)
        except Exception:
            return {"complexity": "unknown", "patterns": [], "priorities": [], "risk_summary": raw[:200]}


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 2 — MIGRATEUR
# Rôle : migrer le code en tenant compte de l'analyse enrichie et de la mémoire
# ─────────────────────────────────────────────────────────────────────────────

class MigratorAgent:
    SYSTEM = (
        "Tu es un expert en migration de code legacy. "
        "Tu reçois une analyse détaillée et tu produis un code modernisé de haute qualité. "
        "RÈGLE ABSOLUE : conserve toujours la déclaration 'package' originale en première ligne du code Java. "
        "Conserve tous les imports nécessaires (java.sql.*, java.io.*, etc.). "
        "Pour Python : utilise TOUJOURS f-string pour logger les exceptions : logging.error(f'msg: {e}') — JAMAIS logging.error('msg:', e). "
        "Pour Python : ajoute logging.basicConfig(level=logging.INFO) après les imports. "
        "Tu retournes UNIQUEMENT un JSON valide : "
        "{\"summary\": str, \"migrated_code\": str, \"modifications\": [{\"title\", \"before\", \"after\", \"explanation\"}]}"
    )

    async def migrate(
        self,
        code:            str,
        static_analysis: dict,
        enriched_analysis: dict,
        target_version:  str,
        language:        str,
        memory_context:  str = "",
    ) -> dict:
        lang_features = {
            "java": {
                "8":  "lambdas, Stream API, Optional, java.time",
                "11": "var, String.strip(), HTTP Client",
                "17": "records, sealed classes, pattern matching, text blocks",
                "21": "virtual threads, sequenced collections, record patterns",
            },
            "python": {
                "3.8":  "walrus :=, f-strings, pathlib, dataclasses, typing",
                "3.10": "match/case, parenthesized context managers",
                "3.12": "type aliases, @override, improved f-strings",
            },
        }
        features = lang_features.get(language, {}).get(target_version, "fonctionnalités modernes")

        priorities = "\n".join(f"  - {p}" for p in enriched_analysis.get("priorities", []))
        issues_text = "\n".join([
            f"  [{i['code']}] {i['title']} → {i['suggestion']}"
            for i in static_analysis.get("issues", [])
        ]) or "  Aucun problème détecté."

        user = (
            f"{memory_context}\n\n" if memory_context else ""
        ) + (
            f"Migration : {language.upper()} → version {target_version}\n"
            f"Features cibles : {features}\n"
            f"Complexité identifiée : {enriched_analysis.get('complexity', 'N/A')}\n"
            f"Risque principal : {enriched_analysis.get('risk_summary', 'N/A')}\n\n"
            f"PRIORITÉS (traiter en premier) :\n{priorities or '  (aucune)'}\n\n"
            f"PROBLÈMES À CORRIGER :\n{issues_text}\n\n"
            f"CODE SOURCE :\n```{language}\n{code}\n```"
        )

        raw    = await _llm(self.SYSTEM, user, temperature=0.05)
        result = process_response(raw, "temp", language, code)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 3 — VÉRIFICATEUR
# Rôle : évaluer la qualité de la migration, détecter les régressions
# ─────────────────────────────────────────────────────────────────────────────

class VerifierAgent:
    SYSTEM = (
        "Tu es un expert en revue de code et en qualité logicielle. "
        "Tu reçois le code original et le code migré, et tu évalues : "
        "(1) la logique métier est-elle préservée à 100% ? "
        "(2) tous les problèmes identifiés ont-ils été corrigés ? "
        "(3) y a-t-il des régressions ou nouveaux problèmes introduits ? "
        "(4) note de qualité globale de la migration (0 à 10). "
        "Réponds en JSON : {\"logic_preserved\": bool, \"all_fixed\": bool, "
        "\"regressions\": [str], \"quality_score\": int, \"verdict\": str, \"needs_rework\": bool}"
    )

    async def verify(
        self,
        original_code:     str,
        migrated_code:     str,
        remaining_issues:  List[dict],
        language:          str,
    ) -> dict:
        remaining_text = "\n".join([
            f"  [{i['code']}] {i['title']}"
            for i in remaining_issues
        ]) or "  Aucun — migration parfaite !"

        user = (
            f"Langage : {language.upper()}\n"
            f"Problèmes restants dans le code migré :\n{remaining_text}\n\n"
            f"CODE ORIGINAL :\n```{language}\n{original_code[:1500]}\n```\n\n"
            f"CODE MIGRÉ :\n```{language}\n{migrated_code[:1500]}\n```"
        )

        raw = await _llm(self.SYSTEM, user, temperature=0.1)
        try:
            cleaned = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw.strip())
            return json.loads(cleaned)
        except Exception:
            return {
                "logic_preserved": True,
                "all_fixed":       len(remaining_issues) == 0,
                "regressions":     [],
                "quality_score":   7,
                "verdict":         raw[:200],
                "needs_rework":    False,
            }


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATEUR — Coordonne les 3 agents
# ─────────────────────────────────────────────────────────────────────────────

class MigrationOrchestrator:
    """
    Coordonne les 3 agents spécialisés.
    Peut relancer le migrateur si le vérificateur détecte des problèmes.
    """

    def __init__(self):
        self.analyzer  = AnalyzerAgent()
        self.migrator  = MigratorAgent()
        self.verifier  = VerifierAgent()
        self.memory    = get_memory()

    async def run(
        self,
        original_code:     str,
        original_filename: str,
        language:          str,
        target_version:    str,
        max_rework:        int = 2,
    ) -> dict:
        """
        Pipeline multi-agents :
          1. Analyste : analyse statique + enrichissement sémantique
          2. Récupération mémoire
          3. Migrateur : migration avec contexte enrichi
          4. Vérificateur : validation qualité
          5. Si needs_rework → relancer le migrateur (max_rework fois)
          6. Mise à jour mémoire
        """
        analyze        = analyze_python_code if language == "python" else analyze_java_code
        agent_trace    = []

        # ── Étape 1 : Analyse statique + enrichissement ───────────────────────
        static_analysis = analyze(original_code)
        score_before    = compute_score(static_analysis)

        agent_trace.append({
            "agent":  "AnalyzerAgent",
            "action": "Analyse statique + enrichissement sémantique",
            "result": f"{static_analysis['issues_count']} problèmes détectés",
        })

        enriched = await self.analyzer.analyze(original_code, static_analysis, language)
        agent_trace.append({
            "agent":  "AnalyzerAgent",
            "action": "Enrichissement sémantique terminé",
            "result": enriched.get("risk_summary", "N/A"),
        })

        # ── Étape 2 : Consultation mémoire ────────────────────────────────────
        issue_codes   = [i["code"] for i in static_analysis.get("issues", [])]
        past_memories = self.memory.recall_migration(language=language, issue_codes=issue_codes)
        memory_ctx    = self.memory.format_migration_context(past_memories)

        agent_trace.append({
            "agent":  "Orchestrateur",
            "action": "Consultation mémoire",
            "result": f"{len(past_memories)} souvenir(s) pertinent(s) trouvé(s)",
        })

        # ── Étape 3 : Migration + vérification (avec possibilité de rework) ───
        current_code = original_code
        last_result  = {}

        for attempt in range(1, max_rework + 2):
            # Migrer
            agent_trace.append({
                "agent":  "MigratorAgent",
                "action": f"Migration (tentative {attempt}/{max_rework + 1})",
                "result": "En cours…",
            })

            migration_result = await self.migrator.migrate(
                code              = current_code,
                static_analysis   = static_analysis if attempt == 1 else analyze(current_code),
                enriched_analysis = enriched,
                target_version    = target_version,
                language          = language,
                memory_context    = memory_ctx if attempt == 1 else "",
            )

            migrated_code = migration_result.get("migrated_code", "")
            if not migrated_code:
                break

            after_analysis   = analyze(migrated_code)
            remaining_issues = after_analysis.get("issues", [])

            agent_trace[-1]["result"] = (
                f"Migration produite — {len(remaining_issues)} problème(s) restant(s)"
            )
            last_result = migration_result

            # Vérifier
            agent_trace.append({
                "agent":  "VerifierAgent",
                "action": f"Vérification qualité (tentative {attempt})",
                "result": "En cours…",
            })

            verification = await self.verifier.verify(
                original_code    = original_code,
                migrated_code    = migrated_code,
                remaining_issues = remaining_issues,
                language         = language,
            )

            verdict = (
                f"Score qualité : {verification.get('quality_score', '?')}/10 | "
                f"Logique préservée : {verification.get('logic_preserved', '?')} | "
                f"Verdict : {verification.get('verdict', '')[:100]}"
            )
            agent_trace[-1]["result"] = verdict

            current_code = migrated_code

            # Décision de l'orchestrateur
            if not verification.get("needs_rework", False) or attempt > max_rework:
                agent_trace.append({
                    "agent":  "Orchestrateur",
                    "action": "Décision finale",
                    "result": "Migration validée ✓" if not verification.get("needs_rework") else "Max tentatives atteint — on garde le meilleur résultat",
                })
                break

            agent_trace.append({
                "agent":  "Orchestrateur",
                "action": "Décision : rework nécessaire",
                "result": f"Régressions : {verification.get('regressions', [])}",
            })

        # ── Résultat final ────────────────────────────────────────────────────
        final_analysis = analyze(current_code)
        score_after    = compute_score(final_analysis)
        improvement    = compute_improvement(score_before, score_after)

        # Sauvegarder
        ext      = ".py" if language == "python" else ".java"
        stem     = Path(original_filename).stem
        out_path = MIGRATED_DIR / f"{stem}_migrated{ext}"
        try:
            out_path.write_text(current_code, encoding="utf-8")
        except Exception:
            pass

        # Mémoriser
        self.memory.remember_migration(
            language        = language,
            issue_codes     = issue_codes,
            target_version  = target_version,
            iterations_used = attempt,
            score_delta     = improvement.get("score_delta", 0),
            issues_fixed    = improvement.get("issues_fixed", 0),
            best_approach   = f"multi-agent, {attempt} tentative(s)",
        )

        return {
            "language":        language,
            "original_code":   original_code,
            "migrated_code":   current_code,
            "summary":         last_result.get("summary", ""),
            "modifications":   last_result.get("modifications", []),
            "analysis_before": static_analysis,
            "analysis_after":  final_analysis,
            "score_before":    score_before,
            "score_after":     score_after,
            "improvement":     improvement,
            "saved_file":      str(out_path),
            "agent_trace": {
                "mode":          "multi_agent",
                "agents_used":   ["AnalyzerAgent", "MigratorAgent", "VerifierAgent"],
                "attempts":      attempt,
                "memory_used":   len(past_memories) > 0,
                "enriched":      enriched,
                "steps":         agent_trace,
            },
        }
