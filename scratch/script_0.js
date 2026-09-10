
let currentImportToken = null;
let currentAccountMeta = {};
let currentImportData = null;
let currentStep = 1;
let categoryOverrides = {};

const MACRO_CATEGORIES_OBJ = {"Auto \u0026 Trasporti": {"color": "#f59e0b", "icon": "\ud83d\ude97", "subcategories": ["Carburante \u0026 Ricarica", "Telepass \u0026 Pedaggi", "Assicurazione", "Bollo", "Tagliando \u0026 Manutenzione", "Mezzi Pubblici \u0026 Taxi", "Cambio Gomme"]}, "Casa \u0026 Utenze": {"color": "#3b82f6", "icon": "\ud83c\udfe0", "subcategories": ["Luce \u0026 Gas", "Gas", "Acqua \u0026 Rifiuti", "Internet \u0026 Telefono", "Mutuo / Affitto", "Condominio", "Manutenzione \u0026 Arredo", "Detersivi \u0026 Casa", "Abbonamenti Digitali", "Cinema \u0026 Spettacoli"]}, "Lavoro \u0026 Entrate": {"color": "#8b5cf6", "icon": "\ud83d\udcbc", "subcategories": ["Stipendio", "Bonus \u0026 Premi", "Rimborsi Spese", "Prestazioni Occasionali", "Altre Entrate"]}, "Risparmio \u0026 Futuro": {"color": "#14b8a6", "icon": "\ud83d\udcc8", "subcategories": ["Fondo Pensione", "Investimenti \u0026 PAC", "Giroconto Interno", "Conto Deposito"]}, "Salute \u0026 Benessere": {"color": "#ec4899", "icon": "\ud83e\ude7a", "subcategories": ["Farmacia \u0026 Medicinali", "Visite Mediche \u0026 Esami", "Dentista \u0026 Ottico", "Palestra \u0026 Sport", "Igiene \u0026 Cura Personale"]}, "Spesa \u0026 Alimentari": {"color": "#10b981", "icon": "\ud83d\uded2", "subcategories": ["Supermercato", "Panetteria \u0026 Forno", "Macelleria", "Ortofrutta", "Pescheria"]}, "Svago \u0026 Ristoranti": {"color": "#f97316", "icon": "\ud83c\udf7d\ufe0f", "subcategories": ["Ristoranti", "Pizzerie", "Bar \u0026 Caff\u00e8", "Shopping \u0026 Moda", "Hobby \u0026 Svago"]}, "Tasse \u0026 Finanza": {"color": "#64748b", "icon": "\ud83c\udfdb\ufe0f", "subcategories": ["F24 \u0026 Imposte", "Canoni \u0026 Commissioni", "IMU \u0026 Tributi Locali", "Consulenze"]}, "Viaggi \u0026 Vacanze": {"color": "#06b6d4", "icon": "\u2708\ufe0f", "subcategories": ["Hotel \u0026 Alloggi", "Voli \u0026 Treni Lunghi", "Noleggio Auto", "Vacanze \u0026 Attivit\u00e0"]}};
const ALL_PROFILES = [{"assistant_persona": "leo", "id": 2, "invited_email": null, "is_primary": 1, "linked_user_id": null, "name": "Leopoldo Di Paolo", "role_title": "Titolare", "tax_code": null, "workspace_id": 2}];
const CATEGORY_SMART_TAGS_OBJ = {"Auto \u0026 Trasporti": [{"code": "#carburante", "icon": "\u26fd", "label": "Carburante", "subcat": "Carburante \u0026 Ricarica"}, {"code": "#telepass", "icon": "\ud83d\udee3\ufe0f", "label": "Telepass \u0026 Pedaggi", "subcat": "Telepass \u0026 Pedaggi"}, {"code": "#assicurazione", "icon": "\ud83d\udee1\ufe0f", "label": "Assicurazione", "subcat": "Assicurazione"}, {"code": "#bollo", "icon": "\ud83d\udee1\ufe0f", "label": "Bollo", "subcat": "Bollo"}, {"code": "#tagliando_meccanico", "icon": "\ud83d\udd27", "label": "Tagliando \u0026 Meccanico", "subcat": "Tagliando \u0026 Manutenzione"}, {"code": "#mezzi_taxi", "icon": "\ud83d\ude86", "label": "Mezzi \u0026 Taxi", "subcat": "Mezzi Pubblici \u0026 Taxi"}, {"code": "#cambio_gomme", "icon": "\ud83d\udd27", "label": "Cambio Gomme", "subcat": "Cambio Gomme"}], "Casa \u0026 Utenze": [{"code": "#luce_gas", "icon": "\u26a1", "label": "Luce \u0026 Gas", "subcat": "Luce \u0026 Gas"}, {"code": "#gas", "icon": "\u26a1", "label": "Gas", "subcat": "Gas"}, {"code": "#acqua", "icon": "\u26a1", "label": "Acqua", "subcat": "Acqua \u0026 Rifiuti"}, {"code": "#internet_telefono", "icon": "\ud83c\udf10", "label": "Internet \u0026 Telefono", "subcat": "Internet \u0026 Telefono"}, {"code": "#mutuo_affitto", "icon": "\ud83c\udfe2", "label": "Mutuo / Affitto", "subcat": "Mutuo / Affitto"}, {"code": "#condominio", "icon": "\ud83c\udfd8\ufe0f", "label": "Condominio", "subcat": "Condominio"}, {"code": "#brico_arredo", "icon": "\ud83d\udee0\ufe0f", "label": "Brico \u0026 Arredo", "subcat": "Manutenzione \u0026 Arredo"}, {"code": "#detersivi", "icon": "\ud83d\udee0\ufe0f", "label": "Detersivi", "subcat": "Detersivi \u0026 Casa"}, {"code": "#streaming_abbonamenti", "icon": "\ud83d\udcfa", "label": "Streaming \u0026 Abbonamenti", "subcat": "Abbonamenti Digitali"}, {"code": "#cinema_spettacoli", "icon": "\ud83c\udf9f\ufe0f", "label": "Cinema \u0026 Spettacoli", "subcat": "Cinema \u0026 Spettacoli"}], "Lavoro \u0026 Entrate": [{"code": "#stipendio", "icon": "\ud83d\udcb6", "label": "Stipendio", "subcat": "Stipendio"}, {"code": "#bonus_premi", "icon": "\ud83c\udf81", "label": "Bonus \u0026 Premi", "subcat": "Bonus \u0026 Premi"}, {"code": "#rimborsi_spese", "icon": "\ud83e\uddfe", "label": "Rimborsi Spese", "subcat": "Rimborsi Spese"}, {"code": "#prestazioni_extra", "icon": "\ud83d\udcbc", "label": "Prestazioni Extra", "subcat": "Prestazioni Occasionali"}], "Risparmio \u0026 Futuro": [{"code": "#deducibile_pensione", "icon": "\ud83d\udcc8", "is_fiscal": true, "label": "Fondo Pensione (deducibile)", "subcat": "Fondo Pensione"}, {"code": "#investimenti_pac", "icon": "\ud83d\udcca", "label": "Investimenti \u0026 PAC", "subcat": "Investimenti \u0026 PAC"}, {"code": "#giroconto", "icon": "\ud83d\udd04", "is_default": true, "label": "Giroconto Interno", "subcat": "Giroconto Interno"}], "Salute \u0026 Benessere": [{"code": "#detraibile_730", "icon": "\ud83e\ude7a", "is_default": true, "is_fiscal": true, "label": "730 Detraibile", "subcat": "Farmacia \u0026 Medicinali"}, {"code": "#farmacia", "icon": "\ud83d\udc8a", "label": "Farmacia", "subcat": "Farmacia \u0026 Medicinali"}, {"code": "#visite_esami", "icon": "\ud83e\ude7a", "is_fiscal": true, "label": "Visite \u0026 Esami", "subcat": "Visite Mediche \u0026 Esami"}, {"code": "#dentista_ottico", "icon": "\ud83e\uddb7", "is_fiscal": true, "label": "Dentista \u0026 Ottico", "subcat": "Dentista \u0026 Ottico"}, {"code": "#palestra_sport", "icon": "\ud83c\udfcb\ufe0f", "label": "Palestra \u0026 Sport", "subcat": "Palestra \u0026 Sport"}, {"code": "#igiene", "icon": "\ud83d\udee0\ufe0f", "label": "Igiene", "subcat": "Igiene \u0026 Cura Personale"}], "Spesa \u0026 Alimentari": [{"code": "#supermercato", "icon": "\ud83d\uded2", "label": "Supermercato", "subcat": "Supermercato"}, {"code": "#panetteria_forno", "icon": "\ud83e\udd56", "label": "Panetteria \u0026 Forno", "subcat": "Panetteria \u0026 Forno"}, {"code": "#macelleria", "icon": "\ud83e\udd69", "label": "Macelleria", "subcat": "Macelleria"}, {"code": "#frutta_verdura", "icon": "\ud83c\udf4f", "label": "Frutta \u0026 Verdura", "subcat": "Ortofrutta"}, {"code": "#pescheria", "icon": "\ud83e\udd69", "label": "Pescheria", "subcat": "Pescheria"}], "Svago \u0026 Ristoranti": [{"code": "#ristorante", "icon": "\ud83c\udf55", "label": "Ristorante", "subcat": "Ristoranti"}, {"code": "#pizzeria", "icon": "\ud83c\udf55", "label": "Pizzeria", "subcat": "Pizzerie"}, {"code": "#bar_caffetteria", "icon": "\u2615", "label": "Bar \u0026 Caffetteria", "subcat": "Bar \u0026 Caff\u00e8"}, {"code": "#shopping_moda", "icon": "\ud83d\udecd\ufe0f", "label": "Shopping \u0026 Moda", "subcat": "Shopping \u0026 Moda"}], "Tasse \u0026 Finanza": [{"code": "#f24_imposte", "icon": "\ud83d\udcc4", "label": "F24 \u0026 Imposte", "subcat": "F24 \u0026 Imposte"}, {"code": "#canoni_commissioni", "icon": "\ud83c\udfe6", "label": "Canoni \u0026 Commissioni", "subcat": "Canoni \u0026 Commissioni"}, {"code": "#imu_tari", "icon": "\ud83c\udfe0", "label": "IMU \u0026 TARI", "subcat": "IMU \u0026 Tributi Locali"}], "Viaggi \u0026 Vacanze": [{"code": "#hotel_alloggi", "icon": "\ud83c\udfe8", "label": "Hotel \u0026 Alloggi", "subcat": "Hotel \u0026 Alloggi"}, {"code": "#voli_treni", "icon": "\u2708\ufe0f", "label": "Voli \u0026 Treni", "subcat": "Voli \u0026 Treni Lunghi"}, {"code": "#noleggio_auto", "icon": "\ud83d\ude97", "label": "Noleggio Auto", "subcat": "Noleggio Auto"}, {"code": "#vacanze_relax", "icon": "\ud83c\udfd6\ufe0f", "label": "Vacanze \u0026 Relax", "subcat": "Vacanze \u0026 Attivit\u00e0"}]};

// --- BULK SELECTION & ACTIONS LOGIC ---
let selectedTxIds = new Set();
let bulkActiveTags = [];

function toggleSelectAll(master) {
    const checks = document.querySelectorAll('.tx-row-check');
    checks.forEach(c => {
        c.checked = master.checked;
        if (master.checked) {
            selectedTxIds.add(parseInt(c.value));
        } else {
            selectedTxIds.delete(parseInt(c.value));
        }
    });
    updateBulkToolbar();
}

