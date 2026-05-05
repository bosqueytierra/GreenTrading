-- =============================================================================
-- TABLA: smc_tendency_h1_m15_setups
-- =============================================================================
-- Estrategia: SMC_TENDENCY_H1_M15
-- Descripción: Tabla exclusiva para estrategia que valida SOLO H1 + evento M15
-- Fecha: 2026-05-05
-- =============================================================================

-- Crear tabla con misma estructura que smc_m15_setups
CREATE TABLE IF NOT EXISTS public.smc_tendency_h1_m15_setups (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    tipo_indice TEXT NOT NULL, -- 'BOOM' o 'CRASH'
    direccion TEXT NOT NULL, -- 'ALCISTA' o 'BAJISTA'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    fecha_detectada TIMESTAMPTZ NOT NULL,
    zona_desde DOUBLE PRECISION NOT NULL,
    zona_hasta DOUBLE PRECISION NOT NULL,
    zona_size_puntos DOUBLE PRECISION NOT NULL,
    precio_actual_detectado DOUBLE PRECISION,
    precio_entrada_referencia DOUBLE PRECISION,
    score INTEGER DEFAULT 0,
    evento TEXT, -- 'CHOCH_ALCISTA', 'BOS_ALCISTA', 'CHOCH_BAJISTA', 'BOS_BAJISTA'
    ob BOOLEAN DEFAULT FALSE,
    fvg BOOLEAN DEFAULT FALSE,
    barrida BOOLEAN DEFAULT FALSE,
    estado TEXT NOT NULL DEFAULT 'ACTIVA', -- 'ACTIVA', 'EN_ZONA', 'PROFIT', 'PAUSADA', 'TP', 'SL'
    tp_price DOUBLE PRECISION,
    sl_price DOUBLE PRECISION,
    ratio_rr DOUBLE PRECISION DEFAULT 1.0,
    max_reaccion_puntos DOUBLE PRECISION DEFAULT 0.0,
    resultado_puntos DOUBLE PRECISION,
    fecha_cierre TIMESTAMPTZ,
    motivo_cierre TEXT,
    tendencia_h1 TEXT, -- Tendencia H1 (usada para validar)
    tendencia_m15 TEXT, -- Tendencia M15 (solo informativa, NO valida)
    strategy TEXT DEFAULT 'SMC_TENDENCY_H1_M15' -- Identificador de estrategia
);

-- Índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_smc_tendency_h1_m15_symbol ON public.smc_tendency_h1_m15_setups(symbol);
CREATE INDEX IF NOT EXISTS idx_smc_tendency_h1_m15_estado ON public.smc_tendency_h1_m15_setups(estado);
CREATE INDEX IF NOT EXISTS idx_smc_tendency_h1_m15_created_at ON public.smc_tendency_h1_m15_setups(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_smc_tendency_h1_m15_tipo_indice ON public.smc_tendency_h1_m15_setups(tipo_indice);
CREATE INDEX IF NOT EXISTS idx_smc_tendency_h1_m15_strategy ON public.smc_tendency_h1_m15_setups(strategy);

-- Trigger para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_smc_tendency_h1_m15_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_smc_tendency_h1_m15_updated_at
    BEFORE UPDATE ON public.smc_tendency_h1_m15_setups
    FOR EACH ROW
    EXECUTE FUNCTION update_smc_tendency_h1_m15_updated_at();

-- =============================================================================
-- POLÍTICAS RLS (Row Level Security)
-- =============================================================================
-- Habilitar RLS
ALTER TABLE public.smc_tendency_h1_m15_setups ENABLE ROW LEVEL SECURITY;

-- Política para lectura (SELECT)
CREATE POLICY "Enable read access for all users"
    ON public.smc_tendency_h1_m15_setups
    FOR SELECT
    USING (true);

-- Política para inserción (INSERT)
CREATE POLICY "Enable insert access for all users"
    ON public.smc_tendency_h1_m15_setups
    FOR INSERT
    WITH CHECK (true);

-- Política para actualización (UPDATE)
CREATE POLICY "Enable update access for all users"
    ON public.smc_tendency_h1_m15_setups
    FOR UPDATE
    USING (true)
    WITH CHECK (true);

-- Política para eliminación (DELETE) - opcional, comentar si no se necesita
-- CREATE POLICY "Enable delete access for all users"
--     ON public.smc_tendency_h1_m15_setups
--     FOR DELETE
--     USING (true);

-- =============================================================================
-- COMENTARIOS SOBRE LA TABLA
-- =============================================================================

COMMENT ON TABLE public.smc_tendency_h1_m15_setups IS 
'Estrategia SMC_TENDENCY_H1_M15: Valida zonas con H1 trend + M15 event. 
NO valida M15 trend (solo informativa). 
NO guarda registros DESCARTADA.';

COMMENT ON COLUMN public.smc_tendency_h1_m15_setups.tendencia_h1 IS 
'Tendencia H1 - USADA PARA VALIDAR zona (BOOM=ALCISTA, CRASH=BAJISTA)';

COMMENT ON COLUMN public.smc_tendency_h1_m15_setups.tendencia_m15 IS 
'Tendencia M15 - SOLO INFORMATIVA, NO se usa para validar zona';

COMMENT ON COLUMN public.smc_tendency_h1_m15_setups.evento IS 
'Evento M15 - USADO PARA VALIDAR zona junto con H1 (CHOCH/BOS alcista/bajista)';

COMMENT ON COLUMN public.smc_tendency_h1_m15_setups.estado IS 
'Estados: ACTIVA, EN_ZONA, PROFIT, PAUSADA, TP, SL. 
NO usa DESCARTADA (zonas inválidas no se guardan).';

COMMENT ON COLUMN public.smc_tendency_h1_m15_setups.strategy IS 
'Identificador de estrategia. Siempre debe ser SMC_TENDENCY_H1_M15';

-- =============================================================================
-- VERIFICACIÓN
-- =============================================================================

-- Verificar que la tabla se creó correctamente
SELECT 
    table_name,
    table_type
FROM information_schema.tables 
WHERE table_schema = 'public' 
    AND table_name = 'smc_tendency_h1_m15_setups';

-- Verificar columnas
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
    AND table_name = 'smc_tendency_h1_m15_setups'
ORDER BY ordinal_position;

-- Verificar índices
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'smc_tendency_h1_m15_setups';

-- Verificar políticas RLS
SELECT 
    policyname,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE tablename = 'smc_tendency_h1_m15_setups';

-- =============================================================================
-- CONSULTAS DE EJEMPLO
-- =============================================================================

-- Ver todas las zonas activas
SELECT * FROM public.smc_tendency_h1_m15_setups 
WHERE estado = 'ACTIVA' 
ORDER BY created_at DESC;

-- Contar zonas por estado
SELECT estado, COUNT(*) 
FROM public.smc_tendency_h1_m15_setups 
GROUP BY estado 
ORDER BY COUNT(*) DESC;

-- Verificar que NO hay registros DESCARTADA (debe retornar 0)
SELECT COUNT(*) FROM public.smc_tendency_h1_m15_setups 
WHERE estado = 'DESCARTADA';

-- Ver zonas BOOM (deben tener H1 ALCISTA y evento ALCISTA)
SELECT symbol, tendencia_h1, evento, estado 
FROM public.smc_tendency_h1_m15_setups 
WHERE tipo_indice = 'BOOM' 
ORDER BY created_at DESC 
LIMIT 10;

-- Ver zonas CRASH (deben tener H1 BAJISTA y evento BAJISTA)
SELECT symbol, tendencia_h1, evento, estado 
FROM public.smc_tendency_h1_m15_setups 
WHERE tipo_indice = 'CRASH' 
ORDER BY created_at DESC 
LIMIT 10;

-- Winrate general
SELECT 
    COUNT(CASE WHEN estado = 'TP' THEN 1 END) as tp_count,
    COUNT(CASE WHEN estado = 'SL' THEN 1 END) as sl_count,
    ROUND(
        COUNT(CASE WHEN estado = 'TP' THEN 1 END)::NUMERIC / 
        NULLIF(
            COUNT(CASE WHEN estado IN ('TP', 'SL') THEN 1 END), 0
        ) * 100, 
        2
    ) as winrate_percent
FROM public.smc_tendency_h1_m15_setups;

-- =============================================================================
-- LIMPIEZA (Usar solo si necesitas recrear la tabla)
-- =============================================================================

-- ⚠️ CUIDADO: Esto borrará todos los datos
-- DROP TABLE IF EXISTS public.smc_tendency_h1_m15_setups CASCADE;
