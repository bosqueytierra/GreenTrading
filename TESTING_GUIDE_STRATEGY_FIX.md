# Testing Guide for Strategy Field Fix

## Pre-deployment Checklist

### 1. Execute SQL Migration
**CRITICAL: Run this BEFORE deploying the JavaScript changes**

```sql
-- In Supabase SQL Editor, execute:
-- File: add_strategy_column.sql
```

This will:
- Add `strategy` column to both tables
- Set default values for existing records
- Create performance indexes

### 2. Verify Migration Success

```sql
-- Check column was added
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name IN ('smc_m15_setups', 'smc_h1_m15_setups')
  AND column_name = 'strategy';
```

Expected output: 2 rows (one per table)

## Post-deployment Testing

### Test 1: New Zones Get Strategy Field

**Steps:**
1. Open application
2. Navigate to SMC M15 PRO tab
3. Wait for a new zone to be detected
4. Query database:

```sql
SELECT id, symbol, estado, strategy, created_at
FROM public.smc_m15_setups
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 5;
```

**Expected:** All new records have `strategy = 'SMC_M15_PRO'`

### Test 2: Tab Switch Doesn't Affect Existing Zones

**Steps:**
1. Open application in SMC M15 PRO tab
2. Note some PAUSADA zones (if any exist)
3. Switch to SMC H1+M15 PRO tab
4. Wait for 2-3 auto-refresh cycles (60-90 seconds)
5. Switch back to SMC M15 PRO tab
6. Check if PAUSADA zones are still there (not DESCARTADA)

**Query to verify:**
```sql
-- Check recent DESCARTADAS in SMC M15 PRO
SELECT id, symbol, estado, motivo_cierre, strategy, fecha_cierre
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '2 hours'
ORDER BY fecha_cierre DESC;
```

**Expected:** 
- No new DESCARTADAS with motivo_cierre containing "Contexto H1", "Contexto M15", or "Evento M15"
- Only DESCARTADAS with motivo_cierre = "Precio tocó SL de zona pausada"

### Test 3: PAUSADA Zones Only Discarded by SL

**Steps:**
1. Find a PAUSADA zone in SMC M15 PRO
2. Note its SL price
3. Wait for price to touch SL
4. Verify zone becomes DESCARTADA with correct reason

**Query:**
```sql
SELECT id, symbol, direccion, sl_price, estado, motivo_cierre
FROM public.smc_m15_setups
WHERE estado = 'PAUSADA'
  AND strategy = 'SMC_M15_PRO'
ORDER BY created_at DESC
LIMIT 10;
```

**Expected:**
- Zone stays PAUSADA until SL is hit
- When SL hit: estado = 'DESCARTADA', motivo_cierre = 'Precio tocó SL de zona pausada'

### Test 4: H1+M15 Strategy Still Works Correctly

**Steps:**
1. Switch to SMC H1+M15 PRO tab
2. Verify zones there can be discarded for context changes
3. Query:

```sql
SELECT 
    motivo_cierre,
    COUNT(*) as cantidad
FROM public.smc_h1_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_H1_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '24 hours'
GROUP BY motivo_cierre;
```

**Expected:**
- Various motivo_cierre including:
  - "Contexto H1 cambió contra la zona" ✅
  - "Contexto M15 cambió contra la zona" ✅
  - "Evento M15 dejó de tener sentido para la zona" ✅
  - "Precio tocó SL de zona pausada" ✅

### Test 5: Cross-Strategy Isolation

**Scenario:** Both strategies running simultaneously

**Steps:**
1. Open two browser tabs/windows
2. Tab 1: SMC M15 PRO
3. Tab 2: SMC H1+M15 PRO
4. Let both run for 10-15 minutes
5. Check both tables:

```sql
-- SMC M15 PRO - should have no context-based DESCARTADAS
SELECT COUNT(*) as incorrect_descartadas
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '1 hour'
  AND (
    motivo_cierre LIKE '%Contexto H1%' 
    OR motivo_cierre LIKE '%Contexto M15%'
    OR motivo_cierre LIKE '%Evento M15%'
  );

-- SMC H1+M15 PRO - can have context-based DESCARTADAS
SELECT COUNT(*) as context_descartadas
FROM public.smc_h1_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_H1_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '1 hour'
  AND (
    motivo_cierre LIKE '%Contexto H1%' 
    OR motivo_cierre LIKE '%Contexto M15%'
    OR motivo_cierre LIKE '%Evento M15%'
  );
```

**Expected:**
- First query: 0 (no incorrect descartadas in SMC M15 PRO)
- Second query: >= 0 (context-based descartadas are valid in H1+M15 PRO)

## Monitoring Queries

### Daily Monitoring (for first week)

```sql
-- Daily summary of DESCARTADAS by strategy and reason
SELECT 
    DATE(fecha_cierre) as fecha,
    strategy,
    motivo_cierre,
    COUNT(*) as cantidad
FROM (
    SELECT fecha_cierre, strategy, motivo_cierre FROM public.smc_m15_setups
    UNION ALL
    SELECT fecha_cierre, strategy, motivo_cierre FROM public.smc_h1_m15_setups
) combined
WHERE estado = 'DESCARTADA'
  AND fecha_cierre > NOW() - INTERVAL '7 days'
GROUP BY fecha, strategy, motivo_cierre
ORDER BY fecha DESC, strategy, cantidad DESC;
```

### Alert Query (run every hour)

```sql
-- Alert: Incorrect DESCARTADAS in SMC M15 PRO
SELECT 
    id,
    symbol,
    motivo_cierre,
    fecha_cierre
FROM public.smc_m15_setups
WHERE estado = 'DESCARTADA'
  AND strategy = 'SMC_M15_PRO'
  AND fecha_cierre > NOW() - INTERVAL '1 hour'
  AND motivo_cierre NOT LIKE '%SL%'
ORDER BY fecha_cierre DESC;
```

**Expected:** 0 rows always

If this returns rows, the fix is not working correctly.

## Rollback Plan

If issues are detected:

1. **Emergency Rollback:**
   ```bash
   git revert HEAD~2  # Revert both commits
   git push origin copilot/smc-m15-pro-fix-close-setup-usage
   ```

2. **Keep SQL changes** (they're harmless and will be used when fix is corrected)

3. **Investigate** why setup.strategy is not being set or read correctly

## Success Criteria

✅ Fix is successful if after 48 hours:

1. Zero SMC M15 PRO zones with DESCARTADA + context change reasons (created after deployment)
2. All new setups have `strategy` field populated
3. PAUSADA zones in SMC M15 PRO only become DESCARTADA when SL is hit
4. SMC H1+M15 PRO strategy still functions normally with all validation rules

## Contact

If any tests fail or unexpected behavior is observed:
- Check browser console for JavaScript errors
- Check application logs for errors in `reevaluatePausedZone`
- Verify SQL migration was executed successfully
- Confirm that new setups have `strategy` field set

## Additional Verification

### Browser Console Tests

Open browser DevTools console and run:

```javascript
// Check that STRATEGIES constant is defined
console.log(STRATEGIES);

// Check current strategy
console.log('Current Strategy:', currentStrategy);

// After creating a new zone, check if it has strategy field
// (This would need to be checked by inspecting network requests to Supabase)
```

### Network Tab Verification

1. Open DevTools Network tab
2. Filter by "supabase"
3. Create a new zone
4. Find POST request to smc_m15_setups or smc_h1_m15_setups
5. Check request payload includes `"strategy": "SMC_M15_PRO"` or similar
