# Learning Atlas

Tracker personal de aprendizaje en **Streamlit + Supabase**, con el tema claro, verde y tipografía serif del prototipo. Organiza cursos, certificaciones, temas, papers, proyectos y práctica profesional.

**Para ponerlo en la web: empieza por [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).** El código está preparado; la creación de tus proyectos, cuenta y secretos se realiza desde tus cuentas. No hay una app publicada ni credenciales incluidas en este repositorio.

**Para publicar cambios posteriores:** consulta [docs/UPDATES.md](docs/UPDATES.md). La carpeta de trabajo prevista es `C:\Users\deef3\learning-atlas`; GitHub recibe los commits mediante `push` y Streamlit actualiza la rama conectada.

## Qué puedes hacer

- Crear aprendizajes, guardar favoritos, editar su información, temario, estimaciones y prioridades.
- Completar unidades y visualizar progreso, tiempo real, estimaciones pendientes, actividad por área y rachas.
- Cargar la ruta Factory Enablement de 8 h/semana, revisar sus siete entregables y guardar nuevas versiones del plan.
- Relacionar temas y habilidades con cursos; registrar práctica laboral, evidencias y autoevaluaciones comparables.
- Mantener un mapa de temas aprendidos y sugerencias de repaso con colores orientativos.
- Generar un plan del día de hasta tres bloques; registrar sólo el tiempo que realmente realizaste.
- Explorar un catálogo persistente de oportunidades oficiales y comunitarias: temarios, habilidades, precios, fuentes, favoritos e historial.
- Añadir oportunidades y Learning Packs a tu aprendizaje o a una fase de tu ruta.
- Investigar novedades bajo demanda o semanalmente con Tavily y Gemini, con fallback y conservación del catálogo ante fallos. Actívalo siguiendo [docs/DISCOVERY_SETUP.md](docs/DISCOVERY_SETUP.md).
- Importar PDF, DOCX, TXT, MD o JSON con lectura, propuesta, revisión y aprobación. Gemini es opcional; la captura manual funciona sin IA.
- Registrar credenciales sin confundirlas con completar un curso, y exportar tus registros en JSON.

La **demo es temporal y ficticia**. Una cuenta real empieza vacía. La ruta inicial y el mapa de habilidades se cargan con botones explícitos y no añaden actividad realizada.

## Ejecutar en tu computadora

Python **3.12**. Desde la carpeta que contiene `streamlit_app.py`, en PowerShell:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Abre la URL local que imprime Streamlit y elige **Explorar demo**. No requiere Supabase ni Gemini.

Para conectar tu cuenta, crea `.streamlit/secrets.toml` siguiendo el archivo de ejemplo y la guía. Este archivo está excluido de Git. Las versiones directas de las dependencias están fijadas a las probadas; no necesitas Node para usar o desplegar la app.

## Organización

```text
streamlit_app.py             Entrada de Streamlit
atlas/app.py                Pantallas y formularios
atlas/ui.py                 Tema y componentes visuales
atlas/models.py             Contratos de entrada validados
atlas/domain.py             Cálculos independientes de la interfaz
atlas/service.py            Acciones y lotes atómicos
atlas/repository.py         Supabase real / demo en memoria
atlas/auth.py               Inicio y cierre de sesión
atlas/importing.py          Extracción y propuestas con Gemini
atlas/extract_worker.py     Proceso limitado para leer documentos
atlas/catalog*.py           Catálogo, historial y adopción explícita
atlas/research.py            Tavily y fallback Gemini
atlas/seed.py, data/         Plantillas y selección editorial
supabase/migrations/         Instalación SQL inicial
tests/                      Pruebas de contratos, SQL e interfaz
docs/                       Guía, modelo y criterios de aceptación
```

## Pruebas

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest -q
```

Para incluir las pruebas SQL localmente sin un servidor PostgreSQL, instala **sólo la herramienta de desarrollo**:

```powershell
npm --prefix scripts/sql-harness ci --ignore-scripts
.venv/Scripts/python.exe -m pytest -q
```

Ese motor ejecuta PostgreSQL en WebAssembly (PGlite). Auth y las tablas de control de Storage se simulan; no reemplaza probar la conexión real de Supabase. La prueba de dos conexiones simultáneas necesita un servidor PostgreSQL y se omite en PGlite.

El workflow de GitHub Actions prepara PostgreSQL 17 desechable y ejecuta también esa prueba. No usa secretos de producción. Consulta [docs/VALIDATION.md](docs/VALIDATION.md) para el alcance y las verificaciones pendientes.

## Límites de esta versión

El plan del día usa reglas. Descubrir combina una selección inicial revisada con propuestas de IA basadas en fuentes; la revisión semanal requiere activar el workflow y sus secretos. No promete sincronización continua ni investigación exhaustiva. El asistente Gemini organiza documentos y siempre requiere revisión. No hay OCR integrado, verificación automática de credenciales, integración privada con Coursera ni medición científica de memoria. DuckDB y un calendario externo no son necesarios para este tamaño de aplicación.

Los adjuntos son privados; las sesiones de acceso se conservan en el servidor para esa conexión del navegador. Una recarga completa puede pedir iniciar sesión de nuevo. Las correcciones de tiempo se hacen anulando la sesión y registrando la correcta, conservando el historial. El JSON de exportación sirve como respaldo de registros, no como restauración automática ni como copia de los archivos binarios.

Consulta [el contrato implementado](docs/CONTRACT.md), [el modelo y seguridad](docs/DATA_MODEL.md) y [el flujo de documentos](docs/IMPORTING.md).
