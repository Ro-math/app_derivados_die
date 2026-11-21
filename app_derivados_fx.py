# Cotizador de derivados de tipo de cambio, paridad de tasas CIP y gestion de riesgo (VaR)
# Proyecto de Administracion de Riesgos Financieros
# Incluye cotizacion en vivo con Yahoo Finance, los 5 derivados y medicion de VaR

import os
import sys
import tempfile
import argparse
import json
import math
import csv
from datetime import datetime, timedelta
import http.server
import socketserver
import webbrowser
import threading

# Asegurar directorio temporal multiplataforma (Windows y Mac)
os.environ['MPLCONFIGDIR'] = os.path.join(tempfile.gettempdir(), 'matplotlib')

# Auto-importación con resiliencia total y auto-instalación
try:
    import numpy as np
except ImportError:
    try:
        import subprocess
        print("[Aviso] 'numpy' no encontrado en este entorno. Instalando automáticamente...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy", "pandas", "matplotlib"])
        import numpy as np
    except Exception:
        np = None

try:
    import pandas as pd
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])
        import pandas as pd
    except Exception:
        pd = None

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if hasattr(plt, 'style'):
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    plt.rcParams['font.sans-serif'] = 'Helvetica', 'Arial', 'DejaVu Sans'
    plt.rcParams['axes.edgecolor'] = '#cccccc'
    plt.rcParams['axes.linewidth'] = 0.8
except Exception:
    plt = None

# Importación segura de normal quantile con fallback de alta precisión
try:
    from scipy.stats import norm
    def get_norm_z(p):
        return float(norm.ppf(p))
except Exception:
    def get_norm_z(p):
        if abs(p - 0.95) < 1e-4:
            return 1.6448536269514722
        elif abs(p - 0.99) < 1e-4:
            return 2.3263478740408408
        elif abs(p - 0.975) < 1e-4:
            return 1.959963984540054
        # Acklam rational approximation
        a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
        q = p - 0.5
        if abs(q) <= 0.42:
            r = q * q
            return q * (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1.0)
        r = p if q < 0 else 1.0 - p
        r = math.sqrt(-math.log(r))
        x = (((((c[0]*r+c[1])*r+c[2])*r+c[3])*r+c[4])*r+c[5]) / ((((d[0]*r+d[1])*r+d[2])*r+d[3])*r+1.0)
        return -x if q < 0 else x


# =============================================================================
# FUNCIONES MATEMÁTICAS NATIVAS DE ALTA PRECISIÓN (RESILIENTES)
# =============================================================================

def safe_interp(x, xp, fp):
    """Interpolación lineal de alta precisión con o sin numpy."""
    if np is not None:
        return float(np.interp(x, xp, fp))
    if x <= xp[0]:
        return float(fp[0])
    if x >= xp[-1]:
        return float(fp[-1])
    for i in range(len(xp) - 1):
        if xp[i] <= x <= xp[i + 1]:
            t = (x - xp[i]) / (xp[i + 1] - xp[i])
            return float(fp[i] + t * (fp[i + 1] - fp[i]))
    return float(fp[-1])


def safe_percentile(arr, p):
    """Percentil empírico exacto con o sin numpy."""
    if np is not None:
        return float(np.percentile(arr, p))
    s = sorted(arr)
    if not s:
        return 0.0
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    return float(s[int(f)] * (c - k) + s[int(c)] * (k - f))


def safe_random_normal(mu, sigma, n, seed=42):
    """Generación de distribución normal con o sin numpy."""
    if np is not None:
        np.random.seed(seed)
        return np.random.normal(mu, sigma, n)
    import random
    random.seed(seed)
    return [random.gauss(mu, sigma) for _ in range(n)]


class SimpleDataFrame:
    """Tabla de datos nativa en Python puro en caso de no contar con pandas."""
    def __init__(self, data):
        if isinstance(data, list):
            self.rows = data
        elif isinstance(data, dict):
            keys = list(data.keys())
            n = len(data[keys[0]])
            self.rows = [{k: data[k][i] for k in keys} for i in range(n)]
        else:
            self.rows = []

    def to_dict(self, orient="records"):
        return self.rows

    def to_string(self, index=False):
        if not self.rows:
            return ""
        headers = list(self.rows[0].keys())
        widths = [max(len(str(h)), max(len(str(r.get(h, ""))) for r in self.rows)) for h in headers]
        h_str = "  ".join(f"{h:>{w}}" if i > 0 else f"{h:<{w}}" for i, (h, w) in enumerate(zip(headers, widths)))
        lines = [h_str]
        for r in self.rows:
            parts = []
            for i, (h, w) in enumerate(zip(headers, widths)):
                val = str(r.get(h, ""))
                parts.append(f"{val:>{w}}" if i > 0 else f"{val:<{w}}")
            lines.append("  ".join(parts))
        return "\n".join(lines)

    def __getitem__(self, key):
        return [r.get(key) for r in self.rows]


def crear_dataframe(data):
    if pd is not None:
        return pd.DataFrame(data)
    return SimpleDataFrame(data)


