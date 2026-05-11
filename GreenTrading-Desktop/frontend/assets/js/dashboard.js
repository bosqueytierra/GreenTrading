console.log("DASHBOARD_JS_VERSION: FASE4_MULTI_STRATEGY_V2");

/**
 * GreenTrading Desktop - Dashboard JavaScript
 * FASE 4 v2: Multi-strategy UI (SMC_M15_PRO + SMC_H1_M15_PRO + SMC_MICRO_IMPULSO + SMC_MICRO_IMPULSO_FILTRADO_M15)
 *
 * Arquitectura:
 *  - Cache independiente por estrategia
 *  - Auto-refresh independiente por endpoint
 *  - Cambio instantáneo entre tabs (sin esperar fetch)
 *  - "TODAS": combina las cuatro estrategias + columna ESTRATEGIA
 */

// ============================================================
// ESTADO GLOBAL
// ============================================================

// Tab activa: 'm15pro' | 'h1m15pro' | 'microimpulso' | 'microimpulso_filtrado_m15' | 'all'
let activeStrategy = 'm15pro';

// Caches independientes por estrategia
const strategyCache = {
    m15pro: [],
    h1m15pro: [],
    microimpulso: [],
    microimpulso_filtrado_m15: []
};

// Guards de concurrencia (uno por endpoint, independientes)
const fetchInProgress = {
    m15pro: false,
    h1m15pro: false,
    microimpulso: false,
    microimpulso_filtrado_m15: false
};

// Timers de auto-refresh independientes
const refreshTimers = {
    m15pro: null,
    h1m15pro: null,
    microimpulso: null,
    microimpulso_filtrado_m15: null
};

// Intervalo de refresco
const AUTO_REFRESH_INTERVAL = 1000;

// ============================================================
// INIT
// ============================================================

async function initDashboard() {
    console.log('🚀 FASE4 v2: Initializing multi-strategy dashboard...');

    setupTabListeners();
    setupRefreshButton();

    // Carga inicial de las cuatro estrategias en paralelo
    await Promise.all([
        fetchStrategy('m15pro'),
        fetchStrategy('h1m15pro'),
        fetchStrategy('microimpulso'),
        fetchStrategy('microimpulso_filtrado_m15')
    ]);

    // Render inicial según tab activa
    renderCurrentTab();

    // Arrancar auto-refresh independiente para cada estrategia
    startAutoRefresh('m15pro');
    startAutoRefresh('h1m15pro');
    startAutoRefresh('microimpulso');
    startAutoRefresh('microimpulso_filtrado_m15');

    console.log('✅ FASE4 v2: Dashboard initialized');
}

// ============================================================
// AUTO-REFRESH
// ============================================================

function startAutoRefresh(strategy) {
    if (refreshTimers[strategy]) {
        clearInterval(refreshTimers[strategy]);
    }
    refreshTimers[strategy] = setInterval(async () => {
        await fetchStrategy(strategy);
        // Re-render solo si la tab activa depende de esta estrategia
        if (activeStrategy === strategy || activeStrategy === 'all') {
            renderCurrentTab();
        }
    }, AUTO_REFRESH_INTERVAL);
    console.log(`Auto-refresh started: ${strategy} every ${AUTO_REFRESH_INTERVAL / 1000}s`);
}

function stopAllAutoRefresh() {
    Object.keys(refreshTimers).forEach(strategy => {
        if (refreshTimers[strategy]) {
            clearInterval(refreshTimers[strategy]);
            refreshTimers[strategy] = null;
        }
    });
}

// ============================================================
// FETCH POR ESTRATEGIA
// ============================================================

