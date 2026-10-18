# Contrato de comportamiento implementado · v1

Propósito: acompañar el crecimiento personal del usuario. La aplicación organiza intención, contenido, práctica y evidencia como hechos distintos. El contrato se verifica con ejemplos de entrada y resultados esperados en `tests/`.

| Regla | Definición | Ejemplo verificable |
|---|---|---|
| Progreso | Peso de unidades hoja obligatorias completadas dividido entre peso obligatorio total. Los módulos padre y unidades opcionales no inflan el denominador. | Dos hojas de pesos 1 y 3: completar la primera da 25%. |
| Sin temario | Sin hojas obligatorias no existe un porcentaje calculable. | Se muestra “Sin definir”, no un 0% inventado. |
| Tiempo real | Suma de minutos de sesiones no anuladas. Completar una unidad no añade tiempo. | Completar una lección sin sesión conserva 0 minutos. |
| Estimación | Suma del material obligatorio y, por separado, del material pendiente; las estimaciones desconocidas se señalan. | Haber estudiado 90 minutos no resta automáticamente 90 a la estimación. |
| Racha | Días locales consecutivos que alcanzan el umbral del perfil; hoy puede no estar completo si ayer sí lo estuvo. | 6 + 4 minutos el mismo día cuentan como 10; 9 minutos no cumplen un umbral de 10. |
| Fecha local | La sesión conserva la fecha local y zona horaria de entrada. No se admiten sesiones futuras. | Cambiar la zona del perfil no mueve retrospectivamente el día registrado. |
| Temas | Cubierto por un curso y aprendido por el usuario son estados diferentes. | Importar el temario no crea un evento “aprendido”. |
| Repaso | Intervalo inicial 3 días; valoración “otra vez” → 1; difícil → ×0,7 redondeado, mínimo 1; recordado → ×2; fácil → ×3, máximo 180. Una valoración efectiva por fecha. | Dos repasos valorados el mismo día no duplican la ampliación. |
| Práctica laboral | Actualiza fecha de práctica y tiempo. Sin valoración no amplía por sí sola el intervalo de repaso. | Trabajo del día 16 puede coexistir con un repaso sugerido para el día 9. |
| Habilidades | Cobertura deduplicada por aprendizaje; minutos repartidos entre habilidades seleccionadas, conservando la suma. | 31 minutos entre dos habilidades → 16 y 15, no 31 para cada una. |
| Autoevaluación | Escala ordinal 0–3 de autonomía; sólo se compara la misma habilidad y rúbrica en fechas distintas. | Una sola medición no se presenta como mejora. |
| Credenciales | Registro explícito del logro, tipo, emisor y vigencia conocida; no se verifican automáticamente. | Un certificado de curso no pasa a ser certificación profesional. |
| Ruta | Calendario y presupuesto versionados; entregables aceptados explícitamente. | El plan de 96 h comienza con 0 sesiones y 0 entregables aceptados. |
| Día libre | 1–3 bloques de 10–40 min, pausas de 5 min, suma dentro del tiempo disponible; puede quedar margen libre. | Presupuesto de 20 min → un bloque, nunca tres bloques de 20. |
| Registro de un bloque | Sólo el registro de la sesión añade minutos; un bloque ya registrado no acepta otra sesión vigente. | Pulsar de nuevo no duplica el tiempo; anular permite corregirlo. |
| Importación | Archivo → extracción → propuesta tipada → borrador → revisión → transacción. | Una referencia inválida revierte todo el lote de registros. |
| Aprobación vigente | El contenido revisado debe coincidir con el borrador actual en servidor. | Editar una propuesta invalida una aprobación anterior. |
| Reintentos | Identificador de operación y recibo; mismo intento confirmado devuelve resultado previo. | Repetir el envío no inserta dos sesiones. Cambiar la intención con el mismo ID se rechaza. |
| Concurrencia | Revisión por usuario; una escritura con versión antigua se rechaza. | Dos pestañas no se sobrescriben silenciosamente. |
| Privacidad | Usuario obtenido de Auth; relaciones compuestas por usuario; lectura por RLS y adjuntos privados. | La cuenta B no lee filas ni referencia entidades de A. |

## Aceptación de esta entrega

La implementación se considera lista para conectar cuando pasan los tests locales, el SQL ejecuta en el motor de pruebas y las pantallas y formularios se verifican. La publicación se considera completa **después** de entrar en la URL de Streamlit con tu cuenta, guardar y recuperar datos y descargar un adjunto desde tu Supabase.

Las pruebas con PGlite ejecutan SQL real en PostgreSQL WebAssembly, con Auth y tablas de control de Storage simuladas. No afirman que una cuenta o servicio externo ya esté configurado. La prueba de simultaneidad real usa dos conexiones PostgreSQL en CI; la de la propuesta Gemini usa respuestas HTTP simuladas hasta que configures tu clave.

## Fuera de esta versión

OCR, sincronización periódica sin intervención, conexiones privadas a plataformas educativas, comprobación externa de certificados, importación automática sin revisión y un modelo validado de memoria. El plan del día usa reglas; las sugerencias de catálogo son editoriales. Estas distinciones se muestran en la app.
