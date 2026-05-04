-- ============================================================================
-- LIMPIEZA DE REGISTROS INCORRECTOS EN smc_m15_setups
-- ============================================================================
-- 
-- Este script identifica y elimina registros que fueron insertados incorrectamente
-- en la tabla smc_m15_setups pero que pertenecen a la estrategia H1+M15.
--
-- La estrategia "SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)" debe usar SOLO smc_h1_m15_setups.
-- La estrategia "SMC M15 PRO" debe usar SOLO smc_m15_setups.
-- ============================================================================

-- PASO 1: Verificar el estado actual
-- ============================================================================

-- Ver registros con estrategia H1+M15 en smc_m15_setups (INCORRECTO)
SELECT 
    'smc_m15_setups (INCORRECTO)' as tabla,
    COUNT(*) as total_registros,
    MIN(fecha_detectada) as fecha_mas_antigua,
    MAX(fecha_detectada) as fecha_mas_reciente
FROM public.smc_m15_setups
WHERE estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)'
   OR tendencia_h1 IS NOT NULL;  -- Solo H1+M15 tiene tendencia_h1

-- Ver registros correctos en smc_h1_m15_setups
SELECT 
    'smc_h1_m15_setups (CORRECTO)' as tabla,
    COUNT(*) as total_registros,
    MIN(fecha_detectada) as fecha_mas_antigua,
    MAX(fecha_detectada) as fecha_mas_reciente
FROM public.smc_h1_m15_setups
WHERE estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)';


-- PASO 2: Listar registros incorrectos con detalle
-- ============================================================================

-- Registros incorrectos en smc_m15_setups que tienen campos de H1+M15
SELECT 
    id,
    symbol,
    direccion,
    fecha_detectada,
    estado,
    estrategia,
    tendencia_h1,
    tendencia_m15
FROM public.smc_m15_setups
WHERE estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)'
   OR tendencia_h1 IS NOT NULL
ORDER BY fecha_detectada DESC;


-- PASO 3: Verificar filtro H1+M15 (Boom ALCISTA, Crash BAJISTA)
-- ============================================================================

-- Registros con filtro H1+M15 aplicado (estos son de la nueva estrategia)
-- Boom con H1 ALCISTA y evento M15 ALCISTA
-- Crash con H1 BAJISTA y evento M15 BAJISTA
SELECT 
    id,
    symbol,
    direccion,
    fecha_detectada,
    tendencia_h1,
    tendencia_m15,
    evento,
    estado
FROM public.smc_m15_setups
WHERE 
    (
        -- Boom con filtro H1+M15 (H1 ALCISTA + evento M15 ALCISTA)
        (symbol LIKE '%Boom%' AND tendencia_h1 = 'ALCISTA' AND evento LIKE '%ALCISTA%')
        OR
        -- Crash con filtro H1+M15 (H1 BAJISTA + evento M15 BAJISTA)
        (symbol LIKE '%Crash%' AND tendencia_h1 = 'BAJISTA' AND evento LIKE '%BAJISTA%')
    )
ORDER BY fecha_detectada DESC;


-- PASO 4: LIMPIEZA - Eliminar registros incorrectos
-- ============================================================================
-- ⚠️ IMPORTANTE: Ejecutar solo después de verificar los pasos 1-3
-- ⚠️ Hacer backup antes de ejecutar: pg_dump o exportar registros

-- Opción A: Eliminar registros con estrategia H1+M15 en tabla incorrecta
BEGIN;

DELETE FROM public.smc_m15_setups
WHERE estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)';

-- Verificar cuántos registros se eliminarán antes de hacer COMMIT
SELECT COUNT(*) as registros_eliminados FROM public.smc_m15_setups WHERE false; -- Esta query no borra nada

-- Si todo está bien, hacer COMMIT. Si no, hacer ROLLBACK
-- COMMIT;
ROLLBACK; -- Descomenta COMMIT y comenta ROLLBACK cuando estés seguro


-- Opción B: Eliminar registros que tienen tendencia_h1 (campo exclusivo de H1+M15)
BEGIN;

DELETE FROM public.smc_m15_setups
WHERE tendencia_h1 IS NOT NULL;

-- Verificar antes de commitear
-- COMMIT;
ROLLBACK;


-- Opción C: Eliminar registros con filtro H1+M15 aplicado
BEGIN;

DELETE FROM public.smc_m15_setups
WHERE 
    (
        (symbol LIKE '%Boom%' AND tendencia_h1 = 'ALCISTA' AND evento LIKE '%ALCISTA%')
        OR
        (symbol LIKE '%Crash%' AND tendencia_h1 = 'BAJISTA' AND evento LIKE '%BAJISTA%')
    );

-- Verificar antes de commitear
-- COMMIT;
ROLLBACK;


-- PASO 5: Verificación post-limpieza
-- ============================================================================

-- Verificar que ya no hay registros H1+M15 en smc_m15_setups
SELECT 
    'POST-LIMPIEZA: smc_m15_setups' as verificacion,
    COUNT(*) as registros_h1_m15_restantes
FROM public.smc_m15_setups
WHERE estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)'
   OR tendencia_h1 IS NOT NULL;
-- Resultado esperado: 0 registros

-- Verificar que smc_h1_m15_setups sigue con sus registros correctos
SELECT 
    'POST-LIMPIEZA: smc_h1_m15_setups' as verificacion,
    COUNT(*) as registros_correctos
FROM public.smc_h1_m15_setups
WHERE estrategia = 'SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)';
-- Estos registros NO se afectan


-- PASO 6: Limpieza adicional - Registros DESCARTADOS antiguos (opcional)
-- ============================================================================

-- Eliminar registros DESCARTADOS con más de 7 días en ambas tablas
-- (Opcional: Solo si quieres limpiar histórico)

-- En smc_m15_setups
DELETE FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND fecha_cierre < NOW() - INTERVAL '7 days';

-- En smc_h1_m15_setups
DELETE FROM public.smc_h1_m15_setups
WHERE estado = 'DESCARTADA'
  AND fecha_cierre < NOW() - INTERVAL '7 days';


-- ============================================================================
-- RESUMEN DE REGLAS
-- ============================================================================
/*

TABLA: smc_m15_setups
- Estrategia: SMC M15 PRO
- Campos: NO debe tener tendencia_h1 (es NULL)
- Filtro: NO aplica filtro H1+M15
- Frontend: Tab "SMC M15 PRO"

TABLA: smc_h1_m15_setups
- Estrategia: SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)
- Campos: DEBE tener tendencia_h1 y tendencia_m15
- Filtro: Boom → H1 ALCISTA + M15 ALCISTA
          Crash → H1 BAJISTA + M15 BAJISTA
- Frontend: Tab "SMC PRO TENDENCIA H1 + CHOCH/BOS (M15)"

*/
