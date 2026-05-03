// Configuración de Supabase
// IMPORTANTE: Reemplazar estas credenciales con las reales de tu proyecto Supabase
// SUPABASE_URL debe ser SOLO la URL base, sin slash final y sin /rest/v1
// Formato correcto: https://xxxx.supabase.co (sin trailing slash)
// Ejemplo: const SUPABASE_URL = 'https://rqjmndaqxxgljpubnfkg.supabase.co';
const SUPABASE_URL = 'https://rqjmndaqxxgljpubnfkg.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxam1uZGFxeHhnbGpwdWJuZmtnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc3NDYzOTMsImV4cCI6MjA5MzMyMjM5M30.6WCZP39R9nMoDPgasGxPt6qbR8rvVcB3kX1gJvnKuv0';

// Variables globales
let autoRefreshInterval = null;
const AUTO_REFRESH_SECONDS = 30;

// Configuración SMC
const SWING_LOOKBACK = 3;
const CLOSE_BREAK = true; // Si true, usa precio de cierre para detectar ruptura; si false, usa high/low
const M1_VELAS_ZONA = 15;
const ORDER_BLOCK_LOOKBACK = 20; // Velas a revisar hacia atrás para buscar Order Blocks
const BARRIDA_LOOKBACK = 40; // Velas a revisar para detectar barridas
const MIN_SEGMENT_LENGTH = 10; // Longitud mínima de segmento para análisis de barrida
const BARRIDA_INITIAL_OFFSET = 5; // Inicio del análisis de barrida desde la vela N

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Verificar configuración
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY || SUPABASE_URL.includes('YOUR_') || SUPABASE_ANON_KEY.includes('YOUR_')) {
        updateStatus('⚠️ Configurar SUPABASE_URL y SUPABASE_ANON_KEY en assets/app.js', 'warning');
        return;
    }

    // Event listeners
    document.getElementById('symbolSelect').addEventListener('change', fetchData);
    document.getElementById('timeframeSelect').addEventListener('change', fetchData);
    document.getElementById('refreshBtn').addEventListener('click', fetchData);

    // Cargar datos iniciales
    fetchData();

    // Iniciar auto-refresh
    startAutoRefresh();
}

function startAutoRefresh() {
    // Limpiar intervalo existente
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }

    // Configurar nuevo intervalo
    autoRefreshInterval = setInterval(() => {
        fetchData(true);
    }, AUTO_REFRESH_SECONDS * 1000);

    updateStatus(`Auto-refresh cada ${AUTO_REFRESH_SECONDS} segundos activado`, 'success');
}

function updateStatus(message, type = 'info') {
    const statusElement = document.getElementById('statusMessage');
    statusElement.textContent = message;
    
    // Opcional: cambiar color según tipo
    if (type === 'error') {
        statusElement.style.color = 'var(--accent-red)';
    } else if (type === 'success') {
        statusElement.style.color = 'var(--accent-green)';
    } else if (type === 'warning') {
        statusElement.style.color = '#f0ad4e';
    } else {
        statusElement.style.color = 'var(--text-secondary)';
    }
}

