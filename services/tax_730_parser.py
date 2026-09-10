# services/tax_730_parser.py
"""
Intelligent, Universal & Bulletproof Parser for Italian Modello 730 Tax Returns (Agenzia delle Entrate).

Supported Formats & Years:
- Modello 730/2020 through 730/2026+ (all official Agenzia delle Entrate templates)
- Dichiarazione Singola (Dichiarante)
- Dichiarazione Congiunta (Dichiarante + Coniuge)
- Modello 730 Senza Sostituto (Rimborsi diretti AdE o Versamenti F24)
- Modello 730 Integrativo e Rettificativo

Extracted Sections:
1. Frontespizio: Anno Fiscale, Anno Dichiarazione, Codice Fiscale, Nome/Cognome, Tipologia Dichiarazione
2. Quadro C: Redditi Dipendente & Ritenute IRPEF/Addizionali
3. Quadro E: Oneri e Spese (E1 Spese Mediche, E7 Mutuo Casa, E27 Previdenza Complementare, E41 Ristrutturazioni 50%, E57 Bonus Mobili, E61 Ecobonus 65%, E8-E10 Altre Spese)
4. Modello 730-3: Prospetto di Liquidazione (Righi 11, 14, 16, 25, 48, 50, 59, 60, 71, 72, 75, 78)
5. Risultato Liquidazione: Rimborso Busta Paga (Rigo 163), Trattenuta Busta Paga (Rigo 161), Rimborso AdE (Rigo 164), Versamento F24 (Rigo 162), o Pareggio.
"""

import io
import re

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pypdf
except ImportError:
    pypdf = None


def clean_amount(val):
    """Converts Italian formatted currency strings (e.g. '1.600,00' or '-1.587,00') to float."""
    if val is None or val == '':
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace('€', '').replace(' ', '').strip()
    if not s or s in [',00', '.00', '-', '']:
        return 0.0
    is_neg = s.startswith('-') or s.endswith('-')
    s = s.replace('-', '').strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        f = float(s)
        return -f if is_neg else f
    except (ValueError, TypeError):
        return 0.0


def extract_text_and_pages(file_stream_or_path):
    """Extracts raw text and page-by-page text from a 730 PDF file."""
    full_text = ""
    pages_text = []

    if isinstance(file_stream_or_path, bytes):
        stream = io.BytesIO(file_stream_or_path)
    else:
        stream = file_stream_or_path

    if pdfplumber:
        try:
            if hasattr(stream, 'seek'):
                stream.seek(0)
            with pdfplumber.open(stream) as pdf:
                for i, page in enumerate(pdf.pages):
                    t = page.extract_text() or ""
                    pages_text.append(t)
                    full_text += f"\n--- PAGE {i+1} ---\n" + t
            if full_text.strip():
                return full_text, pages_text
        except Exception as e:
            print(f"pdfplumber 730 extraction fallback: {e}")

    if pypdf:
        try:
            if hasattr(stream, 'seek'):
                stream.seek(0)
            reader = pypdf.PdfReader(stream)
            for i, page in enumerate(reader.pages):
                t = page.extract_text() or ""
                pages_text.append(t)
                full_text += f"\n--- PAGE {i+1} ---\n" + t
        except Exception as e:
            print(f"pypdf 730 extraction error: {e}")

    return full_text, pages_text


