"""Prueba de juego de L_Arena en el editor (PIE): comprueba que el GameMode del nivel no crea la arena de prueba,
que el jugador aparece sobre el suelo de mármol y frente al rival, y saca una captura con la cámara real del juego.

  UnrealEditor.exe DuelingGame.uproject -ExecCmds="py D:/Repos/_arena_work/scripts/ue_pie_test.py"
"""
import os
import unreal

MAP = "/Game/Arena/Maps/L_Arena"
OUT = os.environ.get("UEKIT_SHOTS", r"D:\Repos\_arena_work\renders\03_unreal")
S = {"tick": 0, "phase": "load", "t0": 0, "handle": None}


def log(m):
    unreal.log_warning("UEKIT " + m)


def game_world():
    try:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    except Exception:
        return unreal.EditorLevelLibrary.get_game_world()


def report(world):
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    if pawn:
        loc = pawn.get_actor_location()
        log(f"PIE pawn={pawn.get_class().get_name()} loc=({loc.x:.0f},{loc.y:.0f},{loc.z:.0f}) yaw={pawn.get_actor_rotation().yaw:.0f}")
    else:
        log("PIE pawn=None")
    for cls_path in ("/Script/DuelingGame.DuelTestArena", "/Script/DuelingGame.DuelTestDummy"):
        cls = unreal.load_class(None, cls_path)
        found = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
        locs = [f"({a.get_actor_location().x:.0f},{a.get_actor_location().y:.0f},{a.get_actor_location().z:.0f})" for a in found]
        log(f"PIE {cls_path.split('.')[-1]} count={len(found)} {' '.join(locs)}")
    gm = unreal.GameplayStatics.get_game_mode(world)
    log(f"PIE gamemode={gm.get_class().get_name() if gm else None}")


def on_tick(dt):
    S["tick"] += 1
    t = S["tick"]
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if S["phase"] == "load" and t > 30:
        les.editor_request_begin_play()
        S["phase"], S["t0"] = "play", t
    elif S["phase"] == "play" and t - S["t0"] > 300:
        world = game_world()
        if world:
            report(world)
        path = os.path.join(OUT, "pie_gameplay.png").replace("\\", "/")
        unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1600x900 filename="{path}"')
        S["phase"], S["t0"] = "shot", t
    elif S["phase"] == "shot" and t - S["t0"] > 120:
        world = game_world()
        if world:
            report(world)                     # segunda lectura: ¿sigue sobre el suelo tras unos segundos?
        les.editor_request_end_play()
        S["phase"], S["t0"] = "end", t
    elif S["phase"] == "end" and t - S["t0"] > 60:
        unreal.unregister_slate_post_tick_callback(S["handle"])
        log("PIE DONE")
        unreal.SystemLibrary.quit_editor()


unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(MAP)
S["handle"] = unreal.register_slate_post_tick_callback(on_tick)