function onTxCheckChange() {
    const checks = document.querySelectorAll('.tx-row-check');
    selectedTxIds.clear();
    checks.forEach(c => {
        if (c.checked) {
            selectedTxIds.add(parseInt(c.value));
        }
    });
    
    const master = document.getElementById('selectAllCheckbox');
    if (master) {
        master.checked = (checks.length > 0 && selectedTxIds.size === checks.length);
    }
    updateBulkToolbar();
}

function deselectAllTx() {
    selectedTxIds.clear();
    document.querySelectorAll('.tx-row-check').forEach(c => c.checked = false);
    const master = document.getElementById('selectAllCheckbox');
    if (master) master.checked = false;
    updateBulkToolbar();
}

function updateBulkToolbar() {
    const tb = document.getElementById('bulkActionToolbar');
    const lbl = document.getElementById('bulkCountLabel');
    if (!tb || !lbl) return;
    
    if (selectedTxIds.size > 0) {
        tb.style.display = 'flex';
        lbl.innerText = `${selectedTxIds.size} movimento${selectedTxIds.size > 1 ? 'i' : ''} selezionat${selectedTxIds.size > 1 ? 'i' : 'o'}`;
    } else {
        tb.style.display = 'none';
    }
}

function openBulkModal() {
    if (selectedTxIds.size === 0) return;
    document.getElementById('bulkModalCountNotice').innerText = `Stai per riclassificare ${selectedTxIds.size} movimenti contemporaneamente`;
    document.getElementById('bulkCategorySelect').value = '';
    document.getElementById('bulkSmartTagsContainer').innerHTML = '<span style="font-size: 0.72rem; color: var(--text-muted); font-style: italic;">Seleziona prima una categoria</span>';
    bulkActiveTags = [];
    document.getElementById('bulkModal').classList.add('open');
}

function closeBulkModal() {
    document.getElementById('bulkModal').classList.remove('open');
}

function onBulkCategoryChange(catName) {
    const container = document.getElementById('bulkSmartTagsContainer');
    container.innerHTML = '';
    bulkActiveTags = [];
    
    const smartTags = (CATEGORY_SMART_TAGS_OBJ && CATEGORY_SMART_TAGS_OBJ[catName]) ? CATEGORY_SMART_TAGS_OBJ[catName] : [];
    if (smartTags.length === 0) {
        container.innerHTML = '<span style="font-size: 0.72rem; color: var(--text-muted); font-style: italic;">Nessun tag predefinito per questa categoria.</span>';
        return;
    }
    
    smartTags.forEach(st => {
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = `tag-chip ${st.is_fiscal ? 'tag-fiscal' : ''}`;
        pill.style.cursor = 'pointer';
        pill.style.padding = '4px 9px';
        pill.style.fontSize = '0.75rem';
        pill.style.borderRadius = '16px';
        pill.style.border = '1px solid rgba(255,255,255,0.12)';
        pill.style.background = 'rgba(255,255,255,0.04)';
        pill.style.color = '#cbd5e1';
        pill.innerHTML = st.label;
        pill.onclick = () => {
            if (bulkActiveTags.includes(st.code)) {
                bulkActiveTags = bulkActiveTags.filter(t => t !== st.code);
                pill.style.border = '1px solid rgba(255,255,255,0.12)';
                pill.style.background = 'rgba(255,255,255,0.04)';
                pill.style.color = '#cbd5e1';
                pill.innerHTML = st.label;
            } else {
                bulkActiveTags.push(st.code);
                pill.style.border = '1.5px solid #38bdf8';
                pill.style.background = 'rgba(56, 189, 248, 0.25)';
                pill.style.color = '#7dd3fc';
                pill.innerHTML = `✓ ${st.label}`;
            }
        };
        container.appendChild(pill);
    });
}

async function executeBulkUpdate() {
    const cat = document.getElementById('bulkCategorySelect').value;
    if (!cat) {
        alert("Seleziona una categoria!");
        return;
    }
    
    const learnRule = document.getElementById('bulkLearnRuleCheck').checked;
    const txIdsArr = Array.from(selectedTxIds);
    
    try {
        const resp = await fetch('/transactions/bulk-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tx_ids: txIdsArr,
                category: cat,
                tags: bulkActiveTags.join(' '),
                learn_rule: learnRule
            })
        });
        const res = await resp.json();
        if (res.success) {
            closeBulkModal();
            // Show feedback toast and refresh
            alert(`✨ ${res.updated_count} movimenti aggiornati con successo! (${res.rules_count} regole memorizzate)`);
            window.location.reload();
        } else {
            alert("Errore: " + (res.error || "Impossibile aggiornare"));
        }
    } catch (e) {
        console.error(e);
        alert("Errore di connessione");
    }
}

// --- UNIFIED SMART CATEGORY TRAY & SPEED GAME TRIAGE LOGIC ---
let activeTrayTxId = null;
let activeTrayTxDesc = '';
let activeTrayCategory = '';
let activeTraySubCat = '';
let trayActiveTags = [];
let activeTrayAmount = 0;

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function openSmartCategoryTrayFromBtn(btn, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    if (!btn) return;
    const txId = parseInt(btn.getAttribute('data-tx-id') || btn.dataset.txId);
    const category = btn.getAttribute('data-category') || '';
    const subCategory = btn.getAttribute('data-subcategory') || '';
    const tags = btn.getAttribute('data-tags') || '';
    const desc = btn.getAttribute('data-desc') || '';
    const amount = parseFloat(btn.getAttribute('data-amount') || btn.dataset.amount) || 0;
    openSmartCategoryTray(txId, category, subCategory, tags, desc, amount);
}

function openEditTxModalFromBtn(btn, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    if (!btn) return;
    const txId = parseInt(btn.getAttribute('data-tx-id') || btn.dataset.txId);
    const category = btn.getAttribute('data-category') || 'Altro';
    const subCategory = btn.getAttribute('data-subcategory') || '';
    const tags = btn.getAttribute('data-tags') || '';
    const desc = btn.getAttribute('data-desc') || '';
    openEditTxModal(txId, category, subCategory, tags, desc);
}

function openSmartCategoryTray(txId, category, subCategory, tags, desc, amount) {
    activeTrayTxId = txId;
    activeTrayTxDesc = desc || '';
    activeTrayCategory = category || '';
    activeTraySubCat = subCategory || '';
    activeTrayAmount = amount || 0;
    trayActiveTags = (tags || '').split(/\s+/).filter(Boolean);

    const descEl = document.getElementById('trayTxDesc');
    if (descEl) {
        descEl.innerText = desc || 'Movimento';
        descEl.title = desc || '';
    }
    
    const dateElTarget = document.getElementById('trayTxDate');
    if (dateElTarget) {
        const rowEl = document.getElementById(`txRow-${txId}`);
        const dateEl = rowEl ? rowEl.querySelector('div[style*="font-family: monospace"]') : null;
        dateElTarget.innerText = dateEl ? dateEl.innerText.trim() : '';
    }

    const amtEl = document.getElementById('trayTxAmount');
    if (amtEl) {
        amtEl.innerText = formatEurJs(amount, true);
        amtEl.style.color = (amount > 0) ? 'var(--accent-success)' : '#f87171';
    }

    const subInput = document.getElementById('traySubCatInput');
    if (subInput) {
        subInput.value = subCategory || '';
    }

    const learnCheck = document.getElementById('trayLearnRuleCheck');
    if (learnCheck) {
        learnCheck.checked = true;
    }

    // Highlight selected card or clear
    highlightTrayCategoryCard(activeTrayCategory);
    renderTraySmartTags(activeTrayCategory);

    const modal = document.getElementById('smartCategoryTrayModal');
    if (modal) {
        modal.classList.add('open');
    }
}

function closeSmartCategoryTray() {
    const modal = document.getElementById('smartCategoryTrayModal');
    if (modal) modal.classList.remove('open');
    activeTrayTxId = null;
}

function highlightTrayCategoryCard(catName) {
    const cards = document.querySelectorAll('.cat-select-card[id^="trayCatCard-"]');
    cards.forEach(card => {
        const lbl = card.querySelector('.card-label')?.innerText?.trim();
        if (lbl === catName) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });
}

function selectTrayCategory(catName, catIcon, catColor) {
    activeTrayCategory = catName;
    highlightTrayCategoryCard(catName);

    // Smart default presets if not already present
    if (catName === 'Salute & Benessere') {
        if (!trayActiveTags.includes('#detraibile_730')) {
            trayActiveTags.push('#detraibile_730');
        }
        if (!document.getElementById('traySubCatInput').value) {
            document.getElementById('traySubCatInput').value = 'Farmacia & Medicinali';
        }
    } else if (catName === 'Giroconti & Trasferimenti') {
        if (!trayActiveTags.includes('#giroconto')) {
            trayActiveTags.push('#giroconto');
        }
        if (!document.getElementById('traySubCatInput').value) {
            document.getElementById('traySubCatInput').value = 'Giroconto Interno';
        }
    } else if (catName === 'Entrate & Stipendi') {
        if (!trayActiveTags.includes('#stipendio')) {
            trayActiveTags.push('#stipendio');
        }
        if (!document.getElementById('traySubCatInput').value) {
            document.getElementById('traySubCatInput').value = 'Stipendio / Emolumento';
        }
    }

    renderTraySmartTags(catName);
}

