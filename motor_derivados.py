"""
=============================================================================
MOTOR CUANTITATIVO DE DERIVADOS Y ESTRATEGIAS FX
=============================================================================
Valuación de:
1. FX Spot (Cash T+0, Tom T+1, Spot T+2, Tom-Next, Spot-Next)
2. FX Swap (Swap Points y Tasa Implícita CIP)
3. FX Forward OTC (Paridad Cubierta de Tasas CIP y Puntos F)
4. Futuros FX (MexDer / CME con Margen Inicial y MTM)
5. Opciones FX (Garman-Kohlhagen: Call y Put con primas y griegas)
=============================================================================
"""

import math
import numpy as np
from datetime import datetime, timedelta

def norm_cdf(x):
    """Función de distribución acumulada de la normal estándar (precisión analítica de Abramowitz-Stegun)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def interpolar_tasas(plazo_dias, curva_local, curva_ext):
    """Interpola linealmente las tasas locales y extranjeras según el plazo."""
    t = max(1, min(plazo_dias, 730))
    dias_loc = sorted(curva_local.keys())
    tasas_loc = [curva_local[d] for d in dias_loc]
    r_loc = float(np.interp(t, dias_loc, tasas_loc))

    dias_ext = sorted(curva_ext.keys())
    tasas_ext = [curva_ext[d] for d in dias_ext]
    r_ext = float(np.interp(t, dias_ext, tasas_ext))
    return r_loc, r_ext


def cotizar_estrategias_completas(mercado_info, operacion="compra", plazo_dias=30, nominal_base=100000.0):
    """
    Cotiza simultáneamente las 5 opciones de inversión / cobertura solicitadas por el profesor:
    1. FX Spot
    2. FX Forward
    3. FX Swap
    4. Futuro FX
    5. Opciones FX (Garman-Kohlhagen)
    """
    es_compra = (operacion.lower() in ["compra", "c", "buy"])
    spot_mid = mercado_info["spot_mid"]
    spot_base = mercado_info["spot_ask"] if es_compra else mercado_info["spot_bid"]
    vol_anual = mercado_info["volatilidad_anual"]
    simb_base = mercado_info["simbolo_base"]
    simb_cot = mercado_info["simbolo_cotizada"]

    # Validación de límite normativo
    plazo_solicitado = plazo_dias
    alerta_plazo = ""
    if plazo_dias > 730:
        alerta_plazo = f"El plazo de {plazo_dias} días excede el límite máximo de política de riesgo de 2 años (730 días). Se acotó a 730 días."
        plazo_dias = 730
    elif plazo_dias < 0:
        plazo_dias = 0

    r_loc, r_ext = interpolar_tasas(plazo_dias, mercado_info["curva_local"], mercado_info["curva_ext"])
    T = max(plazo_dias, 1) / 360.0

    # -------------------------------------------------------------------------
    # 1. FX Forward por Paridad Cubierta de Tasas (CIP)
    # -------------------------------------------------------------------------
    factor_loc = 1.0 + r_loc * T
    factor_ext = 1.0 + r_ext * T
    fwd_precio = round(spot_base * (factor_loc / factor_ext), 4)
    puntos_f = round(fwd_precio - spot_base, 4)
    puntos_pips = round(puntos_f * 10000.0, 1)

    # Tasa implícita de fondeo en pesos (CIP)
    tasa_implicita = ((fwd_precio / spot_base) * factor_ext - 1.0) / T if T > 0 else r_loc

    # -------------------------------------------------------------------------
    # 2. Opciones FX (Modelo Garman-Kohlhagen 1983)
    # -------------------------------------------------------------------------
    strike = fwd_precio  # Opción At-The-Money Forward
    sigma = max(vol_anual, 0.05)
    T_opcion = max(plazo_dias, 1) / 365.0  # Base año continuo para Black-Scholes

    d1 = (math.log(spot_base / strike) + (r_loc - r_ext + 0.5 * sigma**2) * T_opcion) / (sigma * math.sqrt(T_opcion))
    d2 = d1 - sigma * math.sqrt(T_opcion)

    nd1 = norm_cdf(d1)
    nd2 = norm_cdf(d2)
    n_minus_d1 = norm_cdf(-d1)
    n_minus_d2 = norm_cdf(-d2)

    # Descuentos continuos
    disc_ext = math.exp(-r_ext * T_opcion)
    disc_loc = math.exp(-r_loc * T_opcion)

    call_unit = spot_base * disc_ext * nd1 - strike * disc_loc * nd2
    put_unit = strike * disc_loc * n_minus_d2 - spot_base * disc_ext * n_minus_d1

    if es_compra:
        tipo_opcion = "Call FX (Derecho a Comprar USD)"
        prima_unitaria = max(call_unit, 0.0001)
        delta = disc_ext * nd1
    else:
        tipo_opcion = "Put FX (Derecho a Vender USD)"
        prima_unitaria = max(put_unit, 0.0001)
        delta = -disc_ext * n_minus_d1

    prima_total = round(nominal_base * prima_unitaria, 2)
    prima_pct = round((prima_unitaria / spot_base) * 100.0, 2)

    # -------------------------------------------------------------------------
    # 3. Futuros FX (MexDer / CME)
    # -------------------------------------------------------------------------
    margen_garantia_pct = 0.06  # 6% de Margen Inicial (AIM) típico en MexDer
    margen_inicial_total = round(nominal_base * fwd_precio * margen_garantia_pct, 2)

    # -------------------------------------------------------------------------
    # 4. Asignación de Plazos Interbancarios
    # -------------------------------------------------------------------------
    if plazo_dias == 0:
        convencion_plazo = "Cash (T+0 - Mismo Día)"
    elif plazo_dias == 1:
        convencion_plazo = "Tom (T+1 - 24 Horas)"
    elif plazo_dias == 2:
        convencion_plazo = "Spot (T+2 - 48 Horas Convención Internacional)"
    elif plazo_dias == 3:
        convencion_plazo = "Tom-Next (T/N Rollover 1d)"
    elif plazo_dias <= 7:
        convencion_plazo = "1 Semana (1W)"
    elif plazo_dias <= 14:
        convencion_plazo = "2 Semanas (2W)"
    elif plazo_dias <= 30:
        convencion_plazo = "1 Mes (1M)"
    elif plazo_dias <= 60:
        convencion_plazo = "2 Meses (2M)"
    elif plazo_dias <= 90:
        convencion_plazo = "3 Meses (3M)"
    elif plazo_dias <= 180:
        convencion_plazo = "6 Meses (6M)"
    elif plazo_dias <= 360:
        convencion_plazo = "1 Año (1Y)"
    else:
        convencion_plazo = "2 Años (2Y - Límite Máximo)"

    # -------------------------------------------------------------------------
    # Construir Catálogo de las 5 Opciones
    # -------------------------------------------------------------------------
    opciones_catalogo = []

    # Opción 1: FX Spot
    es_spot_viable = (plazo_dias <= 2)
    opciones_catalogo.append({
        "id": "spot",
        "nombre": "FX Spot (Mercado de Contado)",
        "subtitulo": f"Liquidación inmediata {convencion_plazo}",
        "precio": spot_base,
        "puntos_f": 0.0,
        "costo_inicial": 0.0,
        "garantia": 0.0,
        "tasa_impl": r_loc,
        "nominal_cotizada": round(nominal_base * spot_base, 2),
        "descripcion": "Intercambio de divisas al contado directo. Sin costos de financiamiento ni puntos forward.",
        "perfil_riesgo": "Exposición total al tipo de cambio de mercado al momento del pacto.",
        "es_recomendada": es_spot_viable,
        "razon_recomendacion": "Plazo de 2 días o menos: La convención estándar de mercado Spot/Cash es la opción óptima sin incurrir en swaps." if es_spot_viable else ""
    })

    # Opción 2: FX Swap
    es_swap_viable = (plazo_dias > 2 and plazo_dias <= 180)
    opciones_catalogo.append({
        "id": "swap",
        "nombre": "FX Swap (Swap Cambiario)",
        "subtitulo": f"Pata spot + Pata forward a {plazo_dias}d",
        "precio": fwd_precio,
        "puntos_f": puntos_f,
        "costo_inicial": 0.0,
        "garantia": 0.0,
        "tasa_impl": tasa_implicita,
        "nominal_cotizada": round(nominal_base * fwd_precio, 2),
        "descripcion": f"Pacta simultáneamente la compra/venta spot y su reversa a futuro. Elimina el riesgo cambiario neto y permite fondearse a la tasa implícita ({tasa_implicita*100:.2f}%).",
        "perfil_riesgo": "Riesgo cambiario CERO (fondos cubiertos en ambas fechas). Solo sujeto a riesgo de liquidez y tasas.",
        "es_recomendada": es_swap_viable,
        "razon_recomendacion": f"Plazo intermedio ({plazo_dias}d): Ideal para tesorerías que buscan mover divisas y fondearse sin riesgo cambiario." if es_swap_viable else ""
    })

    # Opción 3: FX Forward OTC
    es_fwd_viable = (plazo_dias > 2 and not es_swap_viable)
    opciones_catalogo.append({
        "id": "forward",
        "nombre": "FX Forward (Contrato a Plazo OTC)",
        "subtitulo": f"Fijación de tipo de cambio a {plazo_dias}d",
        "precio": fwd_precio,
        "puntos_f": puntos_f,
        "costo_inicial": 0.0,
        "garantia": 0.0,
        "tasa_impl": tasa_implicita,
        "nominal_cotizada": round(nominal_base * fwd_precio, 2),
        "descripcion": f"Congela el tipo de cambio futuro a ${fwd_precio:.4f} MXN. Sin desembolso inicial. 100% de certidumbre para presupuestos y flujos futuros.",
        "perfil_riesgo": "Cobertura simétrica total. Elimina pérdidas por devaluación, pero renuncia a ganancias si el tipo de cambio mejora.",
        "es_recomendada": es_fwd_viable,
        "razon_recomendacion": f"Plazo largo ({plazo_dias}d): Cobertura formal sin costo inicial para congelar flujos exactos." if es_fwd_viable else ""
    })

    # Opción 4: Futuro FX
    opciones_catalogo.append({
        "id": "futuro",
        "nombre": "Futuro FX (MexDer / CME)",
        "subtitulo": f"Contrato estandarizado en bolsa a {plazo_dias}d",
        "precio": fwd_precio,
        "puntos_f": puntos_f,
        "costo_inicial": 0.0,
        "garantia": margen_inicial_total,
        "tasa_impl": tasa_implicita,
        "nominal_cotizada": round(nominal_base * fwd_precio, 2),
        "descripcion": f"Negociado en bolsa organizada con liquidación diaria Mark-to-Market (MTM) y Cámara de Compensación. Requiere Aportación Inicial Mínima (AIM) de ${margen_inicial_total:,.2f} MXN (6%).",
        "perfil_riesgo": "Sin riesgo de crédito de contraparte gracias a la Cámara. Requiere liquidez diaria para llamadas de margen.",
        "es_recomendada": False,
        "razon_recomendacion": ""
    })

    # Opción 5: Opciones FX (Garman-Kohlhagen)
    opciones_catalogo.append({
        "id": "opcion",
        "nombre": f"Opción FX ({tipo_opcion})",
        "subtitulo": f"Strike ATM ${strike:.4f} a {plazo_dias}d",
        "precio": strike,
        "puntos_f": puntos_f,
        "costo_inicial": prima_total,
        "garantia": 0.0,
        "tasa_impl": tasa_implicita,
        "nominal_cotizada": round(nominal_base * strike, 2),
        "prima_pct": prima_pct,
        "delta": round(delta, 3),
        "descripcion": f"Seguro cambiario: Derecho pero no obligación. Paga una prima de ${prima_total:,.2f} MXN ({prima_pct}%). Si el mercado se mueve en contra, tu pérdida máxima es la prima; si favorece, participas de ganancias ilimitadas.",
        "perfil_riesgo": "Riesgo asimétrico acotado estrictamente a la prima pagada.",
        "es_recomendada": (plazo_dias >= 14 and not es_swap_viable and not es_fwd_viable),
        "razon_recomendacion": "Protección con seguro: Conserva la ganancia si el mercado te favorece."
    })

    return {
        "par": mercado_info["par"],
        "operacion": "COMPRA" if es_compra else "VENTA",
        "es_compra": es_compra,
        "plazo_dias": plazo_dias,
        "plazo_solicitado": plazo_solicitado,
        "alerta_plazo": alerta_plazo,
        "convencion_plazo": convencion_plazo,
        "spot_base": spot_base,
        "spot_mid": spot_mid,
        "fwd_precio": fwd_precio,
        "puntos_f": puntos_f,
        "puntos_pips": puntos_pips,
        "r_loc": r_loc,
        "r_ext": r_ext,
        "tasa_implicita": tasa_implicita,
        "nominal_base": nominal_base,
        "nominal_cotizada": round(nominal_base * fwd_precio, 2),
        "opciones": opciones_catalogo
    }


def calcular_pnl_y_var_estrategia(mercado_info, estrategia_id, operacion="compra", plazo_dias=30, nominal_base=100000.0):
    """
    Calcula la matriz de P&L al vencimiento y el Value at Risk (VaR) para la estrategia seleccionada.
    """
    cotiz = cotizar_estrategias_completas(mercado_info, operacion, plazo_dias, nominal_base)
    es_compra = cotiz["es_compra"]
    fwd_precio = cotiz["fwd_precio"]
    nominal_base = cotiz["nominal_base"]
    nominal_mxn = cotiz["nominal_cotizada"]

    # Extraer parámetros de la estrategia seleccionada
    estrategia = next((o for o in cotiz["opciones"] if o["id"] == estrategia_id), cotiz["opciones"][1])
    precio_pactado = estrategia["precio"]
    prima_pagada = estrategia.get("costo_inicial", 0.0)

    # 1. Matriz de P&L de -15% a +15%
    variaciones = [-0.15, -0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, 0.15]
    escenarios = []

    for v in variaciones:
        st = round(fwd_precio * (1.0 + v), 4)

        if estrategia_id == "opcion":
            # Perfil no lineal de opción
            if es_compra:
                payoff_bruto = max(st - precio_pactado, 0.0) * nominal_base
            else:
                payoff_bruto = max(precio_pactado - st, 0.0) * nominal_base
            pnl_neto = round(payoff_bruto - prima_pagada, 2)
        else:
            # Perfil lineal Forward / Swap / Futuro / Spot
            if es_compra:
                pnl_neto = round(nominal_base * (st - precio_pactado), 2)
            else:
                pnl_neto = round(nominal_base * (precio_pactado - st), 2)

        flujo_mercado = round(nominal_base * st, 2)
        rend_pct = round((pnl_neto / nominal_mxn) * 100.0, 2)
        estado = "GANANCIA" if pnl_neto > 0 else ("PÉRDIDA" if pnl_neto < 0 else "PRECIO PACTADO")

        escenarios.append({
            "variacion_pct": f"{v*100:+.1f}%",
            "st_proyectado": st,
            "flujo_pactado": nominal_mxn,
            "flujo_mercado": flujo_mercado,
            "pnl_neto": pnl_neto,
            "rendimiento_pct": rend_pct,
            "estado": estado
        })

    # 2. Medición de Value at Risk (VaR)
    retornos = mercado_info["retornos_historicos"]
    sigma_diaria = mercado_info["volatilidad_diaria"]
    mu_diaria = float(np.mean(retornos))

    sigma_10d = sigma_diaria * math.sqrt(10)
    z_95 = 1.64485
    z_99 = 2.32635

    # A) VaR Paramétrico (Delta-Normal a 1d y 10d)
    var_p95_1d = z_95 * sigma_diaria * nominal_mxn
    var_p99_1d = z_99 * sigma_diaria * nominal_mxn
    var_p95_10d = z_95 * sigma_10d * nominal_mxn
    var_p99_10d = z_99 * sigma_10d * nominal_mxn

    # Si es opción, la pérdida máxima está acotada por la prima pagada
    if estrategia_id == "opcion":
        var_p95_10d = min(var_p95_10d, prima_pagada)
        var_p99_10d = min(var_p99_10d, prima_pagada)

    # B) VaR Histórico (1 día empírico)
    ret_posicion = retornos if es_compra else -retornos
    p5_hist = abs(float(np.percentile(ret_posicion, 5)))
    p1_hist = abs(float(np.percentile(ret_posicion, 1)))
    var_h95_1d = p5_hist * nominal_mxn
    var_h99_1d = p1_hist * nominal_mxn

    # C) VaR Monte Carlo (10 días con 12,500 simulaciones)
    n_sim = 12500
    np.random.seed(42)
    shocks = np.random.normal(0, 1, n_sim)
    sim_ret_10d = mu_diaria * 10 + sigma_10d * shocks
    sim_pnl_pct = sim_ret_10d if es_compra else -sim_ret_10d
    sim_pnl_mxn = sim_pnl_pct * nominal_mxn

    if estrategia_id == "opcion":
        # Ajuste de payoff para Monte Carlo en opción
        st_sims = fwd_precio * (1.0 + sim_ret_10d)
        if es_compra:
            sim_pnl_mxn = np.maximum(st_sims - precio_pactado, 0.0) * nominal_base - prima_pagada
        else:
            sim_pnl_mxn = np.maximum(precio_pactado - st_sims, 0.0) * nominal_base - prima_pagada
        sim_perdidas = -sim_pnl_mxn
        var_mc95_10d = max(float(np.percentile(sim_perdidas, 95)), 0.0)
        var_mc99_10d = max(float(np.percentile(sim_perdidas, 99)), 0.0)
    else:
        mc_p5 = abs(float(np.percentile(sim_pnl_pct, 5)))
        mc_p1 = abs(float(np.percentile(sim_pnl_pct, 1)))
        var_mc95_10d = mc_p5 * nominal_mxn
        var_mc99_10d = mc_p1 * nominal_mxn

    return {
        "cotizacion": cotiz,
        "estrategia_seleccionada": estrategia,
        "escenarios_pnl": escenarios,
        "var": {
            "volatilidad_diaria_pct": round(sigma_diaria * 100, 2),
            "volatilidad_anual_pct": round(mercado_info["volatilidad_anual"] * 100, 2),
            "var_param_95_10d": round(var_p95_10d, 2),
            "var_param_99_10d": round(var_p99_10d, 2),
            "var_param_95_1d": round(var_p95_1d, 2),
            "var_param_99_1d": round(var_p99_1d, 2),
            "var_hist_95_1d": round(var_h95_1d, 2),
            "var_hist_99_1d": round(var_h99_1d, 2),
            "var_mc_95_10d": round(var_mc95_10d, 2),
            "var_mc_99_10d": round(var_mc99_10d, 2)
        }
    }
