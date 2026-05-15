# legacy_data_processor.py — Code Python legacy avec de mauvaises pratiques

import os
import json
import datetime

# Variable globale sans type hint
data_cache = {}
errors = []

# Pas de type hints, pas de docstring
def load_data(filename):
    f = open(filename, 'r')  # fichier jamais fermé
    content = f.read()
    return content

# bare except — avale toutes les erreurs
def parse_json(text):
    try:
        result = json.loads(text)
        return result
    except:
        print("Erreur parsing JSON")
        return None

# Concatenation de string avec +
def build_report(items):
    report = ""
    for item in items:
        report = report + "- " + str(item) + "\n"
    return report

# Comparaison avec == None au lieu de is None
def validate_user(user):
    if user == None:
        return False
    if user["age"] == None:
        return False
    return True

# print() au lieu de logging
def process_records(records):
    print("Debut traitement")
    results = []
    for i in range(len(records)):   # range(len()) old-style
        record = records[i]
        if record != None:
            results.append(record)
            print("Traite : " + str(record))
    print("Fin traitement : " + str(len(results)) + " records")
    return results

# Pas de type hints + logique complexe sans docstring
def calculate_stats(numbers):
    total = 0
    count = 0
    minimum = None
    maximum = None
    for n in numbers:
        total = total + n
        count = count + 1
        if minimum == None or n < minimum:
            minimum = n
        if maximum == None or n > maximum:
            maximum = n
    if count == 0:
        return None
    average = total / count
    return {"total": total, "average": average, "min": minimum, "max": maximum}

# datetime.datetime.now() old-style
def get_timestamp():
    now = datetime.datetime.now()
    return str(now.year) + "-" + str(now.month) + "-" + str(now.day)

# Pas de f-string, concaténation manuelle
def format_message(name, score, level):
    msg = "Utilisateur: " + name + " | Score: " + str(score) + " | Niveau: " + level
    return msg

# Exception générique levée
def divide(a, b):
    if b == 0:
        raise Exception("Division par zero")
    return a / b

# Fonction trop longue sans découpage
def full_pipeline(filename, users):
    print("=== Debut pipeline ===")

    # Chargement
    try:
        f = open(filename, 'r')
        data = f.read()
        f.close()
    except:
        print("Fichier introuvable")
        data = "[]"

    # Parsing
    try:
        records = json.loads(data)
    except:
        records = []

    # Traitement users
    valid_users = []
    for i in range(len(users)):
        u = users[i]
        if u != None and u["name"] != None:
            valid_users.append(u)

    # Stats
    scores = []
    for u in valid_users:
        scores.append(u.get("score", 0))

    stats = calculate_stats(scores)

    report = ""
    for u in valid_users:
        report = report + format_message(u["name"], u.get("score", 0), u.get("level", "basic")) + "\n"

    print("=== Fin pipeline ===")
    print(report)
    return {"users": valid_users, "stats": stats, "records": records}


if __name__ == "__main__":
    # Test build_report
    items = ["Alice", "Bob", "Charlie"]
    print(build_report(items))

    # Test calculate_stats
    numbers = [10, 25, 3, 47, 8, 19]
    stats = calculate_stats(numbers)
    print("Stats:", stats)

    # Test format_message
    print(format_message("Alice", 95, "gold"))

    # Test get_timestamp
    print("Date:", get_timestamp())

    # Test process_records
    records = ["rec1", None, "rec2", "rec3", None]
    process_records(records)

    # Test divide
    try:
        print("10/2 =", divide(10, 2))
        print("10/0 =", divide(10, 0))
    except Exception as e:
        print("Erreur:", e)

    # Test validate_user
    user1 = {"name": "Alice", "age": 30}
    user2 = {"name": "Bob", "age": None}
    print("User1 valide:", validate_user(user1))
    print("User2 valide:", validate_user(user2))

    # Test full_pipeline
    users = [
        {"name": "Alice", "score": 95, "level": "gold"},
        {"name": "Bob", "score": 72, "level": "silver"},
        None,
        {"name": "Charlie", "score": 88, "level": "gold"},
    ]
    result = full_pipeline("data.json", users)
    print("Pipeline result:", result["stats"])