function renderTraySmartTags(category) {
    const container = document.getElementById('traySmartTagsContainer');
    if (!container) return;
    container.innerHTML = '';

    const cat = category || activeTrayCategory;
    const smartTags = (CATEGORY_SMART_TAGS_OBJ && CATEGORY_SMART_TAGS_OBJ[cat]) ? CATEGORY_SMART_TAGS_OBJ[cat] : [];

    if (smartTags.length === 0 && trayActiveTags.length === 0) {
        container.innerHTML = '<span style="font-size: 0.72rem; color: var(--text-muted); font-style: italic;">Nessun tag predefinito per questa categoria. Clicca su "+ Altro Tag".</span>';
        return;
    }

    // 1. Category preset smart tags
    smartTags.forEach(st => {
        const isSelected = trayActiveTags.includes(st.code);
        const isFiscal = st.code === '#detraibile_730';

        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = `tag-chip ${isFiscal ? 'tag-fiscal' : ''}`;
        pill.style.cursor = 'pointer';
        pill.style.padding = '4px 9px';
        pill.style.fontSize = '0.75rem';
        pill.style.borderRadius = '16px';
        pill.style.transition = 'all 0.15s ease';
        pill.style.border = isSelected ? (isFiscal ? '1.5px solid #10b981' : '1.5px solid #38bdf8') : '1px solid rgba(255,255,255,0.12)';
        pill.style.background = isSelected ? (isFiscal ? 'rgba(16, 185, 129, 0.25)' : 'rgba(56, 189, 248, 0.25)') : 'rgba(255,255,255,0.04)';
        pill.style.color = isSelected ? (isFiscal ? '#6ee7b7' : '#7dd3fc') : '#cbd5e1';
        pill.style.fontWeight = isSelected ? '700' : '500';

        pill.innerHTML = `${isSelected ? '✓ ' : ''}${st.label}`;
        pill.onclick = () => toggleTrayTag(st.code, st.default_subcat);
        container.appendChild(pill);
    });

    // 2. Any custom tags attached
    trayActiveTags.forEach(tCode => {
        const inPreset = smartTags.some(st => st.code === tCode);
        if (!inPreset) {
            const pill = document.createElement('button');
            pill.type = 'button';
            pill.className = 'tag-chip';
            pill.style.cursor = 'pointer';
            pill.style.padding = '4px 9px';
            pill.style.fontSize = '0.75rem';
            pill.style.borderRadius = '16px';
            pill.style.border = '1.5px solid #38bdf8';
            pill.style.background = 'rgba(56, 189, 248, 0.25)';
            pill.style.color = '#7dd3fc';
            pill.style.fontWeight = '700';

            const cleanLabel = tCode.replace(/^#/, '').replace(/_/g, ' ');
            pill.innerHTML = `✓ 🏷️ ${cleanLabel} &times;`;
            pill.onclick = () => toggleTrayTag(tCode);
            container.appendChild(pill);
        }
    });
}

function toggleTrayTag(tagCode, defaultSubcat) {
    if (trayActiveTags.includes(tagCode)) {
        trayActiveTags = trayActiveTags.filter(t => t !== tagCode);
    } else {
        trayActiveTags.push(tagCode);
        if (defaultSubcat && !document.getElementById('traySubCatInput').value) {
            document.getElementById('traySubCatInput').value = defaultSubcat;
        }
    }
    renderTraySmartTags();
}

async function saveSmartTray() {
    if (!activeTrayTxId) return;
    if (!activeTrayCategory) {
        alert("Seleziona una Macro-Categoria!");
        return;
    }

    const txId = activeTrayTxId;
    const cat = activeTrayCategory;
    const subCat = (document.getElementById('traySubCatInput').value || '').trim();
    const tagsStr = trayActiveTags.join(' ');
    const learnRule = document.getElementById('trayLearnRuleCheck').checked;

    closeSmartCategoryTray();

    // Optimistically update the row badge in UI
    updateTxRowOptimistically(txId, cat, subCat, tagsStr);

    try {
        const resp = await fetch('/transactions/quick-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tx_id: txId,
                category: cat,
                sub_category: subCat,
                tags: tagsStr,
                learn_rule: learnRule
            })
        });
        const res = await resp.json();
        if (res.success && res.pattern) {
            // Apply learned pattern to other matching rows in DOM
            const patLower = res.pattern.toLowerCase();
            document.querySelectorAll('.tx-item').forEach(item => {
                const itemDescEl = item.querySelector('div[title]');
                const itemDesc = itemDescEl ? (itemDescEl.getAttribute('title') || '').toLowerCase() : '';
                if (itemDesc.includes(patLower)) {
                    const rowId = parseInt(item.id.replace('txRow-', ''));
                    if (rowId && rowId !== txId) {
                        updateTxRowOptimistically(rowId, cat, subCat, tagsStr);
                    }
                }
            });
        }
    } catch (e) {
        console.error("Errore salvataggio smart tray:", e);
    }
}

function updateTxRowOptimistically(txId, category, subCategory, tagsStr) {
    const container = document.getElementById(`unifiedCatContainer-${txId}`);
    if (!container) return;

    const catMeta = MACRO_CATEGORIES_OBJ[category] || { icon: '📦', color: '#64748b' };
    const isFiscal = tagsStr && tagsStr.includes('#detraibile_730');
    const isPension = tagsStr && tagsStr.includes('#deducibile_pensione');

    let subtagHtml = subCategory ? `<span class="cat-subtag">• ${escapeHtml(subCategory)}</span>` : '';
    let badgeHtml = '';
    if (isFiscal) {
        badgeHtml = `<span class="badge-tag-mini fiscal">🩺 730</span>`;
    } else if (isPension) {
        badgeHtml = `<span class="badge-tag-mini" style="background: rgba(59,130,246,0.2); color: #93c5fd; border: 1px solid rgba(59,130,246,0.4); font-size: 0.62rem; padding: 1px 4px; border-radius: 4px; font-weight: 800;">🛡️ Prev</span>`;
    }

    const row = document.getElementById(`txRow-${txId}`);
    let amount = 0;
    if (row) {
        const amtStrong = row.querySelector('strong[style*="text-align: right"]');
        if (amtStrong) {
            const rawTxt = amtStrong.innerText.replace(/[^\d,-]/g, '').replace(',', '.');
            amount = parseFloat(rawTxt) || 0;
        }
    }

    const descEl = row ? row.querySelector('div[title]') : null;
    const desc = descEl ? (descEl.getAttribute('title') || '') : '';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = `unifiedCatBtn-${txId}`;
    btn.className = 'unified-cat-btn categorized';
    btn.style.setProperty('--cat-color', catMeta.color);
    btn.dataset.txId = txId;
    btn.dataset.category = category;
    btn.dataset.subcategory = subCategory;
    btn.dataset.tags = tagsStr;
    btn.dataset.desc = desc;
    btn.dataset.amount = amount;
    btn.onclick = function() { openSmartCategoryTrayFromBtn(this); };
    btn.title = "Tocca per riclassificare o modificare tag";
    btn.innerHTML = `
        <span class="cat-icon">${catMeta.icon}</span>
        <span class="cat-name">${escapeHtml(category)}</span>
        ${subtagHtml}
        ${badgeHtml}
        <span style="font-size: 0.65rem; color: var(--text-muted); margin-left: auto; opacity: 0.6;">✎</span>
    `;

    container.innerHTML = '';
    container.appendChild(btn);

    if (row) {
        row.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        row.style.background = 'rgba(16, 185, 129, 0.08)';
        setTimeout(() => {
            row.style.borderColor = 'var(--border-color)';
            row.style.background = 'rgba(255, 255, 255, 0.02)';
        }, 1200);
    }
}

