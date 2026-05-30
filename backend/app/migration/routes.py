"""
routes.py — Endpoints FastAPI du module de migration (Java + Python)
"""

import asyncio
import logging
import re
import subprocess
import tempfile
import traceback
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.migration.service import migrate_code_file, migrate_with_reflection
from app.migration.multi_agent import MigrationOrchestrator

router = APIRouter()

UPLOAD_DIR   = Path("data/uploads/migration")
MIGRATED_DIR = Path("data/migrated")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MIGRATED_DIR.mkdir(parents=True, exist_ok=True)

VALID_JAVA_VERSIONS   = {"8", "11", "17", "21"}
VALID_PYTHON_VERSIONS = {"3.8", "3.10", "3.12"}
VALID_EXTENSIONS      = {".java", ".py"}


def _detect_language(filename: str) -> str:
    return "python" if filename.endswith(".py") else "java"


# ─────────────────────────────────────────────────────────────────────────────
# POST /upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload d'un fichier Java ou Python")
async def upload_file(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in VALID_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers .java et .py sont acceptés."
        )

    content = await file.read()
    if len(content) > 1 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux. Max : 1 MB.")

    # Sauvegarder avec extension .upload pour éviter le rechargement uvicorn
    save_path = UPLOAD_DIR / (file.filename + ".upload")
    save_path.write_bytes(content)

    return {
        "message":    "Fichier uploadé avec succès.",
        "filename":   file.filename,
        "language":   _detect_language(file.filename),
        "size_bytes": len(content),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /migrate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/migrate", summary="Migrer un fichier Java ou Python via LLM")
async def migrate_file(filename: str, target_version: str = "17"):
    """
    Lance la migration complète d'un fichier Java ou Python.

    Paramètres :
    - filename       : nom du fichier uploadé (ex: MyService.java ou script.py)
    - target_version : Java → 8|11|17|21 (défaut: 17) | Python → 3.8|3.10|3.12

    Retourne :
    - language, original_code, migrated_code
    - analysis_before, analysis_after
    - score_before, score_after, improvement
    - modifications, summary, saved_file
    """
    language = _detect_language(filename)

    valid_versions = VALID_PYTHON_VERSIONS if language == "python" else VALID_JAVA_VERSIONS
    if target_version not in valid_versions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Version invalide : '{target_version}'. "
                f"Valeurs acceptées pour {language} : {sorted(valid_versions)}"
            )
        )

    file_path = UPLOAD_DIR / (filename + ".upload")
    if not file_path.exists():
        # Fallback : ancienne convention sans .upload
        file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Fichier '{filename}' introuvable. Uploadez-le d'abord via /upload."
        )

    result = await migrate_code_file(
        file_path         = str(file_path),
        original_filename = filename,
        target_version    = target_version,
        language          = language,
    )

    lang_label = f"Python {target_version}" if language == "python" else f"Java {target_version}"

    return {
        "status":          "success",
        "filename":        filename,
        "language":        language,
        "target_version":  lang_label,
        "original_code":   result["original_code"],
        "migrated_code":   result["migrated_code"],
        "summary":         result["summary"],
        "modifications":   result["modifications"],
        "analysis_before": result["analysis_before"],
        "analysis_after":  result["analysis_after"],
        "score_before":    result["score_before"],
        "score_after":     result["score_after"],
        "improvement":     result["improvement"],
        "saved_file":      result["saved_file"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /migrate-agent   (Idée 1 — boucle de réflexion)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/migrate-agent", summary="Migration agentique avec boucle de réflexion (max 3 itérations)")
async def migrate_file_agent(
    filename: str,
    target_version: str = "17",
    max_iterations: int = 3,
):
    """
    Migration avec boucle de réflexion :
    L'agent migre, analyse son propre résultat, se corrige si nécessaire.
    Retourne la trace complète des itérations + mémoire utilisée.
    """
    language = _detect_language(filename)

    valid_versions = VALID_PYTHON_VERSIONS if language == "python" else VALID_JAVA_VERSIONS
    if target_version not in valid_versions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Version invalide : '{target_version}'. "
                f"Valeurs acceptées pour {language} : {sorted(valid_versions)}"
            )
        )

    file_path = UPLOAD_DIR / (filename + ".upload")
    if not file_path.exists():
        file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Fichier '{filename}' introuvable. Uploadez-le d'abord via /upload."
        )

    if max_iterations < 1 or max_iterations > 5:
        raise HTTPException(status_code=400, detail="max_iterations doit être entre 1 et 5.")

    try:
        result = await migrate_with_reflection(
            file_path         = str(file_path),
            original_filename = filename,
            target_version    = target_version,
            language          = language,
            max_iterations    = max_iterations,
        )
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[migrate-agent] ERREUR : {e}\n{tb}")
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "traceback": tb,
            "hint": "Vérifiez le terminal backend pour le détail complet"
        })

    lang_label = f"Python {target_version}" if language == "python" else f"Java {target_version}"

    return {
        "status":          "success",
        "mode":            "agent_reflection",
        "filename":        filename,
        "language":        language,
        "target_version":  lang_label,
        "original_code":   result["original_code"],
        "migrated_code":   result["migrated_code"],
        "summary":         result["summary"],
        "modifications":   result["modifications"],
        "analysis_before": result["analysis_before"],
        "analysis_after":  result["analysis_after"],
        "score_before":    result["score_before"],
        "score_after":     result["score_after"],
        "improvement":     result["improvement"],
        "saved_file":      result["saved_file"],
        "agent_trace":     result["agent_trace"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /migrate-multi-agent   (Idée 4 — 3 agents coordonnés)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/migrate-multi-agent", summary="Migration multi-agents : Analyste + Migrateur(s) + Vérificateur")
async def migrate_file_multi_agent(
    filename: str,
    target_version: str = "17",
    max_rework: int = 3,
):
    """
    Pipeline de réparation progressive multi-agents :
    1. AnalyzerAgent   → enrichissement sémantique de l'analyse
    2. MigratorAgent   → migration du code (peut tourner jusqu'à max_rework+1 fois)
    3. DeterministicFixer → corrections regex garanties après chaque migration
    4. VerifierAgent   → rapport qualité final (1 seul appel LLM, à la fin)

    Entre les tentatives, l'orchestrateur utilise l'analyseur statique (sans LLM)
    pour décider si une nouvelle passe est nécessaire.
    Arrêt dès que 0 problème restant ou stagnation détectée.
    """
    logger.info(f"[migrate-multi-agent] START — filename={filename} target={target_version} max_rework={max_rework}")
    try:
        language = _detect_language(filename)

        valid_versions = VALID_PYTHON_VERSIONS if language == "python" else VALID_JAVA_VERSIONS
        if target_version not in valid_versions:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Version invalide : '{target_version}'. "
                    f"Valeurs acceptées pour {language} : {sorted(valid_versions)}"
                )
            )

        file_path = UPLOAD_DIR / (filename + ".upload")
        if not file_path.exists():
            file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Fichier '{filename}' introuvable. Uploadez-le d'abord via /upload."
            )

        if max_rework < 0 or max_rework > 5:
            raise HTTPException(status_code=400, detail="max_rework doit être entre 0 et 5.")

        logger.info(f"[migrate-multi-agent] Lecture fichier : {file_path}")
        original_code = file_path.read_text(encoding="utf-8")
        logger.info(f"[migrate-multi-agent] Fichier lu ({len(original_code)} chars) — création orchestrateur")

        orchestrator = MigrationOrchestrator()
        logger.info("[migrate-multi-agent] Orchestrateur créé — lancement pipeline")

        result = await orchestrator.run(
            original_code     = original_code,
            original_filename = filename,
            language          = language,
            target_version    = target_version,
            max_rework        = max_rework,
        )
        logger.info("[migrate-multi-agent] Pipeline terminé avec succès")

    except HTTPException:
        raise
    except asyncio.CancelledError:
        logger.warning("[migrate-multi-agent] Requête annulée (timeout client ou redémarrage)")
        return JSONResponse(status_code=503, content={"error": "Requête annulée — pipeline trop long ou timeout. Réessayez ou réduisez max_rework."})
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"[migrate-multi-agent] ERREUR FATALE : {type(e).__name__}: {e}\n{tb}")
        return JSONResponse(status_code=500, content={
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": tb,
            "hint": "Vérifiez le terminal backend pour le détail complet"
        })

    lang_label = f"Python {target_version}" if language == "python" else f"Java {target_version}"

    return {
        "status":          "success",
        "mode":            "multi_agent",
        "filename":        filename,
        "language":        language,
        "target_version":  lang_label,
        "original_code":   result["original_code"],
        "migrated_code":   result["migrated_code"],
        "summary":         result["summary"],
        "modifications":   result["modifications"],
        "analysis_before": result["analysis_before"],
        "analysis_after":  result["analysis_after"],
        "score_before":    result["score_before"],
        "score_after":     result["score_after"],
        "improvement":     result["improvement"],
        "saved_file":      result["saved_file"],
        "agent_trace":     result["agent_trace"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /download/{filename}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/download/{filename}", summary="Télécharger le fichier migré")
async def download_migrated_file(filename: str):
    stem = Path(filename).stem.replace("_migrated", "")
    is_python = filename.endswith(".py") or (
        not filename.endswith(".java") and not filename.endswith("_migrated.java")
    )

    if is_python:
        target = MIGRATED_DIR / f"{stem}_migrated.py"
        media  = "text/x-python"
        dl     = f"{stem}_migrated.py"
    else:
        target = MIGRATED_DIR / f"{stem}_migrated.java"
        media  = "text/x-java-source"
        dl     = f"{stem}_migrated.java"

    # Fallback : chercher n'importe quelle extension
    if not target.exists():
        for ext in (".java", ".py"):
            candidate = MIGRATED_DIR / f"{stem}_migrated{ext}"
            if candidate.exists():
                target = candidate
                break

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Fichier '{filename}' migré introuvable.")

    return FileResponse(path=str(target), media_type=media, filename=dl)


# ─────────────────────────────────────────────────────────────────────────────
# GET /history
# ─────────────────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    code: str
    language: str  # "python" | "java"


@router.post("/execute", summary="Exécuter le code migré dans un sandbox")
async def execute_migrated_code(req: ExecuteRequest):
    """
    Exécute le code migré dans un subprocess sécurisé (timeout 10s).
    Supporte Python uniquement pour l'instant (Java nécessite javac + jvm).
    """
    if req.language not in ("python", "java"):
        raise HTTPException(status_code=400, detail="Langage non supporté")

    if req.language == "python":
        # Créer un dossier temporaire pour l'exécution
        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir) / "migrated.py"
        tmp_path.write_text(req.code, encoding="utf-8")

        # Créer des fichiers de test courants pour éviter les FileNotFoundError
        (Path(tmp_dir) / "data.json").write_text("[]", encoding="utf-8")
        (Path(tmp_dir) / "orders.log").write_text("", encoding="utf-8")
        (Path(tmp_dir) / "transactions.log").write_text("", encoding="utf-8")
        (Path(tmp_dir) / "log.txt").write_text("", encoding="utf-8")

        try:
            proc = subprocess.run(
                ["python", str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=tmp_dir,
            )
            stderr = proc.stderr
            # Détecter les erreurs de dépendances manquantes et donner un conseil
            if proc.returncode != 0 and "ModuleNotFoundError" in stderr:
                import re as _re
                m = _re.search(r"No module named '([^']+)'", stderr)
                missing = m.group(1) if m else "une bibliothèque externe"
                stderr += (
                    f"\n\n💡 CONSEIL : Ce code utilise '{missing}' qui n'est pas installé sur le serveur.\n"
                    "   → Utilisez le bouton '🤖 IA + Exécuter' qui remplace automatiquement\n"
                    "     les dépendances externes par des données mockées pour tester la logique."
                )
            return {
                "language": "python",
                "stdout":    proc.stdout,
                "stderr":    stderr,
                "exit_code": proc.returncode,
                "success":   proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "language": "python",
                "stdout":    "",
                "stderr":    "⏱ Timeout : le code a dépassé 10 secondes d'exécution.",
                "exit_code": -1,
                "success":   False,
            }
        except FileNotFoundError:
            return {
                "language": "python",
                "stdout":    "",
                "stderr":    "Python introuvable sur le serveur.",
                "exit_code": -1,
                "success":   False,
            }
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif req.language == "java":
        import re
        match = re.search(r'public\s+class\s+(\w+)', req.code)
        class_name = match.group(1) if match else "Main"

        # Vérifier que le code contient un main exécutable
        if "public static void main" not in req.code:
            return {
                "language": "java",
                "stdout":   "",
                "stderr":   "⚠️ Ce code ne contient pas de méthode main() — il ne peut pas être exécuté directement.\nIl s'agit d'une classe de service/utilitaire.",
                "exit_code": -1,
                "success":  False,
            }

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                src = Path(tmpdir) / f"{class_name}.java"
                src.write_text(req.code, encoding="utf-8")
                compile_proc = subprocess.run(
                    ["javac", str(src)],
                    capture_output=True, text=True, timeout=15, cwd=tmpdir,
                )
                if compile_proc.returncode != 0:
                    return {
                        "language": "java",
                        "stdout":   "",
                        "stderr":   f"Erreur de compilation :\n{compile_proc.stderr}",
                        "exit_code": compile_proc.returncode,
                        "success":  False,
                    }
                run_proc = subprocess.run(
                    ["java", class_name],
                    capture_output=True, text=True, timeout=10, cwd=tmpdir,
                )
                return {
                    "language": "java",
                    "stdout":   run_proc.stdout,
                    "stderr":   run_proc.stderr,
                    "exit_code": run_proc.returncode,
                    "success":  run_proc.returncode == 0,
                }
        except FileNotFoundError:
            return {
                "language": "java",
                "stdout":   "",
                "stderr":   "❌ javac introuvable.\nInstallez le JDK : https://adoptium.net puis redémarrez le serveur.",
                "exit_code": -1,
                "success":  False,
            }
        except subprocess.TimeoutExpired:
            return {
                "language": "java",
                "stdout":   "",
                "stderr":   "⏱ Timeout : exécution dépassée (15s).",
                "exit_code": -1,
                "success":  False,
            }


class GenerateMainRequest(BaseModel):
    code: str
    language: str  # "java" | "python"


@router.post("/generate-and-execute", summary="Générer un main() via LLM puis exécuter")
async def generate_main_and_execute(req: GenerateMainRequest):
    """
    1. Utilise le LLM pour ajouter un main() de démonstration au code
    2. Compile et exécute le résultat
    """
    import os
    from openai import AsyncOpenAI

    if req.language not in ("python", "java"):
        raise HTTPException(status_code=400, detail="Langage non supporté")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY manquante.")
    client = AsyncOpenAI(api_key=api_key)

    # ── Demander au LLM de générer le main() ────────────────────────────────
    if req.language == "java":
        prompt = f"""Tu as ce code Java. Modifie-le pour le rendre exécutable avec un simple `javac` sans dépendances externes.

RÈGLES STRICTES (toutes obligatoires) :
1. UNIQUEMENT des imports java.* et javax.* standard du JDK — JAMAIS org.slf4j, log4j, spring, etc.
2. Remplace tout logger externe (org.slf4j, log4j) par java.util.logging.Logger du JDK
3. Remplace la déclaration du logger : `private static final Logger logger = Logger.getLogger(NomClasse.class.getName());`
4. Si la classe a des dépendances (ex: Employee, User), définis-les comme classes internes statiques simples DANS le même fichier
5. Ajoute une méthode `public static void main(String[] args)` qui :
   - Crée des objets fictifs avec des données hardcodées réalistes
   - Appelle TOUTES les méthodes publiques non-DB
   - Affiche les résultats avec System.out.println()
   - Commente ou remplace les appels DB par des données mockées
6. Supprime le `package com.company.hr;` (nécessite une structure de dossiers)
7. Le fichier doit compiler avec : javac NomFichier.java (SANS classpath externe)

Retourne UNIQUEMENT le code Java complet modifié, sans markdown, sans explication.

CODE:
{req.code}"""
    else:
        prompt = f"""Tu as ce code Python. Transforme-le pour qu'il soit exécutable avec un simple `python script.py` sans installer aucune bibliothèque externe.

RÈGLES STRICTES (toutes obligatoires) :
1. SUPPRIME ou REMPLACE tous les imports de bibliothèques tierces non-standard :
   - `import MySQLdb` → supprimer, utiliser des données mockées à la place
   - `import pymysql`, `import psycopg2`, `import cx_Oracle` → idem, supprimer
   - `import redis`, `import pymongo`, `import elasticsearch` → idem, supprimer
   - `import requests`, `import httpx`, `import aiohttp` → remplacer par données hardcodées
   - Garde UNIQUEMENT les modules de la bibliothèque standard Python (os, sys, json, logging, datetime, pathlib, typing, re, math, collections, functools, itertools, etc.)
2. Remplace TOUTES les connexions DB par des données mockées hardcodées (listes, dicts)
3. Remplace TOUS les appels réseau (API, HTTP) par des données fictives hardcodées
4. Ajoute un bloc `if __name__ == '__main__':` qui :
   - Crée des instances fictives avec des données hardcodées réalistes
   - Appelle TOUTES les fonctions et méthodes publiques
   - Affiche les résultats avec print()
5. Le code doit s'exécuter avec UNIQUEMENT la bibliothèque standard Python, sans pip install

Retourne UNIQUEMENT le code Python complet modifié, sans markdown, sans explication.

CODE:
{req.code}"""

    try:
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu es un expert en génération de code de test. Tu retournes UNIQUEMENT du code, jamais de markdown ni d'explication."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=3000,
        )
        generated_code = response.choices[0].message.content.strip()
        # Nettoyer les éventuels blocs markdown
        generated_code = re.sub(r"^```\w*\s*", "", generated_code)
        generated_code = re.sub(r"\s*```$", "", generated_code)
        generated_code = generated_code.strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur LLM : {str(e)}")

    # ── Exécuter le code généré ──────────────────────────────────────────────
    if req.language == "python":
        tmp_dir = tempfile.mkdtemp()
        tmp_path = Path(tmp_dir) / "generated_main.py"
        tmp_path.write_text(generated_code, encoding="utf-8")
        for dummy in ("data.json", "log.txt", "orders.log"):
            (Path(tmp_dir) / dummy).write_text("[]" if dummy.endswith(".json") else "", encoding="utf-8")
        try:
            proc = subprocess.run(
                ["python", str(tmp_path)],
                capture_output=True, text=True, timeout=15, cwd=tmp_dir,
            )
            return {
                "language": "python",
                "generated_code": generated_code,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
                "success": proc.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"language": "python", "generated_code": generated_code, "stdout": "", "stderr": "Timeout 15s", "exit_code": -1, "success": False}
        finally:
            import shutil; shutil.rmtree(tmp_dir, ignore_errors=True)

    else:  # java
        match = re.search(r'public\s+class\s+(\w+)', generated_code)
        class_name = match.group(1) if match else "EmployeeService"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                src = Path(tmpdir) / f"{class_name}.java"
                src.write_text(generated_code, encoding="utf-8")
                compile_proc = subprocess.run(
                    ["javac", str(src)],
                    capture_output=True, text=True, timeout=20, cwd=tmpdir,
                )
                if compile_proc.returncode != 0:
                    return {
                        "language": "java",
                        "generated_code": generated_code,
                        "stdout": "",
                        "stderr": f"Erreur compilation :\n{compile_proc.stderr}",
                        "exit_code": compile_proc.returncode,
                        "success": False,
                    }
                run_proc = subprocess.run(
                    ["java", class_name],
                    capture_output=True, text=True, timeout=10, cwd=tmpdir,
                )
                return {
                    "language": "java",
                    "generated_code": generated_code,
                    "stdout": run_proc.stdout,
                    "stderr": run_proc.stderr,
                    "exit_code": run_proc.returncode,
                    "success": run_proc.returncode == 0,
                }
        except FileNotFoundError:
            return {"language": "java", "generated_code": generated_code, "stdout": "", "stderr": "javac introuvable. Vérifiez que le JDK est dans le PATH.", "exit_code": -1, "success": False}
        except subprocess.TimeoutExpired:
            return {"language": "java", "generated_code": generated_code, "stdout": "", "stderr": "Timeout 20s", "exit_code": -1, "success": False}


@router.get("/history", summary="Liste des fichiers migrés")
async def list_migrated_files():
    files = sorted(
        [f for f in MIGRATED_DIR.glob("*_migrated.*") if f.suffix in {".java", ".py"}],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return {"count": 0, "files": []}
    return {
        "count": len(files),
        "files": [
            {
                "filename":     f.name,
                "language":     "python" if f.suffix == ".py" else "java",
                "size_bytes":   f.stat().st_size,
                "download_url": f"/api/migration/download/{f.name}",
            }
            for f in files
        ],
    }
