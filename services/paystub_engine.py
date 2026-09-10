import calendar
from datetime import datetime
from database import get_db_connection

def parse_float(val, default=0.0):
    if val is None or val == '':
        return default
    try:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            s = val.replace("€", "").strip()
            if "," in s and "." in s:
                # e.g. "1.950,00" -> remove thousands dot, replace comma with dot
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                # e.g. "1950,00" -> replace comma with dot
                s = s.replace(",", ".")
            return float(s)
        return float(val)
    except (ValueError, TypeError):
        return default


PAYSTUB_GLOSSARY = {
    'paga_base': {
        'title': 'Paga Base / Tabellare CCNL',
        'icon': '💼',
        'what': 'La retribuzione minima garantita stabilita dal Contratto Collettivo Nazionale (es. Metalmeccanici) per il tuo livello.',
        'how': 'Fissata dalle tabelle contrattuali nazionali e rivalutata periodicamente con i rinnovi di categoria.',
        'tip': 'Non può mai essere ridotta dall\'azienda. È la base su cui si calcolano straordinari, scatti e TFR.'
    },
    'superminimo': {
        'title': 'Superminimo Individuale',
        'icon': '⭐',
        'what': 'Un aumento concordato individualmente tra te e l\'azienda, che si somma alla paga base del CCNL.',
        'how': 'Può essere "Assorbibile" (si riduce all\'aumentare del CCNL) o "Non assorbibile" (rimane fisso e si aggiunge a ogni aumento).',
        'tip': 'Verifica se sulla lettera di assunzione è NON assorbibile per non perdere il valore negli anni!'
    },
    'scatti_anzianita': {
        'title': 'Scatti di Anzianità',
        'icon': '⏳',
        'what': 'Aumenti periodici automatici maturati per la permanenza continuativa nella stessa azienda (ogni 2 o 3 anni).',
        'how': 'Importo fisso stabilito dal CCNL moltiplicato per il numero di scatti maturati (es. 4 o 5 scatti).',
        'tip': 'Scattano automaticamente nel mese successivo al compimento del biennio o triennio di anzianità.'
    },
    'inps': {
        'title': 'Contributi Previdenziali INPS',
        'icon': '🏛️',
        'what': 'La quota versata all\'INPS per finanziare la tua pensione pubblica futura, maternità, malattia e cassa integrazione.',
        'how': 'Di norma è il 9,19% o 9,49% dell\'imponibile previdenziale lordo (al netto di eventuale taglio del cuneo fiscale).',
        'tip': 'I contributi INPS sono interamente deducibili: abbassano la base imponibile su cui si calcola l\'IRPEF!'
    },
    'irpef_lorda': {
        'title': 'IRPEF Lorda',
        'icon': '📊',
        'what': 'L\'imposta sul reddito calcolata a scaglioni prima di applicare gli sconti fiscali (detrazioni).',
        'how': 'Aliquote progressive per scaglioni (23% fino a 28k€, 35% fino a 50k€, 43% oltre).',
        'tip': 'Non è ciò che paghi realmente, perché da questa cifra vengono sottratte le tue detrazioni.'
    },
    'detrazioni': {
        'title': 'Detrazioni Lavoro Dipendente & Famiglia',
        'icon': '🛡️',
        'what': 'Sconti fiscali che lo Stato riconosce ai lavoratori dipendenti per ridurre le tasse da pagare.',
        'how': 'Calcolate in misura decrescente all\'aumentare del reddito complessivo (si azzerano sopra i 50.000 €).',
        'tip': 'Riducono euro su euro l\'IRPEF lorda trattenuta ogni mese in busta paga.'
    },
    'irpef_netta': {
        'title': 'IRPEF Netta Trattenuta',
        'icon': '💵',
        'what': 'L\'imposta effettiva che il datore di lavoro trattiene dallo stipendio e versa all\'Agenzia delle Entrate.',
        'how': 'Formula: IRPEF Lorda - Detrazioni Lavoro Dipendente = IRPEF Netta.',
        'tip': 'Nel Modello 730 questa cifra viene conguagliata con le spese sanitarie e deduzioni per darti il rimborso.'
    },
    'addizionali': {
        'title': 'Addizionali Regionali & Comunali',
        'icon': '📍',
        'what': 'Tasse locali destinate alla tua Regione (es. sanità) e al tuo Comune di residenza.',
        'how': 'Calcolate sul reddito dell\'anno precedente e rateizzate di norma in 9-11 rate da marzo a novembre.',
        'tip': 'Ecco spiegato perché tra marzo e novembre il netto è lievemente inferiore rispetto a gennaio e febbraio!'
    },
    'fondo_pensione': {
        'title': 'Fondo Pensione Complementare (es. FONDAPI / COMETA)',
        'icon': '🚀',
        'what': 'La previdenza integrativa dove confluiscono il tuo TFR e i contributi mensili per la seconda pensione.',
        'how': 'Tu versi una quota (es. 1,2% o importo fisso), e l\'AZIENDA è obbligata a versare una quota aggiuntiva a suo carico (soldi extra gratis per te)!',
        'tip': 'I tuoi versamenti sono deducibili fino a 5.164,57 €/anno, permettendoti di recuperare fino al 43% di tasse nel 730!'
    },
    'tfr': {
        'title': 'T.F.R. (Trattamento di Fine Rapporto)',
        'icon': '💰',
        'what': 'La "liquidazione": stipendio differito accantonato ogni mese che ti viene liquidato quando lasci l\'azienda o vai in pensione.',
        'how': 'Maturazione mensile: Retribuzione Utile divisa per 13,5 (~6,91% del lordo annuo).',
        'tip': 'Nel fondo pensione beneficia di tassazione agevolata (dal 15% al 9%) rispetto a lasciarlo in azienda (23-43%).'
    },
    'ferie_rol': {
        'title': 'Ferie, Permessi (P.A.R.) & Conto Ore',
        'icon': '🏖️',
        'what': 'Il tuo tesoretto di ore di riposo retribuito accumulate e non ancora godute.',
        'how': 'Ogni mese maturi circa 2-2,5 giorni tra Ferie e R.O.L./P.A.R. Le ore non usate restano a credito.',
        'tip': 'Se lasci l\'azienda o ti dimetti, tutte le ore residue devono esserti pagate al 100% come indennità economica!'
    },
    'buoni_pasto': {
        'title': 'Buoni Pasto Elettronici / Welfare Esentasse',
        'icon': '🥪',
        'what': 'Voucher elettronici aziendali erogati per ogni giornata di presenza effettiva al lavoro per le spese alimentari.',
        'how': 'Completamente esentasse (no INPS, no IRPEF) fino a un massimo di 8,00 € al giorno per i buoni elettronici (Art. 51 TUIR).',
        'tip': 'Rappresentano potere d\'acquisto netto puro: 16 buoni da 8€ equivalgono a 128€ netti in tasca extra ogni mese!'
    },
    'premi_bonus': {
        'title': 'Premi di Risultato / Bonus M.B.O. / Una Tantum',
        'icon': '🏆',
        'what': 'Compensi variabili legati al raggiungimento di obiettivi individuali (M.B.O.) o aziendali (Premio di Risultato / Produzione).',
        'how': 'I premi di risultato legati ad accordi sindacali possono beneficiare dell\'imposta sostitutiva agevolata al 5% fino a 3.000 €, oppure della conversione esentasse al 100% in Welfare Aziendale.',
        'tip': 'Convertire il bonus MBO in Welfare ti permette di azzerare completamente le trattenute IRPEF (fino al 43%) e INPS!'
    }
}