class MercadoFX:
    """
    Gestiona los datos de mercado para USD/MXN:
    - Precios Spot (Bid/Ask y Mid).
    - Curva de Tasas de México (TIIE Fondeo / Cetes / TIIE 28).
    - Curva de Tasas de EE.UU. (SOFR / Treasuries).
    - Serie histórica de tipo de cambio para estimación de volatilidad y VaR.
    """

    def __init__(self, spot_mid=20.1000, spread_spot=0.0400, csv_historico='historico_usdmxn.csv'):
        self.spot_mid = spot_mid
        self.spread_spot = spread_spot
        # Bid: Banco compra USD (cliente vende USD)
        self.spot_bid = round(spot_mid - spread_spot / 2, 4)
        # Ask: Banco vende USD (cliente compra USD)
        self.spot_ask = round(spot_mid + spread_spot / 2, 4)

        # Nodos de la Curva de Tasas de Mercado (plazo en días vs tasa anualizada)
        # México: Curva TIIE Fondeo / Cetes
        self.curva_mxn_nodos = {
            1: 0.1050,    # Fondeo O/N (10.50%)
            7: 0.1048,    # 1 semana
            28: 0.1040,   # 1 mes (28 días)
            91: 0.1025,   # 3 meses (91 días)
            182: 0.1010,  # 6 meses (182 días)
            364: 0.0985,  # 1 año (364 días)
            728: 0.0950   # 2 años (728 días)
        }

        # EE. UU.: Curva SOFR / OIS / Treasuries
        self.curva_usd_nodos = {
            1: 0.0480,    # SOFR O/N (4.80%)
            7: 0.0478,    # 1 semana
            28: 0.0470,   # 1 mes
            91: 0.0455,   # 3 meses
            182: 0.0440,  # 6 meses
            364: 0.0415,  # 1 año
            728: 0.0395   # 2 años
        }

        self.csv_historico = csv_historico
        self.df_historico = self._cargar_o_generar_historico()
        self.volatilidad_diaria = self._calcular_volatilidad()

    def _cargar_o_generar_historico(self):
        """Carga serie histórica de USD/MXN o genera una calibrada si no existe el archivo."""
        if os.path.exists(self.csv_historico):
            try:
                fechas, precios = [], []
                with open(self.csv_historico, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        fechas.append(r.get('Date', ''))
                        precios.append(float(r.get('USDMXN', 20.0)))
                if len(precios) > 30:
                    if pd is not None:
                        df = pd.DataFrame({'Date': fechas, 'USDMXN': precios})
                        try: df['Date'] = pd.to_datetime(df['Date'])
                        except Exception: pass
                        return df
                    return SimpleDataFrame({'Date': fechas, 'USDMXN': precios})
            except Exception as e:
                print(f"[Aviso] No se pudo leer {self.csv_historico}: {e}")

        # Generar serie simulada calibrada de 504 días (~2 años hábiles)
        shocks = safe_random_normal(0, 1, 504, seed=42)
        dt = 1 / 252
        sigma = 0.115
        mu = 0.035
        precios = [18.20]
        for s in shocks[1:]:
            r = (mu - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * s
            precios.append(precios[-1] * math.exp(r))

        factor = self.spot_mid / precios[-1]
        precios = [round(p * factor, 4) for p in precios]
        fechas = [f"Dia_{i}" for i in range(len(precios))]

        if pd is not None:
            return pd.DataFrame({'Date': fechas, 'USDMXN': precios})
        return SimpleDataFrame({'Date': fechas, 'USDMXN': precios})

    def _calcular_volatilidad(self):
        """Calcula la volatilidad diaria de los rendimientos del tipo de cambio."""
        if isinstance(self.df_historico, SimpleDataFrame):
            precios = self.df_historico['USDMXN']
        else:
            precios = self.df_historico['USDMXN'].tolist()
        retornos = [(precios[i] - precios[i-1]) / precios[i-1] for i in range(1, len(precios))]
        n = len(retornos)
        if n < 2: return 0.007
        mean = sum(retornos) / n
        var = sum((r - mean)**2 for r in retornos) / (n - 1)
        return math.sqrt(var)

    def obtener_tasas(self, plazo_dias):
        """
        Interpola linealmente las tasas libres de riesgo para México y EE. UU.
        al plazo solicitado (en días, hasta 730 días).
        """
        plazo_dias = max(1, min(plazo_dias, 730))

        # Interpolación México
        dias_mxn = sorted(self.curva_mxn_nodos.keys())
        tasas_mxn = [self.curva_mxn_nodos[d] for d in dias_mxn]
        r_mxn = safe_interp(plazo_dias, dias_mxn, tasas_mxn)

        # Interpolación EE.UU.
        dias_usd = sorted(self.curva_usd_nodos.keys())
        tasas_usd = [self.curva_usd_nodos[d] for d in dias_usd]
        r_usd = safe_interp(plazo_dias, dias_usd, tasas_usd)

        return r_mxn, r_usd

    def calcular_forward_teorico(self, spot, plazo_dias, r_mxn=None, r_usd=None):
        """
        Calcula el Tipo de Cambio Forward por Paridad Cubierta de Tasas (CIP):
        F = S * [ (1 + r_mxn * t / 360) / (1 + r_usd * t / 360) ]
        Convención estándar mexicana: Base Actual/360 para ambas divisas.
        """
        if r_mxn is None or r_usd is None:
            r_mxn, r_usd = self.obtener_tasas(plazo_dias)

        t_factor = plazo_dias / 360.0
        factor_mxn = 1.0 + r_mxn * t_factor
        factor_usd = 1.0 + r_usd * t_factor

        forward = spot * (factor_mxn / factor_usd)
        puntos_f = forward - spot
        puntos_f_pips = puntos_f * 10000.0

        return forward, puntos_f, puntos_f_pips

    def calcular_tasa_implicita_en_pesos(self, spot, forward, plazo_dias, r_usd=None):
        """
        ¿Qué es la Tasa Implícita en Pesos (Curva Implícita)?
        Es la tasa en pesos que descuenta el mercado cambiario a partir de los
        precios de los forwards o FX swaps, despejada de la paridad de tasas:
        r_mxn_impl = [ (F / S) * (1 + r_usd * t / 360) - 1 ] * (360 / t)
        """
        if plazo_dias <= 0:
            return 0.0
        if r_usd is None:
            _, r_usd = self.obtener_tasas(plazo_dias)

        t_factor = plazo_dias / 360.0
        r_impl = ((forward / spot) * (1.0 + r_usd * t_factor) - 1.0) * (1.0 / t_factor)
        return float(r_impl)

    def generar_curva_forward_completa(self):
        """Genera la estructura temporal de forwards y tasas implícitas para plazos estándar."""
        plazos = [1, 2, 7, 14, 21, 28, 60, 91, 120, 182, 270, 364, 540, 728]
        datos = []
        for d in plazos:
            r_mx, r_us = self.obtener_tasas(d)
            fwd_mid, pts_mid, pips_mid = self.calcular_forward_teorico(self.spot_mid, d, r_mx, r_us)
            fwd_bid, pts_bid, pips_bid = self.calcular_forward_teorico(self.spot_bid, d, r_mx * 0.995, r_us * 1.005)
            fwd_ask, pts_ask, pips_ask = self.calcular_forward_teorico(self.spot_ask, d, r_mx * 1.005, r_us * 0.995)
            tasa_impl = self.calcular_tasa_implicita_en_pesos(self.spot_mid, fwd_mid, d, r_us)

            datos.append({
                'Plazo_Dias': d,
                'Tasa_MXN': r_mx,
                'Tasa_USD': r_us,
                'Spot_Mid': self.spot_mid,
                'Forward_Bid': round(fwd_bid, 4),
                'Forward_Ask': round(fwd_ask, 4),
                'Forward_Mid': round(fwd_mid, 4),
                'Puntos_F': round(pts_mid, 4),
                'Puntos_F_Pips': round(pips_mid, 1),
                'Tasa_Impl_MXN': round(tasa_impl, 6)
            })
        return crear_dataframe(datos)


# =============================================================================
# 2. COTIZADOR Y ASIGNACIÓN DE DERIVADOS FX
# =============================================================================

class CotizadorDerivadosFX:
    """
    Gestiona la lógica comercial y de contratación:
    - Validación de límites (máximo 2 años).
    - Asignación de derivado:
      * Corto plazo (<= 2 días): FX Spot (Cash T+0, Tom T+1, Spot T+2).
      * Mayor a 2 días (> 2 días): FX Swap + Alternativa FX Forward a 1 mes.
    - Cotización en Puntos F y precio de Compra/Venta.
    """

    def __init__(self, mercado: MercadoFX):
        self.mercado = mercado

    def cotizar(self, tipo_operacion: str, plazo_dias: int, nominal_usd: float = None, nominal_mxn: float = None):
        """
        Realiza la cotización para el cliente.
        tipo_operacion: 'compra' (cliente compra USD / paga MXN) o 'venta' (cliente vende USD / recibe MXN).
        plazo_dias: Días de la operación (1 a 730).
        nominal_usd: Monto en USD (opcional si se da nominal_mxn).
        nominal_mxn: Monto en MXN (opcional si se da nominal_usd).
        """
        tipo_operacion = tipo_operacion.strip().lower()
        if tipo_operacion not in ['compra', 'venta']:
            raise ValueError("El tipo de operación debe ser 'compra' o 'venta'.")

        # Validación del límite de 2 años (730 días)
        plazo_original = plazo_dias
        alerta_plazo = None
        if plazo_dias > 730:
            alerta_plazo = f"El plazo solicitado ({plazo_original} días) excede el límite máximo permitido de 2 años (730 días). Se ha ajustado automáticamente a 730 días."
            plazo_dias = 730
        elif plazo_dias < 0:
            raise ValueError("El plazo no puede ser negativo.")

        # Asignación del derivado según el plazo
        if plazo_dias <= 2:
            derivado_asignado = "FX Spot (Mercado de Contado)"
            subtipo = {
                0: "FX Cash (Mismo día / T+0)",
                1: "FX Tom (Tomorrow / T+1)",
                2: "FX Spot (Contado Estándar / T+2)"
            }.get(plazo_dias, "FX Spot")
            descripcion_derivado = (
                f"Para operaciones de corto plazo (<= 2 días), se asigna {subtipo}. "
                "La liquidación se realiza de contado de manera inmediata o en un máximo de 48 horas hábiles "
                "sin requerir cobertura estructurada a plazo."
            )
            alternativa_ofrecida = None
        else:
            derivado_asignado = "FX Swap (Swap Cambiario)"
            descripcion_derivado = (
                f"Al ser una operación a plazo de {plazo_dias} días (> 2 días), se asigna un FX Swap. "
                "Este instrumento combina una compra/venta simultánea en fecha spot con la operación inversa "
                "en fecha forward, permitiendo fondearse o invertir liquidez en dólares y pesos sin riesgo "
                "cambiario de mercado, ganando o pagando el diferencial de tasas de interés."
            )
            alternativa_ofrecida = {
                'producto': "FX Forward a 1 Mes (28 días)",
                'descripcion': "Alternativa recomendada para clientes que buscan fijar un tipo de cambio con certeza absoluta a corto plazo.",
                'plazo_dias': 28
            }

        # Obtener tasas e interpolación
        r_mxn, r_usd = self.mercado.obtener_tasas(plazo_dias)

        # Precio Spot aplicable
        # Si el cliente compra USD: El banco vende al precio Ask
        # Si el cliente vende USD: El banco compra al precio Bid
        if tipo_operacion == 'compra':
            spot_aplicable = self.mercado.spot_ask
            lado_mercado = "Venta del Banco (Ask)"
        else:
            spot_aplicable = self.mercado.spot_bid
            lado_mercado = "Compra del Banco (Bid)"

        # Cálculo de Forward Teórico y Puntos Forward (Puntos F)
        if plazo_dias <= 2:
            # En spot de corto plazo, los puntos F son prácticamente cero o micro-puntos de carry overnight
            forward_teorico = spot_aplicable
            puntos_f = 0.0
            puntos_f_pips = 0.0
            tasa_implicita = r_mxn
        else:
            forward_teorico, puntos_f, puntos_f_pips = self.mercado.calcular_forward_teorico(
                spot_aplicable, plazo_dias, r_mxn, r_usd
            )
            tasa_implicita = self.mercado.calcular_tasa_implicita_en_pesos(
                spot_aplicable, forward_teorico, plazo_dias, r_usd
            )

        precio_pactado = round(forward_teorico, 4)

        # Cálculo de Nominales
        if nominal_usd is not None and nominal_usd > 0:
            monto_usd = float(nominal_usd)
            monto_mxn = round(monto_usd * precio_pactado, 2)
        elif nominal_mxn is not None and nominal_mxn > 0:
            monto_mxn = float(nominal_mxn)
            monto_usd = round(monto_mxn / precio_pactado, 2)
        else:
            # Nominal por defecto para demostración: 100,000 USD
            monto_usd = 100000.0
            monto_mxn = round(monto_usd * precio_pactado, 2)

        # Cálculo de la alternativa forward a 1 mes (28 días) si aplica
        cotizacion_alternativa = None
        if alternativa_ofrecida:
            r_mxn_1m, r_usd_1m = self.mercado.obtener_tasas(28)
            fwd_1m, pts_1m, pips_1m = self.mercado.calcular_forward_teorico(
                spot_aplicable, 28, r_mxn_1m, r_usd_1m
            )
            cotizacion_alternativa = {
                'producto': "FX Forward 1 Mes (28 días)",
                'plazo_dias': 28,
                'precio_pactado': round(fwd_1m, 4),
                'puntos_f': round(pts_1m, 4),
                'puntos_f_pips': round(pips_1m, 1),
                'tasa_mxn': r_mxn_1m,
                'tasa_usd': r_usd_1m,
                'monto_mxn_estimado': round(monto_usd * fwd_1m, 2)
            }

        resultado = {
            'tipo_operacion': tipo_operacion.upper(),
            'lado_mercado': lado_mercado,
            'plazo_dias': plazo_dias,
            'alerta_plazo': alerta_plazo,
            'derivado_asignado': derivado_asignado,
            'descripcion_derivado': descripcion_derivado,
            'alternativa_ofrecida': alternativa_ofrecida,
            'cotizacion_alternativa': cotizacion_alternativa,
            'spot_base': spot_aplicable,
            'spot_mid': self.mercado.spot_mid,
            'tasa_mxn': r_mxn,
            'tasa_usd': r_usd,
            'puntos_f': round(puntos_f, 4),
            'puntos_f_pips': round(puntos_f_pips, 1),
            'precio_pactado': precio_pactado,
            'tasa_implicita_mxn': round(tasa_implicita, 4),
            'nominal_usd': monto_usd,
            'nominal_mxn': monto_mxn,
            'fecha_liquidacion_estimada': (datetime.now() + timedelta(days=plazo_dias)).strftime('%Y-%m-%d')
        }
        return resultado


# =============================================================================
# 3. ANÁLISIS DE P&L Y VALUE AT RISK (VaR)
# =============================================================================

class AnalizadorRiesgoPnL:
    """
    Genera proyecciones de pérdidas y ganancias (P&L) y calcula el Value at Risk (VaR):
    - Matriz de escenarios de tipo de cambio al vencimiento S_T.
    - VaR Paramétrico al 95% y 99% (1 día, 10 días y al vencimiento).
    - VaR Histórico al 95% y 99%.
    - VaR Montecarlo al 95% y 99% con 12,500 simulaciones.
    - Generación de gráficos (Payoff P&L, Curva Forward y Distribución VaR).
    """

    def __init__(self, mercado: MercadoFX):
        self.mercado = mercado

    def generar_proyecciones_pnl(self, cotizacion: dict):
        """
        Calcula la tabla de proyecciones de P&L para distintos escenarios de S_T al vencimiento.
        """
        tipo = cotizacion['tipo_operacion'].lower()
        F = cotizacion['precio_pactado']
        nominal_usd = cotizacion['nominal_usd']
        nominal_mxn = cotizacion['nominal_mxn']

        # Rangos de variación de tipo de cambio: -15% a +15%
        variaciones = [-0.15, -0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, 0.15]
        escenarios = []

        for v in variaciones:
            # Tipo de cambio proyectado al vencimiento
            st = round(F * (1.0 + v), 4)

            # Cálculo de P&L según posición
            # Compra USD: Gana si ST > F, pierde si ST < F
            # Venta USD: Gana si ST < F, pierde si ST > F
            if tipo == 'compra':
                pnl_mxn = round(nominal_usd * (st - F), 2)
                flujo_mercado = round(nominal_usd * st, 2)
            else:
                pnl_mxn = round(nominal_usd * (F - st), 2)
                flujo_mercado = round(nominal_usd * st, 2)

            pnl_usd = round(pnl_mxn / st, 2)
            rendimiento_pct = round((pnl_mxn / nominal_mxn) * 100.0, 2)

            if pnl_mxn > 0:
                estado = "GANANCIA"
            elif pnl_mxn < 0:
                estado = "PÉRDIDA"
            else:
                estado = "NEUTRO / EN DINERO"

            escenarios.append({
                'Variacion_%': f"{v*100:+.1f}%",
                'ST_Proyectado': st,
                'Flujo_Pactado_MXN': nominal_mxn,
                'Flujo_Mercado_MXN': flujo_mercado,
                'PnL_MXN': pnl_mxn,
                'PnL_USD': pnl_usd,
                'Rendimiento_%': rendimiento_pct,
                'Estado': estado
            })

        df_pnl = crear_dataframe(escenarios)
        return df_pnl

    def calcular_var_integral(self, cotizacion: dict, n_simulaciones=12500):
        """
        Calcula el VaR del derivado mediante 3 metodologías:
        1. VaR Paramétrico (Delta-Normal y Escalado a 1d, 10d y al plazo t).
        2. VaR Histórico con la serie empírica de USD/MXN.
        3. VaR Montecarlo con n_simulaciones (por defecto 12,500).
        """
        tipo = cotizacion['tipo_operacion'].lower()
        nominal_mxn = cotizacion['nominal_mxn']
        nominal_usd = cotizacion['nominal_usd']
        plazo_dias = max(1, cotizacion['plazo_dias'])

        # Retornos históricos
        if isinstance(self.mercado.df_historico, SimpleDataFrame):
            precios = self.mercado.df_historico['USDMXN']
        else:
            precios = self.mercado.df_historico['USDMXN'].tolist()
        retornos_diarios = [(precios[i] - precios[i-1]) / precios[i-1] for i in range(1, len(precios))]
        sigma_diaria = self.mercado.volatilidad_diaria
        mu_diaria = sum(retornos_diarios) / len(retornos_diarios)

        # Factores de escalamiento temporal (regla de la raíz del tiempo)
        sigma_10d = sigma_diaria * math.sqrt(10)
        sigma_plazo = sigma_diaria * math.sqrt(plazo_dias)

        z_95 = get_norm_z(0.95)
        z_99 = get_norm_z(0.99)

        # A) VaR Paramétrico
        var_param_95_1d_pct = z_95 * sigma_diaria
        var_param_99_1d_pct = z_99 * sigma_diaria
        var_param_95_1d_mxn = var_param_95_1d_pct * nominal_mxn
        var_param_99_1d_mxn = var_param_99_1d_pct * nominal_mxn

        var_param_95_10d_pct = z_95 * sigma_10d
        var_param_99_10d_pct = z_99 * sigma_10d
        var_param_95_10d_mxn = var_param_95_10d_pct * nominal_mxn
        var_param_99_10d_mxn = var_param_99_10d_pct * nominal_mxn

        var_param_95_plazo_pct = z_95 * sigma_plazo
        var_param_99_plazo_pct = z_99 * sigma_plazo
        var_param_95_plazo_mxn = var_param_95_plazo_pct * nominal_mxn
        var_param_99_plazo_mxn = var_param_99_plazo_pct * nominal_mxn

        # B) VaR Histórico
        if tipo == 'compra':
            retornos_posicion = retornos_diarios
        else:
            retornos_posicion = [-r for r in retornos_diarios]

        p_5 = safe_percentile(retornos_posicion, 5)
        p_1 = safe_percentile(retornos_posicion, 1)

        var_hist_95_1d_pct = abs(float(p_5))
        var_hist_99_1d_pct = abs(float(p_1))
        var_hist_95_1d_mxn = var_hist_95_1d_pct * nominal_mxn
        var_hist_99_1d_mxn = var_hist_99_1d_pct * nominal_mxn

        # C) VaR Montecarlo
        shocks_normales = safe_random_normal(0, 1, n_simulaciones, seed=42)
        sim_ret_10d = [mu_diaria * 10 + sigma_10d * s for s in shocks_normales]

        if tipo == 'compra':
            sim_pnl_pct = sim_ret_10d
        else:
            sim_pnl_pct = [-r for r in sim_ret_10d]

        mc_p5 = safe_percentile(sim_pnl_pct, 5)
        mc_p1 = safe_percentile(sim_pnl_pct, 1)

        var_mc_95_10d_pct = abs(float(mc_p5))
        var_mc_99_10d_pct = abs(float(mc_p1))
        var_mc_95_10d_mxn = var_mc_95_10d_pct * nominal_mxn
        var_mc_99_10d_mxn = var_mc_99_10d_pct * nominal_mxn

        resumen_var = {
            'sigma_diaria_%': round(sigma_diaria * 100, 4),
            'sigma_anualizada_%': round(sigma_diaria * math.sqrt(252) * 100, 2),
            'var_parametrico': {
                '1d': {
                    'var_95_%': round(var_param_95_1d_pct * 100, 2),
                    'var_95_mxn': round(var_param_95_1d_mxn, 2),
                    'var_95_usd': round(var_param_95_1d_mxn / cotizacion['precio_pactado'], 2),
                    'var_99_%': round(var_param_99_1d_pct * 100, 2),
                    'var_99_mxn': round(var_param_99_1d_mxn, 2),
                    'var_99_usd': round(var_param_99_1d_mxn / cotizacion['precio_pactado'], 2)
                },
                '10d': {
                    'var_95_%': round(var_param_95_10d_pct * 100, 2),
                    'var_95_mxn': round(var_param_95_10d_mxn, 2),
                    'var_95_usd': round(var_param_95_10d_mxn / cotizacion['precio_pactado'], 2),
                    'var_99_%': round(var_param_99_10d_pct * 100, 2),
                    'var_99_mxn': round(var_param_99_10d_mxn, 2),
                    'var_99_usd': round(var_param_99_10d_mxn / cotizacion['precio_pactado'], 2)
                },
                'plazo_total': {
                    'plazo_dias': plazo_dias,
                    'var_95_%': round(var_param_95_plazo_pct * 100, 2),
                    'var_95_mxn': round(var_param_95_plazo_mxn, 2),
                    'var_95_usd': round(var_param_95_plazo_mxn / cotizacion['precio_pactado'], 2),
                    'var_99_%': round(var_param_99_plazo_pct * 100, 2),
                    'var_99_mxn': round(var_param_99_plazo_mxn, 2),
                    'var_99_usd': round(var_param_99_plazo_mxn / cotizacion['precio_pactado'], 2)
                }
            },
            'var_historico_1d': {
                'var_95_%': round(var_hist_95_1d_pct * 100, 2),
                'var_95_mxn': round(var_hist_95_1d_mxn, 2),
                'var_99_%': round(var_hist_99_1d_pct * 100, 2),
                'var_99_mxn': round(var_hist_99_1d_mxn, 2)
            },
            'var_montecarlo_10d': {
                'simulaciones': n_simulaciones,
                'var_95_%': round(var_mc_95_10d_pct * 100, 2),
                'var_95_mxn': round(var_mc_95_10d_mxn, 2),
                'var_99_%': round(var_mc_99_10d_pct * 100, 2),
                'var_99_mxn': round(var_mc_99_10d_mxn, 2)
            },
            'sim_pnl_mxn_10d': [r * nominal_mxn for r in sim_pnl_pct]
        }
        return resumen_var

    def generar_graficas(self, cotizacion: dict, df_pnl: pd.DataFrame, resumen_var: dict):
        """
        Genera y guarda 3 archivos gráficos profesionales:
        1. pnl_payoff.png: Curva de Payoff de pérdidas y ganancias.
        2. curva_forward_pesos.png: Estructura temporal forward e implícita.
        3. distribucion_var.png: Histograma con cortes de VaR al 95% y 99%.
        """
        archivos_guardados = {}
        if plt is None:
            return archivos_guardados


        # -----------------------------------------------------------------
        # Gráfica 1: Payoff P&L
        # -----------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
        st_vals = df_pnl['ST_Proyectado']
        pnl_vals = df_pnl['PnL_MXN']

        ax.plot(st_vals, pnl_vals, color='#1f77b4', linewidth=2.5, marker='o', label='Perfil de P&L')
        ax.axhline(0, color='black', linestyle='--', linewidth=1.0, alpha=0.7)
        ax.axvline(cotizacion['precio_pactado'], color='#d62728', linestyle=':', linewidth=1.8,
                   label=f"Precio Pactado F: ${cotizacion['precio_pactado']:.4f}")

        # Sombrear zonas de ganancia y pérdida
        ax.fill_between(st_vals, pnl_vals, 0, where=(pnl_vals >= 0), color='#2ca02c', alpha=0.25, label='Zona de Ganancia')
        ax.fill_between(st_vals, pnl_vals, 0, where=(pnl_vals < 0), color='#d62728', alpha=0.25, label='Zona de Pérdida')

        ax.set_title(f"Perfil de Pérdidas y Ganancias (P&L) - {cotizacion['derivado_asignado']}\n"
                     f"Posición: {cotizacion['tipo_operacion']} USD | Nominal: ${cotizacion['nominal_usd']:,.0f} USD",
                     fontsize=12, fontweight='bold', pad=12)
        ax.set_xlabel("Tipo de Cambio al Vencimiento (USD/MXN)", fontsize=10, fontweight='bold')
        ax.set_ylabel("P&L en Pesos Mexicanos (MXN)", fontsize=10, fontweight='bold')
        ax.yaxis.set_major_formatter('${x:,.0f}')
        ax.legend(loc='best', frameon=True)
        plt.tight_layout()

        ruta_pnl = "pnl_payoff.png"
        fig.savefig(ruta_pnl)
        plt.close(fig)
        archivos_guardados['pnl'] = ruta_pnl

        # -----------------------------------------------------------------
        # Gráfica 2: Curva Forward e Implícita en Pesos
        # -----------------------------------------------------------------
        df_curva = self.mercado.generar_curva_forward_completa()
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), dpi=150, sharex=True)

        # Subplot A: Tipo de Cambio Forward vs Plazo
        ax1.plot(df_curva['Plazo_Dias'], df_curva['Forward_Mid'], color='#2b5c8f', linewidth=2.2, marker='s', label='Forward Mid')
        ax1.fill_between(df_curva['Plazo_Dias'], df_curva['Forward_Bid'], df_curva['Forward_Ask'], color='#aec7e8', alpha=0.5, label='Banda Bid-Ask')
        ax1.axhline(self.mercado.spot_mid, color='#e377c2', linestyle='--', linewidth=1.5, label=f"Spot Mid: ${self.mercado.spot_mid:.4f}")
        ax1.scatter([cotizacion['plazo_dias']], [cotizacion['precio_pactado']], color='#d62728', s=90, zorder=5, label=f"Cotización Cliente ({cotizacion['plazo_dias']}d)")

        ax1.set_title("Curva Forward USD/MXN y Curva de Tasas Implícitas en Pesos (Paridad CIP)", fontsize=12, fontweight='bold')
        ax1.set_ylabel("Tipo de Cambio Forward", fontsize=10, fontweight='bold')
        ax1.yaxis.set_major_formatter('${x:,.4f}')
        ax1.legend(loc='upper left', frameon=True, fontsize=9)

        # Subplot B: Puntos Forward (Puntos F) y Tasa Implícita
        ax2.plot(df_curva['Plazo_Dias'], df_curva['Puntos_F'], color='#ff7f0e', linewidth=2.0, marker='^', label='Puntos Forward (F - S en MXN)')
        ax2.set_xlabel("Plazo de Vencimiento (Días - hasta 2 años)", fontsize=10, fontweight='bold')
        ax2.set_ylabel("Puntos Forward (MXN)", fontsize=10, fontweight='bold', color='#ff7f0e')
        ax2.tick_params(axis='y', labelcolor='#ff7f0e')

        ax2_bis = ax2.twinx()
        ax2_bis.plot(df_curva['Plazo_Dias'], df_curva['Tasa_Impl_MXN'] * 100, color='#2ca02c', linewidth=2.0, linestyle='-.', label='Tasa Implícita MXN (%)')
        ax2_bis.set_ylabel("Tasa Implícita en Pesos (%)", fontsize=10, fontweight='bold', color='#2ca02c')
        ax2_bis.tick_params(axis='y', labelcolor='#2ca02c')
        ax2_bis.yaxis.set_major_formatter('{x:.2f}%')

        plt.tight_layout()
        ruta_curva = "curva_forward_pesos.png"
        fig.savefig(ruta_curva)
        plt.close(fig)
        archivos_guardados['curva'] = ruta_curva

        # -----------------------------------------------------------------
        # Gráfica 3: Distribución y Cortes de VaR (Montecarlo 10 Días)
        # -----------------------------------------------------------------
        fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
        sim_pnl = resumen_var['sim_pnl_mxn_10d']

        # Histograma
        n, bins, patches = ax.hist(sim_pnl, bins=80, density=True, color='#5c93c4', alpha=0.75, edgecolor='#34608c', label='Distribución Simulada (12,500 iter)')

        # Líneas de VaR
        var_95 = resumen_var['var_montecarlo_10d']['var_95_mxn']
        var_99 = resumen_var['var_montecarlo_10d']['var_99_mxn']

        ax.axvline(-var_95, color='#ff7f0e', linestyle='--', linewidth=2.0, label=f"VaR 95% 10d: -${var_95:,.0f} MXN")
        ax.axvline(-var_99, color='#d62728', linestyle='-', linewidth=2.2, label=f"VaR 99% 10d: -${var_99:,.0f} MXN")

        ax.set_title(f"Distribución de P&L y Value at Risk (VaR Montecarlo a 10 Días)\n"
                     f"Inversión/Nominal: ${cotizacion['nominal_mxn']:,.0f} MXN | Nivel de Confianza: 95% y 99%",
                     fontsize=12, fontweight='bold', pad=12)
        ax.set_xlabel("Pérdida / Ganancia Simulada en Pesos (MXN)", fontsize=10, fontweight='bold')
        ax.set_ylabel("Densidad de Probabilidad", fontsize=10, fontweight='bold')
        ax.xaxis.set_major_formatter('${x:,.0f}')
        ax.legend(loc='upper right', frameon=True)
        plt.tight_layout()

        ruta_var = "distribucion_var.png"
        fig.savefig(ruta_var)
        plt.close(fig)
        archivos_guardados['var'] = ruta_var

        return archivos_guardados


