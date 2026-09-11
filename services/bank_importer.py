import os
import io
import re
import csv
import copy
import hashlib
from datetime import datetime
import pandas as pd

# ---------------------------------------------------------
# 1. TAXONOMY: 12 Macro-Families & Sub-Categories
# ---------------------------------------------------------
MACRO_CATEGORIES = {
    "Spesa & Alimentari": {
        "icon": "🛒",
        "color": "#10b981", # Emerald Green
        "subcategories": ["Supermercato", "Panetteria & Forno", "Macelleria", "Ortofrutta", "Pescheria"]
    },
    "Casa & Immobili": {
        "icon": "🏠",
        "color": "#3b82f6", # Vivid Royal Blue
        "subcategories": ["Mutuo", "Affitto", "Condominio", "Manutenzione Casa", "Arredo & Brico", "Ristrutturazioni"]
    },
    "Bollette & Utenze": {
        "icon": "💡",
        "color": "#06b6d4", # Electric Cyan
        "subcategories": ["Luce & Gas", "Gas", "Acqua & Rifiuti", "Riscaldamento"]
    },
    "Auto & Mobilità": {
        "icon": "🚗",
        "color": "#f59e0b", # Amber Gold
        "subcategories": ["Carburante & Ricarica", "Telepass & Pedaggi", "Parcheggi & Garage", "Assicurazione", "Bollo", "Tagliando & Manutenzione", "Mezzi Pubblici & Taxi", "Cambio Gomme"]
    },
    "Ristoranti & Bar": {
        "icon": "🍽️",
        "color": "#f97316", # Vivid Coral Orange
        "subcategories": ["Ristoranti", "Pizzerie", "Bar & Colazioni", "Pranzi Lavoro", "Fast Food & Asporto"]
    },
    "Shopping & Abbigliamento": {
        "icon": "🛍️",
        "color": "#ec4899", # Vivid Neon Pink
        "subcategories": ["Abbigliamento & Scarpe", "Infanzia, Giochi & Scuola", "Elettronica & Gadget", "Articoli Persona", "Acquisti Online Vari"]
    },
    "Digitale, Tech & Tel": {
        "icon": "🌐",
        "color": "#8b5cf6", # Vivid Electric Violet
        "subcategories": ["Cloud, Server & Hosting", "Telefonia & SIM", "Fibra & Internet Casa", "Tool AI & Software", "Streaming & Media"]
    },
    "Viaggi & Tempo Libero": {
        "icon": "✈️",
        "color": "#14b8a6", # Vivid Teal / Turquoise
        "subcategories": ["Hotel & Alloggi", "Voli & Treni Lunghi", "Noleggio Auto", "Vacanze & Attività", "Cinema & Concerti", "Hobby & Sport Eventi"]
    },
    "Salute & Benessere": {
        "icon": "🩺",
        "color": "#ef4444", # Vivid Crimson Red
        "subcategories": ["Farmacia & Medicinali", "Visite Mediche & Esami", "Dentista & Ottico", "Palestra & Sport", "Igiene & Cura Personale"]
    },
    "Lavoro & Entrate": {
        "icon": "💼",
        "color": "#a855f7", # Bright Purple
        "subcategories": ["Stipendio", "Bonus & Premi", "Rimborsi Spese", "Prestazioni Occasionali", "Altre Entrate"]
    },
    "Risparmio & Investimenti": {
        "icon": "📈",
        "color": "#059669", # Mint Jade Green
        "subcategories": ["Fondo Pensione", "Investimenti & PAC", "Giroconto Interno", "Conto Deposito"]
    },
    "Tasse, Fisco & Banche": {
        "icon": "🏛️",
        "color": "#6366f1", # Indigo Slate
        "subcategories": ["F24 & Imposte", "Canoni & Commissioni", "IMU & Tributi Locali", "Consulenze & CAF", "Prelievo Contante & Bancomat"]
    }
}

# ---------------------------------------------------------
# Curated Intelligent Tag Taxonomy per Macro-Category
# ---------------------------------------------------------
CATEGORY_SMART_TAGS = {
    "Spesa & Alimentari": [
        {"code": "#supermercato", "label": "Supermercato", "icon": "🛒", "subcat": "Supermercato"},
        {"code": "#panetteria_forno", "label": "Panetteria & Forno", "icon": "🥖", "subcat": "Panetteria & Forno"},
        {"code": "#macelleria", "label": "Macelleria", "icon": "🥩", "subcat": "Macelleria"},
        {"code": "#frutta_verdura", "label": "Frutta & Verdura", "icon": "🍏", "subcat": "Ortofrutta"},
        {"code": "#pescheria", "label": "Pescheria", "icon": "🐟", "subcat": "Pescheria"}
    ],
    "Casa & Immobili": [
        {"code": "#mutuo", "label": "Mutuo", "icon": "🏠", "subcat": "Mutuo"},
        {"code": "#affitto", "label": "Affitto", "icon": "🏢", "subcat": "Affitto"},
        {"code": "#condominio", "label": "Condominio", "icon": "🏘️", "subcat": "Condominio"},
        {"code": "#manutenzione_casa", "label": "Manutenzione Casa", "icon": "🔧", "subcat": "Manutenzione Casa"},
        {"code": "#brico_arredo", "label": "Brico & Arredo", "icon": "🛠️", "subcat": "Arredo & Brico"},
        {"code": "#cura_casa", "label": "Cura Casa & Igiene", "icon": "🧹", "subcat": "Cura Casa & Igiene"},
        {"code": "#ristrutturazione", "label": "Ristrutturazione", "icon": "🏗️", "subcat": "Ristrutturazioni"}
    ],
    "Bollette & Utenze": [
        {"code": "#luce_gas", "label": "Luce & Gas", "icon": "⚡", "subcat": "Luce & Gas"},
        {"code": "#gas", "label": "Gas", "icon": "🔥", "subcat": "Gas"},
        {"code": "#acqua", "label": "Acqua", "icon": "💧", "subcat": "Acqua & Rifiuti"},
        {"code": "#rifiuti_tari", "label": "Rifiuti / TARI", "icon": "🗑️", "subcat": "Acqua & Rifiuti"},
        {"code": "#riscaldamento", "label": "Riscaldamento", "icon": "🌡️", "subcat": "Riscaldamento"}
    ],
    "Auto & Mobilità": [
        {"code": "#carburante", "label": "Carburante", "icon": "⛽", "subcat": "Carburante & Ricarica"},
        {"code": "#telepass", "label": "Telepass & Pedaggi", "icon": "🛣️", "subcat": "Telepass & Pedaggi"},
        {"code": "#parcheggio", "label": "Parcheggio", "icon": "🅿️", "subcat": "Parcheggi & Garage"},
        {"code": "#assicurazione", "label": "Assicurazione", "icon": "🛡️", "subcat": "Assicurazione"},
        {"code": "#bollo", "label": "Bollo Auto", "icon": "📋", "subcat": "Bollo"},
        {"code": "#tagliando_meccanico", "label": "Tagliando & Meccanico", "icon": "🔧", "subcat": "Tagliando & Manutenzione"},
        {"code": "#mezzi_taxi", "label": "Mezzi & Taxi", "icon": "🚆", "subcat": "Mezzi Pubblici & Taxi"},
        {"code": "#cambio_gomme", "label": "Cambio Gomme", "icon": "⚙️", "subcat": "Cambio Gomme"}
    ],
    "Ristoranti & Bar": [
        {"code": "#ristorante", "label": "Ristorante", "icon": "🍽️", "subcat": "Ristoranti"},
        {"code": "#pizzeria", "label": "Pizzeria", "icon": "🍕", "subcat": "Pizzerie"},
        {"code": "#bar_caffetteria", "label": "Bar & Caffetteria", "icon": "☕", "subcat": "Bar & Colazioni"},
        {"code": "#pranzo_lavoro", "label": "Pranzo Lavoro", "icon": "🥪", "subcat": "Pranzi Lavoro"},
        {"code": "#delivery_asporto", "label": "Fast Food & Delivery", "icon": "🛵", "subcat": "Fast Food & Asporto"}
    ],
    "Shopping & Abbigliamento": [
        {"code": "#abbigliamento", "label": "Abbigliamento & Scarpe", "icon": "👗", "subcat": "Abbigliamento & Scarpe"},
        {"code": "#figlio", "label": "Bimbi, Scuola & Figli", "icon": "👶", "subcat": "Infanzia, Giochi & Scuola"},
        {"code": "#elettronica", "label": "Elettronica & Gadget", "icon": "📱", "subcat": "Elettronica & Gadget"},
        {"code": "#cura_persona", "label": "Articoli Persona", "icon": "🧴", "subcat": "Articoli Persona"},
        {"code": "#amazon_online", "label": "Acquisti Online", "icon": "📦", "subcat": "Acquisti Online Vari"}
    ],
    "Digitale, Tech & Tel": [
        {"code": "#cloud_hosting", "label": "Cloud & Server (Render/AWS)", "icon": "☁️", "subcat": "Cloud, Server & Hosting"},
        {"code": "#telefonia", "label": "Telefonia & SIM", "icon": "📞", "subcat": "Telefonia & SIM"},
        {"code": "#fibra_internet", "label": "Fibra & Internet Casa", "icon": "🌐", "subcat": "Fibra & Internet Casa"},
        {"code": "#software_ai", "label": "Software & Tool AI", "icon": "🤖", "subcat": "Tool AI & Software"},
        {"code": "#streaming", "label": "Streaming (Netflix/Spotify)", "icon": "📺", "subcat": "Streaming & Media"}
    ],
    "Viaggi & Tempo Libero": [
        {"code": "#hotel_alloggi", "label": "Hotel & Alloggi", "icon": "🏨", "subcat": "Hotel & Alloggi"},
        {"code": "#voli_treni", "label": "Voli & Treni", "icon": "✈️", "subcat": "Voli & Treni Lunghi"},
        {"code": "#noleggio_auto", "label": "Noleggio Auto", "icon": "🚗", "subcat": "Noleggio Auto"},
        {"code": "#vacanze_relax", "label": "Vacanze & Attività", "icon": "🏖️", "subcat": "Vacanze & Attività"},
        {"code": "#cinema_eventi", "label": "Cinema & Concerti", "icon": "🎟️", "subcat": "Cinema & Concerti"},
        {"code": "#hobby_sport", "label": "Hobby & Sport Eventi", "icon": "🎮", "subcat": "Hobby & Sport Eventi"}
    ],
    "Salute & Benessere": [
        {"code": "#detraibile_730", "label": "730 Detraibile", "icon": "🩺", "subcat": "Farmacia & Medicinali", "is_fiscal": True, "is_default": True},
        {"code": "#farmacia", "label": "Farmacia", "icon": "💊", "subcat": "Farmacia & Medicinali"},
        {"code": "#visite_esami", "label": "Visite & Esami", "icon": "🩺", "subcat": "Visite Mediche & Esami", "is_fiscal": True},
        {"code": "#dentista_ottico", "label": "Dentista & Ottico", "icon": "🦷", "subcat": "Dentista & Ottico", "is_fiscal": True},
        {"code": "#palestra_sport", "label": "Palestra & Sport", "icon": "🏋️", "subcat": "Palestra & Sport"},
        {"code": "#igiene", "label": "Igiene & Cura", "icon": "✨", "subcat": "Igiene & Cura Personale"}
    ],
    "Lavoro & Entrate": [
        {"code": "#stipendio", "label": "Stipendio", "icon": "💶", "subcat": "Stipendio"},
        {"code": "#bonus_premi", "label": "Bonus & Premi", "icon": "🎁", "subcat": "Bonus & Premi"},
        {"code": "#rimborsi_spese", "label": "Rimborsi Spese", "icon": "🧾", "subcat": "Rimborsi Spese"},
        {"code": "#prestazioni_extra", "label": "Prestazioni Extra", "icon": "💼", "subcat": "Prestazioni Occasionali"}
    ],
    "Risparmio & Investimenti": [
        {"code": "#deducibile_pensione", "label": "Fondo Pensione (deducibile)", "icon": "📈", "subcat": "Fondo Pensione", "is_fiscal": True},
        {"code": "#investimenti_pac", "label": "Investimenti & PAC", "icon": "📊", "subcat": "Investimenti & PAC"},
        {"code": "#giroconto", "label": "Giroconto Interno", "icon": "🔄", "subcat": "Giroconto Interno", "is_default": True}
    ],
    "Tasse, Fisco & Banche": [
        {"code": "#prelievo_contante", "label": "Prelievo Contante / ATM", "icon": "🏧", "subcat": "Prelievo Contante & Bancomat"},
        {"code": "#f24_imposte", "label": "F24 & Imposte", "icon": "📄", "subcat": "F24 & Imposte"},
        {"code": "#canoni_commissioni", "label": "Canoni & Commissioni", "icon": "🏦", "subcat": "Canoni & Commissioni"},
        {"code": "#imu_tari", "label": "IMU & Tributi Locali", "icon": "🏛️", "subcat": "IMU & Tributi Locali"},
        {"code": "#consulenze_caf", "label": "Consulenze & CAF", "icon": "⚖️", "subcat": "Consulenze & CAF"}
    ]
}