def calculate_paystub_metrics(form_data):
    """
    Parses and verifies consistency of paystub figures.
    Returns cleaned dict with computed totals and checks.
    """
    base_salary = parse_float(form_data.get('base_salary'))
    contingenza = parse_float(form_data.get('contingenza'))
    superminimo = parse_float(form_data.get('superminimo'))
    scatti_anzianita = parse_float(form_data.get('scatti_anzianita'))
    overtime_amount = parse_float(form_data.get('overtime_amount'))
    bonuses = parse_float(form_data.get('bonuses'))
    fringe_benefit = parse_float(form_data.get('fringe_benefit'))
    other_additions = parse_float(form_data.get('other_additions'))

    sum_gross_components = (base_salary + contingenza + superminimo + scatti_anzianita +
                            overtime_amount + bonuses + other_additions)
    gross_input = parse_float(form_data.get('gross_amount'))
    gross_amount = gross_input if gross_input > 0 else sum_gross_components

    # Taxes & Deductions
    inps_tax = parse_float(form_data.get('inps_tax'))
    irpef_gross = parse_float(form_data.get('irpef_gross'))
    tax_deductions = parse_float(form_data.get('tax_deductions'))
    
    irpef_net_input = parse_float(form_data.get('irpef_net'))
    if irpef_net_input > 0:
        irpef_net = irpef_net_input
    elif irpef_gross > 0:
        irpef_net = max(0.0, irpef_gross - tax_deductions)
    else:
        irpef_net = parse_float(form_data.get('irpef_tax'))

    regional_tax = parse_float(form_data.get('regional_tax'))
    municipal_tax_acc = parse_float(form_data.get('municipal_tax_acc'))
    municipal_tax_saldo = parse_float(form_data.get('municipal_tax_saldo'))
    municipal_tax = municipal_tax_acc + municipal_tax_saldo if (municipal_tax_acc + municipal_tax_saldo) > 0 else parse_float(form_data.get('municipal_tax'))
    
    trattamento_integrativo = parse_float(form_data.get('trattamento_integrativo'))
    other_deductions = parse_float(form_data.get('other_deductions'))

    # Pension Fund fields
    pension_fund_name = form_data.get('pension_fund_name', 'Azienda') or form_data.get('tfr_fund_type', 'Azienda') or 'Azienda'
    pension_fund_contrib_employee = parse_float(form_data.get('pension_fund_contrib_employee'))
    pension_fund_contrib_company = parse_float(form_data.get('pension_fund_contrib_company'))
    pension_fund_tfr_month = parse_float(form_data.get('pension_fund_tfr_month'))
    pension_fund_total = parse_float(form_data.get('pension_fund_total'))

    # Net Salary
    net_input = parse_float(form_data.get('net_amount'))
    computed_net = gross_amount - inps_tax - irpef_net - regional_tax - municipal_tax - other_deductions - pension_fund_contrib_employee + trattamento_integrativo
    net_amount = net_input if net_input > 0 else computed_net

    # TFR & Leave
    tfr_month = parse_float(form_data.get('tfr_month'))
    if tfr_month == 0.0 and pension_fund_tfr_month > 0:
        tfr_month = pension_fund_tfr_month
    elif tfr_month == 0.0 and gross_amount > 0:
        tfr_month = round(gross_amount / 13.5, 2)

    tfr_accumulated_total = parse_float(form_data.get('tfr_accumulated_total'))
    if tfr_accumulated_total == 0.0 and pension_fund_total > 0:
        tfr_accumulated_total = pension_fund_total

    ferie_residue_ore = parse_float(form_data.get('ferie_residue_ore'))
    rol_residui_ore = parse_float(form_data.get('rol_residui_ore'))

    # Meal Vouchers (Buoni Pasto)
    ticket_count = parse_float(form_data.get('ticket_count'))
    ticket_unit_val_raw = form_data.get('ticket_unit_value')
    ticket_unit_value = parse_float(ticket_unit_val_raw, default=8.0) if ticket_unit_val_raw is not None and ticket_unit_val_raw != '' else 8.0
    ticket_tot_raw = parse_float(form_data.get('ticket_total_value'))
    ticket_total_value = ticket_tot_raw if ticket_tot_raw > 0 else round(ticket_count * ticket_unit_value, 2)

    total_taxes = round(inps_tax + irpef_net + regional_tax + municipal_tax + other_deductions + pension_fund_contrib_employee, 2)

    return {
        'month': int(form_data.get('month', 1)) if form_data.get('month') else None,
        'year': int(form_data.get('year', 2026)) if form_data.get('year') else None,
        'gross_amount': round(gross_amount, 2),
        'net_amount': round(net_amount, 2),
        'base_salary': round(base_salary, 2),
        'contingenza': round(contingenza, 2),
        'superminimo': round(superminimo, 2),
        'scatti_anzianita': round(scatti_anzianita, 2),
        'overtime_amount': round(overtime_amount, 2),
        'bonuses': round(bonuses, 2),
        'fringe_benefit': round(fringe_benefit, 2),
        'other_additions': round(other_additions, 2),
        'inps_tax': round(inps_tax, 2),
        'irpef_tax': round(irpef_net, 2),
        'irpef_gross': round(irpef_gross, 2),
        'tax_deductions': round(tax_deductions, 2),
        'irpef_net': round(irpef_net, 2),
        'regional_tax': round(regional_tax, 2),
        'municipal_tax': round(municipal_tax, 2),
        'municipal_tax_acc': round(municipal_tax_acc, 2),
        'municipal_tax_saldo': round(municipal_tax_saldo, 2),
        'trattamento_integrativo': round(trattamento_integrativo, 2),
        'other_deductions': round(other_deductions, 2),
        'pension_fund_name': pension_fund_name,
        'pension_fund_contrib_employee': round(pension_fund_contrib_employee, 2),
        'pension_fund_contrib_company': round(pension_fund_contrib_company, 2),
        'pension_fund_tfr_month': round(pension_fund_tfr_month, 2),
        'pension_fund_total': round(pension_fund_total, 2),
        'tfr_month': round(tfr_month, 2),
        'tfr_fund_type': pension_fund_name,
        'tfr_accumulated_total': round(tfr_accumulated_total, 2),
        'ferie_residue_ore': round(ferie_residue_ore, 2),
        'rol_residui_ore': round(rol_residui_ore, 2),
        'ticket_count': round(ticket_count, 1),
        'ticket_unit_value': round(ticket_unit_value, 2),
        'ticket_total_value': round(ticket_total_value, 2),
        'total_taxes': total_taxes,
        'tax_wedge_pct': round((total_taxes / gross_amount * 100), 1) if gross_amount > 0 else 0.0
    }


