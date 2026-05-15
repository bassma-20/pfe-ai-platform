import os, sys, json
from math import *

cache = {}

def load_data(filepath):
    print("Loading data from " + filepath)
    try:
        f = open(filepath, 'r')
        data = json.load(f)
        f.close()
        return data
    except:
        print("Error loading file")
        return None

def process_items(items, results=[]):
    for item in items:
        if item != None:
            results.append(item)
    return results

def format_report(name, score, total):
    line = "User: %s | Score: %d / %d" % (name, score, total)
    print(line)
    return line

def get_value(obj):
    if type(obj) == dict:
        return obj.get('value')
    elif type(obj) == list:
        return obj[0] if obj else None
    return str(obj)

def build_csv(rows):
    output = ""
    for row in rows:
        output = output + ",".join(str(x) for x in row) + "\n"
    return output

def parse_number(s):
    try:
        return float(s)
    except:
        pass

def update_cache(key, value):
    global cache
    cache[key] = value
    print("Cache updated: " + key + " = " + str(value))

transform = lambda x, y, z: x * 2 + y - z if x > 0 else abs(x - y + z)

def is_valid(item):
    if item['active'] == True:
        return True
    if item['deleted'] == False:
        return True
    return False

def run_dynamic(code_string):
    exec(code_string)

if __name__ == "__main__":
    data = load_data("data.json")
    print("Done")
