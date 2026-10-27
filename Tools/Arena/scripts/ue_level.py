"""Monta el nivel /Game/Arena/Maps/L_Arena con el kit importado y saca capturas con SceneCapture2D.

Necesita el editor completo (los subsistemas de editor no existen en el commandlet):
  UnrealEditor.exe DuelingGame.uproject -ExecutePythonScript="D:/Repos/_arena_work/scripts/ue_level.py" -unattended
El script guarda el nivel, espera unos fotogramas para que Lumen converja, captura y cierra el editor.

Coordenadas: el kit se diseñó en Blender (Z arriba, dextrógiro). Al importar el FBX, Unreal refleja el eje Y,
así que una posición de Blender (x, y, z) en metros va a (100x, -100y, 100z) en cm y un giro en Z de θ pasa a -θ.
"""
import math, os
import unreal

WORK = r"D:\Repos\_arena_work"
OUT = os.path.join(WORK, "renders", "03_unreal")
MAP = "/Game/Arena/Maps/L_Arena"
MESH = "/Game/Arena/Meshes/"
GM_BP = "/Game/Arena/Blueprints/BP_ArenaGameMode"

PILLAR_RING_R = 15.6
PAIR_CENTERS = [45, 135, 225, 315]
PAIR_SPREAD = 20.0
BANNER_Z, BANNER_OFFSET = 5.45, 0.52
FLOOR_TOP_CM = 60.0
SUN_ELEV, SUN_AZIM = 11.0, 62.0          # mismo sol que en Blender (azimut desde +X hacia +Y de Blender)
SPAWN_X = 500.0                          # el GameMode coloca jugador y rival en X = ∓500

EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log_warning("UEKIT " + msg)


def b2u(x, y, z=0.0):
    return unreal.Vector(x * 100.0, -y * 100.0, z * 100.0)


def yaw_b2u(rad):
    return -math.degrees(rad)


def look_rot(src, dst):
    d = unreal.Vector(dst.x - src.x, dst.y - src.y, dst.z - src.z)
    yaw = math.degrees(math.atan2(d.y, d.x))
    pitch = math.degrees(math.atan2(d.z, math.hypot(d.x, d.y)))
    return unreal.Rotator(roll=0.0, pitch=pitch, yaw=yaw)


# ---------------------------------------------------------------- GameMode del nivel
def make_game_mode():
    gm_class = unreal.load_class(None, "/Script/DuelingGame.DuelGameMode")
    if EAL.does_asset_exist(GM_BP):
        bp = EAL.load_asset(GM_BP)
    else:
        f = unreal.BlueprintFactory()
        f.set_editor_property("parent_class", gm_class)
        bp = AT.create_asset("BP_ArenaGameMode", "/Game/Arena/Blueprints", unreal.Blueprint, f)
    gen = unreal.BlueprintEditorLibrary.generated_class(bp)
    cdo = unreal.get_default_object(gen)
    for prop, val in (("spawn_test_arena", False), ("spawn_test_dummy", True),
                      ("player_spawn_location", unreal.Vector(-SPAWN_X, 0, FLOOR_TOP_CM + 100)),
                      ("dummy_spawn_location", unreal.Vector(SPAWN_X, 0, FLOOR_TOP_CM + 100))):
        try:
            cdo.set_editor_property(prop, val)
        except Exception as e:
            log(f"GameMode prop {prop}: {e}")
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)
    log(f"GameMode {GM_BP} spawn_test_arena={cdo.get_editor_property('spawn_test_arena')}")
    return gen