def get_month_bank_coverage(workspace_id, month, year, profile_id=None):
    """
    Analyzes the presence, timeframe, and completeness of bank transaction imports
    for a given month and year in the workspace, strictly scoped to the active profile.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    m_str = f"{year}-{month:02d}"
    
    # Query transactions in that calendar month for this specific profile
    if profile_id:
        cursor.execute('''
            SELECT 
                COUNT(*) as tx_count,
                MIN(date) as min_date,
                MAX(date) as max_date
            FROM transactions
            WHERE workspace_id = ? AND (profile_id = ? OR profile_id IS NULL) AND date LIKE ?
        ''', (workspace_id, profile_id, f"{m_str}%"))
        row = cursor.fetchone()
        
        cursor.execute('''
            SELECT DISTINCT a.name, a.bank_name
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.workspace_id = ? AND (t.profile_id = ? OR t.profile_id IS NULL) AND t.date LIKE ?
        ''', (workspace_id, profile_id, f"{m_str}%"))
        acc_rows = cursor.fetchall()

        cursor.execute('''
            SELECT COUNT(*) as salary_tx_count
            FROM transactions
            WHERE workspace_id = ? AND (profile_id = ? OR profile_id IS NULL) AND date LIKE ?
              AND (description LIKE '%STIPENDIO%' OR description LIKE '%EMOLUMENTI%' OR description LIKE '%SALARIO%' OR description LIKE '%SMC%')
              AND amount > 0
        ''', (workspace_id, profile_id, f"{m_str}%"))
        salary_count = cursor.fetchone()['salary_tx_count']
    else:
        cursor.execute('''
            SELECT 
                COUNT(*) as tx_count,
                MIN(date) as min_date,
                MAX(date) as max_date
            FROM transactions
            WHERE workspace_id = ? AND date LIKE ?
        ''', (workspace_id, f"{m_str}%"))
        row = cursor.fetchone()
        
        cursor.execute('''
            SELECT DISTINCT a.name, a.bank_name
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.workspace_id = ? AND t.date LIKE ?
        ''', (workspace_id, f"{m_str}%"))
        acc_rows = cursor.fetchall()

        cursor.execute('''
            SELECT COUNT(*) as salary_tx_count
            FROM transactions
            WHERE workspace_id = ? AND date LIKE ?
              AND (description LIKE '%STIPENDIO%' OR description LIKE '%EMOLUMENTI%' OR description LIKE '%SALARIO%' OR description LIKE '%SMC%')
              AND amount > 0
        ''', (workspace_id, f"{m_str}%"))
        salary_count = cursor.fetchone()['salary_tx_count']

    account_names = [f"{r['bank_name'] or r['name']}" for r in acc_rows if r['name'] or r['bank_name']]
    conn.close()

    tx_count = row['tx_count'] if row and row['tx_count'] else 0
    min_date = row['min_date'] if row and row['min_date'] else None
    max_date = row['max_date'] if row and row['max_date'] else None
    
    # Format dates in Italian format (DD/MM/YYYY)
    max_date_it = ""
    if max_date:
        try:
            parts = max_date.split('-')
            max_date_it = f"{parts[2]}/{parts[1]}/{parts[0]}"
        except Exception:
            max_date_it = max_date

    # Assess completeness
    if tx_count == 0 or salary_count == 0:
        coverage_status = 'NOT_IMPORTED'
        coverage_label = f"Nessun accredito stipendio o estratto conto conto corrente registrato per {month:02d}/{year}"
        is_partial = False
        is_complete = False
    else:
        try:
            day_max = int(max_date.split('-')[2]) if max_date else 0
        except Exception:
            day_max = 0

        if day_max >= 26:
            coverage_status = 'COMPLETE'
            coverage_label = f"Estratto conto completo ({tx_count} movimenti fino al {max_date_it})"
            is_partial = False
            is_complete = True
        else:
            coverage_status = 'PARTIAL'
            coverage_label = f"Estratto conto parziale ({tx_count} movimenti fino al {max_date_it})"
            is_partial = True
            is_complete = False

    return {
        'month': month,
        'year': year,
        'tx_count': tx_count,
        'min_date': min_date,
        'max_date': max_date,
        'max_date_it': max_date_it,
        'coverage_status': coverage_status,
        'coverage_label': coverage_label,
        'is_partial': is_partial,
        'is_complete': is_complete,
        'salary_tx_count': salary_count,
        'account_names': account_names
    }


def find_candidate_bank_transfers(workspace_id, profile_id, month, year, net_amount):
    """
    Scans transactions in the workspace to find potential bank salary deposits,
    strictly scoped to the target profile.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    m_str = f"{year}-{month:02d}"
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1
    next_m_str = f"{next_y}-{next_m:02d}"

    query = '''
        SELECT t.*, a.name as account_name, a.bank_name
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE t.workspace_id = ?
          AND (t.profile_id = ? OR t.profile_id IS NULL)
          AND t.amount > 0
          AND (t.date LIKE ? OR t.date LIKE ?)
        ORDER BY t.date DESC
    '''
    cursor.execute(query, (workspace_id, profile_id, f"{m_str}%", f"{next_m_str}%"))
    rows = cursor.fetchall()
    conn.close()

    # Italian month names mapping for causal text matching
    it_month_keywords = {
        1: ['gennaio', 'gen'],
        2: ['febbraio', 'feb'],
        3: ['marzo', 'mar'],
        4: ['aprile', 'apr'],
        5: ['maggio', 'mag'],
        6: ['giugno', 'giu'],
        7: ['luglio', 'lug'],
        8: ['agosto', 'ago'],
        9: ['settembre', 'set'],
        10: ['ottobre', 'ott'],
        11: ['novembre', 'nov'],
        12: ['dicembre', 'dic'],
        13: ['tredicesima', '13esima', '13ª', 'acconto mens suppl', 'mens suppl', 'mens.suppl'],
        14: ['quattordicesima', '14esima', '14ª']
    }

    candidates = []
    for r in rows:
        desc = (r['description'] or '') + ' ' + (r['raw_description'] or '')
        desc_lower = desc.lower()
        amt = float(r['amount'])
        
        score = 0
        reasons = []
        
        if any(kw in desc_lower for kw in ['stipendio', 'emolument', 'retribuz', 'salario', 'busta', 'cedolino', 'accredito']):
            score += 50
            reasons.append("Causale bancaria stipendio")
        elif 'bonifico' in desc_lower or 'disposizione' in desc_lower:
            score += 20
            reasons.append("Bonifico in entrata")

        # Check target month keywords vs other months keywords
        target_kws = it_month_keywords.get(month, [])
        if any(k in desc_lower for k in target_kws) or f"{month:02d}/{year}" in desc_lower or f"{month}/{year}" in desc_lower:
            score += 60
            reasons.append(f"Mese corrispondente nella causale ({r['date']})")
        else:
            # Check if it mentions a DIFFERENT month
            for other_m, other_kws in it_month_keywords.items():
                if other_m != month and any(ok in desc_lower for ok in other_kws):
                    score -= 50
                    break

        # Proximity bonus if in exact paystub calendar month
        if r['date'] and r['date'].startswith(m_str):
            score += 20

        diff = abs(amt - net_amount)
        if diff < 0.05:
            score += 50
            reasons.append("Importo identico al centesimo (100% match)")
        elif diff <= (net_amount * 0.05):
            score += 30
            reasons.append(f"Importo compatibile (diff. {diff:,.2f} €)")
        elif amt >= (net_amount * 0.8) and amt <= (net_amount * 1.2):
            score += 15
            reasons.append("Importo in fascia plausibile")

        if score >= 35 or (diff < 1.0 and amt > 500):
            candidates.append({
                'id': r['id'],
                'date': r['date'],
                'amount': amt,
                'description': r['description'],
                'account_name': r['account_name'] or 'Conto Principale',
                'bank_name': r['bank_name'] or '',
                'score': score,
                'reasons': ", ".join(reasons),
                'is_exact': diff < 0.05
            })

    candidates.sort(key=lambda x: (x['is_exact'], x['score']), reverse=True)
    return candidates

