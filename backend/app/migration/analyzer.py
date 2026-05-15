"""
analyzer.py — Analyse statique du code Java (sans AST, sans LLM)
Détecte les patterns obsolètes, les mauvaises pratiques et les anti-patterns.
"""

import re
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE DE PROBLÈME
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Issue:
    code:        str   # identifiant ex: "J001"
    category:    str   # ex: "Collections obsolètes"
    title:       str   # ex: "Utilisation de Vector"
    description: str   # ex: "Vector est thread-safe mais lent, préférer ArrayList"
    severity:    str   # "low" | "medium" | "high" | "critical"
    line:        int   # numéro de ligne (0 si non détecté)
    suggestion:  str   # correction recommandée


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLES DE DÉTECTION
# ─────────────────────────────────────────────────────────────────────────────

RULES = [

    # ── Collections obsolètes ──────────────────────────────────────────────
    {
        "code":        "J001",
        "category":    "Collections obsolètes",
        "pattern":     r"\bVector\b",
        "title":       "Utilisation de Vector",
        "description": "Vector est synchronisé par défaut, lent et obsolète depuis Java 2.",
        "severity":    "high",
        "suggestion":  "Remplacer par ArrayList<T> ou CopyOnWriteArrayList si thread-safety requise.",
    },
    {
        "code":        "J002",
        "category":    "Collections obsolètes",
        "pattern":     r"\bHashtable\b",
        "title":       "Utilisation de Hashtable",
        "description": "Hashtable est obsolète, remplacé par HashMap ou ConcurrentHashMap.",
        "severity":    "high",
        "suggestion":  "Remplacer par HashMap<K,V> ou ConcurrentHashMap si accès concurrent.",
    },
    {
        "code":        "J003",
        "category":    "Collections obsolètes",
        "pattern":     r"\bStack\b",
        "title":       "Utilisation de Stack",
        "description": "Stack hérite de Vector (obsolète). Préférer Deque.",
        "severity":    "medium",
        "suggestion":  "Remplacer par ArrayDeque<T> utilisée comme pile.",
    },

    # ── Manipulation de chaînes ────────────────────────────────────────────
    {
        "code":        "J004",
        "category":    "Performance chaînes",
        "pattern":     r"\bStringBuffer\b",
        "title":       "Utilisation de StringBuffer",
        "description": "StringBuffer est synchronisé (lent). StringBuilder est suffisant en mono-thread.",
        "severity":    "medium",
        "suggestion":  "Remplacer par StringBuilder sauf si accès multi-thread nécessaire.",
    },
    {
        "code":        "J005",
        "category":    "Performance chaînes",
        "pattern":     r"for\s*\([^)]+\)\s*\{[^}]*\+=\s*[\"']",
        "title":       "Concaténation String dans une boucle",
        "description": "La concaténation avec += dans une boucle crée de nombreux objets temporaires.",
        "severity":    "high",
        "suggestion":  "Utiliser StringBuilder.append() dans la boucle, puis toString().",
    },

    # ── Gestion des dates ──────────────────────────────────────────────────
    {
        "code":        "J006",
        "category":    "API Date obsolète",
        "pattern":     r"\bnew\s+Date\s*\(",
        "title":       "Utilisation de java.util.Date",
        "description": "java.util.Date est mutable, mal conçu et déprécié pour la plupart des usages.",
        "severity":    "high",
        "suggestion":  "Remplacer par LocalDate, LocalDateTime ou ZonedDateTime (java.time).",
    },
    {
        "code":        "J007",
        "category":    "API Date obsolète",
        "pattern":     r"\bCalendar\.getInstance\(\)",
        "title":       "Utilisation de Calendar",
        "description": "Calendar est verbeux et difficile à utiliser correctement.",
        "severity":    "medium",
        "suggestion":  "Remplacer par java.time.LocalDateTime ou ZonedDateTime.",
    },

    # ── Gestion des exceptions ─────────────────────────────────────────────
    {
        "code":        "J008",
        "category":    "Mauvaise gestion des exceptions",
        "pattern":     r"e\.printStackTrace\(\)",
        "title":       "Utilisation de printStackTrace()",
        "description": "printStackTrace() écrit sur stderr sans contrôle. Non utilisable en production.",
        "severity":    "high",
        "suggestion":  "Utiliser un logger : logger.error(\"message\", e)",
    },
    {
        "code":        "J009",
        "category":    "Mauvaise gestion des exceptions",
        "pattern":     r"catch\s*\(\s*Exception\s+\w+\s*\)",
        "title":       "Catch Exception générique",
        "description": "Attraper Exception masque les erreurs spécifiques et rend le débogage difficile.",
        "severity":    "high",
        "suggestion":  "Attraper les exceptions spécifiques (IOException, SQLException, etc.).",
    },
    {
        "code":        "J010",
        "category":    "Mauvaise gestion des exceptions",
        "pattern":     r"catch\s*\(\s*Throwable\s+\w+\s*\)",
        "title":       "Catch Throwable",
        "description": "Attraper Throwable inclut les erreurs JVM (OutOfMemoryError, etc.).",
        "severity":    "critical",
        "suggestion":  "N'attraper que les exceptions applicatives, pas Throwable.",
    },

    # ── API dépréciées / dangereuses ───────────────────────────────────────
    {
        "code":        "J011",
        "category":    "API dangereuse",
        "pattern":     r"\.stop\s*\(\s*\)",
        "title":       "Utilisation de Thread.stop()",
        "description": "Thread.stop() est déprécié depuis Java 1.2 — peut corrompre l'état de l'application.",
        "severity":    "critical",
        "suggestion":  "Utiliser un flag volatile boolean ou Thread.interrupt().",
    },
    {
        "code":        "J012",
        "category":    "API dangereuse",
        "pattern":     r"\.suspend\s*\(\s*\)|\.resume\s*\(\s*\)",
        "title":       "Utilisation de Thread.suspend()/resume()",
        "description": "Thread.suspend() et resume() sont dépréciés — risque de deadlock.",
        "severity":    "critical",
        "suggestion":  "Utiliser des mécanismes de synchronisation modernes (wait/notify, Lock).",
    },

    # ── Logging ────────────────────────────────────────────────────────────
    {
        "code":        "J013",
        "category":    "Logging inadapté",
        "pattern":     r"System\.out\.print(ln)?\s*\(",
        "title":       "System.out.println() comme logging",
        "description": "System.out.println est synchronisé, non configurable et non désactivable en prod.",
        "severity":    "medium",
        "suggestion":  "Utiliser un framework de logging : SLF4J + Logback ou java.util.logging.",
    },
    {
        "code":        "J014",
        "category":    "Logging inadapté",
        "pattern":     r"System\.err\.print(ln)?\s*\(",
        "title":       "System.err.println() comme logging",
        "description": "System.err non contrôlé en production.",
        "severity":    "medium",
        "suggestion":  "Utiliser logger.error() à la place.",
    },

    # ── Types génériques ───────────────────────────────────────────────────
    {
        "code":        "J015",
        "category":    "Raw types",
        "pattern":     r"\b(List|Map|Set|Collection|ArrayList|HashMap|HashSet)\s+\w+\s*=\s*new\s+(ArrayList|HashMap|HashSet|LinkedList)\s*\(\s*\)",
        "title":       "Raw type sans generics",
        "description": "L'absence de generics empêche la vérification de types à la compilation.",
        "severity":    "medium",
        "suggestion":  "Ajouter les paramètres de type : List<String>, Map<String, Integer>, etc.",
    },

    # ── Comparaison de chaînes ─────────────────────────────────────────────
    {
        "code":        "J016",
        "category":    "Comparaison incorrecte",
        "pattern":     r'==\s*"[^"]*"|"[^"]*"\s*==',
        "title":       "Comparaison de String avec ==",
        "description": "L'opérateur == compare les références, pas le contenu des chaînes.",
        "severity":    "high",
        "suggestion":  "Utiliser .equals() ou Objects.equals() pour comparer le contenu.",
    },

    # ── Null checks ────────────────────────────────────────────────────────
    {
        "code":        "J017",
        "category":    "Null safety",
        "pattern":     r"if\s*\(\s*\w+\s*!=\s*null\s*\)",
        "title":       "Null check manuel répété",
        "description": "Les null checks manuels sont verbeux et sources de NullPointerException.",
        "severity":    "low",
        "suggestion":  "Utiliser Optional<T> pour représenter les valeurs potentiellement nulles.",
    },

    # ── Finalize ───────────────────────────────────────────────────────────
    {
        "code":        "J018",
        "category":    "API dépréciée",
        "pattern":     r"protected\s+void\s+finalize\s*\(\s*\)",
        "title":       "Utilisation de finalize()",
        "description": "finalize() est déprécié depuis Java 9 et supprimé en Java 18.",
        "severity":    "critical",
        "suggestion":  "Utiliser try-with-resources ou Cleaner (Java 9+).",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE D'ANALYSE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_java_code(code: str) -> dict:
    """
    Analyse statique complète d'un fichier Java.
    Retourne toutes les métriques et problèmes détectés.
    """
    lines        = code.splitlines()
    issues       = _detect_issues(code, lines)
    metrics      = _compute_metrics(code, lines)
    version_est  = _estimate_java_version(code)

    return {
        "estimated_java_version": version_est,
        "metrics":                metrics,
        "issues":                 [_issue_to_dict(i) for i in issues],
        "issues_count":           len(issues),
        "issues_by_severity":     _group_by_severity(issues),
        "issues_by_category":     _group_by_category(issues),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DÉTECTION DES PROBLÈMES
# ─────────────────────────────────────────────────────────────────────────────

def _detect_issues(code: str, lines: list[str]) -> list[Issue]:
    issues = []
    for rule in RULES:
        for match in re.finditer(rule["pattern"], code):
            line_num = code[:match.start()].count("\n") + 1
            issues.append(Issue(
                code        = rule["code"],
                category    = rule["category"],
                title       = rule["title"],
                description = rule["description"],
                severity    = rule["severity"],
                line        = line_num,
                suggestion  = rule["suggestion"],
            ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# MÉTRIQUES GÉNÉRALES
# ─────────────────────────────────────────────────────────────────────────────

def _compute_metrics(code: str, lines: list[str]) -> dict:
    non_empty = [l for l in lines if l.strip() and not l.strip().startswith("//")]
    return {
        "total_lines":        len(lines),
        "code_lines":         len(non_empty),
        "comment_lines":      len([l for l in lines if l.strip().startswith("//") or l.strip().startswith("*")]),
        "class_count":        len(re.findall(r"\bclass\s+\w+", code)),
        "method_count":       len(re.findall(r"(public|private|protected)\s+\w[\w<>\[\]]*\s+\w+\s*\(", code)),
        "import_count":       len(re.findall(r"^import\s+", code, re.MULTILINE)),
        "try_catch_count":    len(re.findall(r"\btry\s*\{", code)),
        "for_loop_count":     len(re.findall(r"\bfor\s*\(", code)),
        "null_checks":        len(re.findall(r"!=\s*null|==\s*null", code)),
        "has_generics":       bool(re.search(r"<\w+>", code)),
        "has_lambda":         bool(re.search(r"->", code)),
        "has_streams":        bool(re.search(r"\.stream\(\)", code)),
        "has_optional":       bool(re.search(r"\bOptional\b", code)),
        "has_records":        bool(re.search(r"\brecord\s+\w+", code)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ESTIMATION DE LA VERSION JAVA SOURCE
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_java_version(code: str) -> str:
    if re.search(r"\brecord\s+\w+|sealed\s+class|instanceof\s+\w+\s+\w+", code):
        return "Java 16–17+"
    if re.search(r"\bvar\s+\w+\s*=|\"\"\"", code):
        return "Java 10–15"
    if re.search(r"->|Stream\.|Optional\.|LocalDate|LocalDateTime", code):
        return "Java 8–9"
    if re.search(r"\bVector\b|\bHashtable\b|\bnew\s+Date\(", code):
        return "Java 4–7 (legacy)"
    return "Java 5–7"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _issue_to_dict(issue: Issue) -> dict:
    return {
        "code":        issue.code,
        "category":    issue.category,
        "title":       issue.title,
        "description": issue.description,
        "severity":    issue.severity,
        "line":        issue.line,
        "suggestion":  issue.suggestion,
    }

def _group_by_severity(issues: list[Issue]) -> dict:
    groups = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for i in issues:
        groups[i.severity] = groups.get(i.severity, 0) + 1
    return groups

def _group_by_category(issues: list[Issue]) -> dict:
    groups = {}
    for i in issues:
        groups[i.category] = groups.get(i.category, 0) + 1
    return groups
