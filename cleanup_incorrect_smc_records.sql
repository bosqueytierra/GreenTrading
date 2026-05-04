-- =============================================================================
-- SCRIPT DE LIMPIEZA: Registros Incorrectos en smc_m15_setups
-- =============================================================================
-- Este script ayuda a identificar y eliminar registros que fueron creados
-- incorrectamente en la tabla smc_m15_setups cuando el sistema intentaba
-- usar la estrategia H1+M15 sin validación.
--
-- IMPORTANTE: 
-- 1. HACER BACKUP ANTES DE EJECUTAR
-- 2. REVISAR registros a eliminar ANTES de ejecutar DELETE
-- 3. Ajustar la fecha según cuándo se implementó la estrategia H1+M15
-- =============================================================================

-- =============================================================================
-- PASO 1: CREAR BACKUP
-- =============================================================================

CREATE TABLE IF NOT EXISTS smc_m15_setups_backup_20260504 AS 
SELECT * FROM public.smc_m15_setups;

-- Verificar backup
SELECT 
    COUNT(*) as total_respaldado,
    MIN(created_at) as fecha_mas_antigua,
    MAX(created_at) as fecha_mas_reciente
FROM smc_m15_setups_backup_20260504;


-- =============================================================================
-- PASO 2: IDENTIFICAR REGISTROS INCORRECTOS
-- =============================================================================

-- Nota: Los registros incorrectos son aquellos que:
-- 1. Fueron creados después de implementar H1+M15 (ajustar fecha)
-- 2. NO cumplen la validación H1+M15:
--    - Boom indices con H1 BAJISTA o eventos BAJISTAS
--    - Crash indices con H1 ALCISTA o eventos ALCISTAS

-- 2.1 Registros BOOM incorrectos
SELECT 
    id,
    symbol,
    direccion,
    tendencia_h1,
    evento,
    estado,
    created_at,
    CASE 
        WHEN tendencia_h1 = 'BAJISTA' THEN 'H1 BAJISTA (debería ser ALCISTA)'
        WHEN evento LIKE '%BAJISTA%' THEN 'Evento BAJISTA (debería ser ALCISTA)'
        ELSE 'Otro motivo'
    END as razon_incorrecta
FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%'
  AND created_at > '2026-05-01'  -- AJUSTAR FECHA según implementación
  AND (
    tendencia_h1 = 'BAJISTA' 
    OR evento LIKE '%BAJISTA%'
  )
ORDER BY created_at DESC;

-- 2.2 Registros CRASH incorrectos
SELECT 
    id,
    symbol,
    direccion,
    tendencia_h1,
    evento,
    estado,
    created_at,
    CASE 
        WHEN tendencia_h1 = 'ALCISTA' THEN 'H1 ALCISTA (debería ser BAJISTA)'
        WHEN evento LIKE '%ALCISTA%' THEN 'Evento ALCISTA (debería ser BAJISTA)'
        ELSE 'Otro motivo'
    END as razon_incorrecta
FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%'
  AND created_at > '2026-05-01'  -- AJUSTAR FECHA según implementación
  AND (
    tendencia_h1 = 'ALCISTA'
    OR evento LIKE '%ALCISTA%'
  )
ORDER BY created_at DESC;

-- 2.3 Resumen de registros a eliminar
SELECT 
    'TOTAL' as tipo,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE created_at > '2026-05-01'
  AND (
    (symbol LIKE 'Boom%' AND (tendencia_h1 = 'BAJISTA' OR evento LIKE '%BAJISTA%'))
    OR
    (symbol LIKE 'Crash%' AND (tendencia_h1 = 'ALCISTA' OR evento LIKE '%ALCISTA%'))
  )
UNION ALL
SELECT 
    'BOOM incorrectos' as tipo,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%'
  AND created_at > '2026-05-01'
  AND (tendencia_h1 = 'BAJISTA' OR evento LIKE '%BAJISTA%')
UNION ALL
SELECT 
    'CRASH incorrectos' as tipo,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%'
  AND created_at > '2026-05-01'
  AND (tendencia_h1 = 'ALCISTA' OR evento LIKE '%ALCISTA%');


-- =============================================================================
-- PASO 3: ELIMINAR REGISTROS INCORRECTOS
-- =============================================================================
-- ⚠️ IMPORTANTE: REVISAR LOS RESULTADOS DEL PASO 2 ANTES DE EJECUTAR
-- ⚠️ ASEGURARSE DE QUE EL BACKUP SE CREÓ CORRECTAMENTE
-- =============================================================================

