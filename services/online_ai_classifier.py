"""
Module: services/online_ai_classifier.py
Provides real-time online merchant search and AI semantic categorization for Italian banking & credit card transactions.
"""

import re
import urllib.request
import urllib.parse
import html

# Pre-compiled Category Semantics for Italian Financial Domain
SEMANTIC_CLASSIFIERS = [
    # 1. Auto & Mobilità
    {
        "category": "Auto & Mobilità",
        "subcategory": "Concessionaria & Officina",
        "tags": ["#auto", "#tagliando_meccanico"],
        "keywords": [
            r"\bauto", r"\bautomobil", r"\bautoveicol", r"\bconcessionari", r"\bofficina\b",
            r"\bgommista\b", r"\bpneumatic", r"\bcarrozzeri", r"\bmeccanic",
            r"\belettrauto\b", r"\brevisione\s*auto", r"\btagliando\b", r"\bautoricamb",
            r"\bautofficina\b", r"\bmotors?\b", r"\bgarage\b", r"\bveicoli\b"
        ]
    },
    {
        "category": "Auto & Mobilità",
        "subcategory": "Carburante & Ricarica",
        "tags": ["#carburante"],
        "keywords": [
            r"\bdistributore\b", r"\bcarburant", r"\bbenzina\b", r"\bgasolio\b",
            r"\bmetano\b", r"\bgpl\b", r"\bstazione\s*di\s*servizio", r"\bricarica\s*elettrica",
            r"\bcolonnina\b", r"\benel\s*x\s*way", r"\btesla\s*supercharger"
        ]
    },
    {
        "category": "Auto & Mobilità",
        "subcategory": "Telepass & Pedaggi",
        "tags": ["#telepass"],
        "keywords": [
            r"\bautostrad", r"\bpedaggi", r"\bcasello\b", r"\btelepass\b", r"\btangenzial"
        ]
    },
    {
        "category": "Auto & Mobilità",
        "subcategory": "Assicurazione",
        "tags": ["#assicurazione"],
        "keywords": [
            r"\bassicurazion", r"\bpolizz", r"\brc\s*auto\b", r"\bcompagnia\s*assicurativa"
        ]
    },

    # 2. Tasse, Fisco & Banche (including Detraibile Donazioni / Onlus & Asilo / Scuola Bimbi)
    {
        "category": "Tasse, Fisco & Banche",
        "subcategory": "Asilo Nido & Scuola",
        "tags": ["#luciano", "#asilo", "#detraibile_730"],
        "keywords": [
            r"\basilo\b", r"\bnido\b", r"\bscuola\s*materna", r"\bscuola\s*infanzia",
            r"\brefezione", r"\bmensa\s*scolastica", r"\bbaby\s*parking", r"\bludoteca\b",
            r"\bistruzione\b", r"\buniversit[aà]", r"\bretta\s*scolastica"
        ]
    },
    {
        "category": "Tasse, Fisco & Banche",
        "subcategory": "Donazioni & Onlus (730)",
        "tags": ["#donazione_onlus", "#detraibile_730"],
        "keywords": [
            r"\bfondazione\b", r"\bonlus\b", r"\bnon\s*profit\b", r"\bnon-profit\b",
            r"\bsenza\s*scopo\s*di\s*lucro", r"\bbeneficenza\b", r"\bdonazion",
            r"\bente\s*del\s*terzo\s*settore", r"\bets\b", r"\btelethon\b",
            r"\bairc\b", r"\bunicef\b", r"\bcroce\s*rossa\b", r"\bmedici\s*senza\s*frontiere",
            r"\bsave\s*the\s*children\b", r"\bvitalba\b", r"\banffas\b"
        ]
    },
    {
        "category": "Tasse, Fisco & Banche",
        "subcategory": "Consulenze & CAF",
        "tags": ["#consulenze_caf"],
        "keywords": [
            r"\bcommercialista\b", r"\bcaf\b", r"\bpatronato\b", r"\bstudio\s*tributario",
            r"\bconsulent", r"\bnotaio\b", r"\bstudio\s*legal", r"\bavvocat"
        ]
    },
    {
        "category": "Tasse, Fisco & Banche",
        "subcategory": "F24 & Imposte",
        "tags": ["#f24_imposte"],
        "keywords": [
            r"\bagenzia\s*delle\s*entrate", r"\bimpost", r"\btass[ae]\b", r"\btribut",
            r"\bf24\b", r"\birpef\b", r"\bbollo\b", r"\bimu\b", r"\btari\b"
        ]
    },

    # 3. Salute & Benessere (730 Detraibile)
    {
        "category": "Salute & Benessere",
        "subcategory": "Farmacia & Medicinali",
        "tags": ["#detraibile_730", "#farmacia"],
        "keywords": [
            r"\bfarmaci", r"\bparafarmaci", r"\bapoteca\b", r"\bmedicinal",
            r"\bomeopati", r"\bfitoterapi", r"\bsanitari\b"
        ]
    },
    {
        "category": "Salute & Benessere",
        "subcategory": "Visite Mediche & Esami",
        "tags": ["#detraibile_730", "#visite_esami"],
        "keywords": [
            r"\bclinic", r"\bospedal", r"\bpoliclinic", r"\blaboratorio\s*analisi",
            r"\banalisi\s*clinich", r"\bpolidiagnostic", r"\bambulatori", r"\bmedic[oi]\b",
            r"\bdottoress", r"\bvisita\s*medica", r"\bdiagnostica\b", r"\bradiologi",
            r"\bpediatr", r"\bcardiolog", r"\bdermatolog", r"\bginecolog",
            r"\becografi", r"\brisonanza\b", r"\bticket\s*sanitari"
        ]
    },
    {
        "category": "Salute & Benessere",
        "subcategory": "Dentista & Ottico",
        "tags": ["#detraibile_730", "#dentista_ottico"],
        "keywords": [
            r"\bdentist", r"\bodontoiatr", r"\bstudio\s*dentistic", r"\bottic[ao]\b",
            r"\bocchiali\b", r"\blenti\s*a\s*contatto", r"\boptometrist"
        ]
    },
    {
        "category": "Salute & Benessere",
        "subcategory": "Palestra & Sport",
        "tags": ["#palestra_sport"],
        "keywords": [
            r"\bpalestr", r"\bfitness\b", r"\bcrossfit\b", r"\bpiscin",
            r"\byoga\b", r"\bpilates\b", r"\barti\s*marziali", r"\bcentro\s*sportivo",
            r"\bpadel\b", r"\btennis\b", r"\bgym\b", r"\bspa\b", r"\bterme\b", r"\bmassaggi"
        ]
    },

    # 4. Spesa & Alimentari
    {
        "category": "Spesa & Alimentari",
        "subcategory": "Supermercato",
        "tags": ["#supermercato"],
        "keywords": [
            r"\bsupermerca", r"\bipermerca", r"\bdiscount\b", r"\balimentari\b",
            r"\bgrocer", r"\bmarket\b", r"\besselunga\b", r"\bconad\b", r"\bcoop\b",
            r"\blidl\b", r"\beurospin\b", r"\bcarrefour\b", r"\bdespar\b", r"\bpam\b"
        ]
    },
    {
        "category": "Spesa & Alimentari",
        "subcategory": "Panetteria & Forno",
        "tags": ["#panetteria_forno"],
        "keywords": [
            r"\bpanifici", r"\bforno\b", r"\bpanetteri", r"\bpane\b", r"\bfocacci"
        ]
    },
    {
        "category": "Spesa & Alimentari",
        "subcategory": "Alimentari Freschi",
        "tags": ["#alimentari"],
        "keywords": [
            r"\bmacelleri", r"\bsalumeri", r"\bpescheri", r"\bortofrutt",
            r"\bfrutta\s*e\s*verdura", r"\bfruttivendol", r"\bgastronomi", r"\bcaseifici", r"\benotec"
        ]
    },

    # 5. Ristoranti & Bar
    {
        "category": "Ristoranti & Bar",
        "subcategory": "Pizzerie",
        "tags": ["#pizzeria"],
        "keywords": [
            r"\bpizzeri", r"\bpizza\b", r"\bpinseri"
        ]
    },
    {
        "category": "Ristoranti & Bar",
        "subcategory": "Bar & Colazioni",
        "tags": ["#bar_caffetteria"],
        "keywords": [
            r"\bbar\b", r"\bcaff[eè]", r"\bpasticceri", r"\bgelateri",
            r"\baperitiv", r"\bbistrot\b", r"\bpub\b", r"\bbirreri", r"\btisaneri"
        ]
    },
    {
        "category": "Ristoranti & Bar",
        "subcategory": "Ristoranti",
        "tags": ["#ristorante"],
        "keywords": [
            r"\bristoran", r"\btrattori", r"\bosteri", r"\bsushi\b",
            r"\btavola\s*calda", r"\bsteakhouse\b", r"\btaverna\b", r"\blocanda\b",
            r"\bfast\s*food\b", r"\bburger\b", r"\bkebab\b", r"\bfood\s*delivery",
            r"\bdeliveroo\b", r"\bjust\s*eat\b", r"\bglovo\b", r"\bubereats\b"
        ]
    },

    # 6. Casa & Immobili
    {
        "category": "Casa & Immobili",
        "subcategory": "Cura della Casa & Detersivi",
        "tags": ["#casa", "#detersivi"],
        "keywords": [
            r"\bdetersiv", r"\bcasaling", r"\bpulizia\b", r"\bigiene\s*casa",
            r"\bacqua\s*(&|e)\s*sapone", r"\btigot[aà]", r"\bcaddy'?s", r"\brisparmio\s*casa"
        ]
    },
    {
        "category": "Casa & Immobili",
        "subcategory": "Arredo & Brico",
        "tags": ["#brico_arredo"],
        "keywords": [
            r"\barred", r"\bmobili\b", r"\bbricolage\b", r"\bferrament",
            r"\bfaidate\b", r"\bfai\s*da\s*te\b", r"\bvernici\b", r"\bmateriale\s*elettrico",
            r"\bleroy\s*merlin", r"\bikea\b", r"\bbrico\b", r"\bbricofer\b", r"\bobi\b", r"\bmondo\s*convenienza",
            r"\bvivaio\b", r"\bpiante\s*e\s*fiori", r"\bgiardin"
        ]
    },
    {
        "category": "Casa & Immobili",
        "subcategory": "Mutuo",
        "tags": ["#mutuo"],
        "keywords": [
            r"\bmutuo\b", r"\brata\s*mutuo\b", r"\bfinanziamento\s*immobile"
        ]
    },

    # 7. Shopping & Abbigliamento (including Children / Baby)
    {
        "category": "Shopping & Abbigliamento",
        "subcategory": "Abbigliamento Bimbi",
        "tags": ["#luciano", "#bambini", "#vestiti_bimbo"],
        "keywords": [
            r"\boriginal\s*marines", r"\bvilla\s*beb[eè]", r"\bchicco\b", r"\bprenatal\b",
            r"\bblukids\b", r"\bzara\s*kids\b", r"\bkiabi\s*kids\b", r"\bbrums\b",
            r"\bmayoral\b", r"\bio\s*bimbo\b", r"\bbimbostore\b", r"\bokaidi\b",
            r"\bidexe\b", r"\bprimigi\b", r"\bprima\s*infanzia\b", r"\bneonat", r"\bbambin"
        ]
    },
    {
        "category": "Shopping & Abbigliamento",
        "subcategory": "Abbigliamento & Scarpe",
        "tags": ["#abbigliamento"],
        "keywords": [
            r"\babbigliamen", r"\bvestit", r"\bcalzatur", r"\bscarp[ae]",
            r"\bmoda\b", r"\bboutique\b", r"\bpelletteri", r"\bborse\b",
            r"\bintim", r"\bcalze\b", r"\bzara\b", r"\bh&m\b", r"\bovs\b", r"\bzalando\b",
            r"\bdecathlon\b", r"\bcisalfa\b", r"\bfoot\s*locker\b", r"\barticoli\s*sportivi"
        ]
    },
    {
        "category": "Shopping & Abbigliamento",
        "subcategory": "Elettronica & Gadget",
        "tags": ["#elettronica"],
        "keywords": [
            r"\belettronic", r"\belettrodomestic", r"\bmediaworld\b", r"\bunieuro\b",
            r"\beuronics\b", r"\bapple\s*store\b", r"\bcomputer\b", r"\bsmartphone\b"
        ]
    },

    # 8. Bollette & Utenze
    {
        "category": "Bollette & Utenze",
        "subcategory": "Luce & Gas",
        "tags": ["#luce_gas"],
        "keywords": [
            r"\bfornitura\s*elettrica", r"\benergia\s*elettrica", r"\bluce\s*e\s*gas",
            r"\bfornitura\s*gas", r"\benel\b", r"\ba2a\b", r"\bsorgenia\b", r"\bedison\b",
            r"\bplenitude\b", r"\bhera\b", r"\biren\b"
        ]
    },
    {
        "category": "Bollette & Utenze",
        "subcategory": "Acqua & Rifiuti",
        "tags": ["#acqua", "#rifiuti_tari"],
        "keywords": [
            r"\bacquedott", r"\bservizio\s*idrico", r"\bacqua\s*potabile", r"\brifiuti\b", r"\btari\b"
        ]
    },

    # 9. Digitale, Tech & Tel
    {
        "category": "Digitale, Tech & Tel",
        "subcategory": "Tool AI & Software",
        "tags": ["#software_ai"],
        "keywords": [
            r"\bsoftware\b", r"\bintelligenza\s*artificiale", r"\bopenai\b", r"\bchatgpt\b",
            r"\bclaude\b", r"\banthropic\b", r"\bmidjourney\b", r"\badobe\b",
            r"\bmicrosoft\s*365", r"\boffice\s*365", r"\bjetbrains\b", r"\bcanva\b",
            r"\bnotion\b", r"\bapp\s*store\b", r"\bgoogle\s*play\b"
        ]
    },
    {
        "category": "Digitale, Tech & Tel",
        "subcategory": "Telefonia & SIM",
        "tags": ["#telefonia"],
        "keywords": [
            r"\btelefoni", r"\bsim\b", r"\boperator[ei]\s*telefonic", r"\biliad\b",
            r"\btim\b", r"\bvodafone\b", r"\bwind\s*tre\b", r"\bho\.\s*mobile\b", r"\bkena\b",
            r"\bfastweb\b", r"\bfibra\b", r"\bconnessione\s*internet\b"
        ]
    },
    {
        "category": "Digitale, Tech & Tel",
        "subcategory": "Streaming & Media",
        "tags": ["#streaming"],
        "keywords": [
            r"\bstreaming\b", r"\bnetflix\b", r"\bspotify\b", r"\bdisney\b",
            r"\bamazon\s*prime\b", r"\byoutube\s*premium\b", r"\bdazn\b", r"\bnow\s*tv\b"
        ]
    },

    # 10. Viaggi & Tempo Libero
    {
        "category": "Viaggi & Tempo Libero",
        "subcategory": "Hotel & Alloggi",
        "tags": ["#hotel_alloggi"],
        "keywords": [
            r"\bhotel\b", r"\balberg", r"\bb&b\b", r"\bbed\s*(&|and)\s*breakfast",
            r"\bresort\b", r"\bagriturism", r"\bostello\b", r"\bbooking\b",
            r"\bairbnb\b", r"\balloggi", r"\bvilla\b", r"\bcampeggi"
        ]
    },
    {
        "category": "Viaggi & Tempo Libero",
        "subcategory": "Voli & Treni Lunghi",
        "tags": ["#voli_treni"],
        "keywords": [
            r"\bvolo\b", r"\bvoli\b", r"\bcompagnia\s*aerea", r"\bryanair\b",
            r"\beasyjet\b", r"\bwizz\s*air\b", r"\btrenitalia\b", r"\bitalo\b",
            r"\bfrecciarossa\b", r"\baeroport"
        ]
    },
    {
        "category": "Viaggi & Tempo Libero",
        "subcategory": "Cinema & Eventi",
        "tags": ["#cinema_eventi"],
        "keywords": [
            r"\bcinema\b", r"\bteatro\b", r"\bconcerto\b", r"\bmuseo\b",
            r"\bmostra\b", r"\bticketone\b", r"\bvivaticket\b", r"\bevento\b",
            r"\bparco\s*divertimenti\b"
        ]
    }
]