async function fetchStrategy(strategy) {
    if (fetchInProgress[strategy]) {
        console.log(`SNAPSHOT FETCH SKIPPED_ALREADY_RUNNING: ${strategy}`);
        return;
    }
    fetchInProgress[strategy] = true;
    console.log(`SNAPSHOT FETCH START: ${strategy}`);

    try {
        let result;
        if (strategy === 'm15pro') {
            result = await window.api.getSmcM15ProSnapshot();
        } else if (strategy === 'h1m15pro') {
            result = await window.api.getSmcH1M15ProSnapshot();
        } else if (strategy === 'microimpulso') {
            result = await window.api.getSmcMicroImpulsoSnapshot();
        } else if (strategy === 'microimpulso_filtrado_m15') {
            result = await window.api.getSmcMicroImpulsoFiltradoM15Snapshot();
        } else {
            console.error(`fetchStrategy: unknown strategy '${strategy}'`);
            return;
        }

        if (!result.success) {
            // SNAPSHOT_ALREADY_RUNNING es silencioso — no es un error real
            if (result.error !== 'SNAPSHOT_ALREADY_RUNNING') {
                throw new Error(result.error || 'Failed to load SMC data');
            }
            return;
        }

        const snapshots = result.data || [];
        strategyCache[strategy] = snapshots;
        console.log(`SNAPSHOT FETCH OK: ${strategy} - ${snapshots.length} snapshots`);

        updateConnectionStatus(true);

    } catch (error) {
        console.error(`SNAPSHOT FETCH ERROR (${strategy}):`, error.message);
        updateConnectionStatus(false);
    } finally {
        fetchInProgress[strategy] = false;
    }
}

// ============================================================
// TABS
// ============================================================

function setupTabListeners() {
    document.querySelectorAll('.strategy-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const strategy = btn.dataset.strategy;
            if (strategy === activeStrategy) return;

            // Actualizar estado visual
            document.querySelectorAll('.strategy-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            activeStrategy = strategy;
            console.log(`Tab switched to: ${activeStrategy}`);

            // Render inmediato desde cache (sin esperar fetch)
            renderCurrentTab();
        });
    });
}

function setupRefreshButton() {
    const btn = document.getElementById('refreshBtn');
    if (btn) {
        btn.addEventListener('click', async () => {
            console.log('Manual refresh triggered');
            await Promise.all([
                fetchStrategy('m15pro'),
                fetchStrategy('h1m15pro'),
                fetchStrategy('microimpulso'),
                fetchStrategy('microimpulso_filtrado_m15')
            ]);
            renderCurrentTab();
            updateLastUpdateTime();
        });
    }
}

// ============================================================
// RENDER SEGÚN TAB ACTIVA
// ============================================================

function renderCurrentTab() {
    const statusEl = document.getElementById('strategyTabStatus');

    if (activeStrategy === 'm15pro') {
        renderTwoTableView(strategyCache.m15pro, 'm15pro');
        if (statusEl) statusEl.textContent = `${strategyCache.m15pro.length} símbolos`;

    } else if (activeStrategy === 'h1m15pro') {
        renderTwoTableView(strategyCache.h1m15pro, 'h1m15pro');
        if (statusEl) statusEl.textContent = `${strategyCache.h1m15pro.length} símbolos`;

    } else if (activeStrategy === 'microimpulso') {
        renderTwoTableView(strategyCache.microimpulso, 'microimpulso');
        if (statusEl) statusEl.textContent = `${strategyCache.microimpulso.length} símbolos`;

    } else if (activeStrategy === 'microimpulso_filtrado_m15') {
        renderTwoTableView(strategyCache.microimpulso_filtrado_m15, 'microimpulso_filtrado_m15');
        if (statusEl) statusEl.textContent = `${strategyCache.microimpulso_filtrado_m15.length} símbolos`;

    } else {
        // TODAS: combina las cuatro estrategias
        const combined = [
            ...strategyCache.m15pro.map(s => ({ ...s, _estrategia: 'm15pro' })),
            ...strategyCache.h1m15pro.map(s => ({ ...s, _estrategia: 'h1m15pro' })),
            ...strategyCache.microimpulso.map(s => ({ ...s, _estrategia: 'microimpulso' })),
            ...strategyCache.microimpulso_filtrado_m15.map(s => ({ ...s, _estrategia: 'microimpulso_filtrado_m15' }))
        ];
        renderAllStrategiesView(combined);
        const count = strategyCache.m15pro.length + strategyCache.h1m15pro.length
            + strategyCache.microimpulso.length + strategyCache.microimpulso_filtrado_m15.length;
        const detail = `${strategyCache.m15pro.length} M15 + ${strategyCache.h1m15pro.length} H1+M15`
            + ` + ${strategyCache.microimpulso.length} Micro + ${strategyCache.microimpulso_filtrado_m15.length} MicroFiltrado`;
        if (statusEl) statusEl.textContent = `${count} símbolos (${detail})`;
    }

    updateLastUpdateTime();
}

