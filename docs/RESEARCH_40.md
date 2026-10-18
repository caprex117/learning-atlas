# Selección personal de 40 oportunidades

Esta es la selección histórica inicial. Consulta la [ampliación vigente a 54](RESEARCH_54.md), que añade 14 fichas y actualiza las prioridades.

Revisión: **18 de octubre de 2026**. Se contrastaron 60 candidatos o recursos complementarios y se seleccionaron **40 fichas: 33 recursos/cursos/certificaciones y siete Learning Packs**. Los packs reúnen recursos que también pueden aparecer como fichas; no representan siete programas oficiales ni horas adicionales.

## Criterio y límites

Prioridad editorial para tu ruta Factory Enablement, tu experiencia en BI/sistemas/proyectos y tu interés explícito en crear apps con IA. Primero: dependencias inmediatas, reutilización en un entregable y herramientas que ya utilizas. Después: integración industrial. Al final: especializaciones y exploración de bajo nivel. El orden no pretende medir demanda laboral ni establecer una clasificación universal.

La ruta principal sigue del 12 de octubre de 2026 al 3 de enero de 2027, con 8 horas semanales y 96 horas totales. Partimos de ningún avance declarado. Los bloques sugeridos son **puntos de entrada estimados por nosotros**: se solapan entre recursos y packs, y se eligen dentro del presupuesto existente. No sumar los 40 bloques ni tomar un recurso consultado como habilidad dominada. El pack de apps puede usar una mejora de Learning Atlas; si amplía el alcance, se pospone o sustituye otra práctica.

Fuentes primarias: documentación oficial, proveedores, proyectos abiertos y organismos responsables. Cada ficha guarda enlaces y evidencia resumida; los temarios son resúmenes salvo los expresamente identificados como publicados o propios. La hora 00:00 es convencional para la fecha de revisión. `checked_at` significa consulta, y `provider_updated_on` sólo se completa cuando la fuente declara una fecha; vacío no significa desactualizado. Las guías de fundamentos antiguas se mantienen cuando resuelven una necesidad actual.

Los precios distinguen lectura gratuita, examen, suscripción y licencias. No estimamos precios que no pudimos confirmar. CCNA figura con USD 300 para el examen; no incluye preparación ni cargos locales. PL-300 y DP-700 tienen precio regional sin importe confirmado. Una documentación gratuita no convierte su producto comercial en gratuito. La guía DP-700 consultada anuncia objetivos efectivos el **19 de octubre**, posteriores a esta revisión. En Cisco Networking Basics se conserva un resumen parcial porque la ficha dinámica no expuso todo el temario. open62541 apunta a documentación de desarrollo: consultar la versión compatible al practicar.

## Orden recomendado

P1 Python/Git · P2 datos/SQL · P3 BI/KPIs · P4 Ignition/OPC UA · P5 sistemas/IA · P6 entrega. Transversal: aplicación a una tarea de la ruta o a tu app. Después: explorar cuando termines o decidas cambiar prioridades.

