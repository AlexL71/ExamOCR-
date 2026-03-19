import re
from collections import Counter
from kiwipiepy import Kiwi

kiwi = Kiwi()

def normalize_text(text):
    if not text:
        return ""
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def analyze_text(text):
    if not text or text.strip() in ["[EMPTY]", ""]:
        return {
            "word_count": 0, 
            "char_count": 0, 
            "keywords": "", 
            "clean_text": "(No text detected)"
        }

    try:
        clean_text = normalize_text(text)
        word_count = len(clean_text.split())
        char_count = len(re.sub(r'\s', '', clean_text))
        
        tokens = kiwi.tokenize(clean_text)
        nouns = [t.form for t in tokens if t.tag in ['NNG', 'NNP'] and len(t.form) > 1]
        
        top_counts = Counter(nouns).most_common(5)
        top_keywords = ", ".join([f"{k}({v})" for k, v in top_counts])
        
        return {
            "word_count": word_count,
            "char_count": char_count,
            "keywords": top_keywords,
            "clean_text": clean_text
        }
        
    except Exception:
         return {
            "word_count": 0, 
            "char_count": 0, 
            "keywords": "", 
            "clean_text": "(Analysis Error)"
        }