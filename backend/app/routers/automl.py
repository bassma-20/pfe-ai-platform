"""
backend/app/routers/automl.py

Router FastAPI AutoML — Version robuste.
Gère les datasets sales, les erreurs LLM, les crashs d'entraînement.
Retourne toujours un JSON structuré, jamais un 500 brut.

✅ FIXES :
  - _build_summary_safe renommé en _build_minimal_summary (cohérence)
  - suggest_target utilise _build_minimal_summary (plus _build_summary_safe)
  - DATA_DIR calculé en absolu depuis l'emplacement du fichier
  - run-full-pipeline lit training_result depuis _RUN_STORE (pas run local)
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse

from app.automl.models.schemas import (
    ApplyPlanResponse,
    DatasetSummary,
    ColumnInfo,
    DecisionPlanRequest,
    DecisionPlanResponse,
    FinalUserReport,
    LLMDecisionPlan,
    ReportResponse,
    TrainWithPlanResponse,
    TechnicalInsights,
    ExecutiveSummary,
    ActionableRecommendation,
    ProblemType,
)
from app.automl.service.data_service import (
    clean_dataset,
    validate_for_training,
    CleaningReport,
)
from app.automl.service.llm_service import (
    build_dataset_summary,
    generate_decision_plan,
    generate_fallback_plan,
    generate_report_explanation,
    suggest_target_and_type,
)
from app.automl.service.action_executor_service import (
    execute_plan,
    validate_plan_against_df,
)
from app.automl.service.training_service import (
    train_with_plan,
    predict_with_saved_model,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automl", tags=["AutoML"])

_RUN_STORE: Dict[str, Dict[str, Any]] = {}

# ✅ Chemin absolu calculé depuis l'emplacement de ce fichier
# __file__ = .../backend/app/routers/automl.py
# remonte : routers/ → app/ → automl/data/
_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv(
    "AUTOML_DATA_DIR",
    os.path.normpath(os.path.join(_HERE, "..", "automl", "data"))
)
logger.info(f"[Config] DATA_DIR = {DATA_DIR}")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _get_run(run_id: str) -> Dict[str, Any]:
    if run_id not in _RUN_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "step": "lookup",
                "error": f"run_id '{run_id}' introuvable.",
                "suggestion": "Uploadez d'abord le dataset via POST /api/automl/upload",
            }
        )
    return _RUN_STORE[run_id]


def _error_response(
    step: str,
    error: str,
    run_id: Optional[str] = None,
    errors_detected: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    suggestion: Optional[str] = None,
    http_code: int = 500,
):
    """Retourne toujours un JSON structuré — jamais un 500 brut."""
    content = {
        "status": "error",
        "step": step,
        "run_id": run_id,
        "error": str(error),
        "errors_detected": errors_detected or [],
        "warnings": warnings or [],
        "suggestion": suggestion,
    }
    return JSONResponse(status_code=http_code, content=content)


def _cleaning_report_to_dict(report: CleaningReport) -> Dict[str, Any]:
    return {
        "dataset_shape_before": list(report.dataset_shape_before),
        "dataset_shape_after": list(report.dataset_shape_after),
        "rows_removed": report.dataset_shape_before[0] - report.dataset_shape_after[0],
        "cols_removed": report.dataset_shape_before[1] - report.dataset_shape_after[1],
        "errors_detected": report.errors_detected,
        "cleaning_actions_applied": report.cleaning_actions_applied,
        "warnings": report.warnings,
        "columns_dropped": report.columns_dropped,
        "columns_converted": report.columns_converted,
        "duplicates_removed": report.duplicates_removed,
        "nulls_filled": report.nulls_filled,
        "outliers_clipped": report.outliers_clipped,
        "impossible_values_fixed": report.impossible_values_fixed,
        "leakage_suspects": report.leakage_suspects,
    }


def _build_minimal_summary(
    df: pd.DataFrame,
    run_id: str,
    target_column: Optional[str],
    problem_type: Optional[str],
) -> DatasetSummary:
    """
    ✅ Construit un DatasetSummary robuste depuis un DataFrame.
    Utilisé comme fallback si build_dataset_summary() échoue.
    Ne retourne JAMAIS None.
    """
    columns = []
    for col in df.columns:
        try:
            series = df[col]
            is_numeric = pd.api.types.is_numeric_dtype(series)

            raw_samples = series.dropna().head(3).tolist()
            safe_samples: List[Any] = []
            for v in raw_samples:
                try:
                    if hasattr(v, "item"):
                        safe_samples.append(v.item())
                    elif isinstance(v, (int, float, str, bool)):
                        safe_samples.append(v)
                    else:
                        safe_samples.append(str(v))
                except Exception:
                    safe_samples.append(str(v))

            columns.append(ColumnInfo(
                name=col,
                dtype=str(series.dtype),
                null_count=int(series.isnull().sum()),
                null_pct=round(float(series.isnull().mean() * 100), 2),
                unique_count=int(series.nunique()),
                sample_values=safe_samples,
                is_numeric=is_numeric,
            ))
        except Exception as e:
            logger.warning(f"[Summary] Colonne '{col}' ignorée : {e}")

    # Class balance
    class_balance = None
    if target_column and target_column in df.columns:
        if problem_type in ("binary_classification", "multiclass_classification"):
            try:
                vc = df[target_column].value_counts(normalize=True)
                class_balance = {str(k): round(float(v), 3) for k, v in vc.items()}
            except Exception:
                pass

    pt = None
    if problem_type:
        try:
            pt = ProblemType(problem_type)
        except ValueError:
            pass

    return DatasetSummary(
        run_id=run_id,
        n_rows=len(df),
        n_cols=len(df.columns),
        target_column=target_column,
        problem_type=pt,
        columns=columns,
        duplicate_rows=int(df.duplicated().sum()),
        total_null_pct=round(float(df.isnull().mean().mean() * 100), 2),
        class_balance=class_balance,
    )


def _get_or_rebuild_summary(
    run: Dict[str, Any],
    run_id: str,
) -> Optional[DatasetSummary]:
    """
    Retourne le summary existant ou le reconstruit depuis df_current.
    Utilisé dans suggest_target et generate_plan pour éviter les None.
    """
    summary = run.get("summary")

    # Summary absent ou sans colonnes → reconstruire
    if summary is None or not summary.columns:
        logger.warning(f"[Summary] Summary absent/vide pour {run_id} — reconstruction")
        try:
            df = run["df_current"]
            target = summary.target_column if summary else None
            summary = _build_minimal_summary(df, run_id, target, None)
            _RUN_STORE[run_id]["summary"] = summary
            logger.info(f"[Summary] Reconstruction OK : {summary.n_rows} rows, {len(summary.columns)} cols")
        except Exception as e:
            logger.error(f"[Summary] Reconstruction échouée : {e}")
            summary = None

    return summary


# ─────────────────────────────────────────────
# ENDPOINT 1 — Upload Robuste
# POST /api/automl/upload
# ─────────────────────────────────────────────

@router.post("/upload", summary="Upload dataset (robuste — gère les données sales)")
async def upload_dataset(
    file: UploadFile = File(...),
    target_column: Optional[str] = Query(default=None),
    problem_type: Optional[str] = Query(default=None),
):
    run_id = str(uuid.uuid4())[:8]
    filename = file.filename or "dataset"

    if not any(filename.lower().endswith(ext) for ext in [".csv", ".xlsx", ".xls"]):
        return _error_response(
            step="upload",
            error=f"Format non supporté : '{filename}'",
            suggestion="Utilisez un fichier CSV (.csv) ou Excel (.xlsx, .xls)",
            http_code=400,
        )

    try:
        content = await file.read()
    except Exception as e:
        return _error_response(step="upload", error=f"Impossible de lire le fichier : {e}", http_code=400)

    if len(content) == 0:
        return _error_response(step="upload", error="Le fichier est vide.", http_code=400)

    if len(content) > 100 * 1024 * 1024:
        return _error_response(step="upload", error="Fichier trop volumineux (max 100 MB).", http_code=413)

    # ✅ Nettoyage automatique avec target_column passé
    try:
        df, cleaning_report = clean_dataset(
            content=content,
            filename=filename,
            target_column=target_column,
        )
    except ValueError as e:
        return _error_response(
            step="upload",
            error=str(e),
            suggestion="Vérifiez que le fichier est un CSV/Excel valide avec au moins 2 colonnes.",
            http_code=400,
        )
    except Exception as e:
        logger.exception(f"[Upload] Erreur inattendue : {e}")
        return _error_response(step="upload", error=f"Erreur lors du nettoyage : {str(e)}", http_code=500)

    if df.empty or len(df) < 5:
        return _error_response(
            step="upload",
            error=f"Dataset trop petit après nettoyage ({len(df)} lignes).",
            errors_detected=cleaning_report.errors_detected,
            warnings=cleaning_report.warnings,
            suggestion="Vérifiez que votre dataset contient suffisamment de données valides.",
            http_code=422,
        )

    # ✅ Construction du summary — jamais None
    summary = None
    try:
        summary = build_dataset_summary(
            df=df,
            run_id=run_id,
            target_column=target_column,
            problem_type=problem_type,
        )
        logger.info(f"[Upload] Summary complet : {summary.n_rows} rows, {summary.n_cols} cols")
    except Exception as e:
        logger.warning(f"[Upload] build_dataset_summary échoué ({e}) — fallback minimal")

    if summary is None:
        try:
            summary = _build_minimal_summary(df, run_id, target_column, problem_type)
            logger.info(f"[Upload] Summary minimal : {summary.n_rows} rows")
        except Exception as e:
            logger.error(f"[Upload] Summary minimal aussi échoué : {e}")
            # Ultra-fallback : summary vide mais non-None
            summary = DatasetSummary(
                run_id=run_id,
                n_rows=len(df),
                n_cols=len(df.columns),
                target_column=target_column,
                columns=[],
                duplicate_rows=0,
                total_null_pct=0.0,
            )

    # Stockage
    _RUN_STORE[run_id] = {
        "df_original": df.copy(),
        "df_current": df.copy(),
        "cleaning_report": cleaning_report,
        "summary": summary,
        "plan": None,
        "execution_report": None,
        "training_result": None,
        "report": None,
        "filename": filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        f"[Upload] run_id={run_id} | "
        f"{cleaning_report.dataset_shape_before} → {df.shape} | "
        f"{len(cleaning_report.cleaning_actions_applied)} actions | "
        f"leakage={cleaning_report.leakage_suspects} | "
        f"file={filename}"
    )

    has_leakage = len(cleaning_report.leakage_suspects) > 0
    has_warnings = len(cleaning_report.warnings) > 0
    upload_status = "success_with_warnings" if (has_warnings or has_leakage) else "success"

    try:
        null_counts = {k: int(v) for k, v in df.isnull().sum().items()}
    except Exception:
        null_counts = {}

    try:
        summary_dict = summary.model_dump()
    except Exception:
        summary_dict = None

    return JSONResponse(
        status_code=200,
        content={
            "status": upload_status,
            "run_id": run_id,
            "filename": filename,
            "cleaning_report": _cleaning_report_to_dict(cleaning_report),
            "dataset_info": {
                "shape_original": list(cleaning_report.dataset_shape_before),
                "shape_after_cleaning": list(df.shape),
                "columns": list(df.columns),
                "dtypes": {col: str(df[col].dtype) for col in df.columns},
                "null_counts": null_counts,
            },
            "summary": summary_dict,
        }
    )


# ─────────────────────────────────────────────
# ENDPOINT 2 — Dataset Summary
# ─────────────────────────────────────────────

@router.get("/summary/{run_id}", summary="Résumé du dataset + rapport de nettoyage")
async def get_summary(run_id: str):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="summary", error=str(e.detail), http_code=e.status_code)

    cleaning_report = run.get("cleaning_report")
    summary = run.get("summary")

    return {
        "run_id": run_id,
        "summary": summary.model_dump() if summary else None,
        "cleaning_report": _cleaning_report_to_dict(cleaning_report) if cleaning_report else None,
        "current_shape": list(run["df_current"].shape),
        "status": {
            "has_plan": run["plan"] is not None,
            "has_execution_report": run["execution_report"] is not None,
            "has_training_result": run["training_result"] is not None,
        }
    }


# ─────────────────────────────────────────────
# ENDPOINT 2b — EDA
# GET /api/automl/eda/{run_id}
# ─────────────────────────────────────────────

@router.get("/eda/{run_id}", summary="Exploratory Data Analysis du dataset")
async def get_eda(run_id: str):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="eda", error=str(e.detail), http_code=e.status_code)

    df: pd.DataFrame = run["df_current"]

    shape = {"rows": int(df.shape[0]), "columns": int(df.shape[1])}
    missing_by_column = {c: int(v) for c, v in df.isnull().sum().items() if v > 0}
    missing_total = int(df.isnull().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_columns = df.select_dtypes(exclude=[np.number]).columns.tolist()
    constant_columns = [c for c in df.columns if df[c].nunique() <= 1]
    high_cardinality_columns = [c for c in categorical_columns if df[c].nunique() > 50]

    outliers = []
    for col in numeric_columns:
        try:
            s = df[col].dropna()
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            iqr_out = int(((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum())
            std = s.std()
            z_out = int(((s - s.mean()).abs() / std > 3).sum()) if std > 0 else 0
            pct = round(iqr_out / len(s) * 100, 1) if len(s) > 0 else 0.0
            if iqr_out > 0 or z_out > 0:
                outliers.append({"column": col, "iqr_outliers": iqr_out,
                                 "zscore_outliers": z_out, "pct": f"{pct}%"})
        except Exception:
            pass

    sample_rows: List[Dict] = []
    try:
        for _, row in df.head(5).iterrows():
            row_dict: Dict[str, Any] = {}
            for col, val in row.items():
                if pd.isna(val):
                    row_dict[col] = None
                elif hasattr(val, "item"):
                    row_dict[col] = val.item()
                else:
                    row_dict[col] = val
            sample_rows.append(row_dict)
    except Exception:
        pass

    return {
        "run_id": run_id,
        "shape": shape,
        "missing_total": missing_total,
        "duplicate_rows": duplicate_rows,
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "outliers": outliers,
        "missing_by_column": missing_by_column,
        "constant_columns": constant_columns,
        "high_cardinality_columns": high_cardinality_columns,
        "sample_rows": sample_rows,
    }


# ─────────────────────────────────────────────
# ENDPOINT 2c — Analyze Features
# POST /api/automl/analyze-features
# ─────────────────────────────────────────────

@router.post("/analyze-features", summary="Analyse des features par rapport à la target")
async def analyze_features_endpoint(payload: Dict[str, Any]):
    run_id   = payload.get("run_id", "")
    target   = payload.get("target", "")
    features = payload.get("features", [])

    if not run_id or not target or not features:
        raise HTTPException(status_code=400, detail="run_id, target et features sont requis.")

    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="analyze_features", error=str(e.detail), http_code=e.status_code)

    df: pd.DataFrame = run["df_current"]

    if target not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target '{target}' introuvable dans le dataset.")

    from app.automl.service.simple_training_service import analyze_features
    return analyze_features(df, target, features)


# ─────────────────────────────────────────────
# ENDPOINT 2d — Simple Train
# POST /api/automl/train
# ─────────────────────────────────────────────

@router.post("/train", summary="Entraînement direct sans plan LLM (multi-modèles + Optuna)")
async def train_simple_endpoint(payload: Dict[str, Any]):
    run_id        = payload.get("run_id", "")
    target        = payload.get("target", "")
    features      = payload.get("features", [])
    task          = payload.get("task", "auto")
    test_size     = float(payload.get("test_size", 0.2))
    cv_folds      = int(payload.get("cv_folds", 5))
    use_optuna    = bool(payload.get("use_optuna", True))
    optuna_trials = int(payload.get("optuna_trials", 40))

    if not run_id or not target or not features:
        raise HTTPException(status_code=400, detail="run_id, target et features sont requis.")

    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="train", error=str(e.detail), http_code=e.status_code)

    df: pd.DataFrame = run["df_current"]

    if target not in df.columns:
        raise HTTPException(status_code=400, detail=f"Target '{target}' introuvable.")

    try:
        from app.automl.service.simple_training_service import train_simple
        result = train_simple(
            df=df, target=target, features=features, task=task,
            test_size=test_size, cv_folds=cv_folds,
            use_optuna=use_optuna, optuna_trials=optuna_trials,
            run_id=run_id, data_dir=DATA_DIR,
        )
        return result
    except Exception as e:
        logger.exception(f"[Train] Erreur : {e}")
        return _error_response(step="train", run_id=run_id, error=str(e), http_code=500)


# ─────────────────────────────────────────────
# ENDPOINT 2e — Simple Predict (JSON)
# POST /api/automl/predict
# ─────────────────────────────────────────────

@router.post("/predict", summary="Prédiction JSON — supporte modèle simple ET modèle agent")
async def predict_simple_endpoint(payload: Dict[str, Any]):
    run_id = payload.get("run_id", "")
    data   = payload.get("data", {})

    if not run_id:
        raise HTTPException(status_code=400, detail="run_id est requis.")

    # ── 1. Essai modèle manuel (simple_training_service) ──────────────────────
    try:
        from app.automl.service.simple_training_service import predict_simple
        return predict_simple(run_id=run_id, data=data, data_dir=DATA_DIR)
    except FileNotFoundError:
        pass   # pas de modèle manuel → on essaie le modèle agent
    except Exception as e:
        logger.exception(f"[Predict/simple] Erreur : {e}")
        return _error_response(step="predict", run_id=run_id, error=str(e), http_code=500)

    # ── 2. Fallback modèle agent (training_service LLM) ───────────────────────
    try:
        from app.automl.service.training_service import predict_with_saved_model, load_train_meta

        meta     = load_train_meta(run_id, DATA_DIR)
        df_input = pd.DataFrame([data])
        result   = predict_with_saved_model(df_input, run_id=run_id, data_dir=DATA_DIR)

        prediction = result["predictions"][0] if result["predictions"] else None
        confidence = result["confidence_scores"][0] if result["confidence_scores"] else None

        # Déduire task depuis le type de problème sauvegardé
        problem_type_str = meta.get("problem_type", "")
        task = "regression" if "regression" in str(problem_type_str) else "classification"

        return {
            "task":       task,
            "prediction": prediction,
            "confidence": confidence,
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Modèle introuvable pour run_id={run_id}. Lancez d'abord l'agent ou l'entraînement manuel."
        )
    except Exception as e:
        logger.exception(f"[Predict/agent] Erreur : {e}")
        return _error_response(step="predict", run_id=run_id, error=str(e), http_code=500)


# ─────────────────────────────────────────────
# ENDPOINT 3 — Suggest Target
# ─────────────────────────────────────────────

@router.get("/llm/suggest-target/{run_id}", summary="LLM suggère la colonne target")
async def suggest_target(run_id: str):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="suggest_target", error=str(e.detail), http_code=e.status_code)

    # ✅ Utilise _get_or_rebuild_summary — jamais None
    summary = _get_or_rebuild_summary(run, run_id)

    if summary is None:
        df = run["df_current"]
        cols = list(df.columns)
        return {
            "run_id": run_id,
            "status": "success_fallback",
            "suggestion": {
                "target": cols[-1] if cols else "",
                "problem_type": "binary_classification",
                "reason": "Impossible de construire le summary. Choisissez manuellement.",
                "available_columns": cols,
            }
        }

    # Si colonnes toujours vides → fallback direct sans appeler le LLM
    if not summary.columns:
        df = run["df_current"]
        cols = list(df.columns)
        return {
            "run_id": run_id,
            "status": "success_fallback",
            "suggestion": {
                "target": cols[-1] if cols else "",
                "problem_type": "binary_classification",
                "reason": "Summary sans colonnes. Choisissez manuellement.",
                "available_columns": cols,
            }
        }

    try:
        suggestion = suggest_target_and_type(summary)
        return {"run_id": run_id, "status": "success", "suggestion": suggestion}
    except Exception as e:
        df = run["df_current"]
        cols = list(df.columns)
        logger.warning(f"[suggest_target] LLM échoué : {e}")
        return {
            "run_id": run_id,
            "status": "success_fallback",
            "suggestion": {
                "target": cols[-1] if cols else "",
                "problem_type": "binary_classification",
                "reason": f"LLM indisponible ({str(e)[:100]}). Colonnes disponibles : {cols}",
                "available_columns": cols,
            }
        }


# ─────────────────────────────────────────────
# ENDPOINT 4 — Generate Decision Plan
# ─────────────────────────────────────────────

@router.post("/llm/decision-plan/{run_id}", summary="LLM génère le plan de décision")
async def generate_plan(
    run_id: str,
    request: Optional[DecisionPlanRequest] = None,
):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="plan", error=str(e.detail), http_code=e.status_code)

    # ✅ Reconstruction automatique si summary absent
    summary = _get_or_rebuild_summary(run, run_id)
    if summary is None:
        return _error_response(
            step="plan",
            run_id=run_id,
            error="Résumé du dataset non disponible.",
            suggestion="Re-uploadez le dataset.",
            http_code=400,
        )

    user_hints = None
    if request and request.user_hints:
        user_hints = request.user_hints
        hints = request.user_hints
        if "target_column" in hints:
            summary.target_column = hints["target_column"]
        if "problem_type" in hints:
            try:
                summary.problem_type = ProblemType(hints["problem_type"])
            except ValueError:
                pass

    if not summary.target_column:
        return _error_response(
            step="plan",
            run_id=run_id,
            error="target_column non définie.",
            suggestion=(
                "Utilisez GET /api/automl/llm/suggest-target/{run_id} "
                "ou passez target_column dans user_hints."
            ),
            http_code=400,
        )

    cleaning_report = run.get("cleaning_report")
    if cleaning_report and cleaning_report.leakage_suspects:
        if user_hints is None:
            user_hints = {}
        user_hints["leakage_warning"] = cleaning_report.leakage_suspects

    try:
        plan = generate_decision_plan(summary=summary, user_hints=user_hints)
        plan_source = "llm"
    except Exception as e:
        logger.warning(f"[Plan] LLM indisponible ({e}) — fallback heuristique")
        try:
            plan = generate_fallback_plan(summary)
            plan_source = "fallback"
        except Exception as e2:
            return _error_response(
                step="plan",
                run_id=run_id,
                error=f"Impossible de générer un plan : {e2}",
                http_code=500,
            )

    df = run["df_current"]
    plan_warnings = validate_plan_against_df(df, plan)
    if plan_warnings:
        plan.data_warnings.extend(plan_warnings)

    _RUN_STORE[run_id]["plan"] = plan
    _RUN_STORE[run_id]["summary"] = summary

    return {
        "run_id": run_id,
        "status": "success",
        "plan_source": plan_source,
        "plan": plan.model_dump(),
    }


# ─────────────────────────────────────────────
# ENDPOINT 5 — Apply Plan
# ─────────────────────────────────────────────

@router.post("/llm/apply-plan/{run_id}", summary="Exécute le plan LLM sur le dataset")
async def apply_plan(run_id: str):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="apply_plan", error=str(e.detail), http_code=e.status_code)

    if run["plan"] is None:
        return _error_response(
            step="apply_plan",
            run_id=run_id,
            error="Aucun plan disponible.",
            suggestion="Appelez d'abord POST /api/automl/llm/decision-plan/{run_id}",
            http_code=400,
        )

    plan: LLMDecisionPlan = run["plan"]
    df = run["df_current"].copy()

    try:
        df_cleaned, execution_report = execute_plan(df=df, plan=plan)
    except Exception as e:
        logger.exception(f"[Apply] Erreur : {e}")
        return _error_response(
            step="apply_plan",
            run_id=run_id,
            error=f"Erreur lors de l'exécution du plan : {str(e)}",
            http_code=500,
        )

    _RUN_STORE[run_id]["df_current"] = df_cleaned
    _RUN_STORE[run_id]["execution_report"] = execution_report

    overall_status = "success"
    if execution_report.errors > 0 and execution_report.successful == 0:
        overall_status = "error"
    elif execution_report.errors > 0 or execution_report.skipped > 0:
        overall_status = "partial"

    return {
        "run_id": run_id,
        "status": overall_status,
        "execution_report": execution_report.model_dump(),
    }


# ─────────────────────────────────────────────
# ENDPOINT 6 — Train With Plan
# ─────────────────────────────────────────────

@router.post("/llm/train-with-plan/{run_id}", summary="Entraîne les modèles selon le plan LLM")
async def train_with_plan_endpoint(
    run_id: str,
    test_size: float = Query(default=0.2, ge=0.1, le=0.4),
    save_model: bool = Query(default=True),
):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="training", error=str(e.detail), http_code=e.status_code)

    if run["plan"] is None:
        return _error_response(
            step="training",
            run_id=run_id,
            error="Plan manquant.",
            suggestion="Appelez d'abord POST /api/automl/llm/decision-plan/{run_id}",
            http_code=400,
        )

    plan: LLMDecisionPlan = run["plan"]
    df = run["df_current"]

    validation_errors = validate_for_training(df, plan.target_column)
    if validation_errors:
        return _error_response(
            step="training",
            run_id=run_id,
            error="Dataset non entraînable après nettoyage.",
            errors_detected=validation_errors,
            suggestion="Vérifiez que le dataset contient des colonnes numériques et une target valide.",
            http_code=422,
        )

    try:
        training_result = train_with_plan(
            df=df,
            plan=plan,
            data_dir=DATA_DIR,
            test_size=test_size,
            save_model=save_model,
        )
    except Exception as e:
        logger.exception(f"[Train] Erreur : {e}")
        return _error_response(
            step="training",
            run_id=run_id,
            error=f"Erreur d'entraînement : {str(e)}",
            suggestion="Vérifiez que le dataset est correctement nettoyé et que la target est valide.",
            http_code=500,
        )

    _RUN_STORE[run_id]["training_result"] = training_result

    return {
        "run_id": run_id,
        "status": "success",
        "training_result": training_result.model_dump(),
        "error": None,
    }


# ─────────────────────────────────────────────
# ENDPOINT 7 — Final Report
# ─────────────────────────────────────────────

@router.get("/report/{run_id}", summary="Rapport final complet — 3 niveaux de lecture")
async def get_report(run_id: str, use_llm: bool = Query(default=True)):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="report", error=str(e.detail), http_code=e.status_code)

    if run["training_result"] is None:
        return _error_response(
            step="report",
            run_id=run_id,
            error="Entraînement non effectué.",
            suggestion="Appelez d'abord POST /api/automl/llm/train-with-plan/{run_id}",
            http_code=400,
        )

    if run.get("report") is not None:
        return {"run_id": run_id, "status": "success", "report": run["report"].model_dump()}

    plan = run["plan"]
    execution_report = run["execution_report"]
    training_result = run["training_result"]
    summary = run.get("summary")
    cleaning_report = run.get("cleaning_report")
    df_original = run["df_original"]
    df_current = run["df_current"]

    columns_dropped = []
    columns_created = []
    if plan:
        columns_dropped = [
            a.model_dump().get("column", "")
            for a in plan.feature_actions
            if a.model_dump().get("action") == "drop_column"
        ]
        columns_created = [
            a.model_dump().get("new_feature", "")
            for a in plan.feature_actions
            if a.model_dump().get("new_feature")
        ]

    if cleaning_report:
        columns_dropped.extend(cleaning_report.columns_dropped)
        columns_dropped = list(set(columns_dropped))

    technical = TechnicalInsights(
        dataset_shape_original=(len(df_original), len(df_original.columns)),
        dataset_shape_after_cleaning=(len(df_current), len(df_current.columns)),
        columns_dropped=[c for c in columns_dropped if c],
        columns_created=[c for c in columns_created if c],
        null_rows_handled=sum(cleaning_report.nulls_filled.values()) if cleaning_report else 0,
        outliers_removed=len(cleaning_report.outliers_clipped) if cleaning_report else 0,
        models_tested=[m.model_name for m in training_result.models_evaluated],
        best_model=training_result.best_model,
        metrics=training_result.best_metrics,
        cv_mean=next(
            (m.cv_mean for m in training_result.models_evaluated
             if m.model_name == training_result.best_model and m.cv_mean is not None),
            None,
        ),
        cv_std=next(
            (m.cv_std for m in training_result.models_evaluated
             if m.model_name == training_result.best_model and m.cv_std is not None),
            None,
        ),
        data_warnings=(
            (plan.data_warnings if plan else []) +
            (cleaning_report.warnings if cleaning_report else [])
        ),
    )

    executive_summary = None
    recommendations = []
    llm_explanation = None

    if use_llm and plan and execution_report and summary and summary.n_rows > 0:
        try:
            llm_data = generate_report_explanation(
                summary=summary,
                plan=plan,
                execution_report=execution_report,
                training_result=training_result,
            )
            exec_data = llm_data.get("executive_summary", {})
            executive_summary = ExecutiveSummary(
                one_liner=exec_data.get("one_liner", "Modèle entraîné avec succès."),
                model_performance=exec_data.get("model_performance", str(training_result.best_metrics)),
                top_factors=exec_data.get(
                    "top_factors",
                    list((training_result.feature_importance or {}).keys())[:5]
                ),
                recommendation=exec_data.get("recommendation", "Évaluer sur de nouvelles données."),
            )
            for rec in llm_data.get("recommendations", []):
                try:
                    recommendations.append(ActionableRecommendation(**rec))
                except Exception:
                    pass
            llm_explanation = llm_data.get("llm_explanation")
        except Exception as e:
            logger.warning(f"[Report] LLM explanation échouée : {e}")

    # Fallback executive summary
    if executive_summary is None:
        best_k = list(training_result.best_metrics.keys())[0] if training_result.best_metrics else "score"
        best_v = list(training_result.best_metrics.values())[0] if training_result.best_metrics else 0.0
        executive_summary = ExecutiveSummary(
            one_liner=f"Modèle {training_result.best_model} entraîné — {best_k}={best_v:.4f}",
            model_performance=str(training_result.best_metrics),
            top_factors=list((training_result.feature_importance or {}).keys())[:5],
            recommendation="Testez sur de nouvelles données avant déploiement.",
        )

    if not recommendations:
        if cleaning_report and cleaning_report.leakage_suspects:
            recommendations.append(ActionableRecommendation(
                priority="high",
                category="data",
                message=f"Data leakage détecté et corrigé : {cleaning_report.leakage_suspects}",
                effort="low",
            ))
        recommendations.append(ActionableRecommendation(
            priority="medium",
            category="model",
            message=f"Le modèle '{training_result.best_model}' est sélectionné. Validez sur des données externes.",
            effort="low",
        ))

    report = FinalUserReport(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        executive_summary=executive_summary,
        technical_insights=technical,
        recommendations=recommendations,
        decision_plan=plan,
        execution_report=execution_report,
        training_result=training_result,
        llm_explanation=llm_explanation,
    )

    _RUN_STORE[run_id]["report"] = report
    return {"run_id": run_id, "status": "success", "report": report.model_dump()}


# ─────────────────────────────────────────────
# ENDPOINT 8 — Predict
# ─────────────────────────────────────────────

@router.post("/predict/{run_id}", summary="Prédiction avec le meilleur modèle")
async def predict(run_id: str, file: UploadFile = File(...)):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="predict", error=str(e.detail), http_code=e.status_code)

    if run["training_result"] is None:
        return _error_response(
            step="predict", run_id=run_id, error="Aucun modèle entraîné.", http_code=400
        )

    try:
        content = await file.read()
        df_pred = pd.read_csv(pd.io.common.BytesIO(content))
    except Exception as e:
        return _error_response(
            step="predict", run_id=run_id,
            error=f"Impossible de lire le fichier : {e}", http_code=400
        )

    try:
        result = predict_with_saved_model(df_pred, run_id=run_id, data_dir=DATA_DIR)
        return {"run_id": run_id, "status": "success", **result}
    except FileNotFoundError:
        return _error_response(
            step="predict", run_id=run_id,
            error="Modèle sauvegardé introuvable.",
            suggestion="Re-entraînez avec save_model=true",
            http_code=404,
        )
    except Exception as e:
        return _error_response(step="predict", run_id=run_id, error=str(e), http_code=500)


# ─────────────────────────────────────────────
# ENDPOINT 9 — Full Pipeline
# ─────────────────────────────────────────────

@router.post("/run-full-pipeline/{run_id}", summary="Pipeline complet en une requête")
async def run_full_pipeline(
    run_id: str,
    target_column: Optional[str] = Query(default=None),
    problem_type: Optional[str] = Query(default=None),
    test_size: float = Query(default=0.2),
):
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="pipeline", error=str(e.detail), http_code=e.status_code)

    summary = _get_or_rebuild_summary(run, run_id)
    if summary is None:
        return _error_response(
            step="pipeline", run_id=run_id,
            error="Résumé non disponible. Re-uploadez le dataset.", http_code=400,
        )

    if target_column:
        summary.target_column = target_column
    if problem_type:
        try:
            summary.problem_type = ProblemType(problem_type)
        except ValueError:
            pass
    _RUN_STORE[run_id]["summary"] = summary

    if not summary.target_column:
        return _error_response(
            step="pipeline", run_id=run_id, error="target_column requis.", http_code=400
        )

    results: Dict[str, Any] = {}

    # Step 1 — Plan
    try:
        await generate_plan(run_id=run_id)
        results["plan"] = {"status": "success"}
    except Exception as e:
        results["plan"] = {"status": "error", "error": str(e)}

    # Step 2 — Apply
    try:
        await apply_plan(run_id=run_id)
        results["apply"] = {"status": "success"}
    except Exception as e:
        results["apply"] = {"status": "error", "error": str(e)}

    # Step 3 — Train
    try:
        await train_with_plan_endpoint(run_id=run_id, test_size=test_size)
        # ✅ Lire depuis _RUN_STORE (pas run local qui est stale)
        tr = _RUN_STORE[run_id].get("training_result")
        results["train"] = {
            "status": "success",
            "best_model": tr.best_model if tr else None,
            "best_metrics": tr.best_metrics if tr else None,
        }
    except Exception as e:
        results["train"] = {"status": "error", "error": str(e)}
        return JSONResponse(
            status_code=500,
            content={"run_id": run_id, "status": "error", "steps": results}
        )

    return {
        "run_id": run_id,
        "status": "success",
        "steps": results,
        "report_url": f"/api/automl/report/{run_id}",
    }


# ─────────────────────────────────────────────
# ENDPOINT 10 — Agent ReAct Run
# POST /api/automl/agent-run/{run_id}
# ─────────────────────────────────────────────

@router.post("/agent-run/{run_id}", summary="Pipeline AutoML piloté par un agent ReAct (Function Calling)")
async def agent_run(
    run_id: str,
    target_column: Optional[str] = Query(default=None),
    problem_type: Optional[str] = Query(default=None),
    max_steps: int = Query(default=10, ge=3, le=20),
):
    """
    Agent ReAct qui pilote autonomement tout le pipeline AutoML :
    - Analyse du dataset
    - Génération du plan
    - Nettoyage + feature engineering
    - Entraînement des modèles
    - Évaluation et sélection du meilleur modèle
    - Rapport final avec raisonnement visible

    L'agent utilise OpenAI Function Calling pour décider quand appeler chaque outil.
    La trace de raisonnement (Thought → Action → Observation) est retournée dans agent_trace.
    """
    try:
        run = _get_run(run_id)
    except HTTPException as e:
        return _error_response(step="agent_run", error=str(e.detail), http_code=e.status_code)

    try:
        from app.automl.service.agent_service import run_automl_agent

        result = await run_automl_agent(
            run_id         = run_id,
            run_store      = _RUN_STORE,
            data_dir       = DATA_DIR,
            target_column  = target_column,
            problem_type   = problem_type,
            max_steps      = max_steps,
        )

        return JSONResponse(status_code=200, content=result)

    except HTTPException as e:
        return _error_response(step="agent_run", error=str(e.detail), http_code=e.status_code)
    except Exception as e:
        logger.exception(f"[Agent] Erreur inattendue : {e}")
        return _error_response(
            step="agent_run",
            run_id=run_id,
            error=f"Erreur agent : {str(e)}",
            suggestion="Vérifiez OPENAI_API_KEY et que le dataset a été uploadé.",
            http_code=500,
        )


# ─────────────────────────────────────────────
# ENDPOINT 11 — Health
# ─────────────────────────────────────────────

@router.get("/health", summary="Health check")
async def health():
    return {
        "status": "ok",
        "active_runs": len(_RUN_STORE),
        "data_dir": DATA_DIR,
        "data_dir_exists": os.path.exists(DATA_DIR),
        "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }