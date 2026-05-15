"""
automl/service/agent_service.py — Agent ReAct avec OpenAI Function Calling.

Pattern ReAct (Reasoning + Acting) :
  Thought → Action (tool call) → Observation → Thought → …

L'agent dispose de 6 outils spécialisés pour piloter le pipeline AutoML.
Il raisonne à chaque étape, appelle l'outil approprié, observe le résultat,
et itère jusqu'à obtenir un pipeline complet et validé.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DÉFINITION DES OUTILS (OpenAI Function Calling schema)
# ─────────────────────────────────────────────────────────────────────────────

AUTOML_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze_dataset",
            "description": (
                "Analyse le dataset uploadé et retourne un résumé détaillé : "
                "statistiques par colonne, valeurs manquantes, outliers, distribution de la cible. "
                "Appelle cet outil EN PREMIER pour comprendre les données."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Identifiant unique du run AutoML",
                    }
                },
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decide_plan",
            "description": (
                "Génère un plan de décision complet : actions de nettoyage, "
                "transformations de features, et modèles à tester. "
                "Appelle cet outil APRÈS analyze_dataset."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Identifiant unique du run AutoML",
                    },
                    "target_column": {
                        "type": "string",
                        "description": "Nom de la colonne cible à prédire",
                    },
                    "problem_type": {
                        "type": "string",
                        "enum": ["binary_classification", "multiclass_classification", "regression"],
                        "description": "Type de problème ML",
                    },
                },
                "required": ["run_id", "target_column", "problem_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_cleaning",
            "description": (
                "Exécute les actions de nettoyage et de feature engineering définies dans le plan. "
                "Appelle cet outil APRÈS decide_plan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Identifiant unique du run AutoML",
                    }
                },
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "train_models",
            "description": (
                "Entraîne tous les modèles définis dans le plan avec optimisation Optuna. "
                "Sélectionne automatiquement le meilleur. "
                "Appelle cet outil APRÈS apply_cleaning."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Identifiant unique du run AutoML",
                    },
                    "test_size": {
                        "type": "number",
                        "description": "Proportion du jeu de test (entre 0.1 et 0.4, défaut 0.2)",
                    },
                },
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_results",
            "description": (
                "Récupère les résultats d'entraînement : métriques, feature importance, "
                "comparaison des modèles. Appelle cet outil APRÈS train_models."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Identifiant unique du run AutoML",
                    }
                },
                "required": ["run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize",
            "description": (
                "Finalise le pipeline et génère le rapport. "
                "Appelle cet outil EN DERNIER, une fois que tu as analysé, nettoyé, "
                "entraîné et évalué. Fournis une conclusion claire."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Identifiant unique du run AutoML",
                    },
                    "conclusion": {
                        "type": "string",
                        "description": "Résumé final de l'agent : meilleur modèle, performance, recommandations",
                    },
                },
                "required": ["run_id", "conclusion"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# EXÉCUTEUR D'OUTILS
# ─────────────────────────────────────────────────────────────────────────────

class AutoMLToolExecutor:
    """Exécute les outils appelés par l'agent ReAct."""

    def __init__(self, run_store: Dict[str, Any], data_dir: str):
        self._store = run_store
        self._data_dir = data_dir

    def _get_run(self, run_id: str) -> Dict[str, Any]:
        if run_id not in self._store:
            raise ValueError(f"run_id '{run_id}' introuvable.")
        return self._store[run_id]

    def analyze_dataset(self, run_id: str) -> Dict[str, Any]:
        from app.automl.service.llm_service import build_dataset_summary

        run = self._get_run(run_id)
        df = run["df_current"]
        summary = run.get("summary")

        if summary is None:
            summary = build_dataset_summary(df, run_id)
            self._store[run_id]["summary"] = summary

        import numpy as np

        col_info = []
        for c in summary.columns[:20]:
            series = df[c.name] if c.name in df.columns else None
            extra = {}
            if series is not None and c.is_numeric:
                s = series.dropna()
                if len(s) > 0:
                    extra["min"]  = round(float(s.min()), 4)
                    extra["max"]  = round(float(s.max()), 4)
                    extra["mean"] = round(float(s.mean()), 4)
                    # Nombre exact d'outliers IQR
                    Q1, Q3 = s.quantile(0.25), s.quantile(0.75)
                    IQR = Q3 - Q1
                    n_out = int(((s < Q1 - 1.5 * IQR) | (s > Q3 + 1.5 * IQR)).sum())
                    extra["n_outliers"] = n_out
                    extra["iqr_lower"]  = round(float(Q1 - 1.5 * IQR), 4)
                    extra["iqr_upper"]  = round(float(Q3 + 1.5 * IQR), 4)
            elif series is not None and not c.is_numeric:
                counts = series.dropna().value_counts().head(5)
                extra["top_values"] = [
                    {"value": str(k), "count": int(v)}
                    for k, v in counts.items()
                ]

            col_info.append({
                "name": c.name,
                "dtype": c.dtype,
                "null_pct": c.null_pct,
                "null_count": c.null_count,
                "unique": c.unique_count,
                "is_numeric": c.is_numeric,
                "has_outliers": c.has_outliers_iqr,
                "skewness": c.skewness,
                "missing_type": c.missing_type,
                "sample_values": [str(v) for v in (c.sample_values or [])[:3]],
                **extra,
            })

        return {
            "shape": [summary.n_rows, summary.n_cols],
            "columns": col_info,
            "total_null_pct": summary.total_null_pct,
            "duplicate_rows": summary.duplicate_rows,
            "class_balance": summary.class_balance,
            "problem_type": summary.problem_type.value if summary.problem_type else None,
            "target_column": summary.target_column,
            "suggested_target": summary.suggested_target,
        }

    def decide_plan(
        self,
        run_id: str,
        target_column: str,
        problem_type: str,
    ) -> Dict[str, Any]:
        from app.automl.models.schemas import ProblemType
        from app.automl.service.llm_service import generate_decision_plan, generate_fallback_plan
        from app.automl.service.action_executor_service import validate_plan_against_df

        run = self._get_run(run_id)
        summary = run.get("summary")
        if summary is None:
            raise ValueError("analyze_dataset doit être appelé en premier.")

        summary.target_column = target_column
        try:
            summary.problem_type = ProblemType(problem_type)
        except ValueError:
            pass

        try:
            plan = generate_decision_plan(summary=summary)
            source = "llm"
        except Exception as e:
            logger.warning(f"[Agent] LLM plan échoué ({e}) — fallback")
            plan = generate_fallback_plan(summary)
            source = "fallback"

        warnings = validate_plan_against_df(run["df_current"], plan)
        if warnings:
            plan.data_warnings.extend(warnings)

        self._store[run_id]["plan"] = plan
        self._store[run_id]["summary"] = summary

        def _serialize_action(a):
            d = {"action": a.action.value if hasattr(a.action, "value") else str(a.action)}
            for field in ("column", "columns", "new_feature", "col1", "col2"):
                val = getattr(a, field, None)
                if val is not None:
                    d[field] = val
            d["reason"] = getattr(a, "reason", None)
            return d

        return {
            "plan_source": source,
            "target_column": plan.target_column,
            "problem_type": plan.problem_type.value,
            "confidence": plan.confidence,
            "reasoning_summary": plan.reasoning_summary,
            "cleaning_actions": len(plan.cleaning_actions),
            "feature_actions": len(plan.feature_actions),
            "cleaning_actions_detail": [_serialize_action(a) for a in plan.cleaning_actions],
            "feature_actions_detail": [_serialize_action(a) for a in plan.feature_actions],
            "models_to_try": [m.value for m in plan.model_plan.models_to_try],
            "model_reason": plan.model_plan.reason,
            "primary_metric": plan.model_plan.primary_metric,
            "use_optuna": plan.model_plan.use_optuna,
            "optuna_trials": plan.model_plan.trials,
            "cv_folds": plan.model_plan.cv_folds,
            "data_warnings": plan.data_warnings[:5],
        }

    def apply_cleaning(self, run_id: str) -> Dict[str, Any]:
        from app.automl.service.action_executor_service import execute_plan

        run = self._get_run(run_id)
        if run.get("plan") is None:
            raise ValueError("decide_plan doit être appelé en premier.")

        df = run["df_current"].copy()
        df_cleaned, exec_report = execute_plan(df=df, plan=run["plan"])

        self._store[run_id]["df_current"] = df_cleaned
        self._store[run_id]["execution_report"] = exec_report

        return {
            "shape_before": list(run["df_current"].shape),
            "shape_after": list(df_cleaned.shape),
            "successful_actions": exec_report.successful,
            "failed_actions": exec_report.errors,
            "skipped_actions": exec_report.skipped,
            "rows_removed": run["df_current"].shape[0] - df_cleaned.shape[0],
            "cols_removed": run["df_current"].shape[1] - df_cleaned.shape[1],
            "actions_detail": [
                {
                    "action": r.action,
                    "column": r.column,
                    "status": r.status,
                    "message": r.message,
                    "rows_affected": r.rows_affected,
                }
                for r in exec_report.results
            ],
        }

    def train_models(self, run_id: str, test_size: float = 0.2) -> Dict[str, Any]:
        from app.automl.service.training_service import train_with_plan
        from app.automl.service.data_service import validate_for_training

        run = self._get_run(run_id)
        if run.get("plan") is None:
            raise ValueError("decide_plan doit être appelé en premier.")

        plan = run["plan"]
        df = run["df_current"]

        errors = validate_for_training(df, plan.target_column)
        if errors:
            raise ValueError(f"Dataset non entraînable : {errors}")

        training_result = train_with_plan(
            df=df,
            plan=plan,
            data_dir=self._data_dir,
            test_size=min(max(test_size, 0.1), 0.4),
            save_model=True,
        )
        self._store[run_id]["training_result"] = training_result

        return {
            "best_model": training_result.best_model,
            "best_metrics": training_result.best_metrics,
            "models_evaluated": len(training_result.models_evaluated),
            "top_features": list((training_result.feature_importance or {}).keys())[:5],
        }

    def evaluate_results(self, run_id: str) -> Dict[str, Any]:
        run = self._get_run(run_id)
        tr = run.get("training_result")
        if tr is None:
            raise ValueError("train_models doit être appelé en premier.")

        models_comparison = [
            {
                "model": m.model_name,
                "metrics": m.metrics,
                "cv_mean": m.cv_mean,
                "cv_std": m.cv_std,
                "training_time_s": m.training_time_seconds,
            }
            for m in tr.models_evaluated
        ]

        return {
            "best_model": tr.best_model,
            "best_metrics": tr.best_metrics,
            "feature_importance": dict(list((tr.feature_importance or {}).items())[:10]),
            "models_comparison": models_comparison,
            "problem_type": tr.problem_type.value,
        }

    def finalize(self, run_id: str, conclusion: str) -> Dict[str, Any]:
        from app.agent.memory import get_memory

        run = self._get_run(run_id)
        tr = run.get("training_result")
        plan = run.get("plan")

        if tr and plan:
            memory = get_memory()
            best_metric_val = list(tr.best_metrics.values())[0] if tr.best_metrics else 0.0
            memory.remember_automl(
                problem_type  = plan.problem_type.value,
                n_rows        = run["summary"].n_rows if run.get("summary") else 0,
                n_features    = run["summary"].n_cols if run.get("summary") else 0,
                best_model    = tr.best_model,
                best_metric   = float(best_metric_val),
                metric_name   = plan.model_plan.primary_metric,
                dataset_hints = plan.data_warnings[:3],
            )

        return {
            "status": "completed",
            "conclusion": conclusion,
            "best_model": tr.best_model if tr else None,
            "best_metrics": tr.best_metrics if tr else {},
        }

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Dispatch l'appel d'outil et retourne le résultat en JSON string."""
        try:
            if tool_name == "analyze_dataset":
                result = self.analyze_dataset(**args)
            elif tool_name == "decide_plan":
                result = self.decide_plan(**args)
            elif tool_name == "apply_cleaning":
                result = self.apply_cleaning(**args)
            elif tool_name == "train_models":
                result = self.train_models(**args)
            elif tool_name == "evaluate_results":
                result = self.evaluate_results(**args)
            elif tool_name == "finalize":
                result = self.finalize(**args)
            else:
                result = {"error": f"Outil inconnu : {tool_name}"}
        except Exception as e:
            result = {"error": str(e)}

        return json.dumps(result, ensure_ascii=False, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# AGENT REACT
# ─────────────────────────────────────────────────────────────────────────────

async def run_automl_agent(
    run_id: str,
    run_store: Dict[str, Any],
    data_dir: str,
    target_column: Optional[str] = None,
    problem_type: Optional[str] = None,
    max_steps: int = 10,
) -> Dict[str, Any]:
    """
    Agent ReAct pour AutoML.

    Boucle Thought → Action → Observation jusqu'à appel de `finalize`.
    Retourne le résultat complet avec trace de raisonnement.
    """
    from openai import AsyncOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY manquante dans .env"
        )

    client   = AsyncOpenAI(api_key=api_key)
    model    = os.getenv("OPENAI_MODEL", "gpt-4o")
    executor = AutoMLToolExecutor(run_store, data_dir)

    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run_id '{run_id}' introuvable.")

    summary = run.get("summary")
    shape = f"{run['df_current'].shape[0]} lignes × {run['df_current'].shape[1]} colonnes"
    cols  = list(run["df_current"].columns)

    # Contexte mémoire AutoML
    from app.agent.memory import get_memory
    memory = get_memory()
    past = memory.recall_automl(
        problem_type  = problem_type or "binary_classification",
        n_rows        = run["df_current"].shape[0],
        n_features    = run["df_current"].shape[1],
    )
    memory_ctx = memory.format_automl_context(past)

    system_prompt = f"""Tu es un agent AutoML expert qui pilote un pipeline de machine learning.
