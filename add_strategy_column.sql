-- Migration script to add strategy column to setup tables
-- This prevents race conditions where global currentStrategy changes affect setup evaluation

-- Add strategy column to smc_m15_setups table
ALTER TABLE public.smc_m15_setups 
ADD COLUMN IF NOT EXISTS strategy VARCHAR(50) DEFAULT 'SMC_M15_PRO';

-- Update existing records in smc_m15_setups to have the correct strategy
UPDATE public.smc_m15_setups 
SET strategy = 'SMC_M15_PRO' 
WHERE strategy IS NULL;

-- Add strategy column to smc_h1_m15_setups table
ALTER TABLE public.smc_h1_m15_setups 
ADD COLUMN IF NOT EXISTS strategy VARCHAR(50) DEFAULT 'SMC_H1_M15_PRO';

-- Update existing records in smc_h1_m15_setups to have the correct strategy
UPDATE public.smc_h1_m15_setups 
SET strategy = 'SMC_H1_M15_PRO' 
WHERE strategy IS NULL;

-- Create index for better query performance
CREATE INDEX IF NOT EXISTS idx_smc_m15_setups_strategy ON public.smc_m15_setups(strategy);
CREATE INDEX IF NOT EXISTS idx_smc_h1_m15_setups_strategy ON public.smc_h1_m15_setups(strategy);

-- Verification queries
-- Check smc_m15_setups records
SELECT 
    strategy,
    COUNT(*) as total_records,
    COUNT(CASE WHEN estado = 'DESCARTADA' THEN 1 END) as descartadas,
    COUNT(CASE WHEN estado = 'PAUSADA' THEN 1 END) as pausadas
FROM public.smc_m15_setups
GROUP BY strategy;

-- Check smc_h1_m15_setups records
SELECT 
    strategy,
    COUNT(*) as total_records,
    COUNT(CASE WHEN estado = 'DESCARTADA' THEN 1 END) as descartadas,
    COUNT(CASE WHEN estado = 'PAUSADA' THEN 1 END) as pausadas
FROM public.smc_h1_m15_setups
GROUP BY strategy;

-- Verify that no SMC_M15_PRO zones have DESCARTADA with context change reasons
SELECT 
    id,
    symbol,
    estado,
    motivo_cierre,
    strategy
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA' 
  AND strategy = 'SMC_M15_PRO'
  AND (
    motivo_cierre LIKE '%Contexto H1%' 
    OR motivo_cierre LIKE '%Contexto M15%'
    OR motivo_cierre LIKE '%Evento M15%'
  )
ORDER BY fecha_cierre DESC
LIMIT 20;
