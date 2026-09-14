import re
import calendar
from datetime import datetime
from database import get_db_connection
from services.bank_importer import MACRO_CATEGORIES

MONTH_NAMES_IT = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno",
    7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
}

MONTH_NAMES_IT_SHORT = {
    1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
    7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
}

def format_clean_tag_display(raw_name, tags="", match_pattern="", category="", amount=0.0):
    """
    Restituisce (display_title, clean_tag, tag_badge) puliti basandosi su tag e regole,
    evitando etichette generiche bancarie (es. DISPOSIZIONE, BONIFICO, PAGAMENTI DIVERSI).
    """
    raw_name_str = (raw_name or '').strip()
    tags_str = (tags or '').strip()
    pat_str = (match_pattern or '').strip().lstrip('#')
    cat_str = (category or '').strip()
    
    # Riconoscimento tag primario pulito
    primary_tag = None
    if tags_str:
        tag_list = [t.strip().lstrip('#') for t in tags_str.split() if t.strip()]
        for t in tag_list:
            t_low = t.lower()
            if t_low not in ['spese', 'generale', 'altro', 'casa', 'bonifico']:
                primary_tag = t
                break
        if not primary_tag and tag_list:
            primary_tag = tag_list[0]
            
    combined_hints = f"{raw_name_str} {tags_str} {pat_str} {cat_str}".lower()
    
    _generic_names = ('disposizione', 'bonifico', 'pagamento', 'rata', 'accredito')
    _is_generic = any(raw_name_str.lower().startswith(g) for g in _generic_names) or raw_name_str.upper() in ('DISPOSIZIONE', 'BONIFICO', 'PAGAMENTO')
    _is_mortgage_by_amt = (900.0 <= abs(amount) <= 1200.0 and _is_generic)
    
    # Helper per match su parole intere
    def has_kw(kw, text):
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE))

    # Commissioni bancarie hanno priorità se importo ridotto o parola chiave commissioni
    _is_commission = any(has_kw(k, combined_hints) for k in ['commissioni', 'comm.', 'commissione']) or (abs(amount) <= 1.5 and any(has_kw(k, combined_hints) for k in ['cbill', 'pagopa', 'bonifico', 'prepaga', 'directa']))
    
    # Riconoscimento intelligente dei casi noti (Directa/Investimenti hanno priorità su euristica importo mutuo)
    if _is_commission:
        display_title = "Canoni e Commissioni Bancarie"
        clean_tag = "CANONI_COMMISSIONI"
    elif any(has_kw(k, combined_hints) for k in ['directa', 'investimenti_pac', 'pac', 'etf']) and abs(amount) > 1.5:
        display_title = "Investimento PAC (Directa)"
        clean_tag = "DIRECTA"
    elif any(has_kw(k, combined_hints) for k in ['mutuo', 'prima casa']) or _is_mortgage_by_amt:
        display_title = "Rata Mutuo (BCC)"
        clean_tag = "MUTUO"
    elif has_kw('tari', combined_hints) or has_kw('pagopa', combined_hints) or (has_kw('comune', combined_hints) and has_kw('aquila', combined_hints)):
        display_title = "TARI (Tassa Rifiuti)"
        clean_tag = "TARI"
    elif has_kw('bollo', combined_hints) or has_kw('aci', combined_hints):
        display_title = "Bollo Auto (ACI)"
        clean_tag = "BOLLO"
    elif any(has_kw(k, combined_hints) for k in ['officina', 'tagliando', 'revisione']):
        display_title = "Manutenzione Auto / Tagliando"
        clean_tag = "TAGLIANDO"
    elif 'iliad' in combined_hints:
        if abs(amount) > 15.0 or 'fibra' in combined_hints:
            display_title = "Fibra Casa (Iliad)"
            clean_tag = "FIBRA"
        else:
            display_title = "SIM Mobile (Iliad)"
            clean_tag = "SIM"
    elif 'enel' in combined_hints:
        display_title = "Luce & Gas (Enel)"
        clean_tag = "BOLLETTE"
    elif 'telepass' in combined_hints:
        display_title = "Telepass & Autostrade"
        clean_tag = "TELEPASS"
    elif 'canone' in combined_hints and 'carta' in combined_hints or 'canone mensile' in combined_hints:
        display_title = "Canone Mensile Carta BPER"
        clean_tag = "CANONE"
    elif 'stipendio' in combined_hints or 'emolumenti' in combined_hints:
        display_title = "Stipendio Mensile"
        clean_tag = "STIPENDIO"
    elif primary_tag:
        display_title = primary_tag.replace('_', ' ').title()
        clean_tag = primary_tag.upper()
    elif _is_generic and pat_str:
        display_title = pat_str.title()
        clean_tag = pat_str.upper()
    else:
        # Pulisci prefissi categoria o stringhe troppo lunghe
        short_title = raw_name_str
        if cat_str and short_title.lower().startswith(f"{cat_str.lower()} - "):
            short_title = short_title[len(cat_str) + 3:].strip()
        display_title = short_title if len(short_title) <= 28 else short_title[:26].strip() + '...'
        clean_tag = (primary_tag or pat_str or '').upper() if (primary_tag or pat_str) else None

    return display_title, clean_tag

# ---------------------------------------------------------
# CATALOGO SCADENZE & TASSE FREQUENTI ITALIANE (PRECOMPILATE)
# ---------------------------------------------------------
DEADLINES_CATALOG = [
    {
        "id_key": "bollo_auto",
        "name": "Bollo Auto / Moto",
        "icon": "🚗",
        "category": "Auto & Mobilità",
        "default_amount": 240.00,
        "default_day": 30,
        "recurrence": "ANNUAL",
        "pattern": "bollo|aci|pagopa",
        "description": "Tassa automobilistica regionale (si ripete ogni anno nello stesso mese)"
    },
    {
        "id_key": "tari",
        "name": "Tassa Rifiuti (TARI)",
        "icon": "💡",
        "category": "Bollette & Utenze",
        "default_amount": 185.00,
        "default_day": 30,
        "recurrence": "ANNUAL",
        "pattern": "tari|rifiuti|tributi|pagopa",
        "description": "Tributo comunale sui rifiuti (Acconto o Saldo annuale)"
    },
    {
        "id_key": "revisione_auto",
        "name": "Revisione Auto (MCTC)",
        "icon": "🔧",
        "category": "Auto & Mobilità",
        "default_amount": 79.00,
        "default_day": 28,
        "recurrence": "BIENNIAL",
        "pattern": "revisione|mctc|officina",
        "description": "Revisione ministeriale obbligatoria ogni 2 anni (Biennale)"
    },
    {
        "id_key": "assicurazione_rc",
        "name": "Assicurazione RC Auto / Moto",
        "icon": "🛡️",
        "category": "Auto & Mobilità",
        "default_amount": 380.00,
        "default_day": 15,
        "recurrence": "ANNUAL",
        "pattern": "assicuraz|allianz|unipol|genial|prima|linear",
        "description": "Polizza veicolo (annuale o semestrale)"
    },
    {
        "id_key": "scuola_libri",
        "name": "Libri Scolastici & Iscrizioni",
        "icon": "🎒",
        "category": "Shopping & Abbigliamento",
        "default_amount": 250.00,
        "default_day": 15,
        "recurrence": "ANNUAL",
        "pattern": "librer|scuol|cartol",
        "description": "Spese per corredo scolastico e testi (si ripropone ogni Settembre)"
    },
    {
        "id_key": "cambio_gomme",
        "name": "Cambio Gomme Stagionale",
        "icon": "🛞",
        "category": "Auto & Mobilità",
        "default_amount": 50.00,
        "default_day": 15,
        "recurrence": "ANNUAL",
        "pattern": "gomm|pneumat",
        "description": "Montaggio pneumatici stagionali (Nov / Apr)"
    },
    {
        "id_key": "visita_dentista",
        "name": "Controllo Dentista / Visita Speciale",
        "icon": "🩺",
        "category": "Salute & Benessere",
        "default_amount": 180.00,
        "default_day": 20,
        "recurrence": "ANNUAL",
        "pattern": "dentist|stomatolog|odontoiatr|visita",
        "description": "Visite sanitarie programmate annuali (detraibili 730)"
    },
    {
        "id_key": "fondo_pensione",
        "name": "Versamento Fondo Pensione (Deduzione 730)",
        "icon": "📈",
        "category": "Risparmio & Investimenti",
        "default_amount": 500.00,
        "default_day": 20,
        "recurrence": "ANNUAL",
        "pattern": "pensione|fondo|cometa|fonchim|secondapensione",
        "description": "Versamento deducibile a fine anno per saturare il tetto 730 di 5.164 €"
    }
]