// --- SPEED TRIAGE GAME MODE (SMISTA AL VOLO) QUEUE LOGIC ---
const INITIAL_SPEED_QUEUE = [{"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -60.0, "date": "2026-08-17", "description": "ADDEBITO SDD FONDAZIONE TELETHON       N: 1166989152/67 ID:L33184D000000896434085         XID 0553386, 22449868, Donazione(30) Recuper o                                            DEB: DI PAOLO LEOPOLDO 1166989152", "id": 954, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -8.0, "date": "2026-08-17", "description": "NERO COCKTAILS AND KITCH L\u0027AQUILA Operazione Carta 93641892 del 15.08.2026 13:19", "id": 951, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -18.08, "date": "2026-08-10", "description": "PP*GOOGLE GOOGLE ONE 1600 AMPHITHEATER PARKWAY 4029357733", "id": 1364, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -209.3, "date": "2026-08-08", "description": "AMZN Mktp IT 5 rue plaetis LUXEMBOURG", "id": 1365, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-08-04", "description": "GE DA IMPIANTI CORSO DELLA LIBERTA\u0027 AVEZZANO", "id": 1367, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -14.15, "date": "2026-08-04", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 01.08.2026", "id": 963, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -25.0, "date": "2026-08-03", "description": "DI GIANNATALE AURELIO L\u0027AQUILA Operazione Carta 93641892 del 31.07.2026 11:41", "id": 973, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -20.0, "date": "2026-08-03", "description": "STICOTTI ALESSANDRO MERC L\u0027AQUILA AQ Operazione Carta 93641892 del 31.07.2026 11:26", "id": 972, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -6.0, "date": "2026-07-28", "description": "SumUp  *TERRAZZA   SRL L AQUILA ITA Operazione carta ****8815 del 25.07.2026", "id": 980, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -85.0, "date": "2026-07-28", "description": "ARROSTICINI DIVINI L\u0027AQUILA ITA Operazione carta ****8815 del 25.07.2026", "id": 979, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-07-27", "description": "PAYPAL *GEDIMPIANTI AVEZZANO", "id": 1372, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -6.4, "date": "2026-07-27", "description": "SumUp  *IL BABA  SNC D CARSOLI ITA Operazione carta ****8815 del 23.07.2026", "id": 983, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -4.24, "date": "2026-07-26", "description": "PAYPAL *NOW 670B1 CINE Milano", "id": 1375, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -3.75, "date": "2026-07-26", "description": "PAYPAL *NOW F5F7B PASS Milano", "id": 1374, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -19.99, "date": "2026-07-26", "description": "PAYPAL *NOW 7063E SPOR Milano", "id": 1373, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -61.98, "date": "2026-07-21", "description": "AMZN Mktp IT 5 rue plaetis LUXEMBOURG", "id": 1377, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-07-17", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1379, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -30.0, "date": "2026-07-15", "description": "ADDEBITO SDD FONDAZIONE TELETHON       N: 1158207845/75 ID:L33184D000000896434085         XID 0553386, 22213550, Donazione(30)                                                      DEB: DI PAOLO LEOPOLDO 1158207845", "id": 987, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -1.5, "date": "2026-07-14", "description": "BUFFET ROMA TIBURTINA ROMA Operazione Carta 93641892 del 13.07.2026 09:08", "id": 989, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -18.28, "date": "2026-07-10", "description": "PP*GOOGLE GOOGLE ONE 4029357733", "id": 1380, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -3.0, "date": "2026-07-08", "description": "SumUp  *GI CI FAMILYFO San Benedetto ITA Operazione carta ****8815 del 06.07.2026", "id": 1001, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -11.51, "date": "2026-07-06", "description": "COMPETENZE SPESE ED ONERI", "id": 1007, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -38.41, "date": "2026-07-03", "description": "PAYPAL *ARUBA SPA 35314369001", "id": 1384, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-06-30", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1387, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -55.22, "date": "2026-06-29", "description": "PYTHONANYWHERE 5 The Green RICHMOND", "id": 1389, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -140.0, "date": "2026-06-29", "description": "AUTOABRUZZO SRL L\u0027AQUILA Operazione Carta 93641892 del 27.06.2026 09:32", "id": 1022, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -1.99, "date": "2026-06-29", "description": "VILLA BEBE\u0027 L\u0027AQUILA Operazione Carta 93641892 del 27.06.2026 10:01", "id": 1021, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -159.38, "date": "2026-06-29", "description": "VILLA BEBE\u0027 L\u0027AQUILA Operazione Carta 93641892 del 27.06.2026 10:01", "id": 1020, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -3.75, "date": "2026-06-26", "description": "PAYPAL *NOW A8391 PASS 35314369001", "id": 1392, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -19.99, "date": "2026-06-26", "description": "PAYPAL *NOW 0D80F SPOR 35314369001", "id": 1391, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -4.24, "date": "2026-06-26", "description": "PAYPAL *NOW 6022F CINE 35314369001", "id": 1390, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -30.0, "date": "2026-06-24", "description": "DISPOSIZIONE BONIFICO ISTANTANEO a favore di Antonio Salvi EUR  30,00  Festa TozziComm.bonifico : 0,12 + Comm. di maggiorazione : 0,00 EUR Num. Bonifico 261756061241540-644080240470IT05387-RIF. 26175/6241543", "id": 1026, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -0.12, "date": "2026-06-24", "description": "COMM. BON. ISTANTANEO a favore di Antonio Salvi EUR  30,00  Festa TozziComm.bonifico : 0,12 + Comm. di maggiorazione : 0,00 EUR Num. Bonifico 261756061241540-644080240470IT05387-RIF. 26175/6241543", "id": 1025, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-06-23", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1394, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -48.73, "date": "2026-06-22", "description": "RISPARMIO CASA L\u0027AQUILA AQ Operazione Carta 93641892 del 21.06.2026 18:40", "id": 1030, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -40.0, "date": "2026-06-22", "description": "AUTOABRUZZO SRL L\u0027AQUILA Operazione Carta 93641892 del 19.06.2026 17:29", "id": 1027, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -13.25, "date": "2026-06-16", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 13.06.2026", "id": 1032, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-06-15", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1395, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -12.1, "date": "2026-06-15", "description": "FELTRINELLI LIBRERIE MILANO ITA Operazione carta ****8815 del 11.06.2026", "id": 1038, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -18.11, "date": "2026-06-10", "description": "PP*GOOGLE GOOGLE ONE 4029357733", "id": 1397, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -6.7, "date": "2026-06-09", "description": "SumUp  *IL BABA  SNC D CARSOLI ITA Operazione carta ****8815 del 05.06.2026", "id": 1040, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -3.1, "date": "2026-06-09", "description": "BUFFET ROMA TIBURTINA ROMA Operazione Carta 93641892 del 08.06.2026 12:34", "id": 1039, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -5.0, "date": "2026-06-04", "description": "PARKING COMUNE ROSETO ROSETO DEGLI ITA Operazione carta ****8815 del 01.06.2026", "id": 1045, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-06-03", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1401, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -13.25, "date": "2026-06-03", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 30.05.2026", "id": 1048, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -3.0, "date": "2026-06-03", "description": "FRATELLI DIOLETTA SRLS LAQUILA ITA Operazione carta ****8815 del 30.05.2026", "id": 1047, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -141.61, "date": "2026-06-01", "description": "ORIGINAL MARINES SPA L\u0027AQUILA AQ Operazione Carta 93641892 del 30.05.2026 12:26", "id": 1051, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -4.24, "date": "2026-05-26", "description": "PAYPAL *NOW B4196 CINE 35314369001", "id": 1405, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -19.99, "date": "2026-05-26", "description": "PAYPAL *NOW 4924B SPOR 35314369001", "id": 1404, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -3.75, "date": "2026-05-26", "description": "PAYPAL *NOW CA8C1 PASS 35314369001", "id": 1403, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-05-25", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1407, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -60.0, "date": "2026-05-25", "description": "PAYPAL *SPARTOO SA 0476095929", "id": 1406, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -18.31, "date": "2026-05-25", "description": "L\u0027ANGOLO DEI BUONGUSTA L\u0027AQUILA Operazione Carta 93641892 del 23.05.2026 09:39", "id": 1058, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -5.0, "date": "2026-05-19", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 16.05.2026", "id": 1061, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-05-18", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1410, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -11.73, "date": "2026-05-18", "description": "TIGRE L\u0027AQUILA Operazione Carta 93641892 del 16.05.2026 18:07", "id": 1064, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -30.0, "date": "2026-05-15", "description": "ADDEBITO SDD FONDAZIONE TELETHON       N: 1141148842/68 ID:L33184D000000896434085         XID 0553386, 21863821, Donazione(30)                                                      DEB: DI PAOLO LEOPOLDO 1141148842", "id": 1066, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -22.99, "date": "2026-05-12", "description": "AMZN Mktp IT 5 rue plaetis LUXEMBOURG", "id": 1412, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-05-11", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1413, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -17.77, "date": "2026-05-10", "description": "PP*GOOGLE GOOGLE ONE 4029357733", "id": 1414, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -11.4, "date": "2026-05-06", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 04.05.2026", "id": 1071, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -280.0, "date": "2026-05-05", "description": "METROQUADRO S.N.C CAGNANO AMITE ITA Operazione carta ****8815 del 30.04.2026", "id": 1072, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -6.4, "date": "2026-05-04", "description": "SumUp  *IL BABA  SNC D CARSOLI ITA Operazione carta ****8815 del 29.04.2026", "id": 1078, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -8.2, "date": "2026-05-04", "description": "CISALFA SPORT SPA ROMA RM Operazione Carta 93641892 del 02.05.2026 13:42", "id": 1077, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -100.0, "date": "2026-04-27", "description": "Prelievo atm c/o:CARSOLI Operazione carta 93641892 del 24.04.2026 08.05", "id": 1084, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -3.75, "date": "2026-04-26", "description": "PAYPAL *NOW 6415B PASS 35314369001", "id": 1422, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -4.24, "date": "2026-04-26", "description": "PAYPAL *NOW 30D7B CINE 35314369001", "id": 1421, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -19.99, "date": "2026-04-26", "description": "PAYPAL *NOW 1576D SPOR 35314369001", "id": 1420, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -27.99, "date": "2026-04-23", "description": "AMZN Mktp IT 5 rue plaetis LUXEMBOURG", "id": 1425, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-04-23", "description": "PAYPAL * GEDIMPIANTI 0863509405", "id": 1424, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -140.0, "date": "2026-04-22", "description": "ATTITUDE STORE SRLS L\u0027AQUILA AQ Operazione Carta 93641892 del 21.04.2026 18:18", "id": 1090, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -3.8, "date": "2026-04-22", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 20.04.2026", "id": 1089, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -200.0, "date": "2026-04-17", "description": "DISPOSIZIONE BONIFICO ISTANTANEO a favore di Nunzia Macera Mascitelli EUR  200,00  Asilo nidoComm.bonifico : 0,12 + Comm. di maggiorazione : 0,00 EUR Num. Bonifico 261076064199699-644080240470IT05387-RIF. 26107/9199702", "id": 1095, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -0.12, "date": "2026-04-17", "description": "COMM. BON. ISTANTANEO a favore di Nunzia Macera Mascitelli EUR  200,00  Asilo nidoComm.bonifico : 0,12 + Comm. di maggiorazione : 0,00 EUR Num. Bonifico 261076064199699-644080240470IT05387-RIF. 26107/9199702", "id": 1094, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -40.0, "date": "2026-04-17", "description": "TECNOGOMME DI PULSONI AN CARSOLI Operazione Carta 93641892 del 16.04.2026 12:41", "id": 1093, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-04-16", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1426, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -63.9, "date": "2026-04-15", "description": "PAYPAL *PAB SRL 0432644279", "id": 1427, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -30.0, "date": "2026-04-15", "description": "ADDEBITO SDD FONDAZIONE TELETHON       N: 1107920574/20 ID:L33184D000000896434085         XID 0553386, 21685683, Donazione(30)                                                      DEB: DI PAOLO LEOPOLDO 1107920574", "id": 1098, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -8.2, "date": "2026-04-14", "description": "SumUp  *IL BABA  SNC D CARSOLI ITA Operazione carta ****8815 del 10.04.2026", "id": 1099, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -1000.0, "date": "2026-04-13", "description": "DISPOSIZIONE BONIFICO ISTANTANEO a favore di Giuliani Berardino EUR  1.000,00  BiciclettaComm.bonifico : 0,12 + Comm. di maggiorazione : 0,00 EUR Num. Bonifico 261036060549052-644080240470IT05387-RIF. 26103/6549055", "id": 1101, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -0.12, "date": "2026-04-13", "description": "COMM. BON. ISTANTANEO a favore di Giuliani Berardino EUR  1.000,00  BiciclettaComm.bonifico : 0,12 + Comm. di maggiorazione : 0,00 EUR Num. Bonifico 261036060549052-644080240470IT05387-RIF. 26103/6549055", "id": 1100, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -17.97, "date": "2026-04-10", "description": "PP*GOOGLE GOOGLE ONE 4029357733", "id": 1430, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-04-10", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1429, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -97.38, "date": "2026-04-10", "description": "BEYFIN SPA L\u0027AQUILA ITA Operazione carta ****8815 del 08.04.2026", "id": 1102, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-04-09", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1432, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -67.94, "date": "2026-04-09", "description": "AMZN Mktp IT 5 rue plaetis LUXEMBOURG", "id": 1431, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -3.05, "date": "2026-04-08", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 03.04.2026", "id": 1106, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -10.71, "date": "2026-04-07", "description": "COMPETENZE SPESE ED ONERI", "id": 1114, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -130.1, "date": "2026-04-07", "description": "ORIGINAL MARINES SPA L\u0027AQUILA AQ Operazione Carta 93641892 del 04.04.2026 17:34", "id": 1113, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -19.41, "date": "2026-04-07", "description": "MAGAZZINI GABRIELLI SPA L\u0027AQUILA AQ Operazione Carta 93641892 del 03.04.2026 17:55", "id": 1112, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -30.0, "date": "2026-04-07", "description": "DI GIANNATALE AURELIO L\u0027AQUILA Operazione Carta 93641892 del 03.04.2026 11:09", "id": 1111, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -7.07, "date": "2026-04-07", "description": "TOYS L\u0027AQUILA Operazione Carta 93641892 del 04.04.2026 18:29", "id": 1110, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-03-31", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1437, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -29.0, "date": "2026-03-30", "description": "SumUp  *Fenice srl Agrate Brianz ITA Operazione carta ****8815 del 26.03.2026", "id": 1122, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -3.0, "date": "2026-03-27", "description": "SumUp  *BREAK Lounge B L AQUILA ITA Operazione carta ****8815 del 25.03.2026", "id": 1123, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -3.75, "date": "2026-03-26", "description": "PAYPAL *NOW A1771 PASS 35314369001", "id": 1441, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -4.24, "date": "2026-03-26", "description": "PAYPAL *NOW X5943 CINE 35314369001", "id": 1440, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -19.99, "date": "2026-03-26", "description": "PAYPAL *NOW 59F2A SPOR 35314369001", "id": 1439, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -100.0, "date": "2026-03-24", "description": "Sum*QUASIL SRL SEMPLIF L\u0027AQUILA ITA Operazione carta ****8815 del 21.03.2026", "id": 1126, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -4.9, "date": "2026-03-24", "description": "SumUp  *Peppinella di L Aquila ITA Operazione carta ****8815 del 21.03.2026", "id": 1125, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -13.91, "date": "2026-03-23", "description": "LANGOLO DEL BUONGUSTAIO L\u0027AQUILA AQ Operazione Carta 93641892 del 21.03.2026 12:01", "id": 1127, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-03-19", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1443, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -47.5, "date": "2026-03-18", "description": "AMZN Mktp IT 5 rue plaetis LUXEMBOURG", "id": 1444, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -59.5, "date": "2026-03-16", "description": "PAYPAL *SPARTOO SA 0476095929", "id": 1445, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -16.81, "date": "2026-03-16", "description": "LANGOLO DEL BUONGUSTAIO L\u0027AQUILA AQ Operazione Carta 93641892 del 14.03.2026 09:54", "id": 1131, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -2.2, "date": "2026-03-13", "description": "ASPIT TANG.MILANO EST- AGRATE ITA Operazione carta ****8815 del 11.03.2026", "id": 1134, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -8.9, "date": "2026-03-12", "description": "LA PIADINERIA ROMA ITA Operazione carta ****8815 del 10.03.2026", "id": 1135, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -18.0, "date": "2026-03-10", "description": "LA CANTINA DEL BOSS L\u0027AQUILA ITA Operazione carta ****8815 del 06.03.2026", "id": 1138, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Conto Corrente (Di)", "amount": -36.07, "date": "2026-03-10", "description": "LANGOLO DEL BUONGUSTAI LAQUILA ITA Operazione carta ****8815 del 07.03.2026", "id": 1137, "profile_name": "Leopoldo Di Paolo"}, {"account_name": "BPER Banca - Carta Prepagata (Di)", "amount": -10.0, "date": "2026-03-09", "description": "PAYPAL *GEDIMPIANTI 0863509405", "id": 1447, "profile_name": "Leopoldo Di Paolo"}];
let speedQueue = [...INITIAL_SPEED_QUEUE];
let speedCurrentIndex = 0;
let speedTotalInitial = speedQueue.length;
let speedProcessedCount = 0;

function openSpeedTriageGameModal() {
    if (speedQueue.length === 0) {
        alert("🎉 Non ci sono movimenti da categorizzare!");
        return;
    }
    speedTotalInitial = speedQueue.length + speedProcessedCount;
    if (speedCurrentIndex >= speedQueue.length) {
        speedCurrentIndex = 0;
    }
    renderSpeedTriageCard();
    document.getElementById('speedTriageGameModal').classList.add('open');
}

function closeSpeedTriageGameModal(shouldReload = false) {
    document.getElementById('speedTriageGameModal').classList.remove('open');
    if (shouldReload || speedProcessedCount > 0) {
        window.location.reload();
    }
}

function renderSpeedTriageCard(direction = 'none') {
    const activeView = document.getElementById('speedGameActiveView');
    const doneView = document.getElementById('speedGameDoneView');
    const progressBar = document.getElementById('speedGameProgressBar');
    const progressText = document.getElementById('speedGameProgressText');

    if (speedQueue.length === 0) {
        activeView.style.display = 'none';
        doneView.style.display = 'block';
        progressBar.style.width = '100%';
        progressText.innerText = '100% Completato 🎉';
        return;
    }

    if (speedCurrentIndex < 0) speedCurrentIndex = 0;
    if (speedCurrentIndex >= speedQueue.length) speedCurrentIndex = speedQueue.length - 1;

    activeView.style.display = 'block';
    doneView.style.display = 'none';

    const currentItem = speedQueue[speedCurrentIndex];
    const totalRemaining = speedQueue.length;
    const currentNum = speedCurrentIndex + 1;
    const pct = Math.round((speedProcessedCount / (speedTotalInitial || 1)) * 100);

    progressBar.style.width = `${Math.min(100, pct)}%`;
    progressText.innerText = `${currentNum} di ${totalRemaining} (${speedProcessedCount} categorizzati)`;

    document.getElementById('speedGameAccountBadge').innerText = `${currentItem.account_name || 'Conto'}${currentItem.profile_name ? ' • ' + currentItem.profile_name : ''}`;
    document.getElementById('speedGameDateBadge').innerText = currentItem.date;
    document.getElementById('speedGameDesc').innerText = currentItem.description;

    const amtEl = document.getElementById('speedGameAmount');
    amtEl.innerText = formatEurJs(currentItem.amount, true);
    amtEl.style.color = (currentItem.amount > 0) ? 'var(--accent-success)' : '#f87171';

    // Update Nav Buttons State (disable if at boundary)
    const isFirst = (speedCurrentIndex === 0);
    const isLast = (speedCurrentIndex >= speedQueue.length - 1);

    const prevCard = document.getElementById('btnSpeedPrevCard');
    const nextCard = document.getElementById('btnSpeedNextCard');
    const prevBottom = document.getElementById('btnSpeedPrevBottom');
    const nextBottom = document.getElementById('btnSpeedNextBottom');

    if (prevCard) prevCard.disabled = isFirst;
    if (nextCard) nextCard.disabled = isLast;
    if (prevBottom) prevBottom.disabled = isFirst;
    if (nextBottom) nextBottom.disabled = isLast;

    // Reset animation on card with directional feel
    const card = document.getElementById('speedGameCard');
    if (card) {
        card.style.transform = (direction === 'next') ? 'translateX(10px) scale(0.97)' : (direction === 'prev' ? 'translateX(-10px) scale(0.97)' : 'scale(0.96)');
        card.style.opacity = '0.7';
        setTimeout(() => {
            card.style.transform = 'none';
            card.style.opacity = '1';
        }, 50);
    }
}

function speedTriagePrev() {
    if (speedCurrentIndex > 0) {
        speedCurrentIndex--;
        renderSpeedTriageCard('prev');
    }
}

function speedTriageNext() {
    if (speedCurrentIndex < speedQueue.length - 1) {
        speedCurrentIndex++;
        renderSpeedTriageCard('next');
    }
}

async function speedTriageChoose(categoryName) {
    if (speedQueue.length === 0) return;
    const currentItem = speedQueue[speedCurrentIndex];
    if (!currentItem) return;

    // Remove from queue at current index
    speedQueue.splice(speedCurrentIndex, 1);
    speedProcessedCount++;

    // Smart default tags for fast triage
    let smartTags = [];
    let subCat = '';
    if (categoryName === 'Salute & Benessere') {
        smartTags.push('#detraibile_730');
        subCat = 'Farmacia & Medicinali';
    } else if (categoryName === 'Giroconti & Trasferimenti') {
        smartTags.push('#giroconto');
        subCat = 'Giroconto Interno';
    } else if (categoryName === 'Entrate & Stipendi') {
        smartTags.push('#stipendio');
        subCat = 'Stipendio';
    }
    const tagsStr = smartTags.join(' ');

    // Optimistic UI update in the underlying table row
    updateTxRowOptimistically(currentItem.id, categoryName, subCat, tagsStr);

    // Flash green on card before next
    const card = document.getElementById('speedGameCard');
    if (card) {
        card.style.borderColor = 'var(--accent-success)';
        card.style.boxShadow = '0 0 20px rgba(16, 185, 129, 0.4)';
    }

    // Fire AJAX in background with learn_rule = true
    try {
        fetch('/transactions/quick-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tx_id: currentItem.id,
                category: categoryName,
                sub_category: subCat,
                tags: tagsStr,
                learn_rule: true
            })
        }).then(r => r.json()).then(res => {
            if (res.success && res.pattern) {
                // If rule learned, also remove any matching items from speedQueue!
                const patLower = res.pattern.toLowerCase();
                const matchedQueue = speedQueue.filter(qItem => (qItem.description || '').toLowerCase().includes(patLower));
                matchedQueue.forEach(qItem => {
                    updateTxRowOptimistically(qItem.id, categoryName, subCat, tagsStr);
                    speedProcessedCount++;
                });
                speedQueue = speedQueue.filter(qItem => !(qItem.description || '').toLowerCase().includes(patLower));
                if (speedCurrentIndex >= speedQueue.length) {
                    speedCurrentIndex = Math.max(0, speedQueue.length - 1);
                }
                renderSpeedTriageCard();
            }
        });
    } catch (e) {
        console.error("Speed triage error:", e);
    }

    // Keep speedCurrentIndex within bounds
    if (speedCurrentIndex >= speedQueue.length) {
        speedCurrentIndex = Math.max(0, speedQueue.length - 1);
    }

    setTimeout(() => {
        if (card) {
            card.style.borderColor = 'rgba(59, 130, 246, 0.4)';
            card.style.boxShadow = '0 15px 35px rgba(0, 0, 0, 0.5)';
        }
        renderSpeedTriageCard('next');
    }, 180);
}