Tu utilises le pattern ReAct : Raisonne (Thought) puis Agis (Action = appel d'outil).

CONTEXTE :
- run_id : {run_id}
- Dataset : {shape}
- Colonnes disponibles : {cols}
- Colonne cible suggérée : {target_column or "non spécifiée"}
- Type de problème suggéré : {problem_type or "à déterminer"}

EXPÉRIENCES PASSÉES :
{memory_ctx}

RÈGLES :
1. Commence TOUJOURS par analyze_dataset pour comprendre les données.
2. Appelle decide_plan avec la target et le type de problème.
3. Applique le nettoyage avec apply_cleaning.
4. Entraîne les modèles avec train_models.
5. Évalue les résultats avec evaluate_results.
6. Termine OBLIGATOIREMENT avec finalize (conclusion claire et actionnable).
7. Ne saute aucune étape.
8. Maximum {max_steps} appels d'outils au total.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Lance le pipeline AutoML complet pour le run_id='{run_id}'. "
                f"{'Colonne cible : ' + target_column if target_column else 'Détermine la colonne cible.'} "
                f"{'Problème : ' + problem_type if problem_type else ''}"
            ),
        },
    ]

    react_trace: List[Dict[str, Any]] = []
    step = 0
    final_result: Optional[Dict[str, Any]] = None

    while step < max_steps:
        step += 1

        response = await client.chat.completions.create(
            model       = model,
            messages    = messages,
            tools       = AUTOML_TOOLS,
            tool_choice = "auto",
            temperature = 0.1,
            max_tokens  = 1024,
        )

        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        # Thought (texte avant un éventuel tool call)
        thought = msg.content or ""

        # Pas d'outil appelé → l'agent a terminé par texte
        if not msg.tool_calls:
            react_trace.append({
                "step":   step,
                "type":   "final_thought",
                "thought": thought,
            })
            break

        # Pour chaque appel d'outil dans ce turn
        messages.append({"role": "assistant", "content": thought, "tool_calls": [
            {
                "id":       tc.id,
                "type":     "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]})

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            observation = executor.execute(tool_name, args)
            obs_data    = json.loads(observation)

            react_trace.append({
                "step":        step,
                "type":        "action",
                "thought":     thought,
                "tool":        tool_name,
                "args":        args,
                "observation": obs_data,
            })

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "content":      observation,
            })

            # Fin détectée via finalize
            if tool_name == "finalize" and "error" not in obs_data:
                final_result = obs_data
                break

        if final_result is not None:
            break

    # ── Résultat final ────────────────────────────────────────────────────────
    run_after = run_store.get(run_id, {})
    tr = run_after.get("training_result")

    return {
        "run_id":  run_id,
        "status":  "completed" if final_result else "max_steps_reached",
        "agent_trace": {
            "mode":        "react",
            "total_steps": step,
            "max_steps":   max_steps,
            "memory_used": len(past) > 0,
            "steps":       react_trace,
        },
        "best_model":        final_result.get("best_model") if final_result else (tr.best_model if tr else None),
        "best_metrics":      final_result.get("best_metrics") if final_result else (tr.best_metrics if tr else {}),
        "conclusion":        final_result.get("conclusion") if final_result else "Max étapes atteint.",
        "training_result":   tr.model_dump() if tr else None,
        "execution_report":  run_after.get("execution_report").model_dump() if run_after.get("execution_report") else None,
        "plan":              run_after.get("plan").model_dump() if run_after.get("plan") else None,
    }
