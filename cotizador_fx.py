# Proyecto: Cotizador de Derivados FX USD/MXN y Medición de Riesgo (VaR)
# Materia: Administración de Riesgos Financieros
#
# Descripción:
# Calcula el precio de compra o venta de dólares a plazo, asigna el derivado
# correspondiente según el plazo (FX Spot o FX Swap + alternativa Forward a 1 mes),
# valúa con la curva forward e implícita en pesos (paridad CIP), genera la matriz
# de pérdidas y ganancias (P&L) al vencimiento y calcula el VaR (Paramétrico,
# Histórico y Monte Carlo con 12,500 simulaciones).

import math
import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# =============================================================================
# 1. Insumos de Mercado (Spot, Curvas de Tasas y Serie Histórica)
# =============================================================================

# Tipo de cambio Spot de referencia de la mesa
spot_mid = 20.1000
spread = 0.0400
spot_bid = spot_mid - spread / 2.0   # 20.0800: Banco compra USD (cliente vende USD)
spot_ask = spot_mid + spread / 2.0   # 20.1200: Banco vende USD (cliente compra USD)

# Curvas de tasas libres de riesgo (porcentaje anualizado)
# México: Curva representativa TIIE Fondeo / Cetes según el plazo en días
curva_mxn = {
    1: 0.1050,    # Fondeo O/N (10.50%)
    7: 0.1048,    # 1 semana (10.48%)
    28: 0.1040,   # 1 mes / 28 días (10.40%)
    91: 0.1025,   # 3 meses / 91 días (10.25%)
    182: 0.1010,  # 6 meses / 182 días (10.10%)
    364: 0.0985,  # 1 año (9.85%)
    728: 0.0950   # 2 años (9.50%)
}

# Estados Unidos: Curva representativa SOFR / OIS
curva_usd = {
    1: 0.0480,    # SOFR O/N (4.80%)
    7: 0.0478,    # 1 semana (4.78%)
    28: 0.0470,   # 1 mes (4.70%)
    91: 0.0455,   # 3 meses (4.55%)
    182: 0.0440,  # 6 meses (4.40%)
    364: 0.0415,  # 1 año (4.15%)
    728: 0.0395   # 2 años (3.95%)
}

# Listas de nodos para interpolación lineal de tasas
dias_mx = sorted(curva_mxn.keys())
tasas_mx = [curva_mxn[d] for d in dias_mx]

dias_us = sorted(curva_usd.keys())
tasas_us = [curva_usd[d] for d in dias_us]

# Cargar serie histórica de USD/MXN
# Si el archivo CSV está en la carpeta lo lee, si estás en Colab genera la serie calibrada
archivo_historico = "historico_usdmxn.csv"
if os.path.exists(archivo_historico):
    df_hist = pd.read_csv(archivo_historico)
    precios = df_hist['USDMXN'].values
else:
    # Serie histórica calibrada de 504 días (~2 años) con volatilidad del 11.5% anual
    np.random.seed(42)
    shocks = np.random.normal(0, 1, 504)
    rendimientos_sim = (0.035 - 0.5 * 0.115**2) * (1/252) + 0.115 * np.sqrt(1/252) * shocks
    precios = [18.20]
    for r in rendimientos_sim[1:]:
        precios.append(precios[-1] * np.exp(r))
    factor = spot_mid / precios[-1]
    precios = np.array([round(p * factor, 4) for p in precios])

# Volatilidad diaria histórica del tipo de cambio
retornos = np.diff(precios) / precios[:-1]
sigma_diaria = float(np.std(retornos, ddof=1))
mu_diaria = float(np.mean(retornos))

# =============================================================================
# 2. Interacción con el usuario: Datos de la operación
# =============================================================================

print("=" * 65)
print("      COTIZADOR DE DERIVADOS FX USD/MXN Y GESTIÓN DE RIESGO")
print("=" * 65)
print(f"Tipo de cambio Spot de Referencia: ${spot_mid:.4f} MXN/USD")
print(f"Precios de Mesa: Compra Banco (Bid) = ${spot_bid:.4f} | Venta Banco (Ask) = ${spot_ask:.4f}\n")

# 1. Tipo de operación
op = input("1. ¿El cliente desea COMPRA o VENTA de dólares? (c/v): ").strip().lower()
es_compra = (op in ['c', 'compra'])
operacion = "COMPRA" if es_compra else "VENTA"
spot_base = spot_ask if es_compra else spot_bid

# 2. Plazo de inversión / cobertura
plazo = int(input("2. Ingrese el plazo en días a invertir o cubrir: ").strip())

