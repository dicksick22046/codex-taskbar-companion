# Codex Taskbar Companion

[English](../../README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · **Español**

Muestra la cuota de Codex, el consumo de tokens y el estado de las tareas en la barra de tareas de Windows 11 o en una cápsula flotante.

[Descargar](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest) · [Informar de un problema](https://github.com/dicksick22046/codex-taskbar-companion/issues) · [Cambios](../../CHANGELOG.md)

![Barra y panel de tareas](../images/preview.png)

*Vista previa con tareas y datos de ejemplo.*

## Instalación

Requiere **Windows 11 x64** y la **aplicación de escritorio de Codex**, instalada y con la sesión iniciada.

1. Descarga `CodexTaskbarCompanion-<version>-Setup-x64.exe` desde [Releases](https://github.com/dicksick22046/codex-taskbar-companion/releases/latest).
2. Ejecuta el instalador y abre la aplicación. Incluye Python, Qt y las fuentes; no requiere permisos de administrador.
3. Haz clic derecho en la barra para abrir los ajustes. Elige qué mostrar y si debe iniciarse al entrar en Windows.

Se coloca a la izquierda de la barra de tareas principal. Si no hay espacio, puedes abrir los ajustes desde la bandeja del sistema. Busca actualizaciones en GitHub, pero solo las instala cuando tú lo eliges.

Elige **Ubicación → Flotante** en los ajustes para mover la cápsula arrastrándola. La posición se conserva al reiniciar. **Mantener encima** es opcional; los paneles se abren arriba o abajo según el espacio disponible. Puedes volver a **Barra de tareas** en cualquier momento.

![Cápsula flotante](../images/floating.png)

*Datos de ejemplo. El modo flotante comparte los controles y paneles del modo de barra de tareas.*

## Uso

| Al hacer clic en | Se abre |
| --- | --- |
| Cuota semanal | Consumo diario de tokens del ciclo actual |
| Consumo de cuota de hoy | Tokens de hoy por tarea y estado |
| Cuota de 5h, si está disponible | Cuota restante, hora de reinicio e historial registrado |
| Cuenta atrás | Historial de reinicios y créditos de reinicio disponibles |
| Punto de estado y cantidad | Tareas de ese estado, con la duración del turno actual o más reciente |
| Nombre de una tarea | Esa tarea en Codex |

Las tareas en curso se alternan en la barra. Al pasar el ratón, la rotación se detiene y los nombres largos se desplazan. Los resultados sin leer, las tareas detenidas y los fallos tienen indicadores separados. Un chat lateral activo cuenta como actividad de su tarea principal, sin duplicarla.

En los ajustes puedes elegir inglés, chino simplificado, japonés o español, abrir paneles al pasar el ratón y activar la rotación de cuotas. En este modo, todos los indicadores activados de la izquierda, incluida la cuenta atrás, comparten una posición de ancho fijo.

En Ajustes puedes elegir manualmente el color oscuro o claro de la cápsula y la transparencia del fondo. Un 0% significa fondo opaco; el texto y los anillos no se atenúan.

Haz clic derecho y elige **Buscar tarea…** para buscar tareas guardadas por título o proyecto. Filtra por proyecto y abre un resultado con un clic o con las flechas y Enter. La búsqueda es local y no guarda el texto introducido. El filtro solo afecta a esta ventana.

La cápsula se ajusta al contenido hasta el ancho máximo anterior. Reserva espacio para la tarea más larga de la rotación, evitando cambios de tamaño entre tareas. El catálogo también incluye ejecuciones CLI guardadas; sus registros pueden aumentar los totales locales de tokens.

![Búsqueda de tareas](../images/task-search.png)

*Datos de ejemplo. La herramienta aún no muestra las solicitudes de entrada o aprobación en tiempo real de otros clientes de Codex.*

## Qué significan los datos

La búsqueda muestra tiempo activo, tokens y turnos acumulados del historial local. Haz clic en una cabecera para ordenar y otra vez para invertir el orden. El historial se procesa por lotes mientras la ventana está abierta y se conserva en caché. El tiempo incluye esperas dentro del turno y excluye pausas entre turnos. `≥` indica un mínimo conocido cuando faltan registros.

Los ajustes se agrupan en Apariencia, Indicadores y General. Una pregunta síncrona sin respuesta aparece como «Requiere respuesta», con un signo de interrogación ámbar. Se responde en Codex. Las preguntas asíncronas, los chats laterales no guardados y las aprobaciones humanas no tienen cobertura completa.

![Ajustes](../images/settings.png)

![Indicador de respuesta pendiente con datos de ejemplo](../images/attention.png)

- Los porcentajes de cuota proceden de la cuenta; los tokens, de los registros de tareas de este equipo. Los tokens no permiten calcular un porcentaje exacto de cuota ni el coste de la suscripción.
- El consumo diario parte de la primera lectura disponible del día y se conserva al reiniciar. No reconstruye el consumo anterior. Si la cuota se reinicia durante el día, suma los intervalos por separado.
- La lista diaria incluye los turnos de hoy. Los paneles de estado muestran la duración del turno actual o más reciente, incluida la espera de herramientas.
- Los totales históricos solo cubren tareas registradas en este equipo. Excluyen otros dispositivos y chats laterales temporales sin consumo guardado.

En el historial, Scheduled indica un cambio de ciclo observado; Manual, un reinicio confirmado mediante esta herramienta; y Official, las demás recuperaciones observadas. Official es una clasificación inferida, no una confirmación de OpenAI. Usar un crédito de reinicio requiere confirmación y consume un crédito real.

## Datos y limitaciones

Los ajustes, nombres de tareas y registros de uso se guardan en `%USERPROFILE%/.codex-taskbar-companion`. Las actualizaciones y la desinstalación conservan esa carpeta. La aplicación no guarda el texto de las conversaciones ni credenciales, y no tiene telemetría. Elimina los datos privados antes de publicar capturas o registros.

Es una versión inicial para Windows 11. No se han validado Windows 10, macOS, widgets independientes en varios monitores ni barras de tareas de terceros. El instalador no tiene firma de código. La detección de chats laterales depende de los registros de Codex y puede necesitar ajustes si cambia su formato. Los fallos temporales de lectura conservan los datos válidos, pero no se detectan todos los errores transitorios de Codex.

## Desarrollo

Usa Python 3.12. Para crear el instalador también necesitas Inno Setup.

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
./start.ps1
.venv/Scripts/python.exe -m unittest discover
./scripts/package.ps1 -Compiler 'C:/Path/To/Inno Setup/ISCC.exe'
```

Cierra la versión instalada antes de ejecutar el código fuente; una segunda instancia abre los ajustes de la que ya está activa. Los resultados se guardan en `dist/` y `release/`; la versión se define en `codex_taskbar/build_info.py`.

Para probar el panel de 5h sin una cuenta que lo ofrezca, ejecuta `./scripts/preview-session.ps1`. Abre una ventana separada con datos de ejemplo y no modifica la cuenta ni los ajustes.

Notas de implementación, en chino: [arquitectura](../architecture.md) y [especificación de interacción](../specs/interaction.md).

## Licencia

[MIT](../../LICENSE). Las fuentes y dependencias mantienen sus propias licencias; consulta [Componentes de terceros](../../THIRD_PARTY.md). Es un proyecto comunitario independiente, sin afiliación con OpenAI.