async function fetchData(isAutoRefresh = false) {
    const symbol = document.getElementById('symbolSelect').value;
    const timeframe = document.getElementById('timeframeSelect').value;

    if (!isAutoRefresh) {
        updateStatus('Cargando datos...', 'info');
    }

    try {
        // Cargar múltiples timeframes para análisis SMC
        const [candlesH1, candlesM15, candlesM1] = await Promise.all([
            fetchCandles(symbol, 'H1', 700),
            fetchCandles(symbol, 'M15', 2000),
            fetchCandles(symbol, 'M1', 10000)
        ]);

        // Log para debugging: cantidad de velas obtenidas
        console.log('=== VELAS OBTENIDAS ===');
        console.log('Velas H1:', candlesH1 ? candlesH1.length : 0);
        console.log('Velas M15:', candlesM15 ? candlesM15.length : 0);
        console.log('Velas M1:', candlesM1 ? candlesM1.length : 0);

        // Validar que al menos tenemos datos M15 (crítico para análisis)
        // H1 y M1 son opcionales pero mejoran el análisis
        if (!candlesM15 || candlesM15.length === 0) {
            updateStatus('No hay datos M15 disponibles (requerido para análisis)', 'warning');
            clearDisplay();
            clearSMCDisplay();
            return;
        }

        // Advertir si faltan timeframes opcionales
        if (!candlesH1 || candlesH1.length === 0) {
            console.warn('No hay datos H1 disponibles. El análisis de tendencia H1 no estará disponible.');
        }
        if (!candlesM1 || candlesM1.length === 0) {
            console.warn('No hay datos M1 disponibles. La zona fina M1 no estará disponible.');
        }

        // Actualizar display con la última vela del timeframe seleccionado
        let currentCandles;
        if (timeframe === 'H1') {
            currentCandles = candlesH1;
        } else if (timeframe === 'M15') {
            currentCandles = candlesM15;
        } else if (timeframe === 'M1') {
            currentCandles = candlesM1;
        } else {
            // Fallback para timeframes no soportados
            currentCandles = candlesM15;
            console.warn(`Timeframe ${timeframe} no soportado, usando M15 por defecto`);
        }
        
        if (currentCandles && currentCandles.length > 0) {
            updateDisplay(currentCandles[currentCandles.length - 1], symbol, timeframe);
            updateTable(currentCandles.slice(-10).reverse());
        }

        // Ejecutar análisis SMC (requiere M15 como mínimo, H1 es opcional para tendencia)
        if (candlesM15 && candlesM15.length > 0) {
            console.log('=== EJECUTANDO ANÁLISIS SMC ===');
            const smcResult = analyzeSMC(candlesH1, candlesM15, candlesM1, symbol);
            console.log('Resultado SMC:', smcResult);
            console.log('Tendencia H1:', smcResult.tendenciaH1);
            console.log('Tendencia M15:', smcResult.tendenciaM15);
            console.log('Dirección operativa:', smcResult.direccionOperativa);
            console.log('Zona M15:', smcResult.zonaM15);
            console.log('Zona M1:', smcResult.zonaM1);
            console.log('Estado:', smcResult.estado);
            updateSMCDisplay(smcResult);
        } else {
            clearSMCDisplay();
        }

        // Actualizar timestamp de última actualización
        updateLastUpdateTime();

        if (!isAutoRefresh) {
            updateStatus('✅ Datos actualizados correctamente', 'success');
        }

    } catch (error) {
        console.error('Error fetching data:', error);
        updateStatus(`❌ Error: ${error.message}`, 'error');
    }
}

async function fetchCandles(symbol, timeframe, limit) {
    // Request latest data in descending order, then reverse to get chronological ascending order
    const url = `${SUPABASE_URL}/rest/v1/market_candles?symbol=eq.${encodeURIComponent(symbol)}&timeframe=eq.${timeframe}&order=timestamp.desc&limit=${limit}`;
    
    console.log(`Fetching ${timeframe} candles:`, url);

    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Content-Type': 'application/json'
        }
    });

    if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
    }

    const data = await response.json();
    
    // Reverse to get data in ascending chronological order for SMC analysis
    return data.reverse();
}

// Helper function to calculate median
function calculateMedian(values) {
    if (values.length === 0) return 0;
    // Ensure numeric sorting by explicitly parsing values
    const sorted = values.slice().sort((a, b) => parseFloat(a) - parseFloat(b));
    const mid = Math.floor(sorted.length / 2);
    
    // For even-length arrays, return average of two middle elements
    if (sorted.length % 2 === 0) {
        return (parseFloat(sorted[mid - 1]) + parseFloat(sorted[mid])) / 2;
    }
    
    // For odd-length arrays, return middle element
    return parseFloat(sorted[mid]);
}

// =========================
// SMC ANALYSIS FUNCTIONS
// =========================

function direccionOperativaPorIndice(symbol) {
    if (symbol.includes('Boom')) {
        return 'ALCISTA';
    }
    if (symbol.includes('Crash')) {
        return 'BAJISTA';
    }
    return null;
}

function detectarSwings(candles, lookback = SWING_LOOKBACK) {
    const swings = [];

    for (let i = lookback; i < candles.length - lookback; i++) {
        const high = candles[i].high;
        const low = candles[i].low;

        const prevHighs = candles.slice(i - lookback, i).map(c => c.high);
        const nextHighs = candles.slice(i + 1, i + 1 + lookback).map(c => c.high);

        const prevLows = candles.slice(i - lookback, i).map(c => c.low);
        const nextLows = candles.slice(i + 1, i + 1 + lookback).map(c => c.low);

        if (high > Math.max(...prevHighs) && high > Math.max(...nextHighs)) {
            swings.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'HIGH',
                precio: parseFloat(high)
            });
        }

        if (low < Math.min(...prevLows) && low < Math.min(...nextLows)) {
            swings.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'LOW',
                precio: parseFloat(low)
            });
        }
    }

    return swings;
}

