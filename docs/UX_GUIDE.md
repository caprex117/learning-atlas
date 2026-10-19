# Learning Atlas · guía del flujo

La app separa **lo que planeas**, **lo que haces** y **lo que ya obtuviste**. Así un documento o un curso guardado no se convierte en aprendizaje realizado por error.

| Sección | Qué hace y qué información usa |
|---|---|
| **Dashboard → Overview** | Resume progreso, tiempo real, rachas y áreas. Lee tus cursos y sesiones; no crea actividad. |
| **Dashboard → My Learning** | Tu biblioteca de cursos, proyectos y certificaciones: pendientes, en curso y terminados. Aquí organizas lecciones y marcas lo completado. No es sólo lo aprendido. |
| **Dashboard → Abilities** | Reúne habilidades asociadas al temario, prácticas y trabajos. Descarga el CSV con su procedencia. La autonomía es una autoevaluación opcional. |
| **Learning Roadmap** | Tu meta dividida en fases, fechas y entregables. Vincula aprendizajes de My Learning a cada fase. Confirmar un entregable registra ese resultado; no completa automáticamente lecciones ni añade horas. |
| **Garden of Knowledge** | Temas que tú confirmas haber comprendido. La última práctica y los repasos valorados orientan el color y la siguiente sugerencia de repaso. |
| **Learning Log** | Registro de estudio, repaso y práctica en el trabajo, con tiempo real. Alimenta horas, rachas, calendario y habilidades asociadas. Sirve tanto para un curso como para una experiencia fuera de él. |
| **Learning Radar** | Catálogo de oportunidades con precios, temas, habilidades y fuentes. Puedes guardar favoritos o añadir algo a My Learning y a una fase. Las revisiones no sustituyen tu catálogo ni alteran el progreso. |
| **Focus Plan** | Propone hasta tres bloques según tu tiempo, energía, aprendizajes en curso con lecciones pendientes y temas cuyo repaso corresponde. No organiza toda tu agenda. Crear el plan no registra tiempo. |
| **Import** | Documento, captura manual o conversación → propuesta → validación → revisión → aprobación. Los cursos van a My Learning; rutas completas a Roadmap; trabajos realizados a Learning Log; los temas y habilidades quedan relacionados al contenido. |
| **Credentials** | Certificados y títulos ya obtenidos. Permite asistencia de Gemini, tabla editable, CSV y guardado en lote revisado. Conserva nombre, emisor, fechas, código del programa, ID personal y enlaces. |
| **Profile & Preferences** | Nombre del espacio, zona horaria, disponibilidad, umbral de racha, enfoque profesional y autorización de búsquedas. También permite exportar los registros. |

## Ejemplo: aprender SQL

Puedes ver este mismo mapa dentro de **Dashboard → Overview → Cómo se conectan las secciones**. My Learning contiene cada curso o proyecto con sus lecciones; Learning Roadmap reúne varios de ellos en fases hacia una meta. Puedes usar un curso sin crear una ruta. Import es una forma de añadirlo, junto al botón Añadir aprendizaje y Learning Radar.

1. Encuentras un curso en Learning Radar y lo añades a My Learning.
2. Lo vinculas a una fase de Learning Roadmap y lo pones **En curso**.
3. Estudias una lección: marcas esa lección completada y registras los minutos reales en Learning Log.
4. Indicas las habilidades que practicaste. Abilities suma esa práctica y conserva de qué aprendizaje vino.
5. Cuando comprendiste JOIN, lo añades como tema a Garden of Knowledge. Aplicarlo después en el trabajo también puede registrarse como práctica.
6. Si obtienes un certificado, lo guardas en Credentials y puedes relacionarlo con el curso.

## Entregables, temas y habilidades

- **Entregable**: resultado concreto de una fase, por ejemplo un script que limpia un CSV. La casilla confirma que cumpliste sus criterios.
- **Trabajo que respalda el resultado**: un enlace o trabajo ya registrado mediante Learning Log o Import. Es opcional.
- **Notas**: qué comprobaste, decisiones o pendientes. Son opcionales.
- **Tema**: conocimiento, por ejemplo JOIN.
- **Habilidad**: capacidad práctica, por ejemplo combinar tablas para resolver una pregunta. Que un curso la incluya no implica dominio; sus conexiones se reúnen automáticamente, pero la práctica requiere sesiones registradas. Evaluar tu autonomía es opcional.

