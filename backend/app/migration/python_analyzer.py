"""
python_analyzer.py — Analyse statique du code Python (sans AST, sans LLM)
Détecte les patterns obsolètes, les mauvaises pratiques et les anti-patterns.
"""

import re
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# MODÈLE DE PROBLÈME
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Issue:
    code:        str
    category:    str
    title:       str
    description: str
    severity:    str
    line:        int
    suggestion:  str


# ─────────────────────────────────────────────────────────────────────────────
# RÈGLES DE DÉTECTION
# ─────────────────────────────────────────────────────────────────────────────

RULES = [

    # ── Logging ───────────────────────────────────────────────────────────────
    {
        "code":        "P001",
        "category":    "Logging inadapté",
        "pattern":     r"\bprint\s*\(",
        "title":       "print() comme logging",
        "description": "print() n'est pas configurable, pas désactivable en production.",
        "severity":    "medium",
        "suggestion":  "Utiliser le module logging : logging.info(), logging.debug(), logging.error().",
    },

    # ── Exceptions ────────────────────────────────────────────────────────────
    {
        "code":        "P002",
        "category":    "Mauvaise gestion des exceptions",
        "pattern":     r"except\s*:",
        "title":       "Bare except clause",
        "description": "except: attrape tout y compris KeyboardInterrupt et SystemExit.",
        "severity":    "high",
        "suggestion":  "Attraper les exceptions spécifiques : except ValueError: ou except (IOError, OSError):",
    },
    {
        "code":        "P003",
        "category":    "Mauvaise gestion des exceptions",
        "pattern":     r"except\s+Exception\s*(?:as\s+\w+)?\s*:",
        "title":       "Catch Exception générique",
        "description": "Attraper Exception masque les erreurs spécifiques et rend le débogage difficile.",
        "severity":    "medium",
        "suggestion":  "Attraper les exceptions spécifiques attendues (ValueError, TypeError, etc.).",
    },
    {
        "code":        "P004",
        "category":    "Mauvaise gestion des exceptions",
        "pattern":     r"except\s+\w[\w\s,]*:\s*\n\s*pass\b",
        "title":       "Exception silencieuse (pass)",
        "description": "Avaler une exception sans la loguer masque les erreurs en production.",
        "severity":    "high",
        "suggestion":  "Au minimum loguer l'exception : logging.exception('message') ou raise.",
    },

    # ── Comparaisons ─────────────────────────────────────────────────────────
    {
        "code":        "P005",
        "category":    "Comparaison incorrecte",
        "pattern":     r"==\s*None|None\s*==",
        "title":       "Comparaison avec None via ==",
        "description": "== peut être overridé par __eq__. PEP 8 recommande 'is None'.",
        "severity":    "medium",
        "suggestion":  "Utiliser 'is None' ou 'is not None'.",
    },
    {
        "code":        "P006",
        "category":    "Comparaison incorrecte",
        "pattern":     r"==\s*True\b|True\s*==|==\s*False\b|False\s*==",
        "title":       "Comparaison explicite avec True/False",
        "description": "Comparer avec True/False est redondant et non pythonique (PEP 8).",
        "severity":    "low",
        "suggestion":  "Utiliser directement la condition : if x: ou if not x:",
    },

    # ── Arguments mutables ────────────────────────────────────────────────────
    {
        "code":        "P007",
        "category":    "Anti-pattern Python",
        "pattern":     r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|\(\))",
        "title":       "Argument par défaut mutable",
        "description": "Les listes/dicts comme valeur par défaut sont partagés entre tous les appels.",
        "severity":    "high",
        "suggestion":  "Utiliser None comme défaut : def f(x=None):  if x is None: x = []",
    },

    # ── Gestion des ressources ────────────────────────────────────────────────
    {
        "code":        "P008",
        "category":    "Gestion des ressources",
        "pattern":     r"(?<!with\s)(?<!with)\b(\w+)\s*=\s*open\s*\(",
        "title":       "open() sans context manager",
        "description": "open() sans 'with' laisse le fichier ouvert si une exception survient.",
        "severity":    "medium",
        "suggestion":  "Utiliser 'with open(...) as f:' pour garantir la fermeture automatique.",
    },

    # ── Type checking ─────────────────────────────────────────────────────────
    {
        "code":        "P009",
        "category":    "Anti-pattern Python",
        "pattern":     r"\btype\s*\(\s*\w+\s*\)\s*==",
        "title":       "type() == pour vérification de type",
        "description": "type() == ne supporte pas l'héritage de classes.",
        "severity":    "medium",
        "suggestion":  "Utiliser isinstance(x, SomeClass) qui supporte l'héritage.",
    },

    # ── Imports ───────────────────────────────────────────────────────────────
    {
        "code":        "P010",
        "category":    "Imports problématiques",
        "pattern":     r"from\s+\w[\w.]*\s+import\s+\*",
        "title":       "Import wildcard (from x import *)",
        "description": "Les imports wildcard polluent le namespace et cachent les dépendances.",
        "severity":    "medium",
        "suggestion":  "Importer explicitement : from module import ClassA, func_b",
    },

    # ── Concaténation ─────────────────────────────────────────────────────────
    {
        "code":        "P011",
        "category":    "Performance chaînes",
        "pattern":     r"for\s+\w+\s+in\s+[^:]+:[^\n]*\n[^\n]*\+=\s*['\"]",
        "title":       "Concaténation de string dans une boucle",
        "description": "L'opérateur += sur les strings crée un nouvel objet à chaque itération (O(n²)).",
        "severity":    "high",
        "suggestion":  "Utiliser une liste + ''.join() : parts = []; parts.append(x); result = ''.join(parts)",
    },

    # ── Formatage ─────────────────────────────────────────────────────────────
    {
        "code":        "P012",
        "category":    "Style moderne",
        "pattern":     r'["\']%[sdf].*["\'].*%\s*[\w(]',
        "title":       "Formatage % (ancien style Python 2)",
        "description": "Le formatage % est hérité de Python 2, moins lisible que les f-strings.",
        "severity":    "low",
        "suggestion":  "Utiliser les f-strings : f'Bonjour {nom}' (Python 3.6+) ou .format()",
    },

    # ── Variables globales ─────────────────────────────────────────────────────
    {
        "code":        "P013",
        "category":    "Anti-pattern Python",
        "pattern":     r"^\s*global\s+\w+",
        "title":       "Utilisation de global",
        "description": "Les variables globales rendent le code difficile à tester et maintenir.",
        "severity":    "medium",
        "suggestion":  "Encapsuler l'état dans une classe ou passer les données en paramètre.",
    },

    # ── Lambda complexe ───────────────────────────────────────────────────────
    {
        "code":        "P014",
        "category":    "Lisibilité",
        "pattern":     r"\blambda\b[^:]+:.{50,}",
        "title":       "Lambda trop complexe",
        "description": "Les lambdas trop longs nuisent à la lisibilité et au débogage.",
        "severity":    "low",
        "suggestion":  "Extraire dans une fonction nommée avec def pour améliorer la lisibilité.",
    },

    # ── exec / eval ───────────────────────────────────────────────────────────
    {
        "code":        "P015",
        "category":    "Sécurité",
        # exec(open( est la forme correcte de execfile() — ne pas flagguer
        # eval( est toujours dangereux
        # exec( suivi de open( = migration de execfile, accepté
        "pattern":     r"\beval\s*\(|\bexec\s*\((?!open\s*\()",
        "title":       "Utilisation de exec() / eval()",
        "description": "exec() et eval() exécutent du code arbitraire — risque de sécurité majeur.",
        "severity":    "critical",
        "suggestion":  "Éviter exec/eval. Si indispensable, valider et assainir l'entrée strictement.",
    },

    # ── Python 2 legacy — imports supprimés en Python 3 ──────────────────────
    {
        "code":        "P016",
        "category":    "Python 2 legacy",
        "pattern":     r"\bimport\s+urllib2\b",
        "title":       "import urllib2 (Python 2 uniquement)",
        "description": "Le module urllib2 a été supprimé en Python 3.",
        "severity":    "critical",
        "suggestion":  "Remplacer par urllib.request et urllib.error (Python 3).",
    },
    {
        "code":        "P017",
        "category":    "Python 2 legacy",
        "pattern":     r"\bimport\s+cPickle\b",
        "title":       "import cPickle (Python 2 uniquement)",
        "description": "cPickle a été fusionné dans pickle en Python 3.",
        "severity":    "critical",
        "suggestion":  "Utiliser import pickle à la place.",
    },
    {
        "code":        "P018",
        "category":    "Python 2 legacy",
        "pattern":     r"\bimport\s+thread\b",
        "title":       "import thread (Python 2 uniquement)",
        "description": "Le module thread a été renommé _thread en Python 3.",
        "severity":    "critical",
        "suggestion":  "Utiliser import threading à la place.",
    },

    # ── Python 2 legacy — fonctions supprimées en Python 3 ───────────────────
    {
        "code":        "P019",
        "category":    "Python 2 legacy",
        "pattern":     r"\bxrange\s*\(",
        "title":       "xrange() supprimé en Python 3",
        "description": "xrange() n'existe plus en Python 3.",
        "severity":    "critical",
        "suggestion":  "Utiliser range() qui est paresseux (lazy) par défaut en Python 3.",
    },
    {
        "code":        "P020",
        "category":    "Python 2 legacy",
        "pattern":     r"\.has_key\s*\(",
        "title":       "dict.has_key() supprimé en Python 3",
        "description": "La méthode has_key() a été supprimée en Python 3.",
        "severity":    "high",
        "suggestion":  "Utiliser l'opérateur 'in' : if key in dict:",
    },
    {
        "code":        "P021",
        "category":    "Python 2 legacy",
        "pattern":     r"\.iteritems\s*\(\)|\.itervalues\s*\(\)|\.iterkeys\s*\(\)",
        "title":       "dict.iteritems/itervalues/iterkeys() supprimés en Python 3",
        "description": "Les méthodes iter*() ont été supprimées en Python 3.",
        "severity":    "high",
        "suggestion":  "Utiliser .items(), .values(), .keys() directement.",
    },
    {
        "code":        "P022",
        "category":    "Python 2 legacy",
        # (?<!\.) exclut les méthodes : df.apply(), self.apply(), etc.
        "pattern":     r"(?<!\.)\bapply\s*\(",
        "title":       "apply() supprimé en Python 3",
        "description": "La fonction apply() builtin a été supprimée en Python 3.",
        "severity":    "high",
        "suggestion":  "Appeler directement : func(*args) ou func(**kwargs).",
    },
    {
        "code":        "P023",
        "category":    "Python 2 legacy",
        # Exclut exec(open( — c'est déjà la forme corrigée de execfile
        "pattern":     r"\bexecfile\s*\(",
        "title":       "execfile() supprimé en Python 3",
        "description": "execfile() a été supprimé en Python 3.",
        "severity":    "high",
        "suggestion":  "Utiliser exec(open(path).read()) ou importlib.",
    },
    {
        "code":        "P024",
        "category":    "Python 2 legacy",
        "pattern":     r"\bbasestring\b",
        "title":       "basestring supprimé en Python 3",
        "description": "basestring n'existe plus en Python 3 (str et bytes séparés).",
        "severity":    "high",
        "suggestion":  "Utiliser str pour les chaînes de caractères.",
    },
    {
        "code":        "P025",
        "category":    "Python 2 legacy",
        "pattern":     r"\bunicode\s*\(",
        "title":       "unicode() supprimé en Python 3",
        "description": "unicode() n'existe plus en Python 3, toutes les str sont unicode.",
        "severity":    "high",
        "suggestion":  "Utiliser str() directement ou supprimer l'appel.",
    },

    # ── Python 2 legacy — syntaxe invalide en Python 3 ───────────────────────
    {
        "code":        "P026",
        "category":    "Python 2 legacy",
        "pattern":     r"^\s*print\s+[^(]",
        "title":       "print sans parenthèses (Python 2)",
        "description": "La syntaxe 'print x' est invalide en Python 3.",
        "severity":    "critical",
        "suggestion":  "Utiliser print(x) avec parenthèses.",
    },
    {
        "code":        "P027",
        "category":    "Python 2 legacy",
        "pattern":     r"\braise\s+\w[\w.]*\s*,",
        "title":       "raise avec virgule (Python 2)",
        "description": "La syntaxe 'raise ExcType, value' est invalide en Python 3.",
        "severity":    "critical",
        "suggestion":  "Utiliser raise ExcType(value) avec parenthèses.",
    },

    # ── Sécurité — injections SQL ─────────────────────────────────────────────
    {
        "code":        "P028",
        "category":    "Sécurité",
        "pattern":     r'execute\s*\(\s*["\'].*%[s\d].*["\'].*%',
        "title":       "Injection SQL via formatage %",
        "description": "Construire une requête SQL avec % permet des injections SQL.",
        "severity":    "critical",
        "suggestion":  "Utiliser des requêtes paramétrées : cursor.execute(sql, (value,))",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE D'ANALYSE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_python_code(code: str) -> dict:
    """
    Analyse statique complète d'un fichier Python.
    Retourne toutes les métriques et problèmes détectés.
    """
    lines       = code.splitlines()
    issues      = _detect_issues(code, lines)
    metrics     = _compute_metrics(code, lines)
    version_est = _estimate_python_version(code)

    return {
        "estimated_version":  version_est,
        "metrics":            metrics,
        "issues":             [_issue_to_dict(i) for i in issues],
        "issues_count":       len(issues),
        "issues_by_severity": _group_by_severity(issues),
        "issues_by_category": _group_by_category(issues),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DÉTECTION DES PROBLÈMES
# ─────────────────────────────────────────────────────────────────────────────

def _detect_issues(code: str, lines: list[str]) -> list[Issue]:
    issues = []
    for rule in RULES:
        flags = re.MULTILINE if (r"^\s*" in rule["pattern"] or rule["pattern"].startswith(r"^\s*")) else 0
        for match in re.finditer(rule["pattern"], code, flags):
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
    non_empty = [l for l in lines if l.strip() and not l.strip().startswith("#")]
    return {
        "total_lines":               len(lines),
        "code_lines":                len(non_empty),
        "comment_lines":             len([l for l in lines if l.strip().startswith("#")]),
        "class_count":               len(re.findall(r"^class\s+\w+", code, re.MULTILINE)),
        "function_count":            len(re.findall(r"^\s*def\s+\w+", code, re.MULTILINE)),
        "import_count":              len(re.findall(r"^(?:import|from)\s+\w+", code, re.MULTILINE)),
        "try_except_count":          len(re.findall(r"\btry\s*:", code)),
        "for_loop_count":            len(re.findall(r"\bfor\s+\w+\s+in\b", code)),
        "list_comprehension_count":  len(re.findall(r"\[.+\bfor\b.+\bin\b", code)),
        "has_type_hints":            bool(re.search(r"def\s+\w+\s*\([^)]*:\s*\w+", code)),
        "has_dataclasses":           bool(re.search(r"@dataclass", code)),
        "has_async":                 bool(re.search(r"\basync\s+def\b", code)),
        "has_fstrings":              bool(re.search(r'(?<!\w)f["\']', code)),
        "has_walrus":                bool(re.search(r":=", code)),
        "has_match":                 bool(re.search(r"^\s*match\s+\w+:", code, re.MULTILINE)),
        "has_logging":               bool(re.search(r"\bimport\s+logging\b", code)),
        "has_context_managers":      bool(re.search(r"\bwith\s+open\s*\(", code)),
        "has_is_none":               bool(re.search(r"\bis\s+None\b|\bis\s+not\s+None\b", code)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ESTIMATION DE LA VERSION PYTHON SOURCE
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_python_version(code: str) -> str:
    if re.search(r"^\s*match\s+\w+:", code, re.MULTILINE):
        return "Python 3.10+"
    if re.search(r":=", code):
        return "Python 3.8+"
    if re.search(r'f["\']|async\s+def|await\s+', code):
        return "Python 3.6+"
    if re.search(r"^\s*print\s+[^(]", code, re.MULTILINE):
        return "Python 2 (legacy)"
    return "Python 3.x"


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
