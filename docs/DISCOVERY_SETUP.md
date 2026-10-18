# Activar el nuevo Descubrir

El código incorpora un catálogo persistente con 54 oportunidades iniciales, filtros, favoritos, precios, temas, habilidades, historial y siete Learning Packs y tres proyectos de apps y un proyecto de pruebas con Playwright. Incluye Factory Enablement y creación de apps con IA, prioridad personal y exportación CSV completa. Añadir una oportunidad a tu aprendizaje o a una fase de tu ruta siempre requiere tu elección. Tu cuenta y tus datos siguen siendo privados. La selección y sus fuentes están en [RESEARCH_54.md](RESEARCH_54.md).

## 1. Instalar las tablas nuevas

En tu proyecto de Supabase → **SQL Editor → New query**, pega **todo** el archivo `supabase/migrations/002_discovery_catalog.sql` y pulsa **Run** una vez.

La migración añade siete tablas y amplía las funciones existentes. Conserva tus aprendizajes, sesiones y credenciales. Requiere que `001_learning_atlas.sql` ya esté instalado; no vuelvas a ejecutar el 001. Si aparece `already exists`, comprueba si el 002 ya se instaló antes de reintentarlo. La operación es transaccional.

## 2. Publicar el código

En GitHub Desktop, selecciona **learning-atlas**, cuya carpeta es `C:\Users\deef3\learning-atlas`.

1. Revisa los cambios, escribe **Añadir catálogo de oportunidades y revisión semanal**, y pulsa **Commit to main**.
2. Pulsa **Push origin**. Espera el resultado verde de **Learning Atlas tests** en GitHub → Actions.
3. Streamlit actualizará la app conectada a esa rama. Si tienes una sesión abierta, ciérrala y vuelve a entrar.

## 3. Claves para Actualizar ahora

