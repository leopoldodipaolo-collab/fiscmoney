# services/assistant_engine.py
"""
Intelligent Virtual Assistant Persona Engine for FiscMoney.
Generates tailored, persona-specific briefings, checks, and recommendations.
"""

ASSISTANT_PERSONAS = {
    'demetrio': {
        'id': 'demetrio',
        'name': 'Demetrio',
        'title': 'Il Consulente Smart & Diretto',
        'avatar': '🚀',
        'image': '/static/images/avatars/demetrio.jpg',
        'role_desc': 'Pragmatico e focalizzato sui numeri. Ti dice subito come stanno le cose e dove ottimizzare patrimonio e tasse.',
        'badge_color': '#38bdf8',
        'badge_bg': 'rgba(56, 189, 248, 0.15)',
        'border_color': 'rgba(56, 189, 248, 0.4)'
    },
    'anna': {
        'id': 'anna',
        'name': 'Anna',
        'title': 'L\'Amica Precisa & Rassicurante',
        'avatar': '🌸',
        'image': '/static/images/avatars/anna.jpg',
        'role_desc': 'Accogliente e protettiva. Ti fa sentire al sicuro spiegandoti ogni voce con delicatezza e semplicità.',
        'badge_color': '#f472b6',
        'badge_bg': 'rgba(244, 114, 182, 0.15)',
        'border_color': 'rgba(244, 114, 182, 0.4)'
    },
    'july': {
        'id': 'july',
        'name': 'July',
        'title': 'La Coach Finanziaria Dinamica',
        'avatar': '⚡',
        'image': '/static/images/avatars/july.jpg',
        'role_desc': 'Energica e motivante. Guarda avanti su crescita del patrimonio, fondo pensione e traguardi di risparmio.',
        'badge_color': '#fbbf24',
        'badge_bg': 'rgba(251, 191, 36, 0.15)',
        'border_color': 'rgba(251, 191, 36, 0.4)'
    },
    'commercialista': {
        'id': 'commercialista',
        'name': 'Dott. Fiscale',
        'title': 'Il Commercialista Istituzionale',
        'avatar': '🏛️',
        'image': '/static/images/avatars/dott_fiscale.jpg',
        'role_desc': 'Formale, rigoroso e puntiglioso. Certifica la regolarità delle trattenute e la quadratura contabile.',
        'badge_color': '#a78bfa',
        'badge_bg': 'rgba(167, 139, 250, 0.15)',
        'border_color': 'rgba(167, 139, 250, 0.4)'
    }
}

def get_persona(persona_key='demetrio'):
    if persona_key in ('leo', 'demetrio'):
        return ASSISTANT_PERSONAS['demetrio']
    if persona_key in ('dott_fiscale', 'commercialista'):
        return ASSISTANT_PERSONAS['commercialista']
    return ASSISTANT_PERSONAS.get(persona_key, ASSISTANT_PERSONAS['demetrio'])

def format_eur_it(val):
    if val is None or val == '':
        return '<span class="privacy-mask" title="Passa sopra per sbirciare">0,00 €</span>'
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return f'<span class="privacy-mask" title="Passa sopra per sbirciare">{val} €</span>'
    abs_val = abs(fval)
    formatted = f"{abs_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    res = f"-{formatted} €" if fval < 0 else f"{formatted} €"
    return f'<span class="privacy-mask" title="Passa sopra per sbirciare">{res}</span>'

