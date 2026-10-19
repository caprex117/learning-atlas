# Activar el nuevo Learning Radar

El código incorpora un catálogo persistente con 54 oportunidades iniciales, filtros, favoritos, precios, temas, habilidades, historial y siete Learning Packs y tres proyectos de apps y un proyecto de pruebas con Playwright. Incluye Factory Enablement y creación de apps con IA, prioridad personal y exportación CSV completa. Añadir una oportunidad a tu aprendizaje o a una fase de tu ruta siempre requiere tu elección. Tu cuenta y tus datos siguen siendo privados. La selección y sus fuentes están en [RESEARCH_54.md](RESEARCH_54.md).

## 1. Instalar las tablas nuevas

En tu proyecto de Supabase → **SQL Editor → New query**, pega **todo** el archivo `supabase/migrations/002_discovery_catalog.sql` y pulsa **Run** una vez.

La migración añade siete tablas y amplía las funciones existentes. Conserva tus aprendizajes, sesiones y credenciales. Requiere que `001_learning_atlas.sql` ya esté instalado; no vuelvas a ejecutar el 001. Si aparece `already exists`, comprueba si el 002 ya se instaló antes de reintentarlo. La operación es transaccional.

## 2. Publicar el código

En GitHub Desktop, selecciona **learning-atlas**, cuya carpeta es `C:\Users\deef3\learning-atlas`.

1. Revisa los cambios, escribe **Simplificar navegación y mejorar asistentes y revisiones**, y pulsa **Commit to main**.
2. Pulsa **Push origin**. Espera el resultado verde de **Learning Atlas tests** en GitHub → Actions.
3. Streamlit actualizará la app conectada a esa rama. Si tienes una sesión abierta, ciérrala y vuelve a entrar.

## 3. Claves para Buscar novedades

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

1. Publica este código y entra a **Learning Radar → Cargar selección inicial**. No consume APIs ni crea progreso. Puedes usarlo sin configurar las claves. Si ya tenías las 40 fichas anteriores, se añaden exactamente 14 y se actualiza el orden personal. Si partías de 17, se conserva su identidad y se enriquece la información manual anterior. Tus decisiones y progreso se conservan. Las revisiones más recientes o de IA no se sustituyen.
2. En **Mi enfoque y opciones de actualización**, revisa dirección profesional y etiquetas. Autoriza enviar ese enfoque a Tavily y Gemini y guarda.
3. Pulsa **Buscar novedades**. Comprueba la fecha, el modelo y el historial del resultado.
4. Abre una ficha: revisa precio, temario y fuentes. Puedes guardarla como favorita o descartarla.
5. Para estudiarla, abre **Añadir a mi aprendizaje o a mi ruta**. Elige una fase si quieres vincularla a una ruta activa, decide si usar el temario como unidades, confirma la revisión y añade.

El aprendizaje empieza planificado, sin horas ni unidades completadas. Los packs crean una unidad por componente y conservan los enlaces. Añadir de nuevo la misma ficha reutiliza ese aprendizaje. Las actualizaciones futuras del catálogo no cambian su temario ni tu avance; así puedes ajustar tu plan conscientemente.

**Alternativa para cargar ahora desde Supabase:** abre `supabase/seeds/learning_catalog_54.sql`, copia todo su contenido en **SQL Editor → New query → Run**. Es una carga de datos, no otra migración; no repitas 001 ni 002 si ya están instaladas. Si hay exactamente un perfil de Learning Atlas, lo selecciona automáticamente. Si hay varios, exige indicar tu UUID en `target_user`; no crea usuarios. Si aún no hay perfil, inicia sesión en la app primero. Una ejecución con error se revierte completa. La carga y el botón son compatibles: usar ambos no duplica los datos.

**CSV:** el archivo `exports/learning_catalog_54.csv` contiene la selección investigada. El botón **Descargar catálogo completo · CSV** descarga todas las fichas actuales de tu cuenta, con fuentes, componentes e historial, sin limitarse a la página o los filtros. Las listas se conservan como JSON dentro de las celdas. Úsalo para análisis; no lo importes directamente en una tabla porque el catálogo tiene varias relaciones.

**Tu interés en apps con IA:** la selección inicial ya lo incluye. Si guardaste un enfoque antes, añade `apps con IA, Streamlit, Supabase, pruebas` a sus etiquetas para orientar también las revisiones futuras. La carga conserva tus ajustes y consentimientos actuales.