# ---------------------------------------------------------------- nivel
def build_level():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if EAL.does_asset_exist(MAP):
        EAL.delete_asset(MAP)
    les.new_level(MAP)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    # new_level parte de una plantilla con su propio cielo, sol y nubes: se quitan para que solo quede lo nuestro
    removed = []
    for a in eas.get_all_level_actors():
        if not isinstance(a, (unreal.WorldSettings, unreal.Brush)):
            removed.append(a.get_actor_label())
            eas.destroy_actor(a)
    log("TEMPLATE ACTORS REMOVED " + ", ".join(removed))

    def mesh_actor(name, label, loc, yaw=0.0, folder="Arena", collision=True, scale=None):
        sm = EAL.load_asset(MESH + name) if not name.startswith("/") else EAL.load_asset(name)
        a = eas.spawn_actor_from_object(sm, loc, unreal.Rotator(0, 0, yaw))
        a.set_actor_label(label)
        a.set_folder_path(folder)
        if scale:
            a.set_actor_scale3d(scale)
        c = a.static_mesh_component
        c.set_mobility(unreal.ComponentMobility.STATIC)
        if not collision:
            c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        return a

    for n in ("SM_Arena_Floor", "SM_Arena_Rim", "SM_Arena_Step"):
        mesh_actor(n, n.replace("SM_Arena_", "Arena_"), b2u(0, 0, 0))
    for p, c in enumerate(PAIR_CENTERS):
        for s in (-1, 1):
            a = math.radians(c + s * PAIR_SPREAD / 2)
            px, py = math.cos(a) * PILLAR_RING_R, math.sin(a) * PILLAR_RING_R
            tag = f"{p}{'ab'[s > 0]}"
            mesh_actor("SM_Arena_Pillar", f"Pillar_{tag}", b2u(px, py, 0), yaw_b2u(a), "Arena/Pillars")
            # ornamentos sin sombra: los crochets dibujaban dientes de sierra sobre la zona de combate
            o = mesh_actor("SM_Arena_PillarOrnament", f"PillarOrn_{tag}", b2u(px, py, 0), yaw_b2u(a), "Arena/Pillars",
                           collision=False)
            o.static_mesh_component.set_editor_property("cast_shadow", False)
            bx, by = px - math.cos(a) * BANNER_OFFSET, py - math.sin(a) * BANNER_OFFSET
            mesh_actor("SM_Arena_Banner", f"Banner_{tag}", b2u(bx, by, BANNER_Z), yaw_b2u(a - math.pi / 2),
                       "Arena/Banners", collision=False)
        cr = math.radians(c)
        mr = PILLAR_RING_R * math.cos(math.radians(PAIR_SPREAD / 2))
        mesh_actor("SM_Arena_Arch", f"Arch_{p}", b2u(math.cos(cr) * mr, math.sin(cr) * mr, 0),
                   yaw_b2u(cr + math.pi / 2), "Arena/Pillars")
        o = mesh_actor("SM_Arena_ArchOrnament", f"ArchOrn_{p}", b2u(math.cos(cr) * mr, math.sin(cr) * mr, 0),
                       yaw_b2u(cr + math.pi / 2), "Arena/Pillars", collision=False)
        o.static_mesh_component.set_editor_property("cast_shadow", False)

    # agua provisional: plano del motor (100x100 cm) escalado a 2 km
    w = mesh_actor("/Engine/BasicShapes/Plane", "Water_Temp", unreal.Vector(0, 0, 0), 0, "Environment",
                   scale=unreal.Vector(2000, 2000, 1))
    w.static_mesh_component.set_material(0, EAL.load_asset("/Game/Arena/Materials/M_Arena_WaterTemp"))
    w.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    w.static_mesh_component.set_editor_property("cast_shadow", False)

    # luz de atardecer
    e, az = math.radians(SUN_ELEV), math.radians(SUN_AZIM)
    # dirección hacia el sol en Unreal (Y reflejado); la luz apunta en sentido contrario
    sx, sy = math.cos(e) * math.cos(az), -math.cos(e) * math.sin(az)
    sun_rot = unreal.Rotator(roll=0.0, pitch=-SUN_ELEV, yaw=math.degrees(math.atan2(-sy, -sx)))
    sun = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 2000), sun_rot)
    sun.set_actor_label("Sun"); sun.set_folder_path("Lighting")
    lc_ = sun.light_component
    lc_.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc_.set_editor_property("intensity", 9.0)
    lc_.set_editor_property("light_color", unreal.Color(255, 214, 170, 255))
    lc_.set_editor_property("atmosphere_sun_light", True)
    lc_.set_editor_property("light_source_angle", 1.2)
    try:
        lc_.set_editor_property("cast_cloud_shadows", True)
    except Exception:
        pass
    sky = eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
    sky.set_actor_label("SkyAtmosphere"); sky.set_folder_path("Lighting")
    # más aerosol (como el dust 2.5 del cielo de Blender): horizonte melocotón y halo cálido alrededor del sol
    skc = sky.get_component_by_class(unreal.SkyAtmosphereComponent)
    for k, v in (("mie_scattering_scale", 0.011), ("mie_anisotropy", 0.82), ("mie_exponential_distribution", 1.6),
                 ("rayleigh_exponential_distribution", 9.0), ("multi_scattering_factor", 1.0)):
        try:
            skc.set_editor_property(k, v)
        except Exception as ex:
            log(f"sky {k}: {ex}")
    sl = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
    sl.set_actor_label("SkyLight"); sl.set_folder_path("Lighting")
    slc = sl.light_component
    slc.set_mobility(unreal.ComponentMobility.MOVABLE)
    slc.set_editor_property("real_time_capture", True)
    slc.set_editor_property("intensity", 1.0)
    fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
    fog.set_actor_label("HeightFog"); fog.set_folder_path("Lighting")
    fc = fog.component
    for k, v in (("fog_density", 0.02), ("fog_height_falloff", 0.1), ("enable_volumetric_fog", True),
                 ("volumetric_fog_scattering_distribution", 0.7), ("volumetric_fog_extinction_scale", 0.6),
                 ("start_distance", 1500.0), ("directional_inscattering_exponent", 6.0),
                 ("directional_inscattering_start_distance", 3000.0)):
        try:
            fc.set_editor_property(k, v)
        except Exception as ex:
            log(f"fog {k}: {ex}")
    for k, v in (("fog_inscattering_luminance", unreal.LinearColor(0.55, 0.42, 0.33, 1)),
                 ("fog_inscattering_color", unreal.LinearColor(0.55, 0.42, 0.33, 1)),
                 ("directional_inscattering_luminance", unreal.LinearColor(1.0, 0.62, 0.35, 1)),
                 ("directional_inscattering_color", unreal.LinearColor(1.0, 0.62, 0.35, 1))):
        try:
            fc.set_editor_property(k, v)
        except Exception:
            pass
    ppv = eas.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    ppv.set_actor_label("PostProcess_Global"); ppv.set_folder_path("Lighting")
    ppv.set_editor_property("unbound", True)
    pps = ppv.get_editor_property("settings")
    for k, v in (("override_auto_exposure_bias", True), ("auto_exposure_bias", 0.6),
                 ("override_bloom_intensity", True), ("bloom_intensity", 0.5),
                 ("override_vignette_intensity", True), ("vignette_intensity", 0.25),
                 ("override_dynamic_global_illumination_method", True),
                 ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
                 ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.LUMEN)):
        try:
            pps.set_editor_property(k, v)
        except Exception as ex:
            log(f"pp {k}: {ex}")
    ppv.set_editor_property("settings", pps)

    # PlayerStart enfrentados a ±5 m (coinciden con PlayerSpawnLocation / DummySpawnLocation del GameMode)
    for i, x in enumerate((-SPAWN_X, SPAWN_X)):
        ps = eas.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(x, 0, FLOOR_TOP_CM + 100),
                                        unreal.Rotator(0, 0, 0 if x < 0 else 180))
        ps.set_actor_label(f"PlayerStart_P{i + 1}"); ps.set_folder_path("Gameplay")

    # cámaras de referencia (las mismas de las capturas)
    cams = {}
    hero_loc, hero_tgt = b2u(-3.0, -12.5, 0.6 + 1.7), b2u(3, 40, 8)
    game_loc = unreal.Vector(-SPAWN_X - 350, 0, FLOOR_TOP_CM + 90 + 160)
    game_tgt = unreal.Vector(SPAWN_X, 0, FLOOR_TOP_CM + 120)
    for name, loc, tgt, fov in (("Cam_Hero", hero_loc, hero_tgt, 82.0), ("Cam_Gameplay", game_loc, game_tgt, 90.0)):
        ca = eas.spawn_actor_from_class(unreal.CameraActor, loc, look_rot(loc, tgt))
        ca.set_actor_label(name); ca.set_folder_path("Cameras")
        ca.camera_component.set_editor_property("field_of_view", fov)
        ca.camera_component.set_editor_property("aspect_ratio", 16 / 9)
        cams[name] = ca

    ws = world.get_world_settings()
    ws.set_editor_property("default_game_mode", make_game_mode())
    les.save_current_level()
    log(f"LEVEL SAVED {MAP} sun_rot={sun_rot}")
    return world, cams