function detectarEstructura(candles, swings) {
    const eventos = [];
    let tendencia = null;
    let ultimoHigh = null;
    let ultimoLow = null;
    const nivelesRotos = new Set();

    for (let i = 0; i < candles.length; i++) {
        const close = parseFloat(candles[i].close);
        const high = parseFloat(candles[i].high);
        const low = parseFloat(candles[i].low);
        const timestamp = candles[i].timestamp;

        const swingsPasados = swings.filter(s => s.index < i);

        const highs = swingsPasados.filter(s => s.tipo === 'HIGH');
        const lows = swingsPasados.filter(s => s.tipo === 'LOW');

        if (highs.length > 0) {
            ultimoHigh = highs[highs.length - 1];
        }

        if (lows.length > 0) {
            ultimoLow = lows[lows.length - 1];
        }

        if (!ultimoHigh || !ultimoLow) {
            continue;
        }

        const rompeHigh = CLOSE_BREAK ? close > ultimoHigh.precio : high > ultimoHigh.precio;
        const rompeLow = CLOSE_BREAK ? close < ultimoLow.precio : low < ultimoLow.precio;

        const highKey = `HIGH_${ultimoHigh.index}`;
        const lowKey = `LOW_${ultimoLow.index}`;

        if (rompeHigh && !nivelesRotos.has(highKey)) {
            let evento;
            if (tendencia === null || tendencia === 'ALCISTA') {
                evento = 'BOS_ALCISTA';
                tendencia = 'ALCISTA';
            } else {
                evento = 'CHOCH_ALCISTA';
                tendencia = 'ALCISTA';
            }

            eventos.push({
                timestamp: timestamp,
                index: i,
                evento: evento,
                nivel_roto: ultimoHigh.precio,
                precio_cierre: close
            });

            nivelesRotos.add(highKey);
        } else if (rompeLow && !nivelesRotos.has(lowKey)) {
            let evento;
            if (tendencia === null || tendencia === 'BAJISTA') {
                evento = 'BOS_BAJISTA';
                tendencia = 'BAJISTA';
            } else {
                evento = 'CHOCH_BAJISTA';
                tendencia = 'BAJISTA';
            }

            eventos.push({
                timestamp: timestamp,
                index: i,
                evento: evento,
                nivel_roto: ultimoLow.precio,
                precio_cierre: close
            });

            nivelesRotos.add(lowKey);
        }
    }

    return { eventos, tendencia };
}

function detectarFVG(candles) {
    const fvgs = [];

    for (let i = 2; i < candles.length; i++) {
        const vela1 = candles[i - 2];
        const vela3 = candles[i];

        if (vela3.low > vela1.high) {
            fvgs.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'FVG_ALCISTA',
                desde: parseFloat(vela1.high),
                hasta: parseFloat(vela3.low)
            });
        }

        if (vela3.high < vela1.low) {
            fvgs.push({
                index: i,
                timestamp: candles[i].timestamp,
                tipo: 'FVG_BAJISTA',
                desde: parseFloat(vela3.high),
                hasta: parseFloat(vela1.low)
            });
        }
    }

    return fvgs;
}

function buscarOrderBlock(candles, evento) {
    const idx = evento.index;
    const direccion = evento.evento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';

    const inicio = Math.max(0, idx - ORDER_BLOCK_LOOKBACK);
    const tramo = candles.slice(inicio, idx);

    if (direccion === 'ALCISTA') {
        const candidatas = tramo.filter(c => c.close < c.open);
        if (candidatas.length === 0) {
            return null;
        }

        const ob = candidatas[candidatas.length - 1];
        return {
            tipo: 'OB_ALCISTA',
            timestamp: ob.timestamp,
            desde: parseFloat(ob.low),
            hasta: parseFloat(ob.high)
        };
    } else {
        const candidatas = tramo.filter(c => c.close > c.open);
        if (candidatas.length === 0) {
            return null;
        }

        const ob = candidatas[candidatas.length - 1];
        return {
            tipo: 'OB_BAJISTA',
            timestamp: ob.timestamp,
            desde: parseFloat(ob.low),
            hasta: parseFloat(ob.high)
        };
    }
}

