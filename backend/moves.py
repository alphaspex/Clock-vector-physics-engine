"""MOVES: Obsolete module. All move parsing and translation is now handled by translator.py and rounds.py.
"""
def extract_thinking(text):
    return "", 0, text, None

def parse(text, motor_info, mastered_moves=None):
    return dict(moves={}, chains={}, do=[], forget=[], errors=[])

def merge(library, parsed):
    return library

def compile_do(do, library):
    return [], []
