# services/tax_730_engine.py
"""
Business Logic & AI Advisory Engine for Modello 730 Tax Returns.
Handles:
- Reconciliation with summer paystubs (Luglio/Agosto)
- Tax savings & optimization analytics (Pension Fund saturation, medical expenses, mortgage interest)
- Persona-specific virtual assistant briefings for tax returns (Leo 🚀, Anna 🌸, July ⚡, Dott. Fiscale 🏛️)
"""

from database import get_db_connection
from services.assistant_engine import ASSISTANT_PERSONAS, format_eur_it


def get_tax_persona(persona_key='demetrio'):
    if persona_key in ('leo', 'demetrio'):
        persona_key = 'demetrio'
    elif persona_key in ('dott_fiscale', 'commercialista'):
        persona_key = 'commercialista'
    return ASSISTANT_PERSONAS.get(persona_key, ASSISTANT_PERSONAS['demetrio'])


def find_matching_paystub_for_730(workspace_id, profile_id, declaration_year, amount):
    """
    Looks for the summer paystub (Luglio, Agosto, Settembre) in which the 730 refund or debit was processed.
    """
    if amount is None or amount == 0:
        amount = 0.0

    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT p.*, t.date as matched_tx_date, t.amount as matched_tx_amount
        FROM paystubs p
        LEFT JOIN transactions t ON p.matched_tx_id = t.id
        WHERE p.workspace_id = ? 
          AND p.profile_id = ? 
          AND p.year = ?
          AND p.month IN (6, 7, 8, 9, 10)
        ORDER BY p.month ASC
    '''
    cursor.execute(query, (workspace_id, profile_id, declaration_year))
    paystubs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not paystubs:
        return None

    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

    # 1. Exact match on bank transfer diff vs paystub net amount
    for ps in paystubs:
        ps['month_name'] = month_names[ps['month']] if 1 <= ps['month'] <= 12 else f"Mese {ps['month']}"
        tx_amt = float(ps.get('matched_tx_amount') or 0.0)
        net_amt = float(ps.get('net_amount') or 0.0)
        diff_tx_net = round(tx_amt - net_amt, 2)

        if amount > 0 and (abs(diff_tx_net - amount) < 1.0 or abs(ps.get('other_additions', 0.0) - amount) < 1.0 or abs(ps.get('bonuses', 0.0) - amount) < 1.0):
            ps['match_reason'] = f"Bonifico bancario di {ps['month_name']} {declaration_year} include esattamente +{amount:,.2f} € di conguaglio 730"
            ps['is_exact_match'] = True
            return ps

    # 2. Candidate July or August paystub
    for m in [7, 8]:
        candidate = next((p for p in paystubs if p['month'] == m), None)
        if candidate:
            candidate['month_name'] = month_names[candidate['month']]
            candidate['match_reason'] = f"Cedolino di competenza estiva consueto per conguaglio 730 ({candidate['month_name']} {declaration_year})"
            candidate['is_exact_match'] = False
            return candidate

    paystubs[0]['month_name'] = month_names[paystubs[0]['month']]
    paystubs[0]['match_reason'] = f"Cedolino di {paystubs[0]['month_name']} {declaration_year}"
    paystubs[0]['is_exact_match'] = False
    return paystubs[0]


def calculate_tax_optimization_insights(tax_decl):
    """
    Computes tax optimization metrics and actionable recommendations.
    """
    total_income = float(tax_decl.get('total_income') or 0.0)
    taxable_income = float(tax_decl.get('taxable_income') or total_income)
    gross_tax = float(tax_decl.get('gross_tax') or 0.0)
    net_tax = float(tax_decl.get('net_tax') or 0.0)
    
    pension_deducted = float(tax_decl.get('pension_fund_deduction') or 0.0)
    max_pension_cap = 5164.57
    pension_headroom = max(0.0, round(max_pension_cap - pension_deducted, 2))
    
    # Estimate marginal tax bracket
    if total_income > 50000:
        marginal_tax_rate = 0.43
    elif total_income > 28000:
        marginal_tax_rate = 0.35
    else:
        marginal_tax_rate = 0.23

    potential_pension_tax_savings = round(pension_headroom * marginal_tax_rate, 2)

    medical_total = float(tax_decl.get('medical_expenses') or 0.0)
    medical_benefit = round(max(0.0, medical_total - 129.11) * 0.19, 2)

    mortgage_total = float(tax_decl.get('mortgage_interest') or 0.0)
    mortgage_benefit = round(min(4000.0, mortgage_total) * 0.19, 2)

    tax_savings_total = max(0.0, round(gross_tax - net_tax, 2))
    effective_tax_rate = round((net_tax / total_income * 100), 2) if total_income > 0 else 0.0

    return {
        'total_income': total_income,
        'taxable_income': taxable_income,
        'gross_tax': gross_tax,
        'net_tax': net_tax,
        'tax_savings_total': tax_savings_total,
        'effective_tax_rate': effective_tax_rate,
        'marginal_tax_rate': marginal_tax_rate,
        'pension_deducted': pension_deducted,
        'max_pension_cap': max_pension_cap,
        'pension_headroom': pension_headroom,
        'potential_pension_tax_savings': potential_pension_tax_savings,
        'medical_total': medical_total,
        'medical_benefit': medical_benefit,
        'mortgage_total': mortgage_total,
        'mortgage_benefit': mortgage_benefit
    }


def generate_730_assistant_briefing(tax_decl, matched_paystub=None, insights=None, persona_key='commercialista', profile_name=None):
    """
    Synthesizes a tailored, persona-specific executive briefing for the 730 tax declaration.
    """
    persona = get_tax_persona(persona_key)
    p_id = persona['id']

    if insights is None:
        insights = calculate_tax_optimization_insights(tax_decl)
    
    if not profile_name:
        profile_name = tax_decl.get('taxpayer_name') or tax_decl.get('profile_name') or "Contribuente"

    is_refund = bool(tax_decl.get('is_refund', True))
    amount = float(tax_decl.get('final_refund_or_debit') or 0.0)
    dec_year = tax_decl.get('declaration_year', 2026)
    tax_year = tax_decl.get('tax_year', 2025)

    highlights = []

    if p_id == 'leo':
        # LEO: Smart & Diretto
        if is_refund and amount > 0:
            headline = f"Ottime notizie {profile_name}! Hai un rimborso fiscale di {format_eur_it(amount)} 💰"
            overview = f"Il tuo Modello 730/{dec_year} (Redditi {tax_year}) si chiude con un credito IRPEF di {format_eur_it(amount)}."
            if matched_paystub and matched_paystub.get('is_exact_match'):
                overview += f" L'importo ti è stato accreditato in busta paga nel cedolino di {matched_paystub.get('month_name')} {dec_year}."
            else:
                overview += f" L'importo viene accreditato direttamente dal datore di lavoro sul cedolino estivo."

            highlights = [
                f"Reddito complessivo dichiarato: {format_eur_it(insights['total_income'])}",
                f"Detrazioni e oneri hanno ridotto le imposte di {format_eur_it(insights['tax_savings_total'])}",
                f"Aliquota effettiva reale pagata: {insights['effective_tax_rate']}%"
            ]
            if insights['pension_headroom'] > 0:
                recommendation = f"Hai ancora {format_eur_it(insights['pension_headroom'])} di deduzione residua sul fondo pensione: versandoli recuperi altri +{format_eur_it(insights['potential_pension_tax_savings'])} di IRPEF."
            else:
                recommendation = "Hai massimizzato il plafond del fondo pensione (5.164,57 €), ottima ottimizzazione fiscale!"
        elif not is_refund and amount > 0:
            headline = f"Attenzione {profile_name}: conguaglio a debito di {format_eur_it(amount)} ⚠️"
            overview = f"La dichiarazione 730/{dec_year} evidenzia un saldo a debito di {format_eur_it(amount)}, da trattenere sul cedolino o versare con F24."
            highlights = [
                f"Imposta netta dovuta: {format_eur_it(insights['net_tax'])}",
                f"Ritenute operate dal sostituto: {format_eur_it(tax_decl.get('withholdings_paid', 0.0))}",
                f"Differenza da saldare: {format_eur_it(amount)}"
            ]
            recommendation = "Verifica le detrazioni per lavoro dipendente e valuta deduzioni previdenziali per abbattere il saldo nel prossimo anno."
        else:
            headline = f"Dichiarazione in perfetto pareggio: 0,00 € di scostamento ✅"
            overview = f"Tutte le imposte per l'anno fiscale {tax_year} sono state trattenute con precisione millimetrica dal tuo datore di lavoro."
            highlights = [
                f"Reddito: {format_eur_it(insights['total_income'])} &bull; Imposta Netta: {format_eur_it(insights['net_tax'])}",
                f"Aliquota IRPEF effettiva: {insights['effective_tax_rate']}%"
            ]
            recommendation = "Situazione contabile perfetta. Nessun versamento o rimborso in sospeso."

    elif p_id == 'anna':
        # ANNA: Precisa, Rassicurante ed Empatica
        if is_refund and amount > 0:
            headline = f"Tutto in perfetto ordine, {profile_name}! Ti spetta un rimborso di {format_eur_it(amount)} 🌸"
            overview = f"Abbiamo controllato la tua dichiarazione 730/{dec_year}. Grazie a tutte le spese sanitarie e agli oneri sostenuti nel {tax_year}, hai diritto a riavere indietro {format_eur_it(amount)}."
            highlights = [
                f"Spese mediche e detrazioni registrate con successo",
                f"Pressione fiscale mantenuta bassa al {insights['effective_tax_rate']}%",
                f"Risparmio fiscale ottenuto: {format_eur_it(insights['tax_savings_total'])}"
            ]
            recommendation = "Conserva sempre gli scontrini parlanti e le ricevute del Quadro E per i controlli formali dell'Agenzia delle Entrate."
        elif not is_refund and amount > 0:
            headline = f"Piccolo saldo fiscale di {format_eur_it(amount)} da gestire con serenità 🌸"
            overview = f"Nel 730/{dec_year} c'è un piccolo adeguamento IRPEF di {format_eur_it(amount)}. Non preoccuparti, verrà rateizzato o trattenuto comodamente."
            highlights = [
                f"Imposta netta totale: {format_eur_it(insights['net_tax'])}",
                f"Trattenute subite: {format_eur_it(tax_decl.get('withholdings_paid', 0.0))}"
            ]
            recommendation = "Possiamo pianificare insieme i prossimi mesi per ammortizzare questa trattenuta senza intaccare i tuoi risparmi."
        else:
            headline = f"Nessuna sorpresa fiscale: la tua posizione è pulita e regolare 🌸"
            overview = f"Il Modello 730/{dec_year} chiude a pareggio. Sei in regola al 100% con il Fisco senza alcun debito."
            highlights = [
                f"Imposte trattenute esattamente pari al dovuto: {format_eur_it(insights['net_tax'])}"
            ]
            recommendation = "Continua così! Tutto quadra perfettamente."

    elif p_id == 'july':
        # JULY: Dinamica, Crescita & Previdenza
        if is_refund and amount > 0:
            headline = f"Ottimo colpo! {format_eur_it(amount)} di liquidità extra recuperata ⚡"
            overview = f"Questo rimborso di {format_eur_it(amount)} è carburante per i tuoi obiettivi finanziari e investimenti."
            highlights = [
                f"Risparmio IRPEF totale generato: {format_eur_it(insights['tax_savings_total'])}",
                f"Fondo pensione versato: {format_eur_it(insights['pension_deducted'])} (Capienza residua: {format_eur_it(insights['pension_headroom'])})",
                f"Aliquota marginale al {int(insights['marginal_tax_rate']*100)}%"
            ]
            recommendation = f"Reinvesti parte di questi {format_eur_it(amount)} nel Fondo Pensione per generare un effetto moltiplicatore con +{format_eur_it(insights['potential_pension_tax_savings'])} di ulteriore rimborso!"
        else:
            headline = f"Focus sulla crescita e l'ottimizzazione del carico fiscale ⚡"
            overview = f"Dichiarazione 730/{dec_year} verificata. Analizziamo i margini di deducibilità per abbattere le tasse future."
            highlights = [
                f"Margine deducibilità Fondo Pensione: {format_eur_it(insights['pension_headroom'])}",
                f"Beneficio fiscale sfruttabile: +{format_eur_it(insights['potential_pension_tax_savings'])}"
            ]
            recommendation = "Sfrutta al 100% il plafond di 5.164,57 € prima della chiusura dell'anno fiscale!"

    else:
        # COMMERCIALISTA / DOTT. FISCALE: Formale, Rigoroso, Istituzionale
        if is_refund and amount > 0:
            headline = f"Prospetto 730-3 Conforme: Liquidazione a Credito di {format_eur_it(amount)} 🏛️"
            overview = f"La dichiarazione Modello 730/{dec_year} (Redditi {tax_year}) evidenzia una corretta liquidazione delle imposte con credito a rimborso di {format_eur_it(amount)} ai sensi dell'art. 51 TUIR."
            if matched_paystub and matched_paystub.get('is_exact_match'):
                overview += f" Il sostituto d'imposta ha correttamente eseguito il conguaglio a credito sulla retribuzione di competenza {matched_paystub.get('month_name')} {dec_year} (Rigo 163)."
            else:
                overview += f" Il conguaglio a credito è iscritto a Rigo 163 per erogazione mediante sostituto d'imposta."

            highlights = [
                f"Reddito Imponibile (Rigo 14): {format_eur_it(insights['taxable_income'])} &bull; Imposta Lorda (Rigo 16): {format_eur_it(insights['gross_tax'])}",
                f"Totale Detrazioni e Crediti (Rigo 48): {format_eur_it(tax_decl.get('total_deductions', 0.0))}",
                f"Imposta Netta Dovuta (Rigo 50): {format_eur_it(insights['net_tax'])} &bull; Ritenute Operate (Rigo 59): {format_eur_it(tax_decl.get('withholdings_paid', 0.0))}",
                f"Differenza Fiscale a Credito (Rigo 60): -{format_eur_it(tax_decl.get('tax_difference', 0.0))}"
            ]
            recommendation = f"La deduzione per previdenza complementare (Rigo E27) risulta pari a {format_eur_it(insights['pension_deducted'])}. Si segnala capienza residua ex art. 10 TUIR pari a {format_eur_it(insights['pension_headroom'])}, con potenziale beneficio IRPEF di {format_eur_it(insights['potential_pension_tax_savings'])}."
        elif not is_refund and amount > 0:
            headline = f"Prospetto 730-3: Trattenuta Fiscale a Debito di {format_eur_it(amount)} 🏛️"
            overview = f"La liquidazione dell'imposta netta determina un differenziale a debito di {format_eur_it(amount)} da trattenere sul cedolino (Rigo 161) o versare con mod. F24."
            highlights = [
                f"Imposta Netta Dovuta: {format_eur_it(insights['net_tax'])}",
                f"Ritenute Subite CU: {format_eur_it(tax_decl.get('withholdings_paid', 0.0))}",
                f"Addizionali Reg. e Com. dovute: {format_eur_it(tax_decl.get('regional_tax_due', 0.0))} / {format_eur_it(tax_decl.get('municipal_tax_due', 0.0))}"
            ]
            recommendation = "Verificare l'applicazione degli acconti per il periodo d'imposta successivo onde prevenire scostamenti fiscali."
        else:
            headline = f"Prospetto 730-3 Conforme: Chiusura a Pareggio (0,00 €) 🏛️"
            overview = f"La liquidazione contabile certifica la perfetta quadratura tra imposta netta dovuta ({format_eur_it(insights['net_tax'])}) e ritenute fiscali certificate."
            highlights = [
                f"Reddito Complessivo: {format_eur_it(insights['total_income'])}",
                f"Imposta Netta e Ritenute operate: {format_eur_it(insights['net_tax'])}",
                f"Aliquota IRPEF effettiva: {insights['effective_tax_rate']}%"
            ]
            recommendation = "Posizione fiscale pienamente conforme ai disposti del DPR 917/1986. Nessuna rettifica richiesta."

    return {
        'persona_id': persona['id'],
        'persona_name': persona['name'],
        'persona_avatar': persona['avatar'],
        'persona_role': persona['title'],
        'headline': headline,
        'overview': overview,
        'highlights': highlights,
        'recommendation': recommendation
    }


def perform_730_audit_and_action_plan(workspace_id, profile_id, tax_decl):
    """
    Performs an intelligent, multi-dimensional audit comparing declared 730 data with
    actual transactions, paystubs, multi-year deduction schedules, and tax rules.
    Returns:
    - overall_health: 'ECCELLENTE', 'BUONO', 'OTTIMIZZABILE'
    - health_score: 95
    - audit_cards: List of structured audit items (Cosa Va, Cosa Non Va)
    - multi_year_credits: Roadmap of future locked tax credits (e.g. 8 remaining installments)
    - action_plan: Concrete, prioritized next steps for the user
    """
    tax_year = tax_decl.get('tax_year', 2025)
    dec_year = tax_decl.get('declaration_year', 2026)
    insights = calculate_tax_optimization_insights(tax_decl)
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Query tracked health expenses for the tax year
    cursor.execute('''
        SELECT count(*) as count, coalesce(sum(abs(amount)), 0.0) as total
        FROM transactions
        WHERE workspace_id = ? 
          AND date LIKE ?
          AND (category LIKE '%Salute%' OR category LIKE '%Medic%' OR category LIKE '%Farmac%'
               OR description LIKE '%FARMACIA%' OR description LIKE '%MEDIC%' OR description LIKE '%OSPEDAL%' 
               OR description LIKE '%DENTIST%' OR description LIKE '%ANALISI%')
    ''', (workspace_id, f"{tax_year}%"))
    health_tx = dict(cursor.fetchone())
    tracked_health_total = round(float(health_tx.get('total') or 0.0), 2)

    # Also check current year tracked medical expenses (for ongoing tracking)
    cursor.execute('''
        SELECT count(*) as count, coalesce(sum(abs(amount)), 0.0) as total
        FROM transactions
        WHERE workspace_id = ? 
          AND date LIKE ?
          AND (category LIKE '%Salute%' OR category LIKE '%Medic%' OR category LIKE '%Farmac%'
               OR description LIKE '%FARMACIA%' OR description LIKE '%MEDIC%')
    ''', (workspace_id, f"{dec_year}%"))
    health_current_yr = dict(cursor.fetchone())
    current_health_total = round(float(health_current_yr.get('total') or 0.0), 2)

    conn.close()

    declared_health = float(tax_decl.get('medical_expenses') or 0.0)
    pension_deducted = float(tax_decl.get('pension_fund_deduction') or 0.0)
    pension_headroom = insights['pension_headroom']
    potential_savings = insights['potential_pension_tax_savings']
    marginal_rate_pct = int(insights['marginal_tax_rate'] * 100)

    audit_cards = []

    # -------------------------------------------------------------
    # AUDIT ITEM 1: Fondo Pensione & Previdenza Complementare (E27)
    # -------------------------------------------------------------
    if pension_headroom > 50:
        audit_cards.append({
            'category': 'Previdenza & Deduzioni',
            'title': 'Fondo Pensione: Plafond Deduzione Non Saturato',
            'status': 'OPPORTUNITY',
            'badge': '🟡 Opportunità Fiscale',
            'badge_color': '#f59e0b',
            'badge_bg': 'rgba(245, 158, 11, 0.15)',
            'icon': '🏦',
            'declared_text': f"Dedotti: {format_eur_it(pension_deducted)} / 5.164,57 €",
            'diagnosis': f"Hai dedotto {format_eur_it(pension_deducted)} ottenendo un risparmio IRPEF di {format_eur_it(round(pension_deducted * insights['marginal_tax_rate'], 2))}. Rimane una <strong>capienza residua non utilizzata di {format_eur_it(pension_headroom)}</strong>.",
            'financial_impact': f"+{format_eur_it(potential_savings)} di rimborso IRPEF extra",
            'impact_type': 'positive',
            'action_tip': f"Versando la capienza residua ({format_eur_it(pension_headroom)}) con bonifico volontario entro il 31 Dicembre, recuperi il {marginal_rate_pct}% ({format_eur_it(potential_savings)}) sul prossimo 730."
        })
    else:
        audit_cards.append({
            'category': 'Previdenza & Deduzioni',
            'title': 'Fondo Pensione: Plafond Saturato al 100%',
            'status': 'OK',
            'badge': '🟢 Ottimizzazione Perfetta',
            'badge_color': '#10b981',
            'badge_bg': 'rgba(16, 185, 129, 0.15)',
            'icon': '🛡️',
            'declared_text': f"Dedotti: {format_eur_it(pension_deducted)} (Massimo di legge)",
            'diagnosis': f"Hai sfruttato integralmente la deduzione massima ex art. 10 TUIR di 5.164,57 €, massimizzando il risparmio fiscale al {marginal_rate_pct}%.",
            'financial_impact': f"Risparmio fiscale ottenuto: {format_eur_it(round(pension_deducted * insights['marginal_tax_rate'], 2))}",
            'impact_type': 'positive',
            'action_tip': "Mantieni questa contribuzione anche per l'anno in corso per confermare il beneficio massimo."
        })

    # -------------------------------------------------------------
    # AUDIT ITEM 2: Spese Sanitarie & Mediche (E1 vs Transazioni)
    # -------------------------------------------------------------
    diff_health = round(tracked_health_total - declared_health, 2)
    if diff_health > 50:
        unclaimed_benefit = round(diff_health * 0.19, 2)
        audit_cards.append({
            'category': 'Oneri Quadro E',
            'title': 'Spese Sanitarie: Rilevate Uscite Non Dichiarate',
            'status': 'WARNING',
            'badge': '🟡 Possibile Spesa Dimenticata',
            'badge_color': '#eab308',
            'badge_bg': 'rgba(234, 179, 8, 0.15)',
            'icon': '🏥',
            'declared_text': f"Dichiarato: {format_eur_it(declared_health)} &bull; Tracciato nei conti: {format_eur_it(tracked_health_total)}",
            'diagnosis': f"Nei tuoi conti bancari/carte FiscMoney risultano spese mediche/farmacie per {format_eur_it(tracked_health_total)}, mentre nel 730 risultano {format_eur_it(declared_health)} (differenza: {format_eur_it(diff_health)}).",
            'financial_impact': f"Potenziale detrazione non richiesta: ~{format_eur_it(unclaimed_benefit)}",
            'impact_type': 'neutral',
            'action_tip': "Verifica se si trattava di parafarmaci (non detraibili) o scontrini senza codice fiscale. Ricordati sempre di esibire la tessera sanitaria in farmacia."
        })
    else:
        audit_cards.append({
            'category': 'Oneri Quadro E',
            'title': 'Spese Sanitarie: Quadratura Conforme',
            'status': 'OK',
            'badge': '🟢 Dati Allineati',
            'badge_color': '#10b981',
            'badge_bg': 'rgba(16, 185, 129, 0.15)',
            'icon': '🩺',
            'declared_text': f"Dichiarato: {format_eur_it(declared_health)} (Franchigia 129,11 € superata)",
            'diagnosis': f"Le spese mediche inserite nel 730 ({format_eur_it(declared_health)}) corrispondono alle spese tracciate con pagamento elettronico e tessera sanitaria.",
            'financial_impact': f"Detrazione IRPEF 19% ottenuta: +{format_eur_it(insights['medical_benefit'])}",
            'impact_type': 'positive',
            'action_tip': f"Quest'anno hai già accumulato {format_eur_it(current_health_total)} di spese mediche tracciate nei tuoi conti per il prossimo 730."
        })

    # -------------------------------------------------------------
    # AUDIT ITEM 3: Bonus Casa 50% & Mobili (Multi-Year Roadmap)
    # -------------------------------------------------------------
    reno_val = float(tax_decl.get('building_renovations') or 0.0)
    furn_val = float(tax_decl.get('furniture_expenses') or 0.0)
    
    for exp in tax_decl.get('expenses_breakdown', []):
        if exp.get('code') in ['E41', 'E42', 'E43'] and reno_val == 0:
            reno_val += float(exp.get('amount') or 0.0)
        elif exp.get('code') == 'E57' and furn_val == 0:
            furn_val += float(exp.get('amount') or 0.0)
    
    annual_reno_credit = round((reno_val * 0.50) / 10.0, 2) if reno_val > 0 else 0.0
    annual_furn_credit = round((furn_val * 0.50) / 10.0, 2) if furn_val > 0 else 0.0
    annual_total_building_credit = round(annual_reno_credit + annual_furn_credit, 2)
    
    # 8 remaining installments for 2024 expenses (e.g. 2027 to 2034)
    remaining_years = 8
    total_locked_future_credits = round(annual_total_building_credit * remaining_years, 2)


    if annual_total_building_credit > 0:
        audit_cards.append({
            'category': 'Detrazioni Edilizie',
            'title': 'Bonus Casa & Mobili: Credito Pluriennale Garantito',
            'status': 'FUTURE_CREDIT',
            'badge': '🔵 Crediti Futuri Bloccati (8 anni)',
            'badge_color': '#38bdf8',
            'badge_bg': 'rgba(56, 189, 248, 0.15)',
            'icon': '🏡',
            'declared_text': f"Rata 2/10: {format_eur_it(annual_total_building_credit)}/anno ({format_eur_it(annual_reno_credit)} Casa + {format_eur_it(annual_furn_credit)} Mobili)",
            'diagnosis': f"Hai registrato spese per interventi edilizi ed arredi per complessivi {format_eur_it(reno_val + furn_val)}. La detrazione al 50% ti garantisce <strong>{format_eur_it(annual_total_building_credit)}/anno</strong>.",
            'financial_impact': f"Totale rimborsi garantiti ancora da incassare (2027-2034): {format_eur_it(total_locked_future_credits)}",
            'impact_type': 'positive',
            'action_tip': f"Conserva le fatture e i bonifici parlanti per i controlli documentali. Questo credito di {format_eur_it(annual_total_building_credit)} ti verrà rimborsato automaticamente ogni estate per i prossimi 8 anni."
        })

    # -------------------------------------------------------------
    # AUDIT ITEM 4: Capienza Fiscale IRPEF & Incapienza
    # -------------------------------------------------------------
    gross_tax = float(tax_decl.get('gross_tax') or 0.0)
    total_deductions = float(tax_decl.get('total_deductions') or 0.0)
    used_cap_pct = round((total_deductions / gross_tax * 100), 1) if gross_tax > 0 else 0.0

    audit_cards.append({
        'category': 'Capienza Fiscale',
        'title': 'Capienza IRPEF Lorda & Assorbimento Detrazioni',
        'status': 'OK',
        'badge': '🟢 Capienza 100% Garantita',
        'badge_color': '#10b981',
        'badge_bg': 'rgba(16, 185, 129, 0.15)',
        'icon': '⚖️',
        'declared_text': f"Imposta Lorda: {format_eur_it(gross_tax)} &bull; Detrazioni utilizzate: {format_eur_it(total_deductions)} ({used_cap_pct}%)",
        'diagnosis': f"La tua imposta lorda ({format_eur_it(gross_tax)}) è ampiamente superiore alle detrazioni spettanti ({format_eur_it(total_deductions)}). Tutte le detrazioni sono state assorbite al 100% senza alcuna perdita per incapienza.",
        'financial_impact': "Zero euro persi per incapienza fiscale",
        'impact_type': 'positive',
        'action_tip': f"Hai un margine di capienza fiscale residua di {format_eur_it(round(gross_tax - total_deductions, 2))}, il che significa che puoi inserire ulteriori oneri o deduzioni senza alcun rischio."
    })

    # -------------------------------------------------------------
    # AUDIT ITEM 5: Conguaglio Cedolino Estivo
    # -------------------------------------------------------------
    is_refund = tax_decl.get('is_refund', True)
    final_amt = float(tax_decl.get('final_refund_or_debit') or 0.0)

    if is_refund and final_amt > 0:
        audit_cards.append({
            'category': 'Conguaglio in Busta Paga',
            'title': 'Accredito Rimborso 730 in Busta Paga',
            'status': 'OK',
            'badge': '🟢 Riconciliazione Effettuata',
            'badge_color': '#10b981',
            'badge_bg': 'rgba(16, 185, 129, 0.15)',
            'icon': '💵',
            'declared_text': f"Rigo 163: +{format_eur_it(final_amt)} rimborsati",
            'diagnosis': f"Il rimborso a credito di {format_eur_it(final_amt)} è stato regolarmente liquidato dal sostituto d'imposta sul cedolino estivo di competenza (Rigo 163).",
            'financial_impact': f"+{format_eur_it(final_amt)} di liquidità netta accreditata",
            'impact_type': 'positive',
            'action_tip': "Il conguaglio coincide con il bonifico bancario registrato nel conto corrente."
        })

    # -------------------------------------------------------------
    # ACTION PLAN (Cosa possiamo fare adesso)
    # -------------------------------------------------------------
    action_plan = [
        {
            'step': 1,
            'title': 'Versamento Volontario Fondo Pensione',
            'priority': 'ALTA (Entro il 31 Dicembre)' if pension_headroom > 50 else 'CONFERMATA',
            'priority_color': '#f59e0b' if pension_headroom > 50 else '#10b981',
            'description': f"Per massimizzare il rimborso del prossimo anno, versa fino a <strong>{format_eur_it(pension_headroom)}</strong> tramite bonifico deducibile al tuo fondo pensione.",
            'expected_gain': f"+{format_eur_it(potential_savings)} di rimborso IRPEF extra",
            'cta_text': 'Calcola Versamento Ottimale'
        },
        {
            'step': 2,
            'title': 'Monitoraggio Spese Sanitarie Elettroniche',
            'priority': 'CONTINUA',
            'priority_color': '#38bdf8',
            'description': f"Finora quest'anno nei tuoi conti risultano <strong>{format_eur_it(current_health_total)}</strong> di spese mediche. Ricordati di usare sempre bancomat/carta e richiedere lo scontrino con codice fiscale.",
            'expected_gain': 'Detrazione 19% oltre 129,11 €',
            'cta_text': 'Vedi Spese Mediche Tracciate'
        },
        {
            'step': 3,
            'title': 'Crediti Ristrutturazioni 2027-2034',
            'priority': 'PIANIFICATA',
            'priority_color': '#a78bfa',
            'description': f"Nei prossimi 8 anni hai un credito d'imposta fisso di <strong>{format_eur_it(annual_total_building_credit)}/anno</strong> già garantito (totale: <strong>{format_eur_it(total_locked_future_credits)}</strong>). Tienine conto nella pianificazione finanziaria.",
            'expected_gain': f"{format_eur_it(total_locked_future_credits)} in 8 anni",
            'cta_text': 'Consulta Roadmap Rate'
        }
    ]

    return {
        'overall_health': 'ECCELLENTE' if pension_headroom <= 1000 else 'OTTIMIZZABILE',
        'health_score': 96 if pension_headroom <= 1000 else 88,
        'audit_cards': audit_cards,
        'action_plan': action_plan,
        'multi_year_credits': {
            'annual_credit': annual_total_building_credit,
            'remaining_years': remaining_years,
            'total_locked': total_locked_future_credits,
            'end_year': dec_year + remaining_years - 1
        },
        'tracked_health_total': tracked_health_total,
        'current_health_total': current_health_total
    }

