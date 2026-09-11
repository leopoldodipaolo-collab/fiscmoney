import re
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from database import get_db_connection
from services.cashflow_engine import DEADLINES_CATALOG

MESI_BREVI_IT = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
MESI_ESTESI_IT = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

def init_deadlines_radar_schema():
    """Migrates and ensures all fields for multi-partner progress tracking exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
    
    cursor.execute("PRAGMA table_info(planned_deadlines)")
    cols = [col[1] for col in cursor.fetchall()]
    
    new_cols = [
        ("recurrence", "TEXT DEFAULT 'ANNUAL'"),
        ("target_type", "TEXT DEFAULT 'SHARED_50_50'"), # 'SHARED_50_50', 'LEOPOLDO_ONLY', 'NUNZIA_ONLY'
        ("p1_paid_amount", "REAL DEFAULT 0.0"),
        ("p2_paid_amount", "REAL DEFAULT 0.0"),
        ("manual_matched_tx_id", "INTEGER"),
        ("custom_months", "TEXT"), # Comma-separated months: e.g. "1,2,4,12"
        ("notes", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE planned_deadlines ADD COLUMN {col_name} {col_type}")
            
    # Fix retroattivo: Assicurarsi che le scadenze ACI / Bollo Auto / Assicurazione veicolo siano LEOPOLDO_ONLY
    cursor.execute("""
        UPDATE planned_deadlines 
        SET target_type = 'LEOPOLDO_ONLY'
        WHERE (LOWER(name) LIKE '%bollo%' OR LOWER(name) LIKE '%aci%' OR LOWER(name) LIKE '%assicurazione%')
          AND (target_type IS NULL OR target_type = 'SHARED_50_50')
    """)

    conn.commit()
    conn.close()


def get_annual_deadlines_radar(workspace_id, profile_id=None, reference_date=None, user_profile_name=None):
    """
    Computes upcoming annual and multi-month financial deadlines:
    1. Monthly timeline distribution (next 12 calendar months).
    2. Progress bar tracking (Expected vs Paid with Partner 1 and Partner 2 quotas).
    3. Auto-matching against banking transactions by pattern/dates or manual links.
    4. Target Type: PERSONAL (Leopoldo only / Nunzia only) vs SHARED (50/50 family).
    """
    init_deadlines_radar_schema()
    conn = get_db_connection()
    
    if not reference_date:
        reference_date = date.today()
        
    curr_ym = reference_date.strftime("%Y-%m")
    
    # 1. Fetch workspace profiles (Primary = Leopoldo, Partner = Nunzia)
    profiles_rows = conn.execute("""
        SELECT id, name, is_primary 
        FROM profiles 
        WHERE workspace_id = ? 
        ORDER BY is_primary DESC, id ASC
    """, (workspace_id,)).fetchall()
    
    p1 = dict(profiles_rows[0]) if len(profiles_rows) > 0 else {"id": 1, "name": "Leopoldo"}
    p2 = dict(profiles_rows[1]) if len(profiles_rows) > 1 else {"id": 2, "name": "Nunzia"}
    
    p1_first = "Leopoldo"
    p2_first = "Nunzia"
    
    # 2. Fetch all planned deadlines for this workspace
    query = "SELECT * FROM planned_deadlines WHERE workspace_id = ?"
    params = [workspace_id]
    if profile_id:
        query += " AND (profile_id = ? OR profile_id IS NULL)"
        params.append(profile_id)
        
    query += " ORDER BY year_month ASC, due_day ASC, id ASC"
    raw_deadlines = conn.execute(query, params).fetchall()
    
    # 3. Fetch all expenses from reference_date - 6 months up to current date for automatic matching
    from_date_tx = (reference_date - relativedelta(months=6)).strftime("%Y-%m-01")
    tx_query = """
        SELECT id, date, amount, description, raw_description, profile_id, category, tags
        FROM transactions
        WHERE workspace_id = ? AND amount < 0 AND is_transfer = 0 AND date >= ?
        ORDER BY date DESC
    """
    all_recent_txs = conn.execute(tx_query, (workspace_id, from_date_tx)).fetchall()
    
    deadlines_list = []
    total_expected_year = 0.0
    total_paid_year = 0.0
    total_remaining_year = 0.0
    
    # Prepare 2 full calendar years (Current Year & Next Year) organized as matrices (12 months each)
    curr_year_int = reference_date.year
    next_year_int = curr_year_int + 1
    
    calendar_years = []
    month_map = {}
    
    for y_val in [curr_year_int, next_year_int]:
        y_months = []
        y_expected = 0.0
        y_paid = 0.0
        for m_idx in range(1, 13):
            ym_key = f"{y_val}-{m_idx:02d}"
            m_obj = {
                "year_month": ym_key,
                "month_num": m_idx,
                "year": y_val,
                "year_short": str(y_val)[-2:],
                "short_name": MESI_BREVI_IT[m_idx - 1],
                "full_name": f"{MESI_ESTESI_IT[m_idx - 1]} {y_val}",
                "is_current": (ym_key == curr_ym),
                "is_past": (ym_key < curr_ym),
                "deadlines": [],
                "total_expected": 0.0,
                "total_paid": 0.0,
                "total_remaining": 0.0,
                "items_count": 0
            }
            y_months.append(m_obj)
            month_map[ym_key] = m_obj
            
        calendar_years.append({
            "year": y_val,
            "months": y_months,
            "total_expected": 0.0,
            "total_paid": 0.0,
            "is_current_year": (y_val == curr_year_int)
        })
        
    timeline_months = month_map.values()
    
    for row in raw_deadlines:
        item = dict(row)
        expected = float(item.get('expected_amount') or 0.0)
        due_ym = item.get('year_month') or curr_ym
        due_day = int(item.get('due_day') or 15)
        pat = (item.get('match_pattern') or item.get('name') or '').strip()
        target_type = item.get('target_type') or 'SHARED_50_50'
        
        # Determine actual paid amounts (auto-match within date window ± 45 days + explicit database values)
        matched_txs = []
        auto_p1_paid = 0.0
        auto_p2_paid = 0.0
        
        if pat:
            for tx in all_recent_txs:
                desc = f"{tx['description'] or ''} {tx['raw_description'] or ''}"
                tx_date_ym = tx['date'][:7]
                if re.search(pat, desc, re.IGNORECASE):
                    try:
                        due_d = datetime.strptime(f"{due_ym}-{due_day:02d}", "%Y-%m-%d").date()
                        tx_d = datetime.strptime(tx['date'], "%Y-%m-%d").date()
                        day_diff = abs((tx_d - due_d).days)
                    except Exception:
                        day_diff = 0 if tx_date_ym == due_ym else 999
                        
                    if day_diff <= 45:
                        tx_amt = abs(float(tx['amount']))
                        matched_txs.append(tx)
                        if target_type == 'LEOPOLDO_ONLY':
                            auto_p1_paid += tx_amt
                        elif target_type == 'NUNZIA_ONLY':
                            auto_p2_paid += tx_amt
                        else: # SHARED_50_50
                            if tx['profile_id'] == p1['id']:
                                auto_p1_paid += tx_amt
                            elif len(profiles_rows) > 1 and tx['profile_id'] == p2['id']:
                                auto_p2_paid += tx_amt
                            else:
                                auto_p1_paid += tx_amt
                        
        manual_p1 = float(item.get('p1_paid_amount') or 0.0)
        manual_p2 = float(item.get('p2_paid_amount') or 0.0)
        
        final_p1_paid = max(manual_p1, auto_p1_paid)
        final_p2_paid = max(manual_p2, auto_p2_paid)
        
        if target_type == 'LEOPOLDO_ONLY':
            final_total_paid = final_p1_paid
            is_shared = False
            scope_badge = "👤 Personale Leopoldo"
            scope_code = "LEOPOLDO"
        elif target_type == 'NUNZIA_ONLY':
            final_total_paid = final_p2_paid
            is_shared = False
            scope_badge = "👩 Personale Nunzia"
            scope_code = "NUNZIA"
        else:
            final_total_paid = final_p1_paid + final_p2_paid
            is_shared = True
            scope_badge = "👥 Spesa Condivisa 50/50"
            scope_code = "SHARED"
            
        # If is_paid flag is explicitly 1 and no specific breakdown, assume full payment
        if item.get('is_paid') and final_total_paid == 0:
            final_total_paid = expected
            if target_type == 'LEOPOLDO_ONLY':
                final_p1_paid = expected
                final_p2_paid = 0.0
            elif target_type == 'NUNZIA_ONLY':
                final_p1_paid = 0.0
                final_p2_paid = expected
            else:
                final_p1_paid = expected / 2
                final_p2_paid = expected / 2
            
        is_fully_paid = (final_total_paid >= (expected - 0.05))
        is_partially_paid = (final_total_paid > 0.05 and not is_fully_paid)
        progress_pct = min(100.0, round((final_total_paid / expected * 100.0), 1)) if expected > 0 else 100.0
        remaining_to_pay = max(0.0, round(expected - final_total_paid, 2))
        
        # Quota targets
        if is_shared:
            half_quota = round(expected / 2.0, 2)
            p1_target = half_quota
            p2_target = half_quota
            p1_missing = max(0.0, round(half_quota - final_p1_paid, 2))
            p2_missing = max(0.0, round(half_quota - final_p2_paid, 2))
        elif target_type == 'LEOPOLDO_ONLY':
            p1_target = expected
            p2_target = 0.0
            p1_missing = remaining_to_pay
            p2_missing = 0.0
            half_quota = expected
        else: # NUNZIA_ONLY
            p1_target = 0.0
            p2_target = expected
            p1_missing = 0.0
            p2_missing = remaining_to_pay
            half_quota = expected
        
        # Status verdict
        if is_fully_paid:
            status_code = "COMPLETED"
            status_label = "Completata ✅"
            status_color = "#10b981"
        elif is_partially_paid:
            status_code = "PARTIAL"
            status_label = f"In Corso ({progress_pct:.0f}%) ⏳"
            status_color = "#eab308"
        else:
            status_code = "PENDING"
            status_label = "Da Saldare 🚨"
            status_color = "#f87171"
            
        formatted_item = {
            "id": item['id'],
            "name": item['name'],
            "category": item['category'],
            "expected_amount": expected,
            "year_month": due_ym,
            "due_day": due_day,
            "due_date_str": f"{due_day} {MESI_BREVI_IT[int(due_ym.split('-')[1])-1]} {due_ym.split('-')[0]}",
            "recurrence": item.get('recurrence') or 'ANNUAL',
            "match_pattern": pat,
            "target_type": target_type,
            "is_shared": is_shared,
            "scope_badge": scope_badge,
            "scope_code": scope_code,
            "is_paid": is_fully_paid,
            "is_partial": is_partially_paid,
            "total_paid": final_total_paid,
            "remaining_to_pay": remaining_to_pay,
            "progress_pct": progress_pct,
            "status_code": status_code,
            "status_label": status_label,
            "status_color": status_color,
            "p1_paid": final_p1_paid,
            "p2_paid": final_p2_paid,
            "p1_missing": p1_missing,
            "p2_missing": p2_missing,
            "p1_target": p1_target,
            "p2_target": p2_target,
            "half_quota": half_quota,
            "p1_name": p1_first,
            "p2_name": p2_first,
            "matched_txs_count": len(matched_txs),
            "notes": item.get('notes') or ''
        }
        deadlines_list.append(formatted_item)
        
        total_expected_year += expected
        total_paid_year += final_total_paid
        total_remaining_year += remaining_to_pay
        
        # Attach to calendar matrix month(s)
        rec_type = item.get('recurrence') or 'ANNUAL'
        c_months_str = item.get('custom_months') or ''
        
        # Mesi target da associare
        if c_months_str and (rec_type == 'CUSTOM_MONTHS'):
            c_months_list = [int(m.strip()) for m in c_months_str.split(',') if m.strip().isdigit()]
            for ym_k, m_obj in month_map.items():
                if m_obj['month_num'] in c_months_list:
                    m_obj["deadlines"].append(formatted_item)
                    m_obj["total_expected"] += expected
                    m_obj["total_paid"] += final_total_paid
                    m_obj["total_remaining"] += remaining_to_pay
                    m_obj["items_count"] += 1
        elif rec_type == 'ANNUAL':
            # Una scadenza annuale si proietta nel mese di scadenza sia nell'anno corrente che nell'anno prossimo
            due_month_int = int(due_ym.split('-')[1]) if '-' in due_ym else reference_date.month
            for ym_k, m_obj in month_map.items():
                if m_obj['month_num'] == due_month_int:
                    m_obj["deadlines"].append(formatted_item)
                    m_obj["total_expected"] += expected
                    if ym_k == due_ym:
                        m_obj["total_paid"] += final_total_paid
                        m_obj["total_remaining"] += remaining_to_pay
                    else:
                        m_obj["total_remaining"] += expected
                    m_obj["items_count"] += 1
        elif rec_type == 'BIENNIAL':
            # Una scadenza biennale si ripete ogni 2 anni (es. Revisione auto):
            # se base è 2026, si ripete nel 2028, non nel 2027!
            try:
                base_year = int(due_ym.split('-')[0])
                due_month_int = int(due_ym.split('-')[1])
            except Exception:
                base_year = reference_date.year
                due_month_int = reference_date.month

            for ym_k, m_obj in month_map.items():
                if m_obj['month_num'] == due_month_int and ((m_obj['year'] - base_year) % 2 == 0):
                    m_obj["deadlines"].append(formatted_item)
                    m_obj["total_expected"] += expected
                    if ym_k == due_ym:
                        m_obj["total_paid"] += final_total_paid
                        m_obj["total_remaining"] += remaining_to_pay
                    else:
                        m_obj["total_remaining"] += expected
                    m_obj["items_count"] += 1
        elif due_ym in month_map:
            month_map[due_ym]["deadlines"].append(formatted_item)
            month_map[due_ym]["total_expected"] += expected
            month_map[due_ym]["total_paid"] += final_total_paid
            month_map[due_ym]["total_remaining"] += remaining_to_pay
            month_map[due_ym]["items_count"] += 1
            
    # Calculate totals for each calendar year
    for cy in calendar_years:
        cy["total_expected"] = sum(m["total_expected"] for m in cy["months"])
        cy["total_paid"] = sum(m["total_paid"] for m in cy["months"])
        cy["total_remaining"] = max(0.0, cy["total_expected"] - cy["total_paid"])
        cy["progress_pct"] = min(100.0, round((cy["total_paid"] / cy["total_expected"] * 100.0), 1)) if cy["total_expected"] > 0 else 0.0

    conn.close()
    
    # Sort deadlines in list: pending first, then by date
    deadlines_list.sort(key=lambda d: (d['is_paid'], d['year_month'], d['due_day']))
    
    overall_progress = min(100.0, round((total_paid_year / total_expected_year * 100.0), 1)) if total_expected_year > 0 else 0.0
    
    return {
        "deadlines": deadlines_list,
        "timeline_months": list(month_map.values()),
        "calendar_years": calendar_years,
        "curr_year": curr_year_int,
        "next_year": next_year_int,
        "total_expected": total_expected_year,
        "total_paid": total_paid_year,
        "total_remaining": total_remaining_year,
        "overall_progress": overall_progress,
        "active_deadlines_count": len([d for d in deadlines_list if not d['is_paid']]),
        "completed_count": len([d for d in deadlines_list if d['is_paid']]),
        "p1": p1,
        "p2": p2,
        "p1_first": p1_first,
        "p2_first": p2_first,
        "catalog": DEADLINES_CATALOG
    }


def auto_seed_typical_family_deadlines(workspace_id, current_year=2026):
    """
    Pre-populates typical deadlines distinguishing between SHARED (Condominio, TARI)
    and PERSONAL (Bollo Auto di Leopoldo, Assicurazione RC Auto).
    """
    init_deadlines_radar_schema()
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM planned_deadlines WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
    
    if count == 0:
        typical_items = [
            {
                "name": "Condominio Annuale Famiglia",
                "category": "Casa & Immobili",
                "expected_amount": 4000.00,
                "year_month": f"{current_year}-09",
                "due_day": 30,
                "match_pattern": "condomin|amministrat",
                "recurrence": "ANNUAL",
                "target_type": "SHARED_50_50",
                "p1_paid_amount": 0.0,
                "p2_paid_amount": 2000.0, # Quota Nunzia anticipata (€2.000)
                "is_paid": 0,
                "notes": "Spesa condivisa 50/50. Nunzia ha già anticipato 2.000 €, quota Leopoldo da saldare."
            },
            {
                "name": "Bollo Auto ACI (Regionale)",
                "category": "Auto & Mobilità",
                "expected_amount": 265.20,
                "year_month": f"{current_year}-09",
                "due_day": 30,
                "match_pattern": "aci|bollo|automobile club",
                "recurrence": "ANNUAL",
                "target_type": "LEOPOLDO_ONLY", # Riguarda solo Leopoldo!
                "p1_paid_amount": 265.20,
                "p2_paid_amount": 0.0,
                "is_paid": 1,
                "notes": "Spesa personale di Leopoldo. Pagato con CBILL da internet banking."
            },
            {
                "name": "TARI (Tassa Rifiuti Comune)",
                "category": "Bollette & Utenze",
                "expected_amount": 240.00,
                "year_month": f"{current_year}-10",
                "due_day": 31,
                "match_pattern": "tari|rifiuti|tributi comunali",
                "recurrence": "ANNUAL",
                "target_type": "SHARED_50_50",
                "p1_paid_amount": 0.0,
                "p2_paid_amount": 0.0,
                "is_paid": 0,
                "notes": "Spesa casa condivisa al 50%. Avviso pagamento TARI rata annuale."
            },
            {
                "name": "Assicurazione RC Auto Semestrale",
                "category": "Auto & Mobilità",
                "expected_amount": 380.00,
                "year_month": f"{current_year}-11",
                "due_day": 15,
                "match_pattern": "assicuraz|allianz|unipol|genial",
                "recurrence": "SEMIANNUAL",
                "target_type": "LEOPOLDO_ONLY", # Spesa personale auto Leopoldo
                "p1_paid_amount": 0.0,
                "p2_paid_amount": 0.0,
                "is_paid": 0,
                "notes": "Spesa personale di Leopoldo. Rinnovo polizza veicolo."
            }
        ]
        
        for it in typical_items:
            conn.execute("""
                INSERT INTO planned_deadlines (
                    workspace_id, name, category, expected_amount, year_month, due_day, 
                    match_pattern, recurrence, target_type, p1_paid_amount, p2_paid_amount, is_paid, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workspace_id, it['name'], it['category'], it['expected_amount'], it['year_month'],
                it['due_day'], it['match_pattern'], it['recurrence'], it['target_type'],
                it['p1_paid_amount'], it['p2_paid_amount'], it['is_paid'], it['notes']
            ))
            
        conn.commit()
    conn.close()
