#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run Processors - Script principal para ejecutar procesadores backend

Este script ejecuta los procesadores de estrategias SMC cada 60 segundos:
1. processor_smc_m15_pro.py - Procesa SMC M15 PRO
2. processor_smc_tendency_h1_m15.py - Procesa SMC_TENDENCY_H1_M15

IMPORTANTE:
- NO depende del dashboard abierto
- Corre independientemente del navegador
- Los procesadores leen desde public.market_candles
- Cada procesador escribe en su tabla específica
- Frontend SOLO lee y visualiza

Uso:
    python run_processors.py

Para detener:
    Presiona Ctrl+C
"""

import time
import sys
from datetime import datetime

# Importar funciones de procesamiento
try:
    from processor_smc_m15_pro import process_all_symbols as process_m15_pro
    from processor_smc_tendency_h1_m15 import process_all_symbols as process_tendency_h1_m15
except ImportError as e:
    print(f"❌ ERROR: No se pudieron importar los procesadores: {e}")
    print("   Asegúrate de que los archivos processor_smc_m15_pro.py y processor_smc_tendency_h1_m15.py existen.")
    sys.exit(1)

# Configuración
INTERVAL_SECONDS = 60  # 1 minuto entre ejecuciones

def run_cycle():
    """
    Ejecuta un ciclo completo de procesamiento.
    Corre ambos procesadores en secuencia.
    """
    print("\n" + "="*70)
    print(f" CICLO DE PROCESAMIENTO - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Procesar SMC M15 PRO
    print("\n📊 Ejecutando: SMC M15 PRO")
    print("─"*70)
    try:
        process_m15_pro()
    except Exception as e:
        print(f"❌ Error en SMC M15 PRO: {e}")
        import traceback
        traceback.print_exc()
    
    # Procesar SMC_TENDENCY_H1_M15
    print("\n📊 Ejecutando: SMC_TENDENCY_H1_M15")
    print("─"*70)
    try:
        process_tendency_h1_m15()
    except Exception as e:
        print(f"❌ Error en SMC_TENDENCY_H1_M15: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print(" CICLO COMPLETADO")
    print("="*70)


def main():
    """Loop principal: ejecuta ciclos cada INTERVAL_SECONDS"""
    print("="*70)
    print(" RUN PROCESSORS - Backend Processors Runner")
    print("="*70)
    print(" Procesadores:")
    print("   1. SMC M15 PRO        → smc_m15_setups")
    print("   2. SMC_TENDENCY_H1_M15 → smc_tendency_h1_m15_setups")
    print()
    print(f" Intervalo: {INTERVAL_SECONDS} segundos")
    print(f" Fuente: public.market_candles")
    print("="*70)
    print("\nPresiona Ctrl+C para detener\n")
    
    ciclo = 0
    
    while True:
        try:
            ciclo += 1
            print(f"\n{'#'*70}")
            print(f"# CICLO #{ciclo}")
            print(f"{'#'*70}")
            
            # Ejecutar ciclo de procesamiento
            run_cycle()
            
            # Esperar antes del próximo ciclo
            print(f"\n⏰ Próximo ciclo en {INTERVAL_SECONDS} segundos...")
            print(f"   (Presiona Ctrl+C para detener)")
            time.sleep(INTERVAL_SECONDS)
        
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print(" 👋 Procesadores detenidos por usuario")
            print("="*70)
            break
        
        except Exception as e:
            print(f"\n❌ Error en ciclo #{ciclo}: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n⏰ Reintentando en {INTERVAL_SECONDS} segundos...")
            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