## 5. Revisión automática cada 21 días (opcional)

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
2. En la app → Learning Radar → Mi enfoque, marca **Permitir revisión automática cada 21 días** y guarda. Mantén también la autorización de envío del enfoque.
3. En GitHub → **Actions → Learning Atlas scheduled research → Run workflow**, ejecuta una primera comprobación. Si cargaste o revisaste el catálogo durante los 21 días anteriores, se omitirá la búsqueda para evitar repetir el gasto: es un resultado esperado.
4. El workflow comprueba diariamente a las **12:17 UTC** (08:17 en Puerto Rico y Bolivia) si han pasado 21 días. Sólo cuando corresponde consume APIs. Una consulta de nombres no aplaza la revisión; una revisión manual del catálogo completada sí la aplaza. Los fallos automáticos se reintentan como máximo una vez al día y comparten el presupuesto. Los intentos que logran iniciar sesión quedan en el historial de Learning Radar; los fallos de acceso se consultan en Actions.

Para detenerlo, cambia la variable a `false` o desmarca la opción en la app. Si cambias la contraseña del usuario, actualiza el secreto de GitHub. GitHub ejecuta los horarios desde la rama predeterminada, puede retrasarlos y desactiva los horarios de repositorios públicos tras 60 días sin actividad. [Documentación del horario](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Coste y alcance

**Empieza con coste mensual de APIs de USD 0**, dentro de las cuotas gratuitas disponibles en tus cuentas; no requiere una suscripción mensual nueva. No actives facturación para probar el catálogo inicial.

Tavily ofrece 1.000 créditos al mes en el nivel gratuito. Esta implementación hace dos búsquedas básicas y dos avanzadas (hasta 20 resultados breves) y extrae hasta diez páginas: **máximo previsto de 8 créditos por revisión** con la tarifa vigente. Una comprobación de nombre usa hasta 2. La app limita a **40 créditos por mes UTC** la suma de sus revisiones y comprobaciones; reserva el máximo antes de llamar y conserva esa reserva si el intento falla o se interrumpe. No mide el saldo global ni limita otras apps que compartan la clave. El panel de Tavily es la referencia de facturación. [Créditos y precios](https://docs.tavily.com/documentation/api-credits).

Gemini organiza únicamente fuentes seleccionadas y un índice breve de hasta 30 fichas relacionadas (nombre, proveedor, enlace y tres temas); Python compara los duplicados con **todo** el catálogo. La revisión limita la entrada serializada a 60.000 caracteres y la salida a 6.000 tokens por intento, hasta cuatro intentos. Los tokens conocidos se suman, incluido un intento con respuesta inválida. La conversación de Import/Credentials usa el modelo de `gemini.model`, con un intento de fallback a Flash-Lite y hasta 6.000 tokens de salida por intento. No hay presupuesto monetario mensual para Gemini; conversar requiere una acción explícita en cada envío. Consulta [precios](https://ai.google.dev/gemini-api/docs/pricing) y las cuotas de tu proyecto antes de activar facturación.

Cada revisión consulta una muestra acotada, combina búsqueda reciente y recursos de fundamentos, y revisita hasta seis enlaces antiguos. El catálogo puede crecer sin límite de tres fichas; una ejecución publica como máximo doce propuestas. No es un rastreo exhaustivo ni una sincronización en tiempo real de toda la web.

Las propuestas de IA deben citar páginas leídas y superar validaciones de esquema, enlaces, citas y precio. Esto reduce invenciones, pero no garantiza que cada interpretación sea correcta. Un temario marcado como resumen puede estar incompleto; una fecha de consulta reciente no significa que el contenido haya sido actualizado recientemente. Los packs son propuestas de Learning Atlas, sin acreditación oficial. Las 54 fichas iniciales se revisaron el **18 de octubre de 2026**.

Se envían el enfoque, etiquetas y páginas públicas; no se envían documentos privados, sesiones, contraseñas de la app ni claves de Supabase a los proveedores de investigación. El workflow inicia sesión bajo tus permisos y termina su propia sesión.


## Navegación y límites de incorporación

- El catálogo puede crecer más allá de 54: ésa es únicamente la selección inicial. Su botón desaparece cuando las 54 fichas ya existen. No consume APIs.
- Buscar novedades abre un diálogo de confirmación. Cada revisión incorpora de **0 a 5 nuevas** y comprueba **hasta 3 existentes**. No se obliga a llenar cupos. Conserva datos detallados previos cuando la nueva lectura es parcial, histórico, favoritos, decisiones y progreso.
- El enfoque y consentimiento se editan aquí o en Profile & Preferences. Si faltan requisitos, la interfaz identifica cuál: Tavily, Gemini, cuenta real, consentimiento o presupuesto.
- La fecha prevista y un calendario se muestran encima del catálogo. No garantizan ejecución si el workflow está desactivado o GitHub lo retrasa.
- Las búsquedas manuales de nombres en Import/Credentials requieren confirmación y forman parte del mismo presupuesto. No se envían IDs personales ni documentos a Tavily: el campo de consulta pide sólo nombre público y emisor.
