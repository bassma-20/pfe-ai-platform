"""
scorer.py — Système de scoring de qualité du code Java et Python
Score de 0 à 100 basé sur les problèmes détectés par l'analyseur statique.
"""


# ─────────────────────────────────────────────────────────────────────────────
# POIDS PAR SÉVÉRITÉ
# ─────────────────────────────────────────────────────────────────────────────

SEVERITY_WEIGHTS = {
    "critical": 15,   # -15 pts par problème critique
    "high":     8,    # -8  pts par problème majeur
    "medium":   4,    # -4  pts par problème moyen
    "low":      2,    # -2  pts par problème mineur
}

# ─────────────────────────────────────────────────────────────────────────────
# BONUS — Java (bonnes pratiques modernes)
# ─────────────────────────────────────────────────────────────────────────────

BONUS_METRICS_JAVA = {
    "has_lambda":   +5,
    "has_streams":  +5,
    "has_optional": +3,
    "has_generics": +3,
    "has_records":  +5,
}

# ─────────────────────────────────────────────────────────────────────────────
# BONUS — Python (fonctionnalités modernes Python 3)
# ─────────────────────────────────────────────────────────────────────────────

BONUS_METRICS_PYTHON = {
    # ── Typage & style Python 3 ────────────────────────────────────────────
    "has_type_hints":       +8,   # def f(x: int) -> str — code typé
    "has_fstrings":         +5,   # f"..." — style moderne
    "has_dataclasses":      +4,   # @dataclass
    "has_async":            +4,   # async/await
    "has_match":            +5,   # match/case (Python 3.10+)
    "has_walrus":           +3,   # := (Python 3.8+)
    # ── Bonnes pratiques de migration ─────────────────────────────────────
    "has_logging":          +5,   # import logging — print() remplacés
    "has_context_managers": +4,   # with open() — ressources bien gérées
    "has_is_none":          +3,   # is None / is not None — comparaisons correctes
}


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE DE SCORING
# ─────────────────────────────────────────────────────────────────────────────

def compute_score(analysis: dict) -> dict:
    """
    Calcule le score de qualité à partir du résultat de analyze_java_code()
    ou analyze_python_code().
    Retourne un dict complet avec score, grade, risk_level et breakdown.
    """
    issues_by_severity = analysis.get("issues_by_severity", {})
    metrics            = analysis.get("metrics", {})
    issues             = analysis.get("issues", [])

    # Détecte si c'est du Python (présence de métriques Python-spécifiques)
    is_python = "has_type_hints" in metrics or "has_fstrings" in metrics
    bonus_table = BONUS_METRICS_PYTHON if is_python else BONUS_METRICS_JAVA

    # ── Calcul des pénalités ──
    penalty = 0
    breakdown_penalties = {}
    for severity, count in issues_by_severity.items():
        weight = SEVERITY_WEIGHTS.get(severity, 0)
        pts    = count * weight
        penalty += pts
        if pts > 0:
            breakdown_penalties[severity] = {
                "count":       count,
                "weight":      weight,
                "points_lost": pts,
            }

    # ── Calcul des bonus ──
    bonus = 0
    breakdown_bonuses = {}
    for metric, pts in bonus_table.items():
        if metrics.get(metric):
            bonus += pts
            breakdown_bonuses[metric] = pts

    # ── Score final (borné entre 0 et 100) ──
    raw_score = 100 - penalty + bonus
    score     = max(0, min(100, raw_score))

    return {
        "score":        score,
        "grade":        _score_to_grade(score),
        "risk_level":   _score_to_risk(score),
        "issues_count": analysis.get("issues_count", 0),
        "penalty":      penalty,
        "bonus":        bonus,
        "breakdown": {
            "penalties": breakdown_penalties,
            "bonuses":   breakdown_bonuses,
            "top_issues": [
                {"title": i["title"], "severity": i["severity"], "line": i["line"]}
                for i in sorted(issues, key=lambda x: SEVERITY_WEIGHTS.get(x["severity"], 0), reverse=True)[:5]
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# CALCUL DE L'AMÉLIORATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_improvement(score_before: dict, score_after: dict) -> dict:
    """
    Compare les deux scores et retourne les métriques d'amélioration.
    """
    delta       = score_after["score"] - score_before["score"]
    delta_issues = score_before["issues_count"] - score_after["issues_count"]

    return {
        "score_delta":   delta,
        "label":         f"+{delta} points" if delta >= 0 else f"{delta} points",
        "issues_fixed":  max(0, delta_issues),
        "issues_added":  max(0, -delta_issues),
        "grade_before":  score_before["grade"],
        "grade_after":   score_after["grade"],
        "risk_before":   score_before["risk_level"],
        "risk_after":    score_after["risk_level"],
        "improved":      delta > 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _score_to_grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 40: return "D"
    return "F"

def _score_to_risk(score: int) -> str:
    if score >= 80: return "low"
    if score >= 60: return "medium"
    if score >= 40: return "high"
    return "critical"
