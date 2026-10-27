"""Coloca el fondo por capas en L_Arena según bg_layout.json (generado por bg_build.py), añade nubes
volumétricas, ajusta sol y niebla para la perspectiva atmosférica, guarda el nivel y saca capturas.

  UnrealEditor.exe DuelingGame.uproject -ExecCmds="py D:/Repos/_arena_work/scripts/ue_background.py"

Conversión Blender -> Unreal: (x, y, z) m -> (100x, -100y, 100z) cm; giro en Z θ -> -θ.
Los actores del fondo van en la carpeta "Background" del outliner y se recrean en cada ejecución.
"""
import json, math, os, sys
import unreal

sys.path.insert(0, r"D:\Repos\_arena_work\scripts")
import ue_shots

WORK = r"D:\Repos\_arena_work"
MAP = "/Game/Arena/Maps/L_Arena"
BGM = "/Game/Arena/Background/Meshes/"
OUT = os.environ.get("UEKIT_SHOTS", os.path.join(WORK, "renders", "04_fondo"))
SUN_ELEV = 16.0          # algo más alto que en el blockout: sombras de los chapiteles más cortas sobre el suelo
log = ue_shots.log
EAL = unreal.EditorAssetLibrary


def u_loc(p):
    return unreal.Vector(p[0] * 100.0, -p[1] * 100.0, p[2] * 100.0)


