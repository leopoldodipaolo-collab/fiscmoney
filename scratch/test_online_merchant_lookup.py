import urllib.request
import urllib.parse
import json
import re

def search_duckduckgo_lite(query):
    """
    Queries DuckDuckGo HTML / Lite for business descriptions.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    encoded_q = urllib.parse.quote_plus(query + " italia azienda attività")
    url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Extract snippets
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            clean_snippets = []
            for s in snippets[:3]:
                # Clean html tags
                text = re.sub(r'<[^>]+>', '', s).strip()
                clean_snippets.append(text)
            return " ".join(clean_snippets)
    except Exception as e:
        return f"Error: {e}"

print("Testing AUTOABRUZZO SRL:")
print(search_duckduckgo_lite("AUTOABRUZZO SRL"))

print("\nTesting FONDAZIONE TELETHON:")
print(search_duckduckgo_lite("FONDAZIONE TELETHON"))