def compare_two_paystubs(current_ps, prev_ps):
    """
    Generates intelligent human-readable explanations of why the net salary changed.
    """
    if not prev_ps:
        return {
            'has_prev': False,
            'summary_text': "Primo cedolino registrato per questo profilo.",
            'diffs': []
        }

    curr_net = float(current_ps['net_amount'])
    prev_net = float(prev_ps['net_amount'])
    net_diff = curr_net - prev_net

    curr_gross = float(current_ps['gross_amount'])
    prev_gross = float(prev_ps['gross_amount'])
    gross_diff = curr_gross - prev_gross

    diffs = []

    # 1. Gross breakdown
    curr_ot = float(current_ps['overtime_amount'] or 0)
    prev_ot = float(prev_ps['overtime_amount'] or 0)
    if curr_ot != prev_ot:
        diffs.append({
            'label': 'Straordinari',
            'diff': curr_ot - prev_ot,
            'type': 'positive' if (curr_ot - prev_ot) > 0 else 'negative',
            'explanation': f"{'+' if (curr_ot - prev_ot) > 0 else ''}{curr_ot - prev_ot:,.2f} € per variazione ore straordinario"
        })

    curr_bonus = float(current_ps['bonuses'] or 0)
    prev_bonus = float(prev_ps['bonuses'] or 0)
    if curr_bonus != prev_bonus:
        diffs.append({
            'label': 'Premi & Bonus',
            'diff': curr_bonus - prev_bonus,
            'type': 'positive' if (curr_bonus - prev_bonus) > 0 else 'negative',
            'explanation': f"{'+' if (curr_bonus - prev_bonus) > 0 else ''}{curr_bonus - prev_bonus:,.2f} € premio di produzione/una tantum"
        })

    # 2. Tax / Deductions differences
    curr_irpef = float(current_ps['irpef_net'] or current_ps['irpef_tax'] or 0)
    prev_irpef = float(prev_ps['irpef_net'] or prev_ps['irpef_tax'] or 0)
    if abs(curr_irpef - prev_irpef) > 5:
        irpef_diff = curr_irpef - prev_irpef
        diffs.append({
            'label': 'IRPEF Netta Trattenuta',
            'diff': -irpef_diff,
            'type': 'negative' if irpef_diff > 0 else 'positive',
            'explanation': f"{'+' if irpef_diff < 0 else '-'}{abs(irpef_diff):,.2f} € di ritenuta IRPEF"
        })

    # Addizionali comunali / regionali
    curr_add = float(current_ps['municipal_tax'] or 0) + float(current_ps['regional_tax'] or 0)
    prev_add = float(prev_ps['municipal_tax'] or 0) + float(prev_ps['regional_tax'] or 0)
    if abs(curr_add - prev_add) > 3:
        add_diff = curr_add - prev_add
        diffs.append({
            'label': 'Addizionali Reg./Com.',
            'diff': -add_diff,
            'type': 'negative' if add_diff > 0 else 'positive',
            'explanation': f"{'+' if add_diff < 0 else '-'}{abs(add_diff):,.2f} € variazione rate addizionali comunali/regionali"
        })

    # 3. Trattamento integrativo (Bonus 100€)
    curr_ti = float(current_ps['trattamento_integrativo'] or 0)
    prev_ti = float(prev_ps['trattamento_integrativo'] or 0)
    if curr_ti != prev_ti:
        ti_diff = curr_ti - prev_ti
        diffs.append({
            'label': 'Trattamento Integrativo',
            'diff': ti_diff,
            'type': 'positive' if ti_diff > 0 else 'negative',
            'explanation': f"{'+' if ti_diff > 0 else ''}{ti_diff:,.2f} € bonus cuneo/trattamento integrativo"
        })

    # Summary text synthesis
    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    prev_m_name = month_names[prev_ps['month']]
    curr_m_name = month_names[current_ps['month']]

    if abs(net_diff) < 2.0:
        summary_text = f"Il netto di {curr_m_name} è sostanzialmente invariato rispetto a {prev_m_name} (differenza minima di {net_diff:+,.2f} €)."
    elif net_diff > 0:
        summary_text = f"Hai incassato +{net_diff:,.2f} € in più rispetto a {prev_m_name}."
    else:
        summary_text = f"Il netto è inferiore di -{abs(net_diff):,.2f} € rispetto a {prev_m_name}."

    return {
        'has_prev': True,
        'prev_month_name': prev_m_name,
        'prev_year': prev_ps['year'],
        'net_diff': round(net_diff, 2),
        'gross_diff': round(gross_diff, 2),
        'summary_text': summary_text,
        'diffs': diffs
    }

