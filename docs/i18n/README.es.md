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

Las instalaciones nuevas usan Auto: prefieren la barra principal y flotan si falta espacio. Se conservan las preferencias anteriores al actualizar. El menú contextual y la bandeja permiten buscar tareas, abrir categorías de estado, cambiar ajustes y salir.

La ubicación de la barra de estado controla la cuota y los recuentos. Las filas fijadas permanecen conectadas a ella, comparten colores y transparencia y no se arrastran por separado.

![Cápsula flotante](../images/floating.png)

**Auto** prefiere la barra de tareas principal y usa el modo flotante si falta espacio. Vuelve cuando el espacio se estabiliza y evita superponerse a la aplicación en primer plano si está a pantalla completa. **Pantalla flotante** permite seguir la principal o fijar una pantalla; al desconectarla usa la principal temporalmente y restaura la posición relativa al reconectarla. No añade integración en barras de tareas secundarias ni implica pruebas físicas en otras versiones de Windows.

*Datos de ejemplo. El modo flotante comparte los controles y paneles del modo de barra de tareas.*

## Uso

| Al hacer clic en | Se abre |
| --- | --- |
| Cuota semanal | Consumo diario de tokens del ciclo actual |
| Consumo de cuota de hoy | Tokens de hoy por tarea y estado |
| Cuota de 5h, si está disponible | Cuota restante, hora de reinicio e historial registrado |
| Cuenta atrás | Historial de reinicios y créditos de reinicio disponibles |
| Punto de estado y cantidad | Abre directamente la tarea si solo hay una; en caso contrario, abre la lista |
| Nombre de una tarea | Esa tarea en Codex |

Los resúmenes de tareas en curso, pendientes de respuesta, no leídas y fallidas aparecen automáticamente encima de la barra. Cada estado ocupa una fila que alterna sus tareas. Al pasar el cursor o enfocar con el teclado aparece el botón de cierre: oculta el grupo actual hasta que entre una tarea, ejecución o estado nuevo. Las actualizaciones normales y los reinicios no lo vuelven a abrir. El resto de la fila abre la tarea; al cerrar los detalles se restauran los resúmenes.

Los paneles de detalles se abren en esa misma zona conectada y sustituyen temporalmente las filas fijadas. Al cerrarlos, las filas vuelven sin cambiar la configuración de fijación.

En los ajustes puedes elegir inglés, chino simplificado, japonés o español, abrir paneles al pasar el ratón y activar la rotación de cuotas. En este modo, todos los indicadores activados de la izquierda, incluida la cuenta atrás, comparten una posición de ancho fijo.

En Ajustes puedes elegir manualmente el color oscuro o claro de la cápsula y la transparencia del fondo. Un 0% significa fondo opaco; el texto y los anillos no se atenúan.

Haz clic derecho y elige **Buscar tarea…** para buscar tareas guardadas por título o proyecto. Filtra por proyecto y abre un resultado con un clic o con las flechas y Enter. La búsqueda es local y no guarda el texto introducido. El filtro solo afecta a esta ventana.

La barra se ajusta al contenido y al espacio disponible. Las filas fijadas reservan un ancho legible, siguen a la barra y se ocultan si esta no está disponible o hay una aplicación a pantalla completa. Los estados fijados vacíos siguen accesibles en el menú de la bandeja para poder desfijarlos.

![Búsqueda de tareas](../images/task-search.png)

*Datos de ejemplo. La herramienta aún no muestra las solicitudes de entrada o aprobación en tiempo real de otros clientes de Codex.*

## Qué significan los datos

Semana y 5h indican cuota restante; Hoy indica consumo observado desde la primera lectura del día. Los detalles muestran el inicio de observación y la última actualización. Un marcador identifica los valores conservados tras un fallo; las cuotas y horas de reinicio caducadas pasan a desconocidas. Los tokens locales no equivalen a un porcentaje exacto de la cuota de cuenta.

La búsqueda muestra inicialmente proyecto, título, estado y actividad reciente. Activa Estadísticas históricas para revelar tiempo, tokens, turnos y unidades. La indexación solo se ejecuta mientras la ventana y las estadísticas están visibles; al ocultarlas se pausa y conserva la caché. La selección y los filtros se mantienen. `≥` indica un mínimo conocido cuando faltan registros.

La barra lateral organiza los ajustes en Apariencia, Indicadores y General. Los cambios se aplican al instante, incluido el ancho de la cápsula. General permite activar avisos de respuesta (desactivados por defecto) y copiar un diagnóstico sin nombres de tareas, cuentas, rutas ni registros.

Una pregunta síncrona sin respuesta aparece como «Requiere respuesta», con un signo de interrogación ámbar. Se responde en Codex. Los avisos agrupan nuevas tareas en espera sin repetir estados sin cambios. Las preguntas asíncronas, los chats laterales no guardados y las aprobaciones humanas no tienen cobertura completa.

![Ajustes](../images/settings.png)

![Indicador de respuesta pendiente con datos de ejemplo](../images/attention.png)

- Los porcentajes de cuota proceden de la cuenta; los tokens, de los registros de tareas de este equipo. Los tokens no permiten calcular un porcentaje exacto de cuota ni el coste de la suscripción.
- El consumo diario parte de la primera lectura disponible del día y se conserva al reiniciar. No reconstruye el consumo anterior. Si la cuota se reinicia durante el día, suma los intervalos por separado.
- La lista diaria incluye los turnos de hoy. Los paneles de estado muestran la duración del turno actual o más reciente, incluida la espera de herramientas.
- Los totales históricos solo cubren tareas registradas en este equipo. Excluyen otros dispositivos y chats laterales temporales sin consumo guardado.
- Selecciona **USD** en el consumo del ciclo o del día, o usa el selector del encabezado del historial, para ver un coste equivalente estimado con tarifas Standard de la API. Los precios, verificados el 16-09-2026, distinguen modelos, caché y contexto largo. No representa la factura de la suscripción; los registros sin modelo o detalle suficiente muestran un guion.

El historial compara el consumo total entre reinicios. Los colores distinguen los programados (azul), oficiales (morado) y manuales (verde azulado); la unidad aparece una sola vez en el encabezado. Las fechas marcan los límites de cada período. Arrastra o desplázate para consultar el historial, sin detalles adicionales al seleccionar barras. Los datos ausentes se indican con un guion. Los reinicios oficiales siguen siendo una clasificación inferida. La [previsión opcional de Codex Reset Today](https://codex-reset.today/developers) es global, no una garantía para tu cuenta. Usar un crédito requiere confirmación.

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
