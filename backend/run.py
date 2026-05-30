"""
run.py — Lance uvicorn avec une configuration qui évite les faux hot-reloads.

Problème évité : uvicorn en mode --reload surveille TOUT le dossier courant,
y compris data/migrated/*.py, data/uploads/*, etc.
Quand le pipeline de migration écrit un fichier .py dans data/migrated/,
uvicorn détecte ce changement et redémarre le serveur en plein milieu de la requête → ECONNRESET.

Solution : on surveille UNIQUEMENT le dossier app/ pour les rechargements.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host        = "0.0.0.0",
        port        = 8000,
        reload      = True,
        reload_dirs = ["app"],      # Ne surveiller QUE le dossier app/ — pas data/
        log_level   = "info",
    )