def get_profile_paystubs_summary(workspace_id, profile_id, year=None):
    """
    Returns aggregated KPIs, annual trends, TFR progress, and monthly history.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if not year:
        year = datetime.now().year

    query = '''
        SELECT p.*, t.date as matched_tx_date, t.amount as matched_tx_amount, a.bank_name, a.name as account_name
        FROM paystubs p
        LEFT JOIN transactions t ON p.matched_tx_id = t.id
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE p.workspace_id = ? AND p.profile_id = ? AND p.year = ?
        ORDER BY p.month DESC
    '''
    cursor.execute(query, (workspace_id, profile_id, year))
    paystubs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    total_gross = sum(p['gross_amount'] for p in paystubs)
    total_net = sum(p['net_amount'] for p in paystubs)
    total_inps = sum(p['inps_tax'] for p in paystubs)
    total_irpef = sum(p['irpef_net'] or p['irpef_tax'] for p in paystubs)
    total_region_com = sum((p['regional_tax'] or 0) + (p['municipal_tax'] or 0) for p in paystubs)
    total_tfr_year = sum(p['tfr_month'] or 0 for p in paystubs)

    count = len(paystubs)
    avg_net = total_net / count if count > 0 else 0.0
    avg_gross = total_gross / count if count > 0 else 0.0

    # Latest paystub for Leave / TFR counters (first in DESC order)
    latest_ps = paystubs[0] if paystubs else None
    latest_tfr_total = latest_ps['tfr_accumulated_total'] if latest_ps and latest_ps['tfr_accumulated_total'] > 0 else total_tfr_year
    latest_ferie_ore = latest_ps['ferie_residue_ore'] if latest_ps else 0.0
    latest_rol_ore = latest_ps['rol_residui_ore'] if latest_ps else 0.0

    leave_economic_value = (latest_ferie_ore + latest_rol_ore) * (avg_net / 168.0 if avg_net > 0 else 11.0)

    # Monthly chart data
    month_labels = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
    chart_gross = [0.0] * 12
    chart_net = [0.0] * 12
    chart_taxes = [0.0] * 12

    for p in paystubs:
        m_idx = p['month'] - 1
        if 0 <= m_idx < 12:
            chart_gross[m_idx] = round(p['gross_amount'], 2)
            chart_net[m_idx] = round(p['net_amount'], 2)
            taxes = (p['inps_tax'] or 0) + (p['irpef_net'] or p['irpef_tax'] or 0) + (p['regional_tax'] or 0) + (p['municipal_tax'] or 0)
            chart_taxes[m_idx] = round(taxes, 2)

    return {
        'year': year,
        'count': count,
        'total_gross': round(total_gross, 2),
        'total_net': round(total_net, 2),
        'total_inps': round(total_inps, 2),
        'total_irpef': round(total_irpef, 2),
        'total_region_com': round(total_region_com, 2),
        'total_tfr_year': round(total_tfr_year, 2),
        'avg_net': round(avg_net, 2),
        'avg_gross': round(avg_gross, 2),
        'latest_tfr_total': round(latest_tfr_total, 2),
        'latest_ferie_ore': latest_ferie_ore,
        'latest_rol_ore': latest_rol_ore,
        'leave_economic_value': round(leave_economic_value, 2),
        'chart_labels': month_labels,
        'chart_gross': chart_gross,
        'chart_net': chart_net,
        'chart_taxes': chart_taxes,
        'paystubs': paystubs
    }


def detect_paystub_anomalies(paystub, profile=None, matched_tx=None, prev_paystub=None, bank_coverage=None):
    """
    Scans the paystub for omissions, discrepancies, and contractual anomalies.
    Returns a list of structured anomaly alerts with descriptions, estimated damages, and HR resolution letters.
    """
    anomalies = []
    
    gross = float(paystub.get('gross_amount') or 0.0)
    net = float(paystub.get('net_amount') or 0.0)
    base_sal = float(paystub.get('base_salary') or 0.0)
    
    fund_name = paystub.get('pension_fund_name') or paystub.get('tfr_fund_type') or 'Azienda'
    fund_dip = float(paystub.get('pension_fund_contrib_employee') or 0.0)
    fund_dtr = float(paystub.get('pension_fund_contrib_company') or 0.0)
    fund_tfr_m = float(paystub.get('pension_fund_tfr_month') or 0.0)
    
    month_val = paystub.get('month', 1)
    year_val = paystub.get('year', 2026)
    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
                   "13ª Mensilità", "14ª Mensilità", "Premio di Risultato"]
    m_name = month_names[month_val] if 1 <= month_val < len(month_names) else f"Mese {month_val}"
    worker_name = profile.get('name', 'Dipendente') if profile else 'Dipendente'

    # Anomaly 1: Fondo Pensione - Contributo Dipendente trattenuto ma Contributo Datoriale (Azienda) Mancante!
    if fund_dip > 0 and fund_dtr == 0.0 and fund_name not in ['Azienda', '', None]:
        est_monthly_loss = round(base_sal * 0.02, 2) if base_sal > 0 else 50.0
        est_yearly_loss = est_monthly_loss * 12
        anomalies.append({
            'code': 'PENSION_FUND_NO_COMPANY_CONTRIB',
            'severity': 'CRITICAL',
            'severity_label': 'Anomalia Fondo Pensione',
            'badge_color': '#ef4444',
            'icon': '🚨',
            'title': f'Contributo Datoriale Mancante su {fund_name}',
            'what': f'Risulta trattenuta la tua quota lavoratore ({fund_dip:,.2f} €), ma l\'azienda NON ha versato il contributo a suo carico ({est_monthly_loss:,.2f} € stimate).',
            'impact': f'Stai perdendo circa {est_monthly_loss:,.2f} € al mese (~{est_yearly_loss:,.2f} € all\'anno) di contributi a fondo perduto dovuti per contratto dal datore di lavoro!',
            'action': 'Richiedi l\'immediata regolarizzazione del contributo datoriale con accredito retroattivo delle quote non versate.',
            'hr_template': f"""Oggetto: Richiesta regolarizzazione contributo datoriale {fund_name} - {worker_name}

