# Publicar y actualizar Learning Atlas

Carpeta de trabajo: `C:\Users\deef3\learning-atlas`.

Repositorio elegido: [caprex117/learning-atlas](https://github.com/caprex117/learning-atlas).

El flujo es **editar archivos → commit → push a GitHub → actualización de Streamlit**. Un commit guarda una versión en tu computadora; push la envía al repositorio remoto. GitHub no vigila la carpeta local. Streamlit Community Cloud toma el código de la rama que hayas conectado, normalmente `main`.

## Primera conexión con GitHub Desktop

1. Instala [GitHub Desktop](https://desktop.github.com/) e inicia sesión con la cuenta que tiene acceso al repositorio. Si pide configurar Git, usa tu nombre y el correo de commits que prefieras, incluido el correo privado que ofrece GitHub.
2. Si la carpeta ya tiene Git inicializado, selecciona **File → Add local repository**, elige `C:\Users\deef3\learning-atlas` y pulsa **Add repository**.
3. Revisa **Repository → Repository settings → Remote**: `origin` debe apuntar a `https://github.com/caprex117/learning-atlas.git`.
4. Revisa los archivos en **Changes**. Deben ser el código, configuración de ejemplo, pruebas y documentación. `.streamlit/secrets.toml`, `.env`, `private/`, `.venv/` y `node_modules/` están excluidos por `.gitignore`.
5. **Si el repositorio remoto está vacío**, escribe `Versión inicial de Learning Atlas` en **Summary**, pulsa **Commit to main** y después **Publish branch** o **Push origin**, según el botón que aparezca. Ya existe un repositorio remoto: no hace falta crear otro con **Publish repository**.
6. En GitHub, comprueba que `streamlit_app.py` y `requirements.txt` aparecen directamente en la raíz. En **Actions**, espera el resultado de **Learning Atlas tests**.

Si el remoto ya contiene commits y la carpeta local no es un clon suyo, primero hay que recuperar y conservar ese historial. No fuerces el push ni publiques una historia independiente encima. La alternativa es clonar el repositorio con Desktop en una carpeta vacía y copiar encima sólo los archivos del proyecto; nunca copies una carpeta `.git` desde otro lugar.

La sesión de GitHub se completa en tu navegador o Desktop. No necesitas pegar tokens ni contraseñas en el chat.

## Conectar Streamlit una vez

En [Streamlit Community Cloud](https://share.streamlit.io/), selecciona el repositorio `caprex117/learning-atlas`, la rama `main` y el archivo `streamlit_app.py`. Sigue [DEPLOYMENT.md](DEPLOYMENT.md) para Python 3.12, Supabase y Secrets.

Después, cada push a esa rama se refleja automáticamente en la app. Un cambio en `requirements.txt` puede tardar más porque reinstala dependencias. No hay que subir un ZIP ni volver a crear la app en cada actualización. [Documentación de Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).

## Cambios posteriores

Para una actualización directa:

1. Abre el repositorio en Desktop y usa **Fetch origin**; si aparece **Pull origin**, descarga los cambios antes de editar.
2. Modifica los archivos de `C:\Users\deef3\learning-atlas` y verifica el cambio.
3. Revisa **Changes**, escribe una descripción y pulsa **Commit to main**.
4. Pulsa **Push origin**. Streamlit recoge la nueva versión y GitHub Actions ejecuta las pruebas.
5. Comprueba el resultado de Actions y abre la app para verificar el comportamiento.

**Streamlit no espera automáticamente a que Actions termine.** Para probar antes de publicar, crea una rama como `codex/mejora-progreso`, guarda y sube allí los cambios, abre un pull request hacia `main` y espera a que las pruebas pasen antes de combinarlo. Al combinarlo, Streamlit actualizará `main`. Este procedimiento es manual mientras no haya reglas del repositorio que exijan las comprobaciones.

El workflow actual ejecuta pruebas en cada push y pull request, usando PostgreSQL temporal. No publica cambios en Supabase ni necesita secretos de tu base real.

## Qué sucede con Supabase

| Cambio | Cómo se aplica |
|---|---|
| Añadir cursos, progreso, sesiones o documentos desde la app conectada | La app guarda en Supabase; no requiere commit ni push. |
| Cambiar pantallas, colores o lógica Python | Commit y push a la rama conectada; Streamlit actualiza el código. |
| Añadir tablas, columnas o cambiar funciones SQL | Requiere una nueva migración SQL y su aplicación a Supabase; el push de Git por sí solo no la ejecuta. |
| Cambiar una clave o configuración secreta | Actualiza Secrets en Streamlit; no la subas a GitHub. |

`001_learning_atlas.sql` instala la base una sola vez. Para futuras modificaciones conservaremos ese archivo y añadiremos una migración nueva, con instrucciones y pruebas específicas. La instalación actual usa el SQL Editor; todavía no hay despliegue automático de base de datos. Antes de adoptar la CLI habrá que conciliar su historial con la instalación ya aplicada, para evitar intentar crear las tablas otra vez. [Migraciones de Supabase](https://supabase.com/docs/guides/deployment/database-migrations).

Los cambios de interfaz no borran tus registros de aprendizaje. Si una actualización necesita modificar datos o estructura, deberá incluir expresamente esa migración y su validación.

## Ejecutar localmente desde la carpeta nueva

El entorno virtual de otra carpeta no se traslada. Si deseas ejecutar o probar la app localmente, crea uno en esta carpeta siguiendo [README.md](../README.md). Para publicar en Streamlit no necesitas instalar ese entorno en tu computadora.
