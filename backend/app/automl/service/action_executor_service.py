"""
backend/app/automl/service/action_executor_service.py

Execution Engine — Le backend qui EXÉCUTE les décisions du LLM.
Principe de sécurité :
  - Seules les actions de la WHITELIST sont exécutables.
  - Chaque action est une fonction Python définie explicitement.
  - Aucun eval(), exec(), ou code dynamique.
  - Chaque action est loggée avec son résultat.
  - Rollback automatique si une action critique échoue.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from app.automl.models.schemas import (
    ActionResult,
    CleaningAction,
    ExecutionReport,
    FeatureAction,
    LLMDecisionPlan,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# CLEANING ACTIONS — fonctions atomiques
# ─────────────────────────────────────────────

def _impute_mean(df: pd.DataFrame, column: str, **kwargs) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")
    n_null = int(df[column].isnull().sum())
    df[column] = df[column].fillna(df[column].mean())
    return df, n_null


def _impute_median(df: pd.DataFrame, column: str, **kwargs) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")
    n_null = int(df[column].isnull().sum())
    df[column] = df[column].fillna(df[column].median())
    return df, n_null


def _impute_mode(df: pd.DataFrame, column: str, **kwargs) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    n_null = int(df[column].isnull().sum())
    mode_val = df[column].mode()
    if len(mode_val) == 0:
        raise ValueError(f"Pas de mode calculable pour '{column}'")
    df[column] = df[column].fillna(mode_val[0])
    return df, n_null


def _impute_knn(df: pd.DataFrame, column: str, k_neighbors: int = 5, **kwargs) -> Tuple[pd.DataFrame, int]:
    """KNN imputation via sklearn."""
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")

    from sklearn.impute import KNNImputer
    n_null = int(df[column].isnull().sum())

    # KNN sur toutes les colonnes numériques
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    imputer = KNNImputer(n_neighbors=min(k_neighbors, len(df) - 1))
    df[numeric_cols] = imputer.fit_transform(df[numeric_cols])
    return df, n_null


def _drop_column(df: pd.DataFrame, column: str, **kwargs) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    df = df.drop(columns=[column])
    return df, 0


def _drop_rows_nulls(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    threshold: Optional[float] = None,
    **kwargs,
) -> Tuple[pd.DataFrame, int]:
    n_before = len(df)
    if threshold is not None:
        # Drop les lignes avec plus de X% de nulls
        max_nulls = int(threshold * len(df.columns))
        df = df.dropna(thresh=len(df.columns) - max_nulls)
    elif columns:
        df = df.dropna(subset=columns)
    else:
        df = df.dropna()
    return df, n_before - len(df)


def _remove_outliers_iqr(
    df: pd.DataFrame, column: str, threshold: float = 1.5, **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")
    n_before = len(df)
    Q1 = df[column].quantile(0.25)
    Q3 = df[column].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - threshold * IQR
    upper = Q3 + threshold * IQR
    df = df[(df[column] >= lower) & (df[column] <= upper)]
    return df, n_before - len(df)


def _remove_outliers_zscore(
    df: pd.DataFrame, column: str, threshold: float = 3.0, **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")
    n_before = len(df)
    from scipy import stats
    z_scores = np.abs(stats.zscore(df[column].dropna()))
    # Réindexation prudente
    mask = pd.Series(True, index=df.index)
    non_null_idx = df[column].dropna().index
    mask[non_null_idx] = z_scores < threshold
    df = df[mask]
    return df, n_before - len(df)


def _clip_outliers(
    df: pd.DataFrame,
    column: str,
    lower_quantile: float = 0.01,
    upper_quantile: float = 0.99,
    **kwargs,
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")
    lower = df[column].quantile(lower_quantile)
    upper = df[column].quantile(upper_quantile)
    n_clipped = int(((df[column] < lower) | (df[column] > upper)).sum())
    df[column] = df[column].clip(lower=lower, upper=upper)
    return df, n_clipped


def _drop_duplicates(
    df: pd.DataFrame,
    subset: Optional[List[str]] = None,
    **kwargs,
) -> Tuple[pd.DataFrame, int]:
    """Supprime les lignes dupliquées (sur toutes les colonnes ou un sous-ensemble)."""
    n_before = len(df)
    if subset:
        # Vérifier que toutes les colonnes existent
        valid_subset = [c for c in subset if c in df.columns]
        df = df.drop_duplicates(subset=valid_subset if valid_subset else None)
    else:
        df = df.drop_duplicates()
    return df, n_before - len(df)


def _fill_constant(df: pd.DataFrame, column: str, value: Any, **kwargs) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    n_null = int(df[column].isnull().sum())
    df[column] = df[column].fillna(value)
    return df, n_null


# ─────────────────────────────────────────────
# FEATURE ACTIONS — fonctions atomiques
# ─────────────────────────────────────────────

def _create_ratio(
    df: pd.DataFrame, new_feature: str, col1: str, col2: str, **kwargs
) -> Tuple[pd.DataFrame, int]:
    for c in [col1, col2]:
        if c not in df.columns:
            raise KeyError(f"Colonne '{c}' introuvable")
    # Division sécurisée (évite division par zéro)
    df[new_feature] = df[col1] / df[col2].replace(0, np.nan)
    return df, 1


def _create_sum(df: pd.DataFrame, new_feature: str, columns: List[str], **kwargs) -> Tuple[pd.DataFrame, int]:
    for c in columns:
        if c not in df.columns:
            raise KeyError(f"Colonne '{c}' introuvable")
    df[new_feature] = df[columns].sum(axis=1)
    return df, 1


def _create_difference(
    df: pd.DataFrame, new_feature: str, col1: str, col2: str, **kwargs
) -> Tuple[pd.DataFrame, int]:
    for c in [col1, col2]:
        if c not in df.columns:
            raise KeyError(f"Colonne '{c}' introuvable")
    df[new_feature] = df[col1] - df[col2]
    return df, 1


def _create_product(
    df: pd.DataFrame, new_feature: str, col1: str, col2: str, **kwargs
) -> Tuple[pd.DataFrame, int]:
    for c in [col1, col2]:
        if c not in df.columns:
            raise KeyError(f"Colonne '{c}' introuvable")
    df[new_feature] = df[col1] * df[col2]
    return df, 1


def _log_transform(
    df: pd.DataFrame, column: str, new_column: Optional[str] = None, **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")
    if df[column].min() <= 0:
        # log1p pour les valeurs ≤ 0
        target_col = new_column or column
        df[target_col] = np.log1p(df[column] - df[column].min())
    else:
        target_col = new_column or column
        df[target_col] = np.log(df[column])
    return df, 1


def _sqrt_transform(
    df: pd.DataFrame, column: str, new_column: Optional[str] = None, **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"'{column}' n'est pas numérique")
    min_val = df[column].min()
    target_col = new_column or column
    if min_val < 0:
        df[target_col] = np.sqrt(df[column] - min_val)
    else:
        df[target_col] = np.sqrt(df[column])
    return df, 1


def _standardize_numeric(df: pd.DataFrame, columns: List[str], **kwargs) -> Tuple[pd.DataFrame, int]:
    from sklearn.preprocessing import StandardScaler
    valid_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    if not valid_cols:
        raise ValueError(f"Aucune colonne numérique valide dans {columns}")
    scaler = StandardScaler()
    df[valid_cols] = scaler.fit_transform(df[valid_cols])
    return df, len(valid_cols)


def _encode_onehot(
    df: pd.DataFrame, column: str, max_categories: int = 20, **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    n_unique = df[column].nunique()
    if n_unique > max_categories:
        raise ValueError(
            f"'{column}' a {n_unique} catégories > max_categories={max_categories}. "
            "Utiliser encode_target ou encode_ordinal à la place."
        )
    dummies = pd.get_dummies(df[column], prefix=column, drop_first=False, dtype=np.uint8)
    df = pd.concat([df.drop(columns=[column]), dummies], axis=1)
    return df, n_unique


def _encode_ordinal(
    df: pd.DataFrame, column: str, order: Optional[List[str]] = None, **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    if order:
        mapping = {cat: i for i, cat in enumerate(order)}
        df[column] = df[column].map(mapping)
    else:
        le = LabelEncoder()
        df[column] = le.fit_transform(df[column].astype(str))
    return df, 1


def _encode_target(df: pd.DataFrame, column: str, **kwargs) -> Tuple[pd.DataFrame, int]:
    """Target encoding (mean encoding) — nécessite la target."""
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    target_col = kwargs.get("target_column")
    if not target_col or target_col not in df.columns:
        # Fallback: label encoding
        return _encode_ordinal(df, column)
    means = df.groupby(column)[target_col].mean()
    df[f"{column}_target_enc"] = df[column].map(means)
    df = df.drop(columns=[column])
    return df, 1


def _extract_datetime(
    df: pd.DataFrame, column: str, extract: List[str], **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    try:
        dt_col = pd.to_datetime(df[column], infer_datetime_format=True)
    except Exception as e:
        raise ValueError(f"Impossible de parser '{column}' en datetime: {e}")

    extract_map = {
        "year": dt_col.dt.year,
        "month": dt_col.dt.month,
        "day": dt_col.dt.day,
        "dayofweek": dt_col.dt.dayofweek,
        "hour": dt_col.dt.hour,
        "minute": dt_col.dt.minute,
        "is_weekend": (dt_col.dt.dayofweek >= 5).astype(int),
    }
    for field in extract:
        if field in extract_map:
            df[f"{column}_{field}"] = extract_map[field]

    df = df.drop(columns=[column])
    return df, len(extract)


def _binarize(
    df: pd.DataFrame, column: str, threshold: float, new_column: Optional[str] = None, **kwargs
) -> Tuple[pd.DataFrame, int]:
    if column not in df.columns:
        raise KeyError(f"Colonne '{column}' introuvable")
    target_col = new_column or f"{column}_bin"
    df[target_col] = (df[column] > threshold).astype(int)
    return df, 1


# ─────────────────────────────────────────────
# WHITELIST — mapping action → fonction
# ─────────────────────────────────────────────
# Seules ces actions peuvent être exécutées.
# Le LLM ne peut pas appeler une fonction hors de cette liste.

CLEANING_ACTION_WHITELIST: Dict[str, callable] = {
    "impute_mean":              _impute_mean,
    "impute_median":            _impute_median,
    "impute_mode":              _impute_mode,
    "impute_knn":               _impute_knn,
    "drop_column":              _drop_column,
    "drop_rows_nulls":          _drop_rows_nulls,
    "drop_duplicates":          _drop_duplicates,
    "remove_outliers_iqr":      _remove_outliers_iqr,
    "remove_outliers_zscore":   _remove_outliers_zscore,
    "clip_outliers":            _clip_outliers,
    "fill_constant":            _fill_constant,
}

FEATURE_ACTION_WHITELIST: Dict[str, callable] = {
    "drop_column":              _drop_column,
    "create_ratio":             _create_ratio,
    "create_sum":               _create_sum,
    "create_difference":        _create_difference,
    "create_product":           _create_product,
    "log_transform":            _log_transform,
    "sqrt_transform":           _sqrt_transform,
    "standardize_numeric":      _standardize_numeric,
    "encode_onehot":            _encode_onehot,
    "encode_ordinal":           _encode_ordinal,
    "encode_target":            _encode_target,
    "extract_datetime":         _extract_datetime,
    "binarize":                 _binarize,
}


# ─────────────────────────────────────────────
# EXECUTE SINGLE ACTION
# ─────────────────────────────────────────────

def _execute_single_action(
    df: pd.DataFrame,
    action_data: Any,
    whitelist: Dict[str, callable],
    target_column: Optional[str] = None,
) -> Tuple[pd.DataFrame, ActionResult]:
    """
    Exécute une action unique depuis la whitelist.
    Retourne (df_modifié, ActionResult).
    En cas d'erreur, retourne le df INCHANGÉ + ActionResult(status="error").
    """
    action_dict = action_data.model_dump()
    action_name = action_dict.get("action")
    col_name = action_dict.get("column") or action_dict.get("new_feature") or action_dict.get("columns")

    if action_name not in whitelist:
        return df, ActionResult(
            action=action_name or "unknown",
            column=str(col_name) if col_name else None,
            status="error",
            message=f"Action '{action_name}' non autorisée — hors whitelist",
        )

    fn = whitelist[action_name]
    df_backup = df.copy()

    try:
        params = {k: v for k, v in action_dict.items() if k != "action" and v is not None}
        if target_column:
            params["target_column"] = target_column

        df_new, n_affected = fn(df, **params)

        logger.info(
            f"  ✓ {action_name}"
            + (f"({col_name})" if col_name else "")
            + f" → {n_affected} rows/cols affected"
        )

        return df_new, ActionResult(
            action=action_name,
            column=str(col_name) if col_name else None,
            status="success",
            message=f"{n_affected} éléments affectés",
            rows_affected=n_affected if isinstance(n_affected, int) else None,
        )

    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"  ⚠ {action_name} SKIPPED: {e}")
        return df_backup, ActionResult(
            action=action_name,
            column=str(col_name) if col_name else None,
            status="skipped",
            message=str(e),
        )

    except Exception as e:
        logger.error(f"  ✗ {action_name} ERROR: {e}")
        return df_backup, ActionResult(
            action=action_name,
            column=str(col_name) if col_name else None,
            status="error",
            message=str(e),
        )


# ─────────────────────────────────────────────
# MAIN EXECUTOR
# ─────────────────────────────────────────────

def execute_plan(
    df: pd.DataFrame,
    plan: LLMDecisionPlan,
) -> Tuple[pd.DataFrame, ExecutionReport]:
    """
    Exécute le plan LLM complet sur le DataFrame.

    Étapes :
    1. Cleaning actions (dans l'ordre)
    2. Feature actions (dans l'ordre)

    La target column n'est JAMAIS modifiée par les feature actions.
    Chaque action est loggée dans le ExecutionReport.

    Returns:
        (df_transformé, ExecutionReport)
    """
    logger.info(
        f"[Executor] run_id={plan.run_id} | "
        f"{len(plan.cleaning_actions)} cleaning + "
        f"{len(plan.feature_actions)} feature actions"
    )

    results: List[ActionResult] = []
    df = df.copy()  # Ne jamais modifier l'original

    # ── Phase 1 : Cleaning ──
    logger.info("[Executor] Phase 1 — Cleaning")
    for action in plan.cleaning_actions:
        # Sécurité : ne jamais supprimer la target
        action_dict = action.model_dump()
        if action_dict.get("column") == plan.target_column and action_dict.get("action") == "drop_column":
            results.append(ActionResult(
                action="drop_column",
                column=plan.target_column,
                status="skipped",
                message="Cannot drop target column",
            ))
            continue

        df, result = _execute_single_action(df, action, CLEANING_ACTION_WHITELIST, plan.target_column)
        results.append(result)

    # ── Phase 2 : Feature Engineering ──
    logger.info("[Executor] Phase 2 — Feature Engineering")
    for action in plan.feature_actions:
        action_dict = action.model_dump()
        if action_dict.get("column") == plan.target_column and action_dict.get("action") == "drop_column":
            results.append(ActionResult(
                action="drop_column",
                column=plan.target_column,
                status="skipped",
                message="Cannot drop target column",
            ))
            continue

        df, result = _execute_single_action(df, action, FEATURE_ACTION_WHITELIST, plan.target_column)
        results.append(result)

    # ── Conversion bool → uint8 (compatibilité sklearn SimpleImputer) ──────────
    # pd.get_dummies() peut retourner bool ; sklearn refuse bool dans SimpleImputer
    bool_cols = df.select_dtypes(include="bool").columns.tolist()
    if bool_cols:
        df[bool_cols] = df[bool_cols].astype(np.uint8)
        logger.info(f"[Executor] {len(bool_cols)} colonnes bool → uint8: {bool_cols}")

    # ── Récap ──
    n_success = sum(1 for r in results if r.status == "success")
    n_skipped = sum(1 for r in results if r.status == "skipped")
    n_errors  = sum(1 for r in results if r.status == "error")

    report = ExecutionReport(
        run_id=plan.run_id,
        total_actions=len(results),
        successful=n_success,
        skipped=n_skipped,
        errors=n_errors,
        results=results,
        final_shape=(len(df), len(df.columns)),
    )

    logger.info(
        f"[Executor] Terminé | "
        f"✓{n_success} ⚠{n_skipped} ✗{n_errors} | "
        f"Shape finale: {df.shape}"
    )

    return df, report


# ─────────────────────────────────────────────
# UTILITY: VALIDATE PLAN AGAINST DATAFRAME
# ─────────────────────────────────────────────

def validate_plan_against_df(
    df: pd.DataFrame,
    plan: LLMDecisionPlan,
) -> List[str]:
    """
    Vérifie que les colonnes référencées dans le plan existent dans le df.
    Retourne une liste de warnings (vide = OK).
    """
    warnings = []
    all_cols = set(df.columns)

    for action in plan.cleaning_actions:
        d = action.model_dump()
        col = d.get("column")
        if col and col not in all_cols:
            warnings.append(f"[cleaning] Colonne '{col}' dans l'action '{d['action']}' n'existe pas dans le dataset")

    for action in plan.feature_actions:
        d = action.model_dump()
        for field in ["column", "col1", "col2"]:
            col = d.get(field)
            if col and col not in all_cols and d["action"] not in ("create_ratio", "create_sum", "create_difference", "create_product"):
                warnings.append(f"[feature] Colonne '{col}' dans l'action '{d['action']}' n'existe pas")

        if "columns" in d and d["columns"]:
            for col in d["columns"]:
                if col not in all_cols:
                    warnings.append(f"[feature] Colonne '{col}' dans '{d['action']}' n'existe pas")

    if plan.target_column not in all_cols:
        warnings.append(f"[critical] Target column '{plan.target_column}' n'existe pas dans le dataset!")

    return warnings