// ============================================================
// VISTA: UNA ESTRATEGIA (dos tablas Boom / Crash)
// ============================================================

function renderTwoTableView(snapshots, strategy) {
    // Restaurar headers de tabla (sin columna ESTRATEGIA)
    setTableHeaders(strategy);

    const boomData = snapshots.filter(s => s.symbol && s.symbol.includes('Boom'));
    const crashData = snapshots.filter(s => s.symbol && s.symbol.includes('Crash'));

    renderTable('boomTableBody', boomData, strategy, false);
    renderTable('crashTableBody', crashData, strategy, false);
}

// ============================================================
// VISTA: TODAS (combina estrategias, añade columna ESTRATEGIA)
// ============================================================

function renderAllStrategiesView(combined) {
    setTableHeaders('all');

    const boomData = combined.filter(s => s.symbol && s.symbol.includes('Boom'));
    const crashData = combined.filter(s => s.symbol && s.symbol.includes('Crash'));

    renderTable('boomTableBody', boomData, 'all', true);
    renderTable('crashTableBody', crashData, 'all', true);
}

// ============================================================
// HEADERS DINÁMICOS
// ============================================================

function setTableHeaders(strategy) {
    const baseHeaders = [
        'ÍNDICE', 'TENDENCIA H1', 'TENDENCIA M15', 'ÚLTIMO EVENTO M15',
        'ZONA MADRE M15', 'SCORE', 'OB', 'FVG', 'BARRIDA', 'ESTADO', 'PRECIO', 'ACTUALIZACIÓN'
    ];

    let headers;
    if (strategy === 'h1m15pro') {
        // Añadir columnas H1+M15 específicas
        headers = [
            'ÍNDICE', 'TENDENCIA H1', 'TENDENCIA M15', 'ÚLTIMO EVENTO M15',
            'ZONA MADRE M15', 'SCORE', 'OB', 'FVG', 'BARRIDA',
            'TP RATIO', 'ALIN. H1', 'ESTADO', 'PRECIO', 'ACTUALIZACIÓN'
        ];
    } else if (strategy === 'microimpulso') {
        // SMC MICRO IMPULSO: columnas específicas M1, sin H1/M15 como filtros principales
        headers = [
            'ÍNDICE', 'EVENTO M1 / MICRO BOS-CHOCH', 'ZONA MICRO',
            'SCORE', 'OB', 'FVG', 'BARRIDA', 'DESPLAZAMIENTO',
            'ESTADO', 'PRECIO', 'ACTUALIZACIÓN'
        ];
    } else if (strategy === 'microimpulso_filtrado_m15') {
        // SMC MICRO IMPULSO FILTRADO M15: columnas propias (sin H1, sin zona madre M15)
        headers = [
            'ÍNDICE', 'M15 DIR', 'EVENTO M1',
            'ZONA MICRO', 'SCORE', 'OB', 'FVG', 'BARRIDA', 'DESPLAZAMIENTO',
            'ESTADO', 'MOTIVO'
        ];
    } else if (strategy === 'all') {
        headers = ['ESTRATEGIA', ...baseHeaders];
    } else {
        headers = baseHeaders;
    }

    ['boomTableBody', 'crashTableBody'].forEach(tbodyId => {
        const tbody = document.getElementById(tbodyId);
        if (!tbody) return;
        const thead = tbody.closest('table').querySelector('thead tr');
        if (!thead) return;
        thead.innerHTML = headers.map(h => `<th>${h}</th>`).join('');
    });
}