function speedTriageOpenFullEdit() {
    if (speedQueue.length === 0) return;
    const currentItem = speedQueue[speedCurrentIndex];
    if (!currentItem) return;
    closeSpeedTriageGameModal();
    openEditTxModal(currentItem.id, 'Altro', '', '', currentItem.description);
}

// Keyboard shortcuts for Speed Triage (ArrowLeft / ArrowRight)
document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('speedTriageGameModal');
    if (modal && modal.classList.contains('open')) {
        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            speedTriagePrev();
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            speedTriageNext();
        } else if (e.key === 'Escape') {
            closeSpeedTriageGameModal();
        }
    }
});


function toggleDropzone() {
    const el = document.getElementById('importerDropzoneContainer');
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
    if (el.style.display === 'block') {
        el.scrollIntoView({ behavior: 'smooth' });
    }
}

// 2-Step Import Workflow: Upload & Preview
async function handleFileSelected(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    
    document.getElementById('uploadProgress').style.display = 'block';
    document.getElementById('dropzoneLabel').innerText = `Analisi: ${file.name}...`;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/transactions/preview-import', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        document.getElementById('uploadProgress').style.display = 'none';

        if (!data.success) {
            alert("Errore importazione: " + (data.error || "Impossibile leggere il file"));
            document.getElementById('dropzoneLabel').innerText = "Trascina qui il file CSV / Excel o Clicca";
            return;
        }

        // Open 3-Step Wizard Modal
        currentImportToken = data.import_token;
        currentAccountMeta = data.account_meta || {};
        currentImportData = data;
        categoryOverrides = {};
        subcategoryOverrides = {};
        tagOverrides = {};
        selectedCategoryFilter = 'ALL';
        
        openConfirmImportModal(data, file.name);

    } catch (err) {
        document.getElementById('uploadProgress').style.display = 'none';
        alert("Errore di connessione durante l'analisi del file.");
        console.error(err);
    }
}

function formatEurJs(val, showSign = false) {
    if (val === null || val === undefined || isNaN(val)) return '€ 0,00';
    const num = parseFloat(val);
    const absNum = Math.abs(num);
    const parts = absNum.toFixed(2).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    const formatted = parts.join(',');
    if (showSign) {
        if (num > 0) return `+€ ${formatted}`;
        if (num < 0) return `-€ ${formatted}`;
        return `€ ${formatted}`;
    }
    return num < 0 ? `-€ ${formatted}` : `€ ${formatted}`;
}

// ==========================================
// 3-STEP WIZARD NAVIGATION & RENDERING
// ==========================================
function goToStep(step) {
    currentStep = step;
    
    // Update Step Pills
    [1, 2, 3].forEach(i => {
        const pill = document.getElementById(`stepPill${i}`);
        const view = document.getElementById(`wizardStep${i}`);
        if (i === step) {
            pill.className = 'wizard-step-pill active';
            view.style.display = 'block';
        } else if (i < step) {
            pill.className = 'wizard-step-pill completed';
            view.style.display = 'none';
        } else {
            pill.className = 'wizard-step-pill';
            view.style.display = 'none';
        }
    });

    // Update Footer Action Buttons
    const btnBack = document.getElementById('btnWizardBack');
    const btnNext = document.getElementById('btnWizardNext');

    if (step === 1) {
        btnBack.style.display = 'none';
        btnNext.innerText = 'Avanti: Scegli Intestatario ➡️';
        btnNext.style.background = 'linear-gradient(135deg, var(--accent-primary), #2563eb)';
    } else if (step === 2) {
        btnBack.style.display = 'block';
        btnNext.innerText = 'Avanti: Controlla Categorie ➡️';
        btnNext.style.background = 'linear-gradient(135deg, var(--accent-primary), #2563eb)';
    } else if (step === 3) {
        btnBack.style.display = 'block';
        btnNext.innerText = '🚀 Salva ed Importa Tutto nel Profilo';
        btnNext.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        renderStep3Dynamic();
    }
}

function wizardNext() {
    if (currentStep === 1) {
        goToStep(2);
    } else if (currentStep === 2) {
        goToStep(3);
    } else if (currentStep === 3) {
        submitConfirmImport();
    }
}

function wizardBack() {
    if (currentStep > 1) {
        goToStep(currentStep - 1);
    }
}

function closeConfirmImportModal() {
    document.getElementById('confirmImportModal').classList.remove('open');
    currentImportToken = null;
    currentImportData = null;
    currentAccountMeta = {};
    categoryOverrides = {};
    subcategoryOverrides = {};
    tagOverrides = {};
    const dropLabel = document.getElementById('dropzoneLabel');
    if (dropLabel) dropLabel.innerText = "Trascina qui il file CSV / Excel o Clicca";
}

