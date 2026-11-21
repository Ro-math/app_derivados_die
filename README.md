# Cotizador de Derivados FX y Gestión de Riesgo

Aplicación interactiva para la cotización de derivados de tipo de cambio, valuación por paridad cubierta de tasas (CIP) y medición de Value at Risk (VaR).

### Enlace en vivo (GitHub Pages)
https://ro-math.github.io/app_derivados_die/

---

### Funcionalidades
1. **Datos de mercado en vivo**: Conexión a Yahoo Finance con respaldo de datos calibrados.
2. **Multidivisa**: Cotización de USD/MXN, EUR/MXN, GBP/MXN, EUR/USD, USD/JPY y GBP/USD con tasas de bancos centrales.
3. **Plazos interbancarios**: Cash (T+0), Tom (T+1), Spot (T+2), Tom-Next, 1W, 2W, 1M, 3M y días personalizados hasta 730 días (2 años máximo).
4. **Comparativa de 5 derivados**:
   - FX Spot (contado directo)
   - FX Swap (pata spot + forward con tasa implícita CIP)
   - FX Forward OTC (puntos forward F)
   - Futuro FX (MexDer con margen del 6%)
   - Opciones FX (modelo Garman-Kohlhagen con call/put, strike ATM y delta)
5. **Analítica de riesgo**:
   - Matriz de escenarios de pérdidas y ganancias (-15% a +15%)
   - Curva de payoff interactiva
   - Value at Risk (VaR): Paramétrico 95/99% a 10d, Histórico a 1d y Monte Carlo con 12,500 simulaciones.

---

### Ejecución local

En macOS / Linux:
```bash
./run.sh web
```

En Windows:
```cmd
run.bat web
```
Abre automáticamente el navegador en `http://localhost:8000`.

---

### Estructura del proyecto
- `index.html`: Aplicación web interactiva (se despliega en GitHub Pages).
- `app_derivados_fx.py`: Servidor web local y endpoints de mercado y riesgo.
- `mercado_live.py`: Conexión a Yahoo Finance y curvas de tasas.
- `motor_derivados.py`: Valuación cuantitativa (Spot, Swap, Forward, Futuro, Opciones y VaR).
- `historico_usdmxn.csv`: Serie de precios de referencia.
- `run.py`, `run.sh`, `run.bat`: Lanzadores automáticos para Mac y Windows.
- `requirements.txt`: Librerías requeridas.