# ---------------------------------------------------------
# 2. ITALIAN MERCHANT & PATTERN RULES (12 Macro-Categories)
# ---------------------------------------------------------
RULES_PATTERNS = [
    # --- Salute & Benessere (730 Detraibile di default) ---
    (r"\b(farmacia|farmacie|parafarmacia|farma|farmac|apoteca|redcare)\b", "Salute & Benessere", "Farmacia & Medicinali", "#detraibile_730 #farmacia"),
    (r"\b(synlab|santagostino|policlinico|ospedale|asl|ticket sanitar|studio medico|dott|dottoressa|laboratorio analisi|analisiclinich|cdi)\b", "Salute & Benessere", "Visite Mediche & Esami", "#detraibile_730 #visite_esami"),
    (r"\b(dentalpro|dentista|odontoiatr|ottica|salmoiraghi|grandvision|fisioterap|osteopat)\b", "Salute & Benessere", "Dentista & Ottico", "#detraibile_730 #dentista_ottico"),
    (r"\b(virgin active|fitprime|gym|palestra|mcfit|fitactive|anytime fitness|piscina|fitness)\b", "Salute & Benessere", "Palestra & Sport", "#palestra_sport"),

    # --- Spesa & Alimentari ---
    (r"\b(esselunga|conad|coop|ipercoop|lidl|eurospin|carrefour|despar|pam|md spa|penny market|il gigante|tigros|famila|bennet|crai|naturasi|supermerc|iperal|iper |tigre |todis|in's|sole365)\b", "Spesa & Alimentari", "Supermercato", "#supermercato"),
    (r"\b(panificio|forno|panetteria)\b", "Spesa & Alimentari", "Panetteria & Forno", "#panetteria_forno"),
    (r"\b(macelleria|salumeria|caseificio)\b", "Spesa & Alimentari", "Macelleria", "#macelleria"),
    (r"\b(pescheria)\b", "Spesa & Alimentari", "Pescheria", "#pescheria"),
    (r"\b(ortofrutta|frutta e verdura|fruttivendolo)\b", "Spesa & Alimentari", "Ortofrutta", "#frutta_verdura"),

    # --- Bollette & Utenze (Puntuali) ---
    (r"\b(enel|servizio elettrico|octopus energy|sorgenia|edison|illumia|e\.on|a2a energia|nen energia)\b", "Bollette & Utenze", "Luce & Gas", "#luce #bollette"),
    (r"\b(eni plenitude|plenitude|gas naturale|italgas|a2a calore)\b", "Bollette & Utenze", "Gas", "#gas #bollette"),
    (r"\b(acquedotto|acque spa|gori|abbanoa|acea acqua|publiacqua|smat|gruppo cap)\b", "Bollette & Utenze", "Acqua & Rifiuti", "#acqua #bollette"),
    (r"\b(tari|tassa rifiuti|ama roma|veritas|amsa|pagopa rifiuti)\b", "Bollette & Utenze", "Acqua & Rifiuti", "#tari #rifiuti"),

    # --- Casa & Immobili ---
    (r"\b(mutuo|rata mutuo|addebito mutuo|banca intesa mutuo)\b", "Casa & Immobili", "Mutuo", "#mutuo #casa"),
    (r"\b(affitto|locazione|canone locazione)\b", "Casa & Immobili", "Affitto", "#affitto #casa"),
    (r"\b(condominio|amministratore condominio|spese condominiali)\b", "Casa & Immobili", "Condominio", "#condominio"),
    (r"\b(acqua\s*&\s*sapone|acqua e sapone|risparmio casa|tigot[aà]|caddy'?s|ipersoap|prodet|splendidi e splendenti|detersiv)\b", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi"),
    (r"\b(leroy merlin|brico|bricocenter|bricoman|tecnomat|obi)\b", "Casa & Immobili", "Arredo & Brico", "#brico #faidate #casa"),
    (r"\b(ikea|mondo convenienza|maisons du monde|poltronesof[aà]|jysk)\b", "Casa & Immobili", "Arredo & Brico", "#arredo #mobili #casa"),

    # --- Auto & Mobilità (Dettagliata) ---
    (r"\b(q8|eni station|ip |esso|tamoil|totalerg|distributore|carburant|benzina|metano|gpl|ricarica ev|enel x way|tesla supercharger)\b", "Auto & Mobilità", "Carburante & Ricarica", "#carburante"),
    (r"\b(telepass|unipolmove|autostrade|tangenziale|pedaggio|aiscat)\b", "Auto & Mobilità", "Telepass & Pedaggi", "#telepass #pedaggi"),
    (r"\b(easypark|mycicero|mooneygo|apcoa|saba|parchegg|garage|sosta\s*auto|park\b|parking)\b", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio"),
    (r"\b(unipolsai|allianz|generali|reale mutua|vittoria ass|prima assicuraz|zurich|verti|direct line)\b", "Auto & Mobilità", "Assicurazione", "#assicurazione #auto"),
    (r"\b(bollo auto|aci bollo|tassa automobilistica)\b", "Auto & Mobilità", "Bollo", "#bollo #auto"),
    (r"\b(gommista|cambio gomme|pneumatici|driver center|euromaster)\b", "Auto & Mobilità", "Cambio Gomme", "#cambiogomme #gommista"),
    (r"\b(centro revisioni|revisione auto|dekra|revisione veicol)\b", "Auto & Mobilità", "Tagliando & Manutenzione", "#revisione #auto"),
    (r"\b(elettrauto|officina|tagliando|norauto|midas|autoricambi|meccanico|carrozzeria)\b", "Auto & Mobilità", "Tagliando & Manutenzione", "#meccanico #tagliando"),
    (r"\b(trenitalia|italo|atm milano|atac|gtt|tper|anm|uber|taxi|freenow|enjoy|share now|dott|lime)\b", "Auto & Mobilità", "Mezzi Pubblici & Taxi", "#mezzi_taxi"),

    # --- Ristoranti & Bar ---
    (r"\b(pizzeria|pizza|pizze)\b", "Ristoranti & Bar", "Pizzerie", "#pizzeria"),
    (r"\b(ristorante|trattoria|osteria|sushi|poke)\b", "Ristoranti & Bar", "Ristoranti", "#ristorante"),
    (r"\b(mc donald|mcdonald|burger king|kfc|just eat|glovo|deliveroo|ubereats)\b", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood"),
    (r"\b(bar |caffe|pasticceria|gelateria|pub |birreria|aperitivo|bistrot|autogrill)\b", "Ristoranti & Bar", "Bar & Colazioni", "#bar_caffetteria"),

    # --- Shopping & Abbigliamento ---
    (r"\b(zara|h&m|ovs|intimissimi|calzedonia|decathlon|zalando|asos|stradivarius|pull&bear|bershka|mango|geox|foot locker|tezenis|uniqlo|snipes)\b", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento"),
    (r"\b(mediaworld|unieuro|euronics|apple store|expert|comet|trony)\b", "Shopping & Abbigliamento", "Elettronica & Gadget", "#elettronica"),
    (r"\b(sephora|kiko|douglas|bottega verde)\b", "Shopping & Abbigliamento", "Articoli Persona", "#cura_persona"),
    (r"\b(amazon|amzn|aliexpress|ebay|temu|shein)\b", "Shopping & Abbigliamento", "Acquisti Online Vari", "#amazon_online"),

    # --- Digitale, Tech & Tel ---
    (r"\b(render|render\.com|vercel|supabase|aws|amazon web services|digitalocean|github|hetzner|cloudflare|ovh|aruba|register\.it|namecheap)\b", "Digitale, Tech & Tel", "Cloud, Server & Hosting", "#cloud_hosting"),
    (r"\b(iliad|tim spa|telecom|vodafone|wind tre|windtre|ho\. mobile|kena|spusu|very mobile|coopvoce|fastweb mobile|poste mobile)\b", "Digitale, Tech & Tel", "Telefonia & SIM", "#telefonia"),
    (r"\b(fastweb|sky wifi|eolo|linkem|fibra city|pianeta fibra)\b", "Digitale, Tech & Tel", "Fibra & Internet Casa", "#fibra_internet"),
    (r"\b(openai|chatgpt|claude|anthropic|midjourney|adobe|microsoft 365|office 365|jetbrains|canva|notion|google one|icloud|apple\.com/bill|google play)\b", "Digitale, Tech & Tel", "Tool AI & Software", "#software_ai"),
    (r"\b(netflix|spotify|amazon prime|disney|youtube premium|dazn|now tv|playstation|nintendo|steam|crunchyroll)\b", "Digitale, Tech & Tel", "Streaming & Media", "#streaming"),

    # --- Viaggi & Tempo Libero ---
    (r"\b(booking\.com|airbnb|hotel|resort|b&b|ostello)\b", "Viaggi & Tempo Libero", "Hotel & Alloggi", "#hotel_alloggi"),
    (r"\b(ryanair|easyjet|wizz air|volotea|vueling|lufthansa|trenitalia freccia|italo treno|ita airways)\b", "Viaggi & Tempo Libero", "Voli & Treni Lunghi", "#voli_treni"),
    (r"\b(rentacar|hertz|avis|europcar|sixt|locauto|maggiore)\b", "Viaggi & Tempo Libero", "Noleggio Auto", "#noleggio_auto"),
    (r"\b(expedia|snav|tirrenia|moby|villaggio vacanze|spiaggia|lido)\b", "Viaggi & Tempo Libero", "Vacanze & Attività", "#vacanze_relax"),
    (r"\b(cinema|the space|uci cinemas|teatro|ticketone|vivaticket|mostra|museo)\b", "Viaggi & Tempo Libero", "Cinema & Concerti", "#cinema_eventi"),

    # --- Lavoro & Entrate ---
    (r"\b(stipendio|emolumenti|salario|accredito stipendio|bonifico retribuzione|pensione inps|bonifico da datore)\b", "Lavoro & Entrate", "Stipendio", "#stipendio"),
    (r"\b(bonus|premio produzione|mbo|incentivo)\b", "Lavoro & Entrate", "Bonus & Premi", "#bonus_premi"),
    (r"\b(rimborso spese|nota spese|parcella|onorario|fattura n|incasso fattura|compenso)\b", "Lavoro & Entrate", "Rimborsi Spese", "#rimborsi_spese"),
    (r"\b(prestazione occasionale|collaborazione|freelance)\b", "Lavoro & Entrate", "Prestazioni Occasionali", "#prestazioni_extra"),

    # --- Risparmio & Investimenti ---
    (r"\b(fondo pensione|fondopensione|cometa|fonte|pegaso|fonchim|previndai|allianz insieme|secondapensione|arcafondi|anima sgr|amundi|pac fondo)\b", "Risparmio & Investimenti", "Fondo Pensione", "#deducibile_pensione"),
    (r"\b(directa|degiro|scalable|trade republic|fineco trading|etoro|crypto|etf)\b", "Risparmio & Investimenti", "Investimenti & PAC", "#investimenti_pac"),
    (r"\b(giroconto|trasferimento fondi|proprio favore|giroconto da|giroconto a|postagiro|ricarica postepay|ric\.prep|carta prepagata ric)\b", "Risparmio & Investimenti", "Giroconto Interno", "#giroconto"),

    # --- Tasse, Fisco & Banche ---
    (r"\b(prelievo atm|prelievo bancomat|prelievo contant|prelievo carta|sportello automatico|postamat prelievo|prelievo c/o|prelievo c\\o|prelievo)\b", "Tasse, Fisco & Banche", "Prelievo Contante & Bancomat", "#prelievo_contante"),
    (r"\b(f24|agenzia delle entrate|imposte|tasse|irpef|addizionale)\b", "Tasse, Fisco & Banche", "F24 & Imposte", "#f24_imposte"),
    (r"\b(tari|imu|tasi|tribut|imposta di bollo|bollo c/c)\b", "Tasse, Fisco & Banche", "IMU & Tributi Locali", "#imu_tari"),
    (r"\b(canone mensile carta|commissioni|commissione|comm\.\s*bon|spese tenuta conto|interessi passivi|spese liquidazione)\b", "Tasse, Fisco & Banche", "Canoni & Commissioni", "#canoni_commissioni"),
    (r"\b(commercialista|caf |patronato|consulente del lavoro|parcella avvocato)\b", "Tasse, Fisco & Banche", "Consulenze & CAF", "#consulenze_caf")
]

# ---------------------------------------------------------
# 3. INTERACTIVE CATEGORY SEARCH DICTIONARY (For UI Cheat Sheet)
# ---------------------------------------------------------
CATEGORY_SEARCH_DICTIONARY = [
    {"term": "Prelievo ATM / Bancomat / Contante", "category": "Tasse, Fisco & Banche", "subcategory": "Prelievo Contante & Bancomat", "tags": "#prelievo_contante", "icon": "🏧", "note": "Prelievo di contanti da sportello bancario o ATM"},
    {"term": "Render / Render.com", "category": "Digitale, Tech & Tel", "subcategory": "Cloud, Server & Hosting", "tags": "#cloud_hosting", "icon": "🌐", "note": "Server, database, hosting cloud per sviluppo"},
    {"term": "Vercel / Supabase / AWS", "category": "Digitale, Tech & Tel", "subcategory": "Cloud, Server & Hosting", "tags": "#cloud_hosting", "icon": "🌐", "note": "Infrastruttura cloud e servizi backend"},
    {"term": "GitHub / GitLab", "category": "Digitale, Tech & Tel", "subcategory": "Cloud, Server & Hosting", "tags": "#cloud_hosting", "icon": "🌐", "note": "Piattaforme di versioning e CI/CD"},
    {"term": "Iliad / ho. / Kena / Spusu", "category": "Digitale, Tech & Tel", "subcategory": "Telefonia & SIM", "tags": "#telefonia", "icon": "📞", "note": "Ricariche e canoni mensili SIM mobile"},
    {"term": "TIM / Vodafone / WindTre Mobile", "category": "Digitale, Tech & Tel", "subcategory": "Telefonia & SIM", "tags": "#telefonia", "icon": "📞", "note": "Abbonamenti telefonici smartphone"},
    {"term": "Fastweb / Eolo / Sky WiFi Casa", "category": "Digitale, Tech & Tel", "subcategory": "Fibra & Internet Casa", "tags": "#fibra_internet", "icon": "🌐", "note": "Connessione internet fibra/FWA domestica"},
    {"term": "ChatGPT / OpenAI / Claude", "category": "Digitale, Tech & Tel", "subcategory": "Tool AI & Software", "tags": "#software_ai", "icon": "🤖", "note": "Abbonamenti a intelligenze artificiali e LLM"},
    {"term": "Microsoft 365 / Adobe / Canva", "category": "Digitale, Tech & Tel", "subcategory": "Tool AI & Software", "tags": "#software_ai", "icon": "🤖", "note": "Software di produttività, grafica e suite office"},
    {"term": "Netflix / Spotify / Disney+", "category": "Digitale, Tech & Tel", "subcategory": "Streaming & Media", "tags": "#streaming", "icon": "📺", "note": "Abbonamenti streaming video e musica"},
    {"term": "Amazon Prime / YouTube Premium", "category": "Digitale, Tech & Tel", "subcategory": "Streaming & Media", "tags": "#streaming", "icon": "📺", "note": "Piattaforme video e servizi premium"},
    {"term": "Supermercato (Esselunga, Conad, Coop)", "category": "Spesa & Alimentari", "subcategory": "Supermercato", "tags": "#supermercato", "icon": "🛒", "note": "Spesa alimentare di routine"},
    {"term": "Panetteria, Macelleria, Ortofrutta", "category": "Spesa & Alimentari", "subcategory": "Panetteria & Forno", "tags": "#panetteria_forno", "icon": "🛒", "note": "Negozi di alimentari specifici"},
    {"term": "Rata Mutuo", "category": "Casa & Immobili", "subcategory": "Mutuo", "tags": "#mutuo", "icon": "🏠", "note": "Spesa principale abitazione"},
    {"term": "Canone Affitto", "category": "Casa & Immobili", "subcategory": "Affitto", "tags": "#affitto", "icon": "🏠", "note": "Pagamento canone mensile affitto"},
    {"term": "Spese Condominiali", "category": "Casa & Immobili", "subcategory": "Condominio", "tags": "#condominio", "icon": "🏠", "note": "Quote ordinarie e straordinarie condominio"},
    {"term": "IKEA / Leroy Merlin / Brico", "category": "Casa & Immobili", "subcategory": "Arredo & Brico", "tags": "#brico_arredo", "icon": "🏠", "note": "Mobili, arredo, bricolage e manutenzione fai-da-te"},
    {"term": "Bolletta Luce / Enel / Plenitude", "category": "Bollette & Utenze", "subcategory": "Luce & Gas", "tags": "#luce_gas", "icon": "💡", "note": "Fornitura energia elettrica"},
    {"term": "Bolletta Gas / Riscaldamento", "category": "Bollette & Utenze", "subcategory": "Gas", "tags": "#gas", "icon": "💡", "note": "Fornitura gas e teleriscaldamento"},
    {"term": "Bolletta Acqua / Rifiuti (TARI)", "category": "Bollette & Utenze", "subcategory": "Acqua & Rifiuti", "tags": "#acqua #rifiuti_tari", "icon": "💡", "note": "Acquedotto e tassa rifiuti comunale"},
    {"term": "Carburante (Q8, Eni, IP) / Ricarica EV", "category": "Auto & Mobilità", "subcategory": "Carburante & Ricarica", "tags": "#carburante", "icon": "🚗", "note": "Benzina, gasolio, metano o ricarica elettrica"},
    {"term": "Telepass & Pedaggi Autostradali", "category": "Auto & Mobilità", "subcategory": "Telepass & Pedaggi", "tags": "#telepass", "icon": "🚗", "note": "Addebiti mensili telepass e caselli"},
    {"term": "Parcheggio (EasyPark, MooneyGo, Sosta)", "category": "Auto & Mobilità", "subcategory": "Parcheggi & Garage", "tags": "#parcheggio", "icon": "🅿️", "note": "Strisce blu, garage e app di sosta"},
    {"term": "Assicurazione Auto / Moto (RC Auto)", "category": "Auto & Mobilità", "subcategory": "Assicurazione", "tags": "#assicurazione", "icon": "🚗", "note": "Polizze veicoli"},
    {"term": "Bollo Auto (Tassa Automobilistica)", "category": "Auto & Mobilità", "subcategory": "Bollo", "tags": "#bollo", "icon": "🚗", "note": "Tassa di possesso regionale"},
    {"term": "Tagliando, Meccanico, Cambio Gomme", "category": "Auto & Mobilità", "subcategory": "Tagliando & Manutenzione", "tags": "#tagliando_meccanico", "icon": "🚗", "note": "Manutenzione ordinaria del veicolo"},
    {"term": "Scontrino Farmacia (con Codice Fiscale)", "category": "Salute & Benessere", "subcategory": "Farmacia & Medicinali", "tags": "#detraibile_730 #farmacia", "icon": "🩺", "note": "Medicinali con scontrino parlante detraibili al 19%"},
    {"term": "Visite Mediche, Esami, Laboratorio", "category": "Salute & Benessere", "subcategory": "Visite Mediche & Esami", "tags": "#detraibile_730 #visite_esami", "icon": "🩺", "note": "Visite specialistiche private o ticket ASL"},
    {"term": "Dentista, Ottico (Occhiali da vista)", "category": "Salute & Benessere", "subcategory": "Dentista & Ottico", "tags": "#detraibile_730 #dentista_ottico", "icon": "🩺", "note": "Cure odontoiatriche e dispositivi medici"},
    {"term": "Palestra, Abbonamento Sport, Piscina", "category": "Salute & Benessere", "subcategory": "Palestra & Sport", "tags": "#palestra_sport", "icon": "🩺", "note": "Attività fisica e benessere personale"},
    {"term": "Zara, H&M, OVS, Zalando, ASOS", "category": "Shopping & Abbigliamento", "subcategory": "Abbigliamento & Scarpe", "tags": "#abbigliamento", "icon": "🛍️", "note": "Capi d'abbigliamento, calzature e accessori"},
    {"term": "MediaWorld, Unieuro, Apple Store", "category": "Shopping & Abbigliamento", "subcategory": "Elettronica & Gadget", "tags": "#elettronica", "icon": "🛍️", "note": "Smartphone, PC, TV ed elettrodomestici"},
    {"term": "Amazon (Acquisti Vari Online)", "category": "Shopping & Abbigliamento", "subcategory": "Acquisti Online Vari", "tags": "#amazon_online", "icon": "🛍️", "note": "Ordini generici e articoli vari"},
    {"term": "Ristorante, Trattoria, Pizzeria, Sushi", "category": "Ristoranti & Bar", "subcategory": "Ristoranti", "tags": "#ristorante #pizzeria", "icon": "🍽️", "note": "Cene e uscite gastronomiche"},
    {"term": "Bar, Colazione, Aperitivo, Gelateria", "category": "Ristoranti & Bar", "subcategory": "Bar & Colazioni", "tags": "#bar_caffetteria", "icon": "🍽️", "note": "Caffè, aperitivi e pause veloci"},
    {"term": "Just Eat, Glovo, Deliveroo, UberEats", "category": "Ristoranti & Bar", "subcategory": "Fast Food & Asporto", "tags": "#delivery_asporto", "icon": "🍽️", "note": "Cibo a domicilio o da asporto"},
    {"term": "Booking.com, Airbnb, Hotel", "category": "Viaggi & Tempo Libero", "subcategory": "Hotel & Alloggi", "tags": "#hotel_alloggi", "icon": "✈️", "note": "Pernottamenti per vacanze o weekend"},
    {"term": "Voli (Ryanair, EasyJet) / Treni Lunghi", "category": "Viaggi & Tempo Libero", "subcategory": "Voli & Treni Lunghi", "tags": "#voli_treni", "icon": "✈️", "note": "Biglietti aerei o Frecciarossa per viaggi"},
    {"term": "Cinema, Teatro, Concerti (TicketOne)", "category": "Viaggi & Tempo Libero", "subcategory": "Cinema & Concerti", "tags": "#cinema_eventi", "icon": "✈️", "note": "Spettacoli e intrattenimento dal vivo"},
    {"term": "Stipendio Netto / Accredito Emolumenti", "category": "Lavoro & Entrate", "subcategory": "Stipendio", "tags": "#stipendio", "icon": "💼", "note": "Entrata da lavoro dipendente"},
    {"term": "Versamento Fondo Pensione Volontario", "category": "Risparmio & Investimenti", "subcategory": "Fondo Pensione", "tags": "#deducibile_pensione", "icon": "📈", "note": "Deducibile fino a 5.164,57 € nel 730"},
    {"term": "PAC ETF / Investimenti / Degiro / Directa", "category": "Risparmio & Investimenti", "subcategory": "Investimenti & PAC", "tags": "#investimenti_pac", "icon": "📈", "note": "Piani di accumulo e strumenti finanziari"},
    {"term": "Giroconto tra propri conti / Ricarica Carta", "category": "Risparmio & Investimenti", "subcategory": "Giroconto Interno", "tags": "#giroconto", "icon": "🔄", "note": "Spostamento interno di liquidità (neutro)"},
    {"term": "F24 Imposte / IRPEF / IMU", "category": "Tasse, Fisco & Banche", "subcategory": "F24 & Imposte", "tags": "#f24_imposte", "icon": "🏛️", "note": "Versamento tributi erariali e comunali"},
    {"term": "Canone Carta / Commissioni / Bollo C/C", "category": "Tasse, Fisco & Banche", "subcategory": "Canoni & Commissioni", "tags": "#canoni_commissioni", "icon": "🏛️", "note": "Costi di tenuta conto bancario e carte"}
]

def extract_clean_merchant_pattern(description):
    """
    Extracts a clean, representative merchant pattern from bank descriptions.
    Strips initial boilerplate (POS, BONIFICO, DISPOSIZIONE, etc.), account holder prefixes,
    and cuts off trailing transaction metadata (Spese, Num. Bonifico, RIF, Operazione, timestamps, TRN, etc.).
    """
    if not description:
        return ""
    text = description
    
    # 0. Specialized unification for bank fees / commissions
    if re.search(r'\b(?:COMMISSIONI?\s+BONIFIC[IO]|COMM\.\s*BON\b|COMMISSIONI?\s+PAGAMENTO\s+BOLLETTINO|COMMISSIONI?\s+CBILL|COMMISSIONE\s+TELEPASS)\b', text, flags=re.IGNORECASE):
        if re.search(r'\b(?:COMMISSIONI?\s+BONIFIC[IO]|COMM\.\s*BON\b)', text, flags=re.IGNORECASE):
            return "Commissioni Bonifico"
        elif re.search(r'\b(?:BOLLETTINO|CBILL)\b', text, flags=re.IGNORECASE):
            return "Commissioni Bollettini & CBILL"
        elif re.search(r'\bTELEPASS\b', text, flags=re.IGNORECASE):
            return "Commissioni Telepass"
        return "Commissioni Bancarie"

    # 1. Remove initial transaction types / prefixes
    text = re.sub(r'^\s*(?:PAGAMENTO\s+POS|PAGAMENTO\s+P\.O\.S\.|POS|COMMISSIONI|COMMISSIONE|BONIFICO\s+SEPA|BONIFICO|DISPOSIZIONE|ACCREDITO|STIPENDIO/PENSIONE|STIPENDIO|PENSIONE|ADDEBITO\s+DIRETTO\s+SDD|ADDEBITO\s+SDD|SDD|MAV|RAV|F24|PAGAM\.\s+DELEGA\s+UNIFICATA)\s*[:\-]?\s*', '', text, flags=re.IGNORECASE)
    
    # 2. Remove 'a favore di Nome Cognome' / 'a carico di' if followed by known bank / company / institution
    text = re.sub(r'^\s*(?:a\s+favore\s+di|a\s+carico\s+di|disposto\s+da)\s+.*?(?=\b(?:BCC|BNL|INTESA|UNICREDIT|POSTE|MUTUO|FINANZIARIA|ENEL|ENI|CONAD|COOP|CARREFOUR|MEDIAWORLD|DECATHLON|TELEPASS)\b)', '', text, flags=re.IGNORECASE)

    # 3. Cut off trailing transaction metadata starting at noise keywords
    text = re.sub(r'\b(?:Operazione\b|Op\.?\s*\d|Carta\b|CARTA\b|PAN\b|TRN\b|Mandato\b|per\s+c/|ABI-CAB|Spese\s*:|Spesa\s*:|Num\.?\s*Bonifico|Numero\s*Bonifico|RIF\.?\s*|Riferimento\b|DEB:\s*|ID:\s*|CBI\s+DEL\s*:?|Codice\s+Dispositivo|Cod\.?\s*Disp|del\s+\d{2}[/\-\.]\d{2}|in\s+data\s+\d|ore\s+\d|presso\s+pos|o/c:?|N:\s*\d+/\d+).*', '', text, flags=re.IGNORECASE)
    
    # 4. Remove dates, times, card masks
    text = re.sub(r'\b\d{2}[/\-\.]\d{2}[/\-\.]\d{2,4}\b', ' ', text)
    text = re.sub(r'\b\d{2}[\.:]\d{2}(?:[\.:]\d{2})?\b', ' ', text)
    text = re.sub(r'\*{2,}\d*', ' ', text)
    
    # 5. Remove trailing country codes / noise
    text = re.sub(r'\s+(?:ITA|ITALIA|ITALY)\b', '', text, flags=re.IGNORECASE)
    
    # 6. Clean punctuation & extra spaces
    text = re.sub(r'[*_#]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # If string is too short or empty, fallback to first 2-3 words of original
    if len(text) < 3:
        words = description.split()[:3]
        text = " ".join(words)
        
    return text

def aggregate_transactions_by_merchant(tx_list):
    """
    Groups transactions by clean merchant / recurring pattern and calculates
    frequency count, total spent/received, average ticket, category uniformity, and tx IDs.
    Returns list sorted by count descending, then total volume descending.
    """
    if not tx_list:
        return []

    groups = {}
    for tx in tx_list:
        # Convert row/dict
        t = dict(tx) if not isinstance(tx, dict) else tx
        desc = t.get('description') or t.get('raw_description') or 'Movimento Bancario'
        pattern = extract_clean_merchant_pattern(desc)
        if not pattern:
            pattern = (desc[:30] if len(desc) > 30 else desc).strip()
            
        key = pattern.strip().upper()
        if not key:
            key = "ALTRI MOVIMENTI"

        if key not in groups:
            groups[key] = {
                'pattern': pattern,
                'key': key,
                'count': 0,
                'total_amount': 0.0,
                'abs_total': 0.0,
                'income_count': 0,
                'expense_count': 0,
                'categories': {},
                'subcategories': {},
                'tx_ids': [],
                'dates': [],
                'sample_descriptions': set()
            }

        g = groups[key]
        amt = float(t.get('amount') or 0.0)
        g['count'] += 1
        g['total_amount'] += amt
        g['abs_total'] += abs(amt)
        if amt >= 0:
            g['income_count'] += 1
        else:
            g['expense_count'] += 1

        cat = t.get('category') or 'Non Categorizzato'
        sub = t.get('sub_category') or ''
        g['categories'][cat] = g['categories'].get(cat, 0) + 1
        if sub:
            g['subcategories'][sub] = g['subcategories'].get(sub, 0) + 1

        if t.get('id'):
            g['tx_ids'].append(t['id'])
        if t.get('date'):
            g['dates'].append(t['date'])
        if len(g['sample_descriptions']) < 3:
            g['sample_descriptions'].add(desc[:60])

    # Convert to structured list with metadata
    aggregated_list = []
    for key, g in groups.items():
        count = g['count']
        total = g['total_amount']
        abs_tot = g['abs_total']
        avg = total / count if count > 0 else 0.0
        
        # Determine dominant category
        sorted_cats = sorted(g['categories'].items(), key=lambda x: x[1], reverse=True)
        primary_cat = sorted_cats[0][0] if sorted_cats else 'Non Categorizzato'
        
        # Check if homogeneous & fully categorized
        is_unassigned = primary_cat in ['Non Categorizzato', 'Altro', 'Da Revisionare', '']
        is_homogeneous = len(g['categories']) == 1 and not is_unassigned
        
        # Metadata from MACRO_CATEGORIES
        cat_meta = MACRO_CATEGORIES.get(primary_cat, {"icon": "🏷️", "color": "#94a3b8"})
        icon = cat_meta.get('icon', '🏷️')
        color = cat_meta.get('color', '#94a3b8')
        
        if is_unassigned:
            status_type = "unassigned"
            status_badge = "⚡ Da Assegnare"
            badge_class = "warning"
        elif not is_homogeneous:
            status_type = "mixed"
            status_badge = f"⚠️ Misto ({len(g['categories'])} cat)"
            badge_class = "info"
        else:
            status_type = "assigned"
            status_badge = f"{icon} {primary_cat}"
            badge_class = "success"

        # Formatted dates
        g['dates'].sort(reverse=True)
        latest_date = g['dates'][0] if g['dates'] else ''
        
        aggregated_list.append({
            'pattern': g['pattern'],
            'key': key,
            'count': count,
            'total_amount': round(total, 2),
            'abs_total': round(abs_tot, 2),
            'avg_amount': round(avg, 2),
            'is_income': g['income_count'] > g['expense_count'],
            'primary_category': primary_cat,
            'categories': list(g['categories'].keys()),
            'is_homogeneous': is_homogeneous,
            'is_unassigned': is_unassigned,
            'status_type': status_type,
            'status_badge': status_badge,
            'badge_class': badge_class,
            'icon': icon,
            'color': color,
            'tx_ids': g['tx_ids'],
            'latest_date': latest_date,
            'sample_descriptions': list(g['sample_descriptions'])
        })

    # Sort primarily by frequency count DESC, then total volume DESC
    aggregated_list.sort(key=lambda x: (x['count'], x['abs_total']), reverse=True)
    return aggregated_list

def group_transactions_by_category(tx_list, macro_categories=None):
    """
    Groups transactions hierarchically by Macro-Category -> Merchant Pattern -> Single Transactions.
    Calculates category spending totals, percentages of total period expense, and merchant sub-blocks.
    Returns categories sorted by total expense volume DESC.
    """
    if macro_categories is None:
        macro_categories = MACRO_CATEGORIES

    if not tx_list:
        return []

    # Normalize all items (handles sqlite3.Row or dict)
    tx_list = [dict(t) if not isinstance(t, dict) else t for t in tx_list]

    # Calculate global totals for relative percentages
    total_period_expenses = sum(abs(float(t.get('amount') or 0.0)) for t in tx_list if float(t.get('amount') or 0.0) < 0)
    total_period_income = sum(float(t.get('amount') or 0.0) for t in tx_list if float(t.get('amount') or 0.0) > 0)

    # Initialize bucket for each known macro category + 'Altro / Da Assegnare'
    cat_buckets = {}
    for cat_name, meta in macro_categories.items():
        cat_buckets[cat_name] = {
            'name': cat_name,
            'icon': meta.get('icon', '🏷️'),
            'color': meta.get('color', '#94a3b8'),
            'description': meta.get('description', ''),
            'smart_tags': meta.get('smart_tags', []),
            'total_spent': 0.0,
            'total_income': 0.0,
            'net_amount': 0.0,
            'tx_count': 0,
            'percent_of_expenses': 0.0,
            'merchant_groups': {},
            'transactions': []
        }

    # Fallback bucket for unassigned or custom categories
    unassigned_name = "Da Assegnare / Altro"
    cat_buckets[unassigned_name] = {
        'name': unassigned_name,
        'icon': '⚡',
        'color': '#f59e0b',
        'description': 'Movimenti in attesa di categorizzazione o non assegnati',
        'smart_tags': [],
        'total_spent': 0.0,
        'total_income': 0.0,
        'net_amount': 0.0,
        'tx_count': 0,
        'percent_of_expenses': 0.0,
        'merchant_groups': {},
        'transactions': []
    }

    for raw_tx in tx_list:
        tx = dict(raw_tx) if not isinstance(raw_tx, dict) else raw_tx
        raw_cat = (tx.get('category') or '').strip()
        
        # Determine target bucket
        if raw_cat in macro_categories:
            target_cat = raw_cat
        elif raw_cat in ['Altro', 'Non Categorizzato', 'Da Revisionare', '', None]:
            target_cat = unassigned_name
        else:
            # Custom category or subcategory
            target_cat = raw_cat
            if target_cat not in cat_buckets:
                cat_buckets[target_cat] = {
                    'name': target_cat,
                    'icon': '🏷️',
                    'color': '#38bdf8',
                    'description': '',
                    'smart_tags': [],
                    'total_spent': 0.0,
                    'total_income': 0.0,
                    'net_amount': 0.0,
                    'tx_count': 0,
                    'percent_of_expenses': 0.0,
                    'merchant_groups': {},
                    'transactions': []
                }

        bucket = cat_buckets[target_cat]
        amt = float(tx.get('amount') or 0.0)
        bucket['tx_count'] += 1
        bucket['net_amount'] += amt
        if amt < 0:
            bucket['total_spent'] += abs(amt)
        else:
            bucket['total_income'] += amt

        # Merchant pattern within category
        desc = tx.get('description') or tx.get('raw_description') or 'Movimento Bancario'
        pattern = extract_clean_merchant_pattern(desc)
        if not pattern:
            pattern = (desc[:30] if len(desc) > 30 else desc).strip()
        m_key = pattern.strip().upper() or "ALTRI MOVIMENTI"

        if m_key not in bucket['merchant_groups']:
            bucket['merchant_groups'][m_key] = {
                'pattern': pattern,
                'count': 0,
                'total_amount': 0.0,
                'tx_ids': [],
                'transactions': []
            }
        
        m_group = bucket['merchant_groups'][m_key]
        m_group['count'] += 1
        m_group['total_amount'] += amt
        if tx.get('id'):
            m_group['tx_ids'].append(tx['id'])
        m_group['transactions'].append(tx)

        bucket['transactions'].append(tx)

    # Finalize list of category folders
    result_folders = []
    for cat_name, bucket in cat_buckets.items():
        if bucket['tx_count'] == 0:
            continue  # Only include folders with transactions for clean UI

        bucket['total_spent'] = round(bucket['total_spent'], 2)
        bucket['total_income'] = round(bucket['total_income'], 2)
        bucket['net_amount'] = round(bucket['net_amount'], 2)

        if total_period_expenses > 0 and bucket['total_spent'] > 0:
            bucket['percent_of_expenses'] = round((bucket['total_spent'] / total_period_expenses) * 100, 1)
        else:
            bucket['percent_of_expenses'] = 0.0

        # Sort merchants inside category by count DESC, then total spend DESC
        merchants_list = list(bucket['merchant_groups'].values())
        merchants_list.sort(key=lambda m: (m['count'], abs(m['total_amount'])), reverse=True)
        bucket['merchants'] = merchants_list

        # Sort transactions inside category by date DESC
        bucket['transactions'].sort(key=lambda x: str(x.get('date') or ''), reverse=True)

        result_folders.append(bucket)

    # Sort categories:
    # 1. Unassigned first if it has pending items (to keep triage attention high)
    # 2. Categories with highest expenses DESC
    # 3. Categories with highest income DESC
    def folder_sort_key(f):
        is_unassigned = 1 if f['name'] == unassigned_name else 0
        return (is_unassigned, f['total_spent'], f['total_income'], f['tx_count'])

    result_folders.sort(key=folder_sort_key, reverse=True)
    return result_folders

def load_workspace_category_rules(workspace_id):
    """Loads active custom rules for a workspace ordered by priority."""
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, pattern, match_type, category, sub_category, tags, priority
        FROM category_rules
        WHERE workspace_id = ?
        ORDER BY priority DESC, id DESC
    ''', (workspace_id,))
    rules = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rules

def save_or_update_category_rule(workspace_id, pattern, category, sub_category="", tags="", match_type="CONTAINS"):
    """Inserts or updates a custom category rule for a workspace."""
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clean_pat = pattern.strip()
    if not clean_pat:
        conn.close()
        return None

    # Check if exact rule pattern already exists
    cursor.execute('''
        SELECT id FROM category_rules
        WHERE workspace_id = ? AND LOWER(pattern) = LOWER(?)
    ''', (workspace_id, clean_pat))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute('''
            UPDATE category_rules
            SET category = ?, sub_category = ?, tags = ?, match_type = ?, created_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (category, sub_category, tags, match_type, existing['id']))
        rule_id = existing['id']
    else:
        cursor.execute('''
            INSERT INTO category_rules (workspace_id, pattern, match_type, category, sub_category, tags, priority)
            VALUES (?, ?, ?, ?, ?, ?, 10)
        ''', (workspace_id, clean_pat, match_type, category, sub_category, tags))
        rule_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return rule_id

def build_dynamic_smart_tags(personalization_data=None):
    """
    Enriches CATEGORY_SMART_TAGS with custom personalized tags (e.g. #luciano, #luna, #mutuo).
    Returns a cloned and enhanced dictionary.
    """
    tags_dict = copy.deepcopy(CATEGORY_SMART_TAGS)
    if not personalization_data:
        return tags_dict

    children_str = personalization_data.get("children_names") or ""
    if children_str:
        kids = [k.strip() for k in children_str.replace(";", ",").split(",") if k.strip()]
        for kid in kids:
            k_slug = kid.lower().replace(" ", "_").replace("#", "")
            kid_tag = {
                "code": f"#{k_slug}",
                "label": f"👶 {kid}",
                "icon": "👶",
                "subcat": "Abbigliamento Figli",
                "is_personalized": True
            }
            kid_asilo_tag = {
                "code": f"#asilo_{k_slug}",
                "label": f"🎒 Asilo {kid}",
                "icon": "🎒",
                "subcat": "Asilo & Scuola",
                "is_personalized": True
            }
            for cat_key in ["Shopping & Abbigliamento", "Salute & Benessere"]:
                if cat_key in tags_dict:
                    if not any(t.get("code") == f"#{k_slug}" for t in tags_dict[cat_key]):
                        tags_dict[cat_key].insert(0, kid_tag)

    pets_str = personalization_data.get("pets_names") or ""
    if pets_str:
        pets = [p.strip() for p in pets_str.replace(";", ",").split(",") if p.strip()]
        for pet in pets:
            p_slug = pet.lower().replace(" ", "_").replace("#", "")
            pet_tag = {
                "code": f"#{p_slug}",
                "label": f"🐾 {pet}",
                "icon": "🐾",
                "subcat": "Animali & Pet",
                "is_personalized": True
            }
            if "Salute & Benessere" in tags_dict:
                if not any(t.get("code") == f"#{p_slug}" for t in tags_dict["Salute & Benessere"]):
                    tags_dict["Salute & Benessere"].insert(0, pet_tag)

    housing = personalization_data.get("housing_type") or "MUTUO"
    bank = personalization_data.get("mortgage_bank") or ""
    if housing == "MUTUO" and "Casa & Immobili" in tags_dict:
        m_label = f"Mutuo {bank}".strip() if bank else "Mutuo"
        mutuo_tag = {"code": "#mutuo", "label": f"🏠 {m_label}", "icon": "🏠", "subcat": "Mutuo", "is_personalized": True}
        if not any(t.get("code") == "#mutuo" for t in tags_dict["Casa & Immobili"]):
            tags_dict["Casa & Immobili"].insert(0, mutuo_tag)

    return tags_dict

def seed_personalization_rules(workspace_id, personalization_data):
    """
    Generates tailored category_rules in workspace database based on user's profile.
    Returns list of newly created or updated rule patterns.
    """
    if not workspace_id or not personalization_data:
        return []

    created_patterns = []

    # 1. Children Merchants
    children_str = personalization_data.get("children_names") or ""
    if children_str:
        kids = [k.strip() for k in children_str.replace(";", ",").split(",") if k.strip()]
        primary_kid_slug = kids[0].lower().replace(" ", "_").replace("#", "") if kids else "figlio"
        all_kids_tags = " ".join([f"#{k.lower().replace(' ', '_').replace('#', '')}" for k in kids])

        kid_patterns = [
            ("ORIGINAL MARINES", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("VILLA BEBE", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("CHICCO", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("PRIMIGI", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("IDEXE", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("OKAIDI", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("IO BIMBO", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("PRENATAL", "Shopping & Abbigliamento", "Abbigliamento Figli", f"{all_kids_tags} #abbigliamento #bambini"),
            ("ASILO NIDO", "Shopping & Abbigliamento", "Asilo & Scuola", f"#{primary_kid_slug} #asilo #scuola"),
            ("SCUOLA MATERNA", "Shopping & Abbigliamento", "Asilo & Scuola", f"#{primary_kid_slug} #asilo #scuola"),
        ]
        for pat, cat, subcat, tags in kid_patterns:
            save_or_update_category_rule(workspace_id, pat, cat, subcat, tags, match_type='CONTAINS')
            created_patterns.append(pat)

    # 2. Pet Merchants
    pets_str = personalization_data.get("pets_names") or ""
    if pets_str:
        pets = [p.strip() for p in pets_str.replace(";", ",").split(",") if p.strip()]
        all_pets_tags = " ".join([f"#{p.lower().replace(' ', '_').replace('#', '')}" for p in pets])

        pet_patterns = [
            ("ARCAPLANET", "Salute & Benessere", "Animali & Pet", f"{all_pets_tags} #animali #pet_food"),
            ("ISOLA DEI TESORI", "Salute & Benessere", "Animali & Pet", f"{all_pets_tags} #animali #pet_food"),
            ("MAXIZOO", "Salute & Benessere", "Animali & Pet", f"{all_pets_tags} #animali #pet_food"),
            ("AMICI DI CASA COOP", "Salute & Benessere", "Animali & Pet", f"{all_pets_tags} #animali #pet_food"),
            ("CLINICA VETERINARIA", "Salute & Benessere", "Veterinario", f"{all_pets_tags} #animali #veterinario"),
            ("AMBULATORIO VETERINARIO", "Salute & Benessere", "Veterinario", f"{all_pets_tags} #animali #veterinario"),
        ]
        for pat, cat, subcat, tags in pet_patterns:
            save_or_update_category_rule(workspace_id, pat, cat, subcat, tags, match_type='CONTAINS')
            created_patterns.append(pat)

    # 3. Mortgage / Housing
    bank = personalization_data.get("mortgage_bank") or ""
    if bank:
        clean_bank = bank.upper().strip()
        save_or_update_category_rule(workspace_id, f"MUTUO {clean_bank}", "Casa & Immobili", "Mutuo", "#mutuo", match_type='CONTAINS')
        save_or_update_category_rule(workspace_id, f"RATA MUTUO {clean_bank}", "Casa & Immobili", "Mutuo", "#mutuo", match_type='CONTAINS')
        created_patterns.extend([f"MUTUO {clean_bank}", f"RATA MUTUO {clean_bank}"])

    return created_patterns

def normalize_for_matching(text):
    """
    Normalizes a text string for fuzzy / whitespace-agnostic and symbol-agnostic rule matching.
    Converts to lowercase, converts punctuation and special symbols (*, -, _, /, ., ,, :, #, @) to space,
    and strips redundant whitespace.
    """
    if not text:
        return ""
    t = re.sub(r'[*_\-/#\.,:;@\(\)\[\]\+]+', ' ', str(text).lower())
    return re.sub(r'\s+', ' ', t).strip()

def matches_rule_pattern(pattern, description, raw_description="", match_type="CONTAINS"):
    """
    Checks if a pattern matches a transaction description or raw_description,
    supporting standard CONTAINS, token-level matching, EXACT, and REGEX.
    """
    if not pattern:
        return False

    pat_clean = str(pattern).strip()
    pat_lower = pat_clean.lower()
    p_norm = normalize_for_matching(pat_clean)

    d_lower = (str(description) if description else "").strip().lower()
    raw_lower = (str(raw_description) if raw_description else "").strip().lower()

    d_norm = normalize_for_matching(description)
    raw_norm = normalize_for_matching(raw_description)

    mtype = (match_type or 'CONTAINS').upper()

    if mtype == 'EXACT':
        return (p_norm and (p_norm == d_norm or p_norm == raw_norm)) or (pat_lower and (pat_lower == d_lower or pat_lower == raw_lower))

    if mtype == 'REGEX':
        try:
            return bool(re.search(pat_clean, description or '', re.IGNORECASE) or (raw_description and re.search(pat_clean, raw_description, re.IGNORECASE)))
        except Exception:
            return pat_lower in d_lower or pat_lower in raw_lower

    # CONTAINS (Default smart matching)
    # 1. Direct raw substring match
    if pat_lower and (pat_lower in d_lower or (raw_lower and pat_lower in raw_lower)):
        return True

    # 2. Normalized contiguous substring match
    if p_norm and (p_norm in d_norm or (raw_norm and p_norm in raw_norm)):
        return True

    # 3. All individual tokens match (e.g. pattern has 'PAYPAL' and 'GEDIMPIANTI')
    tokens = [t for t in p_norm.split() if len(t) > 1]
    if tokens:
        if all(t in d_norm for t in tokens):
            return True
        if raw_norm and all(t in raw_norm for t in tokens):
            return True

    return False

def apply_rule_retroactively(workspace_id, pattern, category, sub_category="", tags="", match_type="CONTAINS"):
    """
    Updates all existing matching transactions in the workspace with the new category and tags,
    using smart normalized matching.
    Returns the number of affected rows.
    """
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    clean_pat = pattern.strip()
    if not clean_pat:
        conn.close()
        return 0

    cursor.execute("SELECT id, description, raw_description, category, sub_category, tags FROM transactions WHERE workspace_id = ?", (workspace_id,))
    rows = cursor.fetchall()
    
    matching_ids = []
    for r in rows:
        if matches_rule_pattern(clean_pat, r['description'], r['raw_description'], match_type):
            matching_ids.append(r['id'])

    affected = 0
    if matching_ids:
        placeholders = ','.join('?' for _ in matching_ids)
        params = [category, sub_category if sub_category else None]
        if tags:
            params.append(tags)
            sql = f"UPDATE transactions SET category = ?, sub_category = ?, tags = ? WHERE id IN ({placeholders}) AND workspace_id = ?"
        else:
            sql = f"UPDATE transactions SET category = ?, sub_category = ? WHERE id IN ({placeholders}) AND workspace_id = ?"
        params.extend(matching_ids)
        params.append(workspace_id)
        cursor.execute(sql, params)
        affected = cursor.rowcount
        conn.commit()

    conn.close()
    return affected

def apply_all_workspace_rules(workspace_id):
    """
    Applies all active category rules of a workspace across all transactions in the workspace.
    Returns the count of updated transactions.
    """
    from database import get_db_connection
    rules = load_workspace_category_rules(workspace_id)
    if not rules:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, raw_description, amount, is_transfer FROM transactions WHERE workspace_id = ?", (workspace_id,))
    txs = cursor.fetchall()

    total_updated = 0
    for tx in txs:
        desc = tx['description'] or tx['raw_description'] or ''
        for rule in rules:
            if matches_rule_pattern(rule['pattern'], desc, tx['raw_description'], rule.get('match_type', 'CONTAINS')):
                cat = rule['category']
                sub_cat = rule.get('sub_category') or None
                tags = rule.get('tags') or None
                if tags:
                    cursor.execute("UPDATE transactions SET category = ?, sub_category = ?, tags = ? WHERE id = ? AND workspace_id = ?", (cat, sub_cat, tags, tx['id'], workspace_id))
                else:
                    cursor.execute("UPDATE transactions SET category = ?, sub_category = ? WHERE id = ? AND workspace_id = ?", (cat, sub_cat, tx['id'], workspace_id))
                total_updated += 1
                break

    conn.commit()
    conn.close()
    return total_updated

# ---------------------------------------------------------
# 3. CATEGORIZER LOGIC
# ---------------------------------------------------------
def categorize_transaction(description, amount, is_transfer=False, custom_rules=None):
    """
    Classifies a transaction into a Macro-Family and Sub-Category.
    Returns: (category, sub_category, tags, is_transfer_flag)
    """
    clean_desc = (description or "").strip()
    desc_lower = clean_desc.lower()
    
    # 1. Check User-Defined Custom Rules first using Smart Pattern Matching
    if custom_rules:
        for rule in custom_rules:
            pat = rule.get('pattern', '')
            mtype = rule.get('match_type', 'CONTAINS')
            if matches_rule_pattern(pat, clean_desc, match_type=mtype):
                return rule['category'], rule.get('sub_category', ''), rule.get('tags', ''), is_transfer

    # 2. Check Giroconti / Internal Transfers / Ricarica Prepagata
    transfer_keywords = ["giroconto", "proprio favore", "ric.prep", "carta prepagata ric", "ricarica postepay", "postagiro"]
    if any(k in desc_lower for k in transfer_keywords):
        return "Risparmio & Futuro", "Giroconto Interno", "#giroconto", True

    # 3. Match Built-in Regex Rules
    for pattern, cat, sub_cat, tags in RULES_PATTERNS:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            # Special check: if income and classified as expense, adjust if needed
            if amount > 0 and cat not in ["Lavoro & Entrate", "Risparmio & Futuro"]:
                if "rimborso" in desc_lower or "reso" in desc_lower:
                    tags = tags + " #rimborso" if tags else "#rimborso"
                    return cat, sub_cat, tags.strip(), is_transfer
            if cat == "Salute & Benessere" and "#detraibile_730" not in tags:
                tags = (tags + " #detraibile_730").strip()
            if cat == "Risparmio & Futuro" and sub_cat == "Giroconto Interno" and "#giroconto" not in tags:
                tags = (tags + " #giroconto").strip()
            return cat, sub_cat, tags, is_transfer

    # 4. Fallback based on amount sign
    if amount > 0:
        return "Lavoro & Entrate", "Altre Entrate", "", is_transfer
    else:
        return "Altro", "", "", is_transfer

# Italian Month Translation Dictionary
MONTHS_IT = {
    'gennaio': '01', 'gen': '01',
    'febbraio': '02', 'feb': '02',
    'marzo': '03', 'mar': '03',
    'aprile': '04', 'apr': '04',
    'maggio': '05', 'mag': '05',
    'giugno': '06', 'giu': '06',
    'luglio': '07', 'lug': '07',
    'agosto': '08', 'ago': '08',
    'settembre': '09', 'set': '09', 'sett': '09',
    'ottobre': '10', 'ott': '10',
    'novembre': '11', 'nov': '11',
    'dicembre': '12', 'dic': '12'
}

# ---------------------------------------------------------
# 4. RESILIENT DATE & AMOUNT NORMALIZERS
# ---------------------------------------------------------
def parse_date_resilient(val):
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime("%Y-%m-%d")
        
    val_str = str(val).strip().lower()
    if not val_str or val_str in ['nan', 'nat', '-', '""']:
        return None
        
    # Replace Italian month names with month numbers
    for m_it, m_num in MONTHS_IT.items():
        if m_it in val_str:
            val_str = re.sub(r'\b' + m_it + r'\b', m_num, val_str)
            break
            
    # Extract digits
    parts = re.findall(r'\d+', val_str)
    if len(parts) >= 3:
        p0, p1, p2 = int(parts[0]), int(parts[1]), int(parts[2])
        if p0 > 1900:  # Format: YYYY-MM-DD
            year, month, day = p0, p1, p2
        else:          # Format: DD-MM-YYYY
            day, month, year = p0, p1, p2
            if year < 100:
                year += 2000
        if 1 <= month <= 12 and 1 <= day <= 31 and 1990 <= year <= 2100:
            return f"{year:04d}-{month:02d}-{day:02d}"
            
    # Fallback with pandas to_datetime
    try:
        dt = pd.to_datetime(val_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def parse_amount_resilient(val):
    if val is None or pd.isna(val) or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    s = str(val).strip()
    s = s.replace("€", "").replace("EUR", "").replace("eur", "").strip()
    
    # Handle negative in brackets e.g. (150.00)
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
        
    # Handle trailing minus e.g. 150,00-
    if s.endswith("-"):
        s = "-" + s[:-1]
        
    # Handle European 1.250,50 vs American 1,250.50
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # European: dots are thousands, comma is decimal
            s = s.replace(".", "").replace(",", ".")
        else:
            # American: commas are thousands, dot is decimal
            s = s.replace(",", "")
    elif "," in s:
        # Only comma: European decimal
        s = s.replace(",", ".")
        
    # Remove any stray characters
    s = re.sub(r"[^\d.-]", "", s)
    try:
        return float(s)
    except ValueError:
        return 0.0

# ---------------------------------------------------------
# 5. HEADER HUNTER: Find Table Start in Bank Statement
# ---------------------------------------------------------
def find_header_row(rows):
    """
    Scans the first 25 rows and finds the row containing bank columns.
    Returns: (header_index, col_mapping_dict)
    """
    DATE_KW = ["data", "date", "data contabile", "data valuta", "data operazione", "booking date", "value date"]
    DESC_KW = ["descrizione", "causale", "dettagli", "beneficiario", "movimento", "operazione", "description", "details", "note", "motivo"]
    AMOUNT_KW = ["importo", "amount", "totale", "valuta importo", "valore"]
    IN_KW = ["entrate", "accrediti", "avere", "in", "accredito", "income", "credit"]
    OUT_KW = ["uscite", "addebiti", "dare", "out", "addebito", "expense", "debit"]
    
    best_row_idx = -1
    best_score = 0
    best_mapping = {}
    
    for idx, row in enumerate(rows[:25]):
        row_str_list = [str(c).strip().lower() for c in row if c is not None]
        if not row_str_list:
            continue
            
        mapping = {"date": None, "desc": None, "amount": None, "in": None, "out": None}
        score = 0
        
        for c_idx, cell in enumerate(row_str_list):
            if not cell:
                continue
            if any(k in cell for k in DATE_KW) and mapping["date"] is None:
                mapping["date"] = c_idx
                score += 3
            elif any(k in cell for k in DESC_KW) and mapping["desc"] is None:
                mapping["desc"] = c_idx
                score += 3
            elif any(k in cell for k in AMOUNT_KW) and mapping["amount"] is None:
                mapping["amount"] = c_idx
                score += 4
            elif any(cell == k or f" {k}" in cell or f"{k} " in cell for k in IN_KW) and mapping["in"] is None:
                mapping["in"] = c_idx
                score += 2
            elif any(cell == k or f" {k}" in cell or f"{k} " in cell for k in OUT_KW) and mapping["out"] is None:
                mapping["out"] = c_idx
                score += 2
                
        # Must have at least Date + Desc + (Amount OR (In and Out))
        has_amount = (mapping["amount"] is not None) or (mapping["in"] is not None and mapping["out"] is not None)
        if mapping["date"] is not None and mapping["desc"] is not None and has_amount:
            score += 5
            if score > best_score:
                best_score = score
                best_row_idx = idx
                best_mapping = mapping
                
    return best_row_idx, best_mapping

# ---------------------------------------------------------
# 5. ACCOUNT METADATA EXTRACTOR (BPER, Poste, BCC, Revolut, etc.)
# ---------------------------------------------------------
def extract_account_metadata(raw_rows, filename=""):
    """
    Extracts bank institute, IBAN, account/card number, holder name and statement balance
    from the header rows of the bank export file.
    """
    meta = {
        "bank_name": "Conto Bancario",
        "account_type": "CHECKING",
        "iban": None,
        "account_number": None,
        "card_pan": None,
        "holder_name": None,
        "extracted_balance": None
    }
    
    if not raw_rows:
        return meta
        
    text_block = ""
    # Only scan header metadata before data rows (first 16 rows)
    for row in raw_rows[:16]:
        row_str = " ".join([str(c).strip() for c in row if c is not None and not pd.isna(c) and str(c).strip() != ""])
        if row_str:
            text_block += row_str + "\n"
        
    text_lower = text_block.lower()
    filename_lower = (filename or "").lower()
    
    # 1. Bank Detection
    if "bper" in text_lower or "bper" in filename_lower or "modena" in text_lower:
        meta["bank_name"] = "BPER Banca"
    elif "bancoposta" in text_lower or ("poste" in text_lower and "postepay" not in text_lower and "postepay" not in filename_lower):
        meta["bank_name"] = "Poste Italiane (BancoPosta)"
    elif "postepay" in text_lower or "postepay" in filename_lower:
        meta["bank_name"] = "Poste Italiane (Postepay)"
        meta["account_type"] = "CARD"
    elif "bcc" in text_lower or "credito cooperativo" in text_lower:
        meta["bank_name"] = "BCC - Credito Cooperativo"
    elif "intesa" in text_lower or "sanpaolo" in text_lower:
        meta["bank_name"] = "Intesa Sanpaolo"
    elif "unicredit" in text_lower:
        meta["bank_name"] = "UniCredit"
    elif "fineco" in text_lower:
        meta["bank_name"] = "Fineco Bank"
    elif "revolut" in text_lower or "revolut" in filename_lower:
        meta["bank_name"] = "Revolut"
    elif "bbva" in text_lower:
        meta["bank_name"] = "BBVA"
    else:
        meta["bank_name"] = "Banca Principale"

    # 3. IBAN
    iban_match = re.search(r'\b(IT\d{2}[A-Z]\d{22})\b', text_block, re.IGNORECASE)
    if iban_match:
        meta["iban"] = iban_match.group(1).upper()

    # 4. PAN Card
    pan_match = re.search(r'(\*{2,4}\s*\*{2,4}\s*\*{2,4}\s*\d{4})', text_block)
    if pan_match:
        meta["card_pan"] = re.sub(r'\s+', ' ', pan_match.group(1)).strip()

    # 5. Account Number
    acc_num_match = re.search(r'(?:conto\s+corrente|conto\s+bancoposta\s+n\.?|n\.\s*conto|c/c\s*n\.?)[:\s]+(\d{6,16})', text_block, re.IGNORECASE)
    if acc_num_match:
        meta["account_number"] = acc_num_match.group(1).strip()

    # 6. Statement Balance
    bal_match = re.search(r'(?:saldo\s+disponibile|saldo\s+contabile|saldo\s+finale|saldo\s+al\s+[\d/.]+)[:\s]+([+-]?\d{1,3}(?:\.\d{3})*,\d{2})', text_block, re.IGNORECASE)
    if bal_match:
        meta["extracted_balance"] = parse_amount_resilient(bal_match.group(1))

    # 2. Account Type (BancoPosta, Conto Corrente, and statements with official balance are CHECKING)
    if "bancoposta" in text_lower or "conto corrente" in text_lower or "c/c" in text_lower or meta.get("iban") or meta.get("account_number") or ("conto" in filename_lower and "postepay" not in filename_lower):
        meta["account_type"] = "CHECKING"
    elif "postepay" in filename_lower or "prepagata" in filename_lower or ("carta" in filename_lower and "conto" not in filename_lower) or "carta prepagata" in text_lower:
        meta["account_type"] = "CARD"
    elif "deposito" in text_lower or "risparmio" in text_lower:
        meta["account_type"] = "SAVINGS"
    else:
        meta["account_type"] = "CHECKING"

    # 7. Holder Name
    holder_match = re.search(r'(?:intestatari[o]?|intestato\s+a|titolare|nominativo)[:\s]+([A-Za-z\s\.\'\-]{3,60}?)(?=\s+saldo|\s{2,}|\n|\r|$)', text_block, re.IGNORECASE)
    if holder_match:
        cand_holder = holder_match.group(1).strip()
        cand_holder = re.split(r'(?:saldo|data|iban|filiale|modena)', cand_holder, flags=re.IGNORECASE)[0].strip()
        # Handle repeated holder strings e.g. "MACERA MASCITELLI NUNZIA MACERA MASCITELLI CESARE"
        words = cand_holder.split()
        if len(words) >= 4 and words[0].lower() == words[len(words)//2].lower():
            words = words[:len(words)//2]
        cand_holder_clean = " ".join(w.capitalize() for w in words)
        if len(cand_holder_clean) >= 3:
            meta["holder_name"] = cand_holder_clean

    return meta



# ---------------------------------------------------------
# 6. UNIVERSAL PARSER (CSV / Excel)
# ---------------------------------------------------------
def parse_bank_file(file_content, filename, workspace_id, account_id=None, custom_rules=None):
    """
    Parses any bank CSV or Excel file in-memory.
    Returns: dict { 'success': True/False, 'account_meta': {...}, 'transactions': [...], 'total_parsed': int, 'error': str }
    """
    if custom_rules is None and workspace_id:
        try:
            custom_rules = load_workspace_category_rules(workspace_id)
        except Exception as e:
            print(f"Warning loading custom rules: {e}")
            custom_rules = []

    filename_lower = filename.lower()
    raw_rows = []
    
    # A. Process Excel (.xlsx, .xls)
    if filename_lower.endswith(('.xlsx', '.xls')):
        # Ensure bytes stream
        if isinstance(file_content, (bytes, bytearray)):
            excel_bytes = io.BytesIO(file_content)
            raw_bytes = file_content
        else:
            raw_bytes = file_content.read()
            excel_bytes = io.BytesIO(raw_bytes)
            
        try:
            engine = 'xlrd' if filename_lower.endswith('.xls') else 'openpyxl'
            try:
                df = pd.read_excel(excel_bytes, header=None, engine=engine)
            except Exception:
                excel_bytes.seek(0)
                df = pd.read_excel(excel_bytes, header=None) # default pandas engine fallback
            raw_rows = df.values.tolist()
        except Exception as e:
            # Fallback 1: Some banks export HTML tables with .xls extension
            try:
                html_dfs = pd.read_html(io.BytesIO(raw_bytes))
                if html_dfs:
                    raw_rows = html_dfs[0].values.tolist()
                else:
                    raise Exception("No HTML tables found")
            except Exception:
                # Fallback 2: Try decoding as CSV text disguised as Excel
                try:
                    text = raw_bytes.decode('utf-8', errors='ignore')
                    if ";" in text or "," in text:
                        reader = csv.reader(io.StringIO(text), delimiter=';' if ';' in text else ',')
                        raw_rows = list(reader)
                    else:
                        raise Exception("Not CSV")
                except Exception:
                    return {"success": False, "error": f"Errore lettura file Excel: {str(e)}", "transactions": []}
            
    # B. Process CSV with Encoding & Delimiter Auto-Detection
    else:
        # Read bytes
        if isinstance(file_content, (bytes, bytearray)):
            data_bytes = file_content
        else:
            data_bytes = file_content.read()
            
        encodings_to_try = ["utf-8-sig", "utf-8", "cp1252", "iso-8859-1", "latin1"]
        decoded_text = None
        for enc in encodings_to_try:
            try:
                decoded_text = data_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
                
        if not decoded_text:
            return {"success": False, "error": "Formato encoding del file non riconosciuto.", "transactions": []}
            
        # Determine candidate delimiters based on character frequencies
        lines = [l for l in decoded_text.splitlines() if l.strip()]
        delim_counts = {';': 0, ',': 0, '\t': 0, '|': 0}
        for l in lines:
            for d in delim_counts:
                delim_counts[d] += l.count(d)
                
        # Sort candidate delimiters by frequency
        candidate_delimiters = sorted(delim_counts.keys(), key=lambda d: delim_counts[d], reverse=True)
        if not candidate_delimiters or delim_counts[candidate_delimiters[0]] == 0:
            candidate_delimiters = [";", ",", "\t", "|"]

        best_result = None
        for delimiter in candidate_delimiters:
            reader = csv.reader(io.StringIO(decoded_text), delimiter=delimiter)
            curr_rows = [row for row in reader if any(field.strip() for field in row)]
            if not curr_rows:
                continue
            h_idx, mapping = find_header_row(curr_rows)
            if h_idx != -1 and mapping.get("date") is not None and (mapping.get("amount") is not None or (mapping.get("in") is not None and mapping.get("out") is not None)):
                raw_rows = curr_rows
                header_idx = h_idx
                best_mapping = mapping
                break
        else:
            # Fallback to the most frequent delimiter even if header confidence was low
            delimiter = candidate_delimiters[0]
            reader = csv.reader(io.StringIO(decoded_text), delimiter=delimiter)
            raw_rows = [row for row in reader if any(field.strip() for field in row)]
            header_idx, best_mapping = find_header_row(raw_rows)

    # C. Verify Header Hunter results
    if 'header_idx' not in locals() or header_idx == -1 or best_mapping.get("date") is None:
        header_idx, best_mapping = find_header_row(raw_rows)
        
    mapping = best_mapping
    if header_idx == -1 or mapping.get("date") is None:
        return {
            "success": False, 
            "error": "Non è stato possibile identificare automaticamente le colonne (Data, Descrizione, Importo). Assicurati che il file contenga queste intestazioni.",
            "transactions": []
        }

    # D. Extract and Normalize Data Rows
    parsed_transactions = []
    data_rows = raw_rows[header_idx + 1:]
    
    for row in data_rows:
        if not row:
            continue
            
        # Date
        date_raw = row[mapping["date"]] if mapping["date"] < len(row) else None
        clean_date = parse_date_resilient(date_raw)
        if not clean_date:
            continue # Skip summary/footer lines that don't have a valid date
            
        # Description
        desc_raw = str(row[mapping["desc"]]).strip() if mapping["desc"] < len(row) else "Movimento Bancario"
        if not desc_raw or desc_raw.lower() in ["totale", "saldo iniziale", "saldo finale", "disclaimer"]:
            continue
            
        # Amount
        amount = 0.0
        if mapping["amount"] is not None and mapping["amount"] < len(row):
            amount = parse_amount_resilient(row[mapping["amount"]])
        elif mapping["in"] is not None and mapping["out"] is not None:
            in_val = parse_amount_resilient(row[mapping["in"]]) if mapping["in"] < len(row) else 0.0
            out_val = parse_amount_resilient(row[mapping["out"]]) if mapping["out"] < len(row) else 0.0
            if in_val != 0.0:
                amount = abs(in_val)
            elif out_val != 0.0:
                amount = -abs(out_val)
                
        if amount == 0.0:
            continue

        # Categorize
        category, sub_category, tags, is_transfer = categorize_transaction(
            desc_raw, amount, custom_rules=custom_rules
        )
        
        # SHA-256 Fingerprint for Deduplication
        hash_input = f"{workspace_id}_{account_id}_{clean_date}_{amount:.2f}_{desc_raw.strip().lower()}"
        tx_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        
        parsed_transactions.append({
            "date": clean_date,
            "description": desc_raw,
            "raw_description": desc_raw,
            "amount": amount,
            "category": category,
            "sub_category": sub_category,
            "tags": tags,
            "is_transfer": 1 if is_transfer else 0,
            "import_hash": tx_hash
        })

    # E. Extract Account Metadata
    account_meta = extract_account_metadata(raw_rows, filename)

    return {
        "success": True,
        "account_meta": account_meta,
        "transactions": parsed_transactions,
        "total_parsed": len(parsed_transactions),
        "header_row": header_idx
    }
