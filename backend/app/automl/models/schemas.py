"""
backend/app/automl/models/schemas.py

Pydantic schemas pour le système LLM-Driven AutoML.
Tous les schémas de validation des décisions LLM et des résultats.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# ENUMS — actions autorisées (whitelist stricte)
# ─────────────────────────────────────────────

class CleaningActionType(str, Enum):
    IMPUTE_MEAN            = "impute_mean"
    IMPUTE_MEDIAN          = "impute_median"
    IMPUTE_MODE            = "impute_mode"
    IMPUTE_KNN             = "impute_knn"
    DROP_COLUMN            = "drop_column"
    DROP_ROWS_NULLS        = "drop_rows_nulls"
    REMOVE_OUTLIERS_IQR    = "remove_outliers_iqr"
    REMOVE_OUTLIERS_ZSCORE = "remove_outliers_zscore"
    CLIP_OUTLIERS          = "clip_outliers"
    FILL_CONSTANT          = "fill_constant"
    DROP_DUPLICATES        = "drop_duplicates"

class FeatureActionType(str, Enum):
    DROP_COLUMN       = "drop_column"
    CREATE_RATIO      = "create_ratio"
    CREATE_SUM        = "create_sum"
    CREATE_DIFFERENCE = "create_difference"
    CREATE_PRODUCT    = "create_product"
    LOG_TRANSFORM     = "log_transform"
    SQRT_TRANSFORM    = "sqrt_transform"
    STANDARDIZE       = "standardize_numeric"
    ENCODE_ONEHOT     = "encode_onehot"
    ENCODE_ORDINAL    = "encode_ordinal"
    ENCODE_TARGET     = "encode_target"
    EXTRACT_DATETIME  = "extract_datetime"
    BINARIZE          = "binarize"

class ModelName(str, Enum):
    RANDOM_FOREST       = "RandomForest"
    GRADIENT_BOOSTING   = "GradientBoosting"
    XGBOOST             = "XGBoost"
    LIGHTGBM            = "LightGBM"
    EXTRA_TREES         = "ExtraTrees"
    LOGISTIC_REGRESSION = "LogisticRegression"
    LINEAR_REGRESSION   = "LinearRegression"
    RIDGE               = "Ridge"
    LASSO               = "Lasso"
    SVM                 = "SVM"
    KNN                 = "KNN"
    DECISION_TREE       = "DecisionTree"

class ProblemType(str, Enum):
    BINARY_CLASSIFICATION     = "binary_classification"
    MULTICLASS_CLASSIFICATION = "multiclass_classification"
    REGRESSION                = "regression"


# ─────────────────────────────────────────────
# CLEANING ACTIONS
# ─────────────────────────────────────────────

class ImputeAction(BaseModel):
    action: Literal[
        CleaningActionType.IMPUTE_MEAN,
        CleaningActionType.IMPUTE_MEDIAN,
        CleaningActionType.IMPUTE_MODE,
        CleaningActionType.IMPUTE_KNN,
    ]
    column: str
    reason: Optional[str] = None
    k_neighbors: Optional[int] = Field(default=5, ge=1, le=20)

class DropColumnAction(BaseModel):
    action: Literal[CleaningActionType.DROP_COLUMN, FeatureActionType.DROP_COLUMN]
    column: str
    reason: Optional[str] = None

class RemoveOutliersAction(BaseModel):
    action: Literal[
        CleaningActionType.REMOVE_OUTLIERS_IQR,
        CleaningActionType.REMOVE_OUTLIERS_ZSCORE,
    ]
    column: str
    threshold: Optional[float] = Field(default=1.5)
    reason: Optional[str] = None

class ClipOutliersAction(BaseModel):
    action: Literal[CleaningActionType.CLIP_OUTLIERS]
    column: str
    lower_quantile: float = Field(default=0.01, ge=0.0, le=0.5)
    upper_quantile: float = Field(default=0.99, ge=0.5, le=1.0)
    reason: Optional[str] = None

class FillConstantAction(BaseModel):
    action: Literal[CleaningActionType.FILL_CONSTANT]
    column: str
    value: Union[str, int, float]
    reason: Optional[str] = None

class DropRowsNullsAction(BaseModel):
    action: Literal[CleaningActionType.DROP_ROWS_NULLS]
    columns: Optional[List[str]] = None
    threshold: Optional[float] = Field(default=None)
    reason: Optional[str] = None

class DropDuplicatesAction(BaseModel):
    action: Literal[CleaningActionType.DROP_DUPLICATES]
    subset: Optional[List[str]] = None   # colonnes à considérer (None = toutes)
    reason: Optional[str] = None

CleaningAction = Union[
    ImputeAction,
    DropColumnAction,
    RemoveOutliersAction,
    ClipOutliersAction,
    FillConstantAction,
    DropRowsNullsAction,
    DropDuplicatesAction,
]


# ─────────────────────────────────────────────
# FEATURE ACTIONS
# ─────────────────────────────────────────────

class CreateRatioAction(BaseModel):
    action: Literal[FeatureActionType.CREATE_RATIO]
    new_feature: str
    col1: str
    col2: str
    reason: Optional[str] = None

class CreateSumAction(BaseModel):
    action: Literal[FeatureActionType.CREATE_SUM]
    new_feature: str
    columns: List[str] = Field(min_length=2)
    reason: Optional[str] = None

class CreateDifferenceAction(BaseModel):
    action: Literal[FeatureActionType.CREATE_DIFFERENCE]
    new_feature: str
    col1: str
    col2: str
    reason: Optional[str] = None

class CreateProductAction(BaseModel):
    action: Literal[FeatureActionType.CREATE_PRODUCT]
    new_feature: str
    col1: str
    col2: str
    reason: Optional[str] = None

class LogTransformAction(BaseModel):
    action: Literal[FeatureActionType.LOG_TRANSFORM]
    column: str
    new_column: Optional[str] = None
    reason: Optional[str] = None

class SqrtTransformAction(BaseModel):
    action: Literal[FeatureActionType.SQRT_TRANSFORM]
    column: str
    new_column: Optional[str] = None
    reason: Optional[str] = None

class StandardizeAction(BaseModel):
    action: Literal[FeatureActionType.STANDARDIZE]
    columns: List[str] = Field(min_length=1)
    reason: Optional[str] = None

class EncodeOneHotAction(BaseModel):
    action: Literal[FeatureActionType.ENCODE_ONEHOT]
    column: str
    max_categories: Optional[int] = Field(default=20, ge=2, le=100)
    reason: Optional[str] = None

class EncodeOrdinalAction(BaseModel):
    action: Literal[FeatureActionType.ENCODE_ORDINAL]
    column: str
    order: Optional[List[str]] = None
    reason: Optional[str] = None

class EncodeTargetAction(BaseModel):
    action: Literal[FeatureActionType.ENCODE_TARGET]
    column: str
    reason: Optional[str] = None

class ExtractDatetimeAction(BaseModel):
    action: Literal[FeatureActionType.EXTRACT_DATETIME]
    column: str
    extract: List[Literal["year", "month", "day", "dayofweek", "hour", "minute", "is_weekend"]]
    reason: Optional[str] = None

class BinarizeAction(BaseModel):
    action: Literal[FeatureActionType.BINARIZE]
    column: str
    threshold: float
    new_column: Optional[str] = None
    reason: Optional[str] = None

FeatureAction = Union[
    DropColumnAction,
    CreateRatioAction,
    CreateSumAction,
    CreateDifferenceAction,
    CreateProductAction,
    LogTransformAction,
    SqrtTransformAction,
    StandardizeAction,
    EncodeOneHotAction,
    EncodeOrdinalAction,
    EncodeTargetAction,
    ExtractDatetimeAction,
    BinarizeAction,
]


# ─────────────────────────────────────────────
# MODEL PLAN
# ─────────────────────────────────────────────

class ModelPlan(BaseModel):
    models_to_try: List[ModelName] = Field(min_length=1, max_length=8)
    use_optuna: bool = True
    trials: int = Field(default=30, ge=5, le=200)
    cv_folds: int = Field(default=5, ge=3, le=10)
    primary_metric: Optional[str] = None
    reason: Optional[str] = None

    @field_validator("models_to_try")
    @classmethod
    def no_duplicate_models(cls, v: List[ModelName]) -> List[ModelName]:
        if len(v) != len(set(v)):
            raise ValueError("models_to_try contient des doublons")
        return v


# ─────────────────────────────────────────────
# DATASET SUMMARY
# ─────────────────────────────────────────────

class ColumnInfo(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: List[Any] = Field(max_length=5)
    is_numeric: bool
    skewness: Optional[float] = None
    has_outliers_iqr: Optional[bool] = None
    missing_type: Optional[Literal["MCAR", "MAR", "MNAR", "none"]] = None

class DatasetSummary(BaseModel):
    run_id: str
    n_rows: int
    n_cols: int
    target_column: Optional[str] = None
    problem_type: Optional[ProblemType] = None
    columns: List[ColumnInfo]
    duplicate_rows: int = 0
    total_null_pct: float = 0.0
    class_balance: Optional[Dict[str, float]] = None
    suggested_target: Optional[str] = None


# ─────────────────────────────────────────────
# LLM DECISION PLAN
# ─────────────────────────────────────────────

class LLMDecisionPlan(BaseModel):
    run_id: str
    problem_type: ProblemType
    target_column: str
    confidence: float = Field(ge=0.0, le=1.0)
    cleaning_actions: List[CleaningAction] = Field(default_factory=list)
    feature_actions: List[FeatureAction] = Field(default_factory=list)
    model_plan: ModelPlan
    data_warnings: List[str] = Field(default_factory=list)
    reasoning_summary: Optional[str] = None
    llm_model_used: Optional[str] = None
    generated_at: Optional[str] = None

    model_config = {"populate_by_name": True}


# ─────────────────────────────────────────────
# EXECUTION RESULTS
# ─────────────────────────────────────────────

class ActionResult(BaseModel):
    action: str
    column: Optional[str] = None
    status: Literal["success", "skipped", "error"]
    message: Optional[str] = None
    rows_affected: Optional[int] = None

class ExecutionReport(BaseModel):
    run_id: str
    total_actions: int
    successful: int
    skipped: int
    errors: int
    results: List[ActionResult]
    final_shape: Optional[tuple] = None

    @property
    def success_rate(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return self.successful / self.total_actions


# ─────────────────────────────────────────────
# TRAINING RESULT
# ─────────────────────────────────────────────

class ModelResult(BaseModel):
    model_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict)
    training_time_sec: Optional[float] = None
    cv_scores: Optional[List[float]] = None
    cv_mean: Optional[float] = None
    cv_std: Optional[float] = None

class TrainingResult(BaseModel):
    run_id: str
    problem_type: ProblemType
    target_column: str
    models_evaluated: List[ModelResult]
    best_model: str
    best_metrics: Dict[str, float]
    best_params: Dict[str, Any] = Field(default_factory=dict)
    feature_importance: Optional[Dict[str, float]] = None
    optuna_used: bool = False
    total_training_time_sec: Optional[float] = None


# ─────────────────────────────────────────────
# FINAL USER REPORT
# ─────────────────────────────────────────────

class ExecutiveSummary(BaseModel):
    one_liner: str
    model_performance: str
    top_factors: List[str] = Field(max_length=5)
    recommendation: str

class TechnicalInsights(BaseModel):
    dataset_shape_original: tuple
    dataset_shape_after_cleaning: tuple
    columns_dropped: List[str] = Field(default_factory=list)
    columns_created: List[str] = Field(default_factory=list)
    null_rows_handled: int = 0
    outliers_removed: int = 0
    models_tested: List[str]
    best_model: str
    metrics: Dict[str, float]
    cv_mean: Optional[float] = None
    cv_std: Optional[float] = None
    data_warnings: List[str] = Field(default_factory=list)

class ActionableRecommendation(BaseModel):
    priority: Literal["high", "medium", "low"]
    category: Literal["data", "features", "model", "deployment"]
    message: str
    estimated_impact: Optional[str] = None
    effort: Optional[Literal["low", "medium", "high"]] = None

class FinalUserReport(BaseModel):
    run_id: str
    generated_at: str
    executive_summary: ExecutiveSummary
    technical_insights: TechnicalInsights
    recommendations: List[ActionableRecommendation] = Field(default_factory=list)
    decision_plan: Optional[LLMDecisionPlan] = None
    execution_report: Optional[ExecutionReport] = None
    training_result: Optional[TrainingResult] = None
    llm_explanation: Optional[str] = None


# ─────────────────────────────────────────────
# API REQUEST / RESPONSE SCHEMAS
# ─────────────────────────────────────────────

class DecisionPlanRequest(BaseModel):
    run_id: str
    dataset_summary: DatasetSummary
    user_hints: Optional[Dict[str, Any]] = None

class DecisionPlanResponse(BaseModel):
    run_id: str
    status: Literal["success", "error"]
    plan: Optional[LLMDecisionPlan] = None
    error: Optional[str] = None

class ApplyPlanResponse(BaseModel):
    run_id: str
    status: Literal["success", "partial", "error"]
    execution_report: Optional[ExecutionReport] = None
    error: Optional[str] = None

class TrainWithPlanResponse(BaseModel):
    run_id: str
    status: Literal["success", "error"]
    training_result: Optional[TrainingResult] = None
    error: Optional[str] = None

class ReportResponse(BaseModel):
    run_id: str
    status: Literal["success", "not_found", "error"]
    report: Optional[FinalUserReport] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────
# CLEANING REPORT SCHEMA
# ─────────────────────────────────────────────

class CleaningReportSchema(BaseModel):
    dataset_shape_before: List[int]
    dataset_shape_after: List[int]
    errors_detected: List[str] = []
    cleaning_actions_applied: List[str] = []
    warnings: List[str] = []
    columns_dropped: List[str] = []
    columns_converted: List[str] = []
    duplicates_removed: int = 0
    nulls_filled: Dict[str, int] = {}
    outliers_clipped: List[str] = []
    impossible_values_fixed: List[str] = []
    leakage_suspects: List[str] = []

    @property
    def rows_removed(self) -> int:
        return self.dataset_shape_before[0] - self.dataset_shape_after[0]

    @property
    def cols_removed(self) -> int:
        return self.dataset_shape_before[1] - self.dataset_shape_after[1]


class RobustUploadResponse(BaseModel):
    status: str
    run_id: str
    filename: str
    cleaning_report: CleaningReportSchema
    dataset_info: Dict[str, Any]
    summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AutoMLErrorResponse(BaseModel):
    status: str = "error"
    run_id: Optional[str] = None
    step: str
    error: str
    errors_detected: List[str] = []
    warnings: List[str] = []
    suggestion: Optional[str] = None