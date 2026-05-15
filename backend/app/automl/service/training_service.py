"""
backend/app/automl/service/training_service.py

Training Service — Entraîne les modèles selon le plan LLM.
✅ Sauvegarde train_meta.json avec les features exactes utilisées.
✅ Alignement automatique lors de la prédiction (aucun hardcoding).
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, StratifiedKFold, KFold
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score,
    r2_score, mean_squared_error, mean_absolute_error,
    precision_score, recall_score,
)

from app.automl.models.schemas import (
    LLMDecisionPlan,
    ModelName,
    ModelPlan,
    ModelResult,
    ProblemType,
    TrainingResult,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# MODEL REGISTRY
# ─────────────────────────────────────────────

def _get_base_model(model_name: ModelName, problem_type: ProblemType):
    from sklearn.ensemble import (
        RandomForestClassifier, RandomForestRegressor,
        GradientBoostingClassifier, GradientBoostingRegressor,
        ExtraTreesClassifier, ExtraTreesRegressor,
    )
    from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge, Lasso
    from sklearn.svm import SVC, SVR
    from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

    is_clf = problem_type in (ProblemType.BINARY_CLASSIFICATION, ProblemType.MULTICLASS_CLASSIFICATION)

    if model_name == ModelName.XGBOOST:
        try:
            from xgboost import XGBClassifier, XGBRegressor
            return (
                XGBClassifier(n_estimators=100, random_state=42, n_jobs=-1, verbosity=0)
                if is_clf else
                XGBRegressor(n_estimators=100, random_state=42, n_jobs=-1, verbosity=0)
            )
        except ImportError:
            logger.warning("XGBoost non installé — GradientBoosting utilisé")
            model_name = ModelName.GRADIENT_BOOSTING

    if model_name == ModelName.LIGHTGBM:
        try:
            from lightgbm import LGBMClassifier, LGBMRegressor
            return (
                LGBMClassifier(n_estimators=100, random_state=42, n_jobs=-1, verbose=-1)
                if is_clf else
                LGBMRegressor(n_estimators=100, random_state=42, n_jobs=-1, verbose=-1)
            )
        except ImportError:
            logger.warning("LightGBM non installé — GradientBoosting utilisé")
            model_name = ModelName.GRADIENT_BOOSTING

    registry = {
        ModelName.RANDOM_FOREST: (
            RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            if is_clf else
            RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        ),
        ModelName.GRADIENT_BOOSTING: (
            GradientBoostingClassifier(n_estimators=100, random_state=42)
            if is_clf else
            GradientBoostingRegressor(n_estimators=100, random_state=42)
        ),
        ModelName.EXTRA_TREES: (
            ExtraTreesClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            if is_clf else
            ExtraTreesRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        ),
        ModelName.LOGISTIC_REGRESSION: LogisticRegression(max_iter=1000, random_state=42),
        ModelName.LINEAR_REGRESSION:   LinearRegression(),
        ModelName.RIDGE:               Ridge(),
        ModelName.LASSO:               Lasso(max_iter=5000),
        ModelName.SVM:  SVC(probability=True, random_state=42) if is_clf else SVR(),
        ModelName.KNN:  KNeighborsClassifier(n_jobs=-1) if is_clf else KNeighborsRegressor(n_jobs=-1),
        ModelName.DECISION_TREE: (
            DecisionTreeClassifier(random_state=42)
            if is_clf else
            DecisionTreeRegressor(random_state=42)
        ),
    }
    return registry.get(model_name)


# ─────────────────────────────────────────────
# OPTUNA SEARCH SPACES
# ─────────────────────────────────────────────

def _get_optuna_params(trial, model_name: ModelName, problem_type: ProblemType) -> Dict[str, Any]:
    if model_name in (ModelName.RANDOM_FOREST, ModelName.EXTRA_TREES):
        return {
            "n_estimators":    trial.suggest_int("n_estimators", 50, 300),
            "max_depth":       trial.suggest_int("max_depth", 3, 20),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
            "min_samples_leaf":  trial.suggest_int("min_samples_leaf", 1, 10),
            "max_features":    trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
        }
    elif model_name == ModelName.GRADIENT_BOOSTING:
        return {
            "n_estimators":  trial.suggest_int("n_estimators", 50, 300),
            "max_depth":     trial.suggest_int("max_depth", 2, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample":     trial.suggest_float("subsample", 0.6, 1.0),
            "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
        }
    elif model_name == ModelName.XGBOOST:
        return {
            "n_estimators":    trial.suggest_int("n_estimators", 50, 300),
            "max_depth":       trial.suggest_int("max_depth", 2, 10),
            "learning_rate":   trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "subsample":       trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        }
    elif model_name == ModelName.LIGHTGBM:
        return {
            "n_estimators":  trial.suggest_int("n_estimators", 50, 300),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves":    trial.suggest_int("num_leaves", 20, 150),
            "subsample":     trial.suggest_float("subsample", 0.6, 1.0),
        }
    elif model_name == ModelName.LOGISTIC_REGRESSION:
        return {
            "C":      trial.suggest_float("C", 0.001, 100.0, log=True),
            "solver": trial.suggest_categorical("solver", ["lbfgs", "liblinear"]),
        }
    elif model_name in (ModelName.RIDGE, ModelName.LASSO):
        return {"alpha": trial.suggest_float("alpha", 0.001, 100.0, log=True)}
    elif model_name == ModelName.KNN:
        return {
            "n_neighbors": trial.suggest_int("n_neighbors", 1, 30),
            "weights":     trial.suggest_categorical("weights", ["uniform", "distance"]),
        }
    elif model_name == ModelName.SVM:
        return {
            "C":      trial.suggest_float("C", 0.01, 100.0, log=True),
            "kernel": trial.suggest_categorical("kernel", ["rbf", "linear"]),
        }
    return {}


# ─────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────

def _compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray],
    problem_type: ProblemType,
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}

    if problem_type == ProblemType.BINARY_CLASSIFICATION:
        metrics["accuracy"]  = round(accuracy_score(y_true, y_pred), 4)
        metrics["f1"]        = round(f1_score(y_true, y_pred, average="binary", zero_division=0), 4)
        metrics["precision"] = round(precision_score(y_true, y_pred, zero_division=0), 4)
        metrics["recall"]    = round(recall_score(y_true, y_pred, zero_division=0), 4)
        if y_proba is not None:
            try:
                metrics["roc_auc"] = round(roc_auc_score(y_true, y_proba[:, 1]), 4)
            except Exception:
                pass

    elif problem_type == ProblemType.MULTICLASS_CLASSIFICATION:
        metrics["accuracy"]    = round(accuracy_score(y_true, y_pred), 4)
        metrics["f1_macro"]    = round(f1_score(y_true, y_pred, average="macro", zero_division=0), 4)
        metrics["f1_weighted"] = round(f1_score(y_true, y_pred, average="weighted", zero_division=0), 4)
        if y_proba is not None:
            try:
                metrics["roc_auc_ovr"] = round(
                    roc_auc_score(y_true, y_proba, multi_class="ovr", average="macro"), 4
                )
            except Exception:
                pass

    elif problem_type == ProblemType.REGRESSION:
        metrics["r2"]   = round(r2_score(y_true, y_pred), 4)
        metrics["rmse"] = round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4)
        metrics["mae"]  = round(float(mean_absolute_error(y_true, y_pred)), 4)

    return metrics


def _get_cv_scorer(primary_metric: Optional[str], problem_type: ProblemType) -> str:
    if primary_metric:
        mapping = {
            "f1":          "f1" if problem_type == ProblemType.BINARY_CLASSIFICATION else "f1_macro",
            "accuracy":    "accuracy",
            "roc_auc":     "roc_auc",
            "r2":          "r2",
            "rmse":        "neg_root_mean_squared_error",
            "mae":         "neg_mean_absolute_error",
            "f1_macro":    "f1_macro",
            "f1_weighted": "f1_weighted",
        }
        if primary_metric in mapping:
            return mapping[primary_metric]
    if problem_type == ProblemType.BINARY_CLASSIFICATION:
        return "f1"
    elif problem_type == ProblemType.MULTICLASS_CLASSIFICATION:
        return "f1_macro"
    return "r2"


# ─────────────────────────────────────────────
# TRAIN SINGLE MODEL
# ✅ Retourne (ModelResult, model_instance)
# ─────────────────────────────────────────────

def _train_single_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_name: ModelName,
    problem_type: ProblemType,
    model_plan: ModelPlan,
) -> Tuple[ModelResult, Any]:
    from sklearn.pipeline import Pipeline as SklearnPipeline
    from app.automl.service.preprocessing_service import build_preprocessor

    logger.info(f"  → Entraînement: {model_name.value}")
    start = time.time()

    is_clf = problem_type in (ProblemType.BINARY_CLASSIFICATION, ProblemType.MULTICLASS_CLASSIFICATION)
    scorer = _get_cv_scorer(model_plan.primary_metric, problem_type)
    cv = (
        StratifiedKFold(n_splits=model_plan.cv_folds, shuffle=True, random_state=42)
        if is_clf else
        KFold(n_splits=model_plan.cv_folds, shuffle=True, random_state=42)
    )

    preprocessor = build_preprocessor(X_train)
    best_params: Dict[str, Any] = {}

    if model_plan.use_optuna:
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial):
                params = _get_optuna_params(trial, model_name, problem_type)
                m = _get_base_model(model_name, problem_type)
                if m is None:
                    raise ValueError(f"Modèle {model_name} non disponible")
                m.set_params(**params)
                pipe = SklearnPipeline([("preprocessor", build_preprocessor(X_train)), ("model", m)])
                scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring=scorer, n_jobs=-1)
                return scores.mean()

            direction = "minimize" if scorer.startswith("neg_") else "maximize"
            study = optuna.create_study(direction=direction, sampler=optuna.samplers.TPESampler(seed=42))
            study.optimize(objective, n_trials=model_plan.trials, show_progress_bar=False)
            best_params = study.best_params
            logger.info(f"    Optuna best: {study.best_value:.4f} | params: {best_params}")
        except ImportError:
            logger.warning("Optuna non installé")
        except Exception as e:
            logger.warning(f"Optuna échoué ({e})")

    base_model = _get_base_model(model_name, problem_type)
    if base_model is None:
        return ModelResult(
            model_name=model_name.value, params={},
            metrics={"error": -1}, training_time_sec=0.0,
        ), None

    if best_params:
        try:
            base_model.set_params(**best_params)
        except Exception as e:
            logger.warning(f"set_params échoué ({e})")

    model = SklearnPipeline([("preprocessor", preprocessor), ("model", base_model)])

    try:
        cv_scores = cross_val_score(model, X_train, y_train, cv=cv, scoring=scorer, n_jobs=-1)
        cv_mean, cv_std = float(cv_scores.mean()), float(cv_scores.std())
    except Exception as e:
        logger.warning(f"CV échouée ({e})")
        cv_scores = np.array([0.0])
        cv_mean, cv_std = 0.0, 0.0

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = None
    if is_clf and hasattr(model, "predict_proba"):
        try:
            y_proba = model.predict_proba(X_test)
        except Exception:
            pass

    metrics = _compute_metrics(y_test, y_pred, y_proba, problem_type)
    training_time = time.time() - start

    logger.info(f"    ✓ {model_name.value}: CV={cv_mean:.4f}±{cv_std:.4f} | metrics={metrics} | {training_time:.1f}s")

    return ModelResult(
        model_name=model_name.value,
        params=best_params,
        metrics=metrics,
        training_time_sec=round(training_time, 2),
        cv_scores=cv_scores.tolist(),
        cv_mean=round(cv_mean, 4),
        cv_std=round(cv_std, 4),
    ), model


# ─────────────────────────────────────────────
# FEATURE IMPORTANCE
# ─────────────────────────────────────────────

def _extract_feature_importance(model, feature_names: List[str]) -> Optional[Dict[str, float]]:
    inner = model.named_steps["model"] if hasattr(model, "named_steps") else model

    importance = None
    if hasattr(inner, "feature_importances_"):
        importance = inner.feature_importances_
    elif hasattr(inner, "coef_"):
        coef = inner.coef_
        importance = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)
    if importance is None:
        return None

    # Try to get transformed feature names from the preprocessor
    names = feature_names
    if hasattr(model, "named_steps") and "preprocessor" in model.named_steps:
        try:
            names = list(model.named_steps["preprocessor"].get_feature_names_out())
        except Exception:
            pass

    if len(names) != len(importance):
        names = [f"feature_{i}" for i in range(len(importance))]

    total = importance.sum()
    if total == 0:
        return None
    importance = importance / total
    result = dict(zip(names, importance.tolist()))
    return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))


# ─────────────────────────────────────────────
# SAVE MODEL + META
# ─────────────────────────────────────────────

def _save_model_and_meta(
    model,
    run_id: str,
    data_dir: str,
    feature_names: List[str],
    target_column: str,
    problem_type: str,
    best_metrics: Dict[str, float],
    best_params: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Sauvegarde le modèle ET train_meta.json.
    train_meta.json contient TOUTES les infos nécessaires pour la prédiction.
    Retourne (model_path, meta_path).
    """
    import joblib

    abs_data_dir = os.path.abspath(data_dir)
    save_dir = os.path.join(abs_data_dir, run_id)
    os.makedirs(save_dir, exist_ok=True)

    # ── Sauvegarde modèle ──
    model_path = os.path.join(save_dir, "best_model.joblib")
    joblib.dump(model, model_path)
    logger.info(f"[Training] ✅ Modèle sauvegardé : {model_path}")

    # ── Sauvegarde meta ──
    meta = {
        "run_id": run_id,
        "target_column": target_column,
        "problem_type": problem_type,
        "feature_names": feature_names,       # ✅ liste ordonnée des features
        "n_features": len(feature_names),
        "best_metrics": best_metrics,
        "best_params": best_params,
        "model_path": model_path,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    meta_path = os.path.join(save_dir, "train_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    logger.info(f"[Training] ✅ Meta sauvegardée : {meta_path}")
    logger.info(f"[Training] Features sauvegardées ({len(feature_names)}) : {feature_names}")

    return model_path, meta_path


# ─────────────────────────────────────────────
# PREPARE DATA
# ─────────────────────────────────────────────

def _prepare_data(
    df: pd.DataFrame,
    target_column: str,
    problem_type: ProblemType,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    from sklearn.model_selection import train_test_split

    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' non trouvée")

    y = df[target_column].copy()
    X = df.drop(columns=[target_column]).copy()

    is_clf = problem_type in (ProblemType.BINARY_CLASSIFICATION, ProblemType.MULTICLASS_CLASSIFICATION)
    if is_clf and not pd.api.types.is_numeric_dtype(y):
        from sklearn.preprocessing import LabelEncoder
        le = LabelEncoder()
        y = pd.Series(le.fit_transform(y.astype(str)), index=y.index, name=y.name)

    stratify = y if is_clf else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=stratify
    )
    return X_train, X_test, y_train, y_test


# ─────────────────────────────────────────────
# MAIN: TRAIN WITH LLM PLAN
# ─────────────────────────────────────────────

def train_with_plan(
    df: pd.DataFrame,
    plan: LLMDecisionPlan,
    data_dir: str = "data",
    test_size: float = 0.2,
    save_model: bool = True,
) -> TrainingResult:
    logger.info(
        f"[Training] Début | run_id={plan.run_id} | "
        f"models={[m.value for m in plan.model_plan.models_to_try]} | "
        f"data_dir={os.path.abspath(data_dir)}"
    )
    total_start = time.time()

    X_train, X_test, y_train, y_test = _prepare_data(
        df, plan.target_column, plan.problem_type, test_size
    )

    # ✅ Sauvegarder la liste exacte des features dans l'ordre
    feature_names: List[str] = list(X_train.columns)
    logger.info(f"[Training] Features utilisées ({len(feature_names)}) : {feature_names}")

    model_results: List[ModelResult] = []
    trained_models: Dict[str, Any] = {}

    for model_name in plan.model_plan.models_to_try:
        try:
            result, trained_model = _train_single_model(
                X_train, y_train, X_test, y_test,
                model_name, plan.problem_type, plan.model_plan,
            )
            model_results.append(result)
            if trained_model is not None:
                trained_models[model_name.value] = trained_model
                logger.info(f"  ✅ {model_name.value} stocké")
            else:
                logger.warning(f"  ⚠ {model_name.value} : modèle None")
        except Exception as e:
            logger.error(f"  ✗ {model_name.value} FAILED: {e}", exc_info=True)
            model_results.append(ModelResult(
                model_name=model_name.value, params={},
                metrics={"error": -1}, training_time_sec=0.0,
            ))

    if not model_results:
        raise RuntimeError("Aucun modèle n'a pu être entraîné")

    scorer_key = plan.model_plan.primary_metric or (
        "r2" if plan.problem_type == ProblemType.REGRESSION else "f1"
    )

    def _get_score(r: ModelResult) -> float:
        if scorer_key in r.metrics:
            return r.metrics[scorer_key]
        vals = [v for v in r.metrics.values() if v != -1]
        return vals[0] if vals else -1.0

    valid_results = [r for r in model_results if _get_score(r) != -1]
    if not valid_results:
        raise RuntimeError("Tous les modèles ont échoué")

    reverse = scorer_key not in ("rmse", "mae")
    best_result = max(valid_results, key=_get_score) if reverse else min(valid_results, key=_get_score)

    logger.info(f"[Training] ✅ Meilleur: {best_result.model_name} | {best_result.metrics}")

    feature_importance = None
    best_model_instance = trained_models.get(best_result.model_name)

    if best_model_instance is not None:
        feature_importance = _extract_feature_importance(best_model_instance, feature_names)
        if save_model:
            try:
                _save_model_and_meta(
                    model=best_model_instance,
                    run_id=plan.run_id,
                    data_dir=data_dir,
                    feature_names=feature_names,        # ✅ features exactes
                    target_column=plan.target_column,
                    problem_type=plan.problem_type.value,
                    best_metrics=best_result.metrics,
                    best_params=best_result.params,
                )
            except Exception as e:
                logger.error(f"[Training] ❌ Sauvegarde échouée : {e}", exc_info=True)
    else:
        logger.error(f"[Training] ❌ best_model_instance None | trained_models={list(trained_models.keys())}")

    total_time = time.time() - total_start
    logger.info(f"[Training] Terminé en {total_time:.1f}s")

    return TrainingResult(
        run_id=plan.run_id,
        problem_type=plan.problem_type,
        target_column=plan.target_column,
        models_evaluated=model_results,
        best_model=best_result.model_name,
        best_metrics=best_result.metrics,
        best_params=best_result.params,
        feature_importance=feature_importance,
        optuna_used=plan.model_plan.use_optuna,
        total_training_time_sec=round(total_time, 2),
    )


# ─────────────────────────────────────────────
# ALIGN FEATURES FOR PREDICTION
# ✅ Fonction générale — aucun hardcoding
# ─────────────────────────────────────────────

def align_features_for_prediction(
    df: pd.DataFrame,
    meta: Dict[str, Any],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Aligne le DataFrame de prédiction avec les features utilisées à l'entraînement.
    Entièrement générique — fonctionne pour n'importe quel dataset.

    Étapes :
    1. Supprimer la colonne target si présente
    2. Supprimer les colonnes inconnues (non vues à l'entraînement)
    3. Ajouter les colonnes manquantes avec valeur 0
    4. Réordonner exactement comme à l'entraînement

    Retourne (df_aligné, rapport_alignement).
    """
    expected_features: List[str] = meta["feature_names"]
    target_column: str = meta.get("target_column", "")

    report = {
        "expected_features": expected_features,
        "original_columns": list(df.columns),
        "target_removed": False,
        "unknown_columns_removed": [],
        "missing_columns_added": [],
        "final_features": [],
        "warnings": [],
    }

    # ── Step 1 : Supprimer la target si présente ──
    if target_column and target_column in df.columns:
        df = df.drop(columns=[target_column])
        report["target_removed"] = True
        report["warnings"].append(
            f"Colonne target '{target_column}' supprimée automatiquement du fichier de prédiction."
        )
        logger.info(f"[Predict] Target '{target_column}' supprimée du fichier de prédiction")

    # ── Step 2 : Supprimer les colonnes inconnues ──
    unknown_cols = [c for c in df.columns if c not in expected_features]
    if unknown_cols:
        df = df.drop(columns=unknown_cols)
        report["unknown_columns_removed"] = unknown_cols
        report["warnings"].append(
            f"Colonnes inconnues supprimées (non vues à l'entraînement) : {unknown_cols}"
        )
        logger.warning(f"[Predict] Colonnes inconnues supprimées : {unknown_cols}")

    # ── Step 3 : Ajouter les colonnes manquantes ──
    missing_cols = [c for c in expected_features if c not in df.columns]
    if missing_cols:
        for col in missing_cols:
            df[col] = 0.0
        report["missing_columns_added"] = missing_cols
        report["warnings"].append(
            f"Colonnes manquantes ajoutées avec valeur 0 : {missing_cols}"
        )
        logger.warning(f"[Predict] Colonnes manquantes ajoutées avec 0 : {missing_cols}")

    # ── Step 4 : Réordonner exactement comme à l'entraînement ──
    df = df[expected_features]

    # ── Remplir les NaN résiduels numériques ──
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0.0)

    report["final_features"] = list(df.columns)

    logger.info(
        f"[Predict] Alignement terminé | "
        f"features: {len(df.columns)} | "
        f"lignes: {len(df)} | "
        f"target_removed={report['target_removed']}"
    )

    return df, report


# ─────────────────────────────────────────────
# LOAD META
# ─────────────────────────────────────────────

def load_train_meta(run_id: str, data_dir: str) -> Dict[str, Any]:
    """Charge train_meta.json pour un run_id donné."""
    abs_data_dir = os.path.abspath(data_dir)
    meta_path = os.path.join(abs_data_dir, run_id, "train_meta.json")

    if not os.path.exists(meta_path):
        raise FileNotFoundError(
            f"train_meta.json introuvable : {meta_path}. "
            "Re-entraînez le modèle avec save_model=true."
        )

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    logger.info(f"[Predict] Meta chargée | features={meta.get('feature_names')} | target={meta.get('target_column')}")
    return meta


# ─────────────────────────────────────────────
# PREDICT WITH SAVED MODEL
# ✅ Alignement automatique via train_meta.json
# ─────────────────────────────────────────────

def predict_with_saved_model(
    df: pd.DataFrame,
    run_id: str,
    data_dir: str = "data",
) -> Dict[str, Any]:
    """
    Prédit avec le modèle sauvegardé.
    ✅ Alignement automatique des features via train_meta.json.
    ✅ Aucun hardcoding — fonctionne pour n'importe quel dataset.
    """
    import joblib

    # ── Charger la meta ──
    meta = load_train_meta(run_id, data_dir)

    # ── Charger le modèle ──
    abs_data_dir = os.path.abspath(data_dir)
    model_path = os.path.join(abs_data_dir, run_id, "best_model.joblib")

    logger.info(f"[Predict] Modèle : {model_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modèle non trouvé : {model_path}")

    model = joblib.load(model_path)

    # ── Alignement automatique ──
    X, alignment_report = align_features_for_prediction(df, meta)

    if X.empty or len(X.columns) == 0:
        raise ValueError(
            f"Aucune feature valide après alignement. "
            f"Features attendues : {meta['feature_names']}. "
            f"Colonnes fournies : {list(df.columns)}"
        )

    if len(X.columns) != len(meta["feature_names"]):
        raise ValueError(
            f"Nombre de features incorrect après alignement : "
            f"{len(X.columns)} vs {len(meta['feature_names'])} attendues."
        )

    # ── Prédiction ──
    predictions = model.predict(X).tolist()
    confidence_scores = None

    if hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(X)
            confidence_scores = proba.max(axis=1).tolist()
        except Exception:
            pass

    return {
        "run_id": run_id,
        "predictions": predictions,
        "confidence_scores": confidence_scores,
        "n_samples": len(predictions),
        "features_used": meta["feature_names"],
        "target_column": meta.get("target_column"),
        "alignment_report": alignment_report,
    }