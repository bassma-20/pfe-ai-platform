"""
routes.py — Endpoints FastAPI du module de migration (Java + Python)
"""

import logging
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

@router.post("/migrate-multi-agent", summary="Migration multi-agents : Analyste + Migrateur + Vérificateur")
async def migrate_file_multi_agent(
    filename: str,
    target_version: str = "17",
    max_rework: int = 2,
):
    """
    Pipeline multi-agents coordonnés par un orchestrateur :
    1. AnalyzerAgent  → enrichissement sémantique de l'analyse
    2. MigratorAgent  → migration avec contexte enrichi + mémoire
    3. VerifierAgent  → vérification qualité (logique préservée ? régressions ?)
    L'orchestrateur peut relancer le migrateur si des problèmes sont détectés.
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

    if max_rework < 0 or max_rework > 3:
        raise HTTPException(status_code=400, detail="max_rework doit être entre 0 et 3.")

    original_code = file_path.read_text(encoding="utf-8")

    orchestrator = MigrationOrchestrator()
    result = await orchestrator.run(
        original_code     = original_code,
        original_filename = filename,
        language          = language,
        target_version    = target_version,
        max_rework        = max_rework,
    )

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
            return {
                "language": "python",
                "stdout":    proc.stdout,
                "stderr":    proc.stderr,
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
