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

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI
from fastapi import HTTPException

from app.migration.analyzer        import analyze_java_code
from app.migration.python_analyzer import analyze_python_code
from app.migration.scorer          import compute_score, compute_improvement
from app.migration.service         import process_response
from app.migration.python_fixer    import apply_deterministic_fixes
from app.agent.memory              import get_memory

logger = logging.getLogger(__name__)

MIGRATED_DIR = Path("data/migrated")
MIGRATED_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT OPENAI PARTAGÉ — créé une seule fois, avec retries et timeout long
# ─────────────────────────────────────────────────────────────────────────────

def _get_shared_client() -> AsyncOpenAI:
    """Client partagé entre tous les agents : max_retries=5, timeout=120s."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY manquante.")
    return AsyncOpenAI(
        api_key     = api_key,
        max_retries = 5,                          # 5 tentatives au lieu de 2
        timeout     = httpx.Timeout(
            connect = 10.0,   # connexion : 10s
            read    = 180.0,  # lecture réponse : 3 minutes
            write   = 30.0,   # envoi requête : 30s
            pool    = 10.0,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# APPEL LLM GÉNÉRIQUE — avec pause anti-rate-limit entre les appels
# ─────────────────────────────────────────────────────────────────────────────

async def _llm(system: str, user: str, temperature: float = 0.1,
               client: AsyncOpenAI = None, pause: float = 2.0) -> str:
    """
    Appel LLM avec :
    - pause anti-rate-limit avant chaque appel (défaut 2s)
    - 5 retries automatiques (gérés par le client OpenAI)
    - timeout généreux de 3 minutes
    """
    model = os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
    if client is None:
        client = _get_shared_client()

    # Pause pour éviter les rate limits (429) entre appels enchaînés
    if pause > 0:
        await asyncio.sleep(pause)

    try:
        response = await client.chat.completions.create(
            model       = model,
            messages    = [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature = temperature,
            max_tokens  = 8192,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur LLM ({model}) : {e}")


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

    async def analyze(self, code: str, static_analysis: dict, language: str,
                      client: AsyncOpenAI = None) -> dict:
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

        raw = await _llm(self.SYSTEM, user, temperature=0.2, client=client, pause=0)
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
        "Tu es un expert en migration de code legacy. Corrige ABSOLUMENT TOUS les problèmes détectés. "
        "Ne laisse AUCUN problème non corrigé. Voici les règles STRICTES avec exemples :\n\n"

        "=== PYTHON 2 → 3 (obligatoire) ===\n"
        "xrange(n) → range(n)\n"
        "d.has_key(k) → k in d\n"
        "d.iteritems() → d.items()  |  d.itervalues() → d.values()  |  d.iterkeys() → d.keys()\n"
        "import urllib2 → import urllib.request; import urllib.error\n"
        "import cPickle → import pickle\n"
        "import thread → import threading\n"
        "basestring → str  |  unicode(x) → str(x)\n"
        "apply(f,a) → f(*a)\n"
        "execfile(p) → exec(open(p).read())\n"
        "raise Exc, msg → raise Exc(msg)\n"
        "print x → logging.info(f'{x}')\n\n"

        "=== LOGGING (obligatoire) ===\n"
        "Remplace TOUS les print() par logging.info/error/debug.\n"
        "Ajoute après les imports : import logging\\nlogging.basicConfig(level=logging.INFO)\\nlogger = logging.getLogger(__name__)\n"
        "TOUJOURS f-string : logging.error(f'erreur: {e}')  JAMAIS logging.error('erreur:', e)\n\n"

        "=== EXCEPTIONS — EXEMPLES OBLIGATOIRES ===\n"
        "AVANT : except:\n"
        "APRÈS : except (IOError, OSError, ValueError):\n\n"
        "AVANT : except Exception as e:\n"
        "APRÈS : except (ValueError, TypeError, KeyError, IOError, OSError) as e:\n\n"
        "AVANT : except Exception as e: pass\n"
        "APRÈS : except (ValueError, OSError) as e: logging.error(f'Erreur: {e}')\n\n"

        "=== SQL INJECTION — EXEMPLES OBLIGATOIRES ===\n"
        "AVANT : cursor.execute(\"SELECT * FROM t WHERE name='%s'\" % name)\n"
        "APRÈS : cursor.execute(\"SELECT * FROM t WHERE name=%s\", (name,))\n\n"
        "AVANT : cursor.execute(\"INSERT INTO t VALUES ('%s','%s')\" % (a, b))\n"
        "APRÈS : cursor.execute(\"INSERT INTO t VALUES (%s,%s)\", (a, b))\n\n"

        "=== RESSOURCES ===\n"
        "AVANT : f = open('file.txt')  ... f.close()\n"
        "APRÈS : with open('file.txt') as f: ...\n\n"

        "=== COMPARAISONS (obligatoire) ===\n"
        "AVANT : if x == None:   APRÈS : if x is None:\n"
        "AVANT : if x != None:   APRÈS : if x is not None:\n"
        "AVANT : if x == True:   APRÈS : if x:\n"
        "AVANT : if x == False:  APRÈS : if not x:\n"
        "AVANT : type(x) == ClassName  APRÈS : isinstance(x, ClassName)\n\n"

        "=== FORMATAGE STRINGS (obligatoire) ===\n"
        "AVANT : 'Bonjour %s' % name         APRÈS : f'Bonjour {name}'\n"
        "AVANT : 'valeur: %d' % count        APRÈS : f'valeur: {count}'\n"
        "AVANT : '%s=%s' % (key, val)        APRÈS : f'{key}={val}'\n\n"

        "=== TYPE HINTS ===\n"
        "Ajouter sur toutes les fonctions : def f(x: int, y: str) -> bool:\n\n"

        "Java — conserve la déclaration 'package' en première ligne.\n\n"

        "Retourne UNIQUEMENT JSON valide (pas de markdown, pas de texte avant/après) :\n"
        "{\"summary\":str, \"migrated_code\":str, \"modifications\":[{\"title\":str,\"before\":str,\"after\":str,\"explanation\":str}]}"
    )

    async def migrate(
        self,
        code:            str,
        static_analysis: dict,
        enriched_analysis: dict,
        target_version:  str,
        language:        str,
        memory_context:  str = "",
        client:          AsyncOpenAI = None,
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

        # pause=3s : laisse OpenAI respirer entre l'analyste et le migrateur
        raw    = await _llm(self.SYSTEM, user, temperature=0.05, client=client, pause=3.0)
        # save=False : évite de créer temp_migrated.py qui déclenche le hot-reload d'uvicorn
        result = process_response(raw, "temp", language, code, save=False)
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
        client:            AsyncOpenAI = None,
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

        raw = await _llm(self.SYSTEM, user, temperature=0.1, client=client, pause=3.0)
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

    Pipeline optimisé :
    ┌─────────────────────────────────────────────────────────────────┐
    │  Analyste (1×LLM)  →  Migrateur + Fixer (N×LLM)  →  Vérificateur (1×LLM)  │
    │                                                                 │
    │  Le Vérificateur LLM ne tourne QU'UNE FOIS à la fin.           │
    │  Entre les tentatives : l'analyseur statique (gratuit) décide.  │
    │  Boucle jusqu'à 0 problème ou max_rework atteint.               │
    └─────────────────────────────────────────────────────────────────┘
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
        max_rework:        int = 3,
    ) -> dict:
        """
        Pipeline de réparation progressive :
          1. Analyste  : analyse statique + enrichissement sémantique
          2. Mémoire   : récupération des migrations similaires passées
          3. Boucle réparation (max_rework+1 tentatives) :
               a. Migrateur  : migre le code ACTUEL (original ou déjà migré)
               b. Fixer      : corrections déterministes (regex)
               c. Analyseur  : compte les problèmes restants
               d. Si 0 → parfait, sortie immédiate
               e. Si stagnation (0 progrès) → sortie
               f. Sinon → reprend la boucle sur le code migré
          4. Vérificateur (1 seul appel LLM, à la fin) : rapport qualité final
          5. Mémoire   : mémorise la migration
        """
        analyze        = analyze_python_code if language == "python" else analyze_java_code
        agent_trace    = []
        max_attempts   = max_rework + 1   # ex: max_rework=3 → 4 tentatives max

        # Client OpenAI partagé entre tous les agents (1 seule instance, 5 retries)
        shared_client = _get_shared_client()

        # ── Étape 1 : Analyse statique + enrichissement ───────────────────────
        static_analysis = analyze(original_code)
        score_before    = compute_score(static_analysis)
        initial_count   = static_analysis.get("issues_count", 0)

        agent_trace.append({
            "agent":  "AnalyzerAgent",
            "action": "Analyse statique du code original",
            "result": f"{initial_count} problème(s) détecté(s) — score {score_before.get('score', 0)}/100",
        })

        enriched = await self.analyzer.analyze(original_code, static_analysis, language,
                                                client=shared_client)
        agent_trace.append({
            "agent":  "AnalyzerAgent",
            "action": "Enrichissement sémantique",
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

        # ── Étape 3 : Boucle de réparation progressive ───────────────────────
        # Principe : chaque tentative travaille sur le code déjà migré,
        # en ciblant uniquement les problèmes RESTANTS.
        current_code      = original_code
        last_result       = {}
        prev_issue_count  = initial_count
        attempt           = 0
        final_remaining   = []

        for attempt in range(1, max_attempts + 1):
            is_first    = (attempt == 1)
            is_last     = (attempt == max_attempts)
            current_analysis = static_analysis if is_first else analyze(current_code)
            remaining_before = current_analysis.get("issues", [])
            remaining_count  = len(remaining_before)

            # Construire l'action label pour la trace
            if is_first:
                action_label = f"Migration initiale — {remaining_count} problème(s) à corriger"
            else:
                action_label = (
                    f"Réparation #{attempt} sur code migré "
                    f"— {remaining_count} problème(s) restant(s)"
                )

            migrator_trace_entry = {
                "agent":  "MigratorAgent",
                "action": action_label,
                "result": "En cours…",
            }
            agent_trace.append(migrator_trace_entry)

            # Sur les tentatives de rework : contexte ciblé (problèmes restants seulement)
            rework_context = ""
            if not is_first and remaining_before:
                remaining_list = "\n".join(
                    f"  [{i['code']}] ligne {i['line']} — {i['title']} → {i['suggestion']}"
                    for i in remaining_before
                )
                rework_context = (
                    f"⚠ REWORK #{attempt} : Ce code a déjà été partiellement migré. "
                    f"Il reste {remaining_count} problème(s) NON corrigés — corrige-les TOUS :\n"
                    f"{remaining_list}\n"
                )

            migration_result = await self.migrator.migrate(
                code              = current_code,
                static_analysis   = current_analysis,
                enriched_analysis = enriched,
                target_version    = target_version,
                language          = language,
                memory_context    = (memory_ctx if is_first else "") + rework_context,
                client            = shared_client,
            )

            migrated_code = migration_result.get("migrated_code", "")
            if not migrated_code:
                migrator_trace_entry["result"] = "⚠ Aucun code retourné par le LLM"
                break

            # ── Correcteur déterministe ───────────────────────────────────────
            if language == "python":
                migrated_code, det_fixes = apply_deterministic_fixes(migrated_code)
                if det_fixes:
                    migration_result["migrated_code"] = migrated_code
                    logger.info(f"[Fixer] {len(det_fixes)} fix(es) déterministe(s) : {det_fixes}")
                    agent_trace.append({
                        "agent":  "DeterministicFixer",
                        "action": f"Corrections garanties ({len(det_fixes)})",
                        "result": ", ".join(det_fixes),
                    })

            # ── Analyse du résultat ───────────────────────────────────────────
            after_analysis   = analyze(migrated_code)
            final_remaining  = after_analysis.get("issues", [])
            issues_after     = len(final_remaining)
            issues_fixed     = remaining_count - issues_after
            score_now        = compute_score(after_analysis).get("score", 0)

            migrator_trace_entry["result"] = (
                f"✓ {issues_fixed} corrigé(s) — {issues_after} restant(s) "
                f"[score intermédiaire : {score_now}/100]"
            )
            last_result  = migration_result
            current_code = migrated_code

            # ── Décision de l'orchestrateur (sans LLM) ───────────────────────
            if issues_after == 0:
                # Migration parfaite !
                agent_trace.append({
                    "agent":  "Orchestrateur",
                    "action": f"✓ Migration parfaite en {attempt} tentative(s)",
                    "result": "0 problème restant — arrêt de la boucle",
                })
                break

            if issues_fixed == 0 and not is_first:
                # Stagnation : le LLM n'arrive plus à progresser
                agent_trace.append({
                    "agent":  "Orchestrateur",
                    "action": "Stagnation détectée",
                    "result": (
                        f"Aucun progrès entre la tentative {attempt-1} et {attempt} "
                        f"({issues_after} problème(s) restant(s)) — arrêt"
                    ),
                })
                break

            if is_last:
                agent_trace.append({
                    "agent":  "Orchestrateur",
                    "action": f"Maximum de tentatives atteint ({max_attempts})",
                    "result": f"{issues_after} problème(s) restant(s) — on conserve le meilleur résultat",
                })
                break

            # Continuer la boucle
            agent_trace.append({
                "agent":  "Orchestrateur",
                "action": f"Tentative {attempt+1} programmée",
                "result": (
                    f"{issues_fixed} problème(s) corrigé(s) dans cette passe, "
                    f"{issues_after} restant(s) → relance sur le code migré"
                ),
            })
            prev_issue_count = issues_after

        # ── Étape 4 : Vérification finale (1 seul appel LLM) ─────────────────
        # Le vérificateur ne tourne QU'UNE FOIS à la fin pour le rapport qualité.
        verification: dict = {}
        if last_result:
            verifier_trace_entry = {
                "agent":  "VerifierAgent",
                "action": "Rapport qualité final",
                "result": "En cours…",
            }
            agent_trace.append(verifier_trace_entry)
            try:
                verification = await self.verifier.verify(
                    original_code    = original_code,
                    migrated_code    = current_code,
                    remaining_issues = final_remaining,
                    language         = language,
                    client           = shared_client,
                )
                verifier_trace_entry["result"] = (
                    f"Score qualité : {verification.get('quality_score', '?')}/10 | "
                    f"Logique préservée : {verification.get('logic_preserved', '?')} | "
                    f"{verification.get('verdict', '')[:120]}"
                )
            except Exception as verif_err:
                logger.warning(f"[VerifierAgent] Échec : {verif_err}")
                verifier_trace_entry["result"] = f"⚠ Vérificateur indisponible — migration conservée"
                verification = {
                    "quality_score": None, "logic_preserved": None,
                    "verdict": "Vérification non disponible", "needs_rework": False,
                }

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
                "agents_used":   ["AnalyzerAgent", "MigratorAgent", "DeterministicFixer", "VerifierAgent"],
                "attempts":      attempt,
                "max_attempts":  max_attempts,
                "memory_used":   len(past_memories) > 0,
                "perfect":       len(final_remaining) == 0,
                "enriched":      enriched,
                "verification":  verification,
                "steps":         agent_trace,
            },
        }
