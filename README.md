# GreenTrading

Trading automation system with real-time web dashboard.

## 🌐 Dashboard Web

Dashboard estático en **GitHub Pages** que muestra datos de trading en tiempo real desde Supabase.

- 📊 Visualización de velas en tiempo real
- 🔄 Auto-refresh cada 30 segundos
- 📱 Diseño responsive y profesional
- 🌙 Tema oscuro
- 🚀 100% estático (HTML + CSS + JavaScript)

👉 **[Ver instrucciones completas del dashboard](README_DASHBOARD.md)**

## 🤖 Sistema de Trading

Bot de trading automatizado que recolecta velas de MetaTrader5 y las almacena en Supabase.

### Componentes:
- `mt5_to_supabase.py` - Recolector de velas MT5 → Supabase
- `master_bot.py` - Bot principal de trading
- `smc_m15_pro.py` - Estrategia SMC
- `web/` - Dashboard web (Flask - legacy)
- `index.html` + `assets/` - Nuevo dashboard estático para GitHub Pages