def init_fixed_costs_schema():
    """Ensures the fixed_costs and planned_deadlines tables exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fixed_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            expected_amount REAL NOT NULL,
            due_day INTEGER DEFAULT 1,
            frequency TEXT DEFAULT 'MONTHLY',
            active_months TEXT,
            match_pattern TEXT,
            is_income BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        )
    ''')
    
    # 2. Planned Deadlines & Commitments Table (for one-off, seasonal, or recurring yearly spikes)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS planned_deadlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            expected_amount REAL NOT NULL,
            year_month TEXT NOT NULL, -- 'YYYY-MM'
            due_day INTEGER DEFAULT 15,
            match_pattern TEXT,
            recurrence TEXT DEFAULT 'ANNUAL', -- 'ANNUAL', 'BIENNIAL', 'SEMIANNUAL', 'ONE_OFF'
            is_paid BOOLEAN DEFAULT 0,
            paid_amount REAL DEFAULT 0.0,
            paid_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        )
    ''')
    
    # Safe migration: add frequency, active_months if missing in fixed_costs
    cursor.execute("PRAGMA table_info(fixed_costs)")
    cols = [col[1] for col in cursor.fetchall()]
    if "frequency" not in cols:
        cursor.execute("ALTER TABLE fixed_costs ADD COLUMN frequency TEXT DEFAULT 'MONTHLY'")
    if "active_months" not in cols:
        cursor.execute("ALTER TABLE fixed_costs ADD COLUMN active_months TEXT")
        
    # Safe migration: add recurrence if missing in planned_deadlines
    cursor.execute("PRAGMA table_info(planned_deadlines)")
    dl_cols = [col[1] for col in cursor.fetchall()]
    if "recurrence" not in dl_cols:
        cursor.execute("ALTER TABLE planned_deadlines ADD COLUMN recurrence TEXT DEFAULT 'ANNUAL'")
        
    conn.commit()
    conn.close()

# Smart recurring items with realistic cadence (e.g. Enel bimestrale mesi pari)
SMART_SEEDS = [
    {
        "name": "Mutuo Prima Casa (BCC)",
        "category": "Casa & Immobili",
        "expected_amount": 1050.00,
        "due_day": 4,
        "frequency": "MONTHLY",
        "active_months": None,
        "match_pattern": "mutuo",
        "is_income": 0
    },
    {
        "name": "Bolletta Luce & Gas (Enel Energia)",
        "category": "Bollette & Utenze",
        "expected_amount": 162.60,
        "due_day": 24,
        "frequency": "BIMONTHLY_EVEN", # Febbraio, Aprile, Giugno, Agosto, Ottobre, Dicembre
        "active_months": "2,4,6,8,10,12",
        "match_pattern": "enel",
        "is_income": 0
    },
    {
        "name": "Fibra Casa (Iliad)",
        "category": "Digitale, Tech & Tel",
        "expected_amount": 25.99,
        "due_day": 29,
        "frequency": "MONTHLY",
        "active_months": None,
        "match_pattern": "iliad",
        "is_income": 0
    },
    {
        "name": "SIM Mobile (Iliad)",
        "category": "Digitale, Tech & Tel",
        "expected_amount": 7.99,
        "due_day": 24,
        "frequency": "MONTHLY",
        "active_months": None,
        "match_pattern": "iliad",
        "is_income": 0
    },
    {
        "name": "Telepass & Pedaggi Autostrada",
        "category": "Auto & Mobilità",
        "expected_amount": 85.00,
        "due_day": 30,
        "frequency": "MONTHLY",
        "active_months": None,
        "match_pattern": "telepass",
        "is_income": 0
    },
    {
        "name": "Canone Mensile Carta BPER",
        "category": "Tasse, Fisco & Banche",
        "expected_amount": 0.50,
        "due_day": 7,
        "frequency": "MONTHLY",
        "active_months": None,
        "match_pattern": "canone mensile",
        "is_income": 0
    },
    {
        "name": "Stipendio Mensile (SMC Italia)",
        "category": "Lavoro & Entrate",
        "expected_amount": 3064.44,
        "due_day": 30,
        "frequency": "MONTHLY",
        "active_months": None,
        "match_pattern": "emolumenti|stipendio",
        "is_income": 1
    }
]

def seed_smart_fixed_costs(workspace_id, profile_id=None, force=False):
    """Initializes or refreshes the smart fixed costs rules (only for demo workspace 1 by default)."""
    init_fixed_costs_schema()
    if workspace_id != 1 and not force:
        return
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM fixed_costs WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
    if count == 0 or force:
        if force:
            conn.execute("DELETE FROM fixed_costs WHERE workspace_id = ?", (workspace_id,))
        for seed in SMART_SEEDS:
            conn.execute('''
                INSERT INTO fixed_costs (workspace_id, profile_id, name, category, expected_amount, due_day, frequency, active_months, match_pattern, is_income, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (workspace_id, profile_id, seed['name'], seed['category'], seed['expected_amount'], seed['due_day'], seed['frequency'], seed['active_months'], seed['match_pattern'], seed['is_income']))
        conn.commit()
    conn.close()

def is_cost_due_in_month(fc, month_num):
    """Determines if a recurring cost falls in the specified month (1-12)."""
    freq = fc.get('frequency', 'MONTHLY')
    active_m = fc.get('active_months')
    
    if active_m:
        months_list = [int(x.strip()) for x in active_m.split(',') if x.strip().isdigit()]
        return month_num in months_list
        
    if freq == 'MONTHLY':
        return True
    elif freq == 'BIMONTHLY_EVEN':
        return month_num % 2 == 0
    elif freq == 'BIMONTHLY_ODD':
        return month_num % 2 == 1
    elif freq == 'QUARTERLY':
        return month_num in [3, 6, 9, 12]
    elif freq == 'ANNUAL':
        # Se non è specificato active_months, ricava il mese da created_at o default mese corrente
        return True
        
    return True

def calculate_average_monthly_income(conn, workspace_id, profile_id=None, exclude_month=None):
    """
    Calculates the realistic monthly income baseline:
    1. First checks for configured fixed income rules (e.g. Stipendio Base).
    2. Otherwise calculates median external salary inflows, ignoring internal transfers (ricariche prepagata/giroconti).
    """
    # 1. Check if an active fixed income rule exists for this profile/workspace
    fc_query = "SELECT SUM(expected_amount) as total_fixed_inc FROM fixed_costs WHERE workspace_id = ? AND is_income = 1 AND is_active = 1"
    fc_params = [workspace_id]
    if profile_id:
        fc_query += " AND (profile_id = ? OR profile_id IS NULL)"
        fc_params.append(profile_id)
    fc_row = conn.execute(fc_query, fc_params).fetchone()
    if fc_row and fc_row['total_fixed_inc'] and fc_row['total_fixed_inc'] > 0:
        return fc_row['total_fixed_inc']

    # 2. Historical query excluding internal transfers and card topups
    query = '''
        SELECT amount 
        FROM transactions
        WHERE workspace_id = ? 
          AND amount > 500
          AND is_transfer = 0
          AND LOWER(description) NOT LIKE '%ric.prep%'
          AND LOWER(description) NOT LIKE '%giroconto%'
          AND LOWER(description) NOT LIKE '%postagiro%'
    '''
    params = [workspace_id]
    if profile_id:
        query += " AND profile_id = ?"
        params.append(profile_id)
    if exclude_month:
        query += " AND substr(date, 1, 7) != ?"
        params.append(exclude_month)
        
    query += " ORDER BY date DESC LIMIT 6"
    rows = conn.execute(query, params).fetchall()
    
    if rows:
        amounts = sorted([r['amount'] for r in rows])
        # Use median to avoid 14th month / bonuses distorting standard budget
        mid = len(amounts) // 2
        median_val = amounts[mid] if len(amounts) % 2 != 0 else (amounts[mid-1] + amounts[mid]) / 2
        return median_val
            
    # For demo workspace 1, fallback to demo baseline. For real/new workspaces with no data, return 0.0
    if workspace_id == 1:
        return 3064.44 if (not profile_id or profile_id == 2) else 1980.00
    return 0.0

def get_monthly_cashflow_data(workspace_id, profile_id=None, year_month=None):
    """
    Computes complete monthly budgeting based on POTENTIAL MONTHLY INCOME (Stipendio / Media Entrate),
    actual fixed expenses due for THIS specific month (with bimestral cadence support),
    and remaining disposable budget for the month.
    """
    init_fixed_costs_schema()
    seed_smart_fixed_costs(workspace_id, profile_id)
    now = datetime.now()
    conn = get_db_connection()
    
    if not year_month:
        cur_ym = now.strftime("%Y-%m")
        # Check if transactions exist in current calendar month
        has_curr = conn.execute("SELECT 1 FROM transactions WHERE workspace_id = ? AND substr(date, 1, 7) = ? LIMIT 1", (workspace_id, cur_ym)).fetchone()
        if has_curr:
            year_month = cur_ym
        else:
            # Fallback to latest available month with transactions or paystubs
            max_row = conn.execute("SELECT MAX(substr(date, 1, 7)) FROM transactions WHERE workspace_id = ?", (workspace_id,)).fetchone()
            if max_row and max_row[0]:
                year_month = max_row[0]
            else:
                max_ps = conn.execute("SELECT MAX(year), MAX(month) FROM paystubs WHERE workspace_id = ?", (workspace_id,)).fetchone()
                if max_ps and max_ps[0] and max_ps[1]:
                    year_month = f"{int(max_ps[0]):04d}-{int(max_ps[1]):02d}"
                else:
                    year_month = cur_ym
        
    seed_smart_fixed_costs(workspace_id, profile_id)
    
    try:
        y, m = map(int, year_month.split("-"))
    except Exception:
        y, m = now.year, now.month
        year_month = f"{y:04d}-{m:02d}"
        
    _, num_days_in_month = calendar.monthrange(y, m)
    is_current_month = (y == now.year and m == now.month)
    current_day = now.day if is_current_month else (num_days_in_month if (y < now.year or (y == now.year and m < now.month)) else 1)
    days_remaining = max(num_days_in_month - current_day, 1)

    # 1. Available Months in Database
    month_rows = conn.execute('''
        SELECT DISTINCT substr(date, 1, 7) as ym 
        FROM transactions 
        WHERE workspace_id = ? 
        ORDER BY ym DESC
    ''', (workspace_id,)).fetchall()
    available_months = [r['ym'] for r in month_rows if r['ym']]
    if year_month not in available_months:
        available_months.insert(0, year_month)
        available_months.sort(reverse=True)

    # 2. Total Accumulated Liquid Balance (Reserve)
    bal_query = "SELECT SUM(balance) as total FROM accounts WHERE workspace_id = ?"
    bal_params = [workspace_id]
    if profile_id:
        bal_query += " AND profile_id = ?"
        bal_params.append(profile_id)
    bal_row = conn.execute(bal_query, bal_params).fetchone()
    total_liquid_reserve = bal_row['total'] if bal_row and bal_row['total'] else 0.0

    # 3. Retrieve Transactions for Selected Month
    tx_query = "SELECT * FROM transactions WHERE workspace_id = ? AND substr(date, 1, 7) = ?"
    tx_params = [workspace_id, year_month]
    if profile_id:
        tx_query += " AND profile_id = ?"
        tx_params.append(profile_id)
    tx_rows = conn.execute(tx_query, tx_params).fetchall()
    
    actual_month_income = 0.0
    actual_month_expenses = 0.0
    for tx in tx_rows:
        if tx['is_transfer']:
            continue
        amt = tx['amount']
        if amt > 0:
            actual_month_income += amt
        else:
            actual_month_expenses += abs(amt)

    # 4. POTENTIAL / EXPECTED MONTHLY INCOME (Baseline)
    avg_3m_income = calculate_average_monthly_income(conn, workspace_id, profile_id, exclude_month=year_month if is_current_month else None)
    
    # Expected Monthly Inflow: If already received substantial income this month (e.g. stipend arrived), use actual, otherwise baseline
    expected_month_income = actual_month_income if actual_month_income >= (avg_3m_income * 0.7) else avg_3m_income

    # 5. Fetch Fixed Costs & Filter ONLY THOSE DUE IN THIS SPECIFIC MONTH (m)
    fc_query = "SELECT * FROM fixed_costs WHERE workspace_id = ? AND is_active = 1"
    fc_params = [workspace_id]
    if profile_id:
        fc_query += " AND (profile_id = ? OR profile_id IS NULL)"
        fc_params.append(profile_id)
    fc_query += " ORDER BY is_income DESC, due_day ASC"
    
    all_fixed_rows = conn.execute(fc_query, fc_params).fetchall()
    
    fixed_items_due = []
    fixed_items_skipped = []
    
    total_fixed_expenses_expected = 0.0
    total_fixed_expenses_paid = 0.0
    total_fixed_expenses_pending = 0.0

    for fc in all_fixed_rows:
        item = dict(fc)
        due_this_month = is_cost_due_in_month(item, m)
        item['is_due_this_month'] = due_this_month
        
        pat = fc['match_pattern'] or fc['name']
        matched_txs = []
        for tx in tx_rows:
            desc = (tx['description'] or '') + " " + (tx['raw_description'] or '')
            # Evita che investimenti Directa o PAC vengano agganciati erroneamente a costi fissi (es. Mutuo)
            if 'directa' in desc.lower() and 'directa' not in pat.lower():
                continue
            if re.search(pat, desc, re.IGNORECASE):
                if (fc['is_income'] and tx['amount'] > 0) or (not fc['is_income'] and tx['amount'] < 0):
                    matched_txs.append(tx)
                    
        is_paid = len(matched_txs) > 0
        actual_amount = sum(abs(t['amount']) for t in matched_txs) if is_paid else 0.0
        paid_date = matched_txs[0]['date'] if is_paid else None
        
        tx_tags = " ".join([t['tags'] or '' for t in matched_txs]) if matched_txs else ""
        disp_title, clean_tg = format_clean_tag_display(
            raw_name=fc['name'],
            tags=tx_tags,
            match_pattern=fc['match_pattern'] or '',
            category=fc['category'] or '',
            amount=actual_amount if is_paid else fc['expected_amount']
        )
        item['display_title'] = disp_title
        item['clean_tag'] = clean_tg
        
        item['is_paid'] = is_paid
        item['actual_amount'] = actual_amount
        item['paid_date'] = paid_date
        item['matched_tx_ids'] = [t['id'] for t in matched_txs]
        
        if due_this_month or is_paid:
            exp_amt = fc['expected_amount']
            if not fc['is_income']:
                total_fixed_expenses_expected += exp_amt
                if is_paid:
                    total_fixed_expenses_paid += actual_amount
                else:
                    total_fixed_expenses_pending += exp_amt
            fixed_items_due.append(item)
        else:
            fixed_items_skipped.append(item)

    # 6.5. PLANNED DEADLINES / IMPEGNI DEL MESE (es. Bollo, TARI, Revisione)
    # Smart Auto-Rollover: If recurring deadlines exist in past years/months, automatically project them into this year_month!
    try:
        cur_year, cur_month = [int(x) for x in year_month.split('-')]
        all_recurring = conn.execute("""
            SELECT * FROM planned_deadlines 
            WHERE workspace_id = ? AND recurrence IN ('ANNUAL', 'BIENNIAL', 'SEMIANNUAL')
        """, (workspace_id,)).fetchall()
        
        for rec in all_recurring:
            rec_dict = dict(rec)
            rec_type = rec_dict.get('recurrence')
            orig_ym = rec_dict.get('year_month')
            
            should_exist = False
            if orig_ym:
                try:
                    orig_y, orig_m = [int(x) for x in orig_ym.split('-')]
                    if rec_type == 'ANNUAL' and orig_m == cur_month:
                        should_exist = True
                    elif rec_type == 'BIENNIAL' and orig_m == cur_month and ((cur_year - orig_y) % 2 == 0):
                        should_exist = True
                    elif rec_type == 'SEMIANNUAL' and (orig_m == cur_month or (orig_m + 6 - 1) % 12 + 1 == cur_month):
                        should_exist = True
                except Exception:
                    pass
            
            if should_exist:
                check_existing = conn.execute("""
                    SELECT id FROM planned_deadlines 
                    WHERE workspace_id = ? AND year_month = ? AND (name = ? OR match_pattern = ?)
                """, (workspace_id, year_month, rec_dict['name'], rec_dict.get('match_pattern'))).fetchone()
                
                if not check_existing:
                    try:
                        conn.execute("""
                            INSERT INTO planned_deadlines (
                                workspace_id, profile_id, name, category, expected_amount,
                                year_month, due_day, recurrence, match_pattern, is_paid
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                        """, (
                            workspace_id,
                            rec_dict.get('profile_id'),
                            rec_dict['name'],
                            rec_dict.get('category') or 'Spese Straordinarie',
                            rec_dict.get('expected_amount') or 0.0,
                            year_month,
                            rec_dict.get('due_day') or 1,
                            rec_type,
                            rec_dict.get('match_pattern')
                        ))
                        conn.commit()
                    except Exception:
                        pass
    except Exception:
        pass

    dl_query = "SELECT * FROM planned_deadlines WHERE workspace_id = ? AND year_month = ?"
    dl_params = [workspace_id, year_month]
    if profile_id:
        dl_query += " AND (profile_id = ? OR profile_id IS NULL)"
        dl_params.append(profile_id)
    dl_query += " ORDER BY due_day ASC, id ASC"
    
    deadlines_rows = conn.execute(dl_query, dl_params).fetchall()
    
    planned_deadlines_list = []
    total_deadlines_expected = 0.0
    total_deadlines_paid = 0.0
    total_deadlines_pending = 0.0
    
    for dl in deadlines_rows:
        item = dict(dl)
        pat = dl['match_pattern'] or dl['name']
        
        # Check if matched in this month's transactions
        matched_txs = []
        for tx in tx_rows:
            desc = (tx['description'] or '') + " " + (tx['raw_description'] or '')
            if re.search(pat, desc, re.IGNORECASE) and tx['amount'] < 0:
                matched_txs.append(tx)
                
        auto_matched = len(matched_txs) > 0
        is_paid = bool(item.get('is_paid')) or auto_matched
        paid_amt = sum(abs(t['amount']) for t in matched_txs) if auto_matched else (item.get('paid_amount') or item['expected_amount']) if is_paid else 0.0
        paid_dt = matched_txs[0]['date'] if auto_matched else (item.get('paid_date') or None)
        
        tx_tags = " ".join([t['tags'] or '' for t in matched_txs]) if matched_txs else ""
        disp_title, clean_tg = format_clean_tag_display(
            raw_name=dl['name'],
            tags=tx_tags,
            match_pattern=dl['match_pattern'] or '',
            category=dl['category'] or '',
            amount=paid_amt if is_paid else dl['expected_amount']
        )
        item['display_title'] = disp_title
        item['clean_tag'] = clean_tg
        
        item['is_paid'] = is_paid
        item['auto_matched'] = auto_matched
        item['actual_amount'] = paid_amt
        item['paid_date'] = paid_dt
        item['matched_tx_ids'] = [t['id'] for t in matched_txs]
        
        total_deadlines_expected += item['expected_amount']
        if is_paid:
            total_deadlines_paid += paid_amt
        else:
            total_deadlines_pending += item['expected_amount']
            
        planned_deadlines_list.append(item)

    # 6.6. Extract Variable Transactions & Separate Investments / PAC
    all_matched_ids = set()
    for fi in fixed_items_due:
        for tid in fi.get('matched_tx_ids', []):
            all_matched_ids.add(tid)
    for dl in planned_deadlines_list:
        for tid in dl.get('matched_tx_ids', []):
            all_matched_ids.add(tid)
            
    variable_tx_list = []
    investment_tx_list = []
    
    for tx in tx_rows:
        if tx['is_transfer']:
            continue
        if tx['amount'] < 0 and tx['id'] not in all_matched_ids:
            tx_tags_raw = (tx['tags'] or '').strip()
            vt_title, vt_tag = format_clean_tag_display(
                raw_name=tx['description'],
                tags=tx_tags_raw,
                match_pattern="",
                category=tx['category'] or '',
                amount=abs(tx['amount'])
            )
            
            tx_data_item = {
                'id': tx['id'],
                'date': tx['date'],
                'amount': abs(tx['amount']),
                'category': tx['category'] or 'Altro',
                'description': tx['description'] or 'Spesa',
                'display_title': vt_title,
                'clean_tag': vt_tag
            }
            
            # Check if this transaction is an investment (e.g. Directa, ETF, PAC, broker)
            is_inv = (
                (vt_tag in ['DIRECTA', 'PAC', 'ETF', 'INVESTIMENTI', 'INVESTIMENTI_PAC'])
                or ('directa' in (tx['description'] or '').lower())
                or ('investiment' in (tx['category'] or '').lower())
                or ('investiment' in tx_tags_raw.lower())
            )
            
            if is_inv:
                investment_tx_list.append(tx_data_item)
            else:
                variable_tx_list.append(tx_data_item)
            
    # Sort by date descending
    variable_tx_list.sort(key=lambda x: x['date'], reverse=True)
    investment_tx_list.sort(key=lambda x: x['date'], reverse=True)

    # Variable Expenses & Investments totals
    variable_expenses = sum(t['amount'] for t in variable_tx_list)
    total_investments_month = sum(t['amount'] for t in investment_tx_list)

    # 7. MONTHLY BUDGET & DISPOSABLE INCOME (Calibrato su stipendio, costi fissi, tutte le scadenze del mese e investimenti!)
    # Se il mese presenta scadenze straordinarie (es. Bollo, TARI) sia pagate che pendenti, vanno entrambe dedotte dal budget mensile.
    total_all_deadlines = total_deadlines_paid + total_deadlines_pending
    monthly_net_margin = max(0.0, expected_month_income - total_fixed_expenses_expected)
    monthly_safe_to_spend = max(0.0, expected_month_income - total_fixed_expenses_expected - variable_expenses - total_all_deadlines - total_investments_month)
    monthly_budget_overrun = max(0.0, (total_fixed_expenses_expected + variable_expenses + total_all_deadlines + total_investments_month) - expected_month_income)
    daily_safe_budget = monthly_safe_to_spend / days_remaining if days_remaining > 0 else 0.0
    burn_rate_daily = actual_month_expenses / current_day if current_day > 0 else 0.0

    MESI_IT = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    month_name_it = f"{MESI_IT[m-1]} {y}"
    daily_avg_spend = actual_month_expenses / num_days_in_month if num_days_in_month > 0 else 0.0

    # Extended Month List with Italian names
    available_months_extended = []
    for ym in available_months:
        try:
            ey, em_idx = map(int, ym.split("-"))
            em_name = f"{MESI_IT[em_idx-1]} {ey}"
        except Exception:
            em_name = ym
        available_months_extended.append({
            "value": ym,
            "label": em_name,
            "is_current": (ym == datetime.now().strftime("%Y-%m"))
        })

    # 7.5. RETROSPECTIVE & HISTORICAL MONTH PERFORMANCE ANALYTICS
    net_savings = actual_month_income - actual_month_expenses
    savings_rate = round((net_savings / actual_month_income * 100), 1) if actual_month_income > 0 else 0.0

    # Previous Month Calculation (for Month-over-Month MoM Comparison)
    if m == 1:
        prev_y, prev_m = y - 1, 12
    else:
        prev_y, prev_m = y, m - 1
    prev_year_month = f"{prev_y:04d}-{prev_m:02d}"
    prev_month_name_it = f"{MESI_IT[prev_m-1]} {prev_y}"

    # Next Month Calculation
    if m == 12:
        next_y, next_m = y + 1, 1
    else:
        next_y, next_m = y, m + 1
    next_year_month = f"{next_y:04d}-{next_m:02d}"
    next_month_name_it = f"{MESI_IT[next_m-1]} {next_y}"

    prev_tx_query = "SELECT t.*, a.name as account_name FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id WHERE t.workspace_id = ? AND substr(t.date, 1, 7) = ?"
    prev_tx_params = [workspace_id, prev_year_month]
    if profile_id:
        prev_tx_query += " AND t.profile_id = ?"
        prev_tx_params.append(profile_id)
    prev_tx_rows = conn.execute(prev_tx_query, prev_tx_params).fetchall()

    prev_month_expenses = 0.0
    prev_category_totals = {}
    for ptx in prev_tx_rows:
        if ptx['is_transfer']:
            continue
        if ptx['amount'] < 0:
            p_amt = abs(ptx['amount'])
            prev_month_expenses += p_amt
            p_cat = ptx['category'] or 'Altro'
            prev_category_totals[p_cat] = prev_category_totals.get(p_cat, 0.0) + p_amt

    mom_diff_expenses = actual_month_expenses - prev_month_expenses
    mom_diff_pct = round((mom_diff_expenses / prev_month_expenses * 100), 1) if prev_month_expenses > 0 else None
    
    # Category Metadata: Colors & Icons dynamically built from MACRO_CATEGORIES
    CATEGORY_META = {
        k: {"icon": v["icon"], "color": v["color"]}
        for k, v in MACRO_CATEGORIES.items()
    }
    # Backward-compatibility aliases for any legacy custom named categories
    CATEGORY_META.update({
        "Casa & Utenze": {"icon": "🏠", "color": "#3b82f6"},
        "Svago & Ristoranti": {"icon": "🍽️", "color": "#f97316"},
        "Auto & Trasporti": {"icon": "🚗", "color": "#f59e0b"},
        "Tasse & Finanza": {"icon": "🏛️", "color": "#6366f1"},
        "Shopping & Personale": {"icon": "🛍️", "color": "#ec4899"},
        "Lavoro & Formazione": {"icon": "💼", "color": "#a855f7"},
        "Risparmio & Futuro": {"icon": "📈", "color": "#059669"},
        "Altro": {"icon": "📦", "color": "#94a3b8"}
    })

    # Category Breakdown & Transactions Drill-down for this month
    category_totals_dict = {}
    category_txs_dict = {}
    
    # Fetch accounts map for tx description enrichment if needed
    for tx in tx_rows:
        if tx['is_transfer']:
            continue
        if tx['amount'] < 0:
            c = tx['category'] or 'Altro'
            amt_val = abs(tx['amount'])
            category_totals_dict[c] = category_totals_dict.get(c, 0.0) + amt_val
            if c not in category_txs_dict:
                category_txs_dict[c] = []
            category_txs_dict[c].append({
                'id': tx['id'],
                'date': tx['date'],
                'amount': amt_val,
                'description': tx['description'] or 'Spesa',
                'raw_description': tx['raw_description'] if ('raw_description' in tx.keys() if hasattr(tx, 'keys') else 'raw_description' in tx) and tx['raw_description'] else '',
                'category': c,
                'sub_category': tx['sub_category'] if ('sub_category' in tx.keys() if hasattr(tx, 'keys') else 'sub_category' in tx) and tx['sub_category'] else '',
                'tags': tx['tags'] if ('tags' in tx.keys() if hasattr(tx, 'keys') else 'tags' in tx) and tx['tags'] else ''
            })
            
    category_breakdown = []
    chart_colors = []
    chart_labels = []
    chart_values = []

    for c_name, c_amt in sorted(category_totals_dict.items(), key=lambda x: x[1], reverse=True):
        c_pct = round((c_amt / actual_month_expenses * 100), 1) if actual_month_expenses > 0 else 0.0
        meta = CATEGORY_META.get(c_name, {"icon": "🏷️", "color": "#94a3b8"})
        
        # Sort category transactions by amount descending (highest impact first), then date
        c_txs = category_txs_dict.get(c_name, [])
        c_txs.sort(key=lambda x: (x['amount'], x['date']), reverse=True)

        # MoM comparison for this category
        prev_c_amt = prev_category_totals.get(c_name, 0.0)
        c_diff_amt = c_amt - prev_c_amt
        c_diff_pct = round((c_diff_amt / prev_c_amt * 100), 1) if prev_c_amt > 0 else None

        category_breakdown.append({
            "name": c_name,
            "icon": meta["icon"],
            "color": meta["color"],
            "amount": c_amt,
            "percent": c_pct,
            "tx_count": len(c_txs),
            "transactions": c_txs,
            "prev_amount": prev_c_amt,
            "diff_amount": c_diff_amt,
            "diff_pct": c_diff_pct
        })
        chart_labels.append(f"{meta['icon']} {c_name}")
        chart_values.append(round(c_amt, 2))
        chart_colors.append(meta["color"])
        
    # Month financial verdict
    if net_savings > 0:
        if savings_rate >= 20:
            verdict_title = "🌟 Mese Eccellente"
            verdict_badge = "success"
            verdict_desc = f"Hai accantonato il {savings_rate}% del reddito ({net_savings:+.2f} € di risparmio netto)!"
        else:
            verdict_title = "🟢 Mese Positivo"
            verdict_badge = "success"
            verdict_desc = f"Chiusura in attivo con {net_savings:+.2f} € risparmiati ({savings_rate}% delle entrate)."
    elif net_savings == 0:
        verdict_title = "⚖️ Pareggio Perfetto"
        verdict_badge = "warning"
        verdict_desc = "Le entrate del mese hanno coperto esattamente le uscite sostenute."
    else:
        verdict_title = "🔴 Mese in Disavanzo"
        verdict_badge = "danger"
        verdict_desc = f"Le uscite hanno superato le entrate di {abs(net_savings):.2f} €. Il disavanzo è stato assorbito dalla riserva liquida."

    # 7.8. Daily Expenses Breakdown & Peaks Analytics (Giorno per Giorno)
    GIORNI_IT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    MESI_SHORT_IT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
    
    daily_breakdown = []
    daily_labels = []
    daily_series_full = []
    daily_series_no_mortgage = []
    daily_is_weekend = []
    daily_is_today = []
    
    peak_day_full = None
    peak_amount_full = 0.0
    peak_label_full = "-"
    
    peak_day_no_mortgage = None
    peak_amount_no_mortgage = 0.0
    peak_label_no_mortgage = "-"
    
    total_mortgage_month = 0.0
    
    # Pre-index transactions by day
    txs_by_day = {d: [] for d in range(1, num_days_in_month + 1)}
    for tx in tx_rows:
        if tx['is_transfer'] or tx['amount'] >= 0:
            continue
        try:
            tx_dt = datetime.strptime(tx['date'][:10], "%Y-%m-%d")
            if tx_dt.year == y and tx_dt.month == m:
                txs_by_day[tx_dt.day].append(tx)
        except Exception:
            pass

    def clean_friendly_tx_title(desc, raw_desc='', sub_cat='', cat=''):
        full_text = f"{desc or ''} {raw_desc or ''}".strip()
        full_upper = full_text.upper()
        
        if "MUTUO" in full_upper:
            return "Mutuo Casa (BCC)"
        if "COMMISSIONI" in full_upper and ("BONIFIC" in full_upper or "BONIFICO" in full_upper):
            return "Commissione Bonifico"
        if "COMMISSIONI" in full_upper and "CBILL" in full_upper:
            return "Commissione CBILL"
        if "CBILL" in full_upper and "ACI" in full_upper:
            return "Bollo Auto (ACI CBILL)"
        if "CBILL" in full_upper:
            return "Bollettino CBILL"
        if "ENEL" in full_upper:
            return "Enel Energia"
        if "ILIAD" in full_upper:
            return "Iliad"
        if "TELEPASS" in full_upper or "AUTOSTRADE" in full_upper:
            return "Telepass"
        if "CONAD" in full_upper:
            return "Conad"
        if "COOP" in full_upper:
            return "Coop"
        if "CARREFOUR" in full_upper:
            return "Carrefour"
        if "ACQUA & SAPONE" in full_upper or "ACQUA E SAPONE" in full_upper:
            return "Acqua & Sapone"
        if "CANONE MENSILE" in full_upper:
            return "Canone Mensile Carta"
            
        if sub_cat and sub_cat not in ['Altro', 'Generale', 'Spese Generali']:
            return sub_cat
            
        clean = (desc or raw_desc or 'Spesa').strip()
        clean = re.sub(r'(?i)PAGAMENTI DIVERSI DA INTERNET BANKING E CSA', '', clean)
        clean = re.sub(r'(?i)PAGAMENTO BOLLETTINO CBILL \d+', 'Bollettino CBILL', clean)
        clean = re.sub(r'(?i)TRAMITE I\.B\. / CSA', '', clean)
        clean = re.sub(r'(?i)DEL \d{2}/\d{2}/\d{4}', '', clean)
        clean = re.sub(r'(?i)Bonifico num\. [\w\-]+', '', clean)
        clean = re.sub(r'(?i)RIF\.? \d+[\/\d]*', '', clean)
        clean = re.sub(r'(?i)DISPOSIZIONE a favore di ([\w\s]+) BCC.*', r'Bonifico \1', clean)
        clean = re.sub(r'\s+', ' ', clean).strip(' -:,/')
        
        if len(clean) > 32:
            return clean[:30].strip() + '...'
        return clean if clean else (cat or 'Spesa')

    for d in range(1, num_days_in_month + 1):
        d_date = datetime(y, m, d)
        day_name_short = GIORNI_IT[d_date.weekday()]
        is_wknd = (d_date.weekday() >= 5) # Sat or Sun
        is_td = (is_current_month and d == now.day)
        
        d_txs = txs_by_day.get(d, [])
        d_total = 0.0
        d_no_mortgage = 0.0
        d_mortgage = 0.0
        d_tx_details = []
        
        for t in d_txs:
            t_amt = abs(t['amount'])
            d_total += t_amt
            
            # Identify Mortgage transactions
            t_cat = (t['category'] or '').strip()
            t_sub = (t['sub_category'] if ('sub_category' in t.keys() if hasattr(t, 'keys') else 'sub_category' in t) and t['sub_category'] else '').strip()
            t_tags = (t['tags'] if ('tags' in t.keys() if hasattr(t, 'keys') else 'tags' in t) and t['tags'] else '').strip().lower()
            raw_d = (t['raw_description'] if ('raw_description' in t.keys() if hasattr(t, 'keys') else 'raw_description' in t) and t['raw_description'] else '')
            t_desc = ((t['description'] or '') + " " + raw_d).lower()
            
            is_mortgage = (
                t_sub.lower() == 'mutuo' or 
                '#mutuo' in t_tags or 
                'mutuo' in t_desc or 
                'addebito mutuo' in t_desc or
                (t_cat in ['Casa & Immobili', 'Casa & Utenze'] and 'mutuo' in t_desc)
            )
            
            if is_mortgage:
                d_mortgage += t_amt
                total_mortgage_month += t_amt
            else:
                d_no_mortgage += t_amt
                
            friendly_name = clean_friendly_tx_title(t['description'], raw_d, t_sub, t_cat)
            meta = CATEGORY_META.get(t_cat, {"icon": "🏷️", "color": "#94a3b8"})
            d_tx_details.append({
                "description": friendly_name,
                "amount": t_amt,
                "category": t_cat,
                "icon": meta["icon"],
                "color": meta["color"],
                "is_mortgage": is_mortgage
            })
            
        # Format label (e.g. "10 Gio (Oggi)" or "1 Mar")
        lbl = f"{d} {day_name_short}"
        if is_td:
            lbl += " (Oggi)"
            
        daily_labels.append(lbl)
        daily_series_full.append(round(d_total, 2))
        daily_series_no_mortgage.append(round(d_no_mortgage, 2))
        daily_is_weekend.append(is_wknd)
        daily_is_today.append(is_td)
        
        if d_total > peak_amount_full:
            peak_amount_full = d_total
            peak_day_full = d
            peak_label_full = f"{d} {day_name_short}"
            
        if d_no_mortgage > peak_amount_no_mortgage:
            peak_amount_no_mortgage = d_no_mortgage
            peak_day_no_mortgage = d
            peak_label_no_mortgage = f"{d} {day_name_short}"
            
        daily_breakdown.append({
            "day": d,
            "date_str": d_date.strftime("%Y-%m-%d"),
            "day_name": day_name_short,
            "label": lbl,
            "is_weekend": is_wknd,
            "is_today": is_td,
            "total_expenses": round(d_total, 2),
            "total_no_mortgage": round(d_no_mortgage, 2),
            "mortgage_amount": round(d_mortgage, 2),
            "has_mortgage": (d_mortgage > 0),
            "tx_count": len(d_tx_details),
            "transactions": d_tx_details
        })

    today_formatted_it = f"{now.day} {MESI_SHORT_IT[now.month-1]} {now.year}"
    has_mortgage_in_month = (total_mortgage_month > 0)

    # 8. SMART HYBRID ENGINE: Auto-Discovery & Anomaly / Churn Detection
    smart_alerts = []
    
    # Check for overdue fixed costs or deadlines ONLY if current month
    if is_current_month:
        for it in fixed_items_due:
            if not it['is_income'] and not it['is_paid']:
                if current_day > (it['due_day'] + 5):
                    smart_alerts.append({
                        "type": "OVERDUE",
                        "id": it['id'],
                        "title": f"Addebito non ancora rilevato: {it['name']}",
                        "message": f"Scadenza prevista il giorno {it['due_day']}. L'addebito di ~{it['expected_amount']:.2f} € non è ancora comparso.",
                        "action_text": "Verifica Movimenti"
                    })

        for dl in planned_deadlines_list:
            if not dl['is_paid'] and current_day > dl['due_day']:
                smart_alerts.append({
                    "type": "DEADLINE_OVERDUE",
                    "id": dl['id'],
                    "title": f"Scadenza del mese non ancora saldata: {dl['name']}",
                    "message": f"Era prevista entro il giorno {dl['due_day']}. Importo: ~{dl['expected_amount']:.2f} €.",
                    "action_text": "Segna Pagato o Verifica"
                })

    conn.close()

    return {
        "year_month": year_month,
        "month_name": calendar.month_name[m],
        "month_name_it": month_name_it,
        "month_number": m,
        "year_number": y,
        "available_months": available_months,
        "available_months_extended": available_months_extended,
        "prev_year_month": prev_year_month,
        "prev_month_name_it": prev_month_name_it,
        "next_year_month": next_year_month,
        "next_month_name_it": next_month_name_it,
        "prev_month_expenses": prev_month_expenses,
        "mom_diff_expenses": mom_diff_expenses,
        "mom_diff_pct": mom_diff_pct,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "chart_colors": chart_colors,
        "is_current_month": is_current_month,
        "current_day": current_day,
        "days_in_month": num_days_in_month,
        "days_remaining": days_remaining,
        "total_liquid_reserve": total_liquid_reserve,
        "expected_month_income": expected_month_income,
        "avg_3m_income": avg_3m_income,
        "actual_month_income": actual_month_income,
        "actual_month_expenses": actual_month_expenses,
        "net_savings": net_savings,
        "savings_rate": savings_rate,
        "daily_avg_spend": daily_avg_spend,
        "category_breakdown": category_breakdown,
        "daily_breakdown": daily_breakdown,
        "daily_labels": daily_labels,
        "daily_series_full": daily_series_full,
        "daily_series_no_mortgage": daily_series_no_mortgage,
        "daily_is_weekend": daily_is_weekend,
        "daily_is_today": daily_is_today,
        "peak_day_full": peak_day_full,
        "peak_amount_full": peak_amount_full,
        "peak_label_full": peak_label_full,
        "peak_day_no_mortgage": peak_day_no_mortgage,
        "peak_amount_no_mortgage": peak_amount_no_mortgage,
        "peak_label_no_mortgage": peak_label_no_mortgage,
        "total_mortgage_month": total_mortgage_month,
        "has_mortgage_in_month": has_mortgage_in_month,
        "today_formatted_it": today_formatted_it,
        "verdict_title": verdict_title,
        "verdict_badge": verdict_badge,
        "verdict_desc": verdict_desc,
        "variable_expenses": variable_expenses,
        "variable_transactions": variable_tx_list,
        "total_investments_month": total_investments_month,
        "investment_transactions": investment_tx_list,
        "fixed_items": fixed_items_due,
        "fixed_items_skipped": fixed_items_skipped,
        "planned_deadlines": planned_deadlines_list,
        "deadlines_catalog": DEADLINES_CATALOG,
        "total_deadlines_expected": total_deadlines_expected,
        "total_deadlines_paid": total_deadlines_paid,
        "total_deadlines_pending": total_deadlines_pending,
        "total_fixed_expenses_expected": total_fixed_expenses_expected,
        "total_fixed_expenses_paid": total_fixed_expenses_paid,
        "total_fixed_expenses_pending": total_fixed_expenses_pending,
        "monthly_net_margin": monthly_net_margin,
        "monthly_safe_to_spend": monthly_safe_to_spend,
        "monthly_budget_overrun": monthly_budget_overrun,
        "total_all_deadlines": total_all_deadlines,
        "daily_safe_budget": daily_safe_budget,
        "burn_rate_daily": burn_rate_daily,
        "smart_alerts": smart_alerts
    }


def get_multi_month_trend_data(workspace_id, profile_id=None, months_count=12):
    """
    Computes historical monthly trend (Income, Expenses, Net Savings, Savings Rate, Target Savings)
    for the last `months_count` calendar months based on registered transactions in the workspace.
    """
    from database import get_db_connection
    conn = get_db_connection()
    
    # 1. Determine months window (anchor to current month, or latest month with registered data)
    now = datetime.now()
    cur_ym = now.strftime("%Y-%m")
    
    has_curr = conn.execute("SELECT 1 FROM transactions WHERE workspace_id = ? AND substr(date, 1, 7) >= ? LIMIT 1", (workspace_id, cur_ym)).fetchone()
    
    anchor_y, anchor_m = now.year, now.month
    if not has_curr:
        max_tx = conn.execute("SELECT MAX(date) FROM transactions WHERE workspace_id = ?", (workspace_id,)).fetchone()
        max_ps = conn.execute("SELECT MAX(year), MAX(month) FROM paystubs WHERE workspace_id = ?", (workspace_id,)).fetchone()
        
        if max_tx and max_tx[0]:
            try:
                parts = max_tx[0].split('-')
                anchor_y, anchor_m = int(parts[0]), int(parts[1])
            except Exception:
                pass
        elif max_ps and max_ps[0] and max_ps[1]:
            try:
                anchor_y, anchor_m = int(max_ps[0]), int(max_ps[1])
            except Exception:
                pass

    cur_y = anchor_y
    cur_m = anchor_m
    
    # Generate list of month keys: YYYY-MM in chronological order
    months_keys = []
    for i in range(months_count - 1, -1, -1):
        target_m = cur_m - i
        target_y = cur_y
        while target_m <= 0:
            target_m += 12
            target_y -= 1
        months_keys.append(f"{target_y:04d}-{target_m:02d}")
        
    MONTH_NAMES_IT_SHORT = {
        1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu",
        7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"
    }

    # Query all transactions within this workspace and profile filter
    query = '''
        SELECT amount, date, category, tags
        FROM transactions
        WHERE workspace_id = ?
    '''
    params = [workspace_id]
    if profile_id and str(profile_id).lower() != 'all':
        try:
            p_val = int(profile_id)
            query += " AND profile_id = ?"
            params.append(p_val)
        except (ValueError, TypeError):
            pass
        
    tx_rows = conn.execute(query, params).fetchall()
    
    # Also check if there are paystubs to complement income if no bank transactions exist
    paystub_query = "SELECT month, year, net_amount FROM paystubs WHERE workspace_id = ?"
    paystub_params = [workspace_id]
    if profile_id and str(profile_id).lower() != 'all':
        try:
            p_val = int(profile_id)
            paystub_query += " AND profile_id = ?"
            paystub_params.append(p_val)
        except (ValueError, TypeError):
            pass
    paystub_rows = conn.execute(paystub_query, paystub_params).fetchall()
    conn.close()

    # Aggregate by month
    monthly_data = {ym: {"income": 0.0, "expenses": 0.0, "tx_count": 0} for ym in months_keys}
    
    for tx in tx_rows:
        d_str = tx['date'] or ''
        amt = tx['amount'] or 0.0
        cat = tx['category'] or ''
        tags = tx['tags'] or ''
        
        # Parse month key YYYY-MM
        ym = None
        if len(d_str) >= 7 and d_str[4] == '-': # YYYY-MM-DD
            ym = d_str[:7]
        elif len(d_str) >= 10 and d_str[2] == '/': # DD/MM/YYYY
            parts = d_str.split('/')
            if len(parts) == 3 and len(parts[2]) == 4:
                ym = f"{parts[2]}-{parts[1].zfill(2)}"
                
        if ym and ym in monthly_data:
            # Exclude internal transfers/giroconti from general income/expense calculation
            if "#giroconto" in tags or cat == "Giroconto Interno":
                continue
                
            if amt > 0:
                monthly_data[ym]["income"] += amt
            else:
                monthly_data[ym]["expenses"] += abs(amt)
            monthly_data[ym]["tx_count"] += 1

    # Optional Paystub income injection for months with 0 bank income if paystub exists
    paystub_income_by_month = {}
    for ps in paystub_rows:
        ps_m = ps['month']
        ps_y = ps['year']
        if ps_m and ps_y:
            ps_ym = f"{int(ps_y):04d}-{int(ps_m):02d}"
            p_net = ps['net_amount'] or 0.0
            paystub_income_by_month[ps_ym] = paystub_income_by_month.get(ps_ym, 0.0) + p_net

    # Build final trend items
    chart_labels = []
    income_series = []
    expense_series = []
    savings_series = []
    target_series = []
    savings_rate_series = []
    months_list = []
    
    total_period_income = 0.0
    total_period_expenses = 0.0
    total_period_savings = 0.0
    best_month = None
    max_savings = -float('inf')

    cur_ym_str = f"{anchor_y:04d}-{anchor_m:02d}"
    for ym in months_keys:
        y_int, m_int = int(ym.split('-')[0]), int(ym.split('-')[1])
        y_short = str(y_int)[2:]
        is_current = (ym == cur_ym_str)
        if is_current:
            label = f"📍 {MONTH_NAMES_IT_SHORT.get(m_int, '')} {y_short} (In Corso)"
        else:
            label = f"{MONTH_NAMES_IT_SHORT.get(m_int, '')} {y_short} (FY{y_short})"
        
        raw_inc = monthly_data[ym]["income"]
        # If no bank income recorded but paystub exists, use paystub net salary
        if raw_inc == 0.0 and ym in paystub_income_by_month:
            raw_inc = paystub_income_by_month[ym]
            
        raw_exp = monthly_data[ym]["expenses"]
        net_sav = raw_inc - raw_exp
        sav_rate = round((net_sav / raw_inc * 100), 1) if raw_inc > 0 else 0.0
        target_sav = round(raw_inc * 0.20, 2) if raw_inc > 0 else 300.00 # Default target: 20% of income or min 300€
        is_target_met = (net_sav >= target_sav) if raw_inc > 0 else False
        
        item = {
            "year_month": ym,
            "label": label,
            "month_name_it": f"{MONTH_NAMES_IT_SHORT.get(m_int, '')} {y_int}",
            "income": round(raw_inc, 2),
            "expenses": round(raw_exp, 2),
            "net_savings": round(net_sav, 2),
            "savings_rate": sav_rate,
            "target_savings": target_sav,
            "is_target_met": is_target_met,
            "is_current_month": is_current,
            "tx_count": monthly_data[ym]["tx_count"]
        }
        
        months_list.append(item)
        chart_labels.append(label)
        income_series.append(round(raw_inc, 2))
        expense_series.append(round(raw_exp, 2))
        savings_series.append(round(net_sav, 2))
        target_series.append(round(target_sav, 2))
        savings_rate_series.append(sav_rate)
        
        total_period_income += raw_inc
        total_period_expenses += raw_exp
        total_period_savings += net_sav
        
        if net_sav > max_savings and (raw_inc > 0 or raw_exp > 0):
            max_savings = net_sav
            best_month = item

    avg_savings_rate = round((total_period_savings / total_period_income * 100), 1) if total_period_income > 0 else 0.0

    return {
        "chart_labels": chart_labels,
        "income_series": income_series,
        "expense_series": expense_series,
        "savings_series": savings_series,
        "target_series": target_series,
        "savings_rate_series": savings_rate_series,
        "months_list": months_list,
        "total_period_income": round(total_period_income, 2),
        "total_period_expenses": round(total_period_expenses, 2),
        "total_period_savings": round(total_period_savings, 2),
        "avg_savings_rate": avg_savings_rate,
        "best_month": best_month,
        "months_count": months_count
    }

def format_eur_advisor(val):
    if val is None:
        return "0,00"
    return f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_macro_advisor_insights(workspace_id, profile_id=None):
    """
    Computes comprehensive executive Macro Advisor insights:
    1. Financial Runway & Emergency Fund (Autonomia Finanziaria in mesi e giorni)
    2. Historical Savings Rate & Net Capital Accumulated
    3. Average Monthly Cashflow & Free Net Margin
    4. Main Expense Driver (Mutuo / Casa / Spese Fisse)
    5. Discretionary / Extra-Housing Spends (Aree di Ottimizzazione)
    """
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Calculate Current Total Balance from Accounts
    acc_query = "SELECT SUM(balance) FROM accounts WHERE workspace_id = ?"
    acc_params = [workspace_id]
    if profile_id and str(profile_id).lower() != 'all':
        try:
            acc_query += " AND profile_id = ?"
            acc_params.append(int(profile_id))
        except (ValueError, TypeError):
            pass
    bal_row = cursor.execute(acc_query, acc_params).fetchone()
    current_balance = float(bal_row[0]) if bal_row and bal_row[0] is not None else 0.0

    # 2. Query Historical Transactions (Excluding internal giroconti / transfers)
    tx_query = """
        SELECT date, amount, category, sub_category, tags, description
        FROM transactions
        WHERE workspace_id = ?
    """
    tx_params = [workspace_id]
    if profile_id and str(profile_id).lower() != 'all':
        try:
            tx_query += " AND profile_id = ?"
            tx_params.append(int(profile_id))
        except (ValueError, TypeError):
            pass
            
    tx_rows = cursor.execute(tx_query, tx_params).fetchall()
    conn.close()

    if not tx_rows:
        return []

    # Group by month and category
    months_dict = {}
    category_totals = {}
    total_income = 0.0
    total_expense = 0.0

    for tx in tx_rows:
        d_str = tx['date'] or ''
        amt = float(tx['amount'] or 0.0)
        cat = tx['category'] or 'Altro'
        subcat = tx['sub_category'] or ''
        tags = (tx['tags'] or '').lower()

        # Exclude Giroconto from pure expense/income consumption
        if '#giroconto' in tags or 'giroconto' in subcat.lower() or 'giroconto' in cat.lower():
            continue

        ym = d_str[:7] if len(d_str) >= 7 and d_str[4] == '-' else None
        if ym:
            if ym not in months_dict:
                months_dict[ym] = {"income": 0.0, "expense": 0.0}
            if amt > 0:
                months_dict[ym]["income"] += amt
                total_income += amt
            elif amt < 0:
                abs_amt = abs(amt)
                months_dict[ym]["expense"] += abs_amt
                total_expense += abs_amt
                category_totals[cat] = category_totals.get(cat, 0.0) + abs_amt

    months_count = len(months_dict) if len(months_dict) > 0 else 1
    avg_monthly_income = total_income / months_count if months_count > 0 else 0.0
    avg_monthly_expense = total_expense / months_count if months_count > 0 else 0.0
    avg_monthly_net = avg_monthly_income - avg_monthly_expense
    net_savings_total = total_income - total_expense
    savings_rate = (net_savings_total / total_income * 100) if total_income > 0 else 0.0

    runway_months = round(current_balance / avg_monthly_expense, 1) if avg_monthly_expense > 0 else 0.0
    runway_days = int(runway_months * 30.5)

    insights = []

    # 1. Autonomia Finanziaria & Fondo Emergenza
    runway_badge = "success" if runway_months >= 6 else ("info" if runway_months >= 3 else "warning")
    insights.append({
        "type": runway_badge,
        "icon": "🛡️",
        "title": "Autonomia Finanziaria & Fondo Emergenza",
        "text": f"Con il tuo Saldo Attuale di <strong>€ {format_eur_advisor(current_balance)}</strong> ed uscite medie mensili di <strong>€ {format_eur_advisor(avg_monthly_expense)}/mese</strong>, la tua riserva garantisce un'autonomia finanziaria di <strong>{runway_months} mesi</strong> (circa {runway_days} giorni) per coprire ogni spesa a uscite invariate."
    })

    # 2. Tasso di Risparmio Globale
    if savings_rate >= 20:
        insights.append({
            "type": "success",
            "icon": "📈",
            "title": "Eccellente Tasso di Risparmio",
            "text": f"Nel periodo analizzato ({months_count} mesi), hai risparmiato il <strong>{savings_rate:.1f}%</strong> delle entrate complessive, accumulando una giacenza netta di <strong>+€ {format_eur_advisor(net_savings_total)}</strong>."
        })
    elif savings_rate > 0:
        insights.append({
            "type": "info",
            "icon": "📈",
            "title": "Saldo Storico Positivo",
            "text": f"Nel periodo analizzato ({months_count} mesi), il tuo tasso di risparmio globale è del <strong>{savings_rate:.1f}%</strong>, con un risparmio accumulato di <strong>+€ {format_eur_advisor(net_savings_total)}</strong>."
        })
    else:
        insights.append({
            "type": "warning",
            "icon": "⚠️",
            "title": "Attenzione al Deficit Cumulato",
            "text": f"Nel periodo analizzato ({months_count} mesi), le uscite complessive (€ {format_eur_advisor(total_expense)}) hanno superato le entrate. Il saldo netto storico registra un disavanzo di <strong>€ {format_eur_advisor(net_savings_total)}</strong>."
        })

    # 3. Principale Voce di Spesa
    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    if sorted_cats:
        top_cat_name, top_cat_tot = sorted_cats[0]
        top_cat_pct = round((top_cat_tot / total_expense * 100), 1) if total_expense > 0 else 0.0
        insights.append({
            "type": "purple",
            "icon": "🛍️",
            "title": f"Principale Voce di Spesa: {top_cat_name}",
            "text": f"La macro-categoria <strong>{top_cat_name}</strong> costituisce il <strong>{top_cat_pct}%</strong> delle tue uscite totali storiche (€ {format_eur_advisor(top_cat_tot)})."
        })

    # 4. Flusso di Cassa Medio Mensile
    flow_type = "success" if avg_monthly_net >= 0 else "warning"
    if avg_monthly_net >= 0:
        flow_text = f"In media registri <strong>€ {format_eur_advisor(avg_monthly_income)}/mese</strong> di entrate a fronte di <strong>€ {format_eur_advisor(avg_monthly_expense)}/mese</strong> di uscite. Il margine libero medio è di <strong>+€ {format_eur_advisor(avg_monthly_net)} / mese</strong>."
    else:
        flow_text = f"In media registri <strong>€ {format_eur_advisor(avg_monthly_income)}/mese</strong> di entrate a fronte di <strong>€ {format_eur_advisor(avg_monthly_expense)}/mese</strong> di uscite (disavanzo medio di <strong>-€ {format_eur_advisor(abs(avg_monthly_net))} / mese</strong>)."

    insights.append({
        "type": flow_type,
        "icon": "⚖️",
        "title": "Flusso di Cassa Medio Mensile",
        "text": flow_text
    })

    # 5. Macro Analisi Spese Extra-Casa / Extra-Mutuo (Aree da Arginare)
    non_housing_cats = [c for c in sorted_cats if not any(kw in c[0].upper() for kw in ['MUTUO', 'FINANZIAMENT', 'CASA & UTENZE'])]
    total_expense_no_housing = sum(c[1] for c in non_housing_cats)
    housing_total = total_expense - total_expense_no_housing

    if non_housing_cats and total_expense_no_housing > 0:
        top_impacts = []
        for c_name, c_tot in non_housing_cats[:3]:
            pct_no_h = round((c_tot / total_expense_no_housing) * 100, 1)
            top_impacts.append(f"<strong>{c_name}</strong> (€ {format_eur_advisor(c_tot)} — {pct_no_h}% del totale extra-casa)")
        
        impact_str = ", ".join(top_impacts)
        insights.append({
            "type": "amber",
            "icon": "✂️",
            "title": "Macro Analisi Spese Comprimibili (Aree di Ottimizzazione)",
            "text": f"Escludendo le spese fisse obbligate di Casa & Utenze (€ {format_eur_advisor(housing_total)}), le 3 voci che impattano maggiormente sulle tue uscite sono: {impact_str}. Monitorare queste categorie e ridurre gli addebiti non categorizzati ('Altro') costituisce la principale leva per arginare gli sprechi ed elevare il tuo margine di risparmio annuo."
        })

    return insights


def get_monthly_forecast_and_considerations(cashflow_data, custom_salary=None, custom_target=None, profile_name="Leopoldo"):
    """
    Computes real-time Current Month Forecast Strip & 7 Smart Tactical Considerations:
    1. Forecast Strip (Giacenza/Margine Oggi, Stima Risparmio Fine Mese, Stima Saldo Conto a Fine Mese, Budget Max Rimanente)
    2. 7 Tactical Insights (Scadenze saldate/pendenti, Costi Fissi Residui, Obiettivo Raggiungibile, Stima a Fine Mese, Tagli Comprimibili, Dettaglio Saldo, Consiglio FONDAPI)
    """
    if not cashflow_data:
        return {"forecast": {}, "considerations": []}

    is_current = cashflow_data.get('is_current_month', True)
    days_passed = cashflow_data.get('current_day', 1)
    days_in_month = cashflow_data.get('days_in_month', 30)
    days_remaining = cashflow_data.get('days_remaining', 0) if is_current else 0
    current_balance = cashflow_data.get('total_liquid_reserve', 0.0)
    
    # Baseline or Custom Salary/Income
    effective_income = float(custom_salary) if custom_salary is not None else float(cashflow_data.get('expected_month_income', 3000.00))
    target_savings = float(custom_target) if custom_target is not None else 500.00
    
    actual_income = float(cashflow_data.get('actual_month_income', 0.0))
    expense = float(cashflow_data.get('actual_month_expenses', 0.0))
    variable_expenses = float(cashflow_data.get('variable_expenses', 0.0))
    
    unpaid_fixed_items = [f for f in cashflow_data.get('fixed_items', []) if not f.get('is_paid') and not f.get('is_income')]
    unpaid_fixed_total = float(cashflow_data.get('total_fixed_expenses_pending', 0.0))
    
    unpaid_upcoming_items = [d for d in cashflow_data.get('planned_deadlines', []) if not d.get('is_paid')]
    unpaid_upcoming_total = float(cashflow_data.get('total_deadlines_pending', 0.0))
    paid_upcoming_items = [d for d in cashflow_data.get('planned_deadlines', []) if d.get('is_paid')]
    paid_upcoming_total = float(cashflow_data.get('total_deadlines_paid', 0.0))

    # A) Variable Daily Trend
    var_daily_avg = (variable_expenses / max(1, days_passed)) if days_passed > 0 else 0.0
    projected_variable_remaining = round(var_daily_avg * days_remaining, 2) if days_remaining > 0 else 0.0

    # B) Projected Total Expense & Savings
    if days_remaining > 0:
        projected_total_expense = round(expense + unpaid_upcoming_total + unpaid_fixed_total + projected_variable_remaining, 2)
    else:
        projected_total_expense = round(expense, 2)

    current_savings_today = round(effective_income - expense, 2)
    projected_savings_end = round(effective_income - projected_total_expense, 2)

    max_expense_allowed_for_target = effective_income - target_savings
    remaining_budget_total = max(0.0, round(max_expense_allowed_for_target - expense, 2))
    
    remaining_projected_expense = max(0.0, round(unpaid_upcoming_total + unpaid_fixed_total + projected_variable_remaining, 2))
    projected_end_balance = round(current_balance - remaining_projected_expense, 2)

    max_daily_budget_remaining = round(remaining_budget_total / days_remaining, 2) if days_remaining > 0 else 0.0

    forecast = {
        "effective_income": effective_income,
        "target_savings": target_savings,
        "current_balance": current_balance,
        "current_savings_today": current_savings_today,
        "projected_savings_end": projected_savings_end,
        "projected_end_balance": projected_end_balance,
        "projected_total_expense": projected_total_expense,
        "remaining_projected_expense": remaining_projected_expense,
        "remaining_budget_total": remaining_budget_total,
        "max_daily_budget_remaining": max_daily_budget_remaining,
        "days_passed": days_passed,
        "days_in_month": days_in_month,
        "days_remaining": days_remaining,
        "is_current_month": is_current
    }

    considerations = []

    # 1. Scadenze in Programma imminenti o saldate (es. TARI)
    if unpaid_upcoming_items:
        up_list_str = ", ".join([f"<strong>{u['name']}</strong> (€ {format_eur_advisor(u.get('expected_amount', 0))})" for u in unpaid_upcoming_items])
        considerations.append({
            'type': 'amber',
            'icon': '📌',
            'title': 'Scadenze in Programma nel Mese',
            'text': f"Nel mese di riferimento hai <strong>{len(unpaid_upcoming_items)}</strong> spesa/e in programma dallo Scadenzario per un totale di <strong>€ {format_eur_advisor(unpaid_upcoming_total)}</strong>: {up_list_str}. Tale importo è stato incluso nel calcolo della previsione di fine mese."
        })
    elif paid_upcoming_items:
        paid_list_str = ", ".join([f"<strong>{u['name']}</strong> (€ {format_eur_advisor(u.get('actual_amount') or u.get('expected_amount', 0))} saldata il {u.get('paid_date') or cashflow_data.get('year_month', '')})" for u in paid_upcoming_items])
        considerations.append({
            'type': 'success',
            'icon': '📌',
            'title': 'Scadenze del Mese Saldate',
            'text': f"✅ Complimenti! Hai già saldato la scadenza in programma per questo mese: {paid_list_str}. L'importo è ora correttamente contabilizzato nelle tue uscite reali."
        })

    # 2. Costi Fissi Residui
    if unpaid_fixed_items and days_remaining > 0:
        sample_names = ", ".join([f['name'] for f in unpaid_fixed_items[:4]])
        if len(unpaid_fixed_items) > 4:
            sample_names += f" e altre {len(unpaid_fixed_items)-4} voci"
        considerations.append({
            'type': 'purple',
            'icon': '🏠',
            'title': 'Costi Fissi Mensili Residui',
            'text': f"Restano ancora da contabilizzare circa <strong>€ {format_eur_advisor(unpaid_fixed_total)}</strong> di Costi Fissi mensili ricorrenti ({len(unpaid_fixed_items)} voci tra cui {sample_names})."
        })

    # 3. Obiettivo Raggiungibile / Margine ad Oggi
    margin_fmt = f"+€ {format_eur_advisor(current_savings_today)}" if current_savings_today >= 0 else f"-€ {format_eur_advisor(abs(current_savings_today))}"
    if current_savings_today >= target_savings:
        considerations.append({
            'type': 'success',
            'icon': '🎯',
            'title': 'Obiettivo Raggiungibile!',
            'text': f"Ad oggi hai sostenuto spese per € {format_eur_advisor(expense)} a fronte di uno stipendio/entrate di riferimento di € {format_eur_advisor(effective_income)}. Il tuo margine attuale nel mese è di <strong>{margin_fmt}</strong>."
        })
    else:
        considerations.append({
            'type': 'amber' if current_savings_today >= 0 else 'warning',
            'icon': '⚠️',
            'title': 'Stima Margine Mese',
            'text': f"Nel mese hai speso € {format_eur_advisor(expense)} su € {format_eur_advisor(effective_income)} di stipendio di riferimento. Ad oggi il tuo margine residuo è di <strong>{margin_fmt}</strong>."
        })

    # 4. Stima a Fine Mese
    proj_margin_fmt = f"+€ {format_eur_advisor(projected_savings_end)}" if projected_savings_end >= 0 else f"-€ {format_eur_advisor(abs(projected_savings_end))}"
    if days_remaining > 0:
        if projected_savings_end >= target_savings:
            considerations.append({
                'type': 'info',
                'icon': '📈',
                'title': 'Stima a Fine Mese Favorevole',
                'text': f"Mancano {days_remaining} giorni alla fine del mese. Considerando le uscite contabilizzate (€ {format_eur_advisor(expense)}), i costi fissi residui (€ {format_eur_advisor(unpaid_fixed_total)}) e le scadenze in programma (€ {format_eur_advisor(unpaid_upcoming_total)}), sosterrai circa € {format_eur_advisor(projected_total_expense)} di spese totali, accumulando circa <strong>{proj_margin_fmt}</strong> a fine mese!"
            })
        else:
            considerations.append({
                'type': 'warning',
                'icon': '🎯',
                'title': 'Consiglio sul Budget Giornaliero',
                'text': f"Per guadagnare/risparmiare almeno € {format_eur_advisor(target_savings)} a fine mese, nei restanti {days_remaining} giorni dovresti spendere al massimo € {format_eur_advisor(max_daily_budget_remaining)}/giorno (budget residuo totale: € {format_eur_advisor(remaining_budget_total)})."
            })
    else:
        if current_savings_today >= target_savings:
            considerations.append({
                'type': 'success',
                'icon': '🏆',
                'title': 'Mese Chiuso in Positivo!',
                'text': f"Hai chiuso il mese con un guadagno/risparmio netto di <strong>{margin_fmt}</strong>, superando il tuo obiettivo di € {format_eur_advisor(target_savings)}!"
            })
        else:
            considerations.append({
                'type': 'warning',
                'icon': '⚠️',
                'title': 'Risparmio Sotto Obiettivo',
                'text': f"Il mese si è chiuso con un margine netto di <strong>{margin_fmt}</strong> rispetto allo stipendio di riferimento di € {format_eur_advisor(effective_income)}."
            })

    # 5. Consigli mirati sui tagli delle spese discrezionali/evitabili
    # (NOTA: Escludiamo 'RISPARMIO', 'INVESTIMENTI', 'FONDO PENSIONE' perché costituiscono accumulo patrimoniale virtuoso, non sprechi di consumo!)
    discretionary_items = []
    investment_items_total = 0.0
    for cat in cashflow_data.get('category_breakdown', []):
        c_amt = cat.get('amount', 0.0)
        if c_amt > 0:
            c_name_upper = cat['name'].upper()
            is_investment = any(kw in c_name_upper for kw in ['RISPARMIO', 'INVESTIMENT', 'PATRIMONIO', 'PAC'])
            if is_investment:
                investment_items_total += c_amt
                continue

            is_fixed = any(kw in c_name_upper for kw in ['MUTUO', 'FINANZIAMENT', 'BOLLETT', 'UTENZ', 'CASA', 'TASSE', 'BANCA', 'COMMISSION', 'GIROCONTO', 'PREPAGATA'])
            if not is_fixed:
                discretionary_items.append(cat)

    discretionary_items.sort(key=lambda x: x['amount'], reverse=True)

    # Nota Strategica PAC & Investimenti se presenti nel mese
    if investment_items_total > 0:
        real_consumption_expense = max(0.0, expense - investment_items_total)
        real_saving_with_invest = round(effective_income - real_consumption_expense, 2)
        real_saving_rate = round((real_saving_with_invest / effective_income * 100), 1) if effective_income > 0 else 0.0
        
        considerations.append({
            'type': 'info',
            'icon': '📈',
            'title': 'Investimenti & Accumulo PAC del Mese',
            'text': f"Nel mese hai destinato <strong>€ {format_eur_advisor(investment_items_total)}</strong> a <strong>Risparmio & Investimenti (PAC / ETF / Broker)</strong>. Questa uscita riduce la liquidità spendibile sul conto corrente ma <strong>accresce il tuo patrimonio netto</strong>: le tue spese vive reali di consumo sono di € {format_eur_advisor(real_consumption_expense)}, portando il tuo reale tasso di risparmio/accumulo al <strong>{real_saving_rate}%</strong>!"
        })

    if days_remaining > 0 and discretionary_items:
        top_disc_names = [f"<strong>{cat['name']}</strong> (€ {format_eur_advisor(cat['amount'])})" for cat in discretionary_items[:3]]
        disc_text = ", ".join(top_disc_names)
        
        considerations.append({
            'type': 'purple',
            'icon': '✂️',
            'title': 'Consiglio sui Tagli di Spesa (Prossimi Giorni)',
            'text': f"Per difendere il tuo budget ed evitare sprechi nei restanti {days_remaining} giorni, le categorie comprimibili/evitabili in cui hai speso di più in questo mese sono: {disc_text}. Contenere le uscite estemporanee o ricreative in queste voci ti consentirà di proteggere il tuo target di risparmio."
        })

    # 6. Dettaglio Stima Saldo a Fine Mese
    if days_remaining > 0:
        actual_income = float(cashflow_data.get('actual_month_income', 0.0))
        salary_already_received = actual_income >= (effective_income * 0.7)
        proj_with_salary = round(projected_end_balance + effective_income, 2)

        if salary_already_received:
            salary_text = f"la tua giacenza bancaria stimata al termine del mese sarà di <strong>€ {format_eur_advisor(projected_end_balance)}</strong> (lo stipendio del mese di € {format_eur_advisor(effective_income)} è già contabilizzato nel saldo attuale)"
        else:
            salary_text = f"la tua giacenza bancaria stimata a fine mese prima dello stipendio sarà di <strong>€ {format_eur_advisor(projected_end_balance)}</strong>, che raggiungerà <strong>€ {format_eur_advisor(proj_with_salary)}</strong> con l'accredito dello stipendio di riferimento (+€ {format_eur_advisor(effective_income)})"

        considerations.append({
            'type': 'info',
            'icon': '💳',
            'title': 'Dettaglio Stima Saldo a Fine Mese',
            'text': f"Partendo dal tuo Saldo Attuale di <strong>€ {format_eur_advisor(current_balance)}</strong> (registrato al giorno {days_passed}), stimiamo uscite per circa <strong>€ {format_eur_advisor(remaining_projected_expense)}</strong> nei restanti {days_remaining} giorni del mese. Di conseguenza, {salary_text}."
        })

    # 7. Piano Deducibilità FONDAPI (Consiglio Strategico 2026 - Attivo verso fine mese con margine reale al netto di costi fissi)
    show_fondapi_timing = (not is_current) or (days_remaining <= 10 or days_passed >= 20)
    free_net_margin = projected_savings_end if is_current else (actual_income - expense)
    current_fondapi = 1369.16
    max_fondapi = 5300.00
    remaining_cap = max(0.0, max_fondapi - current_fondapi)

    if show_fondapi_timing and free_net_margin >= 250 and remaining_cap > 0:
        suggested_transfer = min(remaining_cap, max(150.0, round(((free_net_margin * 0.50) / 50.0)) * 50.0))
        irpef_saved = suggested_transfer * 0.43
        net_cost = suggested_transfer - irpef_saved
        user_name_salute = profile_name if profile_name else "Leopoldo"

        considerations.append({
            'type': 'amber',
            'icon': '💰',
            'title': 'Piano Deducibilità FONDAPI (Consiglio Strategico 2026)',
            'text': f"{user_name_salute}, considerando le entrate di riferimento di <strong>€ {format_eur_advisor(effective_income)}</strong>, le spese sostenute e tutti i costi fissi/scadenze del mese (per complessivi € {format_eur_advisor(projected_total_expense)}), a fine mese disporrai di un <strong>margine libero netto stimato di +€ {format_eur_advisor(free_net_margin)}</strong>! Che ne dici di destinare <strong>€ {format_eur_advisor(suggested_transfer)}</strong> a FONDAPI senza intaccare il tuo budget quotidiano? Questo versamento ti restituirà <strong>+€ {format_eur_advisor(irpef_saved)} netti di sconto IRPEF nel 730</strong> (costo effettivo netto per te: € {format_eur_advisor(net_cost)})."
        })

    return {
        "forecast": forecast,
        "considerations": considerations
    }