-- 3.1 Eliminar registros BOOM incorrectos
-- DESCOMENTAR CUANDO ESTÉS SEGURO:
/*
DELETE FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%'
  AND created_at > '2026-05-01'  -- AJUSTAR FECHA
  AND (
    tendencia_h1 = 'BAJISTA' 
    OR evento LIKE '%BAJISTA%'
  );
*/

-- 3.2 Eliminar registros CRASH incorrectos
-- DESCOMENTAR CUANDO ESTÉS SEGURO:
/*
DELETE FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%'
  AND created_at > '2026-05-01'  -- AJUSTAR FECHA
  AND (
    tendencia_h1 = 'ALCISTA'
    OR evento LIKE '%ALCISTA%'
  );
*/


-- =============================================================================
-- PASO 4: VERIFICAR LIMPIEZA
-- =============================================================================

-- 4.1 Verificar que no quedan registros incorrectos
SELECT 
    'BOOM con problemas' as tipo,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%'
  AND (tendencia_h1 = 'BAJISTA' OR evento LIKE '%BAJISTA%')
UNION ALL
SELECT 
    'CRASH con problemas' as tipo,
    COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%'
  AND (tendencia_h1 = 'ALCISTA' OR evento LIKE '%ALCISTA%');
-- Ambos deben ser 0

-- 4.2 Verificar registros totales después de limpieza
SELECT 
    COUNT(*) as total_actual,
    COUNT(CASE WHEN estado = 'ACTIVA' THEN 1 END) as activas,
    COUNT(CASE WHEN estado = 'EN_ZONA' THEN 1 END) as en_zona,
    COUNT(CASE WHEN estado = 'PROFIT' THEN 1 END) as profit,
    COUNT(CASE WHEN estado = 'TP' THEN 1 END) as tp,
    COUNT(CASE WHEN estado = 'SL' THEN 1 END) as sl,
    COUNT(CASE WHEN estado = 'PAUSADA' THEN 1 END) as pausada,
    COUNT(CASE WHEN estado = 'DESCARTADA' THEN 1 END) as descartada
FROM public.smc_m15_setups;


-- =============================================================================
-- PASO 5 (OPCIONAL): RESTAURAR DESDE BACKUP SI ALGO SALIÓ MAL
-- =============================================================================

-- Si necesitas restaurar el backup:
-- ⚠️ ESTO SOBRESCRIBIRÁ LA TABLA ACTUAL
/*
DROP TABLE public.smc_m15_setups;

CREATE TABLE public.smc_m15_setups AS 
SELECT * FROM smc_m15_setups_backup_20260504;

-- Recrear índices y constraints según sea necesario
-- (ver DATABASE_MIGRATION.md para detalles)
*/


-- =============================================================================
-- CONSULTAS ÚTILES ADICIONALES
-- =============================================================================

-- Verificar estado actual de ambas tablas
SELECT 
    'smc_m15_setups' as tabla,
    COUNT(*) as total,
    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as ultimas_24h
FROM public.smc_m15_setups
UNION ALL
SELECT 
    'smc_h1_m15_setups' as tabla,
    COUNT(*) as total,
    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as ultimas_24h
FROM public.smc_h1_m15_setups;

-- Verificar registros recientes por símbolo
SELECT 
    symbol,
    COUNT(*) as total,
    MAX(created_at) as ultimo_registro
FROM public.smc_m15_setups
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY symbol
ORDER BY symbol;

-- Verificar integridad de validación H1+M15
-- (Todos estos deben retornar 0 filas)
SELECT 'BOOM con tendencia H1 incorrecta' as problema, COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Boom%' AND tendencia_h1 IS NOT NULL AND tendencia_h1 != 'ALCISTA'
UNION ALL
SELECT 'BOOM con evento M15 incorrecto' as problema, COUNT(*) as cantidad
FROM public.smc_m15_setups  
WHERE symbol LIKE 'Boom%' AND evento LIKE '%BAJISTA%'
UNION ALL
SELECT 'CRASH con tendencia H1 incorrecta' as problema, COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%' AND tendencia_h1 IS NOT NULL AND tendencia_h1 != 'BAJISTA'
UNION ALL
SELECT 'CRASH con evento M15 incorrecto' as problema, COUNT(*) as cantidad
FROM public.smc_m15_setups
WHERE symbol LIKE 'Crash%' AND evento LIKE '%ALCISTA%';
