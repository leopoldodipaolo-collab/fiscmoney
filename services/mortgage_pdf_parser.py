"""Parse Italian mortgage statements (rendiconto / piano di ammortamento)."""
import re
from datetime import datetime

from services.paystub_pdf_parser import clean_amount, extract_text_from_pdf

IT_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
IT_MONEY = re.compile(r"\b\d{1,3}(?:\.\d{3})*,\d{2}\b")


def _iso_date(raw):
    m = IT_DATE.search(raw or "")
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return datetime(y, mo, d).date().isoformat()
    except ValueError:
        return None


def _add_months(iso_date, months):
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except Exception:
        return iso_date
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return datetime(y, m, d).date().isoformat()


def infer_annual_rate(principal, months, installment):
    """Newton solve TAN (%) from French amortization."""
    if not principal or not months or not installment or installment <= 0:
        return None
    r = 0.003
    for _ in range(50):
        if abs(r) < 1e-12:
            return 0.0
        x = (1 + r) ** months
        f = principal * r * x / (x - 1) - installment
        dx = months * (1 + r) ** (months - 1)
        df = principal * ((x - 1) * (x + r * dx) - r * x * dx) / (x - 1) ** 2
        if abs(df) < 1e-18:
            break
        r -= f / df
        if r <= -0.9:
            r = 0.001
    tan = round(r * 12 * 100, 3)
    if tan < 0 or tan > 20:
        return None
    return tan


def _find_after(text, patterns, flags=re.I):
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            return m
    return None


def parse_mortgage_statement_text(text):
    if not text or len(text.strip()) < 40:
        return {
            "success": False,
            "error": "PDF senza testo selezionabile (probabile scansione). Carica il rendiconto digitale dalla banca, non la foto.",
        }

    compact = re.sub(r"[ \t]+", " ", text)
    blob = compact.replace("\n", " ")

    bank = None
    bm = _find_after(blob, [
        r"(BCC\s+[A-ZÀ-Ú']+(?:\s+[A-ZÀ-Ú']+){0,5})",
        r"(Banca(?:\s+di)?\s+Credito\s+Cooperativo[^\n]{0,60})",
        r"(Intesa Sanpaolo|UniCredit|BPER|BNL|Monte dei Paschi|Crédit Agricole|ING Bank)",
    ])
    if bm:
        bank = re.sub(r"\s+", " ", bm.group(1)).strip(" -")
        bank = re.split(
            r"\s+(?:RENDICONTO|RELATIVO|EROGATO|Via\b|Banca di Credito|MUTUI)\b",
            bank,
            maxsplit=1,
        )[0].strip()[:80]

    contract = None
    cm = _find_after(blob, [
        r"MUTUI\s+IPOTECARI\s*N[°ºo]?\s*([0-9]{2,6}\s*[0-9]{3,8})",
        r"contratto\s+(?:di\s+mutuo\s+)?n[°ºo]?\s*([0-9 /.-]{5,20})",
    ])
    if cm:
        contract = re.sub(r"\s+", " ", cm.group(1)).strip()

    disbursed = None
    dm = _find_after(blob, [r"EROGATO\s+IL\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"])
    if dm:
        disbursed = _iso_date(dm.group(1))

    statement_date = None
    sm = _find_after(blob, [r"RENDICONTO\s+AL\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"])
    if sm:
        statement_date = _iso_date(sm.group(1))

    residual = None
    rm = _find_after(blob, [
        r"Debito\s+residuo\s+in\s+linea\s+capitale\s+(?:EUR\s*)?(%s)" % IT_MONEY.pattern,
    ])
    if rm:
        residual = clean_amount(rm.group(1))

    extra_cost = 0.0
    em = re.findall(r"(?:spese e commissioni|costi aggiuntivi)[^\d]{0,40}(%s)" % IT_MONEY.pattern, blob, re.I)
    if em:
        extra_cost = clean_amount(em[0])
    else:
        twos = re.findall(r"\b2,50\b", blob)
        if len(twos) >= 5:
            extra_cost = 2.5

    installment = None
    im = re.findall(r"(?:Totale Rata|Totale rata)[^\d]{0,20}(%s)" % IT_MONEY.pattern, blob, re.I)
    if im:
        installment = clean_amount(im[0])
    if not installment:
        # most frequent money around 1.000
        counts = {}
        for tok in IT_MONEY.findall(blob):
            val = round(clean_amount(tok), 2)
            if 200 <= val <= 2500:
                counts[val] = counts.get(val, 0) + 1
        if counts:
            installment = max(counts.items(), key=lambda kv: kv[1])[0]

    duration_months = None
    last_n = None
    nums = [int(x) for x in re.findall(r"(?m)^\s*0*(\d{1,3})\s+%s" % IT_MONEY.pattern, text)]
    if not nums:
        nums = [int(x) for x in re.findall(r"\b0*(\d{2,3})\s+1\.\d{3},\d{2}", blob)]
    if nums:
        last_n = max(n for n in nums if 12 <= n <= 480)
    if last_n:
        duration_months = last_n

    original = None
    tot2 = re.search(
        r"Totale\s+(%s)\s+(%s)\s+(%s)\s+(%s)" % (IT_MONEY.pattern, IT_MONEY.pattern, IT_MONEY.pattern, IT_MONEY.pattern),
        blob,
        re.I,
    )
    total_paid = total_interest = total_extra = None
    if tot2:
        total_paid = clean_amount(tot2.group(1))
        total_interest = clean_amount(tot2.group(2))
        original = clean_amount(tot2.group(3))
        total_extra = clean_amount(tot2.group(4))
        if duration_months and total_extra and extra_cost <= 0:
            extra_cost = round(total_extra / duration_months, 2)

    start_date = None
    first_due = re.search(r"\b001\b.{0,80}?(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", blob)
    if first_due:
        start_date = _iso_date(first_due.group(1))
    if not start_date and disbursed:
        start_date = _add_months(disbursed, 1)

    net_inst = None
    if installment:
        net_inst = round(installment - (extra_cost or 0), 2)
        if net_inst <= 0:
            net_inst = installment

    rate = infer_annual_rate(original, duration_months, net_inst) if original and duration_months and net_inst else None

    looks_mortgage = bool(
        re.search(r"mutuo|ipotecar|ammortamento|piano di rientro|rendiconto", blob, re.I)
    )
    if not looks_mortgage:
        return {
            "success": False,
            "error": "Il PDF non sembra un rendiconto o piano di ammortamento mutuo.",
        }

    if not original and not installment:
        return {
            "success": False,
            "error": "Non ho trovato capitale e rata nel PDF. Serve il rendiconto con piano di rientro.",
        }

    return {
        "success": True,
        "bank_name": bank or "Banca",
        "contract_number": contract,
        "disbursed_date": disbursed,
        "statement_date": statement_date,
        "start_date": start_date,
        "original_amount": original,
        "duration_months": duration_months,
        "monthly_installment": installment,
        "extra_monthly_cost": extra_cost or 0.0,
        "residual_at_statement": residual,
        "annual_interest_rate": rate,
        "total_paid": total_paid,
        "total_interest": total_interest,
        "total_extra": total_extra,
        "interest_type": "FIXED",
        "name": "Mutuo Prima Casa",
        "is_primary_residence": 1,
    }


