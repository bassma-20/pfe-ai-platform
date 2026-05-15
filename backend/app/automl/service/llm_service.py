"""
backend/app/automl/service/llm_service.py

Service LLM-Driven AutoML.
Le LLM DÉCIDE uniquement via JSON structuré — il ne code jamais.
Le backend EXÉCUTE les décisions après validation Pydantic stricte.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.automl.models.schemas import (
    DatasetSummary,
    LLMDecisionPlan,
    ExecutiveSummary,
    ActionableRecommendation,
    FinalUserReport,
    TrainingResult,
    ExecutionReport,
    TechnicalInsights,
    ProblemType,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# PROMPT TEMPLATES
# ─────────────────────────────────────────────

DECISION_PLAN_SYSTEM_PROMPT = """
You are an expert AutoML decision engine. Your ONLY job is to analyze a dataset summary
and return a structured JSON decision plan.

CRITICAL RULES:
1. Return ONLY valid JSON — no markdown, no code blocks, no explanation outside JSON.
2. Use ONLY the allowed action types listed below.
3. Every decision must have a "reason" field explaining WHY.
4. Never invent column names — only use columns from the dataset summary.
5. Be conservative: prefer simple, safe transformations.

ALLOWED CLEANING ACTIONS:
- impute_mean, impute_median, impute_mode, impute_knn
- drop_column, drop_rows_nulls
- remove_outliers_iqr, remove_outliers_zscore, clip_outliers
- fill_constant

ALLOWED FEATURE ACTIONS:
- drop_column
- create_ratio, create_sum, create_difference, create_product
- log_transform, sqrt_transform
- standardize_numeric
- encode_onehot, encode_ordinal, encode_target
- extract_datetime
- binarize

ALLOWED MODELS:
- RandomForest, GradientBoosting, XGBoost, LightGBM, ExtraTrees
- LogisticRegression, LinearRegression, Ridge, Lasso, SVM, KNN, DecisionTree

OUTPUT FORMAT (strict):
{
  "run_id": "<run_id>",
  "problem_type": "binary_classification|multiclass_classification|regression",
  "target_column": "<col>",
  "confidence": 0.85,
  "cleaning_actions": [...],
  "feature_actions": [...],
  "model_plan": {
    "models_to_try": [...],
    "use_optuna": true,
    "trials": 30,
    "cv_folds": 5,
    "primary_metric": "f1|accuracy|roc_auc|r2|rmse",
    "reason": "..."
  },
  "data_warnings": [...],
  "reasoning_summary": "..."
}
"""

DECISION_PLAN_USER_TEMPLATE = """
Analyze this dataset and return the JSON decision plan.

DATASET SUMMARY:
- run_id: {run_id}
- Shape: {n_rows} rows × {n_cols} columns
- Target column: {target_column}
- Problem type: {problem_type}
- Total null %: {total_null_pct:.1f}%
- Duplicate rows: {duplicate_rows}
- Class balance: {class_balance}

COLUMNS DETAIL:
{columns_detail}

USER HINTS:
{user_hints}