Spett.le Ufficio Risorse Umane / Amministrazione del Personale,

Con la presente desidero segnalare che nel mio cedolino di {m_name} {year_val} risulta trattenuto il contributo dipendente per il fondo {fund_name} (pari a € {fund_dip:,.2f}), tuttavia non risulta esposto il contributo obbligatorio a carico azienda previsto dal CCNL applicato.

Vi chiedo cortesemente di verificare la mia posizione contributiva e di procedere all'accredito delle quote datoriali correnti e dei relativi arretrati maturati sul fondo {fund_name}.

Resto a disposizione per qualsiasi chiarimento.
Cordiali saluti,
{worker_name}"""
        })

    # Anomaly 2: Fondo Pensione - Quota TFR mensile non accantonata al Fondo
    if fund_name not in ['Azienda', '', None] and fund_tfr_m == 0.0 and gross > 1000:
        est_tfr_m = round(gross / 13.5, 2)
        anomalies.append({
            'code': 'PENSION_FUND_NO_TFR',
            'severity': 'HIGH',
            'severity_label': 'Mancato TFR al Fondo',
            'badge_color': '#f59e0b',
            'icon': '⚠️',
            'title': f'Quota TFR non trasferita al Fondo {fund_name}',
            'what': f'Il tuo TFR mensile (stimato in circa {est_tfr_m:,.2f} €) non risulta accreditato al fondo di previdenza complementare {fund_name}.',
            'impact': f'Il TFR rischia di rimanere in azienda o all\'INPS perdendo la tassazione agevolata del fondo (dal 15% al 9%).',
            'action': 'Verifica se l\'adesione al fondo include la destinazione del 100% del TFR maturando.',
            'hr_template': f"""Oggetto: Verifica destinazione TFR mensile {fund_name} - {worker_name}