function detectarBarridaPrevia(candles, evento, direccion, lookback = BARRIDA_LOOKBACK) {
    const idx = evento.index;
    const inicio = Math.max(0, idx - lookback);
    const tramo = candles.slice(inicio, idx);

    if (tramo.length < MIN_SEGMENT_LENGTH) {
        return null;
    }

    if (direccion === 'ALCISTA') {
        for (let j = 5; j < tramo.length; j++) {
            const minimoAnterior = Math.min(...tramo.slice(0, j).map(c => c.low));
            const vela = tramo[j];

            if (vela.low < minimoAnterior && vela.close > minimoAnterior) {
                return {
                    timestamp: vela.timestamp,
                    tipo: 'BARRIDA_BAJISTA_PREVIA',
                    nivel: minimoAnterior,
                    low: parseFloat(vela.low),
                    close: parseFloat(vela.close)
                };
            }
        }
    } else {
        for (let j = 5; j < tramo.length; j++) {
            const maximoAnterior = Math.max(...tramo.slice(0, j).map(c => c.high));
            const vela = tramo[j];

            if (vela.high > maximoAnterior && vela.close < maximoAnterior) {
                return {
                    timestamp: vela.timestamp,
                    tipo: 'BARRIDA_ALCISTA_PREVIA',
                    nivel: maximoAnterior,
                    high: parseFloat(vela.high),
                    close: parseFloat(vela.close)
                };
            }
        }
    }

    return null;
}

function crearZonaM15(candlesM15, eventosM15, fvgsM15, symbol, precioActual) {
    if (!eventosM15 || eventosM15.length === 0) {
        return null;
    }

    const direccionOperativa = direccionOperativaPorIndice(symbol);
    let eventosFiltrados = eventosM15;

    if (direccionOperativa) {
        eventosFiltrados = eventosM15.filter(e => {
            const direccionEvento = e.evento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';
            return direccionEvento === direccionOperativa;
        });
    }

    if (eventosFiltrados.length === 0) {
        return null;
    }

    // Buscar desde el último evento hacia atrás
    for (let i = eventosFiltrados.length - 1; i >= 0; i--) {
        const ultimoEvento = eventosFiltrados[i];
        const direccion = ultimoEvento.evento.includes('ALCISTA') ? 'ALCISTA' : 'BAJISTA';

        const ob = buscarOrderBlock(candlesM15, ultimoEvento);

        const fvgsValidos = fvgsM15.filter(f => {
            const cumpleIndex = f.index <= ultimoEvento.index;
            const cumpleTipo = (direccion === 'ALCISTA' && f.tipo === 'FVG_ALCISTA') ||
                              (direccion === 'BAJISTA' && f.tipo === 'FVG_BAJISTA');
            return cumpleIndex && cumpleTipo;
        });

        const fvg = fvgsValidos.length > 0 ? fvgsValidos[fvgsValidos.length - 1] : null;
        const barrida = detectarBarridaPrevia(candlesM15, ultimoEvento, direccion);

        let zonaDesde = null;
        let zonaHasta = null;

        if (ob && fvg) {
            zonaDesde = Math.min(ob.desde, fvg.desde, fvg.hasta);
            zonaHasta = Math.max(ob.hasta, fvg.desde, fvg.hasta);
        } else if (ob) {
            zonaDesde = ob.desde;
            zonaHasta = ob.hasta;
        } else if (fvg) {
            zonaDesde = Math.min(fvg.desde, fvg.hasta);
            zonaHasta = Math.max(fvg.desde, fvg.hasta);
        }

        if (zonaDesde === null) {
            continue;
        }

        const zona = {
            direccion: direccion,
            evento: ultimoEvento,
            ob: ob,
            fvg: fvg,
            barrida: barrida,
            zona_desde: zonaDesde,
            zona_hasta: zonaHasta,
            score: 0
        };

        // Validar utilidad de zona según Boom/Crash
        let esUtil = true;
        let motivo = '';

        if (direccionOperativa === 'ALCISTA') {
            esUtil = zonaHasta <= precioActual;
            motivo = 'Boom busca reacción alcista: la zona debe estar bajo el precio actual.';
        } else if (direccionOperativa === 'BAJISTA') {
            esUtil = zonaDesde >= precioActual;
            motivo = 'Crash busca reacción bajista: la zona debe estar sobre el precio actual.';
        } else {
            motivo = 'Índice no clasificado como Boom/Crash.';
        }

        // Calcular score
        let score = 0;
        if (ultimoEvento.evento.includes('CHOCH')) {
            score += 3;
        }
        if (ultimoEvento.evento.includes('BOS')) {
            score += 2;
        }
        if (ob) {
            score += 2;
        }
        if (fvg) {
            score += 2;
        }
        if (barrida) {
            score += 3;
        }
        if (esUtil) {
            score += 2;
        }

        zona.score = score;
        zona.es_util = esUtil;
        zona.motivo = motivo;
        zona.direccion_operativa = direccionOperativa;

        if (esUtil) {
            return zona;
        }
    }

    return null;
}

