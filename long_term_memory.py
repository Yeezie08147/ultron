"""
long_term_memory.py — ULTRON Knowledge Graph
"""
import sqlite3
import os
import logging
import re

log = logging.getLogger("ultron.memory")

DB_PATH = os.path.join(os.path.dirname(__file__), "ultron_memory.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS facts
                 (id INTEGER PRIMARY KEY, fact TEXT UNIQUE)''')
    conn.commit()
    conn.close()

def add_fact(fact: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO facts (fact) VALUES (?)", (fact,))
        conn.commit()
        conn.close()
        log.info(f"Learned new fact: {fact}")
    except Exception as e:
        log.error(f"Memory write failed: {e}")

def get_all_facts() -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT fact FROM facts")
        rows = c.fetchall()
        conn.close()
        if not rows:
            return ""
        return "\n".join(f"- {row[0]}" for row in rows)
    except Exception as e:
        log.error(f"Memory read failed: {e}")
        return ""

def extract_and_store_fact(user_text: str):
    """
    Heuristically extract facts like 'My favorite color is red'
    or 'Remember that I like coffee'.
    """
    lower = user_text.lower()
    
    # 1. "Remember that..."
    match = re.search(r"remember that (.*)", lower, re.IGNORECASE)
    if match:
        add_fact(match.group(1).strip())
        return

    # 2. "My [property] is [value]"
    match = re.search(r"my (\w+(?: \w+)*) is (.*)", lower, re.IGNORECASE)
    if match:
        prop, val = match.groups()
        add_fact(f"The user's {prop} is {val}")
        return
        
    # 3. "I am [property]"
    match = re.search(r"i am (\w+(?: \w+)*)", lower, re.IGNORECASE)
    if match:
        prop = match.group(1)
        add_fact(f"The user is {prop}")
        return

init_db()
