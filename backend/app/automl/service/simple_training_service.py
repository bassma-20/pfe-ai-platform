"""
simple_training_service.py — Direct training API (sans plan LLM).
Utilisé par les endpoints /analyze-features, /train, /predict.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    GradientBoostingClassifier, GradientBoostingRegressor,
    RandomForestClassifier, RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score, f1_score, mean_absolute_error,
    mean_squared_error, r2_score, roc_auc_score,
)
from sklearn.model_selection import (
    KFold, StratifiedKFold, cross_val_score, train_test_split,
)
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

import joblib

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _detect_task(y: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(y):
        n_unique = y.nunique()
        if n_unique <= 10 and n_unique / max(len(y), 1) < 0.05:
            return "classification"
        return "regression"
    return "classification"


def _quality(score: float, task: str) -> str:
    if task == "classification":
        if score >= 0.90: return "excellent"
        if score >= 0.80: return "good"
        if score >= 0.65: return "weak"
        return "poor"
    else:
        if score >= 0.90: return "excellent"
        if score >= 0.75: return "good"
        if score >= 0.50: return "weak"
        return "poor"


def _build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    # Convertir bool → uint8 pour éviter SimpleImputer crash (pd.get_dummies retourne bool)
    bool_cols = X.select_dtypes(include="bool").columns.tolist()
    if bool_cols:
        X = X.copy()
        X[bool_cols] = X[bool_cols].astype(np.uint8)
    num_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = X.select_dtypes(exclude=[np.number]).columns.tolist()

    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("scl", StandardScaler()),
        ]), num_cols))
    if cat_cols:
        transformers.append(("cat", Pipeline([
            ("imp", SimpleImputer(strategy="constant", fill_value="missing")),
            ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),  # sklearn ≥1.2
        ]), cat_cols))

    return ColumnTransformer(transformers, remainder="drop")


# ─────────────────────────────────────────────
# ANALYZE FEATURES
# ─────────────────────────────────────────────

def analyze_features(df: pd.DataFrame, target: str, features: List[str]) -> Dict[str, Any]:
    y = df[target].dropna()
    task_detected = _detect_task(y)

    warnings: List[str] = []
    recommended_features: List[Dict] = []

    for f in features:
        if f not in df.columns:
            warnings.append(f"Feature '{f}' introuvable dans le dataset")
            continue

        col = df[f]

        null_pct = col.isnull().mean() * 100
        if null_pct > 30:
            warnings.append(f"'{f}' a {null_pct:.1f}% de valeurs manquantes")
        if col.nunique() <= 1:
            warnings.append(f"'{f}' est une colonne constante (inutile pour l'entraînement)")

        corr = None
        if pd.api.types.is_numeric_dtype(col):
            try:
                yy = pd.to_numeric(y, errors="coerce") if not pd.api.types.is_numeric_dtype(y) else y
                col_a = col.loc[yy.index].dropna()
                yy = yy.loc[col_a.index].dropna()
                col_a = col_a.loc[yy.index]
                corr = round(float(abs(col_a.corr(yy))), 4)
            except Exception:
                corr = None

        if corr is not None:
            recommended_features.append({"feature": f, "correlation": corr})

    recommended_features.sort(key=lambda x: x["correlation"], reverse=True)

    imbalance_info: Dict[str, Any] = {"imbalanced": False}
    if task_detected == "classification":
        try:
            vc = y.value_counts()
            if len(vc) >= 2:
                ratio = round(float(vc.iloc[0] / vc.iloc[-1]), 2)
                if ratio > 3:
                    imbalance_info = {
                        "imbalanced": True,
                        "ratio": ratio,
                        "recommendation": "Considérez class_weight='balanced' ou sur-échantillonnage",
                    }
        except Exception:
            pass

    return {
        "task_detected": task_detected,
        "feature_analysis": {"warnings": warnings, "recommended_features": recommended_features},
        "imbalance_info": imbalance_info,
    }


# ─────────────────────────────────────────────
# TRAIN
# ─────────────────────────────────────────────

def train_simple(
    df: pd.DataFrame,
    target: str,
    features: List[str],
    task: str,
    test_size: float,
    cv_folds: int,
    use_optuna: bool,
    optuna_trials: int,
    run_id: str,
    data_dir: str,
) -> Dict[str, Any]:

    avail = [f for f in features if f in df.columns]
    X = df[avail].copy()
    y = df[target].copy()

    if task == "auto":
        task = _detect_task(y)

    # Encode target for classification
    le: Optional[LabelEncoder] = None
    if task == "classification" and not pd.api.types.is_numeric_dtype(y):
        le = LabelEncoder()
        y = pd.Series(le.fit_transform(y.astype(str)), index=y.index, name=target)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)

    is_clf = task == "classification"
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42) if is_clf else \
         KFold(n_splits=cv_folds, shuffle=True, random_state=42)

    if is_clf:
        model_specs = [
            ("RandomForest",       RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)),
            ("GradientBoosting",   GradientBoostingClassifier(n_estimators=100, random_state=42)),
            ("LogisticRegression", LogisticRegression(max_iter=1000, random_state=42)),
            ("DecisionTree",       DecisionTreeClassifier(random_state=42)),
            ("KNN",                KNeighborsClassifier()),
        ]
        cv_scoring = "f1_weighted"
        sort_key = "f1_weighted"
    else:
        model_specs = [
            ("RandomForest",     RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)),
            ("GradientBoosting", GradientBoostingRegressor(n_estimators=100, random_state=42)),
            ("Ridge",            Ridge()),
            ("LinearRegression", LinearRegression()),
            ("DecisionTree",     DecisionTreeRegressor(random_state=42)),
        ]
        cv_scoring = "neg_root_mean_squared_error"
        sort_key = "r2"

    leaderboard: List[Dict] = []
    best_score = -float("inf")
    best_pipeline: Optional[Pipeline] = None
    best_model_name = ""

    for name, model in model_specs:
        try:
            t0 = time.time()
            pipe = Pipeline([("pre", _build_preprocessor(X)), ("mdl", model)])
            pipe.fit(X_train, y_train)
            elapsed = round(time.time() - t0, 2)
            y_pred = pipe.predict(X_test)

            # CV scores (fresh pipeline to avoid data leakage)
            cv_pipe = Pipeline([("pre", _build_preprocessor(X)), ("mdl", model.__class__(**model.get_params()))])
            cv_scores = cross_val_score(cv_pipe, X, y, cv=cv, scoring=cv_scoring, n_jobs=-1)

            if is_clf:
                f1  = round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)), 4)
                acc = round(float(accuracy_score(y_test, y_pred)), 4)
                cv_f1 = round(float(cv_scores.mean()), 4)
                roc = None
                try:
                    if hasattr(pipe, "predict_proba"):
                        proba = pipe.predict_proba(X_test)
                        if proba.shape[1] == 2:
                            roc = round(float(roc_auc_score(y_test, proba[:, 1])), 4)
                        else:
                            roc = round(float(roc_auc_score(y_test, proba, multi_class="ovr", average="weighted")), 4)
                except Exception:
                    pass
                score = f1
                entry = {"model": name, "f1_weighted": f1, "accuracy": acc,
                         "cv_f1_weighted": cv_f1, "roc_auc": roc,
                         "training_time_sec": elapsed, "model_quality": _quality(f1, task)}
            else:
                r2   = round(float(r2_score(y_test, y_pred)), 4)
                rmse = round(float(mean_squared_error(y_test, y_pred) ** 0.5), 4)
                mae  = round(float(mean_absolute_error(y_test, y_pred)), 4)
                cv_rmse = round(float(-cv_scores.mean()), 4)
                score = r2
                entry = {"model": name, "r2": r2, "rmse": rmse, "mae": mae,
                         "cv_rmse": cv_rmse, "training_time_sec": elapsed,
                         "model_quality": _quality(r2, task)}

            leaderboard.append(entry)
            if score > best_score:
                best_score = score
                best_pipeline = pipe
                best_model_name = name

        except Exception as e:
            logger.warning(f"[Train] {name} échoué : {e}")

    # ── Optuna ──────────────────────────────────────────────────────────────
    optuna_used = False
    if use_optuna:
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def objective(trial: "optuna.Trial") -> float:
                params = {
                    "n_estimators":      trial.suggest_int("n_estimators", 50, 300),
                    "max_depth":         trial.suggest_int("max_depth", 3, 20),
                    "min_samples_split": trial.suggest_int("min_samples_split", 2, 10),
                }
                m = (RandomForestClassifier if is_clf else RandomForestRegressor)(**params, random_state=42, n_jobs=-1)
                p = Pipeline([("pre", _build_preprocessor(X_train)), ("mdl", m)])
                sc = cross_val_score(p, X_train, y_train, cv=3, scoring=cv_scoring)
                return float(sc.mean())

            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=min(optuna_trials, 20), timeout=60)

            bp = study.best_params
            opt_m = (RandomForestClassifier if is_clf else RandomForestRegressor)(**bp, random_state=42, n_jobs=-1)
            opt_pipe = Pipeline([("pre", _build_preprocessor(X)), ("mdl", opt_m)])
            t0 = time.time()
            opt_pipe.fit(X_train, y_train)
            elapsed = round(time.time() - t0, 2)
            y_pred = opt_pipe.predict(X_test)

            if is_clf:
                f1  = round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)), 4)
                acc = round(float(accuracy_score(y_test, y_pred)), 4)
                opt_entry = {"model": "RandomForest (Optuna)", "f1_weighted": f1, "accuracy": acc,
                             "cv_f1_weighted": round(float(study.best_value), 4), "roc_auc": None,
                             "training_time_sec": elapsed, "model_quality": _quality(f1, task)}
                if f1 > best_score:
                    best_score, best_pipeline, best_model_name = f1, opt_pipe, "RandomForest (Optuna)"
            else:
                r2   = round(float(r2_score(y_test, y_pred)), 4)
                rmse = round(float(mean_squared_error(y_test, y_pred) ** 0.5), 4)
                mae  = round(float(mean_absolute_error(y_test, y_pred)), 4)
                opt_entry = {"model": "RandomForest (Optuna)", "r2": r2, "rmse": rmse, "mae": mae,
                             "cv_rmse": round(float(-study.best_value), 4),
                             "training_time_sec": elapsed, "model_quality": _quality(r2, task)}
                if r2 > best_score:
                    best_score, best_pipeline, best_model_name = r2, opt_pipe, "RandomForest (Optuna)"

            leaderboard.append(opt_entry)
            optuna_used = True

        except ImportError:
            logger.warning("[Train] Optuna non installé")
        except Exception as e:
            logger.warning(f"[Train] Optuna échoué : {e}")

    # Sort leaderboard
    leaderboard.sort(key=lambda x: x.get(sort_key, -float("inf")), reverse=True)

    # ── Feature importance ───────────────────────────────────────────────────
    feature_importance: Dict[str, Any] = {"available": False, "items": []}
    if best_pipeline:
        try:
            mdl = best_pipeline.named_steps["mdl"]
            pre = best_pipeline.named_steps["pre"]
            if hasattr(mdl, "feature_importances_"):
                try:
                    feat_names = list(pre.get_feature_names_out())
                except Exception:
                    feat_names = avail
                items = sorted(
                    [{"feature": str(n), "importance": round(float(v), 6)}
                     for n, v in zip(feat_names, mdl.feature_importances_)],
                    key=lambda x: x["importance"], reverse=True
                )[:20]
                feature_importance = {"available": True, "items": items}
        except Exception as e:
            logger.debug(f"[Train] Feature importance : {e}")

    # ── SHAP ────────────────────────────────────────────────────────────────
    shap_summary: Dict[str, Any] = {"available": False, "values": []}
    if best_pipeline:
        try:
            import shap
            mdl = best_pipeline.named_steps["mdl"]
            pre = best_pipeline.named_steps["pre"]
            X_t = pre.transform(X_test.iloc[:min(100, len(X_test))])
            exp = shap.TreeExplainer(mdl)
            sv  = exp.shap_values(X_t)
            if isinstance(sv, list):
                sv = np.abs(sv[0])
            else:
                sv = np.abs(sv)
            mean_sv = np.mean(sv, axis=0)
            try:
                feat_names = list(pre.get_feature_names_out())
            except Exception:
                feat_names = avail
            vals = sorted(
                [{"feature": str(n), "shap_importance": round(float(v), 6)}
                 for n, v in zip(feat_names, mean_sv)],
                key=lambda x: x["shap_importance"], reverse=True
            )[:10]
            shap_summary = {"available": True, "values": vals}
        except Exception as e:
            logger.debug(f"[Train] SHAP : {e}")

    # ── Save model ───────────────────────────────────────────────────────────
    if best_pipeline and data_dir:
        try:
            os.makedirs(data_dir, exist_ok=True)
            joblib.dump(best_pipeline, os.path.join(data_dir, f"{run_id}_simple_model.pkl"))
            meta = {
                "task": task,
                "features": avail,
                "target": target,
                "le_classes": le.classes_.tolist() if le else None,
                "model_name": best_model_name,
            }
            with open(os.path.join(data_dir, f"{run_id}_simple_meta.json"), "w") as fh:
                json.dump(meta, fh)
        except Exception as e:
            logger.warning(f"[Train] Sauvegarde échouée : {e}")

    # ── Recommendation ───────────────────────────────────────────────────────
    metric_label = sort_key
    rec = f"'{best_model_name}' : {metric_label}={best_score:.4f}."
    if best_score < 0.5:
        rec += " Performances faibles — ajoutez des features ou plus de données."
    elif best_score > 0.9:
        rec += " Excellentes performances — vérifiez l'absence de data leakage."

    return {
        "task": task,
        "best_model": {"name": best_model_name, "quality": _quality(best_score, task)},
        "optuna_used": optuna_used,
        "recommendation": rec,
        "leaderboard": leaderboard,
        "feature_importance": feature_importance,
        "shap_summary": shap_summary,
    }


# ─────────────────────────────────────────────
# PREDICT
# ─────────────────────────────────────────────

def predict_simple(run_id: str, data: Dict[str, Any], data_dir: str) -> Dict[str, Any]:
    model_path = os.path.join(data_dir, f"{run_id}_simple_model.pkl")
    meta_path  = os.path.join(data_dir, f"{run_id}_simple_meta.json")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modèle introuvable pour run_id={run_id}. Entraînez d'abord.")

    pipeline = joblib.load(model_path)
    with open(meta_path) as fh:
        meta = json.load(fh)

    task       = meta["task"]
    features   = meta["features"]
    le_classes = meta.get("le_classes")

    df_in = pd.DataFrame([{f: data.get(f) for f in features}])
    raw_pred = pipeline.predict(df_in)[0]

    if le_classes is not None:
        try:
            prediction = le_classes[int(raw_pred)]
        except Exception:
            prediction = str(raw_pred)
    elif hasattr(raw_pred, "item"):
        prediction = raw_pred.item()
    else:
        prediction = raw_pred

    confidence = None
    if task == "classification":
        try:
            proba = pipeline.predict_proba(df_in)[0]
            confidence = round(float(max(proba)), 4)
        except Exception:
            pass

    return {
        "task": task,
        "prediction": prediction if isinstance(prediction, (int, float, bool, str)) else str(prediction),
        "confidence": confidence,
    }