def parse_tax_730_pdf(file_stream_or_path):
    """
    Comprehensive parsing of Italian Modello 730 tax declaration.
    Returns structured data dictionary.
    """
    full_text, pages_text = extract_text_and_pages(file_stream_or_path)
    if not full_text:
        return {
            'success': False,
            'error': "Impossibile estrarre dati dal file PDF Modello 730."
        }

    raw_lower = full_text.lower()

    # -------------------------------------------------------------
    # 1. Detect Years (Declaration Year & Tax Year)
    # -------------------------------------------------------------
    dec_year = None
    tax_year = None

    m_head = re.search(r'modello\s+730[/]?(\d{4})', raw_lower)
    m_redd = re.search(r'redditi\s+(\d{4})', raw_lower)

    if m_head:
        dec_year = int(m_head.group(1))
    if m_redd:
        tax_year = int(m_redd.group(1))

    if dec_year and not tax_year:
        tax_year = dec_year - 1
    elif tax_year and not dec_year:
        dec_year = tax_year + 1
    elif not dec_year and not tax_year:
        dec_year = 2026
        tax_year = 2025

    # -------------------------------------------------------------
    # 2. Frontespizio: Taxpayer Info & Declaration Type
    # -------------------------------------------------------------
    fiscal_code = None
    p1_text = pages_text[0] if pages_text else full_text

    m_cf = re.search(r'([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])', full_text)
    if m_cf:
        fiscal_code = m_cf.group(1).upper()

    taxpayer_name = "Contribuente"
    m_name = re.search(r'CONTRIBUENTE\s+([A-Z\s]{4,40}?)(?:\s+M|\s+F|\s+DATA|\s+COMUNE|\s+AQ|\s+RM|\s+MI)', p1_text)
    if m_name:
        taxpayer_name = m_name.group(1).strip()
    else:
        m_name_fallback = re.search(r'dichiarante\s+([A-Z\s]+?)(?:coniuge|riepilogo|$)', full_text, re.MULTILINE)
        if m_name_fallback and len(m_name_fallback.group(1).strip()) > 3:
            taxpayer_name = m_name_fallback.group(1).strip()

    is_joint = bool(re.search(r'DICHIARAZIONE\s+CONGIUNTA\s+X|CONGIUNTA\s+X', p1_text, re.I))
    is_no_employer = bool(re.search(r'730\s+senza\s+sostituto\s+X|senza\s+sostituto\s+X', p1_text, re.I))
    declaration_type = "CONGIUNTA" if is_joint else ("SENZA SOSTITUTO" if is_no_employer else "ORDINARIO")

    # -------------------------------------------------------------
    # 3. Line Normalization & Merging
    # -------------------------------------------------------------
    all_lines = []
    for page_text in pages_text:
        lines = page_text.split('\n')
        merged = []
        for l in lines:
            s = l.strip()
            if not s:
                continue
            if (s.startswith(',') or s == ',00') and merged:
                merged[-1] = merged[-1] + s
            else:
                merged.append(s)

        for m in merged:
            cleaned = m
            for _ in range(6):
                cleaned = re.sub(r'(?<=\d|\.|\,)\s+(?=\d|\.|\,)', '', cleaned)
            all_lines.append(cleaned.strip())

    # -------------------------------------------------------------
    # 4. Prospetto di Liquidazione 730-3 Parsing
    # -------------------------------------------------------------
    righi = {}
    for i, l in enumerate(all_lines):
        # Match standard numbered 730-3 liquidation lines
        for num in ['11', '12', '13', '14', '15', '16', '21', '22', '23', '24', '25', '26', '27', '28', 
                    '48', '50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '60',
                    '71', '72', '73', '74', '75', '76', '77', '78', '79', '80', '81', '91', '92', '93']:
            pattern = rf'^\s*{num}\b.*?(?P<amt>-?\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}|-?\d+,\d{{2}})'
            m = re.search(pattern, l, re.IGNORECASE)
            if m and num not in righi:
                righi[num] = clean_amount(m.group('amt'))

        # Rigo 161 (Importo trattenuto dal datore in busta paga)
        if (l.startswith('161 ') or l == '161') and '161' not in righi:
            combined = ' '.join(all_lines[i:i+3])
            clean_combined = re.sub(r'231\s+a\s+245', '', combined)
            amts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', clean_combined)
            non_zero = [clean_amount(a) for a in amts if clean_amount(a) > 0]
            righi['161'] = non_zero[0] if non_zero else 0.0

        # Rigo 162 (Importo da versare con F24)
        if (l.startswith('162 ') or l == '162') and '162' not in righi:
            combined = ' '.join(all_lines[i:i+3])
            clean_combined = re.sub(r'231\s+a\s+245', '', combined)
            amts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', clean_combined)
            non_zero = [clean_amount(a) for a in amts if clean_amount(a) > 0]
            righi['162'] = non_zero[0] if non_zero else 0.0

        # Rigo 163 (Importo rimborsato in busta paga)
        if (l.startswith('163') or l == '163') and '163' not in righi:
            combined = ' '.join(all_lines[i:i+3])
            amts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', combined)
            non_zero = [clean_amount(a) for a in amts if clean_amount(a) > 0]
            righi['163'] = non_zero[0] if non_zero else 0.0

        # Rigo 164 (Importo rimborsato da Agenzia Entrate senza sostituto)
        if (l.startswith('164') or l == '164') and '164' not in righi:
            combined = ' '.join(all_lines[i:i+3])
            amts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', combined)
            non_zero = [clean_amount(a) for a in amts if clean_amount(a) > 0]
            righi['164'] = non_zero[0] if non_zero else 0.0

    total_income = righi.get('11', 0.0)
    principal_residence_deduction = righi.get('12', 0.0)
    taxable_income = righi.get('14', total_income)
    gross_tax = righi.get('16', 0.0)
    employee_tax_credit = righi.get('25', 0.0)
    total_deductions = righi.get('48', 0.0)
    net_tax = righi.get('50', 0.0)
    withholdings_paid = righi.get('59', 0.0)
    tax_difference = righi.get('60', round(net_tax - withholdings_paid, 2))
    regional_tax_due = righi.get('72', 0.0)
    municipal_tax_due = righi.get('75', 0.0)
    municipal_tax_acc = righi.get('78', 0.0)

    # -------------------------------------------------------------
    # 5. Quadro E Breakdown (Targeted Multi-Pass Extraction)
    # -------------------------------------------------------------
    medical_expenses = 0.0
    mortgage_interest = 0.0
    pension_fund_deduction = 0.0
    building_renovations = 0.0
    furniture_expenses = 0.0
    energy_saving_expenses = 0.0
    other_expenses_total = 0.0
    expenses_breakdown = []

    quadro_e_text = ""
    for pt in pages_text:
        if 'QUADRO E' in pt or 'Oneri e spese' in pt:
            quadro_e_text += "\n" + pt

    # E1 Spese sanitarie
    m_san = re.search(r'(?:n\s*e\s*2|SPESE SANITARIE[\w\s]*?)\s*(\d[\d\s]*)\n\s*,00', quadro_e_text)
    if m_san:
        san_clean = m_san.group(1).replace(' ', '').strip()
        if san_clean and san_clean.isdigit():
            medical_expenses = float(san_clean)
            if medical_expenses > 10:
                expenses_breakdown.append({
                    'code': 'E1',
                    'title': 'Spese Sanitarie e Mediche',
                    'amount': medical_expenses,
                    'deductible': max(0.0, round(medical_expenses - 129.11, 2)),
                    'tax_benefit': round(max(0.0, medical_expenses - 129.11) * 0.19, 2),
                    'rule': 'Detrazione IRPEF 19% sulla quota oltre la franchigia di 129,11 €'
                })

    # E7 Mutuo Passivi
    m_mutuo = re.search(r'E7[^\n]*?(\d{1,3}(?:\.\d{3})+|\d{3,4}),\d{2}', quadro_e_text)
    if m_mutuo:
        mortgage_interest = clean_amount(m_mutuo.group(1))
        if mortgage_interest > 0:
            expenses_breakdown.append({
                'code': 'E7',
                'title': 'Interessi Passivi Mutuo Prima Casa',
                'amount': mortgage_interest,
                'deductible': min(4000.0, mortgage_interest),
                'tax_benefit': round(min(4000.0, mortgage_interest) * 0.19, 2),
                'rule': 'Detrazione IRPEF 19% fino a un massimo di 4.000,00 €'
            })

    # E27 Previdenza Complementare (Fondi Pensione)
    m_prev = re.search(r'E27[^\n]*\n\s*([\d\s\.]+),\d{2}', quadro_e_text)
    if m_prev:
        p_str = m_prev.group(1).replace(' ', '').replace('.', '').strip()
        if p_str and p_str.isdigit():
            pension_fund_deduction = float(p_str)
            if pension_fund_deduction > 50:
                expenses_breakdown.append({
                    'code': 'E27',
                    'title': 'Previdenza Complementare (Fondo Pensione)',
                    'amount': pension_fund_deduction,
                    'deductible': min(5164.57, pension_fund_deduction),
                    'tax_benefit': round(min(5164.57, pension_fund_deduction) * 0.35, 2),
                    'rule': 'Deduzione totale dal reddito imponibile fino al tetto di 5.164,57 €'
                })

    # E41 Ristrutturazioni Edilizie (Bonus Casa 50%)
    m_reno = re.search(r'E41[^\n]*?(\d{1,3}(?:\.\d{3})+)', quadro_e_text)
    if m_reno:
        r_str = m_reno.group(1).replace('.', '').strip()
        if r_str and r_str.isdigit():
            building_renovations = float(r_str)
            if building_renovations > 100:
                expenses_breakdown.append({
                    'code': 'E41',
                    'title': 'Interventi Recupero Patrimonio Edilizio (Bonus Casa)',
                    'amount': building_renovations,
                    'deductible': building_renovations,
                    'tax_benefit': round((building_renovations * 0.50) / 10.0, 2),
                    'rule': 'Detrazione 50% ripartita in 10 rate annuali costanti'
                })

    # E57 Bonus Mobili (50%)
    m_mob = re.search(r'E57[^\n]*?(\d{1,3}(?:\.\d{3})+)', quadro_e_text)
    if m_mob:
        mb_str = m_mob.group(1).replace('.', '').strip()
        if mb_str and mb_str.isdigit():
            furniture_expenses = float(mb_str)
            if furniture_expenses > 100:
                expenses_breakdown.append({
                    'code': 'E57',
                    'title': 'Bonus Mobili ed Elettrodomestici',
                    'amount': furniture_expenses,
                    'deductible': furniture_expenses,
                    'tax_benefit': round((furniture_expenses * 0.50) / 10.0, 2),
                    'rule': 'Detrazione 50% in 10 rate annuali'
                })

    # E61 Risparmio Energetico (Ecobonus 65%)
    m_eco = re.search(r'E61[^\n]*?(\d{1,3}(?:\.\d{3})+)', quadro_e_text)
    if m_eco:
        ec_str = m_eco.group(1).replace('.', '').strip()
        if ec_str and ec_str.isdigit():
            energy_saving_expenses = float(ec_str)
            if energy_saving_expenses > 100:
                expenses_breakdown.append({
                    'code': 'E61',
                    'title': 'Riqualificazione Energetica (Ecobonus)',
                    'amount': energy_saving_expenses,
                    'deductible': energy_saving_expenses,
                    'tax_benefit': round((energy_saving_expenses * 0.65) / 10.0, 2),
                    'rule': 'Detrazione 65% in 10 quote annuali'
                })

    # E8-E10 Altre spese
    for code in ['E8', 'E9', 'E10']:
        m_oth = re.search(rf'{code}\s+ALTRE\s+SPESE[^\n]*?(\d{{1,3}})[,\s]+(\d{{1,4}}),\d{{2}}', quadro_e_text, re.I)
        if m_oth:
            sub_code = m_oth.group(1)
            oth_amt = float(m_oth.group(2))
            if oth_amt > 0 and oth_amt < 5000:
                other_expenses_total += oth_amt
                expenses_breakdown.append({
                    'code': f"{code} (Cod. {sub_code})",
                    'title': 'Altre Spese Detraibili (Istruzione / Assicurazioni / Sport)',
                    'amount': oth_amt,
                    'deductible': oth_amt,
                    'tax_benefit': round(oth_amt * 0.19, 2),
                    'rule': 'Detrazione IRPEF 19%'
                })

    # -------------------------------------------------------------
    # 6. Final Result Determination
    # -------------------------------------------------------------
    final_refund_or_debit = 0.0
    result_type = "PAREGGIO"
    is_refund = True

    rigo_163 = righi.get('163', 0.0)
    rigo_161 = righi.get('161', 0.0)
    rigo_164 = righi.get('164', 0.0)
    rigo_162 = righi.get('162', 0.0)

    if rigo_163 > 0:
        final_refund_or_debit = rigo_163
        result_type = "RIMBORSO"
        is_refund = True
    elif rigo_164 > 0:
        final_refund_or_debit = rigo_164
        result_type = "RIMBORSO"
        is_refund = True
    elif rigo_161 > 0:
        final_refund_or_debit = rigo_161
        result_type = "DEBITO"
        is_refund = False
    elif rigo_162 > 0:
        final_refund_or_debit = rigo_162
        result_type = "DEBITO"
        is_refund = False
    elif tax_difference < 0:
        final_refund_or_debit = abs(tax_difference)
        result_type = "RIMBORSO"
        is_refund = True
    elif tax_difference > 0:
        final_refund_or_debit = tax_difference
        result_type = "DEBITO"
        is_refund = False
    else:
        final_refund_or_debit = 0.0
        result_type = "PAREGGIO"
        is_refund = True

    tax_savings_total = max(0.0, round(gross_tax - net_tax, 2))
    effective_tax_rate = round((net_tax / total_income * 100), 2) if total_income > 0 else 0.0

    return {
        'success': True,
        'tax_year': tax_year,
        'declaration_year': dec_year,
        'fiscal_code': fiscal_code,
        'taxpayer_name': taxpayer_name,
        'is_joint_declaration': is_joint,
        'declaration_type': declaration_type,
        'result_type': result_type,
        'total_income': round(total_income, 2),
        'principal_residence_deduction': round(principal_residence_deduction, 2),
        'taxable_income': round(taxable_income, 2),
        'gross_tax': round(gross_tax, 2),
        'employee_tax_credit': round(employee_tax_credit, 2),
        'total_deductions': round(total_deductions, 2),
        'net_tax': round(net_tax, 2),
        'withholdings_paid': round(withholdings_paid, 2),
        'tax_difference': round(tax_difference, 2),
        'regional_tax_due': round(regional_tax_due, 2),
        'municipal_tax_due': round(municipal_tax_due, 2),
        'municipal_tax_acc': round(municipal_tax_acc, 2),
        'rigo_161_trattenuta': round(rigo_161, 2),
        'rigo_162_versamento_f24': round(rigo_162, 2),
        'rigo_163_rimborso': round(rigo_163, 2),
        'rigo_164_rimborso_ade': round(rigo_164, 2),
        'final_refund_or_debit': round(final_refund_or_debit, 2),
        'is_refund': is_refund,
        'medical_expenses': round(medical_expenses, 2),
        'medical_expenses_deductible': max(0.0, round(medical_expenses - 129.11, 2)),
        'mortgage_interest': round(mortgage_interest, 2),
        'pension_fund_deduction': round(pension_fund_deduction, 2),
        'building_renovations': round(building_renovations, 2),
        'furniture_expenses': round(furniture_expenses, 2),
        'energy_saving_expenses': round(energy_saving_expenses, 2),
        'other_expenses_total': round(other_expenses_total, 2),
        'expenses_breakdown': expenses_breakdown,
        'tax_savings_total': tax_savings_total,
        'effective_tax_rate': effective_tax_rate
    }
