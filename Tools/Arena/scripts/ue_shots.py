"""Capturas desde el visor del editor: pilota cada CameraActor en vista de juego, espera a que Lumen, las nubes
y la exposición converjan y lanza HighResShot. Al terminar puede cerrar el editor."""
import os
import unreal

WARMUP_TICKS, WRITE_TICKS = 360, 90
_S = {}


def log(m):
    unreal.log_warning("UEKIT " + m)


def _tick(dt):
    s = _S
    s["tick"] += 1
    s["clock"] += dt
    t = s["tick"]
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not s["queue"]:
        if t - s["t0"] >= WRITE_TICKS:
            unreal.unregister_slate_post_tick_callback(s["handle"])
            log("ALL CAPTURES DONE")
            if s["quit"]:
                unreal.SystemLibrary.quit_editor()
        return
    name, cam = s["queue"][0]
    try:
        les.editor_invalidate_viewports()
    except Exception:
        pass
    if s["phase"] is None:
        les.pilot_level_actor(cam)
        les.editor_set_game_view(True)
        s["phase"], s["t0"], s["c0"] = "warm", t, s["clock"]
    elif s["phase"] == "warm" and s["clock"] - s["c0"] >= (s["first_warmup_s"] if s["first"] else s["warmup_s"]):
        s["first"] = False
        path = os.path.join(s["out"], name + ".png").replace("\\", "/")
        unreal.SystemLibrary.execute_console_command(None, f'HighResShot 1600x900 filename="{path}"')
        log(f"CAPTURED {name} -> {path}")
        s["phase"], s["t0"] = "write", t
    elif s["phase"] == "write" and t - s["t0"] >= WRITE_TICKS:
        les.eject_pilot_level_actor()
        s["queue"].pop(0)
        s["phase"], s["t0"] = None, t


def start(queue, out, quit_after=True, warmup=WARMUP_TICKS):
    """queue: lista de (nombre_archivo, CameraActor)."""
    os.makedirs(out, exist_ok=True)
    # si la ventana del editor no está en primer plano, el visor deja de pintar y HighResShot no llega a disparar:
    # se desactiva ese ahorro de CPU solo en memoria (no se guarda en la configuración del usuario)
    try:
        unreal.get_default_object(unreal.EditorPerformanceSettings).set_editor_property(
            "throttle_cpu_when_not_foreground", False)
    except Exception as e:
        log(f"no se pudo quitar el ahorro de CPU en segundo plano: {e}")
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    try:
        les.editor_set_viewport_realtime(True)
    except Exception as e:
        log(f"realtime: {e}")
    # texturas recién importadas se compilan en segundo plano: la primera captura espera mucho más
    for cmd in ("r.Streaming.FullyLoadUsedTextures 1", "r.Streaming.PoolSize 4000"):
        unreal.SystemLibrary.execute_console_command(None, cmd)
    _S.update(tick=0, phase=None, t0=0, queue=list(queue), out=out, quit=quit_after, warmup=warmup,
              first=True, clock=0.0, c0=0.0, warmup_s=5.0,
              first_warmup_s=float(os.environ.get("UEKIT_FIRST_WARMUP", "25")))
    _S["handle"] = unreal.register_slate_post_tick_callback(_tick)