Crea una cuenta en [Tavily](https://app.tavily.com/) y copia una API key. Puedes empezar con el plan gratuito. Usa tu clave existente de Gemini de Google AI Studio.

En **Streamlit Community Cloud → tu app → Settings → Secrets**, conserva `[supabase]` y `[app]`. Añade `[tavily]` y revisa tu sección `[gemini]`; no dupliques encabezados:

```toml
[gemini]
api_key = "TU_CLAVE_GEMINI"
model = "gemini-3.5-flash-lite"

[tavily]
api_key = "TU_CLAVE_TAVILY"
```

`gemini.model` continúa controlando la organización de documentos. La investigación utiliza su propia secuencia: **gemini-3.8-flash → gemini-3.5-flash-lite**. Se hace un reintento breve ante saturación o fallo de red y luego se cambia de modelo. No se usa el alias `gemini-3.5-flash`, que redirige a 3.6 Flash según la [tabla oficial de modelos retirados](https://ai.google.dev/gemini-api/docs/deprecations).

No publiques claves en archivos ni las pegues en el chat. Si ambos modelos fallan, se conserva el catálogo anterior y aparece el intento fallido.

## 4. Primer uso

1. Publica este código y entra a **Descubrir → Cargar / actualizar selección de 54**. No consume APIs ni crea progreso. Puedes usarlo sin configurar las claves. Si ya tenías las 40 fichas anteriores, se añaden exactamente 14 y se actualiza el orden personal. Si partías de 17, se conserva su identidad y se enriquece la información manual anterior. Tus decisiones y progreso se conservan. Las revisiones más recientes o de IA no se sustituyen.
2. En **Mi enfoque y actualización semanal**, revisa dirección profesional y etiquetas. Autoriza enviar ese enfoque a Tavily y Gemini y guarda.
3. Pulsa **Actualizar ahora**. Comprueba la fecha, el modelo y el historial del resultado.
4. Abre una ficha: revisa precio, temario y fuentes. Puedes guardarla como favorita o descartarla.
5. Para estudiarla, abre **Añadir a mi aprendizaje o a mi ruta**. Elige una fase si quieres vincularla a una ruta activa, decide si usar el temario como unidades, confirma la revisión y añade.

El aprendizaje empieza planificado, sin horas ni unidades completadas. Los packs crean una unidad por componente y conservan los enlaces. Añadir de nuevo la misma ficha reutiliza ese aprendizaje. Las actualizaciones futuras del catálogo no cambian su temario ni tu avance; así puedes ajustar tu plan conscientemente.

**Alternativa para cargar ahora desde Supabase:** abre `supabase/seeds/learning_catalog_54.sql`, copia todo su contenido en **SQL Editor → New query → Run**. Es una carga de datos, no otra migración; no repitas 001 ni 002 si ya están instaladas. Si hay exactamente un perfil de Learning Atlas, lo selecciona automáticamente. Si hay varios, exige indicar tu UUID en `target_user`; no crea usuarios. Si aún no hay perfil, inicia sesión en la app primero. Una ejecución con error se revierte completa. La carga y el botón son compatibles: usar ambos no duplica los datos.

**CSV:** el archivo `exports/learning_catalog_54.csv` contiene la selección investigada. El botón **Descargar catálogo completo · CSV** descarga todas las fichas actuales de tu cuenta, con fuentes, componentes e historial, sin limitarse a la página o los filtros. Las listas se conservan como JSON dentro de las celdas. Úsalo para análisis; no lo importes directamente en una tabla porque el catálogo tiene varias relaciones.

**Tu interés en apps con IA:** la selección inicial ya lo incluye. Si guardaste un enfoque antes, añade `apps con IA, Streamlit, Supabase, pruebas` a sus etiquetas para orientar también las revisiones futuras. La carga conserva tus ajustes y consentimientos actuales.

## 5. Revisión semanal automática (opcional)

La ejecuta GitHub Actions, incluso si nadie abre Streamlit. Usa **tu mismo usuario de la app**, no crea otro usuario ni emplea una clave administrativa.

En [los ajustes del repositorio](https://github.com/caprex117/learning-atlas/settings/secrets/actions) → **Secrets and variables → Actions → Secrets → New repository secret**, guarda estos seis secretos:

| Nombre exacto | Valor |
|---|---|
| `SUPABASE_URL` | La misma URL de `[supabase].url` en Streamlit. |
| `SUPABASE_KEY` | La misma clave pública publishable o anon de `[supabase].key`. |
| `ATLAS_EMAIL` | El correo con el que entras a Learning Atlas. |
| `ATLAS_PASSWORD` | La contraseña de ese usuario de la app, no la del sitio Supabase ni la de PostgreSQL. |
| `TAVILY_API_KEY` | Tu clave de Tavily. |
| `GEMINI_API_KEY` | Tu clave de Gemini. |

Después:

1. En la pestaña **Variables**, crea `ATLAS_RESEARCH_ENABLED` con valor `true`.
2. En la app → Descubrir → Mi enfoque, marca **Permitir revisión semanal desde GitHub Actions** y guarda. Mantén también la autorización de envío del enfoque.
3. En GitHub → **Actions → Learning Atlas weekly research → Run workflow**, ejecuta una primera comprobación. Si actualizaste el catálogo durante los seis días anteriores, se omitirá la búsqueda para evitar repetir el gasto: es un resultado esperado.
4. Queda programado los domingos a las **12:17 UTC** (08:17 en Puerto Rico y Bolivia). Los intentos que logran iniciar sesión quedan en el historial de Descubrir; los fallos de acceso se consultan en Actions.

Para detenerlo, cambia la variable a `false` o desmarca la opción en la app. Si cambias la contraseña del usuario, actualiza el secreto de GitHub. GitHub ejecuta los horarios desde la rama predeterminada, puede retrasarlos y desactiva los horarios de repositorios públicos tras 60 días sin actividad. [Documentación del horario](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Coste y alcance

**Empieza con coste mensual de APIs de USD 0**, dentro de las cuotas gratuitas disponibles en tus cuentas; no requiere una suscripción mensual nueva. No actives facturación para probar el catálogo inicial.

Tavily ofrece 1.000 créditos al mes en el nivel gratuito. Esta implementación hace cuatro búsquedas avanzadas y extrae hasta doce páginas: aproximadamente **11 créditos por actualización**, unos 55 con cinco revisiones semanales, más las manuales. El historial guarda el uso devuelto por la API; el panel de Tavily es la referencia para facturación y solicitudes fallidas. [Créditos y precios](https://docs.tavily.com/documentation/api-credits).

Gemini ofrece nivel gratuito para los modelos seleccionados, sujeto a cuotas y disponibilidad por proyecto. Con facturación activada se cobra por uso, no una mensualidad fija: hasta el 31 de diciembre de 2026, 3.8 Flash figura a USD 0,75/3,75 por millón de tokens de entrada/salida; Flash-Lite a USD 0,30/2,50. Después, el precio anunciado para 3.8 cambia. Los reintentos con respuesta pueden consumir tokens. Consulta [precios](https://ai.google.dev/gemini-api/docs/pricing) y [límites](https://ai.google.dev/gemini-api/docs/rate-limits) antes de activar pago. No hay un tope mensual monetario implementado en la app.

Cada revisión consulta una muestra acotada, combina búsqueda reciente y recursos de fundamentos, y revisita hasta seis enlaces antiguos. El catálogo puede crecer sin límite de tres fichas; una ejecución publica como máximo doce propuestas. No es un rastreo exhaustivo ni una sincronización en tiempo real de toda la web.

Las propuestas de IA deben citar páginas leídas y superar validaciones de esquema, enlaces, citas y precio. Esto reduce invenciones, pero no garantiza que cada interpretación sea correcta. Un temario marcado como resumen puede estar incompleto; una fecha de consulta reciente no significa que el contenido haya sido actualizado recientemente. Los packs son propuestas de Learning Atlas, sin acreditación oficial. Las 54 fichas iniciales se revisaron el **18 de octubre de 2026**.

Se envían el enfoque, etiquetas y páginas públicas; no se envían documentos privados, sesiones, contraseñas de la app ni claves de Supabase a los proveedores de investigación. El workflow inicia sesión bajo tus permisos y termina su propia sesión.
