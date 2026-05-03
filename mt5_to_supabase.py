#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mt5_to_supabase.py
Recolector local de velas de MetaTrader5 que las sube a Supabase.
Se ejecuta en PC local donde está instalado MT5.
Mini app visual para Windows con sistema de bandeja.
"""

import os
import sys
import time
import math
import threading
from datetime import datetime, timezone
import MetaTrader5 as mt5
import pandas as pd
import requests
from dotenv import load_dotenv
import tkinter as tk
from tkinter import scrolledtext

# Verificar dependencias opcionales
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("⚠️  pystray o pillow no están instalados.")
    print("Para habilitar el icono en la bandeja del sistema, instala:")
    print("pip install pystray pillow")
    print("")

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Validar credenciales
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("❌ ERROR: No se encontró SUPABASE_URL o SUPABASE_ANON_KEY en .env")
    sys.exit(1)

# Configuración
SYMBOLS = [
    "Boom 1000 Index",
    "Boom 900 Index",
    "Boom 600 Index",
    "Boom 500 Index",
    "Boom 300 Index",
    "Crash 1000 Index",
    "Crash 900 Index",
    "Crash 600 Index",
    "Crash 500 Index",
    "Crash 300 Index"
]

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1
}

# Configuración de velas por timeframe para carga inicial
INITIAL_CANDLES_BY_TIMEFRAME = {
    "M1": 10000,
    "M15": 2000,
    "H1": 700
}

# Configuración de velas fijas para actualización (cuando hay histórico)
UPDATE_CANDLES_BY_TIMEFRAME = {
    "M1": 20,
    "M15": 10,
    "H1": 5
}

# Configuración de recuperación automática por timeframe
RECOVERY_CONFIG = {
    "M1": {
        "divisor": 1,      # Minutos por vela
        "margen": 20,      # Velas extra de seguridad
        "minimo": 20,      # Mínimo de velas a recuperar
        "maximo": 10000    # Máximo de velas a recuperar
    },
    "M15": {
        "divisor": 15,
        "margen": 10,
        "minimo": 10,
        "maximo": 2000
    },
    "H1": {
        "divisor": 60,
        "margen": 5,
        "minimo": 5,
        "maximo": 700
    }
}

# Intervalo de sincronización (3 minutos)
SYNC_INTERVAL_SECONDS = 180


class CollectorGUI:
    """Interfaz gráfica para el recolector MT5"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GreenTrading - MT5 to Supabase Collector")
        self.root.geometry("900x700")
        self.root.configure(bg="#1e1e1e")
        
        # Estado del recolector
        self.is_paused = False
        self.is_running = True
        self.mt5_connected = False
        self.collector_thread = None
        self.icon = None
        
        # Crear UI
        self.create_ui()
        
        # Configurar eventos de ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Iniciar recolector en thread separado
        self.start_collector_thread()
        
        # Iniciar icono de bandeja si está disponible
        if TRAY_AVAILABLE:
            self.start_tray_icon()
    
    def create_ui(self):
        """Crear interfaz de usuario"""
        
        # Frame superior - Estado
        status_frame = tk.Frame(self.root, bg="#2d2d2d", height=80)
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        status_frame.pack_propagate(False)
        
        # Título
        title_label = tk.Label(
            status_frame,
            text="🌿 GreenTrading Collector",
            font=("Consolas", 16, "bold"),
            bg="#2d2d2d",
            fg="#4CAF50"
        )
        title_label.pack(pady=5)
        
        # Estado
        self.status_label = tk.Label(
            status_frame,
            text="Estado: Iniciando...",
            font=("Consolas", 12),
            bg="#2d2d2d",
            fg="#ffffff"
        )
        self.status_label.pack()
        
        # Frame de botones
        button_frame = tk.Frame(self.root, bg="#1e1e1e")
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Botón Pausar/Reanudar
        self.pause_button = tk.Button(
            button_frame,
            text="⏸ Pausar",
            font=("Consolas", 10, "bold"),
            bg="#FF9800",
            fg="#000000",
            command=self.toggle_pause,
            width=15,
            relief=tk.RAISED,
            bd=2
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        # Botón Minimizar a bandeja
        if TRAY_AVAILABLE:
            minimize_button = tk.Button(
                button_frame,
                text="📍 Minimizar a Bandeja",
                font=("Consolas", 10),
                bg="#2196F3",
                fg="#ffffff",
                command=self.minimize_to_tray,
                width=20,
                relief=tk.RAISED,
                bd=2
            )
            minimize_button.pack(side=tk.LEFT, padx=5)
        
        # Botón Limpiar logs
        clear_button = tk.Button(
            button_frame,
            text="🗑 Limpiar Logs",
            font=("Consolas", 10),
            bg="#607D8B",
            fg="#ffffff",
            command=self.clear_logs,
            width=15,
            relief=tk.RAISED,
            bd=2
        )
        clear_button.pack(side=tk.LEFT, padx=5)
        
        # Área de logs
        log_label = tk.Label(
            self.root,
            text="📋 Logs del Recolector",
            font=("Consolas", 11, "bold"),
            bg="#1e1e1e",
            fg="#4CAF50"
        )
        log_label.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # ScrolledText para logs
        self.log_text = scrolledtext.ScrolledText(
            self.root,
            font=("Consolas", 9),
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Configurar tags para colores
        self.log_text.tag_config("header", foreground="#4CAF50", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("success", foreground="#4CAF50")
        self.log_text.tag_config("error", foreground="#f85149")
        self.log_text.tag_config("warning", foreground="#FFC107")
        self.log_text.tag_config("info", foreground="#58a6ff")
        self.log_text.tag_config("separator", foreground="#30363d")
    
    def log(self, message, tag="info"):
        """Agregar mensaje al log con formato"""
        def append():
            self.log_text.insert(tk.END, message + "\n", tag)
            self.log_text.see(tk.END)
        
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, append)
        else:
            append()
    
    def log_separator(self):
        """Agregar separador visual"""
        self.log("═" * 100, "separator")
    
    def log_cycle_header(self, cycle_num):
        """Agregar encabezado de ciclo"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_separator()
        self.log(f"🔄 CICLO #{cycle_num} - {now}", "header")
        self.log_separator()
    
    def log_index_header(self, symbol):
        """Agregar encabezado de índice"""
        self.log(f"\n┌─ 📊 {symbol} " + "─" * (90 - len(symbol)), "info")
    
    def log_index_footer(self):
        """Agregar pie de índice"""
        self.log("└" + "─" * 95, "info")
    
    def clear_logs(self):
        """Limpiar el área de logs"""
        self.log_text.delete(1.0, tk.END)
        self.log("🗑 Logs limpiados", "info")
    
    def update_status(self, status, color="#ffffff"):
        """Actualizar el estado en la UI"""
        def update():
            self.status_label.config(text=f"Estado: {status}", fg=color)
        
        if threading.current_thread() != threading.main_thread():
            self.root.after(0, update)
        else:
            update()
    
    def toggle_pause(self):
        """Pausar o reanudar el recolector"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self.pause_button.config(text="▶ Reanudar", bg="#4CAF50")
            self.update_status("⏸ Pausado", "#FFC107")
            self.log("\n⏸ Recolector PAUSADO por usuario", "warning")
        else:
            self.pause_button.config(text="⏸ Pausar", bg="#FF9800")
            self.update_status("✅ Conectado", "#4CAF50")
            self.log("▶ Recolector REANUDADO", "success")
    
    def minimize_to_tray(self):
        """Minimizar ventana a la bandeja"""
        if TRAY_AVAILABLE:
            self.root.withdraw()
            self.log("📍 Aplicación minimizada a la bandeja del sistema", "info")
    
    def show_window(self):
        """Mostrar ventana desde la bandeja"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def on_closing(self):
        """Manejar cierre de ventana"""
        if TRAY_AVAILABLE:
            self.minimize_to_tray()
        else:
            self.quit_app()
    
    def quit_app(self):
        """Cerrar completamente la aplicación"""
        self.is_running = False
        self.log("\n⚠️ Cerrando aplicación...", "warning")
        
        # Esperar a que el thread termine
        if self.collector_thread and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=2)
        
        # Cerrar MT5
        mt5.shutdown()
        
        # Detener icono de bandeja
        if self.icon:
            self.icon.stop()
        
        self.root.quit()
        self.root.destroy()
    
    def create_tray_icon(self):
        """Crear imagen para el icono de la bandeja"""
        # Crear un icono simple verde
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), '#4CAF50')
        draw = ImageDraw.Draw(image)
        
        # Dibujar un símbolo de gráfico simple
        draw.rectangle([10, 40, 20, 54], fill='#ffffff')
        draw.rectangle([25, 30, 35, 54], fill='#ffffff')
        draw.rectangle([40, 20, 50, 54], fill='#ffffff')
        
        return image
    
    def start_tray_icon(self):
        """Iniciar icono en la bandeja del sistema"""
        if not TRAY_AVAILABLE:
            return
        
        def run_tray():
            image = self.create_tray_icon()
            
            menu = pystray.Menu(
                pystray.MenuItem("Mostrar Ventana", lambda: self.root.after(0, self.show_window)),
                pystray.MenuItem(
                    "Pausar/Reanudar",
                    lambda: self.root.after(0, self.toggle_pause)
                ),
                pystray.MenuItem("Salir", lambda: self.root.after(0, self.quit_app))
            )
            
            self.icon = pystray.Icon("GreenTrading", image, "GreenTrading Collector", menu)
            self.icon.run()
        
        tray_thread = threading.Thread(target=run_tray, daemon=True)
        tray_thread.start()
    
    def start_collector_thread(self):
        """Iniciar el thread del recolector"""
        self.collector_thread = threading.Thread(target=self.run_collector, daemon=True)
        self.collector_thread.start()
    
    def run_collector(self):
        """Ejecutar el recolector en loop"""
        self.log("🚀 Iniciando GreenTrading Collector...", "header")
        self.log(f"⏱ Intervalo de sincronización: {SYNC_INTERVAL_SECONDS} segundos\n", "info")
        
        # Conectar a MT5
        if not self.connect_mt5():
            self.log("❌ No se pudo conectar a MT5. Verifica que esté instalado y ejecutándose.", "error")
            self.update_status("❌ Error: MT5 no conectado", "#f85149")
            return
        
        self.mt5_connected = True
        self.update_status("✅ Conectado", "#4CAF50")
        
        cycle = 0
        
        try:
            while self.is_running:
                # Si está pausado, esperar
                if self.is_paused:
                    time.sleep(1)
                    continue
                
                cycle += 1
                
                try:
                    self.log_cycle_header(cycle)
                    total_uploaded = self.collect_and_upload()
                    
                    # Resumen del ciclo
                    now = datetime.now().strftime("%H:%M:%S")
                    self.log(f"\n✅ Total de velas subidas: {total_uploaded}", "success")
                    self.log(f"🕐 Hora de finalización: {now}", "info")
                    self.log(f"⏳ Próximo ciclo en {SYNC_INTERVAL_SECONDS} segundos\n", "info")
                    
                except Exception as e:
                    self.log(f"\n⚠️ Error en ciclo #{cycle}: {e}", "error")
                    self.update_status("⚠️ Error en ciclo", "#FFC107")
                
                # Esperar intervalo
                for _ in range(SYNC_INTERVAL_SECONDS):
                    if not self.is_running:
                        break
                    time.sleep(1)
        
        except Exception as e:
            self.log(f"\n❌ Error crítico: {e}", "error")
            self.update_status("❌ Error crítico", "#f85149")
        
        finally:
            mt5.shutdown()
            self.log("✅ MT5 cerrado", "info")
    
    def connect_mt5(self):
        """Conectar a MetaTrader5"""
        if not mt5.initialize():
            error = mt5.last_error()
            self.log(f"❌ Error MT5: {error}", "error")
            return False
        
        self.log("✅ MT5 conectado correctamente", "success")
        return True
    
    def collect_and_upload(self):
        """Proceso principal: recolectar y subir velas con UPSERT"""
        total_uploaded = 0
        
        for symbol in SYMBOLS:
            self.log_index_header(symbol)
            symbol_uploaded = 0
            
            for tf_name, tf_mt5 in TIMEFRAMES.items():
                # 1. Consultar último timestamp en Supabase
                last_timestamp_supabase = get_last_timestamp_from_supabase(symbol, tf_name)
                
                # Carga inicial o actualización con recuperación automática
                if last_timestamp_supabase is None:
                    # Carga inicial: obtener histórico completo
                    num_candles = INITIAL_CANDLES_BY_TIMEFRAME[tf_name]
                    self.log(f"│  🔄 [{tf_name}] Carga inicial: {num_candles} velas", "info")
                    df = self.read_candles(symbol, tf_name, tf_mt5, num_candles)
                    
                    if df is None:
                        continue
                    
                    candles_batch = []
                    for _, row in df.iterrows():
                        candle = format_candle_for_supabase(symbol, tf_name, row)
                        candles_batch.append(candle)
                    
                    if upload_to_supabase(candles_batch):
                        symbol_uploaded += len(candles_batch)
                        self.log(f"│  ✅ [{tf_name}] Carga inicial: {len(candles_batch)} velas", "success")
                    else:
                        self.log(f"│  ❌ [{tf_name}] Error en carga inicial", "error")
                else:
                    # 2. Leer última vela disponible desde MT5
                    if not mt5.symbol_select(symbol, True):
                        self.log(f"│  ⚠️ No se pudo seleccionar: {symbol}", "warning")
                        continue
                    
                    last_mt5_rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, 1)
                    
                    if last_mt5_rates is None or len(last_mt5_rates) == 0:
                        self.log(f"│  ⚠️ [{tf_name}] No hay velas disponibles en MT5", "warning")
                        continue
                    
                    # 3. Tomar timestamp de última vela MT5
                    last_timestamp_mt5 = int(last_mt5_rates[0]["time"])
                    
                    # Convertir last_timestamp_supabase a timestamp Unix
                    # Manejar timestamps ISO con o sin 'Z'
                    timestamp_str = last_timestamp_supabase.replace('Z', '+00:00') if 'Z' in last_timestamp_supabase else last_timestamp_supabase
                    last_timestamp_supabase_unix = int(datetime.fromisoformat(timestamp_str).timestamp())
                    
                    # Log de timestamps
                    self.log(f"│  📅 [{tf_name}] Última Supabase: {last_timestamp_supabase}", "info")
                    self.log(f"│  📅 [{tf_name}] Última MT5: {datetime.fromtimestamp(last_timestamp_mt5, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}Z", "info")
                    
                    # 4. Comparar: diferencia en segundos
                    diferencia_segundos = last_timestamp_mt5 - last_timestamp_supabase_unix
                    diferencia_minutos = diferencia_segundos / 60.0
                    
                    # Validar que la diferencia no sea negativa
                    if diferencia_segundos < 0:
                        self.log(f"│  ⚠️ [{tf_name}] MT5 tiene timestamp anterior a Supabase. Usando mínimo configurado.", "warning")
                        num_candles = RECOVERY_CONFIG[tf_name]["minimo"]
                    else:
                        # 5. Calcular velas faltantes según timeframe
                        config = RECOVERY_CONFIG.get(tf_name)
                        if config is None:
                            self.log(f"│  ⚠️ [{tf_name}] Configuración no encontrada", "warning")
                            continue
                        
                        # Usar ceil para asegurar que se cubren todas las velas parciales
                        velas_faltantes = math.ceil(diferencia_minutos / config["divisor"])
                        
                        # 6. Agregar margen
                        num_candles = velas_faltantes + config["margen"]
                        
                        # 7. Aplicar mínimos
                        if num_candles < config["minimo"]:
                            num_candles = config["minimo"]
                        
                        # 8. Aplicar máximos
                        if num_candles > config["maximo"]:
                            num_candles = config["maximo"]
                    
                    # Log de recuperación
                    self.log(f"│  🔄 [{tf_name}] Recuperación: leyendo {num_candles} velas", "info")
                    
                    # 9. Leer esa cantidad desde MT5
                    df = self.read_candles(symbol, tf_name, tf_mt5, num_candles)
                    
                    if df is None:
                        continue
                    
                    # 10. Mandar todas esas velas a Supabase con UPSERT
                    candles_batch = []
                    for _, row in df.iterrows():
                        candle = format_candle_for_supabase(symbol, tf_name, row)
                        candles_batch.append(candle)
                    
                    if upload_to_supabase(candles_batch):
                        symbol_uploaded += len(candles_batch)
                        self.log(f"│  ✅ [{tf_name}] UPSERT: {len(candles_batch)} velas procesadas", "success")
                    else:
                        self.log(f"│  ❌ [{tf_name}] Error al hacer UPSERT", "error")
            
            total_uploaded += symbol_uploaded
            self.log(f"│  📊 Subtotal {symbol}: {symbol_uploaded} velas", "info")
            self.log_index_footer()
        
        return total_uploaded
    
    def read_candles(self, symbol, timeframe_name, timeframe_mt5, num_candles):
        """Leer velas de MT5"""
        if not mt5.symbol_select(symbol, True):
            self.log(f"│  ⚠️ No se pudo seleccionar: {symbol}", "warning")
            return None
        
        rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, num_candles)
        
        if rates is None or len(rates) == 0:
            self.log(f"│  ⚠️ MT5 no devolvió velas para [{timeframe_name}]", "warning")
            return None
        
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        
        return df
    
    def run(self):
        """Iniciar la aplicación"""
        self.root.mainloop()


def connect_mt5():
    """Conectar a MetaTrader5"""
    if not mt5.initialize():
        error = mt5.last_error()
        print(f"❌ Error MT5: {error}")
        return False
    
    print("✅ MT5 conectado")
    return True


def get_last_timestamp_from_supabase(symbol, timeframe):
    """
    Consultar el último timestamp guardado en Supabase para un symbol/timeframe.
    Retorna None si no hay datos previos, o el timestamp como string ISO.
    """
    url = f"{SUPABASE_URL}/rest/v1/market_candles"
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {
        "symbol": f"eq.{symbol}",
        "timeframe": f"eq.{timeframe}",
        "select": "timestamp",
        "order": "timestamp.desc",
        "limit": "1"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return data[0]["timestamp"]
            else:
                return None
        else:
            print(f"⚠️ Error al consultar último timestamp: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"❌ Error al consultar Supabase: {e}")
        return None


def read_candles(symbol, timeframe_name, timeframe_mt5, num_candles):
    """Leer velas de MT5 para un símbolo y timeframe"""
    
    # Intentar seleccionar el símbolo
    if not mt5.symbol_select(symbol, True):
        print(f"❌ No se pudo seleccionar símbolo: {symbol}")
        return None
    
    # Obtener las velas
    rates = mt5.copy_rates_from_pos(symbol, timeframe_mt5, 0, num_candles)
    
    if rates is None or len(rates) == 0:
        print(f"⚠️ MT5 no devolvió velas para {symbol} [{timeframe_name}]")
        return None
    
    print(f"📊 {symbol} [{timeframe_name}]: {len(rates)} velas")
    
    # Convertir a DataFrame
    df = pd.DataFrame(rates)
    # Convertir time a UTC-aware datetime para compatibilidad con Supabase
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    
    return df


def format_candle_for_supabase(symbol, timeframe, row):
    """Formatear una vela para insertar en Supabase"""
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "timestamp": row["time"].isoformat(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "tick_volume": int(row["tick_volume"]),
        "spread": int(row["spread"]),
        "real_volume": int(row["real_volume"])
    }


def upload_to_supabase(candles_data):
    """
    Subir velas a Supabase tabla market_candles usando UPSERT para actualizar velas existentes.
    
    El UPSERT se basa en el constraint unique_candle (symbol, timeframe, timestamp).
    Si una vela ya existe con esa combinación, se actualizan sus valores OHLC.
    Si no existe, se inserta como nueva.
    """
    
    if not candles_data:
        return False
    
    # POST con UPSERT: actualiza si existe (on_conflict) o inserta si no existe
    url = f"{SUPABASE_URL}/rest/v1/market_candles?on_conflict=symbol,timeframe,timestamp"
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal"
    }
    
    try:
        response = requests.post(url, headers=headers, json=candles_data)
        
        # Considerar éxito si el status es 200, 201 o 204
        # 200/201: velas insertadas/actualizadas exitosamente
        # 204: operación exitosa sin contenido
        if response.status_code in [200, 201, 204]:
            return True
        else:
            print(f"❌ Supabase rechazó la subida")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    
    except Exception as e:
        print(f"❌ Error al subir a Supabase: {e}")
        return False


def main():
    """Función principal"""
    # Validar credenciales al inicio
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("❌ ERROR: No se encontró SUPABASE_URL o SUPABASE_ANON_KEY en .env")
        if TRAY_AVAILABLE:
            import tkinter.messagebox as messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error de Configuración",
                "No se encontraron las variables de entorno SUPABASE_URL o SUPABASE_ANON_KEY.\n\n"
                "Asegúrate de tener un archivo .env con estas variables."
            )
            root.destroy()
        sys.exit(1)
    
    # Crear y ejecutar la aplicación GUI
    app = CollectorGUI()
    app.run()


if __name__ == "__main__":
    main()

