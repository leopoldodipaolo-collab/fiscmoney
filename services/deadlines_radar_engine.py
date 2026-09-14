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
            
    # Svuota una tantum i vecchi dati demo se presenti
    cursor.execute("""
        DELETE FROM planned_deadlines 
        WHERE notes LIKE '%Spesa condivisa 50/50. Nunzia ha già anticipato%'
           OR notes LIKE '%Pagato con CBILL da internet banking%'
           OR notes LIKE '%Avviso pagamento TARI rata annuale%'
           OR notes LIKE '%Rinnovo polizza veicolo%'
    """)

    conn.commit()
    conn.close()



def _compute_match(pat, target_ym, due_day, target_type, p1_id, p2_id, all_txs, manual_p1=0.0, manual_p2=0.0, is_paid_flag=False, expected=0.0, profiles_count=1, full_year_window=False):
    """
    Calcola l'importo pagato per una scadenza in un determinato anno/mese.
    - full_year_window=True: cattura TUTTE le transazioni nell'anno solare del target_ym
      (utile per scadenze ANNUAL con pagamenti distribuiti nell'anno, es. Condominio).
    - full_year_window=False (default): finestra ±45 giorni intorno alla data di scadenza.
    - Matching flessibile su: description, raw_description, tags (inclusi #hashtag) e category.
    """
    auto_p1_paid = 0.0
    auto_p2_paid = 0.0
    matched_count = 0
    
    if pat:
        clean_pat = pat.strip().lstrip('#')
        target_year = target_ym.split('-')[0]  # es. "2026"
        try:
            due_d = datetime.strptime(f"{target_ym}-{due_day:02d}", "%Y-%m-%d").date()
        except Exception:
            due_d = None
            
        for tx in all_txs:
            desc = f"{tx['description'] or ''} {tx['raw_description'] or ''} {tx['tags'] or ''} {tx['category'] or ''}"
            # Regex flessibile: parola intera o sottostringa
            if re.search(r'\b' + re.escape(clean_pat) + r'\b', desc, re.IGNORECASE) or re.search(re.escape(clean_pat), desc, re.IGNORECASE):
                try:
                    tx_d = datetime.strptime(tx['date'], "%Y-%m-%d").date()
                    if full_year_window:
                        # Cattura qualsiasi transazione nell'anno solare target
                        matches_window = (tx['date'][:4] == target_year)
                    else:
                        day_diff = abs((tx_d - due_d).days) if due_d else (0 if tx['date'][:7] == target_ym else 999)
                        matches_window = (day_diff <= 45)
                except Exception:
                    matches_window = False
                    
                if matches_window:
                    tx_amt = abs(float(tx['amount']))
                    matched_count += 1
                    tx_profile_id = tx['profile_id']
                    if target_type == 'LEOPOLDO_ONLY':
                        auto_p1_paid += tx_amt
                    elif target_type == 'NUNZIA_ONLY':
                        auto_p2_paid += tx_amt
                    else:  # SHARED_50_50
                        if tx_profile_id == p1_id:
                            auto_p1_paid += tx_amt
                        elif profiles_count > 1 and tx_profile_id == p2_id:
                            auto_p2_paid += tx_amt
                        else:
                            # Se profile_id non è valorizzato o non coincide, controlla il nome profilo o conto
                            auto_p1_paid += tx_amt

    final_p1 = max(manual_p1, auto_p1_paid)
    final_p2 = max(manual_p2, auto_p2_paid)
    
    if target_type == 'LEOPOLDO_ONLY':
        total = final_p1
    elif target_type == 'NUNZIA_ONLY':
        total = final_p2
    else:
        total = final_p1 + final_p2
    
    # is_paid flag fallback
    if is_paid_flag and total == 0:
        total = expected
        if target_type == 'LEOPOLDO_ONLY':
            final_p1 = expected
        elif target_type == 'NUNZIA_ONLY':
            final_p2 = expected
        else:
            final_p1 = expected / 2
            final_p2 = expected / 2
    
    return total, final_p1, final_p2, matched_count


