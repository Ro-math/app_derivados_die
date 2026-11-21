# Modulo para jalar los datos de mercado en vivo de Yahoo Finance
# y tener las curvas de tasas interbancarias para cada divisa

import os
import sys
import math
import json
from datetime import datetime, timedelta

# Importamos yfinance, y si no esta instalado o no hay red usamos los datos de respaldo
try:
    import yfinance as yf
except ImportError:
    yf = None

import numpy as np
import pandas as pd

# Guardamos datos en cache para no saturar peticiones
cache_dir = os.path.join(os.path.dirname(__file__), ".cache_market")
os.makedirs(cache_dir, exist_ok=True)

# Configuracion de los pares de divisas con sus tickers en Yahoo y tasas de bancos centrales
DIVISAS_CONFIG = {
    "USD/MXN": {
        "ticker": "USDMXN=X",
        "nombre": "Dólar Americano / Peso Mexicano",
        "simbolo_base": "USD",
        "simbolo_cotizada": "MXN",
        "spot_default": 20.2500,
        "spread_default": 0.0400,
        "tasa_local": 0.1025,      # Banxico TIIE de Fondeo (~10.25%)
        "tasa_extranjera": 0.0460, # Tasa Fed / SOFR (~4.60%)
        "tasa_local_nombre": "Banxico (TIIE)",
        "tasa_ext_nombre": "Fed (SOFR)",
        "curva_local": {1: 0.1050, 7: 0.1048, 28: 0.1025, 91: 0.1010, 182: 0.0985, 364: 0.0950, 728: 0.0920},
        "curva_ext": {1: 0.0480, 7: 0.0475, 28: 0.0460, 91: 0.0445, 182: 0.0425, 364: 0.0400, 728: 0.0380}
    },
    "EUR/MXN": {
        "ticker": "EURMXN=X",
        "nombre": "Euro / Peso Mexicano",
        "simbolo_base": "EUR",
        "simbolo_cotizada": "MXN",
        "spot_default": 21.8500,
        "spread_default": 0.0600,
        "tasa_local": 0.1025,
        "tasa_extranjera": 0.0325, # BCE (~3.25%)
        "tasa_local_nombre": "Banxico (TIIE)",
        "tasa_ext_nombre": "BCE (€STR)",
        "curva_local": {1: 0.1050, 7: 0.1048, 28: 0.1025, 91: 0.1010, 182: 0.0985, 364: 0.0950, 728: 0.0920},
        "curva_ext": {1: 0.0340, 7: 0.0335, 28: 0.0325, 91: 0.0315, 182: 0.0300, 364: 0.0285, 728: 0.0270}
    },
    "GBP/MXN": {
        "ticker": "GBPMXN=X",
        "nombre": "Libra Esterlina / Peso Mexicano",
        "simbolo_base": "GBP",
        "simbolo_cotizada": "MXN",
        "spot_default": 25.6000,
        "spread_default": 0.0800,
        "tasa_local": 0.1025,
        "tasa_extranjera": 0.0475, # Bank of England SONIA (~4.75%)
        "tasa_local_nombre": "Banxico (TIIE)",
        "tasa_ext_nombre": "BoE (SONIA)",
        "curva_local": {1: 0.1050, 7: 0.1048, 28: 0.1025, 91: 0.1010, 182: 0.0985, 364: 0.0950, 728: 0.0920},
        "curva_ext": {1: 0.0490, 7: 0.0485, 28: 0.0475, 91: 0.0460, 182: 0.0440, 364: 0.0420, 728: 0.0400}
    },
    "EUR/USD": {
        "ticker": "EURUSD=X",
        "nombre": "Euro / Dólar Americano",
        "simbolo_base": "EUR",
        "simbolo_cotizada": "USD",
        "spot_default": 1.0520,
        "spread_default": 0.0004,
        "tasa_local": 0.0460,      # USD
        "tasa_extranjera": 0.0325, # EUR
        "tasa_local_nombre": "Fed (SOFR)",
        "tasa_ext_nombre": "BCE (€STR)",
        "curva_local": {1: 0.0480, 7: 0.0475, 28: 0.0460, 91: 0.0445, 182: 0.0425, 364: 0.0400, 728: 0.0380},
        "curva_ext": {1: 0.0340, 7: 0.0335, 28: 0.0325, 91: 0.0315, 182: 0.0300, 364: 0.0285, 728: 0.0270}
    },
    "GBP/USD": {
        "ticker": "GBPUSD=X",
        "nombre": "Libra Esterlina / Dólar Americano",
        "simbolo_base": "GBP",
        "simbolo_cotizada": "USD",
        "spot_default": 1.2640,
        "spread_default": 0.0005,
        "tasa_local": 0.0460,
        "tasa_extranjera": 0.0475,
        "tasa_local_nombre": "Fed (SOFR)",
        "tasa_ext_nombre": "BoE (SONIA)",
        "curva_local": {1: 0.0480, 7: 0.0475, 28: 0.0460, 91: 0.0445, 182: 0.0425, 364: 0.0400, 728: 0.0380},
        "curva_ext": {1: 0.0490, 7: 0.0485, 28: 0.0475, 91: 0.0460, 182: 0.0440, 364: 0.0420, 728: 0.0400}
    },
    "USD/JPY": {
        "ticker": "USDJPY=X",
        "nombre": "Dólar Americano / Yen Japonés",
        "simbolo_base": "USD",
        "simbolo_cotizada": "JPY",
        "spot_default": 154.2000,
        "spread_default": 0.0400,
        "tasa_local": 0.0025,      # Banco de Japon (~0.25%)
        "tasa_extranjera": 0.0460, # Fed (~4.60%)
        "tasa_local_nombre": "BoJ (TONA)",
        "tasa_ext_nombre": "Fed (SOFR)",
        "curva_local": {1: 0.0025, 7: 0.0025, 28: 0.0025, 91: 0.0030, 182: 0.0035, 364: 0.0040, 728: 0.0050},
        "curva_ext": {1: 0.0480, 7: 0.0475, 28: 0.0460, 91: 0.0445, 182: 0.0425, 364: 0.0400, 728: 0.0380}
    }
}


