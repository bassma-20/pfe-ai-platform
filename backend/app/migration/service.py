"""
service.py — Logique principale du module de migration (Java + Python)
Pipeline : lecture → analyse → score_before → LLM → analyse → score_after → résultat
"""

import os
import re
import json
from pathlib import Path
from openai import AsyncOpenAI
from fastapi import HTTPException
from dotenv import load_dotenv

from app.migration.analyzer        import analyze_java_code
from app.migration.python_analyzer import analyze_python_code
from app.migration.scorer          import compute_score, compute_improvement

load_dotenv()

MIGRATED_DIR = Path("data/migrated")
MIGRATED_DIR.mkdir(parents=True, exist_ok=True)

MAX_REFLECTION_ITERATIONS = 3   # L'agent peut se corriger jusqu'à 3 fois


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT OPENAI
# ─────────────────────────────────────────────────────────────────────────────

def get_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY manquante. Créez backend/.env avec OPENAI_API_KEY=sk-..."
        )
    return AsyncOpenAI(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
# LECTURE DU FICHIER
# ─────────────────────────────────────────────────────────────────────────────

def read_file(file_path: str, language: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier introuvable : {file_path}")
    ext = path.suffix.lower()
    if language == "java" and ext != ".java":
        raise HTTPException(status_code=400, detail="Seuls les fichiers .java sont acceptés.")
    if language == "python" and ext != ".py":
        raise HTTPException(status_code=400, detail="Seuls les fichiers .py sont acceptés.")
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture : {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCTION DES PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

def _issues_text(analysis: dict) -> str:
    issues = analysis.get("issues", [])
    if not issues:
        return "  Aucun problème majeur détecté par l'analyse statique."
    return "\n".join([
        f"  - [{i['code']}] {i['title']} (ligne {i['line']}) → {i['suggestion']}"
        for i in issues
    ])


def _extract_java_package(code: str) -> str:
    """Extrait la déclaration package d'un fichier Java (ex: 'package com.example.service;')"""
    match = re.search(r'^\s*(package\s+[\w.]+\s*;)', code, re.MULTILINE)
    return match.group(1).strip() if match else ""


def build_java_prompt(java_code: str, analysis: dict, target_version: str) -> str:
    version_features = {
        "8":  "lambdas, Stream API, Optional, java.time, default methods",
        "11": "var, String.strip()/isBlank()/lines(), HTTP Client",
        "17": "records, sealed classes, pattern matching instanceof, switch expressions, text blocks",
        "21": "virtual threads, sequenced collections, record patterns, switch pattern matching",
    }
    features = version_features.get(target_version, "fonctionnalités modernes Java")
    issues_text = _issues_text(analysis)
    package_decl = _extract_java_package(java_code)
    package_instruction = (
        f"0. OBLIGATOIRE : conserve exactement cette déclaration en première ligne : `{package_decl}`"
        if package_decl else
        "0. Ce fichier n'a pas de package — ne pas en ajouter."
    )

    return f"""Tu es un expert Java senior. Migre ce code vers Java {target_version}.

PROBLÈMES DÉTECTÉS (à corriger obligatoirement) :
{issues_text}

FEATURES Java {target_version} à utiliser : {features}

CODE SOURCE :
```java
{java_code}
```

INSTRUCTIONS STRICTES :
{package_instruction}
1. Corrige TOUS les problèmes listés ci-dessus
2. Utilise les features Java {target_version} listées
3. Préserve 100% de la logique métier (imports, noms de classes, signatures de méthodes)
4. Garde TOUS les imports nécessaires (java.sql.*, java.io.*, etc.)
5. Retourne UNIQUEMENT un objet JSON valide, sans texte avant ou après
6. N'ajoute pas de balises markdown autour du JSON

FORMAT DE RÉPONSE (JSON strict) :
{{
  "summary": "Résumé court de la migration en 2-3 phrases",
  "migrated_code": "// code Java {target_version} complet ici",
  "modifications": [
    {{
      "title": "Titre court du changement",
      "before": "ancien code",
      "after": "nouveau code",
      "explanation": "Pourquoi ce changement"
    }}
  ]
}}"""


def build_python_prompt(python_code: str, analysis: dict, target_version: str) -> str:
    version_features = {
        "3.8":  "walrus operator (:=), f-strings, typing module, pathlib, dataclasses",
        "3.10": "match/case (pattern matching), parenthesized context managers, better error messages",
        "3.12": "type aliases (type X = Y), @override decorator, improved f-strings, better performance",
    }
    features = version_features.get(target_version, "fonctionnalités modernes Python")
    issues_text = _issues_text(analysis)

    return f"""Tu es un expert Python senior. Modernise ce code vers Python {target_version}.

PROBLÈMES DÉTECTÉS (à corriger obligatoirement) :
{issues_text}

FEATURES Python {target_version} à utiliser : {features}

CODE SOURCE :
```python
{python_code}
```

INSTRUCTIONS STRICTES :
1. Corrige TOUS les problèmes listés ci-dessus
2. Utilise les features Python {target_version} listées
3. Remplace print() par logging, bare except: par des exceptions spécifiques (FileNotFoundError, ValueError, etc.)
4. Ajoute des type hints si absents
5. Préserve 100% de la logique métier ET tous les blocs try/except existants — ne jamais supprimer la gestion d'erreurs
6. OBLIGATOIRE : ajoute toujours `logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')` juste après les imports
7. OBLIGATOIRE : pour logger une exception utilise TOUJOURS f-string : `logging.error(f"Message: {{e}}")` — JAMAIS `logging.error("msg:", e)` car c'est invalide
8. Retourne UNIQUEMENT un objet JSON valide, sans texte avant ou après
9. N'ajoute pas de balises markdown autour du JSON

FORMAT DE RÉPONSE (JSON strict) :
{{
  "summary": "Résumé court de la migration en 2-3 phrases",
  "migrated_code": "# code Python {target_version} complet ici",
  "modifications": [
    {{
      "title": "Titre court du changement",
      "before": "ancien code",
      "after": "nouveau code",
      "explanation": "Pourquoi ce changement"
    }}
  ]
}}"""


def build_prompt(code: str, analysis: dict, target_version: str, language: str = "java") -> str:
    if language == "python":
        return build_python_prompt(code, analysis, target_version)
    return build_java_prompt(code, analysis, target_version)


# ─────────────────────────────────────────────────────────────────────────────
# APPEL AU LLM
# ─────────────────────────────────────────────────────────────────────────────

async def call_llm(prompt: str, language: str) -> str:
    lang_label = "Java" if language == "java" else "Python"
    try:
        response = await get_client().chat.completions.create(
            model       = os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages    = [
                {
                    "role":    "system",
                    "content": (
                        f"Tu es un expert {lang_label} spécialisé en migration de code legacy. "
                        "Tu retournes TOUJOURS un JSON valide et rien d'autre. "
                        "Pas de texte avant, pas de texte après, pas de balises markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature = 0.1,
            max_tokens  = 4096,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur LLM : {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# TRAITEMENT DE LA RÉPONSE
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_java_package(migrated_code: str, original_code: str) -> str:
    """
    Sécurité : si le LLM a oublié le 'package' dans le code migré,
    on le réinjecte automatiquement depuis l'original.
    """
    if not migrated_code:
        return migrated_code
    package_in_migrated = re.search(r'^\s*package\s+[\w.]+\s*;', migrated_code, re.MULTILINE)
    if package_in_migrated:
        return migrated_code  # Déjà présent, rien à faire
    original_package = _extract_java_package(original_code)
    if original_package:
        return original_package + "\n\n" + migrated_code
    return migrated_code


def process_response(raw: str, original_filename: str, language: str, original_code: str = "") -> dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*",     "", cleaned)
    cleaned = re.sub(r"\s*```$",     "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    summary       = data.get("summary", "")
    migrated_code = data.get("migrated_code", "")
    modifications = data.get("modifications", [])

    # ── Sécurité : réinjecter le package Java si oublié par le LLM ───────────
    if language == "java" and original_code:
        migrated_code = _ensure_java_package(migrated_code, original_code)

    saved_file = None
    if migrated_code:
        ext      = ".py" if language == "python" else ".java"
        stem     = Path(original_filename).stem
        out_path = MIGRATED_DIR / f"{stem}_migrated{ext}"
        try:
            out_path.write_text(migrated_code, encoding="utf-8")
            saved_file = str(out_path)
        except Exception:
            pass

    return {
        "summary":       summary,
        "migrated_code": migrated_code,
        "modifications": modifications,
        "saved_file":    saved_file,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATEUR PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

async def migrate_code_file(
    file_path:         str,
    original_filename: str,
    target_version:    str = "17",
    language:          str = "java",
) -> dict:
    """
    Pipeline complet (Java ou Python) :
      1. Lecture du fichier
      2. Analyse statique du code original
      3. Score avant migration
      4. Construction du prompt enrichi
      5. Appel LLM
      6. Traitement de la réponse
      7. Analyse statique du code migré
      8. Score après migration
      9. Calcul de l'amélioration
    """
    analyze = analyze_python_code if language == "python" else analyze_java_code

    original_code    = read_file(file_path, language)
    analysis_before  = analyze(original_code)
    score_before     = compute_score(analysis_before)
    prompt           = build_prompt(original_code, analysis_before, target_version, language)
    raw_response     = await call_llm(prompt, language)
    result           = process_response(raw_response, original_filename, language, original_code)

    analysis_after = analyze(result["migrated_code"]) if result["migrated_code"] else {}
    score_after    = (
        compute_score(analysis_after)
        if analysis_after
        else {"score": 0, "grade": "N/A", "risk_level": "N/A", "issues_count": 0}
    )
    improvement = compute_improvement(score_before, score_after)

    return {
        "language":        language,
        "original_code":   original_code,
        "migrated_code":   result["migrated_code"],
        "summary":         result["summary"],
        "modifications":   result["modifications"],
        "analysis_before": analysis_before,
        "analysis_after":  analysis_after,
        "score_before":    score_before,
        "score_after":     score_after,
        "improvement":     improvement,
        "saved_file":      result["saved_file"],
    }


# Alias rétro-compatible
async def migrate_java_file(
    file_path:         str,
    original_filename: str,
    target_version:    str = "17",
) -> dict:
    return await migrate_code_file(file_path, original_filename, target_version, "java")


# ─────────────────────────────────────────────────────────────────────────────
# IDÉE 1 — BOUCLE DE RÉFLEXION (comportement agentique)
# L'agent migre, ré-analyse son propre output, et corrige si nécessaire.
# ─────────────────────────────────────────────────────────────────────────────

async def migrate_with_reflection(
    file_path:         str,
    original_filename: str,
    target_version:    str = "17",
    language:          str = "java",
    max_iterations:    int = MAX_REFLECTION_ITERATIONS,
) -> dict:
    """
    Pipeline agentique avec boucle de réflexion :
    1. Migration initiale
    2. L'agent analyse SON propre code migré
    3. S'il reste des problèmes → l'agent reçoit le feedback et corrige
    4. Répéter jusqu'à 0 problème ou max_iterations atteint
    """
    from app.agent.memory import get_memory

    analyze = analyze_python_code if language == "python" else analyze_java_code
    memory  = get_memory()

    original_code   = read_file(file_path, language)
    analysis_before = analyze(original_code)
    score_before    = compute_score(analysis_before)

    # Consulter la mémoire pour enrichir le premier prompt
    past_memories = memory.recall_migration(
        language    = language,
        issue_codes = [i["code"] for i in analysis_before.get("issues", [])],
    )
    memory_context = memory.format_migration_context(past_memories)

    current_code = original_code
    iterations   = []

    for i in range(1, max_iterations + 1):
        current_analysis = analyze(current_code)
        issues_left      = current_analysis.get("issues_count", 0)

        # Construire le prompt enrichi
        base_prompt = build_prompt(current_code, current_analysis, target_version, language)

        if i == 1:
            # Premier appel : inclure la mémoire
            prompt = f"{memory_context}\n\n{base_prompt}"
        else:
            # Itérations suivantes : feedback explicite sur ce qui reste
            remaining = [
                f"[{iss['code']}] {iss['title']} ligne {iss['line']}"
                for iss in current_analysis.get("issues", [])
            ]
            feedback = (
                f"\n\n⚠ FEEDBACK ITÉRATION {i} : "
                f"Ton code précédent contient encore {issues_left} problème(s) :\n"
                + "\n".join(f"  - {r}" for r in remaining)
                + "\nCorrige-les impérativement dans cette itération."
            )
            prompt = base_prompt + feedback

        raw      = await call_llm(prompt, language)
        result   = process_response(raw, original_filename, language, original_code)
        migrated = result.get("migrated_code", "")

        if not migrated:
            break

        analysis_iter = analyze(migrated)
        score_iter    = compute_score(analysis_iter)

        iterations.append({
            "iteration":       i,
            "issues_before":   issues_left,
            "issues_after":    analysis_iter.get("issues_count", 0),
            "score":           score_iter.get("score", 0),
            "summary":         result.get("summary", ""),
            "modifications":   result.get("modifications", []),
        })

        current_code = migrated

        if analysis_iter.get("issues_count", 0) == 0:
            break   # Agent satisfait : plus aucun problème

    # ── Résultat final ────────────────────────────────────────────────────────
    final_analysis = analyze(current_code)
    score_after    = compute_score(final_analysis)
    improvement    = compute_improvement(score_before, score_after)

    # ── Sauvegarder le fichier final ──────────────────────────────────────────
    ext      = ".py" if language == "python" else ".java"
    stem     = Path(original_filename).stem
    out_path = MIGRATED_DIR / f"{stem}_migrated{ext}"
    try:
        out_path.write_text(current_code, encoding="utf-8")
    except Exception:
        pass

    # ── Mettre à jour la mémoire ──────────────────────────────────────────────
    memory.remember_migration(
        language        = language,
        issue_codes     = [i["code"] for i in analysis_before.get("issues", [])],
        target_version  = target_version,
        iterations_used = len(iterations),
        score_delta     = improvement.get("score_delta", 0),
        issues_fixed    = improvement.get("issues_fixed", 0),
        best_approach   = (
            f"{len(iterations)} itération(s), "
            f"score {score_before.get('score')}→{score_after.get('score')}"
        ),
    )

    return {
        "language":         language,
        "original_code":    original_code,
        "migrated_code":    current_code,
        "summary":          iterations[-1]["summary"] if iterations else "",
        "modifications":    iterations[-1]["modifications"] if iterations else [],
        "analysis_before":  analysis_before,
        "analysis_after":   final_analysis,
        "score_before":     score_before,
        "score_after":      score_after,
        "improvement":      improvement,
        "saved_file":       str(out_path),
        "agent_trace": {
            "mode":             "reflection",
            "iterations_used":  len(iterations),
            "max_iterations":   max_iterations,
            "memory_used":      len(past_memories) > 0,
            "iterations":       iterations,
        },
    }
