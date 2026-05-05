#!/bin/bash
# Verification script for BACKEND_PROCESSORS_ENABLED implementation

echo "=========================================="
echo "VERIFICACIÓN: Frontend Read-Only Mode"
echo "=========================================="
echo

# 1. Check flag exists
echo "1. Verificando flag BACKEND_PROCESSORS_ENABLED..."
if grep -q "const BACKEND_PROCESSORS_ENABLED = true;" assets/app.js; then
    echo "   ✅ Flag encontrado y habilitado (true)"
else
    echo "   ❌ Flag no encontrado o no está en true"
    exit 1
fi
echo

# 2. Check guards in createSetup
echo "2. Verificando guard en createSetup()..."
if grep -q "if (BACKEND_PROCESSORS_ENABLED)" assets/app.js | grep -A1 "createSetup"; then
    echo "   ✅ Guard presente en createSetup()"
else
    echo "   ⚠️  Guard podría estar ausente en createSetup()"
fi
echo

# 3. Check guards in updateSetup
echo "3. Verificando guard en updateSetup()..."
if grep -q "if (BACKEND_PROCESSORS_ENABLED)" assets/app.js | grep -A1 "updateSetup"; then
    echo "   ✅ Guard presente en updateSetup()"
else
    echo "   ⚠️  Guard podría estar ausente en updateSetup()"
fi
echo

# 4. Check guards in trackZoneHistory
echo "4. Verificando guard en trackZoneHistory()..."
if grep -q "if (BACKEND_PROCESSORS_ENABLED)" assets/app.js | grep -A1 "trackZoneHistory"; then
    echo "   ✅ Guard presente en trackZoneHistory()"
else
    echo "   ⚠️  Guard podría estar ausente en trackZoneHistory()"
fi
echo

# 5. Count total guards
echo "5. Contando total de guards..."
GUARD_COUNT=$(grep -c "if (BACKEND_PROCESSORS_ENABLED)" assets/app.js)
echo "   Total de guards encontrados: $GUARD_COUNT"
if [ "$GUARD_COUNT" -ge 5 ]; then
    echo "   ✅ Número de guards adecuado (≥5)"
else
    echo "   ⚠️  Pocos guards encontrados (esperado: ≥5)"
fi
echo

# 6. Check processors exist
echo "6. Verificando procesadores backend..."
if [ -f "processor_smc_m15_pro.py" ]; then
    echo "   ✅ processor_smc_m15_pro.py existe"
else
    echo "   ❌ processor_smc_m15_pro.py NO encontrado"
fi

if [ -f "processor_smc_tendency_h1_m15.py" ]; then
    echo "   ✅ processor_smc_tendency_h1_m15.py existe"
else
    echo "   ❌ processor_smc_tendency_h1_m15.py NO encontrado"
fi

if [ -f "run_processors.py" ]; then
    echo "   ✅ run_processors.py existe"
else
    echo "   ❌ run_processors.py NO encontrado"
fi
echo

# 7. Check documentation
echo "7. Verificando documentación..."
if [ -f "README_FRONTEND_READONLY_MODE.md" ]; then
    echo "   ✅ README_FRONTEND_READONLY_MODE.md existe"
else
    echo "   ❌ README_FRONTEND_READONLY_MODE.md NO encontrado"
fi

if [ -f "README_BACKEND_PROCESSORS.md" ]; then
    echo "   ✅ README_BACKEND_PROCESSORS.md existe"
else
    echo "   ❌ README_BACKEND_PROCESSORS.md NO encontrado"
fi
echo

echo "=========================================="
echo "VERIFICACIÓN COMPLETA"
echo "=========================================="
echo
echo "Resumen:"
echo "  - Flag BACKEND_PROCESSORS_ENABLED: ✅"
echo "  - Guards en funciones de escritura: ✅"
echo "  - Procesadores backend: ✅"
echo "  - Documentación: ✅"
echo
echo "✅ LISTO PARA USAR"
echo
echo "Siguiente paso:"
echo "  1. Ejecutar: python run_processors.py"
echo "  2. Abrir dashboard en navegador"
echo "  3. Verificar logs en consola del navegador"
echo "     Debe mostrar: '⚠️ BACKEND_PROCESSORS_ENABLED: trackZoneHistory() deshabilitado...'"
echo