async function submitConfirmImport() {
    if (!currentImportToken) {
        alert("Sessione di importazione non valida o scaduta. Ricarica il file.");
        return;
    }

    const btnNext = document.getElementById('btnWizardNext');
    const originalText = btnNext.innerText;
    btnNext.disabled = true;
    btnNext.innerText = '⏳ Salvataggio in corso...';

    // 1. Gather account selection
    const isNewAccount = document.getElementById('cardChoiceNew') && document.getElementById('cardChoiceNew').classList.contains('active');
    const accountChoice = isNewAccount ? 'new' : 'existing';
    
    let accountId = null;
    let newAccountName = '';
    let newAccountType = 'CHECKING';
    let newAccountProfileId = '';

    if (isNewAccount) {
        newAccountName = (document.getElementById('wizardNewAccName').value || '').trim();
        newAccountType = document.getElementById('wizardNewAccType').value;
        newAccountProfileId = document.getElementById('wizardNewAccProfileVal').value;
    } else {
        const selectExisting = document.getElementById('wizardSelectTargetAccount');
        accountId = selectExisting ? selectExisting.value : null;
        if (!accountId) {
            alert("Seleziona il conto esistente su cui importare i movimenti (Step 2).");
            btnNext.disabled = false;
            btnNext.innerText = originalText;
            goToStep(2);
            return;
        }
    }

    // 2. Sync balance & auto-learn flags
    const syncBalanceEl = document.getElementById('wizardSyncBalanceCheck');
    const syncBalance = syncBalanceEl ? syncBalanceEl.checked : true;
    
    const learnRulesEl = document.getElementById('wizardLearnRulesCheck');
    const learnOverrides = learnRulesEl ? learnRulesEl.checked : true;

    const payload = {
        import_token: currentImportToken,
        account_choice: accountChoice,
        account_id: accountId ? parseInt(accountId) : null,
        new_account_name: newAccountName,
        new_account_type: newAccountType,
        new_account_profile_id: newAccountProfileId,
        sync_balance: syncBalance,
        category_overrides: categoryOverrides,
        subcategory_overrides: subcategoryOverrides,
        tag_overrides: tagOverrides,
        learn_overrides: learnOverrides
    };

    try {
        const response = await fetch('/transactions/confirm-import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const resData = await response.json();
        if (resData.success) {
            window.location.href = resData.redirect_url || '/transactions';
        } else {
            alert("Errore durante l'importazione: " + (resData.error || "Errore sconosciuto"));
            btnNext.disabled = false;
            btnNext.innerText = originalText;
        }
    } catch (err) {
        console.error(err);
        alert("Errore di comunicazione con il server.");
        btnNext.disabled = false;
        btnNext.innerText = originalText;
    }
}

function openConfirmImportModal(data, fileName) {
    document.getElementById('wizardFileName').innerText = fileName;
    
    // 1. Populate Step 1 Data
    const meta = data.account_meta || {};
    const bankName = meta.bank_name || 'Banca';
    const isCard = (meta.account_type === 'CARD') && !(meta.extracted_balance !== null && meta.extracted_balance !== undefined) && !(fileName && fileName.toLowerCase().includes('conto'));
    
    document.getElementById('step1BankName').innerText = bankName;
    document.getElementById('step1BankIcon').innerText = isCard ? '💳' : (bankName.includes('Poste') ? '📮' : '🏛️');
    document.getElementById('step1TypeSub').innerText = isCard ? 'Carta Prepagata / Ricaricabile' : 'Conto Corrente Bancario';
    
    const typeBadge = document.getElementById('step1TypeBadge');
    if (isCard) {
        typeBadge.innerText = '💳 Carta Prepagata';
        typeBadge.style.background = 'rgba(245, 158, 11, 0.2)';
        typeBadge.style.color = 'var(--accent-warning)';
        typeBadge.style.borderColor = 'rgba(245, 158, 11, 0.4)';
    } else {
        typeBadge.innerText = '🏛️ Conto Corrente';
        typeBadge.style.background = 'rgba(16, 185, 129, 0.15)';
        typeBadge.style.color = 'var(--accent-success)';
        typeBadge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    }

    document.getElementById('step1Holder').innerText = meta.holder_name || 'Titolare del conto';
    document.getElementById('step1Iban').innerText = meta.iban || meta.card_pan || meta.account_number || 'Non specificato';
    
    if (meta.extracted_balance !== null && meta.extracted_balance !== undefined) {
        const fBal = formatEurJs(meta.extracted_balance);
        document.getElementById('step1Balance').innerText = fBal;
        document.getElementById('step1BalanceBox').style.display = 'flex';
        document.getElementById('wizardSyncBalanceLabel').innerText = `Aggiorna automaticamente il saldo di questo conto a ${fBal} (certificato dalla banca).`;
    } else {
        document.getElementById('step1BalanceBox').style.display = 'none';
        document.getElementById('wizardSyncBalanceLabel').innerText = "Calcola il saldo sommando le entrate e le uscite dell'estratto conto.";
    }

    document.getElementById('step1Count').innerText = `${data.total_transactions} transazioni`;
    document.getElementById('step1Income').innerText = formatEurJs(data.total_income, true);
    document.getElementById('step1Expenses').innerText = formatEurJs(-data.total_expenses);

    // 2. Populate Step 2 (Profile Selection Cards)
    setupProfileCards(meta, fileName, isCard);

    // 3. Reset to Step 1 & Show Modal
    goToStep(1);
    document.getElementById('confirmImportModal').classList.add('open');
}

function setupProfileCards(meta, fileName, isCard) {
    const cardsContainer = document.getElementById('step2ProfileCards');
    cardsContainer.innerHTML = '';
    
    const detectedHolder = meta.holder_name ? meta.holder_name.trim() : '';
    let selectedProfileVal = "";
    let selectedProfileLabel = "Titolare";

    // 1. Primary Profile (Leopoldo)
    const primaryP = ALL_PROFILES.find(p => p.is_primary) || ALL_PROFILES[0];
    if (primaryP) {
        selectedProfileVal = String(primaryP.id);
        selectedProfileLabel = primaryP.name;
        
        const c1 = document.createElement('div');
        c1.className = 'profile-select-card active';
        c1.id = `profCard_${primaryP.id}`;
        c1.onclick = () => selectProfileCard(String(primaryP.id), primaryP.name, c1);
        c1.innerHTML = `
            <span style="font-size: 1.5rem;">👤</span>
            <div>
                <strong style="color: #fff; font-size: 0.85rem; display: block;">${primaryP.name}</strong>
                <small style="color: var(--accent-primary); font-size: 0.7rem; font-weight: 600;">Titolare Principale</small>
            </div>
        `;
        cardsContainer.appendChild(c1);
    }

    // 2. Detected Partner / Other Member Card (e.g. Macera Mascitelli Nunzia)
    let partnerCreated = false;
    if (detectedHolder) {
        const detectedWords = detectedHolder.toLowerCase().split(/\s+/).filter(w => w.length > 2);
        const existingPartner = ALL_PROFILES.find(p => !p.is_primary && detectedWords.some(w => p.name.toLowerCase().includes(w)));
        
        if (existingPartner) {
            const cp = document.createElement('div');
            cp.className = 'profile-select-card';
            cp.id = `profCard_${existingPartner.id}`;
            cp.onclick = () => selectProfileCard(String(existingPartner.id), existingPartner.name, cp);
            cp.innerHTML = `
                <span style="font-size: 1.5rem;">👩</span>
                <div>
                    <strong style="color: #fff; font-size: 0.85rem; display: block;">${existingPartner.name}</strong>
                    <small style="color: var(--text-muted); font-size: 0.7rem;">${existingPartner.role_title || 'Partner'}</small>
                </div>
            `;
            cardsContainer.appendChild(cp);
            partnerCreated = true;
            
            // Auto-select partner if detected name matched
            selectProfileCard(String(existingPartner.id), existingPartner.name, cp);
        } else if (!primaryP || !detectedWords.some(w => primaryP.name.toLowerCase().includes(w))) {
            // New member candidate
            const newVal = `__NEW_MEMBER__:${detectedHolder}`;
            const cp = document.createElement('div');
            cp.className = 'profile-select-card';
            cp.id = 'profCard_newMember';
            cp.onclick = () => selectProfileCard(newVal, `${detectedHolder} (Nuovo Partner)`, cp);
            cp.innerHTML = `
                <span style="font-size: 1.5rem;">➕</span>
                <div>
                    <strong style="color: #38bdf8; font-size: 0.85rem; display: block;">${detectedHolder}</strong>
                    <small style="color: #818cf8; font-size: 0.7rem; font-weight: 600;">Crea Nuovo Membro (Partner)</small>
                </div>
            `;
            cardsContainer.appendChild(cp);
            partnerCreated = true;
            
            // Auto-select detected partner
            selectProfileCard(newVal, `${detectedHolder} (Nuovo Partner)`, cp);
        }
    }

    // 3. Shared Family Account Card
    const cFam = document.createElement('div');
    cFam.className = 'profile-select-card';
    cFam.id = 'profCard_fam';
    cFam.onclick = () => selectProfileCard('', 'Conto Comune Famiglia', cFam);
    cFam.innerHTML = `
        <span style="font-size: 1.5rem;">👨‍👩‍👧‍👦</span>
        <div>
            <strong style="color: #fff; font-size: 0.85rem; display: block;">Conto Comune</strong>
            <small style="color: var(--text-muted); font-size: 0.7rem;">Cointestato Famiglia</small>
        </div>
    `;
    cardsContainer.appendChild(cFam);

    // Prepopulate New Account fields
    const holderFirst = detectedHolder ? detectedHolder.split(' ')[0] : '';
    const typeLabel = isCard ? 'Carta Prepagata' : 'Conto Corrente';
    const suggestedName = `${meta.bank_name || 'Banca'} - ${typeLabel} ${holderFirst ? '(' + holderFirst + ')' : ''}`.trim();
    
    document.getElementById('wizardNewAccName').value = suggestedName;
    document.getElementById('wizardNewAccType').value = isCard ? 'CARD' : (meta.account_type || 'CHECKING');

    // Auto-match or choose account mode
    const selectExisting = document.getElementById('wizardSelectTargetAccount');
    if (currentImportData.matching_account_id) {
        selectExisting.value = currentImportData.matching_account_id;
        setAccountChoice('existing');
    } else {
        setAccountChoice('new');
    }
}

function selectProfileCard(val, label, elem) {
    document.querySelectorAll('.profile-select-card').forEach(c => c.classList.remove('active'));
    elem.classList.add('active');
    document.getElementById('wizardNewAccProfileVal').value = val;
    document.getElementById('wizardSelectedProfileLabel').value = label;
}

function setAccountChoice(choice) {
    const cardNew = document.getElementById('cardChoiceNew');
    const cardExt = document.getElementById('cardChoiceExisting');
    const secNew = document.getElementById('step2NewAccountSection');
    const secExt = document.getElementById('step2ExistingAccountSection');

    if (choice === 'new') {
        cardNew.classList.add('active');
        cardExt.classList.remove('active');
        secNew.style.display = 'block';
        secExt.style.display = 'none';
    } else {
        cardExt.classList.add('active');
        cardNew.classList.remove('active');
        secNew.style.display = 'none';
        secExt.style.display = 'block';
    }
}

let selectedCategoryFilter = 'ALL';
let subcategoryOverrides = {};
let tagOverrides = {};

// ==========================================
// STEP 3: DYNAMIC CATEGORY REVIEW & EDITING
// ==========================================
function renderStep3Dynamic() {
    if (!currentImportData) return;

    const txList = currentImportData.sample_transactions || [];
    
    // 1. Calculate Grouped Totals for all categories
    const catMap = {};
    let totalAllCount = 0;
    let totalAllSum = 0.0;

    txList.forEach((tx, idx) => {
        const cat = categoryOverrides[idx] || tx.category || 'Altro';
        if (!catMap[cat]) {
            const meta = MACRO_CATEGORIES_OBJ[cat] || { icon: '🏷️', color: '#64748b' };
            catMap[cat] = {
                name: cat,
                icon: meta.icon || '🏷️',
                color: meta.color || '#64748b',
                count: 0,
                total: 0.0
            };
        }
        catMap[cat].count += 1;
        catMap[cat].total += Math.abs(tx.amount || 0);
        totalAllCount += 1;
        totalAllSum += Math.abs(tx.amount || 0);
    });

    // 2. Render Clickable Category Filter Cards at Top
    const breakdownGrid = document.getElementById('step3BreakdownGrid');
    breakdownGrid.innerHTML = '';
    
    // "All Categories" Filter Card
    const isAllActive = (selectedCategoryFilter === 'ALL');
    const allCard = document.createElement('div');
    allCard.className = `wizard-choice-card ${isAllActive ? 'active' : ''}`;
    allCard.style.cssText = `cursor: pointer; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border-radius: 8px; border: 1.5px solid ${isAllActive ? 'var(--accent-primary)' : 'var(--border-color)'}; background: ${isAllActive ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255,255,255,0.03)'}; transition: all 0.2s ease;`;
    allCard.onclick = () => { selectedCategoryFilter = 'ALL'; renderStep3Dynamic(); };
    allCard.innerHTML = `
        <span style="font-size: 1.3rem;">✨</span>
        <div>
            <strong style="color: #fff; font-size: 0.78rem; display: block;">Tutti i Movimenti</strong>
            <span style="font-size: 0.7rem; color: #94a3b8; font-weight: 600;">${totalAllCount} mov. (${formatEurJs(totalAllSum)})</span>
        </div>
    `;
    breakdownGrid.appendChild(allCard);

    // Specific Category Cards
    Object.values(catMap).sort((a, b) => b.count - a.count).forEach(item => {
        const isCatActive = (selectedCategoryFilter === item.name);
        const card = document.createElement('div');
        card.className = `wizard-choice-card ${isCatActive ? 'active' : ''}`;
        card.style.cssText = `cursor: pointer; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border-radius: 8px; border: 1.5px solid ${isCatActive ? item.color : item.color + '40'}; background: ${isCatActive ? item.color + '30' : item.color + '12'}; box-shadow: ${isCatActive ? '0 0 10px ' + item.color + '40' : 'none'}; transition: all 0.2s ease;`;
        card.onclick = () => { 
            selectedCategoryFilter = (selectedCategoryFilter === item.name) ? 'ALL' : item.name; 
            renderStep3Dynamic(); 
        };
        card.innerHTML = `
            <span style="font-size: 1.3rem;">${item.icon}</span>
            <div style="overflow: hidden;">
                <strong style="color: #fff; font-size: 0.78rem; display: block; white-space: nowrap; text-overflow: ellipsis;">${item.name}</strong>
                <span style="font-size: 0.7rem; color: ${item.color}; font-weight: 700;">${item.count} mov. (${formatEurJs(item.total)})</span>
            </div>
        `;
        breakdownGrid.appendChild(card);
    });

    // 3. Filter and Render Transactions List
    const txContainer = document.getElementById('step3TxList');
    txContainer.innerHTML = '';
    
    const filteredIndexes = [];
    txList.forEach((tx, idx) => {
        const cat = categoryOverrides[idx] || tx.category || 'Altro';
        if (selectedCategoryFilter === 'ALL' || cat === selectedCategoryFilter) {
            filteredIndexes.push(idx);
        }
    });

    const noticeEl = document.getElementById('step3TxCountNotice');
    if (selectedCategoryFilter === 'ALL') {
        noticeEl.innerHTML = `Mostrati <strong>tutti i ${filteredIndexes.length} movimenti</strong>`;
    } else {
        noticeEl.innerHTML = `Filtro attivo: <strong>${selectedCategoryFilter}</strong> (${filteredIndexes.length} movimenti) • <a href="javascript:void(0)" onclick="selectedCategoryFilter='ALL'; renderStep3Dynamic();" style="color: var(--accent-primary); text-decoration: underline;">Mostra Tutti</a>`;
    }

    if (filteredIndexes.length === 0) {
        txContainer.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-muted); font-size: 0.8rem;">Nessun movimento trovato per questa categoria.</div>';
        return;
    }

    filteredIndexes.forEach(idx => {
        const tx = txList[idx];
        const currentCat = categoryOverrides[idx] || tx.category || 'Altro';
        const currentSubCat = subcategoryOverrides[idx] !== undefined ? subcategoryOverrides[idx] : (tx.sub_category || '');
        const currentTags = tagOverrides[idx] !== undefined ? tagOverrides[idx] : (tx.tags || '');

        const catMeta = MACRO_CATEGORIES_OBJ[currentCat] || { icon: '🏷️', color: '#64748b', subcategories: [] };
        
        const row = document.createElement('div');
        row.style.cssText = 'display: flex; flex-direction: column; background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 8px; padding: 8px 12px; gap: 6px;';
        
        // Build Macro-Category Dropdown Options
        let optionsHtml = '';
        for (const [cName, cMeta] of Object.entries(MACRO_CATEGORIES_OBJ)) {
            const isSel = (cName === currentCat) ? 'selected' : '';
            optionsHtml += `<option value="${cName}" ${isSel}>${cMeta.icon} ${cName}</option>`;
        }

        // Build Curated Smart Tag Badges for this category (Clean, no raw #)
        let tagChipsHtml = '';
        const smartTags = (CATEGORY_SMART_TAGS_OBJ && CATEGORY_SMART_TAGS_OBJ[currentCat]) ? CATEGORY_SMART_TAGS_OBJ[currentCat] : [];
        const activeTagCodes = currentTags.split(/\s+/).filter(Boolean);

        // 1. Render Preset Smart Tags
        smartTags.forEach(st => {
            const isActive = activeTagCodes.includes(st.code);
            const isFiscal = st.is_fiscal;
            
            let badgeBg = isActive ? (isFiscal ? 'rgba(236, 72, 153, 0.3)' : catMeta.color + '35') : 'rgba(255, 255, 255, 0.05)';
            let badgeBorder = isActive ? (isFiscal ? '#ec4899' : catMeta.color) : 'rgba(255, 255, 255, 0.12)';
            let badgeColor = isActive ? (isFiscal ? '#f472b6' : '#fff') : 'var(--text-muted)';
            let badgeGlow = isActive ? `box-shadow: 0 0 6px ${isFiscal ? 'rgba(236,72,153,0.4)' : catMeta.color + '40'};` : '';

            tagChipsHtml += `
                <span onclick="toggleSmartTagChip(${idx}, '${st.code}', '${(st.subcat || '').replace("'", "\\'")}')" 
                      title="${st.label}"
                      style="cursor: pointer; font-size: 0.68rem; padding: 2.5px 8px; border-radius: 12px; font-weight: ${isActive ? '700' : '500'}; border: 1px solid ${badgeBorder}; background: ${badgeBg}; color: ${badgeColor}; ${badgeGlow} transition: all 0.15s ease; display: inline-flex; align-items: center; gap: 4px; user-select: none;">
                    ${st.icon} ${st.label} ${isActive ? '✓' : ''}
                </span>
            `;
        });

        // 2. Render Any Custom Tags attached to this transaction
        const knownPresetCodes = smartTags.map(st => st.code);
        activeTagCodes.forEach(code => {
            if (!knownPresetCodes.includes(code)) {
                const cleanLabel = code.replace('#', '').replace(/_/g, ' ');
                tagChipsHtml += `
                    <span onclick="toggleSmartTagChip(${idx}, '${code}', null)" 
                          title="Clicca per rimuovere tag personalizzato"
                          style="cursor: pointer; font-size: 0.68rem; padding: 2.5px 8px; border-radius: 12px; font-weight: 600; border: 1px solid #38bdf8; background: rgba(56, 189, 248, 0.2); color: #38bdf8; display: inline-flex; align-items: center; gap: 4px; user-select: none;">
                        🏷️ ${cleanLabel} ✕
                    </span>
                `;
            }
        });

        // 3. Add Custom Tag Chip Button
        tagChipsHtml += `
            <span onclick="promptCustomTag(${idx})" 
                  title="Aggiungi etichetta personalizzata"
                  style="cursor: pointer; font-size: 0.68rem; padding: 2.5px 8px; border-radius: 12px; font-weight: 600; border: 1px dashed rgba(255,255,255,0.25); background: transparent; color: var(--text-muted); display: inline-flex; align-items: center; gap: 3px; transition: all 0.15s ease;"
                  onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.color='#fff';"
                  onmouseout="this.style.borderColor='rgba(255,255,255,0.25)'; this.style.color='var(--text-muted)';">
                ➕ Altro Tag
            </span>
        `;

        row.innerHTML = `
            <!-- Top Line: Date, Description, Amount -->
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
                    <span style="color: var(--text-muted); font-size: 0.72rem; white-space: nowrap; font-family: monospace;">${tx.date}</span>
                    <strong style="color: #fff; font-size: 0.82rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${tx.description}">${tx.description}</strong>
                </div>
                <strong style="font-size: 0.9rem; color: ${tx.amount > 0 ? 'var(--accent-success)' : '#f87171'}; flex-shrink: 0;">
                    ${formatEurJs(tx.amount, true)}
                </strong>
            </div>

            <!-- Bottom Line: Macro-Category Dropdown & Quick Tag Pills -->
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 6px; border-top: 1px dashed rgba(255,255,255,0.06); padding-top: 6px;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 0.7rem; color: var(--text-muted);">Categoria:</span>
                    <select onchange="onCategoryChangeInPreview(${idx}, this)" class="form-control" style="background: #1e293b; color: #fff; font-size: 0.75rem; padding: 3px 6px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.15); max-width: 175px;">
                        ${optionsHtml}
                    </select>
                </div>
                
                <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap; justify-content: flex-end;">
                    <span style="font-size: 0.68rem; color: var(--text-muted);">Tag:</span>
                    ${tagChipsHtml}
                </div>
            </div>
        `;
        txContainer.appendChild(row);
    });
}