function crearZonaFinaM1(candlesM1, zonaM15, symbol) {
    if (!candlesM1 || candlesM1.length === 0 || !zonaM15) {
        return null;
    }

    const precioActual = parseFloat(candlesM1[candlesM1.length - 1].close);
    const direccionOperativa = direccionOperativaPorIndice(symbol);

    // Filtrar velas cercanas y almacenar índice original para evitar indexOf
    const cercanas = [];
    for (let i = 0; i < candlesM1.length; i++) {
        const c = candlesM1[i];
        if (c.high >= zonaM15.zona_desde && c.low <= zonaM15.zona_hasta) {
            cercanas.push({ candle: c, originalIndex: i });
        }
    }

    let tramo;
    let confirmacion;

    if (cercanas.length > 0) {
        const lastCercana = cercanas[cercanas.length - 1];
        const idx = lastCercana.originalIndex;
        const inicio = Math.max(0, idx - M1_VELAS_ZONA + 1);
        tramo = candlesM1.slice(inicio, idx + 1);
        confirmacion = 'M1 dentro/cerca de zona madre M15';
    } else {
        tramo = candlesM1.slice(-M1_VELAS_ZONA);
        confirmacion = 'M1 últimas velas cercanas al precio actual';
    }

    if (tramo.length === 0) {
        return null;
    }

    let zonaDesde, zonaHasta;

    if (direccionOperativa === 'ALCISTA') {
        zonaDesde = Math.min(...tramo.map(c => c.low));
        zonaHasta = calculateMedian(tramo.map(c => c.close));
    } else if (direccionOperativa === 'BAJISTA') {
        zonaDesde = calculateMedian(tramo.map(c => c.close));
        zonaHasta = Math.max(...tramo.map(c => c.high));
    } else {
        zonaDesde = Math.min(...tramo.map(c => c.low));
        zonaHasta = Math.max(...tramo.map(c => c.high));
    }

    if (zonaDesde > zonaHasta) {
        // Advertir sobre inversión de límites de zona
        console.warn('Zona M1: límites invertidos, corrigiendo. Desde:', zonaDesde, 'Hasta:', zonaHasta);
        [zonaDesde, zonaHasta] = [zonaHasta, zonaDesde];
    }

    const dentro = zonaDesde <= precioActual && precioActual <= zonaHasta;

    return {
        zona_m1_desde: zonaDesde,
        zona_m1_hasta: zonaHasta,
        m1_confirmacion: confirmacion,
        velas_m1_usadas: M1_VELAS_ZONA,
        precio_dentro_m1: dentro
    };
}

