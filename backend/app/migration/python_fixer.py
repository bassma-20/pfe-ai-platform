"""
python_fixer.py — Correcteur déterministe Python 2 → 3

Applique des transformations regex fiables APRÈS la migration LLM
pour garantir que certains patterns sont toujours corrigés,
même si le LLM les rate.

Usage :
    from app.migration.python_fixer import apply_deterministic_fixes
    fixed_code, applied = apply_deterministic_fixes(migrated_code)
"""

from __future__ import annotations

import re
from typing import Tuple, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS pour parser les arguments de fonctions avec parenthèses imbriquées
# ─────────────────────────────────────────────────────────────────────────────

def _extract_balanced(text: str) -> Optional[str]:
    """
    Extrait le contenu d'un appel de fonction jusqu'à la parenthèse fermante
    équilibrée. `text` commence juste APRÈS la `(` ouvrante.

    Exemple : _extract_balanced("func, [1,2], kwargs)")  →  "func, [1,2], kwargs"
    Retourne None si les parenthèses ne sont pas équilibrées.
    """
    depth = 1
    for i, ch in enumerate(text):
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
            if depth == 0:
                return text[:i]
    return None


def _split_args(text: str, maxsplit: int = -1) -> List[str]:
    """
    Découpe une liste d'arguments en respectant les parenthèses/crochets imbriqués.
    Exemple : _split_args("func, [1,2,3], kwargs", 2) → ["func", "[1,2,3]", "kwargs"]
    """
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    splits = 0
    for ch in text:
        if ch in '([{':
            depth += 1
            current.append(ch)
        elif ch in ')]}':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            if maxsplit >= 0 and splits >= maxsplit:
                current.append(ch)
            else:
                parts.append(''.join(current).strip())
                current = []
                splits += 1
        else:
            current.append(ch)
    if current:
        parts.append(''.join(current).strip())
    return [p for p in parts if p]