// ============================================================
// RENDER TABLE
// ============================================================

function renderTable(tableBodyId, data, strategy, showEstrategia) {
    const tbody = document.getElementById(tableBodyId);
    if (!tbody) {
        console.error(`Table body ${tableBodyId} not found`);
        return;
    }

    // Column count for colspan in empty/loading rows
    // m15pro: 12 cols, h1m15pro: 14 cols (adds TP RATIO + ALIN. H1),
    // microimpulso: 11 cols, microimpulso_filtrado_m15: 11 cols, all: 13 (adds ESTRATEGIA)
    const colCount = showEstrategia ? 13 : (strategy === 'h1m15pro' ? 14 : (strategy === 'microimpulso' || strategy === 'microimpulso_filtrado_m15' ? 11 : 12));

    if (data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="${colCount}" class="loading-cell" style="text-align:center;padding:20px;">
                    No hay datos disponibles
                </td>
            </tr>
        `;
        return;
    }

    const rows = data.map(snapshot => createTableRow(snapshot, strategy, showEstrategia)).join('');
    tbody.innerHTML = rows;
}

// ============================================================
// CREAR FILA
// ============================================================

function createTableRow(snapshot, strategy, showEstrategia) {
    const {
        symbol,
        price,
        tendencia_h1,
        tendencia_m15,
        ultimo_evento_m15,
        ultimo_evento_m1,
        zona_madre_m15,
        zona_madre_m1,
        entrada,
        stoploss,
        score,
        ob,
        fvg,
        barrida,
        desplazamiento_valido,
        micro_bos_choch,
        estado,
        estado_dashboard,
        estado_final,
        estado_historial,
        updated_at,
        // H1+M15 específicos
        tp_ratio,
        alineacion_h1,
        estado_h1_m15,
        // combinado
        _estrategia
    } = snapshot;

    // Resolver estado a mostrar en dashboard live
    const DASHBOARD_BLOCKED = new Set(['SL', 'TP', 'DESCARTADA', 'PAUSADA']);
    const estadoCandidate = estado_final || estado_historial || estado;
    const estadoNorm = estadoCandidate ? estadoCandidate.toUpperCase().replace(/ /g, '_') : '';
    const estadoToDisplay = (!estadoNorm || DASHBOARD_BLOCKED.has(estadoNorm)) ? 'SIN_SETUP' : estadoCandidate;

    const symbolShort = (symbol || '').replace(' Index', '');
    const priceStr = price !== null && price !== undefined ? formatPrice(price) : '--';
    const estadoBadge = formatEstadoBadge(estadoToDisplay);
    const scoreBadge = formatScoreBadge(score);
    const timeStr = formatTime(updated_at);

    const ACTIVE_ESTADOS = new Set(['ACTIVA', 'ESPERANDO_ENTRADA', 'LLEGANDO_A_ZONA', 'EN_ZONA', 'PROFIT']);
    const rowClass = ACTIVE_ESTADOS.has(estadoNorm) ? 'row-activa' : 'row-sin-setup';

    // Columna ESTRATEGIA para vista TODAS
    const estrategiaCol = showEstrategia
        ? `<td>${formatEstrategiaBadge(_estrategia)}</td>`
        : '';

    // ----------------------------------------------------------------
    // Vista específica SMC MICRO IMPULSO
    // ----------------------------------------------------------------
    if (strategy === 'microimpulso') {
        const zonaCell = formatZonaMadre(zona_madre_m1, entrada, stoploss, symbolShort);
        // micro_bos_choch muestra BOS/CHOCH o "--"; nunca el estado
        const microBosChochStr = (micro_bos_choch != null && micro_bos_choch !== '') ? micro_bos_choch : '--';
        const desp = desplazamiento_valido || '--';

        return `
            <tr class="${rowClass}">
                <td><span class="symbol-name">${symbolShort}</span></td>
                <td><span class="event-label">${microBosChochStr}</span></td>
                <td>${zonaCell}</td>
                <td>${scoreBadge}</td>
                <td><span class="indicator-badge">${ob || '--'}</span></td>
                <td><span class="indicator-badge">${fvg || '--'}</span></td>
                <td><span class="indicator-badge">${barrida || '--'}</span></td>
                <td><span class="indicator-badge">${desp}</span></td>
                <td>${estadoBadge}</td>
                <td><span class="price-value">${priceStr}</span></td>
                <td><span class="time-value">${timeStr}</span></td>
            </tr>
        `;
    }

    // ----------------------------------------------------------------
    // Vista específica SMC MICRO IMPULSO FILTRADO M15
    // Columnas: ÍNDICE | M15 DIR | EVENTO M1 | ZONA MICRO | SCORE |
    //           OB | FVG | BARRIDA | DESPLAZAMIENTO | ESTADO | MOTIVO
    // Sin H1, sin zona madre M15, sin precio separado (está en zona micro)
    // ----------------------------------------------------------------
    if (strategy === 'microimpulso_filtrado_m15') {
        const dirM15 = snapshot.direccion_m15 || '--';
        const eventoM1 = snapshot.micro_bos_choch || '--';
        const zonaCell = formatZonaMadre(
            snapshot.zona_desde || snapshot.zona_hasta
                ? { desde: snapshot.zona_desde || 0, hasta: snapshot.zona_hasta || 0 }
                : null,
            entrada,
            stoploss,
            symbolShort
        );
        const desp = snapshot.desplazamiento || '--';
        const motivoStr = snapshot.motivo || '--';

        return `
            <tr class="${rowClass}">
                <td><span class="symbol-name">${symbolShort}</span></td>
                <td><span class="trend-badge">${dirM15}</span></td>
                <td><span class="event-label">${eventoM1}</span></td>
                <td>${zonaCell}</td>
                <td>${scoreBadge}</td>
                <td><span class="indicator-badge">${ob || '--'}</span></td>
                <td><span class="indicator-badge">${fvg || '--'}</span></td>
                <td><span class="indicator-badge">${barrida || '--'}</span></td>
                <td><span class="indicator-badge">${desp}</span></td>
                <td>${estadoBadge}</td>
                <td><span class="motivo-label">${motivoStr}</span></td>
            </tr>
        `;
    }

    // ----------------------------------------------------------------
    // Vista H1+M15 PRO
    // ----------------------------------------------------------------
    if (strategy === 'h1m15pro') {
        const zonaCell = formatZonaMadre(zona_madre_m15, entrada, stoploss, symbolShort);
        const tpRatioDisplay = tp_ratio ? `TP ${tp_ratio}` : '--';
        const alinStr = alineacion_h1 || '--';

        return `
            <tr class="${rowClass}">
                <td><span class="symbol-name">${symbolShort}</span></td>
                <td><span class="trend-badge">${tendencia_h1 || '--'}</span></td>
                <td><span class="trend-badge">${tendencia_m15 || '--'}</span></td>
                <td><span class="event-label">${ultimo_evento_m15 || '--'}</span></td>
                <td>${zonaCell}</td>
                <td>${scoreBadge}</td>
                <td><span class="indicator-badge">${ob || '--'}</span></td>
                <td><span class="indicator-badge">${fvg || '--'}</span></td>
                <td><span class="indicator-badge">${barrida || '--'}</span></td>
                <td><span class="tp-ratio-badge">${tpRatioDisplay}</span></td>
                <td><span class="h1-badge">${alinStr}</span></td>
                <td>${estadoBadge}</td>
                <td><span class="price-value">${priceStr}</span></td>
                <td><span class="time-value">${timeStr}</span></td>
            </tr>
        `;
    }

    // ----------------------------------------------------------------
    // Vista M15 PRO (default) y TODAS (all)
    // In the "all" view, all rows share the same 12-column base format
    // (ÍNDICE, TENDENCIA H1, TENDENCIA M15, ÚLTIMO EVENTO M15, ZONA MADRE M15,
    //  SCORE, OB, FVG, BARRIDA, ESTADO, PRECIO, ACTUALIZACIÓN + ESTRATEGIA prefix).
    // Both micro-impulso strategies map their M1-specific fields to the closest
    // base columns so they render correctly without breaking the shared layout.
    // ----------------------------------------------------------------
    let zonaToUse;
    if (_estrategia === 'microimpulso') {
        zonaToUse = zona_madre_m1;
    } else if (_estrategia === 'microimpulso_filtrado_m15') {
        zonaToUse = (snapshot.zona_desde || snapshot.zona_hasta)
            ? { desde: snapshot.zona_desde || 0, hasta: snapshot.zona_hasta || 0 }
            : null;
    } else {
        zonaToUse = zona_madre_m15;
    }
    const eventoToUse = (_estrategia === 'microimpulso' || _estrategia === 'microimpulso_filtrado_m15')
        ? (micro_bos_choch || ultimo_evento_m1 || '--')
        : (ultimo_evento_m15 || '--');
    const zonaCell = formatZonaMadre(zonaToUse, entrada, stoploss, symbolShort);

    return `
        <tr class="${rowClass}">
            ${estrategiaCol}
            <td><span class="symbol-name">${symbolShort}</span></td>
            <td><span class="trend-badge">${tendencia_h1 || '--'}</span></td>
            <td><span class="trend-badge">${tendencia_m15 || '--'}</span></td>
            <td><span class="event-label">${eventoToUse}</span></td>
            <td>${zonaCell}</td>
            <td>${scoreBadge}</td>
            <td><span class="indicator-badge">${ob || '--'}</span></td>
            <td><span class="indicator-badge">${fvg || '--'}</span></td>
            <td><span class="indicator-badge">${barrida || '--'}</span></td>
            <td>${estadoBadge}</td>
            <td><span class="price-value">${priceStr}</span></td>
            <td><span class="time-value">${timeStr}</span></td>
        </tr>
    `;
}

// ============================================================
// BADGES / FORMATTERS
// ============================================================

function formatEstrategiaBadge(estrategia) {
    if (estrategia === 'm15pro') {
        return '<span class="estrategia-badge estrategia-m15pro">M15 PRO</span>';
    }
    if (estrategia === 'microimpulso') {
        return '<span class="estrategia-badge estrategia-microimpulso">MICRO IMPULSO</span>';
    }
    if (estrategia === 'microimpulso_filtrado_m15') {
        return '<span class="estrategia-badge estrategia-microimpulso-filtrado">MICRO FILTRADO M15</span>';
    }
    return '<span class="estrategia-badge estrategia-h1m15">H1+M15 PRO</span>';
}

function formatZonaMadre(zona, entrada, stoploss, symbolShort) {
    const hasZona = zona && (zona.desde !== 0 || zona.hasta !== 0);
    const hasEntrada = entrada !== null && entrada !== undefined && entrada !== 0;
    const hasSL = stoploss !== null && stoploss !== undefined && stoploss !== 0;

    if (!hasZona && !hasEntrada) {
        return '<span class="zone-range">--</span>';
    }

    const entradaStr = hasEntrada ? Number(entrada).toFixed(2) : '--';
    const slStr = hasSL ? Number(stoploss).toFixed(2) : '--';
    const entradaAttr = escapeHtmlAttr(entradaStr);
    const slAttr = escapeHtmlAttr(slStr);

    return `
        <div class="zona-madre-cell">
            <div class="zona-linea">
                <span class="zona-label">ENTRADA:</span>
                <span class="zona-valor">${entradaStr}</span>
                <button class="copy-zona-btn"
                    data-value="${entradaAttr}"
                    onclick="copyZoneValue(this)"
                    aria-label="Copiar ENTRADA"
                    title="Copiar ENTRADA">&#x2398;</button>
            </div>
            <div class="zona-linea">
                <span class="zona-label">STOPLOSS:</span>
                <span class="zona-valor zona-sl">${slStr}</span>
                <button class="copy-zona-btn"
                    data-value="${slAttr}"
                    onclick="copyZoneValue(this)"
                    aria-label="Copiar STOPLOSS"
                    title="Copiar STOPLOSS">&#x2398;</button>
            </div>
        </div>
    `;
}

function escapeHtmlAttr(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function copyZoneValue(btn) {
    const text = btn.dataset.value || '--';
    const handleSuccess = () => {
        const original = btn.textContent;
        btn.textContent = '✓';
        btn.classList.add('copy-zona-btn--copiado');
        setTimeout(() => {
            btn.textContent = original;
            btn.classList.remove('copy-zona-btn--copiado');
        }, 1500);
    };
    const handleError = (err) => {
        console.error('Error copiando al portapapeles:', err);
        const original = btn.textContent;
        btn.textContent = '!';
        setTimeout(() => { btn.textContent = original; }, 1500);
    };

    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(text).then(handleSuccess).catch(handleError);
        return;
    }
    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.setAttribute('readonly', '');
        textArea.style.position = 'absolute';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(textArea);
        if (copied) handleSuccess();
        else handleError(new Error('execCommand(copy) returned false'));
    } catch (err) {
        handleError(err);
    }
}

function formatEstadoBadge(estado) {
    const estadoNormalized = estado ? estado.toUpperCase().replace(/ /g, '_') : 'SIN_SETUP';
    switch (estadoNormalized) {
        case 'ACTIVA':             return '<span class="status-badge status-activa">✓ ACTIVA</span>';
        case 'ESPERANDO_ENTRADA':  return '<span class="status-badge status-esperando">⏳ ESPERANDO ENTRADA</span>';
        case 'LLEGANDO_A_ZONA':    return '<span class="status-badge status-llegando">↓ LLEGANDO A ZONA</span>';
        case 'EN_ZONA':            return '<span class="status-badge status-en-zona">🎯 EN ZONA</span>';
        case 'PROFIT':             return '<span class="status-badge status-profit">💰 PROFIT</span>';
        case 'TP':                 return '<span class="status-badge status-tp">✅ TP</span>';
        case 'SL':                 return '<span class="status-badge status-sl">❌ SL</span>';
        case 'PAUSADA':            return '<span class="status-badge status-pausada">⏸ PAUSADA</span>';
        case 'DESCARTADA':         return '<span class="status-badge status-descartada">🗑 DESCARTADA</span>';
        case 'SIN_SETUP':
        case 'SIN SETUP':
        default:                   return '<span class="status-badge status-sin-setup">○ SIN SETUP</span>';
    }
}

function formatScoreBadge(score) {
    let badgeClass = 'score-badge';
    if (score >= 7)      badgeClass += ' score-high';
    else if (score >= 4) badgeClass += ' score-medium';
    else                 badgeClass += ' score-low';
    return `<span class="${badgeClass}">${score ?? '--'}</span>`;
}

function formatPrice(price) {
    if (price === null || price === undefined) return '--';
    return price.toFixed(2);
}

function formatTime(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (e) { return '--'; }
}

// ============================================================
// CONNECTION / TIMESTAMPS
// ============================================================

function updateConnectionStatus(connected) {
    const statusDot = document.getElementById('statusDot');
    const connectionText = document.getElementById('connectionText');
    if (statusDot) {
        if (connected) statusDot.classList.remove('disconnected');
        else statusDot.classList.add('disconnected');
    }
    if (connectionText) {
        connectionText.textContent = connected ? 'MT5: Conectado' : 'MT5: Desconectado';
    }
}

function updateLastUpdateTime() {
    const lastUpdate = document.getElementById('lastUpdate');
    if (lastUpdate) {
        const now = new Date();
        lastUpdate.textContent = `Última actualización: ${now.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    }
}

// ============================================================
// BOOT
// ============================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}

window.addEventListener('beforeunload', stopAllAutoRefresh);

console.log('✅ FASE4 Dashboard script loaded');

