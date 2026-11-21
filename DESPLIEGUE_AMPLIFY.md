# GUÍA DE DESPLIEGUE EN AWS AMPLIFY (ENLACE PÚBLICO EN VIVO)

Esta aplicación fue empaquetada como una **Single Page Application (SPA)** de arquitectura sin servidor (serverless), optimizada para **AWS Amplify Hosting**. 

Al montarla en AWS Amplify obtendrás un enlace público con certificado de seguridad SSL HTTPS (por ejemplo `https://main.d1x2y3z4.amplifyapp.com`) que puedes enviar directamente a tu profesor para que abra e interactúe con la plataforma desde cualquier computadora, tableta o celular sin instalar nada.

---

## MÉTODO 1: DESPLIEGUE INMEDIATO (ARRASTRAR Y SOLTAR - 60 SEGUNDOS)
*No requiere Git ni conocimientos de nube. Es el método más rápido.*

1. **Abre la consola de AWS Amplify**:
   - Ingresa a: [https://console.aws.amazon.com/amplify/](https://console.aws.amazon.com/amplify/)
   - Inicia sesión con tu cuenta de AWS (la capa gratuita incluye alojamiento de Amplify).

2. **Crear nueva aplicación**:
   - Da clic en el botón superior derecho: **"Create new app"** (o "Crear nueva app").
   - Selecciona la opción **"Deploy without Git provider"** (Desplegar sin proveedor de Git).
   - Da clic en **"Next"** (Siguiente).

3. **Subir el paquete**:
   - **App name**: Escribe `quantfx-terminal` (o el nombre que prefieras).
   - **Environment name**: Deja `production` o `main`.
   - **Method**: Selecciona **"Drag and drop"** (Arrastrar y soltar).
   - Arrastra o selecciona el archivo:
     `app_derivados_fx/amplify_deploy.zip`
   - Da clic en **"Save and deploy"** (Guardar y desplegar).

4. **¡Listo!**:
   - AWS Amplify subirá los archivos y en 30 segundos mostrará una palomita verde con tu URL pública oficial:
     `https://main.dXXXXXXXX.amplifyapp.com`
   - Haz clic en la liga para verificar que la terminal de trading cargue en vivo y compártela.

---

## MÉTODO 2: CONECTANDO CON GITHUB (CI/CD AUTOMÁTICO)
*Si prefieres que cada cambio en tu repositorio se actualice automáticamente.*

1. Sube tu carpeta del proyecto a un repositorio de GitHub (público o privado).
2. En la consola de AWS Amplify, selecciona **"Host web app"** -> **"GitHub"**.
3. Autoriza el acceso a tu cuenta de GitHub y selecciona el repositorio y la rama `main`.
4. AWS Amplify detectará automáticamente el archivo `amplify.yml` incluido en la carpeta `amplify_deploy/`.
5. Da clic en **"Save and deploy"**.
6. Amplify compilará y desplegará tu aplicación en un dominio HTTPS gratuito.

---

## CARACTERÍSTICAS INCLUIDAS EN LA APLICACIÓN DESPLEGADA
- **Diseño Visual de Trading Terminal**: Modo oscuro profesional de alto contraste con cotización en vivo y pestañas de divisas.
- **Conexión Multidivisa**: USD/MXN, EUR/MXN, GBP/MXN, EUR/USD, USD/JPY, GBP/USD.
- **Plazos Interbancarios**: Cash ($T+0$), Tom ($T+1$), Spot ($T+2$), Tom-Next ($T/N$), 1W, 2W, 1M, 2M, 3M, 6M, 1Y y 2Y (con alerta de límite regulatorio a 730 días).
- **Comparación Cuantitativa de 5 Instrumentos**:
  1. *FX Spot*: Contado inmediato.
  2. *FX Swap*: Pata spot + forward, puntos swap y tasa implícita en pesos.
  3. *FX Forward (OTC)*: Paridad de tasas cubierta (CIP) y Puntos F.
  4. *Futuro FX*: Estandarizado con margen de garantía inicial del 6%.
  5. *Opciones FX*: Modelo Garman-Kohlhagen (1983) para Call y Put, strike ATM, delta y prima.
- **Analítica de Riesgo y P&L**:
  - Matriz de escenarios de $-15\%$ a $+15\%$.
  - Gráfica interactiva de Payoff al vencimiento (Chart.js).
  - Medición integral de Value at Risk (VaR): Paramétrico 95/99% (1d y 10d), Histórico 95% y Monte Carlo (12,500 iteraciones).
