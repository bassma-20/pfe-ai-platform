import pandas as pd
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.preprocessing import (
    StandardScaler,
    OneHotEncoder,
    OrdinalEncoder,
    LabelEncoder,
)

from app.automl.core.logging import get_logger

log = get_logger("preprocessing_service")

# High cardinality threshold for switching OrdinalEncoder
HIGH_CARDINALITY_THRESHOLD = 15


def infer_task(y: pd.Series) -> str:
    """Auto-detect classification vs regression from target series."""
    y_clean = y.dropna()
    if not pd.api.types.is_numeric_dtype(y_clean):
        return "classification"
    n_unique = y_clean.nunique()
    n_rows = len(y_clean)
    if n_unique <= 20 or n_unique <= max(2, int(0.05 * n_rows)):
        return "classification"
    return "regression"


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    """
    Build a smart ColumnTransformer:
    - Numeric  : KNNImputer → StandardScaler
    - Categorical low card  : MostFrequent → OneHotEncoder
    - Categorical high card : MostFrequent → OrdinalEncoder
    """
    # ── Sécurité : convertir les bool en uint8 (évite SimpleImputer crash) ──────
    # pd.get_dummies() retourne bool dans pandas >= 1.x ; sklearn ne supporte pas bool
    bool_cols = X.select_dtypes(include="bool").columns.tolist()
    if bool_cols:
        X = X.copy()
        X[bool_cols] = X[bool_cols].astype(np.uint8)
        log.info(f"[preprocessor] {len(bool_cols)} colonnes bool converties en uint8: {bool_cols}")

    numeric_features = X.select_dtypes(include="number").columns.tolist()
    cat_features = X.select_dtypes(exclude="number").columns.tolist()

    # Split categoricals by cardinality
    low_card = [c for c in cat_features if X[c].nunique(dropna=True) <= HIGH_CARDINALITY_THRESHOLD]
    high_card = [c for c in cat_features if X[c].nunique(dropna=True) > HIGH_CARDINALITY_THRESHOLD]

    transformers = []

    if numeric_features:
        numeric_pipe = Pipeline([
            ("imputer", KNNImputer(n_neighbors=5)),
            ("scaler", StandardScaler()),
        ])
        transformers.append(("num", numeric_pipe, numeric_features))

    if low_card:
        low_card_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])
        transformers.append(("cat_low", low_card_pipe, low_card))

    if high_card:
        high_card_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("ordinal", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ])
        transformers.append(("cat_high", high_card_pipe, high_card))

    if not transformers:
        # Fallback: passthrough
        from sklearn.preprocessing import FunctionTransformer
        return ColumnTransformer(
            transformers=[("passthrough", "passthrough", X.columns.tolist())]
        )

    # ✅ CORRIGÉ : f-string au lieu de kwargs
    log.info(
        f"[preprocessor_built] numeric={len(numeric_features)}"
        f" cat_low={len(low_card)} cat_high={len(high_card)}"
    )

    return ColumnTransformer(transformers=transformers, remainder="drop")


def encode_target(y: pd.Series) -> tuple[pd.Series, LabelEncoder | None]:
    """Encode string targets for classification. Returns encoded y and encoder."""
    if pd.api.types.is_numeric_dtype(y):
        return y, None
    le = LabelEncoder()
    y_encoded = pd.Series(le.fit_transform(y.astype(str)), index=y.index)
    # ✅ CORRIGÉ : f-string au lieu de kwargs
    log.info(f"[target_encoded] classes={list(le.classes_)}")
    return y_encoded, le