# Límite normativo de riesgo: máximo 2 años (730 días)
if plazo > 730:
    print(f"\n[Aviso]: El plazo solicitado ({plazo} días) supera el límite de riesgo (2 años / 730 días).")
    print("Se ajusta automáticamente al máximo permitido de 730 días.\n")
    plazo = 730
elif plazo < 0:
    plazo = 0

# 3. Valor nominal
moneda = input("3. ¿Ingresará el valor nominal en DÓLARES o en PESOS? (usd/mxn): ").strip().lower()
monto = float(input(f"   Ingrese el monto nominal en {moneda.upper()}: ").replace(',', '').strip())

# =============================================================================
# 3. Asignación del Derivado y Valuación por Paridad de Tasas (CIP)
# =============================================================================

# Interpolación lineal de tasas para el plazo solicitado
r_mxn = float(np.interp(plazo, dias_mx, tasas_mx))
r_usd = float(np.interp(plazo, dias_us, tasas_us))

# Regla de asignación según el plazo:
if plazo <= 2:
    # Corto plazo (<= 2 días): Mercado de contado (FX Spot)
    if plazo == 0:
        derivado = "FX Spot (Cash T+0 - Mismo Día)"
    elif plazo == 1:
        derivado = "FX Spot (Tom T+1 - 24 Horas)"
    else:
        derivado = "FX Spot (Spot T+2 - 48 Horas Estándar)"
    racional = "Operación de contado directo. Para plazos de 2 días o menos no se requiere una estructura de swap ni forward, ya que la liquidación estándar del mercado de divisas cubre la necesidad de liquidez inmediata."
    precio_pactado = spot_base
    puntos_f = 0.0
    puntos_pips = 0.0
    tasa_implicita = r_mxn
    tiene_alternativa = False
else:
    # Mayor a 2 días: FX Swap y se ofrece como alternativa un Forward a 1 mes (28 días)
    derivado = "FX Swap (Swap Cambiario)"
    racional = f"Al ser un plazo de {plazo} días (> 2 días), el FX Swap permite fondear e intercambiar divisas al contado y pactar simultáneamente la operación inversa a futuro a precio forward, eliminando el riesgo cambiario neto."
    
    # Paridad Cubierta de Tasas (CIP):
    # F = S * [ (1 + r_mxn * t/360) / (1 + r_usd * t/360) ]
    factor_mx = 1.0 + r_mxn * (plazo / 360.0)
    factor_us = 1.0 + r_usd * (plazo / 360.0)
    precio_pactado = round(spot_base * (factor_mx / factor_us), 4)
    
    # Puntos Forward (Puntos F = F - S)
    puntos_f = round(precio_pactado - spot_base, 4)
    puntos_pips = round(puntos_f * 10000.0, 1)

    # Curva Implícita en Pesos (despejada de la paridad de tasas CIP):
    # r_impl = [ (F/S) * (1 + r_usd * t/360) - 1 ] * (360/t)
    t_factor = plazo / 360.0
    tasa_implicita = ((precio_pactado / spot_base) * (1.0 + r_usd * t_factor) - 1.0) * (1.0 / t_factor)

    # Cotización alternativa de Forward a 1 mes (28 días)
    r_mxn_1m = float(np.interp(28, dias_mx, tasas_mx))
    r_usd_1m = float(np.interp(28, dias_us, tasas_us))
    fwd_1m = round(spot_base * ((1.0 + r_mxn_1m * (28 / 360.0)) / (1.0 + r_usd_1m * (28 / 360.0))), 4)
    puntos_f_1m = round(fwd_1m - spot_base, 4)
    tiene_alternativa = True

# Cálculo de nominales equivalentes
if moneda == 'usd':
    nominal_usd = monto
    nominal_mxn = round(nominal_usd * precio_pactado, 2)
else:
    nominal_mxn = monto
    nominal_usd = round(nominal_mxn / precio_pactado, 2)

# Desplegar resumen de cotización al cliente
print("\n" + "=" * 65)
print("             RESUMEN DE COTIZACIÓN COMERCIAL")
print("=" * 65)
print(f"Operación:                 {operacion} de USD")
print(f"Plazo Cotizado:            {plazo} días")
print(f"DERIVADO ASIGNADO:         >>> {derivado} <<<")
print(f"Racional:                  {racional}\n")
print(f"Spot Base de Mesa:         ${spot_base:.4f} MXN/USD")
print(f"Tasa MXN (Mercado):        {r_mxn*100:.2f}% (TIIE Fondeo / Cetes)")
print(f"Tasa USD (Mercado):        {r_usd*100:.2f}% (SOFR / OIS)")
print(f"PUNTOS FORWARD (Puntos F): {puntos_f:+.4f} MXN  ({puntos_pips:+.1f} pips)")
print(f"PRECIO PACTADO (Forward):  ${precio_pactado:.4f} MXN/USD")
print(f"Tasa Implícita en Pesos:   {tasa_implicita*100:.2f}% anual\n")
print(f"Nominal en Dólares:        ${nominal_usd:,.2f} USD")
print(f"Nominal en Pesos:          ${nominal_mxn:,.2f} MXN")