## IA e importación

Gemini prepara borradores; no escribe directamente en las tablas de aprendizaje. Si necesitas comprobar un nombre oficial, usa la búsqueda pública dentro del asistente y después pide a Gemini que revise esas fuentes. Comprobar el nombre del programa **no verifica que hayas obtenido la credencial**.

Puedes descargar la propuesta de Import como TXT. El archivo incluye texto legible y una estructura JSON al final, que conserva lecciones y relaciones. Puedes volver a subir ese TXT sin otra llamada a IA, o llevar el borrador directamente a revisión. JSON es un formato de intercambio, no algo que tengas que escribir.

El CSV de Credentials se puede recuperar dentro de esa misma sección. Antes de guardar puedes corregir y eliminar filas. No se inventan fechas exactas si sólo recuerdas un semestre. Revisar duplicados evita volver a insertar una credencial con los mismos datos de identificación; nombres distintos todavía requieren tu revisión.

**Enlaces distintos:** la URL del emisor sirve para consultar/verificar la credencial; la URL de documentos puede apuntar a tu certificado o a una carpeta de Drive. El código del programa (p. ej., PL-300) y el identificador personal son campos separados.

## Qué significa revisar Learning Radar

La selección inicial tiene 54 fichas; **no es un límite del catálogo**. Cargarla no usa APIs y su botón desaparece al estar completa.

Una revisión busca hasta 20 resultados breves, lee como máximo diez páginas y propone **0–5 fichas nuevas y hasta 3 existentes revisadas**. Se compara con todo el catálogo por enlace normalizado y nombre/proveedor. Gemini recibe un índice breve de las fichas más relacionadas, no el historial completo. No se rellenan cupos sin resultados útiles. Los detalles anteriores no se vacían sólo porque una lectura nueva sea parcial. Los cambios guardan historial; las rutas y el avance no se alteran.

La frecuencia automática es de **21 días**, con última revisión, fecha prevista y calendario. Necesita el workflow de GitHub y el consentimiento activados. La ejecución manual muestra una confirmación antes de llamar a APIs.

Tavily: hasta **8 créditos por revisión**, hasta **2 por consulta de nombre**, con presupuesto compartido de **40 por mes UTC dentro de esta app**. Los fallos conservan su reserva porque pueden haber consumido cuota. No es el saldo global de tu cuenta. Gemini utiliza tokens: su contexto y salida están acotados, pero no hay un presupuesto monetario mensual de Gemini en la app. Cada mensaje es una acción explícita.

## Copia de datos

La exportación de Profile & Preferences incluye los registros de tu usuario: perfil, biblioteca, rutas, lecciones, relaciones, sesiones, temas, habilidades, evaluaciones, credenciales, planes, importaciones y catálogo con su historial.

No contiene contraseñas, claves API ni los archivos adjuntos como PDF/DOCX. Guarda las referencias a esos archivos; descárgalos por separado. **Es una exportación de datos, no una restauración automática:** el importador de cursos no acepta este respaldo como si fuera un plan.

## Activar esta actualización

1. Ejecuta **una vez** `supabase/migrations/003_credential_details.sql` en SQL Editor de Supabase. Añade tres campos de credenciales; no reemplaza tablas ni borra datos. No repitas 001 ni 002.
2. En GitHub Desktop, revisa los cambios y haz commit + push. Mensaje: `Simplificar navegación y añadir asistentes de aprendizaje`.
3. Comprueba los tests de Actions. Streamlit desplegará los cambios; si conserva la pantalla anterior, usa Reboot.
4. Las claves de Gemini y Tavily se conservan. En Profile & Preferences, revisa enfoque y autorizaciones. Para automatización, conserva los secretos del workflow y `ATLAS_RESEARCH_ENABLED=true`.

Las llamadas externas y el despliegue real requieren una comprobación con tus cuentas después de publicar. Las pruebas locales usan respuestas simuladas y una base temporal.
