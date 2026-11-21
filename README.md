# QUANTFX TERMINAL | Plataforma de Derivados y Gestión de Riesgos FX

Plataforma visual de trading y valuación cuantitativa de derivados de tipo de cambio, paridad cubierta de tasas (CIP) y medición integral de Value at Risk (VaR).

Diseñada atendiendo los requerimientos y retroalimentación académica del profesor García Huerta Pablo Ronaldo:
1. **Interfaz Gráfica Visual de Trading**: Plataforma interactiva en modo oscuro inspirada en terminales institucionales de divisas con botones de Compra/Venta, cotizaciones en tiempo real y selector de instrumentos.
2. **Conexión a Datos de Mercado en Vivo**: Conexión a Yahoo Finance (`yfinance`) para tipos de cambio spot y series históricas, con modelo estocástico de respaldo en caso de desconexión.
3. **Soporte Multidivisa**: Cotización de USD/MXN, EUR/MXN, GBP/MXN, EUR/USD, USD/JPY y GBP/USD con curvas de tasas de bancos centrales (Banxico, Fed, BCE, BoE, BoJ).
4. **Plazos Interbancarios Completos**: Cash ($T+0$), Tom ($T+1$), Spot ($T+2$), Tom-Next ($T/N$), Spot-Next ($S/N$), 1W, 2W, 1M, 2M, 3M, 6M, 1Y y 2Y (con límite normativo estricto a 730 días).
5. **Catálogo Cuantitativo de 5 Estrategias**:
   - **FX Spot**: Contado inmediato.
   - **FX Swap**: Pata spot + forward, puntos swap y tasa implícita en pesos.
   - **FX Forward (OTC)**: Paridad de tasas CIP y puntos F.
   - **Futuro FX**: Estandarizado tipo MexDer/CME con margen inicial del 6%.
   - **Opciones FX**: Modelo Garman-Kohlhagen (1983) para Call y Put, strike ATM, delta y cálculo de prima.
6. **Analítica de Riesgo y P&L**: Matriz de escenarios de $-15\%$ a $+15\%$, gráfica de Payoff y VaR (Paramétrico 95/99% a 1d y 10d, Histórico 1d y Monte Carlo con 12,500 simulaciones).
7. **Despliegue en AWS Amplify**: Empaquetado listo para publicar en la nube y obtener un enlace público HTTPS para compartir con el profesor.

---

## 1. Despliegue en AWS Amplify (Enlace Web Público en la Nube)

Para que el profesor pueda acceder desde cualquier dispositivo sin instalar nada:
1. Abre la consola de AWS: [https://console.aws.amazon.com/amplify/](https://console.aws.amazon.com/amplify/)
2. Haz clic en **"Create new app"** -> **"Deploy without Git provider"**.
3. Escribe el nombre `quantfx-terminal` y arrastra el archivo:
   `app_derivados_fx/amplify_deploy.zip`
4. Clic en **"Save and deploy"**.
5. En 30 segundos obtendrás tu URL pública oficial (ejemplo: `https://main.d1x2y3z4.amplifyapp.com`).

*(Consulta la guía detallada paso a paso en [DESPLIEGUE_AMPLIFY.md](file:///Users/ro-yass/Projects%20Code/e/app_derivados_fx/DESPLIEGUE_AMPLIFY.md))*

---

## 2. Ejecución Local en tu Computadora (Un Solo Comando)

### En macOS / Linux
```bash
./run.sh web
./run.sh consola
./run.sh comand
```
*(O también: `python3 run.py web` | `python3 run.py consola` | `python3 run.py comand`)*

### En Windows (PowerShell o CMD)
```cmd
run.bat web
run.bat consola
run.bat comand
```
*(O también: `python run.py web` | `python run.py consola` | `python run.py comand`)*

---

## 3. Modos de Ejecución

* **`web`**:
  Levanta el servidor local, abre el navegador automáticamente en `http://localhost:8000` y muestra la terminal interactiva de trading con gráficos en vivo de Chart.js y cotización de los 5 derivados.
* **`consola`**:
  Ejecuta el cotizador interactivo guiado por texto en la terminal.
* **`comand`**:
  Ejecuta el cálculo benchmark automatizado de compra de $100,000 USD a 30 días con matriz de P&L, cálculo de VaR y guardado de reportes gráficos.

---

## 4. Estructura de Archivos

* `amplify_deploy/`: Paquete autónomo para AWS Amplify con `index.html` y `amplify.yml`.
* `amplify_deploy.zip`: Archivo comprimido listo para arrastrar y soltar en AWS Amplify Console.
* `DESPLIEGUE_AMPLIFY.md`: Instrucciones paso a paso para publicar en AWS Amplify.
* `mercado_live.py`: Motor de datos en vivo con conexión a Yahoo Finance y curvas interbancarias.
* `motor_derivados.py`: Valuación cuantitativa (Spot, Swap, Forward, Futuro, Opciones Garman-Kohlhagen, P&L y VaR).
* `app_derivados_fx.py`: Aplicación unificada con servidor web local y endpoints JSON.
* `run.py`, `run.sh`, `run.bat`: Lanzadores multiplataforma con auto-configuración de dependencias.
* `requirements.txt`: Librerías requeridas (`numpy`, `pandas`, `matplotlib`, `scipy`, `yfinance`).