Return ONLY the JSON decision plan. No markdown, no explanation.
"""

EXPLANATION_SYSTEM_PROMPT = """
You are an AI assistant explaining AutoML results to a non-technical user.
Be clear, concise, and avoid jargon. Speak in the user's language (detect from context).
Focus on business value, not technical details.
"""

REPORT_SYSTEM_PROMPT = """
You are an AutoML report generator. Generate a clear, professional explanation
of the AutoML pipeline results. Structure your response as JSON with these fields:
{
  "executive_summary": {
    "one_liner": "...",
    "model_performance": "...",
    "top_factors": ["...", "...", "..."],
    "recommendation": "..."
  },
  "recommendations": [
    {
      "priority": "high|medium|low",
      "category": "data|features|model|deployment",
      "message": "...",
      "estimated_impact": "...",
      "effort": "low|medium|high"
    }
  ],
  "llm_explanation": "..."
}
"""


# ─────────────────────────────────────────────
# LLM CLIENT FACTORY
# ─────────────────────────────────────────────

def _get_llm_client():
    import os
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "anthropic":
        try:
            import anthropic
            return "anthropic", anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        except ImportError:
            raise RuntimeError("pip install anthropic")

    elif provider == "openai":
        try:
            from openai import OpenAI  # ✅ Nouvelle syntaxe
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            return "openai", client
        except ImportError:
            raise RuntimeError("pip install openai")

    else:
        raise ValueError(f"LLM_PROVIDER non supporté: {provider}")


def _call_llm(system_prompt: str, user_message: str, max_tokens: int = 4000) -> str:
    import os
    provider, client = _get_llm_client()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if provider == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    elif provider == "openai":
        # ✅ Nouvelle syntaxe openai >= 1.0.0
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    raise ValueError(f"Provider inconnu: {provider}")


# ─────────────────────────────────────────────
# JSON EXTRACTION
# ─────────────────────────────────────────────

def _extract_json_from_response(text: str) -> Dict[str, Any]:
    """
    Extrait le JSON depuis la réponse LLM.
    Gère les cas où le LLM ajoute du markdown ou du texte autour.
    """
    # Tentative 1 : JSON pur
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Tentative 2 : extraire depuis ```json ... ```
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Tentative 3 : trouver le premier { ... } de niveau 0
    depth = 0
    start = None
    for i, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    break

    raise ValueError(f"Impossible d'extraire un JSON valide de la réponse LLM:\n{text[:500]}")


# ─────────────────────────────────────────────
# DATASET SUMMARY BUILDER
# ─────────────────────────────────────────────

def build_dataset_summary(
    df,  # pandas DataFrame
    run_id: str,
    target_column: Optional[str] = None,
    problem_type: Optional[str] = None,
) -> DatasetSummary:
    """
    Construit le DatasetSummary depuis un DataFrame pandas.
    Analyse les colonnes, détecte les types de missing, etc.
    """
    import numpy as np
    import pandas as pd
    from app.automl.models.schemas import ColumnInfo

    columns_info = []
    for col in df.columns:
        series = df[col]
        null_count = int(series.isnull().sum())
        null_pct = round(null_count / len(df) * 100, 2)
        is_numeric = pd.api.types.is_numeric_dtype(series)

        # Skewness pour colonnes numériques
        skewness = None
        if is_numeric and null_count < len(df):
            try:
                skewness = round(float(series.dropna().skew()), 3)
            except Exception:
                pass

        # Détection outliers IQR basique
        has_outliers_iqr = None
        if is_numeric and null_count < len(df):
            try:
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                n_out = int(((series < lower) | (series > upper)).sum())
                has_outliers_iqr = n_out > 0
            except Exception:
                pass

        # Détection type de missing (heuristique simple)
        missing_type = "none"
        if null_pct > 0:
            # Heuristique : si corrélation du masque de null avec d'autres colonnes
            if null_pct > 80:
                missing_type = "MNAR"
            elif null_pct > 5:
                missing_type = "MAR"
            else:
                missing_type = "MCAR"

        sample_vals = series.dropna().head(5).tolist()
        # Convertir numpy types en Python natifs
        sample_vals = [
            v.item() if hasattr(v, "item") else v
            for v in sample_vals
        ]

        columns_info.append(ColumnInfo(
            name=col,
            dtype=str(series.dtype),
            null_count=null_count,
            null_pct=null_pct,
            unique_count=int(series.nunique()),
            sample_values=sample_vals,
            is_numeric=is_numeric,
            skewness=skewness,
            has_outliers_iqr=has_outliers_iqr,
            missing_type=missing_type,
        ))

    # Class balance pour classification
    class_balance = None
    if target_column and target_column in df.columns:
        if problem_type in ("binary_classification", "multiclass_classification"):
            vc = df[target_column].value_counts(normalize=True)
            class_balance = {str(k): round(float(v), 3) for k, v in vc.items()}

    return DatasetSummary(
        run_id=run_id,
        n_rows=len(df),
        n_cols=len(df.columns),
        target_column=target_column,
        problem_type=ProblemType(problem_type) if problem_type else None,
        columns=columns_info,
        duplicate_rows=int(df.duplicated().sum()),
        total_null_pct=round(df.isnull().mean().mean() * 100, 2),
        class_balance=class_balance,
    )


# ─────────────────────────────────────────────
# COLONNES DETAIL STRING (pour le prompt)
# ─────────────────────────────────────────────

def _format_columns_detail(summary: DatasetSummary) -> str:
    lines = []
    for col in summary.columns:
        line = (
            f"  - {col.name} | dtype={col.dtype} | "
            f"null={col.null_pct:.1f}% ({col.missing_type}) | "
            f"unique={col.unique_count}"
        )
        if col.skewness is not None:
            line += f" | skew={col.skewness:.2f}"
        if col.has_outliers_iqr:
            line += " | HAS_OUTLIERS"
        line += f" | samples={col.sample_values[:3]}"
        lines.append(line)
    return "\n".join(lines)


# ─────────────────────────────────────────────
# CORE: GENERATE DECISION PLAN
# ─────────────────────────────────────────────

def generate_decision_plan(
    summary: DatasetSummary,
    user_hints: Optional[Dict[str, Any]] = None,
) -> LLMDecisionPlan:
    """
    Demande au LLM de générer un plan de décision structuré.
    Valide le JSON retourné avec Pydantic avant de le retourner.

    Raises:
        ValidationError: si le LLM retourne un JSON invalide
        ValueError: si l'extraction JSON échoue
        RuntimeError: si l'appel LLM échoue
    """
    logger.info(f"[LLM] Génération du plan de décision pour run_id={summary.run_id}")

    user_message = DECISION_PLAN_USER_TEMPLATE.format(
        run_id=summary.run_id,
        n_rows=summary.n_rows,
        n_cols=summary.n_cols,
        target_column=summary.target_column or "NOT_SPECIFIED",
        problem_type=summary.problem_type.value if summary.problem_type else "NOT_SPECIFIED",
        total_null_pct=summary.total_null_pct,
        duplicate_rows=summary.duplicate_rows,
        class_balance=json.dumps(summary.class_balance) if summary.class_balance else "N/A",
        columns_detail=_format_columns_detail(summary),
        user_hints=json.dumps(user_hints or {}, indent=2),
    )

    raw_response = _call_llm(
        system_prompt=DECISION_PLAN_SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=4000,
    )

    logger.debug(f"[LLM] Réponse brute (500 chars): {raw_response[:500]}")

    raw_json = _extract_json_from_response(raw_response)

    # Injection du run_id si absent
    raw_json.setdefault("run_id", summary.run_id)

    # Ajout metadata
    import os
    raw_json["llm_model_used"] = os.getenv("LLM_MODEL", "unknown")
    raw_json["generated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        plan = LLMDecisionPlan.model_validate(raw_json)
    except ValidationError as e:
        logger.error(f"[LLM] Plan JSON invalide: {e}")
        logger.error(f"[LLM] JSON reçu: {json.dumps(raw_json, indent=2)[:1000]}")
        raise

    logger.info(
        f"[LLM] Plan généré: "
        f"{len(plan.cleaning_actions)} cleaning, "
        f"{len(plan.feature_actions)} feature, "
        f"{len(plan.model_plan.models_to_try)} modèles, "
        f"confiance={plan.confidence:.0%}"
    )
    return plan


# ─────────────────────────────────────────────
# SUGGEST TARGET COLUMN (usage simple)
# ─────────────────────────────────────────────

def suggest_target_and_type(summary: DatasetSummary) -> Dict[str, str]:
    """
    Demande au LLM de suggérer la colonne target et le type de problème.
    Retourne {"target": "...", "problem_type": "..."}.
    """
    system = (
        "You are an ML expert. Given a dataset summary, suggest the target column "
        "and problem type. Return ONLY JSON: "
        '{"target": "col_name", "problem_type": "binary_classification|multiclass_classification|regression", '
        '"reason": "..."}'
    )
    user = (
        f"Dataset: {summary.n_rows} rows, columns: "
        f"{[c.name for c in summary.columns]}\n"
        f"Dtypes: {[f'{c.name}:{c.dtype}' for c in summary.columns]}\n"
        f"Unique counts: {[f'{c.name}:{c.unique_count}' for c in summary.columns]}\n"
        "Suggest target and problem type. Return ONLY JSON."
    )

    raw = _call_llm(system, user, max_tokens=300)
    return _extract_json_from_response(raw)


# ─────────────────────────────────────────────
# GENERATE FINAL REPORT (LLM explanation)
# ─────────────────────────────────────────────

def generate_report_explanation(
    summary: DatasetSummary,
    plan: LLMDecisionPlan,
    execution_report: ExecutionReport,
    training_result: TrainingResult,
) -> Dict[str, Any]:
    """
    Demande au LLM de générer l'explication narrative du rapport final.
    Retourne executive_summary + recommendations + llm_explanation.
    """
    logger.info(f"[LLM] Génération de l'explication du rapport pour run_id={summary.run_id}")

    context = f"""