def generate_paystub_assistant_briefing(paystub, profile_name="Utente", persona_key='leo', matched_tx=None, diff_info=None, anomalies=None, bank_coverage=None):
    """
    Synthesizes a human-like, contextual briefing based on the selected virtual assistant persona.
    """
    persona = get_persona(persona_key)
    p_id = persona['id']
    
    anomalies = anomalies or []
    has_anomalies = len(anomalies) > 0
    
    net_amt = float(paystub.get('net_amount', 0.0))
    gross_amt = float(paystub.get('gross_amount', 0.0))
    inps_tax = float(paystub.get('inps_tax', 0.0))
    irpef_net = float(paystub.get('irpef_net') or paystub.get('irpef_tax') or 0.0)
    
    fund_name = paystub.get('pension_fund_name') or paystub.get('tfr_fund_type') or 'Azienda'
    fund_dip = float(paystub.get('pension_fund_contrib_employee') or 0.0)
    fund_dtr = float(paystub.get('pension_fund_contrib_company') or 0.0)
    fund_tot = float(paystub.get('pension_fund_total') or paystub.get('tfr_accumulated_total') or 0.0)
    
    ferie_ore = float(paystub.get('ferie_residue_ore') or 0.0)
    rol_ore = float(paystub.get('rol_residui_ore') or 0.0)
    
    ticket_count = float(paystub.get('ticket_count') or 0.0)
    ticket_total_val = float(paystub.get('ticket_total_value') or (ticket_count * 8.0))
    
    # Month Name
    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
                   "Tredicesima", "Quattordicesima", "Premio di Risultato"]
    m_idx = paystub.get('month', 1)
    m_name = month_names[m_idx] if 1 <= m_idx < len(month_names) else f"Mese {m_idx}"
    y_val = paystub.get('year', 2026)

    # Bank coverage status
    cov_status = bank_coverage.get('coverage_status') if bank_coverage else 'UNKNOWN'
    max_date_it = bank_coverage.get('max_date_it', '') if bank_coverage else ''

    # Status indicator
    is_matched = bool(matched_tx)
    if has_anomalies and any(a.get('severity') in ['CRITICAL', 'HIGH'] for a in anomalies):
        crit_count = sum(1 for a in anomalies if a.get('severity') in ['CRITICAL', 'HIGH'])
        status_tag = f"🚨 {crit_count} Anomali{'a' if crit_count == 1 else 'e'} da Risolvere"
    elif is_matched:
        status_tag = "Verificato & In Regola 100% ✅"
    elif cov_status == 'NOT_IMPORTED':
        status_tag = "Estratto Conto Non Presente ⏳"
    elif bank_coverage and bank_coverage.get('is_partial'):
        status_tag = f"Estratto Conto Parziale ({max_date_it}) ⏳"
    else:
        status_tag = "In Attesa di Riconciliazione ⚠️"

    bullets = []

    if p_id in ('leo', 'demetrio'):
        # DEMETRIO / LEO: Diretto, pragmatico, focus risparmio e numeri
        if has_anomalies:
            headline = f"Attenzione {profile_name}! Ho scovato un'anomalia nel cedolino di {m_name}."
            p1 = f"Ciao <strong>{profile_name}</strong>! C'è una cosa importante che non torna: <strong>{anomalies[0]['title']}</strong>. {anomalies[0]['what']}"
            p2 = f"⚠️ <strong>Impatto:</strong> {anomalies[0]['impact']} In fondo alla pagina ho preparato per te il <strong>modulo precompilato da inviare all'ufficio HR</strong> per chiedere il rimborso o la correzione."
        else:
            headline = f"Tutto in ordine su questo cedolino di {m_name}!" if is_matched else f"Cedolino di {m_name} registrato: verifichiamo l'accredito."
            p1 = f"Ciao <strong>{profile_name}</strong>! Ho esaminato la busta paga di <strong>{m_name} {y_val}</strong>: il netto finale è di <strong>{format_eur_it(net_amt)}</strong>."
            if is_matched:
                p1 += f" L'accredito su <strong>{matched_tx.get('account_name', 'conto')}</strong> è arrivato puntuale il {matched_tx.get('date')} e quadra <strong>al centesimo</strong>."
            elif cov_status == 'NOT_IMPORTED':
                p1 += f" Per {m_name} non risultano ancora estratti conto bancari caricati: quando importerai i movimenti collegheremo l'accredito in automatico."
            elif bank_coverage and bank_coverage.get('is_partial'):
                p1 += f" I movimenti bancari registrati per {m_name} arrivano fino al {max_date_it}: i bonifici di fine mese non sono ancora inclusi nell'import."
            else:
                p1 += f" Non ho ancora trovato il bonifico bancario abbinato nell'estratto conto: quando importi i movimenti lo collegheremo in automatico."

            p2 = f"Le trattenute fiscali (INPS {format_eur_it(inps_tax)} e IRPEF {format_eur_it(irpef_net)}) sono coerenti con la tua aliquota."
            if fund_dip > 0 and fund_name != 'Azienda':
                p2 += f" Ottima mossa la previdenza integrativa su <strong>{fund_name}</strong>: questo mese l'azienda ti ha versato <strong>+{format_eur_it(fund_dtr)} gratis</strong> a suo carico, portando la tua posizione a <strong>{format_eur_it(fund_tot)}</strong>."
            if ticket_count > 0:
                p2 += f" In più hai maturato <strong>{int(ticket_count)} buoni pasto elettronici</strong> per un valore netto di <strong>{format_eur_it(ticket_total_val)}</strong> 100% esentasse per la spesa alimentare!"

        bullets = [
            f"💰 <strong>Netto in tasca:</strong> {format_eur_it(net_amt)} (Lordo {format_eur_it(gross_amt)})",
            f"🎁 <strong>Beneficio Fondo:</strong> {'+'+format_eur_it(fund_dtr) if fund_dtr > 0 else 'Verifica anomalia'}",
            f"🏖️ <strong>Tesoretto Permessi:</strong> {ferie_ore + rol_ore:.1f} ore residue pronte all'uso"
        ]
        if ticket_count > 0:
            bullets.append(f"🥪 <strong>Buoni Pasto:</strong> {int(ticket_count)} ticket ({format_eur_it(ticket_total_val)} spesa netta)")

    elif p_id == 'anna':
        # ANNA: Rassicurante, empatica, chiara
        if has_anomalies:
            headline = f"{profile_name}, ti proteggo io: c'è un dettaglio da chiarire con l'azienda."
            p1 = f"Caro <strong>{profile_name}</strong>, controllando il tuo cedolino ho notato una discrepanza: <strong>{anomalies[0]['title']}</strong>."
            p2 = f"Non preoccuparti: capita spesso per sviste del software paghe. {anomalies[0]['impact']} Ho già preparato per te un messaggio gentile da inoltrare alle Risorse Umane."
        else:
            headline = f"Tranquillo {profile_name}, lo stipendio di {m_name} è al sicuro!"
            p1 = f"Carissimo <strong>{profile_name}</strong>, buone notizie! Ho controllato con cura tutti i dettagli del tuo stipendio di <strong>{m_name}</strong>."
            if is_matched:
                p1 += f" Il tuo bonifico di <strong>{format_eur_it(net_amt)}</strong> è già stato depositato in banca in totale sicurezza."
            elif cov_status == 'NOT_IMPORTED':
                p1 += f" Il netto calcolato è di <strong>{format_eur_it(net_amt)}</strong>. Appena importerai l'estratto conto della banca verificherò la ricezione."
            elif bank_coverage and bank_coverage.get('is_partial'):
                p1 += f" Il netto è di <strong>{format_eur_it(net_amt)}</strong>. I movimenti caricati si fermano al {max_date_it}, perciò attendo l'import di fine mese."
            else:
                p1 += f" Il netto calcolato è di <strong>{format_eur_it(net_amt)}</strong>. Appena arriverà il bonifico ti avviserò."

            p2 = f"Tutte le imposte sono state conteggiate correttamente secondo le regole di legge, senza brutte sorprese."
            if fund_name != 'Azienda':
                p2 += f" È rassicurante vedere che il tuo futuro su <strong>{fund_name}</strong> è protetto e continua a crescere mese dopo mese."
            if ticket_count > 0:
                p2 += f" Ricordati anche dei tuoi <strong>{int(ticket_count)} buoni pasto</strong> ({format_eur_it(ticket_total_val)}) per fare la spesa in serenità!"

        bullets = [
            f"🛡️ <strong>Stato:</strong> {'Da verificare con HR' if has_anomalies else 'Nessuna anomalia'}",
            f"🌱 <strong>Fondo Pensione:</strong> {format_eur_it(fund_tot)} totali",
            f"☕ <strong>Riposo maturato:</strong> {ferie_ore:.1f} ore di ferie"
        ]
        if ticket_count > 0:
            bullets.append(f"🥪 <strong>Buoni Pasto:</strong> {int(ticket_count)} ticket ({format_eur_it(ticket_total_val)})")

    elif p_id == 'july':
        # JULY: Coach dinamica, obiettivi, net worth, energia
        if has_anomalies:
            headline = f"Alt {profile_name}! Un'anomalia sta frenando il tuo capitale 🛑"
            p1 = f"Ciao <strong>{profile_name}</strong>! Dobbiamo intervenire subito: <strong>{anomalies[0]['title']}</strong>."
            p2 = f"Non regalare soldi a nessuno: {anomalies[0]['impact']} Fai valere i tuoi diritti contrattuali usando la richiesta formale pronta qui sotto!"
        else:
            headline = f"Ottimo colpo! Patrimonio in crescita a {m_name} {y_val} 🚀"
            p1 = f"Ciao <strong>{profile_name}</strong>! Mese molto positivo per le tue finanze personali con un incasso netto di <strong>{format_eur_it(net_amt)}</strong>."
            if diff_info and diff_info.get('has_prev') and diff_info.get('net_diff', 0) > 0:
                p1 += f" Hai guadagnato <strong>+{format_eur_it(diff_info['net_diff'])} in più</strong> rispetto al mese scorso!"

            p2 = f"Guarda il quadro d'insieme: tra TFR e previdenza integrativa <strong>{fund_name}</strong> il tuo montante è salito a <strong>{format_eur_it(fund_tot)}</strong>. Inoltre hai <strong>{ferie_ore + rol_ore:.1f} ore</strong> di riposo retribuito, pari a oltre {format_eur_it((ferie_ore + rol_ore) * (net_amt / 168.0))}!"
            if ticket_count > 0:
                p2 += f" Potere d'acquisto extra: <strong>+{format_eur_it(ticket_total_val)}</strong> in buoni pasto elettronici senza 1 centesimo di tasse!"

        bullets = [
            f"📈 <strong>Flusso netto:</strong> {format_eur_it(net_amt)}",
            f"💎 <strong>Capitale Fondo:</strong> {format_eur_it(fund_tot)} su {fund_name}",
            f"⚡ <strong>Azione immediata:</strong> {'Invia richiesta HR' if has_anomalies else 'Traguardo raggiunto'}"
        ]
        if ticket_count > 0:
            bullets.append(f"🥪 <strong>Welfare Spesa:</strong> +{format_eur_it(ticket_total_val)} ({int(ticket_count)} ticket)")

    else:
        # COMMERCIALISTA: Formale, conformità, rigoroso
        if has_anomalies:
            headline = f"Notifica di difformità contabile/contrattuale - Mensilità {m_name} {y_val}"
            p1 = f"Gentile <strong>{profile_name}</strong>, si rileva una non conformità nel prospetto paga: <strong>{anomalies[0]['title']}</strong>. {anomalies[0]['what']}"
            p2 = f"Si attesta un pregiudizio economico stimato: {anomalies[0]['impact']} Si raccomanda formale istanza di regolarizzazione mediante l'atto predisposto in calce."
        else:
            headline = f"Attestazione di regolarità contabile - Mensilità di {m_name} {y_val}"
            p1 = f"Gentile <strong>{profile_name}</strong>, si certifica la conformità del prospetto paga relativo al periodo di competenza <strong>{m_name} {y_val}</strong>."
            if is_matched:
                p1 += f" Si riscontra perfetta corrispondenza tra l'emolumento netto liquidato pari a <strong>{format_eur_it(net_amt)}</strong> e l'accredito bancario avvenuto in data {matched_tx.get('date')}."
            elif cov_status == 'NOT_IMPORTED':
                p1 += f" Si attesta la congruità del prospetto paga con netto liquidabile di <strong>{format_eur_it(net_amt)}</strong>. Risulta pendente l'acquisizione degli estratti conto del periodo."
            elif bank_coverage and bank_coverage.get('is_partial'):
                p1 += f" Si certifica il netto di <strong>{format_eur_it(net_amt)}</strong>. L'acquisizione contabile dei movimenti bancari risulta parziale (fino al {max_date_it})."
            else:
                p1 += f" Si notifica che l'accredito bancario dell'importo netto di <strong>{format_eur_it(net_amt)}</strong> risulta al momento pendente di abbinamento contabile."

            p2 = f"Le ritenute previdenziali IVS e le imposte progressive IRPEF risultano calcolate secondo le vigenti aliquote di scaglione. Accantonamento TFR conforme alle disposizioni del CCNL."
            if ticket_count > 0:
                p2 += f" Si attesta l'erogazione di n. {int(ticket_count)} buoni pasto per un controvalore di {format_eur_it(ticket_total_val)} in regime di totale esenzione fiscale ai sensi dell'Art. 51 comma 2 lett. c) del TUIR."

        bullets = [
            f"📋 <strong>Imponibile Lordo:</strong> {format_eur_it(gross_amt)}",
            f"🏛️ <strong>Totale Fisco & INPS:</strong> {format_eur_it(inps_tax + irpef_net)}",
            f"⚖️ <strong>Audit Conformità:</strong> {'NON CONFORME 🚨' if has_anomalies else 'REGOLARE ✅'}"
        ]
        if ticket_count > 0:
            bullets.append(f"🥪 <strong>Welfare Esente (Art.51 TUIR):</strong> {format_eur_it(ticket_total_val)} ({int(ticket_count)} vch)")

    return {
        'persona': persona,
        'headline': headline,
        'status_tag': status_tag,
        'has_anomalies': has_anomalies,
        'anomalies_count': len(anomalies),
        'is_matched': is_matched,
        'p1': p1,
        'p2': p2,
        'bullets': bullets
    }


