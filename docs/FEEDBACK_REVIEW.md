# Revisión del feedback antes de publicar · 19 de octubre de 2026

Se compararon las solicitudes de la conversación con el código y los contratos. No se añadieron avances ficticios ni se conectó Drive, y no se publicó esta revisión.

| Petición / confusión | Resolución |
|---|---|
| Menú con iconos, mayor letra, nombres e introducciones | Ya presentes. Dashboard contiene Overview, My Learning y Abilities. |
| Roadmap tiene tareas pero My Learning está vacío | Se explica que la plantilla crea fases y entregables, no cursos. Ahora cada fase permite crear un aprendizaje y vincularlo en una sola operación. |
| ¿Tengo que completar lo mismo en dos sitios? | Roadmap muestra las lecciones vinculadas y permite marcarlas sobre el mismo registro de My Learning. El entregable sigue siendo una confirmación separada del resultado final. |
| Buscar un aprendizaje en un desplegable | Añadido selector con búsqueda nativa, conservando filtros. Una búsqueda sin resultados se distingue de una biblioteca sin registros. |
| ¿Qué significa Sin asociar? ¿Puedo añadir áreas? | El formulario explica la práctica independiente. Permite escribir un área nueva incluso sin tener cursos. No se requiere crear un aprendizaje ficticio para registrar trabajo. |
| Fases finalizadas y demasiadas opciones | El selector muestra fases activas pendientes y finalizadas hoy o ayer. Una casilla permite ver finalizadas anteriores y versiones archivadas. Al editar se conserva la fase original disponible. |
| Editar una sesión sin reescribirla | Formulario precargado. La sustitución es atómica: conserva el original anulado, mueve las referencias de evidencias y Focus Plan al registro vigente, y recalcula minutos sin duplicarlos. Las evidencias mantienen sus IDs, contenido, adjuntos y vínculos con entregables. |
| Editar habilidades | Botón junto a cada habilidad; nombre, descripción y área conservando relaciones. La autonomía sigue siendo una autoevaluación separada y opcional. |
| ¿Una sesión se pierde si no completo la lección? | No. Se explica que planes, progreso y sesiones son hechos distintos. Una sesión válida cuenta aunque una lección quede pendiente. |
| Guardar notas, materiales y Drive | Las notas de la ficha admiten resúmenes y enlaces. Se aclara que no hay lectura automática de carpetas; conexión privada a Drive diferida por acuerdo. |
| Radar: 54 no es un máximo; precio, temas, habilidades, adopción y CSV | Ya presentes. Confirmación antes de revisar, intervalo de 21 días, presupuesto y límites por ejecución; no se reemplaza todo el catálogo. Se corrigieron menciones antiguas a revisión semanal en la documentación principal. |
| Import y Credentials con asistencia | Ya presentes: propuestas revisables antes de guardar, TXT recuperable y tabla/CSV de credenciales. Código del programa, ID personal y enlaces tienen campos distintos. |
| Ejemplo completo sin confusión | WALKTHROUGH.md sigue un proyecto de Python de principio a fin. Disponible también dentro de Dashboard y como descarga. No requiere recorrer todas las secciones a diario. |

No se fusionaron las tablas de cursos, fases y sesiones: eso haría que una tarea terminada inventase horas o que aceptar un entregable completase cursos que podrían seguir pendientes. La interfaz ofrece accesos al mismo registro para reducir pasos.

Esta entrega usa las tablas y RPC existentes; no requiere otra migración SQL. La migración 003 de Credentials ya fue confirmada por el usuario. La publicación y la prueba con su cuenta quedan para después del commit y push.