Spett.le Amministrazione,
nel cedolino di {m_name} {year_val} non riscontro il conferimento della quota mensile di TFR a favore del fondo {fund_name}. 
Avendo optato per la destinazione del TFR alla previdenza complementare, vi chiedo di verificare che il flusso di versamento sia regolarmente attivo.

Ringraziando per la disponibilità, porgo cordiali saluti.
{worker_name}"""
        })

    # Anomaly 3: Riconciliazione Bancaria - Valutazione intelligente con stato dell'import bancario
    if matched_tx:
        tx_amt = float(matched_tx.get('amount') or 0.0)
        diff_bank = net - tx_amt
        if diff_bank > 1.0:
            bon_val = float(paystub.get('bonuses') or 0.0)
            bonus_note = f" (Nota: Nel cedolino è presente una voce Premio/MBO di {bon_val:,.2f} €. Se hai destinato parte del premio a Welfare aziendale / flexible benefit o se l'azienda lo eroga in tranche separata, questo spiega la differenza)." if bon_val > 0 else ""
            
            anomalies.append({
                'code': 'BANK_TRANSFER_UNDERPAID',
                'severity': 'HIGH' if bon_val > 0 else 'CRITICAL',
                'severity_label': 'Differenza Bonifico' if bon_val == 0 else 'Discrepanza Bonifico (Bonus MBO presente)',
                'badge_color': '#f59e0b' if bon_val > 0 else '#ef4444',
                'icon': '💡' if bon_val > 0 else '🚨',
                'title': f'Bonifico Bancario Inferiore al Netto Cedolino (-{diff_bank:,.2f} €)',
                'what': f'La busta paga indica un netto di {net:,.2f} €, mentre il bonifico registrato sul conto corrente ammonta a {tx_amt:,.2f} € (differenza di -{diff_bank:,.2f} €).{bonus_note}',
                'impact': f'Risultano {diff_bank:,.2f} € di differenza rispetto al netto del prospetto paga.',
                'action': 'Verifica se l\'eccedenza del premio è stata convertita in Welfare aziendale esentasse o se è previsto un bonifico integrativo.',
                'hr_template': f"""Oggetto: Richiesta chiarimento liquidazione netto cedolino {m_name} {year_val} - {worker_name}