def apply_deterministic_fixes(code: str) -> Tuple[str, List[str]]:
    """
    Applique des corrections déterministes (regex) sur le code Python migré.

    Returns:
        (corrected_code, list_of_applied_fixes)
    """
    applied: List[str] = []

    # ─── 1. xrange → range ─────────────────────────────────────────────────
    if re.search(r'\bxrange\b', code):
        code = re.sub(r'\bxrange\b', 'range', code)
        applied.append("xrange() → range()")

    # ─── 2. .iteritems() / .itervalues() / .iterkeys() ─────────────────────
    if '.iteritems()' in code:
        code = code.replace('.iteritems()', '.items()')
        applied.append(".iteritems() → .items()")
    if '.itervalues()' in code:
        code = code.replace('.itervalues()', '.values()')
        applied.append(".itervalues() → .values()")
    if '.iterkeys()' in code:
        code = code.replace('.iterkeys()', '.keys()')
        applied.append(".iterkeys() → .keys()")

    # ─── 3. dict.has_key(k) → k in dict ────────────────────────────────────
    if '.has_key(' in code:
        code = re.sub(
            r'(\w[\w.]*)\s*\.\s*has_key\s*\(\s*([^)]+?)\s*\)',
            r'\2 in \1',
            code,
        )
        applied.append(".has_key(k) → k in dict")

    # ─── 4. import urllib2 → import urllib.request + urllib.error ──────────
    if re.search(r'\bimport\s+urllib2\b', code):
        code = re.sub(r'\bimport\s+urllib2\b',
                      'import urllib.request\nimport urllib.error', code)
        code = re.sub(r'\burllib2\.urlopen\b',   'urllib.request.urlopen',  code)
        code = re.sub(r'\burllib2\.Request\b',   'urllib.request.Request',  code)
        code = re.sub(r'\burllib2\.HTTPError\b', 'urllib.error.HTTPError',  code)
        code = re.sub(r'\burllib2\.URLError\b',  'urllib.error.URLError',   code)
        code = re.sub(r'\burllib2\.',            'urllib.request.',         code)
        applied.append("urllib2 → urllib.request / urllib.error")

    # ─── 5. import cPickle → import pickle ─────────────────────────────────
    if re.search(r'\bimport\s+cPickle\b', code):
        code = re.sub(r'\bimport\s+cPickle\b', 'import pickle', code)
        code = re.sub(r'\bcPickle\.', 'pickle.', code)
        applied.append("cPickle → pickle")

    # ─── 6. import thread → import threading ───────────────────────────────
    if re.search(r'^\s*import\s+thread\s*$', code, re.MULTILINE):
        code = re.sub(r'\bimport\s+thread\b', 'import threading', code)
        applied.append("import thread → import threading")

    # ─── 7. basestring → str ────────────────────────────────────────────────
    if re.search(r'\bbasestring\b', code):
        code = re.sub(r'\bbasestring\b', 'str', code)
        applied.append("basestring → str")

    # ─── 8. unicode(x) → str(x) ─────────────────────────────────────────────
    if re.search(r'\bunicode\s*\(', code):
        code = re.sub(r'\bunicode\s*\(', 'str(', code)
        applied.append("unicode() → str()")

    # ─── 9. apply(func, args) → func(*args) ─────────────────────────────────
    # (?<!\.) exclut .apply() méthodes (pandas, etc.)
    # Utilise _extract_call_args pour gérer les parenthèses imbriquées
    if re.search(r'(?<!\.)\bapply\s*\(\s*\w', code):
        def _fix_apply_match(m: re.Match) -> str:
            # m.group(0) = "apply(...)" complet
            raw = m.group(0)
            # Extraire le contenu entre les parenthèses externes
            inner = _extract_balanced(raw[raw.index('(') + 1:])
            if inner is None:
                return raw  # ne pas toucher si extraction échoue
            # Découper en max 3 parties (func, args, kwargs)
            parts = _split_args(inner, maxsplit=2)
            if len(parts) == 0:
                return raw
            elif len(parts) == 1:
                return f"{parts[0]}()"
            elif len(parts) == 2:
                return f"{parts[0]}(*{parts[1]})"
            else:
                return f"{parts[0]}(*{parts[1]}, **{parts[2]})"

        new_code = re.sub(r'(?<!\.)\bapply\s*\([^;#\n]*?\)', _fix_apply_match, code)
        if new_code != code:
            code = new_code
            applied.append("apply(f, args) → f(*args)")

    # ─── 10. execfile(path) → exec(open(path).read()) ───────────────────────
    if re.search(r'\bexecfile\s*\(', code):
        code = re.sub(
            r'\bexecfile\s*\(\s*([^)]+?)\s*\)',
            r'exec(open(\1).read())',
            code,
        )
        applied.append("execfile(path) → exec(open(path).read())")

    # ─── 11. raise ExcType, msg → raise ExcType(msg) ────────────────────────
    if re.search(r'\braise\s+\w[\w.]*\s*,', code):
        code = re.sub(
            r'\braise\s+(\w[\w.]*)\s*,\s*(.+)',
            r'raise \1(\2)',
            code,
        )
        applied.append("raise ExcType, msg → raise ExcType(msg)")

    # ─── 12. print statement → print() function ─────────────────────────────
    # Only fix `print x` (no parentheses), not already-valid `print(x)`
    if re.search(r'^\s*print\s+[^(\n]', code, re.MULTILINE):
        def _fix_print(m: re.Match) -> str:
            indent = m.group(1)
            expr   = m.group(2).rstrip()
            return f'{indent}print({expr})'
        code = re.sub(
            r'^(\s*)print\s+(?!\()(.+)$',
            _fix_print,
            code,
            flags=re.MULTILINE,
        )
        applied.append("print statement → print() function")

    # ─── 13. SQL injection: cursor.execute("...%s..." % val) ─────────────────
    # Simple safe pattern:  execute("..." % something)
    #   → execute("...", (something,))
    # We handle the two most common forms:
    #   a) execute("SELECT ... '%s'" % name)
    #   b) execute("SELECT ... '%s'" % (name,))
    _sql_pattern = re.compile(
        r"""(\.execute\s*\(\s*)"""           # .execute(
        r"""(["'])((?:[^"'\\]|\\.)*?)\2"""   # "sql string"
        r"""\s*%\s*"""                        # %
        r"""(.+?)"""                          # value(s)
        r"""(\s*\))""",                       # closing )
        re.DOTALL,
    )

    def _fix_sql(m: re.Match) -> str:
        exec_call  = m.group(1)  # .execute(
        quote      = m.group(2)  # " or '
        sql        = m.group(3)  # SQL body
        val        = m.group(4).strip()  # the parameter value(s)
        close_par  = m.group(5)  # )

        # Replace '%s' and '%d' (with surrounding quotes) → %s / %d
        sql_clean = re.sub(r"'%s'", '%s', sql)
        sql_clean = re.sub(r"'%d'", '%d', sql_clean)
        sql_clean = re.sub(r'"(%[sd])"', r'\1', sql_clean)

        # Normalise val into a proper tuple
        if val.startswith('(') and val.endswith(')'):
            params = val  # already a tuple: (name,) or (a, b)
        else:
            params = f'({val},)'

        return f'{exec_call}{quote}{sql_clean}{quote}, {params}{close_par}'

    if re.search(r'\.execute\s*\(\s*["\'].*["\'].*%', code):
        new_code = _sql_pattern.sub(_fix_sql, code)
        if new_code != code:
            code = new_code
            applied.append("Injection SQL % → requêtes paramétrées")

    # ─── 14. Ensure `import logging` is present when logging.* is used ──────
    if re.search(r'\blogging\s*\.', code):
        if not re.search(r'^\s*import\s+logging\b', code, re.MULTILINE):
            lines = code.splitlines()
            last_import = -1
            for idx, line in enumerate(lines):
                s = line.lstrip()
                if s.startswith('import ') or s.startswith('from '):
                    last_import = idx
            insert_at = last_import + 1 if last_import >= 0 else 0
            lines.insert(insert_at, 'import logging')
            code = '\n'.join(lines)
            applied.append("import logging ajouté (manquant)")

    # ─── 15. == None / != None → is None / is not None (P005) ───────────────
    # Safe: only match outside strings (best-effort with simple regex)
    if re.search(r'==\s*None|None\s*==|!=\s*None|None\s*!=', code):
        before = code
        # x == None  →  x is None
        code = re.sub(r'(\w[\w.\[\]()\'\"]*)\s*==\s*None\b',  r'\1 is None',     code)
        # None == x  →  x is None
        code = re.sub(r'\bNone\s*==\s*(\w[\w.\[\]()\'\"]*)' , r'\1 is None',     code)
        # x != None  →  x is not None
        code = re.sub(r'(\w[\w.\[\]()\'\"]*)\s*!=\s*None\b',  r'\1 is not None', code)
        # None != x  →  x is not None
        code = re.sub(r'\bNone\s*!=\s*(\w[\w.\[\]()\'\"]*)' , r'\1 is not None', code)
        if code != before:
            applied.append("== None / != None → is None / is not None")

    # ─── 16. == True / == False → direct boolean (P006) ────────────────────
    if re.search(r'==\s*True\b|==\s*False\b|\bTrue\s*==|\bFalse\s*==', code):
        before = code
        code = re.sub(r'(\w[\w.\[\]()\'\"]*)\s*==\s*True\b',   r'\1',     code)
        code = re.sub(r'\bTrue\s*==\s*(\w[\w.\[\]()\'\"]*)' ,  r'\1',     code)
        code = re.sub(r'(\w[\w.\[\]()\'\"]*)\s*==\s*False\b',  r'not \1', code)
        code = re.sub(r'\bFalse\s*==\s*(\w[\w.\[\]()\'\"]*)' , r'not \1', code)
        if code != before:
            applied.append("== True / == False → direct boolean check")

    # ─── 17. type(x) == ClassName → isinstance(x, ClassName) (P009) ────────
    if re.search(r'\btype\s*\(\s*\w[\w.]*\s*\)\s*==', code):
        before = code
        code = re.sub(
            r'\btype\s*\(\s*(\w[\w.]*)\s*\)\s*==\s*(\w[\w.]*)',
            r'isinstance(\1, \2)',
            code,
        )
        if code != before:
            applied.append("type(x) == Class → isinstance(x, Class)")

    # ─── 18. Old-style % string formatting → f-strings (P012) ──────────────
    # Simple safe case: "Hello %s" % name → f"Hello {name}"
    # Only handles single substitution to avoid complex tuple parsing
    if re.search(r'["\'].*%[sd].*["\'].*%\s*\w', code):
        def _fix_percent_str(m: re.Match) -> str:
            quote  = m.group(1)
            text   = m.group(2)
            var    = m.group(3).strip()
            # Replace %s/%d with {var}
            result = re.sub(r'%[sd]', f'{{{var}}}', text, count=1)
            return f'f{quote}{result}{quote}'

        before = code
        code = re.sub(
            r'(["\'])((?:[^"\'\\]|\\.)*%[sd](?:[^"\'\\]|\\.)*)\1\s*%\s*(\w[\w.]*)',
            _fix_percent_str,
            code,
        )
        if code != before:
            applied.append("'%s' % x → f-string")

    return code, applied