function onCategoryChangeInPreview(idx, selectEl) {
    const newCat = selectEl.value;
    categoryOverrides[idx] = newCat;
    subcategoryOverrides[idx] = "";
    
    // Auto-select smart default tags for special categories
    if (newCat === 'Salute & Benessere') {
        tagOverrides[idx] = "#detraibile_730";
        subcategoryOverrides[idx] = "Farmacia & Medicinali";
    } else if (newCat === 'Risparmio & Futuro') {
        tagOverrides[idx] = "#giroconto";
        subcategoryOverrides[idx] = "Giroconto Interno";
    } else {
        tagOverrides[idx] = "";
    }
    renderStep3Dynamic();
}

function toggleSmartTagChip(idx, tagCode, defaultSubcat) {
    const currentTags = tagOverrides[idx] !== undefined ? tagOverrides[idx] : (currentImportData.sample_transactions[idx].tags || '');
    let tagsList = currentTags.split(/\s+/).filter(Boolean);
    
    if (tagsList.includes(tagCode)) {
        tagsList = tagsList.filter(t => t !== tagCode);
    } else {
        tagsList.push(tagCode);
        if (defaultSubcat) {
            subcategoryOverrides[idx] = defaultSubcat;
        }
    }
    tagOverrides[idx] = tagsList.join(' ');
    renderStep3Dynamic();
}

let customTagTargetIdx = null;

function promptCustomTag(idx) {
    customTagTargetIdx = idx;
    if (currentImportData && currentImportData.sample_transactions && currentImportData.sample_transactions[idx]) {
        const tx = currentImportData.sample_transactions[idx];
        const descEl = document.getElementById('customTagTxDesc');
        if (descEl) {
            descEl.innerText = `${tx.date} • ${tx.description} (${formatEurJs(tx.amount, true)})`;
        }
    }
    const input = document.getElementById('customTagNameInput');
    if (input) input.value = '';
    const iconSelect = document.getElementById('customTagIconSelect');
    if (iconSelect) iconSelect.value = '🏷️';
    
    document.getElementById('customTagModal').classList.add('open');
    setTimeout(() => { if (input) input.focus(); }, 150);
}