def parse_mortgage_pdf(file_stream_or_path):
    text, _tables = extract_text_from_pdf(file_stream_or_path)
    return parse_mortgage_statement_text(text)


def merge_mortgage_parses(results):
    """Merge several pages / files of the same rendiconto."""
    ok = [r for r in results if r and r.get("success")]
    if not ok:
        err = next((r.get("error") for r in results if r and r.get("error")), None)
        return {
            "success": False,
            "error": err or "Impossibile leggere il rendiconto mutuo dal PDF.",
        }
    merged = dict(ok[0])
    for r in ok[1:]:
        for k, v in r.items():
            if k in ("success",):
                continue
            if v in (None, "", 0, 0.0) and merged.get(k) not in (None, "", 0, 0.0):
                continue
            if k == "duration_months":
                merged[k] = max(int(merged.get(k) or 0), int(v or 0)) or merged.get(k)
            elif k in ("original_amount", "total_paid", "total_interest") and v:
                if not merged.get(k) or float(v) >= float(merged.get(k) or 0):
                    merged[k] = v
            else:
                if v not in (None, ""):
                    merged[k] = v
    if merged.get("original_amount") and merged.get("duration_months") and merged.get("monthly_installment"):
        net = round(merged["monthly_installment"] - (merged.get("extra_monthly_cost") or 0), 2)
        merged["annual_interest_rate"] = infer_annual_rate(
            merged["original_amount"], merged["duration_months"], net
        ) or merged.get("annual_interest_rate")
    return merged