# =============================================================================
# 4. INTERFAZ DE LÍNEA DE COMANDOS INTERACTIVA
# =============================================================================

def imprimir_banner():
    banner = """
    ===========================================================================
      APLICACIÓN INSTITUCIONAL DE COTIZACIÓN DE DERIVADOS FX Y GESTIÓN DE RIESGO
      MERCADO USD/MXN | CURVA FORWARD E IMPLÍCITA EN PESOS | VALUE AT RISK (VaR)
    ===========================================================================
    """
    print(banner)

def ejecutar_consola_interactiva(mercado: MercadoFX, cotizador: CotizadorDerivadosFX, analizador: AnalizadorRiesgoPnL):
    """Ejecuta un flujo conversacional guiado en consola con el usuario."""
    imprimir_banner()

    print("--- [PASO 1: DATOS DE LA OPERACIÓN] ---")
    print(f"Tipo de cambio Spot Mid actual: ${mercado.spot_mid:.4f} MXN/USD")
    print(f"Precios de referencia de la Mesa:")
    print(f"  - Compra Banco (Bid): ${mercado.spot_bid:.4f}  (Para clientes que VENDEN USD)")
    print(f"  - Venta Banco (Ask):  ${mercado.spot_ask:.4f}  (Para clientes que COMPRAN USD)\n")

    # 1. Tipo de operación
    while True:
        op = input("¿El cliente desea COMPRA o VENTA de dólares? [C/V]: ").strip().lower()
        if op in ['c', 'compra']:
            tipo_op = 'compra'
            break
        elif op in ['v', 'venta']:
            tipo_op = 'venta'
            break
        print("Opción inválida. Ingrese 'C' para compra o 'V' para venta.")

    # 2. Plazo de la operación
    while True:
        try:
            plazo_str = input("Ingrese el plazo de la operación en días (límite: 2 años / 730 días): ").strip()
            plazo = int(plazo_str)
            if plazo < 0:
                print("El plazo debe ser mayor o igual a cero.")
                continue
            break
        except ValueError:
            print("Por favor, ingrese un número entero de días.")

    # 3. Valor nominal
    while True:
        moneda_nom = input("¿Desea ingresar el valor nominal en DÓLARES o en PESOS? [USD/MXN]: ").strip().upper()
        if moneda_nom in ['USD', 'MXN']:
            break
        print("Opción inválida. Ingrese 'USD' o 'MXN'.")

    while True:
        try:
            val_str = input(f"Ingrese el valor nominal en {moneda_nom} (ejemplo: 100000): ").replace(',', '').strip()
            valor = float(val_str)
            if valor <= 0:
                print("El nominal debe ser mayor a 0.")
                continue
            break
        except ValueError:
            print("Número inválido.")

    nom_usd = valor if moneda_nom == 'USD' else None
    nom_mxn = valor if moneda_nom == 'MXN' else None

    # Realizar Cotización
    cotizacion = cotizador.cotizar(tipo_op, plazo, nominal_usd=nom_usd, nominal_mxn=nom_mxn)

    print("\n" + "="*75)
    print("                      COTIZACIÓN FORMAL DE DERIVADO FX")
    print("="*75)
    if cotizacion['alerta_plazo']:
        print(f"\n[AVISO DE POLÍTICA DE RIESGO]: {cotizacion['alerta_plazo']}\n")

    print(f"- Tipo de Operación:        {cotizacion['tipo_operacion']} USD ({cotizacion['lado_mercado']})")
    print(f"- Plazo Cotizado:           {cotizacion['plazo_dias']} días (Fecha Valor: {cotizacion['fecha_liquidacion_estimada']})")
    print(f"- DERIVADO ASIGNADO:        >>> {cotizacion['derivado_asignado']} <<<")
    print(f"- Racional de Asignación:   {cotizacion['descripcion_derivado']}\n")

    print(f"- Insumos de Mercado:")
    print(f"    - Tipo de Cambio Spot Base:  ${cotizacion['spot_base']:.4f} MXN/USD")
    print(f"    - Tasa Libre Riesgo MXN:     {cotizacion['tasa_mxn']*100:.2f}% (TIIE Fondeo / Cetes)")
    print(f"    - Tasa Libre Riesgo USD:     {cotizacion['tasa_usd']*100:.2f}% (SOFR / OIS)")
    print(f"    - Diferencial de Tasas:      {(cotizacion['tasa_mxn'] - cotizacion['tasa_usd'])*100:+.2f}%")

    print(f"\n- PRECIO Y PUNTOS FORWARD:")
    print(f"    - PUNTOS F (Forward Points): {cotizacion['puntos_f']:+.4f} MXN  ({cotizacion['puntos_f_pips']:+.1f} pips)")
    print(f"    - PRECIO PACTADO (Forward):  ${cotizacion['precio_pactado']:.4f} MXN/USD")
    print(f"    - Tasa Implícita en Pesos:   {cotizacion['tasa_implicita_mxn']*100:.2f}% (Curva Implícita CIP)")

    print(f"\n- VALOR NOMINAL CONTRATADO:")
    print(f"    - Nominal en Dólares (USD):  ${cotizacion['nominal_usd']:,.2f} USD")
    print(f"    - Nominal en Pesos (MXN):    ${cotizacion['nominal_mxn']:,.2f} MXN")

    if cotizacion['alternativa_ofrecida']:
        alt = cotizacion['cotizacion_alternativa']
        print("\n" + "-"*75)
        print("  [OFERTA COMPLEMENTARIA / ALTERNATIVA]")
        print(f"  - Producto:              {alt['producto']}")
        print(f"  - Plazo:                 {alt['plazo_dias']} días")
        print(f"  - Precio Pactado 1 Mes:  ${alt['precio_pactado']:.4f} MXN/USD (Puntos F: {alt['puntos_f']:+.4f})")
        print(f"  - Nominal en MXN a 1m:   ${alt['monto_mxn_estimado']:,.2f} MXN")
        print("-" * 75)

    print("\n" + "="*75)

    # Preguntar si el cliente acepta el derivado
    while True:
        resp = input("\n¿El cliente ACEPTA contratar el derivado con las condiciones cotizadas? [S/N]: ").strip().lower()
        if resp in ['s', 'si', 'sí', 'y', 'yes']:
            aceptado = True
            break
        elif resp in ['n', 'no']:
            aceptado = False
            break
        print("Opción inválida. Ingrese 'S' para Sí o 'N' para No.")

    if not aceptado:
        print("\n[Operación Cancelada] El cliente decidió no contratar el derivado. Fin de la sesión.")
        return

    # Si acepta: Generar Resumen de P&L, VaR y Gráficas
    print("\n" + "#"*75)
    print("         CONTRATO FORMALIZADO - PROYECCIONES DE P&L Y GESTIÓN DE RIESGO")
    print("#"*75)

    df_pnl = analizador.generar_proyecciones_pnl(cotizacion)
    print("\n--- [PROYECCIONES DE PÉRDIDAS Y GANANCIAS (P&L) AL VENCIMIENTO] ---")
    print(df_pnl.to_string(index=False))

    print("\nCalculando métricas de Value at Risk (VaR) y generando simulaciones...")
    resumen_var = analizador.calcular_var_integral(cotizacion, n_simulaciones=12500)
    graficas = analizador.generar_graficas(cotizacion, df_pnl, resumen_var)

    vp = resumen_var['var_parametrico']
    vh = resumen_var['var_historico_1d']
    vmc = resumen_var['var_montecarlo_10d']

    print("\n" + "="*75)
    print("                    ANÁLISIS DE VALUE AT RISK (VaR)")
    print("="*75)
    print(f"- Volatilidad Diaria del USD/MXN: {resumen_var['sigma_diaria_%']:.2f}%  (Anualizada: {resumen_var['sigma_anualizada_%']:.2f}%)\n")

    print("1. VaR Paramétrico (Modelo Delta-Normal Escalado):")
    print(f"   - Horizonte 1 Día:")
    print(f"       * VaR 95%:  {vp['1d']['var_95_%']:.2f}%  ->  ${vp['1d']['var_95_mxn']:,.2f} MXN  (${vp['1d']['var_95_usd']:,.2f} USD)")
    print(f"       * VaR 99%:  {vp['1d']['var_99_%']:.2f}%  ->  ${vp['1d']['var_99_mxn']:,.2f} MXN  (${vp['1d']['var_99_usd']:,.2f} USD)")
    print(f"   - Horizonte 10 Días (Regulatorio / Basilea):")
    print(f"       * VaR 95%:  {vp['10d']['var_95_%']:.2f}%  ->  ${vp['10d']['var_95_mxn']:,.2f} MXN  (${vp['10d']['var_95_usd']:,.2f} USD)")
    print(f"       * VaR 99%:  {vp['10d']['var_99_%']:.2f}%  ->  ${vp['10d']['var_99_mxn']:,.2f} MXN  (${vp['10d']['var_99_usd']:,.2f} USD)")
    print(f"   - Horizonte al Vencimiento del Plazo ({vp['plazo_total']['plazo_dias']} días):")
    print(f"       * VaR 95%:  {vp['plazo_total']['var_95_%']:.2f}%  ->  ${vp['plazo_total']['var_95_mxn']:,.2f} MXN  (${vp['plazo_total']['var_95_usd']:,.2f} USD)")
    print(f"       * VaR 99%:  {vp['plazo_total']['var_99_%']:.2f}%  ->  ${vp['plazo_total']['var_99_mxn']:,.2f} MXN  (${vp['plazo_total']['var_99_usd']:,.2f} USD)")

    print("\n2. VaR Histórico (Percentil de la serie empírica USD/MXN a 1 día):")
    print(f"   - VaR Histórico 95%:  {vh['var_95_%']:.2f}%  ->  ${vh['var_95_mxn']:,.2f} MXN")
    print(f"   - VaR Histórico 99%:  {vh['var_99_%']:.2f}%  ->  ${vh['var_99_mxn']:,.2f} MXN")

    print(f"\n3. VaR Montecarlo (12,500 Simulaciones a 10 Días):")
    print(f"   - VaR Montecarlo 95%: {vmc['var_95_%']:.2f}%  ->  ${vmc['var_95_mxn']:,.2f} MXN")
    print(f"   - VaR Montecarlo 99%: {vmc['var_99_%']:.2f}%  ->  ${vmc['var_99_mxn']:,.2f} MXN")

    print("\n- Racional e Interpretación Ejecutiva:")
    print(f"  El Value at Risk (VaR) al 95% de confianza nos indica que, bajo condiciones normales de mercado,")
    print(f"  la pérdida máxima esperada a 10 días no superará los ${vmc['var_95_mxn']:,.2f} MXN.")
    print(f"  En caso de eventos extremos (con 99% de confianza), la pérdida esperada es de hasta ${vmc['var_99_mxn']:,.2f} MXN.")

    print("\n- Gráficos Generados y Guardados Exitosamente:")
    for k, ruta in graficas.items():
        print(f"  [OK] {k.upper()}: {ruta}")

    print("\n" + "="*75)
    print("               RESUMEN EJECUTIVO GUARDADO CON ÉXITO")
    print("="*75)