if tiene_alternativa:
    print("\n--- Alternativa Ofrecida ---")
    print("Producto:                  FX Forward a 1 Mes (28 días)")
    print(f"Precio Forward a 1 mes:    ${fwd_1m:.4f} MXN (Puntos F: {puntos_f_1m:+.4f})")
    print(f"Equivalente en Pesos:      ${nominal_usd * fwd_1m:,.2f} MXN")
print("=" * 65)

# =============================================================================
# 4. Aceptación del cliente, Proyecciones de P&L y Value at Risk (VaR)
# =============================================================================

aceptar = input("\n¿El cliente ACEPTA contratar el derivado con estas condiciones? (s/n): ").strip().lower()

if aceptar not in ['s', 'si', 'sí', 'y', 'yes']:
    print("\nOperación cancelada por el cliente. No se generaron contratos.")
else:
    print("\n" + "#" * 65)
    print("      CONTRATO FORMALIZADO: PROYECCIONES DE P&L Y RIESGO")
    print("#" * 65)

    # 1. Matriz de escenarios de pérdidas y ganancias (P&L) al vencimiento
    variaciones = [-0.15, -0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, 0.15]
    filas_pnl = []

    for v in variaciones:
        st = round(precio_pactado * (1.0 + v), 4)
        # Si compró dólares: gana si el dólar sube (ST > F), pierde si baja
        # Si vendió dólares: gana si el dólar baja (F > ST), pierde si sube
        if es_compra:
            pnl = round(nominal_usd * (st - precio_pactado), 2)
        else:
            pnl = round(nominal_usd * (precio_pactado - st), 2)
        
        flujo_mercado = round(nominal_usd * st, 2)
        pnl_usd = round(pnl / st, 2)
        rend = round((pnl / nominal_mxn) * 100.0, 2)
        estado = "GANANCIA" if pnl > 0 else ("PÉRDIDA" if pnl < 0 else "PRECIO PACTADO")

        filas_pnl.append({
            'Variación %': f"{v*100:+.1f}%",
            'ST Proyectado': st,
            'Flujo Pactado (MXN)': nominal_mxn,
            'Flujo Mercado (MXN)': flujo_mercado,
            'P&L (MXN)': pnl,
            'P&L (USD)': pnl_usd,
            'Rendimiento %': f"{rend:+.2f}%",
            'Estado': estado
        })

    df_pnl = pd.DataFrame(filas_pnl)
    print("\n--- MATRIZ DE ESCENARIOS DE PÉRDIDAS Y GANANCIAS (P&L) AL VENCIMIENTO ---")
    print(df_pnl.to_string(index=False))

    # 2. Cálculo de Value at Risk (VaR)
    # A) VaR Paramétrico a 10 días (regla de la raíz del tiempo)
    sigma_10d = sigma_diaria * np.sqrt(10)
    var_param_95 = 1.645 * sigma_10d * nominal_mxn
    var_param_99 = 2.326 * sigma_10d * nominal_mxn

    # B) VaR Histórico (1 día empírico)
    ret_posicion = retornos if es_compra else -retornos
    var_hist_95 = abs(float(np.percentile(ret_posicion, 5))) * nominal_mxn
    var_hist_99 = abs(float(np.percentile(ret_posicion, 1))) * nominal_mxn

    # C) VaR Monte Carlo (10 días con 12,500 simulaciones estocásticas)
    np.random.seed(42)
    shocks_mc = np.random.normal(0, 1, 12500)
    sim_ret_10d = mu_diaria * 10 + sigma_10d * shocks_mc
    sim_pnl_pct = sim_ret_10d if es_compra else -sim_ret_10d
    sim_pnl_mxn = sim_pnl_pct * nominal_mxn

    var_mc_95 = abs(float(np.percentile(sim_pnl_pct, 5))) * nominal_mxn
    var_mc_99 = abs(float(np.percentile(sim_pnl_pct, 1))) * nominal_mxn

    print("\n" + "-" * 65)
    print("                  MEDICIÓN DE VALUE AT RISK (VaR)")
    print("-" * 65)
    print(f"Volatilidad Diaria USD/MXN: {sigma_diaria*100:.2f}%  (Anualizada: {sigma_diaria*np.sqrt(252)*100:.2f}%)\n")

    print("1. VaR Paramétrico (Horizonte 10 Días):")
    print(f"   - Confianza 95%:  ${var_param_95:,.2f} MXN  ({(var_param_95/nominal_mxn)*100:.2f}%)")
    print(f"   - Confianza 99%:  ${var_param_99:,.2f} MXN  ({(var_param_99/nominal_mxn)*100:.2f}%)\n")

    print("2. VaR Histórico (Horizonte 1 Día):")
    print(f"   - Confianza 95%:  ${var_hist_95:,.2f} MXN  ({(var_hist_95/nominal_mxn)*100:.2f}%)")
    print(f"   - Confianza 99%:  ${var_hist_99:,.2f} MXN  ({(var_hist_99/nominal_mxn)*100:.2f}%)\n")

    print("3. VaR Monte Carlo (10 Días con 12,500 Simulaciones):")
    print(f"   - Confianza 95%:  ${var_mc_95:,.2f} MXN  ({(var_mc_95/nominal_mxn)*100:.2f}%)")
    print(f"   - Confianza 99%:  ${var_mc_99:,.2f} MXN  ({(var_mc_99/nominal_mxn)*100:.2f}%)")
    print("=" * 65)

    # 3. Gráficas financieras con Matplotlib
    # Gráfica 1: Perfil de Payoff de Pérdidas y Ganancias
    plt.figure(figsize=(9, 4.5))
    plt.plot(df_pnl['ST Proyectado'], df_pnl['P&L (MXN)'], marker='o', color='#ff7a1a', linewidth=2.2, label='Perfil P&L')
    plt.axhline(0, color='black', linestyle='--', linewidth=0.8)
    plt.axvline(precio_pactado, color='red', linestyle=':', linewidth=1.5, label=f'Precio Pactado (${precio_pactado:.4f})')
    plt.fill_between(df_pnl['ST Proyectado'], df_pnl['P&L (MXN)'], 0, where=(df_pnl['P&L (MXN)'] >= 0), color='#10b981', alpha=0.25, label='Zona de Ganancia')
    plt.fill_between(df_pnl['ST Proyectado'], df_pnl['P&L (MXN)'], 0, where=(df_pnl['P&L (MXN)'] < 0), color='#f43f5e', alpha=0.25, label='Zona de Pérdida')
    plt.title(f"Perfil de Payoff P&L - Posición {operacion} USD ({derivado})", fontweight='bold')
    plt.xlabel("Tipo de Cambio al Vencimiento ST (MXN/USD)")
    plt.ylabel("P&L en Pesos (MXN)")
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Gráfica 2: Distribución simulada de Monte Carlo y cortes de VaR
    plt.figure(figsize=(9, 4.5))
    plt.hist(sim_pnl_mxn, bins=70, color='#2563eb', alpha=0.65, edgecolor='#1e40af', density=True, label='Simulaciones Monte Carlo (N=12,500)')
    plt.axvline(-var_mc_95, color='#ff7a1a', linestyle='--', linewidth=2.0, label=f"VaR 95% (-${var_mc_95:,.0f} MXN)")
    plt.axvline(-var_mc_99, color='#ef4444', linestyle='-', linewidth=2.2, label=f"VaR 99% (-${var_mc_99:,.0f} MXN)")
    plt.title("Distribución de Pérdidas y Ganancias Simuladas (10 Días) y Cortes de VaR", fontweight='bold')
    plt.xlabel("Pérdida / Ganancia Simulada en Pesos (MXN)")
    plt.ylabel("Densidad")
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Gráfica 3: Curva Forward USD/MXN
    plazos_estandar = [1, 2, 7, 14, 28, 60, 91, 182, 364, 728]
    fwds = []
    for d in plazos_estandar:
        rmx = float(np.interp(d, dias_mx, tasas_mx))
        rus = float(np.interp(d, dias_us, tasas_us))
        f_teorico = spot_base * ((1.0 + rmx * (d / 360.0)) / (1.0 + rus * (d / 360.0)))
        fwds.append(f_teorico)
    
    plt.figure(figsize=(9, 4.0))
    plt.plot(plazos_estandar, fwds, marker='s', color='#2563eb', linewidth=2.0, label='Curva Forward Teórica (CIP)')
    plt.scatter([plazo], [precio_pactado], color='#ff7a1a', s=90, zorder=5, label=f"Operación Cotizada ({plazo}d: ${precio_pactado:.4f})")
    plt.title("Estructura Temporal de Tipo de Cambio Forward (Paridad CIP)", fontweight='bold')
    plt.xlabel("Plazo de Vencimiento (Días)")
    plt.ylabel("Forward MXN/USD")
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

    print("\nProceso finalizado con éxito.\n")
