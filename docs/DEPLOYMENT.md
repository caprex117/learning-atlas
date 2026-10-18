# Publicar Learning Atlas en Streamlit Community Cloud

El trabajo de código está preparado. Lo que falta de tu parte es **crear un proyecto Supabase, subir el código a tu GitHub y conectar ambos desde Streamlit**. Gemini es opcional. No necesitas compartir contraseñas, claves privadas ni tokens en el chat.

## 1. Crear Supabase

1. Entra a [Supabase](https://supabase.com/dashboard) con tu cuenta y crea un **proyecto nuevo** para Learning Atlas. Guarda su contraseña de base de datos en tu gestor de contraseñas; la app no la necesita.
2. Abre **SQL Editor** y crea una consulta nueva.
3. Copia **todo** el contenido de `supabase/migrations/001_learning_atlas.sql` y ejecútalo una vez. Crea 30 tablas de aplicación, una tabla de recibos, funciones transaccionales, políticas por usuario y el bucket privado `learning-documents`.
4. Ejecuta también supabase/migrations/002_discovery_catalog.sql una vez para el catálogo. Si ya usabas la app, ejecuta únicamente el 002 y sigue [DISCOVERY_SETUP.md](DISCOVERY_SETUP.md). Confirma que aparecen `profiles`, `learning_tracks`, `study_sessions` e `import_jobs` en el explorador de tablas. En Storage, `learning-documents` debe ser **privado**.
5. En **Authentication → Users**, crea tu usuario con correo y contraseña. Usa la opción para que el correo quede confirmado si la pantalla la ofrece. Si lo creas sin confirmar, completa la confirmación antes de entrar.
6. En la configuración de Authentication, deshabilita el registro de usuarios nuevos para este tracker personal. La app sólo ofrece inicio de sesión; el bloqueo del registro también debe quedar en Supabase.
7. En **Project Settings / API**, copia la **Project URL** y la clave **publishable** (`sb_publishable_…`), o la antigua clave pública **anon** si tu proyecto usa ese formato.

**Nunca uses la clave `service_role`, una `sb_secret_…`, tu contraseña de base de datos ni claves del proyecto Anime-App.** La app rechaza claves privilegiadas. El aislamiento de filas se aplica con el usuario autenticado, no con una clave que lo omita.

La migración es para un proyecto nuevo. Si aparece `already exists`, no borres tus tablas ni repitas fragmentos al azar: comprueba si ya se ejecutó. Al estar dentro de una transacción, un error revierte esa ejecución completa.

## 2. Subir el código a GitHub

Para trabajar desde `C:\Users\deef3\learning-atlas` y conectar el repositorio `caprex117/learning-atlas`, sigue [UPDATES.md](UPDATES.md). Esa guía usa GitHub Desktop y explica cómo publicar los cambios posteriores. Si ya creaste ese repositorio, no crees un duplicado.

La alternativa siguiente permite una primera subida manual desde la web:

La forma más directa es usar el ZIP de entrega, que ya excluye entornos, datos privados y secretos:

1. Descomprime **Learning-Atlas-Streamlit.zip** en una carpeta nueva.
2. En [GitHub](https://github.com/new), crea un repositorio, por ejemplo `learning-atlas`. Puede ser privado. Puedes dejar sin seleccionar la creación automática de README porque el proyecto ya incluye uno.
3. Abre **Add file → Upload files** y sube **el contenido** de la carpeta descomprimida, conservando sus subcarpetas. No subas sólo el ZIP: Streamlit necesita ver el código.
4. Confirma que en la raíz del repositorio están `streamlit_app.py`, `requirements.txt`, `atlas/`, `data/`, `supabase/`, `.streamlit/` y `.github/`. Incluye `.gitignore` y los documentos.
5. Guarda el primer commit en la rama que vas a desplegar, normalmente `main`.
6. Abre la pestaña **Actions** y espera el resultado de **Learning Atlas tests**. Si GitHub pide habilitar Actions para tu repositorio, puedes hacerlo allí. El workflow utiliza una base temporal; no se conecta a tu Supabase.

Si prefieres GitHub Desktop, añade como repositorio la carpeta **descomprimida aparte**. No añadas toda la carpeta anterior de Power BI: contiene otros proyectos y documentos. Revisa que no aparezcan `.venv`, `node_modules`, `private` o `secrets.toml` en los cambios a publicar.

## 3. Desplegar en Streamlit

1. Entra a [Streamlit Community Cloud](https://share.streamlit.io/) y conecta tu cuenta GitHub. Para un repositorio privado, concede acceso a ese repositorio cuando el servicio lo solicite.
2. Crea una app y selecciona tu repositorio y rama.
3. **Main file path:** `streamlit_app.py`.
4. En **Advanced settings**, selecciona **Python 3.12** y pega los secretos en formato TOML:

```toml
[supabase]
url = "https://TU_PROYECTO.supabase.co"
key = "TU_CLAVE_PUBLISHABLE_O_ANON"

[app]
allow_demo = false
```

5. Sustituye los dos valores. Mantén las comillas y los encabezados con corchetes. **Pégalos en Secrets de Streamlit, no en un archivo del repositorio.**
6. Pulsa **Deploy**. Cuando termine, abre la URL que te asigne y entra con el correo y contraseña de tu usuario Supabase.

Streamlit permite administrar estos secretos desde la configuración de la app. El archivo local `.streamlit/secrets.toml` no debe versionarse. [Guía oficial de secretos](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## 4. Primera entrada a tu espacio real

1. Abre **Mi espacio** y elige el nombre y la zona horaria. Para Puerto Rico puedes usar `America/Puerto_Rico`. Confirma **480 minutos semanales** y el umbral de racha que prefieras (inicialmente 10 minutos).
2. En **Habilidades**, pulsa **Cargar mapa inicial de habilidades**, o crea las tuyas.
3. En **Mi ruta**, pulsa **Crear mi ruta Factory Enablement**. Mantiene el 12 de octubre de 2026 al 3 de enero de 2027, 96 h presupuestadas y ningún progreso realizado. Si decides cambiar las fechas, guarda una versión nueva desde esa misma sección.
4. Añade el primer aprendizaje con sus unidades, o importa tu documento. Los ejemplos de la demo no se copian a tu cuenta.
5. En **Credenciales**, registra tus logros previos. Si sólo recuerdas el semestre, usa el campo de período y deja la fecha exacta vacía.

## 5. Prueba breve en la web

Haz primero este recorrido con datos de prueba claramente identificados:

- Crea un aprendizaje “Prueba de instalación” con dos unidades. Debe mostrar 0%.
- Completa una unidad: debe mostrar 50%, y **0 minutos** si no registraste una sesión.
- Registra una sesión de 20 minutos con dos habilidades: deben sumar 20 minutos entre ambas, no 40.
- Cierra sesión y vuelve a entrar: los registros deben seguir ahí. Marca el aprendizaje de prueba como archivado si ya no lo necesitas; anula su sesión con motivo para excluirla de tus métricas.
- Sube `examples/plan-mini.md`, prepara una propuesta manual, valida, revisa y aprueba. Debe quedar en tu biblioteca con progreso 0 y adjunto descargable.
- Reabre la importación: debe indicar “Importado” sin repetir datos.

La suite local prueba cálculos, transacciones y permisos SQL. **Esta prueba web completa lo que sólo puede verificarse con tus cuentas: Auth, API de Supabase, Storage y el despliegue real.**

## 6. Activar Gemini, si quieres

En [Google AI Studio](https://aistudio.google.com/), crea tu clave y confirma qué modelo de texto admite salida estructurada en tu cuenta. Añade a **Secrets de Streamlit**:

```toml
[gemini]
api_key = "TU_CLAVE_GEMINI"
model = "IDENTIFICADOR_DEL_MODELO_DISPONIBLE"
```

Usa el identificador sin el prefijo `models/`. No se fija un modelo de ejemplo que pueda estar retirado o fuera de tu cuota. Comprueba las condiciones y cuota de tu cuenta en AI Studio.

En **Importar documentos**, lee el archivo y marca la autorización para enviar **ese texto** a Google. El historial de aprendizaje, las credenciales de acceso y otros adjuntos no se incluyen. La propuesta se valida y se revisa antes de guardar; una respuesta de IA no escribe directamente en la base.

Primera prueba sugerida: usa el documento ficticio de `examples/`, comprueba el temario y las estimaciones y luego aprueba. Si el modelo o la cuota fallan, usa captura manual o JSON. Esta integración se probó con respuestas simuladas, **no con una clave real de tu cuenta**. [API oficial de generación](https://ai.google.dev/api/generate-content).

## Si algo falla

| Síntoma | Qué revisar |
|---|---|
| Sólo ves la demo / falta Supabase | Secrets contiene `[supabase]`, `url` y `key`; guarda y reinicia la app. |
| No puedes iniciar sesión | Correo, contraseña, confirmación de correo y usuario en Authentication. |
| Error al recuperar o guardar datos | Migración completa instalada; clave pública del mismo proyecto; sesión vigente. Sal y vuelve a entrar. |
| “Los datos cambiaron” | Otra pestaña guardó algo. Actualiza y vuelve a revisar antes de guardar. |
| PDF sin texto | Es probable que necesite OCR. Convierte fuera de la app a un documento con texto o usa captura manual. |
| No se pudo consultar el radar | La fuente puede estar temporalmente indisponible o limitada. Conserva la última consulta y reintenta después. |
| arXiv respondió sin publicaciones | Una ventana del feed puede estar vacía; no significa que el importador esté roto. |
| Subida interrumpida antes de crear borrador | Reintenta en esa misma sesión. Si cerraste el navegador, un archivo sin referencia puede quedar en Storage; revisa y elimina sólo ese archivo huérfano desde tu proyecto. |

No hace falta instalar Docker, Node ni las dependencias de pruebas en Streamlit Cloud. La app usa `requirements.txt`. Referencia: [publicación en Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