| Prioridad | Oportunidad / fuente principal | Momento | Primer alcance sugerido |
|---:|---|---|---|
| 1 | [Learning Pack — Python verificable: de un CSV a un resultado confiable](https://docs.python.org/3/library/csv.html) | P1 | Construir el validador y seis casos de prueba como parte de las 16 h de la fase 1. |
| 2 | [Learning Pack — Construir una app con IA: del contrato al despliegue](https://docs.github.com/en/copilot/tutorials/copilot-cookbook/refactor-code) | Transversal | Elegir una mejora pequeña de Learning Atlas y cerrar contrato, diff, tests y verificación; sustituye parte de la práctica, no suma una ruta nueva. |
| 3 | [Exercism — Python Track](https://exercism.org/tracks/python) | P1 | Empezar los ejercicios de tu plan y revisar dos soluciones explicando sus tests. |
| 4 | [The Python Tutorial](https://docs.python.org/3/tutorial) | P1 | Consultar funciones, colecciones y excepciones sólo cuando lo necesite el ejercicio. |
| 5 | [Pro Git — fundamentos y ramas](https://git-scm.com/book/en/v2) | P1 | Practicar status, diff, add, commit, log y una rama de cambio. |
| 6 | [GitHub Skills — Introduction to GitHub](https://github.com/skills/introduction-to-github) | P1 | Completar el recorrido de rama, commit y pull request. |
| 7 | [Streamlit — tutoriales para apps de datos](https://docs.streamlit.io/develop/tutorials) | Transversal | Añadir un formulario con validación y estado de sesión a tu app. |
| 8 | [Supabase — Auth, PostgreSQL y Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security) | Transversal | Comprobar acceso propio, acceso ajeno y acceso sin sesión en una tabla de práctica. |
| 9 | [Desarrollo asistido por IA — revisar y refactorizar código](https://docs.github.com/en/copilot/tutorials/copilot-cookbook/refactor-code) | Transversal | Pedir una refactorización corta y comprobar comportamiento antes y después. |
| 10 | [pandas — Getting started tutorials](https://pandas.pydata.org/docs/getting_started/intro_tutorials/index.html) | P2 | Limpiar eventos conservando raw y anotar reglas de fecha, duplicados y faltantes. |
| 11 | [PostgreSQL — Tutorial](https://postgresql.org/docs/current/tutorial.html) | P2 | Crear tablas con claves y cinco consultas; usar una ventana para primer y último intento. |
| 12 | [CS50’s Introduction to Databases with SQL](https://cs50.harvard.edu/sql) | P2 | Elegir el módulo de consultas o relaciones que resuelva una brecha; no cursar todo ahora. |
| 13 | [Learning Pack — De registros operativos a datos utilizables](https://docs.python.org/3/tutorial) | P2 | Integrar la transformación y carga idempotente del mismo dataset. |
| 14 | [Prepare data for analysis with Power BI](https://learn.microsoft.com/en-us/training/paths/prepare-data-power-bi) | P3 | Priorizar limpieza y tipos; la ruta completa oficial dura 273 minutos. |
| 15 | [Power BI — guía de esquema en estrella](https://learn.microsoft.com/power-bi/guidance/star-schema) | P3 | Dibujar hechos, dimensiones, grano y relaciones antes de construir el modelo. |
| 16 | [DAX 101 — Row context and filter context](https://sqlbi.com/articles/row-context-and-filter-context-in-dax) | P3 | Explicar dos medidas bajo filtros diferentes y verificar su denominador. |
| 17 | [Microsoft Power BI Data Analyst — PL-300](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/pl-300) | P3 | Usar la guía como diagnóstico de brechas; decidir más adelante si pagar el examen. |
| 18 | [Learning Pack — KPIs industriales con contratos y reconciliación](https://asq.org/quality-resources/quality-glossary) | P3 | Reconciliar FPY, yield final y OEE en casos pequeños antes del dashboard. |
| 19 | [OEE — cálculo de disponibilidad, rendimiento y calidad](https://oee.com/calculating-oee) | P3 | Calcular un caso a mano y comprobar las tres pérdidas por separado. |
| 20 | [Inductive University — Ignition 8.3 Core Training](https://inductiveuniversity.com/courses/ignition/ignition-overview/8.3) | P4 | Crear una máquina simulada, tags, alarma y una vista con timestamp/calidad. |
| 21 | [OPC UA — arquitectura e intercambio de información](https://opcfoundation.org/about/opc-technologies/opc-ua) | P4 | Mapear cliente, servidor, espacio de nombres, permisos y suscripciones del laboratorio. |
| 22 | [Cisco Networking Basics](https://netacad.com/courses/networking-basics) | P4 | Repasar IP, conectividad y diagnóstico útil para el servidor de práctica. |
| 23 | [NIST SP 800-82 Rev. 3 — Guide to OT Security](https://csrc.nist.gov/pubs/sp/800/82/r3/final) | P4 | Leer arquitectura y riesgos OT, y documentar tres controles del laboratorio. |
| 24 | [MQTT Essentials](https://hivemq.com/mqtt) | Después | Explorar pub/sub, QoS y retained messages antes de elegir un segundo protocolo. |
| 25 | [Node-RED — Tutorials](https://nodered.org/docs/tutorials) | Después | Montar un flujo pequeño de eventos sintéticos con salida de depuración. |
| 26 | [Learning Pack — Primer mapa de integración OT/IT](https://hivemq.com/mqtt) | Después | Dibujar el flujo de eventos y riesgos; implementar sólo si el laboratorio principal ya está listo. |
| 27 | [ISA-95 — mapa de integración empresa y manufactura](https://isa.org/standards-and-publications/isa-standards/isa-95-standard) | P5 | Ubicar control, operaciones y empresa en un diagrama de una página. |
| 28 | [Learning Pack — Mapa de sistemas: MES, ERP, PLM, CMMS y RTLS](https://isa.org/standards-and-publications/isa-standards/isa-95-standard) | P5 | Asignar cinco datos a su sistema responsable y dibujar sus intercambios. |
| 29 | [NIST AI RMF — evaluar un caso de uso de IA](https://nist.gov/itl/ai-risk-management-framework) | P5 | Comparar tres ideas de IA por valor, riesgo y esfuerzo, con criterio para aceptar o rechazar. |
| 30 | [OWASP Top 10 for LLM Applications — edición 2025](https://genai.owasp.org/llm-top-10) | Transversal | Revisar importación de documentos, salida del modelo, permisos y consumo de tu app. |
| 31 | [Learning Pack — Piloto reproducible y entrega a otra persona](https://docs.github.com/en/actions/get-started/quickstart) | P6 | Preparar README, tests, demo con fallo controlado y entrega del mismo piloto. |
| 32 | [Power Automate — Microsoft Learn](https://learn.microsoft.com/en-us/training/powerplatform/power-automate) | Después | Identificar una tarea repetitiva y estudiar un flujo sencillo antes de licenciar conectores. |
| 33 | [Docker — Get started](https://docs.docker.com/get-started) | P6 opcional | Reproducir el entorno sólo si facilita la entrega; un entorno virtual documentado también sirve. |
| 34 | [FastAPI — Tutorial: User Guide](https://fastapi.tiangolo.com/tutorial) | Después | Crear una API mínima con validación y un test, sin reescribir la app existente. |
| 35 | [GitHub Actions — primera automatización de pruebas](https://docs.github.com/en/actions/get-started/quickstart) | P6 | Entender el workflow actual y añadir un caso de regresión a la ejecución automática. |
| 36 | [Cisco Certified Network Associate — CCNA](https://cisco.com/site/us/en/learn/training-certifications/certifications/enterprise/ccna/index.html) | Después | Revisar objetivos y contrastarlos con Networking Basics antes de elegir preparación o examen. |
| 37 | [Microsoft Fabric Data Engineer — DP-700](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/dp-700) | Después | Comparar requisitos con tu base de SQL y Power BI; no abrir otra certificación durante el piloto. |
| 38 | [open62541 — tutoriales de OPC UA en C](https://open62541.org/doc/master/tutorials.html) | Después | Leer un servidor mínimo y anotar qué fundamentos de C necesitas reforzar antes de compilar. |
| 39 | [OSSU — Computer Science curriculum](https://github.com/ossu/computer-science) | Después | Elegir una sola materia de fundamentos que cubra una brecha detectada. |
| 40 | [Nand to Tetris — Projects](https://nand2tetris.org/course) | Después | Explorar el primer proyecto para decidir si profundizar en la relación hardware-software. |

## Alternativas y complementos revisados

No seleccionados como ficha independiente en esta primera lista. Algunos ya están incorporados dentro de un pack; otros quedan como opciones posteriores. Los motivos son decisiones para tu situación, no valoraciones negativas de los recursos.

| Recurso | Decisión |
|---|---|
| [CS50P](https://cs50.harvard.edu/python/) | Alternativa más extensa para reforzar Python; por ahora tu práctica de Exercism y el validador cubren el punto de entrada. |
| [Kaggle Intro to SQL](https://www.kaggle.com/learn/intro-to-sql) | Otra puerta de entrada a SQL; evitar tres cursos iniciales simultáneos. |
| [freeCodeCamp Relational Databases](https://www.freecodecamp.org/news/freecodecamps-new-relational-databases-certification-is-now-live) | Alternativa comunitaria de práctica; priorizar PostgreSQL aplicado a tu dataset. |
| [Microsoft DP-600](https://learn.microsoft.com/en-us/credentials/certifications/fabric-analytics-engineer-associate/) | Especialización de Fabric para más adelante, después del modelo Power BI y del piloto. |
| [Microsoft AZ-900](https://learn.microsoft.com/en-us/credentials/certifications/azure-fundamentals/) | Elegir fundamentos de nube cuando exista un destino concreto de despliegue. |
| [AWS Cloud Practitioner](https://docs.aws.amazon.com/aws-certification/latest/cloud-practitioner-02/) | No abrir otra nube mientras consolidas tu stack actual. |
| [PMI CAPM](https://www.pmi.org/certifications/certified-associate-capm) | Tu minor y experiencia de proyectos permiten priorizar ahora la evidencia técnica del piloto. |
| [PMI PMP](https://www.pmi.org/certifications/project-management-pmp) | Evaluar elegibilidad y objetivos profesionales en otra etapa; no se presume que ya cumplas sus requisitos. |
| [ISACA CISA](https://www.isaca.org/credentialing/cisa) | Mantener el taller ya mencionado; no crear otra obligación ni dar por obtenida la credencial. |
| [ISC2 CC](https://www.isc2.org/certifications/cc) | Ya declaraste esta certificación; reutilizar la base, no recomendarla como si fuera nueva. |
| [Google Cybersecurity](https://www.coursera.org/professional-certificates/google-cybersecurity) | Ya declaraste este certificado; evitar duplicar aprendizaje y gasto. |
| [dbt Learn](https://www.getdbt.com/dbt-learn) | Interesante después de SQL y reglas reproducibles; no introducir otra capa de transformación ahora. |
| [Data Engineering Zoomcamp](https://github.com/DataTalksClub/data-engineering-zoomcamp) | Ruta comunitaria amplia; posible continuación después de enero, no programa paralelo. |
| [Confluent Developer / Kafka](https://developer.confluent.io/) | Elegir mensajería distribuida cuando haya una necesidad real; MQTT y OPC UA están más cerca del laboratorio actual. |
| [pytest](https://docs.pytest.org/en/stable/getting-started.html) | Incluido como componente de los packs de apps y entrega; no ocupa una ficha adicional. |
| [Kubernetes Basics](https://kubernetes.io/docs/tutorials/kubernetes-basics/) | No necesitas un clúster para publicar estas apps y demostrar el piloto. |
| [C# introductorio](https://learn.microsoft.com/en-us/training/paths/get-started-c-sharp-part-1/) | Ya tienes C# entre tus habilidades; profundizar cuando una integración lo requiera. |
| [SQLAlchemy Unified Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/) | Complemento posterior para APIs Python; no reemplazar el acceso actual sólo para sumar tecnología. |
| [The Rust Programming Language](https://doc.rust-lang.org/book/) | Exploración de sistemas más adelante; open62541 y Nand to Tetris conectan primero con tus preguntas de bajo nivel. |
| [ISA/IEC 62443 Certificate Program](https://www.isa.org/certification/certificate-programs/isa-iec-62443-cybersecurity-certificate-program) | Evaluar inversión en formación específica de OT después de la base de redes y del laboratorio. |

## Cómo llega a Supabase

`data/catalog_seed.json` es la investigación validada. La app o el archivo `supabase/seeds/learning_catalog_40.sql` distribuyen los datos en `opportunities`, `opportunity_sources`, `pack_components`, `opportunity_versions` y `discovery_runs`. La prioridad, fase y bloque sugerido se conservan en `discovery_runs.details.rankings`, relacionados por la identidad estable de la ficha; no hace falta otra migración. `opportunity_choices` sólo cambia cuando decides guardar, descartar o incorporar una oportunidad.

La carga conserva los IDs de las 17 fichas anteriores, enriquece su investigación manual y añade las 23 nuevas. Las fichas revisadas posteriormente o por IA se conservan; nunca se eliminan oportunidades extra, favoritos, sesiones ni progreso. Repetir la misma carga no duplica fichas ni versiones. No se crean otros usuarios ni se modifican permisos. Añadir una oportunidad a tu ruta sigue siendo una decisión tuya.

`exports/learning_catalog_40.csv` permite analizar esta selección inicial; no incluye datos de tu cuenta. En la app, **Descubrir → Descargar catálogo completo · CSV** exporta todas tus oportunidades actuales, incluso las descartadas o ya incorporadas, con decisiones e historial. Las listas, fuentes, componentes y versiones están en celdas JSON para preservar todos sus campos. En Power Query puedes usar `Json.Document` y expandirlas. La codificación UTF-8 con BOM conserva las tildes; los precios o duraciones desconocidos quedan vacíos. El CSV es para análisis, **no para importarlo directamente en una sola tabla de Supabase**: para poblar las relaciones utiliza la app o el SQL.

La selección manual no modifica tus ajustes de investigación. Para que próximas revisiones incluyan apps con IA, añade `apps con IA, Streamlit, Supabase, pruebas` a tus temas en **Mi enfoque y actualización semanal**. La prioridad personal conserva este criterio inicial; el orden Relevancia se recalcula según tu enfoque vigente.