def generate_dashboard_assistant_briefing(persona_key='leo', profile_name="Utente", cashflow=None, latest_paystub=None, latest_730=None, total_balance=0.0):
    """
    Generates a personalized executive dashboard briefing in the active assistant persona's voice.
    Synthesizes cashflow safe-to-spend, latest salary & tickets, 730 tax status, and upcoming optimizations.
    """
    persona = get_persona(persona_key)
    p_id = persona['id']

    safe_spend = float(cashflow.get('monthly_safe_to_spend') or 0.0) if cashflow else 0.0
    daily_budget = float(cashflow.get('daily_safe_budget') or 0.0) if cashflow else 0.0
    days_rem = cashflow.get('days_remaining', 20) if cashflow else 20
    
    ps_net = float(latest_paystub.get('net_amount') or 0.0) if latest_paystub else 0.0
    ps_month = latest_paystub.get('month_name', '') if latest_paystub else ''
    ps_year = latest_paystub.get('year', '') if latest_paystub else ''
    ticket_count = float(latest_paystub.get('ticket_count') or 0.0) if latest_paystub else 0.0
    ticket_val = float(latest_paystub.get('ticket_total_value') or 0.0) if latest_paystub else 0.0

    has_730 = latest_730 is not None
    tax_refund = float(latest_730.get('final_refund_or_debit') or 0.0) if has_730 else 0.0
    is_refund = latest_730.get('is_refund', True) if has_730 else True
    dec_year = latest_730.get('declaration_year', 2026) if has_730 else 2026
    pension_headroom = float(latest_730.get('pension_headroom') or 0.0) if has_730 else 2472.57
    potential_savings = float(latest_730.get('potential_pension_tax_savings') or 0.0) if has_730 else 1063.21

    cards = []

    is_empty_state = (total_balance == 0.0 and safe_spend == 0.0 and not latest_paystub and not latest_730)

    if p_id in ('leo', 'demetrio'):
        # DEMETRIO / LEO: Smart, Diretto, Focalizzato sui soldi
        if is_empty_state:
            headline = f"Benvenuto su FiscMoney, {profile_name}! 🚀 Cominciamo insieme!"
            overview = "Sono <strong>Demetrio</strong>, il tuo assistente finanziario smart. Il mio compito è farti capire subito dove vanno i tuoi soldi, quanto puoi spendere a cuor leggero ogni mese e come risparmiare senza rinunce."
            cards.append({
                'icon': '📄',
                'title': '1. Carica Estratto Conto',
                'value': 'Pronto',
                'sub': 'Trascina PDF o Excel della banca in 5 sec',
                'color': '#38bdf8'
            })
            cards.append({
                'icon': '🎯',
                'title': '2. Profilo Intelligente',
                'value': '60 Secondi',
                'sub': 'Insegnami se hai mutuo, casa, figli o auto',
                'color': '#10b981'
            })
            cards.append({
                'icon': '✨',
                'title': '3. Safe-to-Spend & 730',
                'value': 'Automatico',
                'sub': 'Scopri subito quanto spendere e recuperare',
                'color': '#fbbf24'
            })
            recommendation = "💡 <strong>Come partire subito:</strong> Carica il tuo primo estratto conto bancario cliccando sul pulsante in alto oppure personalizza le tue abitudini con un tocco!"
        else:
            headline = f"Ciao {profile_name}! Ecco la sintesi finanziaria e fiscale di oggi 🚀"
            overview = f"Situazione generale solida con <strong>{format_eur_it(total_balance)}</strong> di liquidità totale. Questo mese hai <strong>{format_eur_it(safe_spend)}</strong> di Safe-to-Spend libero (~{format_eur_it(daily_budget)}/giorno per {days_rem} giorni)."
            
            if has_730 and is_refund and tax_refund > 0:
                overview += f" Il tuo Modello 730/{dec_year} ha generato un <strong>rimborso di {format_eur_it(tax_refund)}</strong> regolarmente incassato."
            
            cards.append({
                'icon': '🎯',
                'title': 'Safe-to-Spend Libero',
                'value': format_eur_it(safe_spend),
                'sub': f"~{format_eur_it(daily_budget)} / giorno ({days_rem} gg rimasti)",
                'color': '#10b981'
            })
            if latest_paystub:
                cards.append({
                    'icon': '💼',
                    'title': f"Ultimo Stipendio ({ps_month})",
                    'value': format_eur_it(ps_net),
                    'sub': f"+{format_eur_it(ticket_val)} in {int(ticket_count)} buoni pasto esenti" if ticket_count > 0 else "Cedolino regolare",
                    'color': '#38bdf8'
                })
            if has_730:
                cards.append({
                    'icon': '🏛️',
                    'title': f"Fisco 730/{dec_year}",
                    'value': f"+{format_eur_it(tax_refund)}" if is_refund else f"-{format_eur_it(tax_refund)}",
                    'sub': "Riconciliato con successo in busta paga",
                    'color': '#34d399'
                })
            if pension_headroom > 50:
                recommendation = f"💡 <strong>Opportunità Fiscale:</strong> Ti rimangono <strong>{format_eur_it(pension_headroom)}</strong> di capienza deducibile sul Fondo Pensione. Versandoli prima del 31/12 recuperi altri <strong>+{format_eur_it(potential_savings)}</strong> di IRPEF!"
            else:
                recommendation = "💡 <strong>Ottima Gestione:</strong> Hai massimizzato le deduzioni fiscali. Continua a monitorare le spese variabili per restare nel budget Safe-to-Spend."

    elif p_id == 'anna':
        # ANNA: Rassicurante, Precisa, Protettiva
        if is_empty_state:
            headline = f"Benvenuto su FiscMoney, {profile_name}! 🌸 Ti aiuto io a fare ordine"
            overview = "Sono <strong>Anna</strong>, la tua assistente per la serenità finanziaria. Nessun termine difficile o ansia da bilancio: ti guiderò passo dopo passo per avere spese, casa e famiglia sempre al sicuro."
            cards.append({
                'icon': '📄',
                'title': '1. Il tuo Estratto Conto',
                'value': 'Semplice',
                'sub': 'Carica il file della tua banca con un click',
                'color': '#f472b6'
            })
            cards.append({
                'icon': '🌸',
                'title': '2. Le tue Abitudini',
                'value': 'Guidato',
                'sub': 'Spiegami le tue spese quotidiane in 1 minuto',
                'color': '#38bdf8'
            })
            cards.append({
                'icon': '🛡️',
                'title': '3. Spese Protette',
                'value': 'Zero Ansia',
                'sub': 'Saprai sempre cosa puoi spendere ogni mese',
                'color': '#10b981'
            })
            recommendation = "🌸 <strong>Consiglio per te:</strong> Inizia caricando un estratto conto recente: riconoscerò bollette, mutuo e spese di tutti i giorni per te."
        else:
            headline = f"Bentornato {profile_name}, tutto è sotto controllo e in perfetto ordine 🌸"
            overview = f"I tuoi conti sono protetti con <strong>{format_eur_it(total_balance)}</strong> di patrimonio liquido disponibile. Puoi spendere con serenità fino a <strong>{format_eur_it(safe_spend)}</strong> per le tue necessità questo mese."
            
            if has_730:
                overview += f" La tua posizione fiscale per il 730/{dec_year} è completamente allineata e verificata."

            cards.append({
                'icon': '🌸',
                'title': 'Tranquillità Spesa Mese',
                'value': format_eur_it(safe_spend),
                'sub': f"Spese fisse e bollette già coperte",
                'color': '#f472b6'
            })
            if latest_paystub:
                cards.append({
                    'icon': '🥪',
                    'title': 'Welfare & Spesa',
                    'value': format_eur_it(ticket_val),
                    'sub': f"{int(ticket_count)} buoni pasto da spendere per la famiglia",
                    'color': '#38bdf8'
                })
            if has_730:
                cards.append({
                    'icon': '🏛️',
                    'title': 'Dichiarazione 730',
                    'value': f"Conforme (+{format_eur_it(tax_refund)})" if is_refund else "Regolare",
                    'sub': "Nessun contenzioso con l'Agenzia Entrate",
                    'color': '#10b981'
                })
            recommendation = "🌸 <strong>Consiglio per te:</strong> Ricordati di conservare scontrini parlanti e ricevute mediche tracciate: quest'anno le stiamo raccogliendo per farti avere il massimo rimborso possibile."

    elif p_id == 'july':
        # JULY: Dinamica, Coach, Obiettivi & Patrimonio
        if is_empty_state:
            headline = f"Benvenuto su FiscMoney, {profile_name}! ⚡ Raggiungiamo i tuoi traguardi!"
            overview = "Sono <strong>July</strong>, la tua financial coach. Insieme daremo una spinta al tuo risparmio, ottimizzando ogni mese il tuo budget libero per i tuoi progetti di vita!"
            cards.append({
                'icon': '📄',
                'title': '1. Connetti i Conti',
                'value': 'Subito',
                'sub': 'Importa le tue transazioni in 5 secondi',
                'color': '#fbbf24'
            })
            cards.append({
                'icon': '⚡',
                'title': '2. Target & Regole',
                'value': 'Smart',
                'sub': 'Definisci le tue categorie in 60s',
                'color': '#38bdf8'
            })
            cards.append({
                'icon': '🚀',
                'title': '3. Crescita',
                'value': 'Attiva',
                'sub': 'Massimizza il margine di risparmio mensile',
                'color': '#10b981'
            })
            recommendation = "⚡ <strong>Primi passi:</strong> Carica il tuo primo estratto conto e iniziamo a costruire il tuo piano di crescita economica!"
        else:
            headline = f"Pronto a far crescere il tuo patrimonio, {profile_name}? ⚡"
            overview = f"Hai <strong>{format_eur_it(total_balance)}</strong> di liquidità attiva e <strong>{format_eur_it(safe_spend)}</strong> di margine libero. Mantenendo questo passo creiamo un flusso di risparmio costante per i tuoi traguardi!"

            cards.append({
                'icon': '⚡',
                'title': 'Capitale Libero Mese',
                'value': format_eur_it(safe_spend),
                'sub': f"Potenziale risparmio: ~{format_eur_it(safe_spend * 0.3)}",
                'color': '#fbbf24'
            })
            if latest_paystub:
                cards.append({
                    'icon': '📈',
                    'title': f"Entrata Netta ({ps_month})",
                    'value': format_eur_it(ps_net),
                    'sub': "Flusso di cassa consolidato",
                    'color': '#38bdf8'
                })
            if has_730 and pension_headroom > 50:
                cards.append({
                    'icon': '🚀',
                    'title': 'Boost Fiscale Fondo Pensione',
                    'value': f"+{format_eur_it(potential_savings)}",
                    'sub': f"Sfruttando i {format_eur_it(pension_headroom)} residui",
                    'color': '#a78bfa'
                })
            recommendation = f"⚡ <strong>Azione Strategica:</strong> Reinvesti parte del rimborso 730 nel Fondo Pensione prima del 31/12 per attivare l'effetto moltiplicatore e incassare altri <strong>+{format_eur_it(potential_savings)}</strong>!"

    else:
        # COMMERCIALISTA / DOTT. FISCALE: Formale, Rigoroso, Istituzionale
        if is_empty_state:
            headline = f"Benvenuto su FiscMoney - Apertura Fascicolo Contabile di {profile_name} 🏛️"
            overview = "Sono il <strong>Dott. Fiscale</strong>. Monitorerò la regolarità dei tuoi flussi bancari, la quadratura delle detrazioni IRPEF 730 e la tracciabilità delle spese deducibili."
            cards.append({
                'icon': '📄',
                'title': '1. Importazione Estratti',
                'value': 'In Attesa',
                'sub': 'Tracciamento contabile movimenti',
                'color': '#a78bfa'
            })
            cards.append({
                'icon': '🏛️',
                'title': '2. Profilazione Fiscale',
                'value': '60 sec',
                'sub': 'Configurazione detrazioni e familiari',
                'color': '#38bdf8'
            })
            cards.append({
                'icon': '⚖️',
                'title': '3. Certificazione 730',
                'value': 'Automatico',
                'sub': 'Stima rimborso e deduzioni TUIR',
                'color': '#10b981'
            })
            recommendation = "🏛️ <strong>Istruzioni:</strong> Procedere con l'acquisizione del primo estratto conto bancario o cedolino per inizializzare i mastri contabili."
        else:
            headline = f"Report di Sintesi Fiscale e Contabile - Posizione di {profile_name} 🏛️"
            overview = f"Si attesta la disponibilità di saldi liquidi complessivi pari a <strong>{format_eur_it(total_balance)}</strong>, con capienza di spesa corrente pari a <strong>{format_eur_it(safe_spend)}</strong> al netto dei costi fissi programmati."

            cards.append({
                'icon': '📊',
                'title': 'Liquidità Verificata',
                'value': format_eur_it(total_balance),
                'sub': 'Saldi bancari riconciliati',
                'color': '#a78bfa'
            })
            if latest_paystub:
                cards.append({
                    'icon': '📋',
                    'title': f"Retribuzione Netta ({ps_month})",
                    'value': format_eur_it(ps_net),
                    'sub': f"Welfare esente art. 51 TUIR: {format_eur_it(ticket_val)}",
                    'color': '#38bdf8'
                })
            if has_730:
                cards.append({
                    'icon': '⚖️',
                    'title': f"Liquidazione 730/{dec_year}",
                    'value': f"+{format_eur_it(tax_refund)}" if is_refund else f"-{format_eur_it(tax_refund)}",
                    'sub': 'Conguaglio a credito regolarmente eseguito',
                    'color': '#10b981'
                })
            recommendation = f"🏛️ <strong>Avviso di Conformità:</strong> Si certifica capienza deducibile residua ex art. 10 TUIR per {format_eur_it(pension_headroom)}. Il versamento entro l'esercizio fiscale in corso genera un credito IRPEF di {format_eur_it(potential_savings)}."

    return {
        'persona_id': persona['id'],
        'persona_name': persona['name'],
        'persona_avatar': persona['avatar'],
        'persona_role': persona['title'],
        'avatar': persona['avatar'],
        'name': persona['name'],
        'role_badge': persona['title'],
        'headline': headline,
        'overview': overview,
        'cards': cards,
        'recommendation': recommendation
    }