# ---------------------------------------------------------------- capturas
# Se usa el propio visor del editor (pilotando cada CameraActor, en vista de juego) y HighResShot: así salen
# Lumen, sombras virtuales y exposición igual que en el editor. SceneCapture2D daba sombras rotas.
STATE = {"tick": 0, "queue": None, "handle": None, "phase": None, "t0": 0}
WARMUP_TICKS, WRITE_TICKS = 240, 90


def on_tick(dt):
    s = STATE
    s["tick"] += 1
    t = s["tick"]
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not s["queue"]:
        if t - s["t0"] >= WRITE_TICKS:
            unreal.unregister_slate_post_tick_callback(s["handle"])
            log("ALL CAPTURES DONE")
            unreal.SystemLibrary.quit_editor()
        return
    name, cam = s["queue"][0]
    if s["phase"] is None:
        les.pilot_level_actor(cam)
        les.editor_set_game_view(True)
        s["phase"], s["t0"] = "warm", t
    elif s["phase"] == "warm" and t - s["t0"] >= WARMUP_TICKS:
        path = os.path.join(OUT, name + ".png").replace("\\", "/")
        unreal.SystemLibrary.execute_console_command(None, f'HighResShot 1600x900 filename="{path}"')
        log(f"CAPTURED {name} -> {path}")
        s["phase"], s["t0"] = "write", t
    elif s["phase"] == "write" and t - s["t0"] >= WRITE_TICKS:
        les.eject_pilot_level_actor()
        s["queue"].pop(0)
        s["phase"], s["t0"] = None, t


def main():
    os.makedirs(OUT, exist_ok=True)
    world, cams = build_level()
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    log("ACTORS " + ", ".join(sorted(f"{a.get_actor_label()}<{a.get_class().get_name()}>" for a in eas.get_all_level_actors())))
    if os.environ.get("UEKIT_NO_SHOTS") == "1":       # solo reconstruir el nivel (ue_background añade el fondo después)
        unreal.SystemLibrary.quit_editor()
        return
    unreal.SystemLibrary.execute_console_command(None, "r.ScreenPercentage 100")
    STATE["queue"] = [("cam_hero", cams["Cam_Hero"]), ("cam_gameplay", cams["Cam_Gameplay"])]
    STATE["handle"] = unreal.register_slate_post_tick_callback(on_tick)


main()