Spett.le Ufficio Risorse Umane / Amministrazione del Personale,
sul prospetto paga di {m_name} {year_val} il netto a pagare risulta pari a € {net:,.2f}, mentre l'accredito registrato sul conto corrente ammonta a € {tx_amt:,.2f} (differenza di € {diff_bank:,.2f}).

Vi chiedo cortesemente un riscontro circa tale differenza (ad es. per eventuale conversione Welfare o disposizione integrativa).

Cordiali saluti,
{worker_name}"""
            })
    else:
        # If no matched transaction, check bank import coverage for the month
        if bank_coverage:
            if bank_coverage['is_partial']:
                anomalies.append({
                    'code': 'BANK_STATEMENT_PARTIAL',
                    'severity': 'LOW',
                    'severity_label': 'Estratto Conto Parziale',
                    'badge_color': '#f59e0b',
                    'icon': '⏳',
                    'title': f'Estratto Conto Bancario Parziale (fino al {bank_coverage.get("max_date_it", "")})',
                    'what': f'I movimenti bancari registrati per {m_name} {year_val} arrivano solo fino al {bank_coverage.get("max_date_it", "")} ({bank_coverage.get("tx_count", 0)} movimenti caricati). I bonifici di fine mese non sono ancora presenti nell\'estratto conto.',
                    'impact': 'La riconciliazione automatica dello stipendio potrà essere completata non appena importerai i movimenti fino a fine mese.',
                    'action': 'Carica l\'estratto conto completo comprendente i movimenti di fine mese (dal 26 in poi).',
                    'hr_template': None
                })
            elif bank_coverage['is_complete'] and bank_coverage['tx_count'] > 0:
                anomalies.append({
                    'code': 'BANK_TRANSFER_MISSING',
                    'severity': 'HIGH',
                    'severity_label': 'Bonifico Non Trovato',
                    'badge_color': '#ef4444',
                    'icon': '🚨',
                    'title': f'Bonifico Non Rilevato nell\'Estratto Conto Completo',
                    'what': f'L\'estratto conto di {m_name} {year_val} è completo fino al {bank_coverage.get("max_date_it", "")} ({bank_coverage.get("tx_count", 0)} movimenti registrati), ma non è stato trovato alcun accredito di stipendio compatibile con il netto di {net:,.2f} €.',
                    'impact': f'Manca il riscontro contabile dell\'accredito di {net:,.2f} € sul tuo conto corrente.',
                    'action': 'Verifica se l\'accredito è avvenuto su un conto corrente alternativo o richiedi la ricevuta contabile CRO/TRN all\'azienda.',
                    'hr_template': f"""Oggetto: Verifica accredito stipendio {m_name} {year_val} - {worker_name}

Spett.le Ufficio Amministrazione / Paghe,
sul prospetto paga di {m_name} {year_val} risulta un netto a pagare di € {net:,.2f}. 
Dalle verifiche sul mio conto corrente non riscontro il relativo accredito bancario. 

Vi chiedo cortesemente di fornirmi il codice CRO/TRN del bonifico o conferma dell'avvenuta disposizione.

Cordiali saluti,
{worker_name}"""
                })

    # Anomaly 4: Superminimo Ridotto/Assorbito senza aumento di Paga Base
    if prev_paystub:
        prev_sup = float(prev_paystub.get('superminimo') or 0.0)
        curr_sup = float(paystub.get('superminimo') or 0.0)
        prev_base = float(prev_paystub.get('base_salary') or 0.0)
        curr_base = float(paystub.get('base_salary') or 0.0)
        
        if prev_sup > curr_sup and curr_base <= prev_base:
            sup_diff = prev_sup - curr_sup
            anomalies.append({
                'code': 'SUPERMINIMO_ANOMALOUS_REDUCTION',
                'severity': 'HIGH',
                'severity_label': 'Superminimo Ridotto',
                'badge_color': '#f59e0b',
                'icon': '📉',
                'title': f'Riduzione Inaspettata del Superminimo (-{sup_diff:,.2f} €)',
                'what': f'Il tuo superminimo è passato da {prev_sup:,.2f} € a {curr_sup:,.2f} € senza che vi sia stato un incremento della paga base tabellare.',
                'impact': f'Hai una retribuzione lorda inferiore di {sup_diff:,.2f} €/mese rispetto al mese precedente.',
                'action': 'Controlla la tua lettera di assunzione per verificare la natura del superminimo (assorbibile o non assorbibile).',
                'hr_template': f"""Oggetto: Chiarimento variazione voce superminimo cedolino {m_name} {year_val} - {worker_name}

Spett.le Risorse Umane,
riscontro nel cedolino di {m_name} una diminuzione della voce Superminimo da € {prev_sup:,.2f} a € {curr_sup:,.2f}. 
Vi chiedo cortesemente un chiarimento sulla causale di tale variazione retributiva.

Cordiali saluti,
{worker_name}"""
            })

    return anomalies