PIPELINE RESULTS:
- Dataset: {summary.n_rows} rows, {summary.n_cols} columns
- Target: {plan.target_column} ({plan.problem_type.value})
- Cleaning: {execution_report.successful}/{execution_report.total_actions} actions réussies
- Best model: {training_result.best_model}
- Best metrics: {json.dumps(training_result.best_metrics, indent=2)}
- Feature importance (top 5): {
    json.dumps(dict(list(training_result.feature_importance.items())[:5]), indent=2)
    if training_result.feature_importance else "N/A"
}
- Data warnings: {plan.data_warnings}
- Cleaning actions applied: {[a.model_dump() for a in plan.cleaning_actions[:5]]}
- Columns dropped: {[a.column for a in plan.feature_actions if a.action == "drop_column"]}

Generate the report JSON with: executive_summary, recommendations, llm_explanation.
Make it clear, professional, and understandable for a non-technical user.
Detect the language from context and respond in the same language.
"""

    raw = _call_llm(REPORT_SYSTEM_PROMPT, context, max_tokens=2000)
    return _extract_json_from_response(raw)


# ─────────────────────────────────────────────
# EXPLAIN RESULTS (endpoint séparé)
# ─────────────────────────────────────────────

def explain_results(
    training_result: TrainingResult,
    plan: LLMDecisionPlan,
    language: str = "fr",
) -> str:
    """
    Explication simple des résultats en langage naturel.
    """
    system = (
        f"You are an ML expert explaining results to a business user in {language}. "
        "Be concise, clear, and focus on actionable insights."
    )
    user = f"""
