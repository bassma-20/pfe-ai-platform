"""
backend/app/automl/service/data_service.py

Service de chargement et nettoyage automatique des datasets.
Robuste face aux données sales, mixtes, et imparfaites.
Ne crashe JAMAIS — retourne toujours un rapport structuré.

✅ FIX detect_leakage :
  - Méthode 1 : Corrélation > 0.95 avec la target
  - Méthode 2 : Copies exactes de la target (valeur par valeur)
  - Méthode 3 : Patterns de noms suspects (leaky, copy, duplicate...)
  - Fonctionne même sans target_column (méthode 3 active)
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# RAPPORT DE NETTOYAGE
# ─────────────────────────────────────────────

@dataclass
class CleaningReport:
    dataset_shape_before: Tuple[int, int] = (0, 0)
    dataset_shape_after: Tuple[int, int] = (0, 0)
    errors_detected: List[str] = field(default_factory=list)
    cleaning_actions_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    columns_dropped: List[str] = field(default_factory=list)
    columns_converted: List[str] = field(default_factory=list)
    duplicates_removed: int = 0
    nulls_filled: Dict[str, int] = field(default_factory=dict)
    outliers_clipped: List[str] = field(default_factory=list)
    impossible_values_fixed: List[str] = field(default_factory=list)
    leakage_suspects: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_shape_before": list(self.dataset_shape_before),
            "dataset_shape_after": list(self.dataset_shape_after),
            "errors_detected": self.errors_detected,
            "cleaning_actions_applied": self.cleaning_actions_applied,
            "warnings": self.warnings,
            "columns_dropped": self.columns_dropped,
            "columns_converted": self.columns_converted,
            "duplicates_removed": self.duplicates_removed,
            "nulls_filled": self.nulls_filled,
            "outliers_clipped": self.outliers_clipped,
            "impossible_values_fixed": self.impossible_values_fixed,
            "leakage_suspects": self.leakage_suspects,
        }


# ─────────────────────────────────────────────
# STEP 1 — LECTURE ROBUSTE DU FICHIER
# ─────────────────────────────────────────────

def read_file_robust(content: bytes, filename: str) -> Tuple[pd.DataFrame, List[str]]:
    warnings: List[str] = []
    filename_lower = filename.lower()

    if filename_lower.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(
                io.BytesIO(content),
                dtype=str,
                na_values=["", "NA", "N/A", "null", "NULL", "None", "none", "nan", "NaN", "-"],
                keep_default_na=True,
            )
            return df, warnings
        except Exception as e:
            raise ValueError(f"Impossible de lire le fichier Excel : {e}")

    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
    separators = [",", ";", "\t", "|"]

    for encoding in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(
                    io.BytesIO(content),
                    sep=sep,
                    encoding=encoding,
                    dtype=str,
                    na_values=["", "NA", "N/A", "null", "NULL", "None", "none", "nan", "NaN", "-"],
                    keep_default_na=True,
                    on_bad_lines="warn",
                    engine="python",
                )
                if len(df.columns) >= 2:
                    if encoding != "utf-8":
                        warnings.append(f"Encodage détecté : {encoding}")
                    if sep != ",":
                        warnings.append(f"Séparateur détecté : '{sep}'")
                    return df, warnings
            except Exception:
                continue

    raise ValueError(
        "Impossible de lire le fichier CSV. "
        "Vérifiez l'encodage et le format (UTF-8, séparateur virgule ou point-virgule)."
    )


# ─────────────────────────────────────────────
# STEP 2 — NETTOYAGE DES NOMS DE COLONNES
# ─────────────────────────────────────────────

def clean_column_names(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    original = list(df.columns)
    df.columns = [re.sub(r'\s+', '_', str(c).strip()) for c in df.columns]
    renamed = [f"{o} → {n}" for o, n in zip(original, df.columns) if o != n]
    if renamed:
        report.cleaning_actions_applied.append(f"Noms de colonnes normalisés : {renamed[:5]}")
    return df


# ─────────────────────────────────────────────
# STEP 3 — CONVERSION AUTOMATIQUE DES TYPES
# ─────────────────────────────────────────────

def _try_parse_numeric(series: pd.Series) -> Tuple[pd.Series, int]:
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(r'[\$€£¥,\s]', '', regex=True)
        .str.replace(r'%$', '', regex=True)
        .str.replace(r'^--?$', 'NaN', regex=True)
    )
    converted = pd.to_numeric(cleaned, errors='coerce')
    n_replaced = max(0, int(converted.isna().sum() - series.isna().sum()))
    return converted, n_replaced


def convert_types_auto(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    for col in df.columns:
        series = df[col]
        n_non_null = series.notna().sum()
        if n_non_null == 0:
            continue

        converted, n_bad = _try_parse_numeric(series)
        n_ok = converted.notna().sum()
        ratio_numeric = n_ok / n_non_null if n_non_null > 0 else 0

        if ratio_numeric >= 0.6:
            df[col] = converted
            report.columns_converted.append(col)
            if n_bad > 0:
                report.errors_detected.append(
                    f"Colonne '{col}' : {n_bad} valeur(s) non-numérique(s) remplacées par NaN"
                )
                report.cleaning_actions_applied.append(
                    f"'{col}' converti en numérique ({n_bad} valeurs → NaN)"
                )
            continue

        col_lower = col.lower()
        if any(kw in col_lower for kw in ["date", "time", "year", "month", "day", "timestamp"]):
            try:
                df[col] = pd.to_datetime(series, infer_datetime_format=True, errors='coerce')
                report.columns_converted.append(col)
                report.cleaning_actions_applied.append(f"'{col}' converti en datetime")
                continue
            except Exception:
                pass

        n_unique = series.nunique()
        n_total = len(series)
        if n_total > 0 and n_unique / n_total < 0.5 and n_unique <= 50:
            df[col] = series.astype("category")

    return df


# ─────────────────────────────────────────────
# STEP 4 — SUPPRESSION DES DOUBLONS
# ─────────────────────────────────────────────

def remove_duplicates(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    n_before = len(df)
    df = df.drop_duplicates()
    n_removed = n_before - len(df)
    if n_removed > 0:
        report.duplicates_removed = n_removed
        report.cleaning_actions_applied.append(f"{n_removed} lignes dupliquées supprimées")
    return df


# ─────────────────────────────────────────────
# STEP 5 — COLONNES INUTILES
# ─────────────────────────────────────────────

_ID_PATTERNS = re.compile(
    r'^(id|index|row_?num|record_?id|_id|uuid|guid|key|ref|reference|no\.?$|num\.?$|#)',
    re.IGNORECASE,
)
_USELESS_PATTERNS = re.compile(
    r'(unnamed|column\d+|col\d+|field\d+)',
    re.IGNORECASE,
)


def drop_useless_columns(
    df: pd.DataFrame,
    report: CleaningReport,
    target_column: Optional[str] = None,
    max_unique_ratio: float = 0.95,
    min_unique_for_id: int = 10,
) -> pd.DataFrame:
    to_drop = []
    n_rows = len(df)

    for col in df.columns:
        if col == target_column:
            continue

        series = df[col].dropna()
        n_unique = series.nunique()

        if n_unique <= 1:
            to_drop.append((col, "colonne constante (0 variance)"))
            continue

        if _USELESS_PATTERNS.search(col):
            to_drop.append((col, "colonne sans nom valide"))
            continue

        if _ID_PATTERNS.search(col.replace(" ", "_")):
            if n_unique >= min_unique_for_id:
                to_drop.append((col, "colonne ID détectée par nom"))
                continue

        if n_rows > 20 and (n_unique / n_rows) > max_unique_ratio:
            if pd.api.types.is_numeric_dtype(df[col]):
                sorted_vals = series.sort_values().reset_index(drop=True)
                is_sequential = (sorted_vals.diff().dropna() == 1).all()
                if is_sequential:
                    to_drop.append((col, f"index séquentiel caché ({n_unique}/{n_rows} valeurs uniques)"))
                    continue
            elif pd.api.types.is_string_dtype(df[col]) or hasattr(df[col], 'cat'):
                to_drop.append((col, f"trop de valeurs uniques ({n_unique}/{n_rows}) — probable ID texte"))
                continue

    if to_drop:
        cols = [c for c, _ in to_drop]
        reasons = [f"'{c}': {r}" for c, r in to_drop]
        df = df.drop(columns=cols, errors='ignore')
        report.columns_dropped.extend(cols)
        report.cleaning_actions_applied.append(f"Colonnes inutiles supprimées : {reasons}")

    return df


# ─────────────────────────────────────────────
# STEP 6 — GESTION DES VALEURS MANQUANTES
# ─────────────────────────────────────────────

def handle_missing_values(
    df: pd.DataFrame,
    report: CleaningReport,
    target_column: Optional[str] = None,
    drop_threshold: float = 0.7,
) -> pd.DataFrame:
    null_ratios = df.isnull().mean()
    high_null_cols = [
        col for col in df.columns
        if null_ratios[col] > drop_threshold and col != target_column
    ]
    if high_null_cols:
        df = df.drop(columns=high_null_cols)
        report.columns_dropped.extend(high_null_cols)
        report.cleaning_actions_applied.append(
            f"Colonnes supprimées (>{drop_threshold*100:.0f}% nulls) : {high_null_cols}"
        )

    if target_column and target_column in df.columns:
        n_before = len(df)
        df = df.dropna(subset=[target_column])
        n_dropped = n_before - len(df)
        if n_dropped > 0:
            report.cleaning_actions_applied.append(
                f"{n_dropped} lignes supprimées (target '{target_column}' nulle)"
            )

    for col in df.columns:
        if col == target_column:
            continue
        n_null = int(df[col].isnull().sum())
        if n_null == 0:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            fill_val = df[col].median()
            df[col] = df[col].fillna(fill_val)
            report.nulls_filled[col] = n_null
            report.cleaning_actions_applied.append(
                f"'{col}' : {n_null} nulls → médiane ({fill_val:.4g})"
            )
        else:
            mode_vals = df[col].mode()
            if len(mode_vals) > 0:
                df[col] = df[col].fillna(mode_vals[0])
                report.nulls_filled[col] = n_null
                report.cleaning_actions_applied.append(
                    f"'{col}' : {n_null} nulls → mode ('{mode_vals[0]}')"
                )
            else:
                df[col] = df[col].fillna("UNKNOWN")
                report.nulls_filled[col] = n_null

    return df


# ─────────────────────────────────────────────
# STEP 7 — VALEURS IMPOSSIBLES
# ─────────────────────────────────────────────

_IMPOSSIBLE_RULES = {
    r'age':                                (0, 120),
    r'experience':                         (0, 70),
    r'salary|salaire|wage|income|revenue': (0, None),
    r'price|prix|cost|amount|total|montant': (0, None),
    r'quantity|qty|quantite|stock':        (0, None),
    r'percentage|pct|ratio|rate|taux':     (0, 100),
    r'year|annee|ann[eé]e':               (1900, 2100),
    r'month|mois':                         (1, 12),
    r'day|jour':                           (1, 31),
    r'hour|heure':                         (0, 23),
    r'score|note|grade':                   (0, None),
}


def fix_impossible_values(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        col_lower = col.lower()
        for pattern, (vmin, vmax) in _IMPOSSIBLE_RULES.items():
            if re.search(pattern, col_lower):
                n_fixed = 0
                if vmin is not None:
                    mask = df[col] < vmin
                    n_fixed += int(mask.sum())
                    df.loc[mask, col] = np.nan
                if vmax is not None:
                    mask = df[col] > vmax
                    n_fixed += int(mask.sum())
                    df.loc[mask, col] = np.nan
                if n_fixed > 0:
                    df[col] = df[col].fillna(df[col].median())
                    report.impossible_values_fixed.append(
                        f"'{col}' : {n_fixed} valeur(s) hors plage [{vmin}, {vmax}] → médiane"
                    )
                    report.cleaning_actions_applied.append(
                        f"Valeurs impossibles corrigées dans '{col}' ({n_fixed} valeurs)"
                    )
                break
    return df


# ─────────────────────────────────────────────
# STEP 8 — OUTLIERS
# ─────────────────────────────────────────────

def handle_outliers(
    df: pd.DataFrame,
    report: CleaningReport,
    target_column: Optional[str] = None,
    iqr_threshold: float = 3.0,
    max_outlier_ratio: float = 0.05,
) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col == target_column:
            continue
        series = df[col].dropna()
        if len(series) < 10:
            continue

        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        if IQR == 0:
            continue

        lower = Q1 - iqr_threshold * IQR
        upper = Q3 + iqr_threshold * IQR
        n_out = int(((df[col] < lower) | (df[col] > upper)).sum())
        ratio = n_out / len(df)

        if 0 < n_out and ratio <= max_outlier_ratio:
            df[col] = df[col].clip(lower=lower, upper=upper)
            report.outliers_clipped.append(f"'{col}' : {n_out} outlier(s) clippés")
            report.cleaning_actions_applied.append(
                f"Outliers clippés dans '{col}' : {n_out} valeurs (IQR×{iqr_threshold})"
            )
        elif ratio > max_outlier_ratio:
            report.warnings.append(
                f"'{col}' : {n_out} outliers ({ratio:.1%}) — trop nombreux pour clipper automatiquement"
            )

    return df


# ─────────────────────────────────────────────
# STEP 9 — DATA LEAKAGE DETECTION (3 MÉTHODES)
# ─────────────────────────────────────────────

# ✅ Patterns de noms suspects — actifs même sans target_column
_LEAKAGE_NAME_PATTERNS = re.compile(
    r'(leaky|leak|target_copy|_copy|copy_|duplicate|dup_|_dup|'
    r'label_copy|y_true|y_pred|prediction_|result_copy|'
    r'answer|cheat|target2|_target$|ground_truth)',
    re.IGNORECASE,
)


def detect_leakage(
    df: pd.DataFrame,
    target_column: Optional[str],
    report: CleaningReport,
    corr_threshold: float = 0.95,  # ✅ Abaissé de 0.98 → 0.95
) -> pd.DataFrame:
    """
    Détecte le data leakage par 3 méthodes complémentaires.

    Méthode 1 — Corrélation avec la target (nécessite target_column)
    Méthode 2 — Copie exacte de la target valeur par valeur (nécessite target_column)
    Méthode 3 — Pattern de nom suspect (fonctionne SANS target_column)
    """
    to_drop: List[str] = []

    # ── Méthode 1 & 2 : nécessitent la target ──
    if target_column and target_column in df.columns:
        logger.info(f"[Leakage] Analyse target='{target_column}' | seuil corr={corr_threshold}")

        if pd.api.types.is_numeric_dtype(df[target_column]):
            y = df[target_column]
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

            for col in numeric_cols:
                if col == target_column or col in to_drop:
                    continue

                # Méthode 2 : copie exacte (prioritaire — plus fiable)
                try:
                    both_null = df[col].isna() & y.isna()
                    both_equal = (df[col] == y) | both_null
                    if both_equal.all():
                        reason = f"copie exacte de la target '{target_column}'"
                        report.leakage_suspects.append(f"'{col}' ({reason})")
                        report.warnings.append(f"⚠ DATA LEAKAGE CRITIQUE : '{col}' — {reason}")
                        to_drop.append(col)
                        logger.warning(f"[Leakage] ✗ '{col}' — {reason}")
                        continue
                except Exception:
                    pass

                # Méthode 1 : corrélation
                try:
                    corr = abs(df[col].corr(y))
                    logger.debug(f"[Leakage] corr('{col}', target) = {corr:.4f}")
                    if corr > corr_threshold:
                        reason = f"corrélation {corr:.2%} avec target '{target_column}'"
                        report.leakage_suspects.append(f"'{col}' ({reason})")
                        report.warnings.append(f"⚠ DATA LEAKAGE : '{col}' — {reason}")
                        to_drop.append(col)
                        logger.warning(f"[Leakage] ✗ '{col}' — {reason}")
                except Exception as e:
                    logger.debug(f"[Leakage] Corrélation '{col}' échouée : {e}")
        else:
            logger.info(f"[Leakage] Target '{target_column}' non numérique — skip méthodes 1 & 2")
    else:
        logger.warning(
            f"[Leakage] target_column='{target_column}' absente — "
            "méthodes 1 & 2 désactivées, méthode 3 (noms) active"
        )

    # ── Méthode 3 : patterns de noms — TOUJOURS active ──
    for col in df.columns:
        if col == target_column or col in to_drop:
            continue
        if _LEAKAGE_NAME_PATTERNS.search(col):
            reason = "nom suspect (pattern leakage)"
            report.leakage_suspects.append(f"'{col}' ({reason})")
            report.warnings.append(f"⚠ DATA LEAKAGE PROBABLE : '{col}' — {reason}")
            to_drop.append(col)
            logger.warning(f"[Leakage] ✗ '{col}' — {reason}")

    # ── Suppression ──
    if to_drop:
        to_drop = list(dict.fromkeys(to_drop))  # dédupliquer en gardant l'ordre
        df = df.drop(columns=to_drop, errors='ignore')
        report.columns_dropped.extend(to_drop)
        report.cleaning_actions_applied.append(
            f"Colonnes leakage supprimées ({len(to_drop)}) : {to_drop}"
        )
        logger.info(f"[Leakage] {len(to_drop)} colonnes supprimées : {to_drop}")
    else:
        logger.info("[Leakage] Aucun leakage détecté ✅")

    return df


# ─────────────────────────────────────────────
# STEP 10 — CATÉGORIES INCOHÉRENTES
# ─────────────────────────────────────────────

def fix_categorical_inconsistencies(df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
    cat_cols = df.select_dtypes(include=["object", "category"]).columns

    for col in cat_cols:
        series = df[col].astype(str)
        stripped = series.str.strip()

        lower_map: Dict[str, str] = {}
        for val in stripped.dropna().unique():
            key = val.lower()
            if key not in lower_map:
                lower_map[key] = val
            elif lower_map[key] != val:
                count_existing = (stripped == lower_map[key]).sum()
                count_new = (stripped == val).sum()
                if count_new > count_existing:
                    lower_map[key] = val

        normalized = stripped.map(lambda x: lower_map.get(x.lower(), x) if pd.notna(x) else x)
        df[col] = normalized

        n_unique = df[col].nunique()
        if n_unique > 10:
            value_counts = df[col].value_counts(normalize=True)
            rare_vals = value_counts[value_counts < 0.01].index.tolist()
            if rare_vals:
                df[col] = df[col].replace(rare_vals, "Other")
                report.cleaning_actions_applied.append(
                    f"'{col}' : {len(rare_vals)} catégories rares → 'Other'"
                )

    return df


# ─────────────────────────────────────────────
# PIPELINE COMPLET
# ─────────────────────────────────────────────

def clean_dataset(
    content: bytes,
    filename: str,
    target_column: Optional[str] = None,
) -> Tuple[pd.DataFrame, CleaningReport]:
    """
    Pipeline complet de nettoyage automatique.
    Ne crashe jamais — retourne toujours (df, rapport).
    """
    report = CleaningReport()

    # ── Step 1 : Lecture ──
    try:
        df, file_warnings = read_file_robust(content, filename)
        report.warnings.extend(file_warnings)
    except ValueError:
        raise

    report.dataset_shape_before = df.shape

    if df.empty:
        raise ValueError("Le dataset est vide après lecture.")
    if len(df.columns) < 2:
        raise ValueError(
            f"Le dataset ne contient qu'une seule colonne ({df.columns.tolist()}). "
            "Vérifiez le séparateur CSV."
        )

    logger.info(f"[DataService] Fichier lu : {df.shape} | colonnes : {list(df.columns[:10])}")
    if target_column:
        logger.info(f"[DataService] target_column='{target_column}'")
    else:
        logger.warning("[DataService] target_column non fourni — leakage par corrélation désactivé")

    # ── Step 2 : Noms de colonnes ──
    try:
        df = clean_column_names(df, report)
        if target_column:
            target_column = re.sub(r'\s+', '_', str(target_column).strip())
    except Exception as e:
        report.warnings.append(f"Nettoyage noms colonnes échoué : {e}")

    # ── Step 3 : Conversion types ──
    try:
        df = convert_types_auto(df, report)
    except Exception as e:
        report.warnings.append(f"Conversion types échouée partiellement : {e}")

    # ── Step 4 : Doublons ──
    try:
        df = remove_duplicates(df, report)
    except Exception as e:
        report.warnings.append(f"Suppression doublons échouée : {e}")

    # ── Step 5 : Colonnes inutiles ──
    try:
        df = drop_useless_columns(df, report, target_column=target_column)
    except Exception as e:
        report.warnings.append(f"Suppression colonnes inutiles échouée : {e}")

    # ── Step 6 : Valeurs impossibles ──
    try:
        df = fix_impossible_values(df, report)
    except Exception as e:
        report.warnings.append(f"Correction valeurs impossibles échouée : {e}")

    # ── Step 7 : Valeurs manquantes ──
    try:
        df = handle_missing_values(df, report, target_column=target_column)
    except Exception as e:
        report.warnings.append(f"Gestion valeurs manquantes échouée : {e}")

    # ── Step 8 : Outliers ──
    try:
        df = handle_outliers(df, report, target_column=target_column)
    except Exception as e:
        report.warnings.append(f"Gestion outliers échouée : {e}")

    # ── Step 9 : Catégories ──
    try:
        df = fix_categorical_inconsistencies(df, report)
    except Exception as e:
        report.warnings.append(f"Correction catégories échouée : {e}")

    # ── Step 10 : Data leakage — TOUJOURS exécuté ──
    try:
        df = detect_leakage(df, target_column, report)
    except Exception as e:
        report.warnings.append(f"Détection leakage échouée : {e}")
        logger.error(f"[Leakage] Erreur inattendue : {e}", exc_info=True)

    report.dataset_shape_after = df.shape

    logger.info(
        f"[DataService] Nettoyage terminé : "
        f"{report.dataset_shape_before} → {report.dataset_shape_after} | "
        f"{len(report.cleaning_actions_applied)} actions | "
        f"{len(report.warnings)} warnings | "
        f"leakage={report.leakage_suspects}"
    )

    return df, report


# ─────────────────────────────────────────────
# VALIDATE DATASET FOR TRAINING
# ─────────────────────────────────────────────

def validate_for_training(
    df: pd.DataFrame,
    target_column: str,
) -> List[str]:
    errors = []

    if target_column not in df.columns:
        errors.append(f"Colonne target '{target_column}' introuvable dans le dataset.")
        return errors

    if len(df) < 10:
        errors.append(f"Dataset trop petit après nettoyage : {len(df)} lignes (minimum 10).")

    if len(df.columns) - 1 < 1:
        errors.append("Aucune feature disponible après nettoyage.")

    n_target_null = int(df[target_column].isnull().sum())
    if n_target_null > 0:
        errors.append(
            f"La colonne target '{target_column}' contient encore {n_target_null} valeurs nulles."
        )

    numeric_features = df.drop(columns=[target_column]).select_dtypes(include=[np.number]).columns
    if len(numeric_features) == 0:
        errors.append(
            "Aucune colonne numérique disponible pour l'entraînement. "
            "Encodez les colonnes catégorielles d'abord."
        )

    return errors