# Arena del Lago Élfico: pipeline

Herramientas que generan la arena (`/Game/Arena`, nivel `L_Arena`). Todo es procedural y reproducible:
las piezas se modelan por script en Blender y se importan y montan en Unreal con Python de editor.
La guía visual está en [STYLE.md](STYLE.md) y los créditos de texturas en [CREDITS.md](CREDITS.md) (todo CC0).

## Requisitos

- Blender 5.2 (`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`)
- Unreal Engine 5.8 (`C:\Aplicaciones\UE_5.8`)
- Los scripts usan una carpeta de trabajo fija, `D:\Repos\_arena_work` (constante `WORK`), con
  `scripts\` (estos archivos), `assets\` (texturas CC0 de ambientCG: Marble014, Metal034, Rock051,
  Moss002, Grass004; ver CREDITS.md) y `export\` (FBX generados). Para usar otra ruta, cambia `WORK`.
- El plugin de Python de Unreal no está activado en el .uproject: se activa por línea de comandos
  con `-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities`.

## Pasos

| Paso | Script | Dónde | Qué hace |
| --- | --- | --- | --- |
| 1 | `kit_build.py` | Blender | Kit de la arena: pilar, arco, suelo, borde, escalones, estandarte y ornamentos (crochets/florones aparte, sin sombra). Exporta `export\SM_Arena_*.fbx` |
| 2 | `bg_build.py` | Blender | Fondo: acantilados, rocas, árboles, cascadas, torres, pabellón, puente, islas, montañas. Exporta `export\SM_BG_*.fbx` y escribe `bg_layout.json` (colocación) |
| 3 | `ue_import.py` | UE commandlet | Texturas, materiales y mallas del kit en `/Game/Arena` (Nanite, colisiones UCX) |
| 4 | `ue_level.py` | UE editor | Crea `L_Arena` desde cero: kit, luz, cielo, niebla, PlayerStart, cámaras y `BP_ArenaGameMode` (sin arena de prueba) |
| 5 | `ue_bg_import.py` | UE commandlet | Texturas, materiales (roca, follaje, agua, cascadas, nubes) y mallas del fondo en `/Game/Arena/Background`, y el Niagara de salpicadura |
| 6 | `ue_background.py` | UE editor | Coloca el fondo en `L_Arena` según `bg_layout.json`, ajusta sol, niebla y nubes, guarda y saca capturas |
| 7 | `ue_pie_test.py` | UE editor | Prueba en Play In Editor: GameMode, jugador sobre el suelo, rival; captura con la cámara de juego |

`ue_shots.py` es el módulo común de capturas (HighResShot desde el visor del editor). `kit_render.py` y
`build_arena.py` son de las primeras fases (render de prueba en Blender y blockout).

## Comandos (PowerShell)

```powershell
$bl  = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$ue  = "C:\Aplicaciones\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$ed  = "C:\Aplicaciones\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$proj = "D:\Repos\Dueling-game\DuelingGame.uproject"
$pl  = "-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities"
# evita que el visor deje de pintar si la ventana del editor no está en primer plano (no se guarda)
$ini = "-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False"
$S   = "D:\Repos\_arena_work\scripts"

& $bl -b --factory-startup --python "$S\kit_build.py"
& $bl -b --factory-startup --python "$S\bg_build.py"
& $ue $proj -run=pythonscript "-script=$S\ue_import.py" $pl -unattended -nosplash -nop4
$env:UEKIT_NO_SHOTS = "1"   # ue_level solo reconstruye el nivel
Start-Process $ed -ArgumentList "`"$proj`"", '-ExecCmds="py D:/Repos/_arena_work/scripts/ue_level.py"', $pl, $ini -Wait
Remove-Item Env:UEKIT_NO_SHOTS
& $ue $proj -run=pythonscript "-script=$S\ue_bg_import.py" $pl -unattended -nosplash -nop4
$env:UEKIT_SHOTS = "D:\Repos\_arena_work\renders\05_pulido"   # carpeta de capturas
Start-Process $ed -ArgumentList "`"$proj`"", '-ExecCmds="py D:/Repos/_arena_work/scripts/ue_background.py"', $pl, $ini -Wait
Start-Process $ed -ArgumentList "`"$proj`"", '-ExecCmds="py D:/Repos/_arena_work/scripts/ue_pie_test.py"', $pl, $ini -Wait
```

Los pasos en editor usan `-ExecCmds="py …"` (y no `-ExecutePythonScript`, que en 5.8 cierra el editor al
terminar el script); el propio script cierra el editor cuando acaba. Ojo: `ue_level.py` borra y recrea
`L_Arena`, así que después hay que volver a ejecutar `ue_background.py`.

## Convenciones

- Blender: 1 u = 1 m, Z arriba; export FBX con `FBX_SCALE_NONE` (1 m = 100 uu en Unreal).
- Al importar, Unreal refleja el eje Y: una posición de Blender `(x, y, z)` m va a `(100x, -100y, 100z)` cm
  y un giro en Z de θ pasa a −θ (ver `b2u` / `u_loc` en los scripts de nivel).
- Pivotes: pilar en su eje a nivel del agua; arco en el punto medio entre sus pilares; suelo, borde y
  escalones en el centro de la arena; estandarte en su punto de anclaje.
- Vertex color `Wear` en el kit: R = musgo, G = suciedad (los materiales de Unreal lo usan).
- `L_Arena` usa `BP_ArenaGameMode` como override; el mapa por defecto del proyecto no se ha cambiado.

## Pendiente

Límite de juego fuera del círculo (el agua no tiene colisión), agua definitiva (Single Layer Water o
plugin Water), material de partícula para la salpicadura de Niagara y más detalle en roca y árboles.