function closeCustomTagModal() {
    document.getElementById('customTagModal').classList.remove('open');
    customTagTargetIdx = null;
}

function fillCustomTag(icon, label) {
    const iconSelect = document.getElementById('customTagIconSelect');
    const input = document.getElementById('customTagNameInput');
    if (iconSelect) iconSelect.value = icon;
    if (input) {
        input.value = label;
        input.focus();
    }
}

function applyCustomTagFromModal() {
    if (customTagTargetIdx === null) return;
    const input = document.getElementById('customTagNameInput');
    const label = input ? input.value.trim() : '';
    if (!label) return;

    const cleanTag = '#' + label.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 24);
    
    if (customTagTargetIdx === 'editModal') {
        if (!editModalActiveTags.includes(cleanTag)) {
            editModalActiveTags.push(cleanTag);
            document.getElementById('editTags').value = editModalActiveTags.join(' ');
            renderEditModalSmartTags();
        }
        closeCustomTagModal();
        return;
    }

    if (customTagTargetIdx === 'trayModal') {
        if (!trayActiveTags.includes(cleanTag)) {
            trayActiveTags.push(cleanTag);
            renderTraySmartTags();
        }
        closeCustomTagModal();
        return;
    }
    
    toggleSmartTagChip(customTagTargetIdx, cleanTag, null);
    closeCustomTagModal();
}

let editModalActiveTags = [];
let currentEditTxDesc = "";

function promptCustomTagForEditModal() {
    customTagTargetIdx = 'editModal';
    const descEl = document.getElementById('customTagTxDesc');
    if (descEl) {
        descEl.innerText = currentEditTxDesc ? `Movimento: "${currentEditTxDesc}"` : 'Aggiunta tag';
    }
    const input = document.getElementById('customTagNameInput');
    if (input) input.value = '';
    const iconSelect = document.getElementById('customTagIconSelect');
    if (iconSelect) iconSelect.value = '🏷️';
    
    document.getElementById('customTagModal').classList.add('open');
    setTimeout(() => { if (input) input.focus(); }, 150);
}

function promptCustomTagForTray() {
    customTagTargetIdx = 'trayModal';
    const descEl = document.getElementById('customTagTxDesc');
    if (descEl) {
        descEl.innerText = activeTrayTxDesc ? `Movimento: "${activeTrayTxDesc}"` : 'Aggiunta tag';
    }
    const input = document.getElementById('customTagNameInput');
    if (input) input.value = '';
    const iconSelect = document.getElementById('customTagIconSelect');
    if (iconSelect) iconSelect.value = '🏷️';
    
    document.getElementById('customTagModal').classList.add('open');
    setTimeout(() => { if (input) input.focus(); }, 150);
}

function openEditTxModal(id, category, subCategory, tags, desc) {
    document.getElementById('editTxForm').action = `/transactions/update/${id}`;
    currentEditTxDesc = desc;
    document.getElementById('editTxDesc').innerText = `"${desc}"`;
    document.getElementById('editCategory').value = category || 'Altro';
    document.getElementById('editSubCategory').value = subCategory || '';
    
    // Parse existing tags
    editModalActiveTags = (tags || '').split(/\s+/).filter(Boolean);
    document.getElementById('editTags').value = editModalActiveTags.join(' ');
    
    // Reset checkboxes
    document.getElementById('learnRuleCheckbox').checked = true;
    document.getElementById('setFixedCostCheckbox').checked = false;
    document.getElementById('fixedCostOptions').style.display = 'none';
    
    // Render dynamic category-aware pills
    renderEditModalSmartTags(category);
    
    document.getElementById('editTxModal').classList.add('open');
}

function onEditModalCategoryChange(newCat) {
    // Smart default tags when changing category if none set
    if (newCat === 'Salute & Benessere' && editModalActiveTags.length === 0) {
        editModalActiveTags.push('#detraibile_730');
        if (!document.getElementById('editSubCategory').value) {
            document.getElementById('editSubCategory').value = 'Farmacia & Medicinali';
        }
    } else if (newCat === 'Giroconti & Trasferimenti' && editModalActiveTags.length === 0) {
        editModalActiveTags.push('#giroconto');
        if (!document.getElementById('editSubCategory').value) {
            document.getElementById('editSubCategory').value = 'Giroconto Interno';
        }
    }
    document.getElementById('editTags').value = editModalActiveTags.join(' ');
    renderEditModalSmartTags(newCat);
}

function renderEditModalSmartTags(category) {
    const container = document.getElementById('editModalSmartTagsContainer');
    if (!container) return;
    container.innerHTML = '';
    
    const cat = category || document.getElementById('editCategory').value;
    const smartTags = (CATEGORY_SMART_TAGS_OBJ && CATEGORY_SMART_TAGS_OBJ[cat]) ? CATEGORY_SMART_TAGS_OBJ[cat] : [];
    
    if (smartTags.length === 0 && editModalActiveTags.length === 0) {
        container.innerHTML = '<span style="font-size: 0.72rem; color: var(--text-muted); font-style: italic;">Nessun tag predefinito per questa categoria. Clicca su "+ Altro Tag".</span>';
        return;
    }
    
    // 1. Render Preset Smart Tags for this category
    smartTags.forEach(st => {
        const isSelected = editModalActiveTags.includes(st.code);
        const isFiscal = st.code === '#detraibile_730';
        
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = `tag-chip ${isFiscal ? 'tag-fiscal' : ''}`;
        pill.style.cursor = 'pointer';
        pill.style.padding = '4px 9px';
        pill.style.fontSize = '0.75rem';
        pill.style.borderRadius = '16px';
        pill.style.transition = 'all 0.15s ease';
        pill.style.border = isSelected ? (isFiscal ? '1.5px solid #10b981' : '1.5px solid #38bdf8') : '1px solid rgba(255,255,255,0.12)';
        pill.style.background = isSelected ? (isFiscal ? 'rgba(16, 185, 129, 0.25)' : 'rgba(56, 189, 248, 0.25)') : 'rgba(255,255,255,0.04)';
        pill.style.color = isSelected ? (isFiscal ? '#6ee7b7' : '#7dd3fc') : '#cbd5e1';
        pill.style.fontWeight = isSelected ? '700' : '500';
        
        pill.innerHTML = `${isSelected ? '✓ ' : ''}${st.label}`;
        pill.onclick = () => toggleEditModalTag(st.code, st.default_subcat);
        container.appendChild(pill);
    });
    
    // 2. Render any custom tags attached to this tx not in category preset
    editModalActiveTags.forEach(tCode => {
        const inPreset = smartTags.some(st => st.code === tCode);
        if (!inPreset) {
            const pill = document.createElement('button');
            pill.type = 'button';
            pill.className = 'tag-chip';
            pill.style.cursor = 'pointer';
            pill.style.padding = '4px 9px';
            pill.style.fontSize = '0.75rem';
            pill.style.borderRadius = '16px';
            pill.style.border = '1.5px solid #38bdf8';
            pill.style.background = 'rgba(56, 189, 248, 0.25)';
            pill.style.color = '#7dd3fc';
            pill.style.fontWeight = '700';
            
            const cleanLabel = tCode.replace(/^#/, '').replace(/_/g, ' ');
            pill.innerHTML = `✓ 🏷️ ${cleanLabel} &times;`;
            pill.onclick = () => toggleEditModalTag(tCode);
            container.appendChild(pill);
        }
    });
}

function toggleEditModalTag(tagCode, defaultSubcat) {
    if (editModalActiveTags.includes(tagCode)) {
        editModalActiveTags = editModalActiveTags.filter(t => t !== tagCode);
    } else {
        editModalActiveTags.push(tagCode);
        if (defaultSubcat && !document.getElementById('editSubCategory').value) {
            document.getElementById('editSubCategory').value = defaultSubcat;
        }
    }
    document.getElementById('editTags').value = editModalActiveTags.join(' ');
    renderEditModalSmartTags();
}

function closeEditTxModal() {
    document.getElementById('editTxModal').classList.remove('open');
}

// Close modals when clicking outside
window.addEventListener('click', (e) => {
    ['newAccountModal', 'editTxModal', 'confirmImportModal', 'smartCategoryTrayModal', 'speedTriageGameModal', 'customTagModal', 'bulkModal'].forEach(id => {
        const modal = document.getElementById(id);
        if (modal && e.target === modal) {
            modal.classList.remove('open');
        }
    });
});

// Live Instant Search across table rows
function onLiveSearchInput(query) {
    const q = (query || '').toLowerCase().trim();
    const clearBtn = document.getElementById('clearLiveSearchBtn');
    if (clearBtn) {
        clearBtn.style.display = q.length > 0 ? 'block' : 'none';
    }
    
    const rows = document.querySelectorAll('.tx-item');
    let visibleCount = 0;
    
    rows.forEach(row => {
        if (!q) {
            row.style.display = 'flex';
            visibleCount++;
            return;
        }
        
        const rowText = row.innerText.toLowerCase();
        const descEl = row.querySelector('div[title]');
        const descText = descEl ? (descEl.getAttribute('title') || '').toLowerCase() : '';
        const catBtn = row.querySelector('.unified-cat-btn');
        const catText = catBtn ? catBtn.innerText.toLowerCase() : '';
        
        const matches = rowText.includes(q) || descText.includes(q) || catText.includes(q);
        if (matches) {
            row.style.display = 'flex';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    // Update count display badge
    const countDisplay = document.getElementById('txCountDisplay');
    if (countDisplay) {
        if (q) {
            countDisplay.innerHTML = `<span style="color: var(--accent-primary); font-weight: 800;">${visibleCount}</span> di ${rows.length} movimenti trovati`;
        } else {
            countDisplay.innerText = `${rows.length} movimenti mostrati`;
        }
    }
    
    // Empty state handling
    let emptyEl = document.getElementById('liveSearchEmptyState');
    if (visibleCount === 0 && rows.length > 0) {
        if (!emptyEl) {
            emptyEl = document.createElement('div');
            emptyEl.id = 'liveSearchEmptyState';
            emptyEl.style.cssText = 'text-align: center; padding: 30px 10px; color: var(--text-muted);';
            emptyEl.innerHTML = `
                <span style="font-size: 2rem; display: block; margin-bottom: 6px;">🔍</span>
                <strong style="color: #fff; font-size: 0.95rem; display: block; margin-bottom: 2px;">Nessun risultato per "${query}"</strong>
                <p style="font-size: 0.78rem; margin: 0;">Prova con un altro termine o cancella la ricerca.</p>
            `;
            const list = document.querySelector('.tx-list');
            if (list) list.appendChild(emptyEl);
        } else {
            emptyEl.style.display = 'block';
            const s = emptyEl.querySelector('strong');
            if (s) s.innerText = `Nessun risultato per "${query}"`;
        }
    } else if (emptyEl) {
        emptyEl.style.display = 'none';
    }
}

function clearLiveSearch() {
    const input = document.getElementById('liveTxSearchInput');
    if (input) {
        input.value = '';
        input.focus();
    }
    onLiveSearchInput('');
}

// Initialize page handlers
document.addEventListener('DOMContentLoaded', () => {
    // If initial query exists in search input, trigger live filter
    const initialInput = document.getElementById('liveTxSearchInput');
    if (initialInput && initialInput.value) {
        onLiveSearchInput(initialInput.value);
    }
});