Model: {training_result.best_model}
Metrics: {json.dumps(training_result.best_metrics)}
Problem: {training_result.problem_type.value}
Target: {training_result.target_column}
Feature importance: {json.dumps(dict(list((training_result.feature_importance or {}).items())[:5]))}
Warnings: {plan.data_warnings}

Explain in 3-4 sentences what these results mean for the business.
"""
    return _call_llm(system, user, max_tokens=500)


# ─────────────────────────────────────────────
# FALLBACK PLAN (si LLM indisponible)
# ─────────────────────────────────────────────

def generate_fallback_plan(summary: DatasetSummary) -> LLMDecisionPlan:
    """
    Plan de décision par défaut si le LLM est indisponible.
    Logique heuristique simple mais robuste.
    """
    from app.automl.models.schemas import (
        CleaningActionType, ModelPlan, ImputeAction,
        RemoveOutliersAction, ModelName,
    )

    cleaning_actions = []
    feature_actions = []

    for col in summary.columns:
        if col.null_pct > 0 and col.name != summary.target_column:
            if col.is_numeric:
                action = "impute_median" if (col.skewness and abs(col.skewness) > 1) else "impute_mean"
                cleaning_actions.append({
                    "action": action,
                    "column": col.name,
                    "reason": f"null_pct={col.null_pct:.1f}%"
                })
            else:
                cleaning_actions.append({
                    "action": "impute_mode",
                    "column": col.name,
                    "reason": f"categorical, null_pct={col.null_pct:.1f}%"
                })

        # Outliers sur colonnes numériques avec skew élevé
        if col.is_numeric and col.has_outliers_iqr and col.name != summary.target_column:
            cleaning_actions.append({
                "action": "clip_outliers",
                "column": col.name,
                "lower_quantile": 0.01,
                "upper_quantile": 0.99,
                "reason": "IQR outliers detected"
            })

    # Modèles par défaut selon le type de problème
    problem = summary.problem_type
    if problem == ProblemType.REGRESSION:
        models = [ModelName.RANDOM_FOREST, ModelName.GRADIENT_BOOSTING, ModelName.RIDGE]
        metric = "r2"
    else:
        models = [ModelName.RANDOM_FOREST, ModelName.GRADIENT_BOOSTING, ModelName.LOGISTIC_REGRESSION]
        metric = "f1"

    return LLMDecisionPlan(
        run_id=summary.run_id,
        problem_type=summary.problem_type or ProblemType.BINARY_CLASSIFICATION,
        target_column=summary.target_column or "",
        confidence=0.5,
        cleaning_actions=cleaning_actions,
        feature_actions=feature_actions,
        model_plan=ModelPlan(
            models_to_try=models,
            use_optuna=True,
            trials=20,
            cv_folds=5,
            primary_metric=metric,
            reason="Fallback plan — LLM unavailable",
        ),
        data_warnings=["LLM unavailable — using heuristic fallback plan"],
        reasoning_summary="Plan généré automatiquement par heuristiques (LLM indisponible)",
        llm_model_used="fallback_heuristic",
        generated_at=datetime.now(timezone.utc).isoformat(),
    )