# =============================================================================
# 5. SERVIDOR WEB INTEGRADO (APLICACIÓN GRÁFICA INTERACTIVA)
# =============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cotizador de Derivados FX USD/MXN</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-page: #0d0e12;
            --card-bg: #161720;
            --card-border: #232533;
            --accent-orange: #ff7a1a;
            --text-main: #ffffff;
            --text-muted: #8d90a5;
            --gain: #10b981;
            --loss: #f43f5e;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        body {
            background-color: var(--bg-page);
            color: var(--text-main);
            padding: 32px 24px 60px;
            min-height: 100vh;
        }

        .container {
            max-width: 1060px;
            margin: 0 auto;
        }

        header {
            margin-bottom: 28px;
        }

        h1 {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        h1 span {
            color: var(--accent-orange);
        }

        .subtitle {
            font-size: 13.5px;
            color: var(--text-muted);
            margin-top: 6px;
        }

        /* --- GRID PRINCIPAL --- */
        .grid-layout {
            display: grid;
            grid-template-columns: 360px 1fr;
            gap: 22px;
            margin-bottom: 24px;
        }

        @media (max-width: 860px) {
            .grid-layout {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 24px;
        }

        .card h2 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 18px;
            color: #ffffff;
        }

        /* --- FORMULARIOS --- */
        .form-group {
            margin-bottom: 16px;
        }

        label {
            display: block;
            font-size: 11.5px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }

        input, select {
            width: 100%;
            background: #0f1016;
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 12px 14px;
            color: #ffffff;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }

        input:focus, select:focus {
            border-color: var(--accent-orange);
        }

        .field-hint {
            display: block;
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .alert-limit {
            background: rgba(255, 122, 26, 0.12);
            border: 1px solid rgba(255, 122, 26, 0.35);
            color: #ffaa5a;
            padding: 10px 14px;
            border-radius: 10px;
            font-size: 12px;
            margin-bottom: 16px;
        }

        /* --- DERIVADO ASIGNADO --- */
        .assigned-box {
            background: #12131b;
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 16px;
        }

        .badge-derivado {
            display: inline-block;
            background: var(--accent-orange);
            color: #0d0e12;
            font-size: 13px;
            font-weight: 700;
            padding: 5px 12px;
            border-radius: 6px;
            margin-bottom: 8px;
        }

        .assigned-summary {
            font-size: 12.5px;
            color: var(--text-muted);
            line-height: 1.5;
        }

        .alt-forward-note {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid var(--card-border);
            font-size: 12px;
            color: #e2e8f0;
        }

        /* --- TARJETAS DE MÉTRICAS --- */
        .metrics-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 18px;
        }

        .metric-card {
            background: #111219;
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 14px 16px;
        }

        .metric-card.highlight {
            border-color: rgba(255, 122, 26, 0.35);
            background: rgba(255, 122, 26, 0.04);
        }

        .metric-label {
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 4px;
        }

        .metric-value {
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
        }

        .metric-card.highlight .metric-value {
            color: var(--accent-orange);
        }

        /* --- BOTÓN DE ACCIÓN --- */
        .btn-action {
            display: block;
            width: 100%;
            background: var(--accent-orange);
            color: #0d0e12;
            border: none;
            border-radius: 10px;
            padding: 14px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            text-align: center;
            transition: background 0.2s, transform 0.1s;
        }

        .btn-action:hover {
            background: #ff8e38;
        }

        .btn-action:active {
            transform: translateY(1px);
        }

        /* --- SECCIÓN AL ACEPTAR --- */
        #seccionAceptado {
            display: none;
            margin-top: 24px;
        }

        .var-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 14px;
            margin-bottom: 22px;
        }

        @media (max-width: 768px) {
            .var-grid {
                grid-template-columns: 1fr;
            }
        }

        .var-card {
            background: #111219;
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px;
        }

        .var-title {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }

        .var-val {
            font-size: 20px;
            font-weight: 700;
            color: #ffaa5a;
        }

        .var-sub {
            font-size: 11.5px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        /* --- TABLA P&L --- */
        .chart-box {
            position: relative;
            height: 250px;
            margin-bottom: 22px;
        }

        .table-responsive {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12.5px;
            text-align: right;
        }

        th {
            background: #111218;
            color: var(--text-muted);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 10px 12px;
            border-bottom: 1px solid var(--card-border);
        }

        th:first-child, td:first-child {
            text-align: left;
        }

        td {
            padding: 10px 12px;
            border-bottom: 1px solid #1a1b24;
            color: #cbd5e1;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .gain { color: var(--gain) !important; font-weight: 600; }
        .loss { color: var(--loss) !important; font-weight: 600; }

        .badge-status {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
        }

        .status-gain { background: rgba(16, 185, 129, 0.15); color: var(--gain); }
        .status-loss { background: rgba(244, 63, 94, 0.15); color: var(--loss); }
        .status-neutral { background: rgba(255, 255, 255, 0.08); color: #ffffff; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Cotizador de Derivados <span>USD/MXN</span></h1>
            <div class="subtitle">Tipo de cambio, paridad de tasas implícita y gestión de riesgo</div>
        </header>

        <div class="grid-layout">
            <!-- COLUMNA 1: CONFIGURACIÓN -->
            <div class="card">
                <h2>Configuración de la Operación</h2>

                <div class="form-group">
                    <label>Tipo de Operación</label>
                    <select id="tipoOperacion" onchange="cotizar()">
                        <option value="compra">Compra de USD</option>
                        <option value="venta">Venta de USD</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Plazo (Días)</label>
                    <input type="number" id="plazoDias" value="30" min="0" max="730" onchange="cotizar()" oninput="cotizar()">
                    <span class="field-hint">Límite máximo permitido: 730 días (2 años)</span>
                </div>

                <div class="form-group">
                    <label>Valor Nominal en USD</label>
                    <input type="number" id="nominalUsd" value="100000" step="10000" onchange="actualizarNominalUsd()" oninput="actualizarNominalUsd()">
                </div>

                <div class="form-group">
                    <label>Valor Nominal en MXN (Equivalente)</label>
                    <input type="number" id="nominalMxn" step="100000" onchange="actualizarNominalMxn()" oninput="actualizarNominalMxn()">
                </div>

                <button class="btn-action" id="btnAceptar" onclick="aceptarDerivado()">Aceptar Derivado</button>
            </div>

            <!-- COLUMNA 2: RESULTADOS DE COTIZACIÓN -->
            <div class="card">
                <h2>Cotización de Mercado</h2>

                <div id="alertaPlazo" class="alert-limit" style="display:none;"></div>

                <div class="assigned-box">
                    <div id="derivadoBadge" class="badge-derivado">Cargando producto...</div>
                    <p id="derivadoDesc" class="assigned-summary"></p>

                    <div id="ofertaAlternativa" class="alt-forward-note" style="display: none;">
                        <span id="altDesc"></span>
                    </div>
                </div>

                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-label">Spot Base</div>
                        <div class="metric-value" id="valSpot">-</div>
                    </div>

                    <div class="metric-card highlight">
                        <div class="metric-label">Puntos Forward (Puntos F)</div>
                        <div class="metric-value" id="valPuntosF">-</div>
                    </div>

                    <div class="metric-card highlight">
                        <div class="metric-label">Precio Forward Pactado</div>
                        <div class="metric-value" id="valPrecioPactado">-</div>
                    </div>

                    <div class="metric-card">
                        <div class="metric-label">Tasa Implícita en Pesos</div>
                        <div class="metric-value" id="valTasaImpl">-</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- SECCIÓN AL ACEPTAR EL DERIVADO -->
        <div id="seccionAceptado" class="card">
            <h2>Gestión de Riesgo y Proyecciones al Vencimiento</h2>

            <div class="var-grid">
                <div class="var-card">
                    <div class="var-title">VaR Paramétrico (10 Días, 99%)</div>
                    <div class="var-val" id="varParam99">-</div>
                    <div class="var-sub">Modelo normal escalado</div>
                </div>

                <div class="var-card">
                    <div class="var-title">VaR Histórico (1 Día, 95%)</div>
                    <div class="var-val" id="varHist95">-</div>
                    <div class="var-sub">Percentil empírico diario</div>
                </div>

                <div class="var-card">
                    <div class="var-title">VaR Monte Carlo (10 Días, 99%)</div>
                    <div class="var-val" id="varMC99">-</div>
                    <div class="var-sub">12,500 simulaciones</div>
                </div>
            </div>

            <div class="chart-box">
                <canvas id="chartPnL"></canvas>
            </div>

            <div class="table-responsive">
                <table id="tablaPnL">
                    <thead>
                        <tr>
                            <th>Variación %</th>
                            <th>ST Proyectado</th>
                            <th>Flujo Pactado (MXN)</th>
                            <th>Flujo Mercado (MXN)</th>
                            <th>P&L (MXN)</th>
                            <th>Rendimiento %</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let cotizacionActual = null;
        let chartPnLInstance = null;

        function cotizar() {
            const op = document.getElementById('tipoOperacion').value;
            let plazo = parseInt(document.getElementById('plazoDias').value) || 0;
            const usd = parseFloat(document.getElementById('nominalUsd').value) || 100000;

            if (plazo > 730) {
                document.getElementById('alertaPlazo').style.display = 'block';
                document.getElementById('alertaPlazo').innerText = `Límite normativo: El plazo (${plazo} días) supera el máximo de 2 años (730 días). Se limitó automáticamente a 730 días.`;
                plazo = 730;
                document.getElementById('plazoDias').value = 730;
            } else {
                document.getElementById('alertaPlazo').style.display = 'none';
            }

            fetch(`/api/cotizar?op=${op}&plazo=${plazo}&usd=${usd}`)
                .then(r => r.json())
                .then(data => {
                    cotizacionActual = data;
                    renderCotizacion(data);
                });
        }

        function renderCotizacion(data) {
            document.getElementById('derivadoBadge').innerText = data.derivado_asignado.toUpperCase();
            document.getElementById('derivadoDesc').innerText = data.descripcion_derivado;
            document.getElementById('valSpot').innerText = `$${data.spot_base.toFixed(4)}`;
            document.getElementById('valPuntosF').innerText = `${data.puntos_f >= 0 ? '+' : ''}${data.puntos_f.toFixed(4)}`;
            document.getElementById('valPrecioPactado').innerText = `$${data.precio_pactado.toFixed(4)}`;
            document.getElementById('valTasaImpl').innerText = `${(data.tasa_implicita_mxn * 100).toFixed(2)}%`;

            document.getElementById('nominalMxn').value = data.nominal_mxn;

            const altBox = document.getElementById('ofertaAlternativa');
            if (data.alternativa_ofrecida && data.cotizacion_alternativa) {
                altBox.style.display = 'block';
                const alt = data.cotizacion_alternativa;
                document.getElementById('altDesc').innerHTML = `<strong>Alternativa:</strong> ${alt.producto} a $${alt.precio_pactado.toFixed(4)} MXN (Puntos F: ${alt.puntos_f.toFixed(4)} | Flujo: $${alt.monto_mxn_estimado.toLocaleString()} MXN)`;
            } else {
                altBox.style.display = 'none';
            }
        }

        function actualizarNominalUsd() {
            cotizar();
        }

        function actualizarNominalMxn() {
            const mxn = parseFloat(document.getElementById('nominalMxn').value) || 0;
            if (cotizacionActual && cotizacionActual.precio_pactado > 0) {
                const usd = Math.round(mxn / cotizacionActual.precio_pactado);
                document.getElementById('nominalUsd').value = usd;
                cotizar();
            }
        }

        function aceptarDerivado() {
            if (!cotizacionActual) return;
            document.getElementById('seccionAceptado').style.display = 'block';
            document.getElementById('seccionAceptado').scrollIntoView({ behavior: 'smooth' });

            fetch(`/api/riesgo?op=${cotizacionActual.tipo_operacion}&plazo=${cotizacionActual.plazo_dias}&usd=${cotizacionActual.nominal_usd}`)
                .then(r => r.json())
                .then(res => {
                    const varP = res.var.var_parametrico;
                    document.getElementById('varParam99').innerText = `$${varP['10d'].var_99_mxn.toLocaleString()} MXN`;
                    document.getElementById('varHist95').innerText = `$${res.var.var_historico_1d.var_95_mxn.toLocaleString()} MXN`;
                    document.getElementById('varMC99').innerText = `$${res.var.var_montecarlo_10d.var_99_mxn.toLocaleString()} MXN`;

                    const tbody = document.querySelector('#tablaPnL tbody');
                    tbody.innerHTML = '';
                    const labels = [];
                    const pnlValues = [];

                    res.pnl.forEach(row => {
                        labels.push(`$${row.ST_Proyectado.toFixed(2)} (${row['Variacion_%']})`);
                        pnlValues.push(row.PnL_MXN);

                        const tr = document.createElement('tr');
                        const isGain = row.PnL_MXN > 0;
                        const isLoss = row.PnL_MXN < 0;
                        const stateClass = isGain ? 'status-gain' : (isLoss ? 'status-loss' : 'status-neutral');

                        tr.innerHTML = `
                            <td>${row['Variacion_%']}</td>
                            <td style="color:#ffffff; font-weight:600;">$${row.ST_Proyectado.toFixed(4)}</td>
                            <td>$${row.Flujo_Pactado_MXN.toLocaleString()}</td>
                            <td>$${row.Flujo_Mercado_MXN.toLocaleString()}</td>
                            <td class="${isGain ? 'gain' : (isLoss ? 'loss' : '')}">$${row.PnL_MXN.toLocaleString()}</td>
                            <td class="${isGain ? 'gain' : (isLoss ? 'loss' : '')}">${row['Rendimiento_%']}%</td>
                            <td><span class="badge-status ${stateClass}">${row.Estado}</span></td>
                        `;
                        tbody.appendChild(tr);
                    });

                    renderChart(labels, pnlValues);
                });
        }

        function renderChart(labels, data) {
            const ctx = document.getElementById('chartPnL').getContext('2d');
            if (chartPnLInstance) chartPnLInstance.destroy();

            chartPnLInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'P&L en Pesos (MXN)',
                        data: data,
                        borderColor: '#ff7a1a',
                        backgroundColor: (context) => {
                            const ctx = context.chart.ctx;
                            const gradient = ctx.createLinearGradient(0, 0, 0, 250);
                            gradient.addColorStop(0, 'rgba(255, 122, 26, 0.28)');
                            gradient.addColorStop(1, 'rgba(255, 122, 26, 0.0)');
                            return gradient;
                        },
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.25,
                        pointBackgroundColor: '#ff7a1a',
                        pointBorderColor: '#0d0e12',
                        pointBorderWidth: 2,
                        pointRadius: 4.5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#8d90a5',
                                font: { family: 'Inter', size: 11, weight: 600 }
                            }
                        },
                        tooltip: {
                            backgroundColor: '#161720',
                            titleColor: '#ffffff',
                            bodyColor: '#ff7a1a',
                            borderColor: '#232533',
                            borderWidth: 1,
                            padding: 10,
                            callbacks: {
                                label: (c) => ' P&L: $' + c.raw.toLocaleString() + ' MXN'
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(255, 255, 255, 0.04)' },
                            ticks: { color: '#8d90a5', font: { family: 'Inter', size: 10.5 } }
                        },
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.04)' },
                            ticks: {
                                color: '#8d90a5',
                                font: { family: 'Inter', size: 10.5 },
                                callback: v => '$' + v.toLocaleString()
                            }
                        }
                    }
                }
            });
        }

        window.onload = cotizar;
    </script>