function analyzeSMC(candlesH1, candlesM15, candlesM1, symbol) {
    console.log('--- Iniciando analyzeSMC ---');
    console.log('Symbol:', symbol);
    
    // Análisis H1 (opcional)
    let swingsH1 = [];
    let eventosH1 = [];
    let tendenciaH1 = null;
    
    if (candlesH1 && candlesH1.length > 0) {
        console.log('Analizando H1 con', candlesH1.length, 'velas');
        swingsH1 = detectarSwings(candlesH1);
        console.log('Swings H1 detectados:', swingsH1.length);
        const resultH1 = detectarEstructura(candlesH1, swingsH1);
        eventosH1 = resultH1.eventos;
        tendenciaH1 = resultH1.tendencia;
        console.log('Eventos H1:', eventosH1.length, 'Tendencia H1:', tendenciaH1);
    } else {
        console.log('Sin datos H1 para análisis');
    }

    // Análisis M15 (requerido)
    console.log('Analizando M15 con', candlesM15.length, 'velas');
    const swingsM15 = detectarSwings(candlesM15);
    console.log('Swings M15 detectados:', swingsM15.length);
    const { eventos: eventosM15, tendencia: tendenciaM15 } = detectarEstructura(candlesM15, swingsM15);
    console.log('Eventos M15:', eventosM15.length, 'Tendencia M15:', tendenciaM15);

    // FVGs M15
    const fvgsM15 = detectarFVG(candlesM15);
    console.log('FVGs M15 detectados:', fvgsM15.length);

    // Precio actual
    const precioActual = candlesM15.length > 0 ? parseFloat(candlesM15[candlesM15.length - 1].close) : null;
    console.log('Precio actual:', precioActual);

    // Zona M15
    const zonaM15 = crearZonaM15(candlesM15, eventosM15, fvgsM15, symbol, precioActual);
    console.log('Zona M15 creada:', zonaM15 ? 'SÍ' : 'NO', zonaM15);

    // Zona M1
    const zonaM1 = candlesM1 && candlesM1.length > 0 ? crearZonaFinaM1(candlesM1, zonaM15, symbol) : null;
    console.log('Zona M1 creada:', zonaM1 ? 'SÍ' : 'NO', zonaM1);

    // Estado
    let estado = '--';
    if (zonaM15 && precioActual !== null) {
        if (precioActual >= zonaM15.zona_desde && precioActual <= zonaM15.zona_hasta) {
            estado = 'PRECIO_DENTRO_DE_ZONA';
        } else {
            estado = 'PRECIO_FUERA_DE_ZONA';
        }
    }
    console.log('Estado final:', estado);

    return {
        tendenciaH1: tendenciaH1 || '--',
        tendenciaM15: tendenciaM15 || '--',
        eventosH1: eventosH1,
        eventosM15: eventosM15,
        zonaM15: zonaM15,
        zonaM1: zonaM1,
        precioActual: precioActual,
        estado: estado,
        direccionOperativa: direccionOperativaPorIndice(symbol)
    };
}

function updateDisplay(candle, symbol, timeframe) {
    document.getElementById('displaySymbol').textContent = symbol;
    document.getElementById('displayTimeframe').textContent = timeframe;
    document.getElementById('closePrice').textContent = formatPrice(candle.close);
    document.getElementById('highPrice').textContent = formatPrice(candle.high);
    document.getElementById('lowPrice').textContent = formatPrice(candle.low);
    document.getElementById('timestamp').textContent = formatTimestamp(candle.timestamp);
}

