# Un documento, una propuesta, una decisión

El flujo está hecho para que puedas usarlo sin asistencia externa:

1. **Subir y leer.** PDF, DOCX, TXT, MD o JSON; máximo 10 MB. Se extrae texto en un proceso separado con tiempo limitado. PDF: hasta 150 páginas. Texto: hasta 120.000 caracteres. No se recorta silenciosamente un documento demasiado largo.
2. **Organizar.** Usa el formulario manual para título, área, lecciones, temas y plataforma, o pide una propuesta a Gemini si lo configuraste y autorizaste el envío. Para documentos complejos, el editor JSON admite módulos, habilidades, fases y evidencias.
3. **Validar.** La app comprueba tipos, nombres, referencias, jerarquía sin ciclos, fechas de fases y límites. Guarda un borrador recuperable y el archivo privado en Supabase.
4. **Revisar.** Ves el temario, las fechas y las estimaciones; se señalan coincidencias con tu biblioteca. Puedes crear un aprendizaje nuevo o incorporar material a uno existente cuando la propuesta contiene un solo aprendizaje.
5. **Aprobar y guardar.** Se incorporan los registros en una transacción. Si una relación falla, se revierte todo el lote de datos. La marca de importado se guarda junto con los registros. Reabrir o reintentar esa importación no los duplica.

## Qué va a cada parte

| Contenido | Destino |
|---|---|
| Curso / certificación / tema | `learning_tracks` |
| Documento y enlace de referencia | `resources`, `track_resources`, `attachments` |
| Módulos y lecciones | `units`; sólo hojas en `track_units` |
| Temas del material | `topics`, `track_topics`, `resource_topics` |
| Habilidades que cubre | `skills`, `track_skills`, `topic_skills` |
| Ruta por fechas y entregables | `learning_goals`, `goal_phases`, `milestones` |
| Entregable explícitamente realizado | `learning_evidence`, `evidence_skills`, sin validación externa |
| Revisión, origen y estado | `import_jobs`, hash de propuesta, versión de extractor / modelo |

**Un temario no crea sesiones, unidades completadas, temas aprendidos ni certificaciones obtenidas.** Estos hechos requieren registro explícito en sus secciones. Los datos ambiguos quedan sin precisar o en advertencias. Revisa particularmente las fechas, horas, jerarquías y la diferencia entre intención y trabajo realizado.

La propuesta de Gemini es contenido no confiable. No recibe herramientas ni credenciales de la base y no puede ejecutar instrucciones incrustadas en tu documento. Pydantic valida su salida, pero no puede confirmar que su interpretación sea correcta: por eso la revisión humana permanece en el flujo.

## Documentos difíciles

Los PDF escaneados necesitan OCR fuera de esta versión. En PDF con columnas o tablas, comprueba el orden de lectura. En DOCX se leen párrafos y tablas del cuerpo; imágenes, notas y encabezados requieren revisión por separado. Si hay páginas vacías, se muestra una advertencia.

La subida del archivo a Storage y la transacción de registros son operaciones distintas. Un fallo antes de guardar el borrador puede dejar un archivo huérfano; reintentar en la misma sesión reutiliza la subida. Cancelar un borrador intenta limpiar su archivo; hay un botón de reintento si Storage falla. Un archivo vinculado a datos importados queda protegido contra borrado desde la política de Storage.

## Ejemplos

- `examples/plan-mini.md`: texto de práctica sin datos personales.
- `examples/import-mini.json`: propuesta correspondiente, con un módulo, dos lecciones, un tema y una habilidad.
- `examples/import.schema.json`: contrato completo, también descargable desde la app.

Los nombres de áreas, temas y habilidades se reutilizan de forma normalizada. Una nueva importación de un archivo idéntico exige una decisión explícita en la interfaz. El nombre por sí solo no fusiona cursos: tú decides el destino. Añadir material a un aprendizaje existente conserva sus unidades anteriores y su progreso; las nuevas unidades empiezan pendientes.
