# Verificación de la entrega · 17 de octubre de 2026

**85 pruebas aprobadas y 1 omitida justificadamente** en Python 3.12.14. Dependencias directas fijadas a las instaladas; `pip check` no encontró incompatibilidades.

## Ejecutado

| Capa | Qué se verificó |
|---|---|
| Contratos | Progreso de hojas obligatorias y pesos, desconocidos, minutos reales, reparto de habilidades, rachas y intervalos de repaso. |
| Servicio | Alta/edición de aprendizajes, unidades, sesiones, anulación, práctica laboral, credenciales, preferencias, autoevaluaciones y versiones de ruta. |
| Importación | Estructura, ciclos, referencias, fechas, datos inválidos, revisión vigente, destino existente, archivos privados, cancelación y reintentos sin duplicación. |
| Documentos | DOCX con párrafos/tablas, UTF-8 en proceso separado, PDF sin texto, formatos corruptos y límites. El plan Collins adjunto también se leyó: 58.924 caracteres y los temas esperados presentes. No se envió a una IA. |
| SQL | Migración completa ejecutada en PostgreSQL WebAssembly (PGlite), con el mismo servicio Python. Pruebas de rollback, permisos por usuario, referencias cruzadas rechazadas, archivos separados, revisiones e idempotencia. |
| Streamlit AppTest | Las 11 secciones; alta de aprendizaje y completado; sesión real; importación manual con aprobación; login/logout con cliente de Auth simulado. |
| Navegador | Vista de escritorio y móvil, menú lateral, formulario de alta, resultado con 0% y 0 minutos; sin errores de consola en la revisión. |
| Fuentes externas | Consultas HTTP reales al feed de versiones de pandas y Streamlit: 8 resultados cada uno. arXiv respondió correctamente con 0 publicaciones en su ventana de consulta. |
| Empaquetado | SQL coincide con el generador; ejemplo JSON válido; fuente filtrada para excluir secretos, archivos privados, dependencias y datos de ejecución. Búsqueda de patrones de credenciales conocidas. |

PGlite ejecuta PostgreSQL; **las capas Auth y Storage de Supabase se simulan en las pruebas SQL**. Las llamadas a Gemini se verifican con respuestas HTTP simuladas y validación del esquema. Estas pruebas no significan que una cuenta externa esté configurada o conectada.

## Prueba omitida localmente

`test_two_connections_cannot_overwrite_same_revision` requiere dos conexiones simultáneas a un servidor PostgreSQL. PGlite sólo proporciona una conexión. La prueba queda incluida en GitHub Actions con PostgreSQL 17; **el workflow aún debe ejecutarse al subir el repositorio**. No se declara aprobada antes de esa ejecución.

## Pendiente con tus cuentas

- Ejecutar la migración en tu nuevo proyecto Supabase y crear tu usuario.
- Verificar login real, persistencia después de cerrar sesión y subida/descarga privada mediante la API de Supabase.
- Ejecutar el workflow de GitHub y confirmar el despliegue en Streamlit Community Cloud.
- Si activas Gemini: comprobar un documento ficticio con tu modelo, clave y cuota reales antes de usar documentos propios.

Estos pasos están detallados en [DEPLOYMENT.md](DEPLOYMENT.md). No se publicaron servicios ni se usaron credenciales de otros proyectos.

## Reproducir

```powershell
python -m pip install -r requirements-dev.txt
npm --prefix scripts/sql-harness ci --ignore-scripts
python scripts/check_package.py
python -m pytest -q --tb=short
```

Para el recorrido con PostgreSQL servidor, configura `ATLAS_TEST_DATABASE_URL` apuntando a una base **desechable y vacía**, cuyo nombre termine en `_test`. El fixture crea roles y schemas de prueba; no uses tu Supabase real. GitHub Actions prepara ese entorno automáticamente.

Los resultados de cada versión futura deben volver a verificarse después de cambios funcionales. El contrato explica qué se espera; las pruebas demuestran casos concretos y no sustituyen la revisión del despliegue real.