def clean_search_term(raw_query: str) -> str:
    """
    Cleans bank transaction text, strips transaction codes, and extracts the primary business name.
    e.g. "PAGAM. POS AUTOABRUZZO SRL 08/09" -> "AUTOABRUZZO SRL"
    """
    if not raw_query:
        return ""
    
    text = raw_query.upper().strip()
    
    # Remove standard bank prefixes / suffixes
    prefixes = [
        r"^PAGAMENTO\s+POS\s*", r"^PAGAM\.?\s*POS\s*", r"^PAGAM\s+DEBITO\s*",
        r"^CARTA\s+N\.\s*\d+\s*", r"^ADDEBITO\s+SDD\s*", r"^SDD\s+CORE\s*",
        r"^BONIFICO\s+A\s+FAVORE\s+DI\s*", r"^BONIFICO\s+SEPA\s+A\s+FAVORE\s+DI\s*",
        r"^DISPOSIZIONE\s+DI\s+PAGAMENTO\s*", r"^OPERAZIONE\s+CARTA\s*",
        r"^COMMISSIONE\s*", r"^PAGAMENTO\s+CARTA\s*", r"^RID\s+",
        r"^PAYPAL\s*\*\s*", r"^SUMUP\s*\*\s*"
    ]
    for p in prefixes:
        text = re.sub(p, "", text, flags=re.IGNORECASE).strip()
    
    # Remove dates, times, amounts, or location tails
    text = re.sub(r"\b\d{2}/\d{2}/\d{2,4}\b", "", text)
    text = re.sub(r"\b\d{2}:\d{2}(:\d{2})?\b", "", text)
    text = re.sub(r"\bN\.\s*\d+\b", "", text)
    text = re.sub(r"\b\d{6,}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text


def fetch_online_merchant_info(business_name: str, timeout: int = 4) -> dict:
    """
    Queries search engine for real-time Italian company / entity details.
    Returns extracted snippets and website clues.
    """
    clean_name = clean_search_term(business_name)
    if not clean_name:
        return {"snippets": "", "clean_name": "", "source": "empty"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    
    # 1. Search Query with Italian Business Context
    search_q = f"{clean_name} italia attività"
    encoded_q = urllib.parse.quote_plus(search_q)
    url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
    
    snippets_text = ""
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html_content = resp.read().decode("utf-8", errors="ignore")
            
            # Extract search snippets
            raw_snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html_content, re.DOTALL)
            clean_list = []
            for s in raw_snippets[:4]:
                t = html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
                if t:
                    clean_list.append(t)
            snippets_text = " ".join(clean_list)
    except Exception as e:
        snippets_text = ""

    return {
        "clean_name": clean_name,
        "snippets": snippets_text,
        "source": "duckduckgo_lite" if snippets_text else "offline_heuristic"
    }


def classify_merchant_online(merchant_text: str) -> dict:
    """
    Combines online search lookup with Italian financial taxonomy to accurately classify
    any merchant (e.g. FONDAZIONE TELETHON, AUTOABRUZZO SRL, Tigotà, etc.).
    """
    if not merchant_text or not merchant_text.strip():
        return {
            "success": False,
            "category": "Altro",
            "subcategory": "",
            "tags": [],
            "source": "empty",
            "confidence": 0,
            "reasoning": "Nessun testo fornito"
        }

    clean_name = clean_search_term(merchant_text)
    
    # 1. Fetch live web snippets for this merchant
    online_data = fetch_online_merchant_info(clean_name)
    combined_corpus = f"{merchant_text} {clean_name} {online_data.get('snippets', '')}".lower()
    
    # 2. Score against Semantic Taxonomies
    best_match = None
    best_score = 0
    matched_keyword = ""

    for rule in SEMANTIC_CLASSIFIERS:
        score = 0
        current_matched_kw = ""
        for kw in rule["keywords"]:
            matches = len(re.findall(kw, combined_corpus, flags=re.IGNORECASE))
            if matches > 0:
                score += (matches * 2)
                # Boost if matched in original merchant name directly
                if re.search(kw, merchant_text, flags=re.IGNORECASE):
                    score += 5
                if not current_matched_kw:
                    current_matched_kw = kw.replace(r"\b", "").replace(r"\s*", " ")
        
        if score > best_score:
            best_score = score
            best_match = rule
            matched_keyword = current_matched_kw

    # 3. Format result
    if best_match and best_score >= 2:
        reasoning = f"Riconosciuto da '{clean_name}'"
        if online_data.get("snippets"):
            # Provide a short 1-line summary from online snippets
            snippet_summary = online_data["snippets"][:120].strip()
            if len(online_data["snippets"]) > 120:
                snippet_summary += "..."
            reasoning = f"Info Online: {snippet_summary}"

        return {
            "success": True,
            "clean_name": clean_name,
            "category": best_match["category"],
            "subcategory": best_match["subcategory"],
            "tags": best_match["tags"],
            "confidence": min(100, best_score * 12),
            "reasoning": reasoning,
            "source": "online_search" if online_data.get("snippets") else "nlp_ontology"
        }
    else:
        return {
            "success": False,
            "clean_name": clean_name,
            "category": "Altro",
            "subcategory": "",
            "tags": [],
            "confidence": 0,
            "reasoning": f"Nessuna corrispondenza chiara trovata per '{clean_name}'",
            "source": "unknown"
        }