def main():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    les.load_level(MAP)
    with open(os.path.join(WORK, "bg_layout.json"), encoding="utf-8") as f:
        L = json.load(f)

    # limpiar una ejecución anterior
    for a in eas.get_all_level_actors():
        if str(a.get_folder_path()).startswith("Background") or a.get_actor_label() in ("Clouds", "Cam_Overview", "FillLight"):
            eas.destroy_actor(a)

    meshes = {}

    def place(mesh, loc, yaw_b, scale, label, folder):
        sm = meshes.get(mesh) or EAL.load_asset(BGM + mesh)
        meshes[mesh] = sm
        a = eas.spawn_actor_from_object(sm, loc, unreal.Rotator(0, 0, -yaw_b))
        a.set_actor_label(label)
        a.set_folder_path(folder)
        a.set_actor_scale3d(unreal.Vector(*scale))
        c = a.static_mesh_component
        c.set_mobility(unreal.ComponentMobility.STATIC)
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        return a

    count = 0
    for i, s in enumerate(L["static"]):
        folder = "Background/Buildings" if s["mesh"] in ("SM_BG_Tower", "SM_BG_Pavilion", "SM_BG_Bridge") else "Background"
        place(s["mesh"], u_loc(s["loc"]), s["yaw"], s["scale"], f"BG_{s['mesh'][6:]}_{i}", folder)
        count += 1

    def waterfall(name, loc, yaw, width, height, throw, base=None):
        place("SM_BG_Waterfall", u_loc(loc), yaw, (width, throw, height), name, "Background/Waterfalls")
        if base:
            b = u_loc(base)
            place("SM_BG_Foam", b, yaw, (width * 0.9, width * 0.9, 1.0), name + "_Foam", "Background/Waterfalls")
            for k, (sc, dz) in enumerate(((1.8, 0.0), (1.2, height * 0.12))):
                m = place("SM_BG_Mist", unreal.Vector(b.x, b.y, b.z + dz * 100), yaw + 30 * k,
                          (width * sc, width * sc, max(8.0, height * 0.35)), f"{name}_Mist{k}", "Background/Waterfalls")
                m.static_mesh_component.set_editor_property("cast_shadow", False)

    for w in L["waterfalls"]:
        waterfall(w["name"], w["loc"], w["yaw"], w["width"], w["height"], w["throw"], w["base"])
        count += 1
    # bandas de bruma al pie de los acantilados (más tenues que la bruma de las cascadas)
    band = EAL.load_asset("/Game/Arena/Background/Materials/MI_BG_MistBand")
    for i, mst in enumerate(L.get("mists", [])):
        a = place("SM_BG_Mist", u_loc(mst["loc"]), mst["yaw"], mst["scale"], f"BG_MistBand_{i}", "Background/Mist")
        a.static_mesh_component.set_material(0, band)
        a.static_mesh_component.set_editor_property("cast_shadow", False)
    # espuma del contacto con la plataforma más tenue (instancia propia)
    ring_mi = EAL.load_asset("/Game/Arena/Background/Materials/MI_BG_FoamRing")
    for a in eas.get_all_level_actors():
        if a.get_actor_label().startswith("BG_FoamRing") and ring_mi:
            a.static_mesh_component.set_material(0, ring_mi)
            a.static_mesh_component.set_editor_property("cast_shadow", False)
    # salpicadura animada (Niagara) en la base de las cascadas más visibles
    splash = EAL.load_asset("/Game/Arena/Background/FX/NS_WaterfallSplash")
    if splash:
        for w in L["waterfalls"]:
            if w["width"] >= 14:
                b = u_loc(w["base"])
                n = eas.spawn_actor_from_object(splash, unreal.Vector(b.x, b.y, 50.0))
                n.set_actor_label(w["name"] + "_Splash"); n.set_folder_path("Background/Waterfalls")
                n.set_actor_scale3d(unreal.Vector(w["width"] * 0.6, w["width"] * 0.6, w["width"] * 0.5))
    for i, isl in enumerate(L["islands"]):
        place(isl["mesh"], u_loc(isl["loc"]), isl["yaw"], isl["scale"], f"BG_Island_{i}", "Background/Islands")
        for j, b in enumerate(isl["buildings"]):
            place(b["mesh"], u_loc(b["loc"]), b["yaw"], b["scale"], f"BG_Island_{i}_{b['mesh'][6:]}_{j}", "Background/Islands")
        th = isl["thread"]
        waterfall(f"BG_Island_{i}_Thread", th["loc"], th["yaw"], th["width"], th["height"], 1.0)
        count += 1
    for a in eas.get_all_level_actors():
        if str(a.get_folder_path()).startswith("Background/Waterfalls") and "Waterfall" in a.get_actor_label() or "Thread" in a.get_actor_label():
            try:
                a.static_mesh_component.set_editor_property("cast_shadow", False)
            except Exception:
                pass

    # cielo: nubes volumétricas de atardecer
    clouds = eas.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0))
    clouds.set_actor_label("Clouds"); clouds.set_folder_path("Lighting")
    cc = clouds.get_component_by_class(unreal.VolumetricCloudComponent)
    # capa de nubes por defecto del motor (la de la plantilla se veía bien); solo se asegura el material
    if not cc.get_editor_property("material"):
        mat = EAL.load_asset("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst")
        if mat:
            cc.set_editor_property("material", mat)
    cmi = EAL.load_asset("/Game/Arena/Background/Materials/MI_Arena_Clouds")
    if cmi:
        cc.set_editor_property("material", cmi)                  # cobertura parcial y tono cálido
    try:
        cc.set_editor_property("layer_bottom_altitude", 6.0)     # base alta (km)
    except Exception as ex:
        log(f"clouds altitude: {ex}")
    log(f"clouds material={cc.get_editor_property('material')}")

    # relleno frontal suave (sin sombras) para que los arcos a contraluz no queden como siluetas negras
    hero = next(a for a in eas.get_all_level_actors() if a.get_actor_label() == "Cam_Hero")
    fill = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1500),
                                      unreal.Rotator(roll=0.0, pitch=-22.0, yaw=hero.get_actor_rotation().yaw))
    fill.set_actor_label("FillLight"); fill.set_folder_path("Lighting")
    flc = fill.light_component
    flc.set_mobility(unreal.ComponentMobility.MOVABLE)
    for k, v in (("intensity", 1.6), ("cast_shadows", False), ("atmosphere_sun_light", False),
                 ("light_color", unreal.Color(205, 220, 255, 255)), ("affect_global_illumination", False)):
        try:
            flc.set_editor_property(k, v)
        except Exception as ex:
            log(f"fill {k}: {ex}")

    # sol algo más alto y penumbra más suave; niebla de altura más presente para separar las capas
    for a in eas.get_all_level_actors():
        lab = a.get_actor_label()
        if lab == "Sun":
            r = a.get_actor_rotation()
            a.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-SUN_ELEV, yaw=r.yaw), False)
            a.light_component.set_editor_property("light_source_angle", 3.0)
            a.light_component.set_editor_property("intensity", 9.5)
            try:
                a.light_component.set_editor_property("cast_cloud_shadows", True)
            except Exception:
                pass
        elif lab == "HeightFog":
            fc = a.component
            # la niebla se pega al lago (caída alta) y empieza lejos: la arena queda limpia y el fondo se aclara
            for k, v in (("fog_density", 0.012), ("fog_height_falloff", 0.09), ("start_distance", 4000.0),
                         ("fog_max_opacity", 0.85), ("volumetric_fog_distance", 60000.0),
                         ("volumetric_fog_scattering_distribution", 0.75), ("volumetric_fog_extinction_scale", 0.5),
                         ("fog_inscattering_luminance", unreal.LinearColor(0.62, 0.5, 0.42, 1)),
                         ("directional_inscattering_luminance", unreal.LinearColor(1.0, 0.6, 0.32, 1)),
                         ("directional_inscattering_start_distance", 5000.0), ("directional_inscattering_exponent", 5.0)):
                try:
                    fc.set_editor_property(k, v)
                except Exception as ex:
                    log(f"fog {k}: {ex}")
        elif lab == "SkyLight":
            a.light_component.set_editor_property("intensity", 1.6)       # más relleno: la arena a contraluz no se hunde
        elif lab == "PostProcess_Global":
            pps = a.get_editor_property("settings")
            pps.set_editor_property("override_auto_exposure_bias", True)
            pps.set_editor_property("auto_exposure_bias", 1.0)
            a.set_editor_property("settings", pps)
        elif lab == "Water_Temp":
            a.set_actor_scale3d(unreal.Vector(6000, 6000, 1))   # 6 km: llega hasta el pie de las montañas
            a.static_mesh_component.set_material(0, EAL.load_asset("/Game/Arena/Background/Materials/M_Arena_Water"))
        elif lab == "SkyAtmosphere":
            skc = a.get_component_by_class(unreal.SkyAtmosphereComponent)
            skc.set_editor_property("mie_scattering_scale", 0.007)        # menos halo blanco junto al sol

    # disco solar más tenue: el cielo junto al sol no debe ser lo más brillante del plano héroe
    for a in eas.get_all_level_actors():
        if a.get_actor_label() == "Sun":
            try:
                a.light_component.set_editor_property("atmosphere_sun_disk_color_scale", unreal.LinearColor(0.25, 0.22, 0.2, 1))
            except Exception as ex:
                log(f"sun disk: {ex}")
        elif a.get_actor_label() == "PostProcess_Global":
            pps = a.get_editor_property("settings")
            pps.set_editor_property("override_lumen_front_layer_translucency_reflections", True)
            pps.set_editor_property("lumen_front_layer_translucency_reflections", True)
            a.set_editor_property("settings", pps)
    # fondo del lago a 5 m: da profundidad al agua translúcida (somera junto a los escalones)
    bed = place_engine_plane = eas.spawn_actor_from_object(EAL.load_asset("/Engine/BasicShapes/Plane"),
                                                           unreal.Vector(0, 0, -500))
    bed.set_actor_label("BG_LakeBed"); bed.set_folder_path("Background")
    bed.set_actor_scale3d(unreal.Vector(6000, 6000, 1))
    bed.static_mesh_component.set_material(0, EAL.load_asset("/Game/Arena/Background/Materials/M_BG_LakeBed"))
    bed.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)

    # vista general alta
    src, dst = u_loc((70, -150, 85)), u_loc((-10, 110, 30))
    d = unreal.Vector(dst.x - src.x, dst.y - src.y, dst.z - src.z)
    rot = unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))), yaw=math.degrees(math.atan2(d.y, d.x)))
    ov = eas.spawn_actor_from_class(unreal.CameraActor, src, rot)
    ov.set_actor_label("Cam_Overview"); ov.set_folder_path("Cameras")
    ov.camera_component.set_editor_property("field_of_view", 70.0)

    for a in eas.get_all_level_actors():
        if a.get_actor_label().startswith("BG_Cliffs"):
            c = a.static_mesh_component
            sm = c.static_mesh
            log(f"DIAG cliffs comp_mat={c.get_material(0).get_path_name() if c.get_material(0) else None} "
                f"mesh_mat={sm.get_material(0).get_path_name() if sm.get_material(0) else None} "
                f"nanite={sm.get_editor_property('nanite_settings').enabled} slots={c.get_num_materials()}")
    les.save_current_level()
    log(f"BACKGROUND PLACED {count} groups; level saved")
    cams = {a.get_actor_label(): a for a in eas.get_all_level_actors() if isinstance(a, unreal.CameraActor)}
    ue_shots.start([("cam_hero", cams["Cam_Hero"]), ("cam_gameplay", cams["Cam_Gameplay"]),
                    ("cam_overview", cams["Cam_Overview"])], OUT)


main()