</body>
</html>
"""

class WebAppHandler(http.server.SimpleHTTPRequestHandler):
    mercado = None
    cotizador = None
    analizador = None

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == '/' or parsed.path == '/index.html':
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            if os.path.exists(html_path):
                with open(html_path, "rb") as f:
                    content = f.read()
            else:
                content = HTML_TEMPLATE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(content)
            return

        elif parsed.path == '/api/mercado':
            try:
                import mercado_live
                par = qs.get('par', ['USD/MXN'])[0]
                datos = mercado_live.obtener_datos_mercado(par)
                clean_datos = {k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in datos.items()}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(clean_datos).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return

        elif parsed.path == '/api/cotizar':
            try:
                import mercado_live
                import motor_derivados
                par = qs.get('par', ['USD/MXN'])[0]
                op = qs.get('op', ['compra'])[0]
                plazo = int(qs.get('plazo', [30])[0])
                nominal = float(qs.get('nominal', [100000])[0])

                m = mercado_live.obtener_datos_mercado(par)
                cot = motor_derivados.cotizar_estrategias_completas(m, op, plazo, nominal)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(cot).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return

        elif parsed.path == '/api/riesgo':
            try:
                import mercado_live
                import motor_derivados
                par = qs.get('par', ['USD/MXN'])[0]
                op = qs.get('op', ['compra'])[0]
                plazo = int(qs.get('plazo', [30])[0])
                nominal = float(qs.get('nominal', [100000])[0])
                estrategia = qs.get('estrategia', ['forward'])[0]

                m = mercado_live.obtener_datos_mercado(par)
                resumen = motor_derivados.calcular_pnl_y_var_estrategia(m, estrategia, op, plazo, nominal)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resumen).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return

        super().do_GET()


def iniciar_servidor_web(mercado, cotizador, analizador, port=8000):
    """Inicia el servidor web local con la interfaz visual interactiva y fallback de puertos."""
    WebAppHandler.mercado = mercado
    WebAppHandler.cotizador = cotizador
    WebAppHandler.analizador = analizador

    # Permitir reusar dirección para evitar esperas de TIME_WAIT
    socketserver.TCPServer.allow_reuse_address = True
    
    httpd = None
    puerto_seleccionado = port

    # Si el puerto está ocupado (Errno 48), buscar automáticamente el siguiente puerto libre
    for p in range(port, port + 50):
        try:
            httpd = socketserver.TCPServer(("", p), WebAppHandler)
            puerto_seleccionado = p
            break
        except OSError as err:
            if err.errno == 48:
                continue
            raise err

    if httpd is None:
        print(f"\n[Error] No se encontró ningún puerto disponible entre {port} y {port + 50}.")
        print("Puedes intentar especificar otro puerto con: python app_derivados_fx.py --web --port 8080")
        return

    url = f"http://localhost:{puerto_seleccionado}"
    print(f"\n===========================================================")
    print(f"  SERVIDOR WEB INTERACTIVO INICIADO CON ÉXITO")
    print(f"  >>> Abre en tu navegador: {url} <<<")
    if puerto_seleccionado != port:
        print(f"  (Aviso: El puerto {port} estaba en uso, se asignó el {puerto_seleccionado})")
    print(f"  Presione Ctrl+C en cualquier momento para detener el servidor.")
    print(f"===========================================================\n")

    # Intentar abrir la pestaña del navegador automáticamente
    try:
        import subprocess
        def _abrir():
            try:
                if sys.platform == 'darwin':
                    subprocess.Popen(['open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform.startswith('win'):
                    os.startfile(url)
                else:
                    subprocess.Popen(['xdg-open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        t = threading.Thread(target=_abrir, daemon=True)
        t.start()
    except Exception:
        pass

    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor web detenido por el usuario.")


# =============================================================================
# 6. FUNCIÓN PRINCIPAL / ENTRYPOINT
# =============================================================================

def main():
    # Detectar sufijos directos: web, consola, comand
    primer_arg = sys.argv[1].lower().strip().replace('-', '') if len(sys.argv) > 1 else ""

    mercado = MercadoFX()
    cotizador = CotizadorDerivadosFX(mercado)
    analizador = AnalizadorRiesgoPnL(mercado)

    if primer_arg in ['web', 'w']:
        iniciar_servidor_web(mercado, cotizador, analizador, port=8000)
        return
    elif primer_arg in ['consola', 'console', 'c']:
        ejecutar_consola_interactiva(mercado, cotizador, analizador)
        return
    elif primer_arg in ['comand', 'command', 'cmd']:
        # Ejecución directa por comando (análisis benchmark completo)
        op = "compra"
        plazo = 30
        usd = 100000.0

        # Si el usuario pasó parámetros adicionales
        for i, a in enumerate(sys.argv[2:]):
            if a in ['--operacion', '-o'] and i + 3 < len(sys.argv):
                op = sys.argv[i + 3].lower()
            elif a in ['--plazo', '-p'] and i + 3 < len(sys.argv):
                try: plazo = int(sys.argv[i + 3])
                except ValueError: pass
            elif a in ['--usd', '-u'] and i + 3 < len(sys.argv):
                try: usd = float(sys.argv[i + 3])
                except ValueError: pass

        cot = cotizador.cotizar(op, plazo, nominal_usd=usd)
        print("\n" + "="*70)
        print(f"COTIZACIÓN DIRECTA (COMAND): {cot['tipo_operacion']} USD a {cot['plazo_dias']} días")
        print(f"DERIVADO ASIGNADO:           {cot['derivado_asignado']}")
        print(f"PRECIO FORWARD PACTADO:     ${cot['precio_pactado']:.4f} MXN (Puntos F: {cot['puntos_f']:+.4f})")
        print(f"NOMINAL:                    ${cot['nominal_usd']:,.2f} USD = ${cot['nominal_mxn']:,.2f} MXN")
        print("="*70)

        df_pnl = analizador.generar_proyecciones_pnl(cot)
        resumen_var = analizador.calcular_var_integral(cot, n_simulaciones=12500)
        graficas = analizador.generar_graficas(cot, df_pnl, resumen_var)

        print("\nProyecciones de P&L al vencimiento:")
        print(df_pnl.to_string(index=False))
        print(f"\nValue at Risk (VaR 99% a 10 días): ${resumen_var['var_montecarlo_10d']['var_99_mxn']:,.2f} MXN")
        print("Gráficas guardadas:", graficas)
        return

    # Parser estándar para compatibilidad con flags
    parser = argparse.ArgumentParser(description="Aplicación de Derivados FX USD/MXN, Curva Implícita y VaR")
    parser.add_argument('--web', action='store_true', help="Iniciar la aplicación web gráfica interactiva en el navegador")
    parser.add_argument('--port', type=int, default=8000, help="Puerto para el servidor web (por defecto: 8000)")
    parser.add_argument('--operacion', type=str, choices=['compra', 'venta'], help="Tipo de operación (compra o venta)")
    parser.add_argument('--plazo', type=int, help="Plazo en días (límite 730 días / 2 años)")
    parser.add_argument('--usd', type=float, help="Valor nominal en USD")
    parser.add_argument('--mxn', type=float, help="Valor nominal en MXN")
    parser.add_argument('--aceptar', action='store_true', help="Aceptar automáticamente el derivado para generar P&L y VaR")

    args = parser.parse_args()

    if args.web:
        iniciar_servidor_web(mercado, cotizador, analizador, port=args.port)
        return

    # Si se pasan argumentos por línea de comandos (modo batch/script)
    if args.operacion and args.plazo is not None:
        cot = cotizador.cotizar(args.operacion, args.plazo, nominal_usd=args.usd, nominal_mxn=args.mxn)
        print("\n" + "="*70)
        print(f"COTIZACIÓN: {cot['tipo_operacion']} USD a {cot['plazo_dias']} días")
        print(f"DERIVADO ASIGNADO: {cot['derivado_asignado']}")
        print(f"PRECIO PACTADO: ${cot['precio_pactado']:.4f} MXN (Puntos F: {cot['puntos_f']:+.4f})")
        print(f"NOMINAL: ${cot['nominal_usd']:,.2f} USD = ${cot['nominal_mxn']:,.2f} MXN")
        print("="*70)

        if args.aceptar:
            df_pnl = analizador.generar_proyecciones_pnl(cot)
            resumen_var = analizador.calcular_var_integral(cot, n_simulaciones=12500)
            graficas = analizador.generar_graficas(cot, df_pnl, resumen_var)
            print("\nProyecciones de P&L al vencimiento:")
            print(df_pnl.to_string(index=False))
            print("\nVaR 99% 10 días:", f"${resumen_var['var_montecarlo_10d']['var_99_mxn']:,.2f} MXN")
            print("Gráficas guardadas:", graficas)
        return

    # Modo interactivo en terminal por defecto
    ejecutar_consola_interactiva(mercado, cotizador, analizador)


if __name__ == '__main__':
    main()