# Funcion principal para sacar el spot y la serie historica de la divisa elegida
def obtener_datos_mercado(par="USD/MXN"):
    cfg = DIVISAS_CONFIG.get(par, DIVISAS_CONFIG["USD/MXN"])
    ticker_sym = cfg["ticker"]
    spot_mid = cfg["spot_default"]
    fuente = "Modelo Calibrado (Mercado FX)"
    serie_precios = None
    cambio_pct_24h = 0.0

    # Primero intentamos conectar directo a Yahoo Finance
    if yf is not None:
        try:
            ticker = yf.Ticker(ticker_sym)
            hist = ticker.history(period="1y", interval="1d")
            if hist is not None and len(hist) > 20:
                closes = hist["Close"].dropna().values
                spot_mid = float(closes[-1])
                prev_close = float(closes[-2])
                cambio_pct_24h = ((spot_mid - prev_close) / prev_close) * 100.0
                serie_precios = closes
                fuente = "Yahoo Finance (En Vivo)"
        except Exception:
            # Si falla la red de la escuela o la api, seguimos con el modelo
            pass

    # Si no hubo internet o fallo Yahoo, generamos la serie historica calibrada para el VaR
    if serie_precios is None or len(serie_precios) < 20:
        np.random.seed(hash(par) % 10000)
        n = 504
        dt = 1.0 / 252.0
        sigma = 0.115 if "MXN" in par else (0.075 if "EUR" in par else 0.095)
        mu = 0.030
        shocks = np.random.normal(0, 1, n)
        log_ret = (mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * shocks
        precios = [spot_mid * 0.92]
        for r in log_ret[1:]:
            precios.append(precios[-1] * math.exp(r))
        factor = spot_mid / precios[-1]
        serie_precios = np.array([round(p * factor, 4) for p in precios])
        cambio_pct_24h = float((serie_precios[-1] - serie_precios[-2]) / serie_precios[-2] * 100.0)

    # Precios de compra y venta de la mesa (Bid / Ask) con spread interbancario
    spread = cfg["spread_default"]
    spot_bid = round(spot_mid - spread / 2.0, 4)
    spot_ask = round(spot_mid + spread / 2.0, 4)

    # Volatilidad historica con rendimientos diarios (desviacion estandar anualizada con raiz de 252)
    retornos = np.diff(serie_precios) / serie_precios[:-1]
    vol_diaria = float(np.std(retornos, ddof=1))
    vol_anual = vol_diaria * math.sqrt(252)

    return {
        "par": par,
        "nombre": cfg["nombre"],
        "simbolo_base": cfg["simbolo_base"],
        "simbolo_cotizada": cfg["simbolo_cotizada"],
        "spot_mid": round(spot_mid, 4),
        "spot_bid": spot_bid,
        "spot_ask": spot_ask,
        "spread": spread,
        "cambio_pct_24h": round(cambio_pct_24h, 2),
        "fuente": fuente,
        "volatilidad_diaria": vol_diaria,
        "volatilidad_anual": vol_anual,
        "serie_historica": [round(p, 4) for p in serie_precios[-60:]], # 60 dias para la grafica
        "retornos_historicos": retornos,
        "curva_local": cfg["curva_local"],
        "curva_ext": cfg["curva_ext"],
        "tasa_local_nombre": cfg["tasa_local_nombre"],
        "tasa_ext_nombre": cfg["tasa_ext_nombre"]
    }