def get_annual_deadlines_radar(workspace_id, profile_id=None, reference_date=None, user_profile_name=None):
    """
    Computes upcoming annual and multi-month financial deadlines:
    1. Monthly timeline distribution (Current Year & Next Year calendar matrices).
    2. Progress bar tracking (Expected vs Paid with Partner 1 and Partner 2 quotas).
    3. Auto-matching against banking transactions by pattern/dates or tags.
    4. Integration of monthly fixed costs (recurring items) for holistic calendar view.
    5. Clear separation between Past (historical/opaque) and Current/Future commitments.
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
    
    # 3. Fetch active recurring fixed costs for monthly calendar integration
    fc_query = "SELECT * FROM fixed_costs WHERE workspace_id = ? AND is_active = 1 AND is_income = 0"
    fc_params = [workspace_id]
    if profile_id:
        fc_query += " AND (profile_id = ? OR profile_id IS NULL)"
        fc_params.append(profile_id)
    fc_rows = conn.execute(fc_query, fc_params).fetchall()
    
    # 4. Fetch all expenses from reference_date - 18 months for matching
    from_date_tx = (reference_date - relativedelta(months=18)).strftime("%Y-%m-01")
    tx_query = """
        SELECT id, date, amount, description, raw_description, profile_id, category, tags
        FROM transactions
        WHERE workspace_id = ? AND amount < 0 AND is_transfer = 0 AND date >= ?
        ORDER BY date DESC
    """
    all_recent_txs = conn.execute(tx_query, (workspace_id, from_date_tx)).fetchall()
    
    # Prepare 2 full calendar years (Current Year & Next Year)
    curr_year_int = reference_date.year
    next_year_int = curr_year_int + 1
    
    calendar_years = []
    month_map = {}
    
    # Helper to check if a recurring fixed cost falls in month m_idx
    def _is_fc_in_month(fc, m_idx):
        active_m = fc.get('active_months')
        if active_m:
            m_list = [int(x.strip()) for x in active_m.split(',') if x.strip().isdigit()]
            return m_idx in m_list
        freq = fc.get('frequency', 'MONTHLY')
        if freq == 'MONTHLY':
            return True
        elif freq == 'BIMONTHLY_EVEN':
            return m_idx % 2 == 0
        elif freq == 'BIMONTHLY_ODD':
            return m_idx % 2 == 1
        elif freq == 'QUARTERLY':
            return m_idx in [3, 6, 9, 12]
        return True

    for y_val in [curr_year_int, next_year_int]:
        y_months = []
        for m_idx in range(1, 13):
            ym_key = f"{y_val}-{m_idx:02d}"
            
            # Calculate recurring fixed costs due in this specific month
            month_fc_items = []
            month_fc_total = 0.0
            month_fc_no_mortgage_total = 0.0
            for r in fc_rows:
                fc_item = dict(r)
                if _is_fc_in_month(fc_item, m_idx):
                    exp_amt = float(fc_item.get('expected_amount') or 0.0)
                    month_fc_total += exp_amt
                    raw_fc_name = fc_item.get('name') or ''
                    fc_pat = (fc_item.get('match_pattern') or '').strip().title()
                    # Se il nome è un pattern generico come DISPOSIZIONE o BONIFICO ma il pattern è es. Mutuo, usa il pattern
                    if raw_fc_name.upper() in ('DISPOSIZIONE', 'BONIFICO', 'PAGAMENTO') and fc_pat:
                        clean_fc_name = fc_pat
                    else:
                        clean_fc_name = raw_fc_name
                    
                    fc_is_mortgage = ('mutuo' in (raw_fc_name + ' ' + fc_pat + ' ' + (fc_item.get('category') or '')).lower())
                    if not fc_is_mortgage:
                        month_fc_no_mortgage_total += exp_amt
                        
                    month_fc_items.append({
                        "name": clean_fc_name,
                        "tag": fc_pat if fc_pat and fc_pat.lower() not in clean_fc_name.lower() else None,
                        "category": fc_item.get('category'),
                        "amount": exp_amt,
                        "due_day": fc_item.get('due_day', 1),
                        "is_mortgage": fc_is_mortgage
                    })
            
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
                "items_count": 0,
                "fixed_costs_total": round(month_fc_total, 2),
                "fixed_costs_without_mortgage": round(month_fc_no_mortgage_total, 2),
                "fixed_costs_items": month_fc_items,
                "grand_total_month": round(month_fc_total, 2)
            }
            y_months.append(m_obj)
            month_map[ym_key] = m_obj
            
        calendar_years.append({
            "year": y_val,
            "months": y_months,
            "total_expected": 0.0,
            "total_paid": 0.0,
            "total_fixed_costs": sum(m["fixed_costs_total"] for m in y_months),
            "total_fixed_costs_without_mortgage": sum(m["fixed_costs_without_mortgage"] for m in y_months),
            "is_current_year": (y_val == curr_year_int)
        })
        
    deadlines_list = []
    
    # Process each registered deadline
    for row in raw_deadlines:
        item = dict(row)
        expected = float(item.get('expected_amount') or 0.0)
        due_ym = item.get('year_month') or curr_ym
        due_day = int(item.get('due_day') or 15)
        pat = (item.get('match_pattern') or item.get('name') or '').strip()
        target_type = item.get('target_type') or 'SHARED_50_50'
        rec_type = item.get('recurrence') or 'ANNUAL'
        
        # Determine actual paid amounts via helper
        manual_p1 = float(item.get('p1_paid_amount') or 0.0)
        manual_p2 = float(item.get('p2_paid_amount') or 0.0)
        is_paid_flag = bool(item.get('is_paid'))
        
        is_past_item = (due_ym < curr_ym)
        # Per qualsiasi scadenza annuale (es. Condominio), utilizziamo l'intera finestra dell'anno
        # solare target per catturare rate/acconti versati nei vari mesi dello stesso anno.
        is_annual = (rec_type == 'ANNUAL')
        
        final_total_paid, final_p1_paid, final_p2_paid, match_count = _compute_match(
            pat, due_ym, due_day, target_type,
            p1['id'], p2['id'],
            all_recent_txs,
            manual_p1=manual_p1, manual_p2=manual_p2,
            is_paid_flag=is_paid_flag, expected=expected,
            profiles_count=len(profiles_rows),
            full_year_window=is_annual
        )
        
        # Scope labels
        if target_type == 'LEOPOLDO_ONLY':
            is_shared = False
            scope_badge = "👤 Personale Leopoldo"
            scope_code = "LEOPOLDO"
        elif target_type == 'NUNZIA_ONLY':
            is_shared = False
            scope_badge = "👩 Personale Nunzia"
            scope_code = "NUNZIA"
        else:
            is_shared = True
            scope_badge = "👥 Spesa Condivisa 50/50"
            scope_code = "SHARED"
        
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
        else:  # NUNZIA_ONLY
            p1_target = 0.0
            p2_target = expected
            p1_missing = 0.0
            p2_missing = remaining_to_pay
            half_quota = expected
        
        # Status verdict
        if is_past_item:
            # Per elementi storici passati, mostra stato Storico desaturato
            if is_fully_paid:
                status_code = "HISTORIC_PAID"
                status_label = "Saldato (Storico) ✓"
                status_color = "#64748b"
            elif is_partially_paid:
                status_code = "HISTORIC_PARTIAL"
                status_label = f"Storico ({progress_pct:.0f}%) ⏳"
                status_color = "#94a3b8"
            else:
                status_code = "HISTORIC_CLOSED"
                status_label = "Storico Concluso 🏛️"
                status_color = "#64748b"
        else:
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
                
        # Estrai un'etichetta pulita (Tag / Nome Breve) anziché la lunga stringa di transazione bancaria
        raw_name = item.get('name') or ''
        category_name = item.get('category') or ''
        clean_tag = (pat or '').strip().lstrip('#')
        
        # Se raw_name contiene il prefisso "Categoria - ", rimuovilo
        short_title = raw_name
        if category_name and short_title.lower().startswith(f"{category_name.lower()} - "):
            short_title = short_title[len(category_name) + 3:].strip()
            
        # Rileva tag o tipologia nota da pattern, nome o categoria (TARI, BOLLO, REVISIONE, MUTUO, CONDOMINIO, ECC.)
        all_text_hints = f"{clean_tag} {short_title} {category_name}".lower()
        if 'tari' in all_text_hints or 'pagopa' in all_text_hints:
            display_title = "Tari (PagoPA)"
        elif 'bollo' in all_text_hints or 'aci' in all_text_hints:
            display_title = "Bollo Auto (ACI)"
        elif 'revisione' in all_text_hints:
            display_title = "Revisione Auto"
        elif 'mutuo' in all_text_hints:
            display_title = "Rata Mutuo"
        elif 'condominio' in all_text_hints:
            display_title = "Spese Condominio"
        elif 'polizza' in all_text_hints or 'assicuraz' in all_text_hints:
            display_title = "Assicurazione"
        elif clean_tag and len(clean_tag) <= 25 and not clean_tag.isupper():
            display_title = clean_tag.title()
        elif short_title and len(short_title) <= 25:
            display_title = short_title.title()
        else:
            # Fallback pulito: prendi le prime parole significative
            words = [w for w in re.split(r'[\s\-_]+', short_title) if w and len(w) > 2 and not w.isdigit()]
            display_title = " ".join(words[:3]).title() if words else short_title[:20].title()
        
        is_mortgage = ('mutuo' in all_text_hints)
        
        formatted_item = {
            "id": item['id'],
            "name": item['name'],
            "display_title": display_title,
            "display_tag": clean_tag.upper() if clean_tag else None,
            "raw_detail": short_title if short_title != display_title else None,
            "category": item['category'],
            "expected_amount": expected,
            "year_month": due_ym,
            "due_day": due_day,
            "due_date_str": f"{due_day} {MESI_BREVI_IT[int(due_ym.split('-')[1])-1]} {due_ym.split('-')[0]}",
            "recurrence": rec_type,
            "match_pattern": pat,
            "target_type": target_type,
            "is_shared": is_shared,
            "is_mortgage": is_mortgage,
            "scope_badge": scope_badge,
            "scope_code": scope_code,
            "is_paid": is_fully_paid,
            "is_partial": is_partially_paid,
            "is_past": is_past_item,
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
            "matched_txs_count": match_count,
            "notes": item.get('notes') or ''
        }
        deadlines_list.append(formatted_item)
        
        # Attach to calendar matrix month(s)
        c_months_str = item.get('custom_months') or ''
        
        if c_months_str and (rec_type == 'CUSTOM_MONTHS'):
            c_months_list = [int(m.strip()) for m in c_months_str.split(',') if m.strip().isdigit()]
            for ym_k, m_obj in month_map.items():
                if m_obj['month_num'] in c_months_list:
                    m_obj["deadlines"].append(formatted_item)
                    m_obj["total_expected"] += expected
                    m_obj["total_paid"] += final_total_paid
                    m_obj["total_remaining"] += remaining_to_pay
                    m_obj["grand_total_month"] += expected
                    m_obj["items_count"] += 1
        elif rec_type == 'ANNUAL':
            due_month_int = int(due_ym.split('-')[1]) if '-' in due_ym else reference_date.month
            for ym_k, m_obj in month_map.items():
                if m_obj['month_num'] == due_month_int:
                    if ym_k == due_ym:
                        # Anno di registrazione originale (presente o storico)
                        m_obj["deadlines"].append(formatted_item)
                        m_obj["total_expected"] += expected
                        m_obj["total_paid"] += final_total_paid
                        m_obj["total_remaining"] += remaining_to_pay
                        m_obj["grand_total_month"] += expected
                        m_obj["items_count"] += 1
                    elif ym_k > due_ym:
                        # Anno futuro proiettato: ricalcola matching per l'anno futuro
                        f_total, f_p1, f_p2, f_cnt = _compute_match(
                            pat, ym_k, due_day, target_type,
                            p1['id'], p2['id'], all_recent_txs,
                            profiles_count=len(profiles_rows)
                        )
                        f_is_paid = (f_total >= (expected - 0.05))
                        f_is_partial = (f_total > 0.05 and not f_is_paid)
                        f_progress = min(100.0, round(f_total / expected * 100.0, 1)) if expected > 0 else 0.0
                        f_remaining = max(0.0, round(expected - f_total, 2))
                        f_p1_missing = max(0.0, round(formatted_item.get('p1_target', 0.0) - f_p1, 2))
                        f_p2_missing = max(0.0, round(formatted_item.get('p2_target', 0.0) - f_p2, 2))
                        if f_is_paid:
                            f_status_code, f_status_label, f_status_color = "COMPLETED", "Completata ✅", "#10b981"
                        elif f_is_partial:
                            f_status_code = "PARTIAL"
                            f_status_label = f"In Corso ({f_progress:.0f}%) ⏳"
                            f_status_color = "#eab308"
                        else:
                            f_status_code = "PENDING"
                            f_status_label = "Da Saldare 🚨"
                            f_status_color = "#f87171"
                        future_year = ym_k.split('-')[0]
                        future_item = dict(formatted_item)
                        future_item.update({
                            "year_month": ym_k,
                            "due_date_str": f"{due_day} {MESI_BREVI_IT[due_month_int-1]} {future_year}",
                            "is_paid": f_is_paid,
                            "is_partial": f_is_partial,
                            "is_past": False,
                            "total_paid": f_total,
                            "remaining_to_pay": f_remaining,
                            "progress_pct": f_progress,
                            "p1_paid": f_p1,
                            "p2_paid": f_p2,
                            "p1_missing": f_p1_missing,
                            "p2_missing": f_p2_missing,
                            "matched_txs_count": f_cnt,
                            "status_code": f_status_code,
                            "status_label": f_status_label,
                            "status_color": f_status_color,
                        })
                        m_obj["deadlines"].append(future_item)
                        deadlines_list.append(future_item)
                        m_obj["total_paid"] += f_total
                        m_obj["total_remaining"] += f_remaining
                        m_obj["total_expected"] += expected
                        m_obj["grand_total_month"] += expected
                        m_obj["items_count"] += 1
        elif rec_type == 'BIENNIAL':
            try:
                base_year = int(due_ym.split('-')[0])
                due_month_int = int(due_ym.split('-')[1])
            except Exception:
                base_year = reference_date.year
                due_month_int = reference_date.month

            for ym_k, m_obj in month_map.items():
                if m_obj['month_num'] == due_month_int and ((m_obj['year'] - base_year) % 2 == 0):
                    if ym_k == due_ym:
                        m_obj["deadlines"].append(formatted_item)
                        m_obj["total_expected"] += expected
                        m_obj["total_paid"] += final_total_paid
                        m_obj["total_remaining"] += remaining_to_pay
                        m_obj["grand_total_month"] += expected
                        m_obj["items_count"] += 1
                    elif ym_k > due_ym:
                        f_total, f_p1, f_p2, f_cnt = _compute_match(
                            pat, ym_k, due_day, target_type,
                            p1['id'], p2['id'], all_recent_txs,
                            profiles_count=len(profiles_rows)
                        )
                        f_is_paid = (f_total >= (expected - 0.05))
                        f_is_partial = (f_total > 0.05 and not f_is_paid)
                        f_progress = min(100.0, round(f_total / expected * 100.0, 1)) if expected > 0 else 0.0
                        f_remaining = max(0.0, round(expected - f_total, 2))
                        f_p1_missing = max(0.0, round(formatted_item.get('p1_target', 0.0) - f_p1, 2))
                        f_p2_missing = max(0.0, round(formatted_item.get('p2_target', 0.0) - f_p2, 2))
                        if f_is_paid:
                            f_status_code, f_status_label, f_status_color = "COMPLETED", "Completata ✅", "#10b981"
                        elif f_is_partial:
                            f_status_code = "PARTIAL"
                            f_status_label = f"In Corso ({f_progress:.0f}%) ⏳"
                            f_status_color = "#eab308"
                        else:
                            f_status_code = "PENDING"
                            f_status_label = "Da Saldare 🚨"
                            f_status_color = "#f87171"
                        future_year = ym_k.split('-')[0]
                        future_item = dict(formatted_item)
                        future_item.update({
                            "year_month": ym_k,
                            "due_date_str": f"{due_day} {MESI_BREVI_IT[due_month_int-1]} {future_year}",
                            "is_paid": f_is_paid,
                            "is_partial": f_is_partial,
                            "is_past": False,
                            "total_paid": f_total,
                            "remaining_to_pay": f_remaining,
                            "progress_pct": f_progress,
                            "p1_paid": f_p1,
                            "p2_paid": f_p2,
                            "p1_missing": f_p1_missing,
                            "p2_missing": f_p2_missing,
                            "matched_txs_count": f_cnt,
                            "status_code": f_status_code,
                            "status_label": f_status_label,
                            "status_color": f_status_color,
                        })
                        m_obj["deadlines"].append(future_item)
                        deadlines_list.append(future_item)
                        m_obj["total_paid"] += f_total
                        m_obj["total_remaining"] += f_remaining
                        m_obj["total_expected"] += expected
                        m_obj["grand_total_month"] += expected
                        m_obj["items_count"] += 1
        elif due_ym in month_map:
            month_map[due_ym]["deadlines"].append(formatted_item)
            month_map[due_ym]["total_expected"] += expected
            month_map[due_ym]["total_paid"] += final_total_paid
            month_map[due_ym]["total_remaining"] += remaining_to_pay
            month_map[due_ym]["grand_total_month"] += expected
            month_map[due_ym]["items_count"] += 1
            
    # Calculate totals for each calendar year
    for cy in calendar_years:
        cy["total_expected"] = sum(m["total_expected"] for m in cy["months"])
        cy["total_paid"] = sum(m["total_paid"] for m in cy["months"])
        cy["total_remaining"] = max(0.0, cy["total_expected"] - cy["total_paid"])
        cy["progress_pct"] = min(100.0, round((cy["total_paid"] / cy["total_expected"] * 100.0), 1)) if cy["total_expected"] > 0 else 0.0

    conn.close()
    
    # Sort deadlines in list: active pending first, then by date, then historic
    deadlines_list.sort(key=lambda d: (d.get('is_past', False), d['is_paid'], d['year_month'], d['due_day']))
    
    # I KPI in alto conteggiano SOLO le scadenze correnti e future (year_month >= curr_ym)
    active_current_future = [d for d in deadlines_list if not d.get('is_past', False)]
    total_expected_active = sum(d['expected_amount'] for d in active_current_future)
    total_paid_active = sum(d['total_paid'] for d in active_current_future)
    total_remaining_active = sum(d['remaining_to_pay'] for d in active_current_future)
    overall_progress_active = min(100.0, round((total_paid_active / total_expected_active * 100.0), 1)) if total_expected_active > 0 else 0.0
    
    return {
        "deadlines": deadlines_list,
        "timeline_months": list(month_map.values()),
        "calendar_years": calendar_years,
        "curr_year": curr_year_int,
        "next_year": next_year_int,
        "total_expected": total_expected_active,
        "total_paid": total_paid_active,
        "total_remaining": total_remaining_active,
        "overall_progress": overall_progress_active,
        "active_deadlines_count": len([d for d in active_current_future if not d['is_paid']]),
        "completed_count": len([d for d in active_current_future if d['is_paid']]),
        "historic_count": len([d for d in deadlines_list if d.get('is_past', False)]),
        "p1": p1,
        "p2": p2,
        "p1_first": p1_first,
        "p2_first": p2_first,
        "catalog": DEADLINES_CATALOG
    }


def auto_seed_typical_family_deadlines(workspace_id, current_year=2026):
    """
    Funzione disattivata: le scadenze vengono aggiunte esclusivamente dall'utente
    tramite la modale o le transazioni.
    """
    pass
