# Quick Start - GreenTrading Desktop Phase 3

## 🚀 Inicio Rápido

### 1. Requisitos Previos
- Node.js y npm instalados
- Python 3.8+ instalado
- MetaTrader 5 instalado y corriendo
- Índices Boom/Crash en Market Watch de MT5

### 2. Instalación (Primera vez)
```bash
cd GreenTrading-Desktop

# Instalar dependencias Python
pip install -r requirements.txt

# Instalar dependencias Node
npm install
```

### 3. Iniciar Aplicación
```bash
npm start
```

## 📊 Dashboard SMC M15 PRO

### Columnas Explicadas

| Columna | Qué Muestra | Ejemplo |
|---------|-------------|---------|
| **ÍNDICE** | Nombre del símbolo | Boom 1000 |
| **TENDENCIA H1** | Tendencia en H1 | ALCISTA / BAJISTA / -- |
| **TENDENCIA M15** | Tendencia en M15 | ALCISTA / BAJISTA / -- |
| **ÚLTIMO EVENTO M15** | Último BOS o CHOCH | BOS ALCISTA |
| **ZONA MADRE M15** | Rango de la zona | 12300.00 - 12320.00 |
| **SCORE** | Calidad del setup (0-10) | 7 🟢 / 5 🟡 / 2 ⚪ |
| **OB** | Order Block presente | SÍ / NO |
| **FVG** | Fair Value Gap presente | SÍ / NO |
| **BARRIDA** | Liquidity Sweep detectado | SÍ / NO |
| **ESTADO** | Estado del setup | ACTIVA / SIN SETUP |
| **PRECIO** | Precio actual MT5 | 12345.67 |
| **ACTUALIZACIÓN** | Última actualización | 14:23:45 |

### Estados

#### ✅ ACTIVA
- Setup válido detectado
- Score mayor a 0
- Zona madre definida
- Al menos una confluencia presente

#### ⚪ SIN SETUP
- Sin setup válido en este momento
- Score = 0
- Esperando nueva estructura
- Puede cambiar en próximo refresh

### Score (Puntaje)

#### 🟢 Alto (7-10)
Setup de alta calidad con múltiples confluencias:
- Tendencias H1 y M15 alineadas
- Evento M15 reciente
- OB + FVG + Barrida presentes

#### 🟡 Medio (4-6)
Setup con confluencias parciales:
- Tendencia H1 definida
- Evento M15 presente
- 1-2 confluencias adicionales

#### ⚪ Bajo (0-3)
Setup débil o sin setup:
- Pocas confluencias
- Sin alineación de tendencias
- Estado: SIN SETUP

### Auto-Refresh

⏱️ **Intervalo: 5 segundos**
- Dashboard actualiza automáticamente
- Sin necesidad de refrescar manualmente
- Badge muestra "Auto-refresh: 5s"

## 🔧 Solución de Problemas

### ❌ Error: "MT5: Desconectado"
**Solución:**
1. Abrir MetaTrader 5
2. Hacer login en tu cuenta
3. Verificar que índices Boom/Crash estén en Market Watch
4. Refrescar dashboard manualmente

### ❌ Error: "Backend not responding"
**Solución:**
1. Cerrar aplicación
2. Verificar que puerto 8765 esté libre
3. Ejecutar `npm start` nuevamente
4. Revisar logs en consola

### ❌ Todos muestran "SIN SETUP"
**Causas posibles:**
1. MT5 recién conectado (esperar siguiente refresh)
2. Mercado sin estructura clara
3. Análisis SMC en progreso (esperar 5s)

### ⚠️ Dashboard lento
**Normal:** Analizar 10 símbolos × 100 velas toma 2-3 segundos
**Optimización:** Reducir símbolos o candle count en código

## 📝 Notas Importantes

### Lo que SÍ hace Phase 3
- ✅ Muestra datos reales de MT5
- ✅ Analiza con motor SMC completo
- ✅ Actualiza cada 5 segundos
- ✅ Calcula scores automáticamente
- ✅ Detecta OB, FVG, Barridas
- ✅ Identifica tendencias H1 y M15

### Lo que NO hace Phase 3
- ❌ NO guarda historial (sin DB)
- ❌ NO rastrea TP/SL
- ❌ NO tiene múltiples estrategias
- ❌ NO almacena setups anteriores
- ❌ NO tiene estados avanzados (EN_ZONA, PROFIT, etc)

## 🎯 Uso Recomendado

1. **Monitoreo en tiempo real:** Dejar abierto para vigilar índices
2. **Identificar setups:** Buscar estado ACTIVA con score alto
3. **Verificar confluencias:** Revisar columnas OB, FVG, BARRIDA
4. **Alineación temporal:** Confirmar H1 y M15 alineados

## 📚 Documentación Adicional

- `PHASE3_SUMMARY.md` - Resumen completo de implementación
- `PHASE3_TESTING.md` - Guía detallada de testing
- `ARCHITECTURE.md` - Arquitectura general
- `README.md` - Información general del proyecto

## 🆘 Soporte

Si encuentras bugs o tienes preguntas:
1. Revisar logs de consola (DevTools en Electron)
2. Verificar logs del backend Python
3. Consultar documentación en `/GreenTrading-Desktop/`

---

**Version:** Phase 3 - SMC M15 PRO Dashboard
**Last Updated:** 2026-05-06