function updateTable(candles) {
    const tbody = document.getElementById('candlesTableBody');
    tbody.innerHTML = '';

    candles.forEach(candle => {
        const row = document.createElement('tr');
        
        // Determinar si es alcista o bajista
        const isBullish = candle.close >= candle.open;
        const closeClass = isBullish ? 'bullish' : 'bearish';

        row.innerHTML = `
            <td>${formatTimestamp(candle.timestamp)}</td>
            <td>${formatPrice(candle.open)}</td>
            <td>${formatPrice(candle.high)}</td>
            <td>${formatPrice(candle.low)}</td>
            <td class="${closeClass}">${formatPrice(candle.close)}</td>
            <td>${formatVolume(candle.tick_volume)}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function updateSMCDisplay(smcResult) {
    console.log('--- Actualizando display SMC ---');
    console.log('smcResult recibido:', smcResult);
    
    // Tendencias
    document.getElementById('smcTendenciaH1').textContent = smcResult.tendenciaH1 || '--';
    document.getElementById('smcTendenciaM15').textContent = smcResult.tendenciaM15 || '--';

    // Dirección operativa
    document.getElementById('smcDireccion').textContent = smcResult.direccionOperativa || '--';

    // Eventos
    if (smcResult.eventosH1 && smcResult.eventosH1.length > 0) {
        const ultimoH1 = smcResult.eventosH1[smcResult.eventosH1.length - 1];
        document.getElementById('smcEventoH1').textContent = `${ultimoH1.evento} @ ${formatPrice(ultimoH1.nivel_roto)}`;
    } else {
        document.getElementById('smcEventoH1').textContent = '--';
    }

    if (smcResult.eventosM15 && smcResult.eventosM15.length > 0) {
        const ultimoM15 = smcResult.eventosM15[smcResult.eventosM15.length - 1];
        document.getElementById('smcEventoM15').textContent = `${ultimoM15.evento} @ ${formatPrice(ultimoM15.nivel_roto)}`;
    } else {
        document.getElementById('smcEventoM15').textContent = '--';
    }

    // Zona M15
    if (smcResult.zonaM15) {
        const zona = smcResult.zonaM15;
        console.log('Actualizando zona M15:', zona);
        document.getElementById('smcZonaM15Desde').textContent = formatPrice(zona.zona_desde);
        document.getElementById('smcZonaM15Hasta').textContent = formatPrice(zona.zona_hasta);
        document.getElementById('smcScore').textContent = zona.score || '0';
        document.getElementById('smcOB').textContent = zona.ob ? '✅ SÍ' : '❌ NO';
        document.getElementById('smcFVG').textContent = zona.fvg ? '✅ SÍ' : '❌ NO';
        document.getElementById('smcBarrida').textContent = zona.barrida ? '✅ SÍ' : '❌ NO';
    } else {
        console.log('No hay zona M15 para actualizar');
        document.getElementById('smcZonaM15Desde').textContent = '--';
        document.getElementById('smcZonaM15Hasta').textContent = '--';
        document.getElementById('smcScore').textContent = '--';
        document.getElementById('smcOB').textContent = '--';
        document.getElementById('smcFVG').textContent = '--';
        document.getElementById('smcBarrida').textContent = '--';
    }

    // Zona M1
    if (smcResult.zonaM1) {
        const zona = smcResult.zonaM1;
        console.log('Actualizando zona M1:', zona);
        document.getElementById('smcZonaM1Desde').textContent = formatPrice(zona.zona_m1_desde);
        document.getElementById('smcZonaM1Hasta').textContent = formatPrice(zona.zona_m1_hasta);
    } else {
        console.log('No hay zona M1 para actualizar');
        document.getElementById('smcZonaM1Desde').textContent = '--';
        document.getElementById('smcZonaM1Hasta').textContent = '--';
    }

    // Estado
    document.getElementById('smcEstado').textContent = smcResult.estado;
    console.log('Display SMC actualizado correctamente');
}

function clearSMCDisplay() {
    document.getElementById('smcTendenciaH1').textContent = '--';
    document.getElementById('smcTendenciaM15').textContent = '--';
    document.getElementById('smcDireccion').textContent = '--';
    document.getElementById('smcScore').textContent = '--';
    document.getElementById('smcEventoH1').textContent = '--';
    document.getElementById('smcEventoM15').textContent = '--';
    document.getElementById('smcZonaM15Desde').textContent = '--';
    document.getElementById('smcZonaM15Hasta').textContent = '--';
    document.getElementById('smcZonaM1Desde').textContent = '--';
    document.getElementById('smcZonaM1Hasta').textContent = '--';
    document.getElementById('smcOB').textContent = '--';
    document.getElementById('smcFVG').textContent = '--';
    document.getElementById('smcBarrida').textContent = '--';
    document.getElementById('smcEstado').textContent = '--';
}

function clearDisplay() {
    document.getElementById('displaySymbol').textContent = '--';
    document.getElementById('displayTimeframe').textContent = '--';
    document.getElementById('closePrice').textContent = '--';
    document.getElementById('highPrice').textContent = '--';
    document.getElementById('lowPrice').textContent = '--';
    document.getElementById('timestamp').textContent = '--';
    
    const tbody = document.getElementById('candlesTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading">No hay datos disponibles</td></tr>';
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('es-ES', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('lastUpdate').textContent = timeString;
}

function formatPrice(price) {
    if (price === null || price === undefined) return '--';
    return parseFloat(price).toFixed(5);
}

function formatVolume(volume) {
    if (volume === null || volume === undefined) return '--';
    const numValue = Number(volume);
    if (isNaN(numValue)) return '--';
    return Math.round(numValue).toLocaleString('es-ES');
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '--';
    
    try {
        const date = new Date(timestamp);
        return date.toLocaleString('es-ES', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    } catch (error) {
        return timestamp;
    }
}

// Cleanup al cerrar/recargar página
window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
});
