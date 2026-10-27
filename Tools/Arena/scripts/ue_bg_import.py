"""Importa el fondo en Unreal: texturas -> /Game/Arena/Background/Textures, materiales -> .../Materials,
mallas SM_BG_* -> .../Meshes (Nanite en las opacas). Reutiliza los ayudantes de ue_import.py.

  UnrealEditor-Cmd.exe DuelingGame.uproject -run=pythonscript -script=ue_bg_import.py -EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities
"""
import os, sys
import unreal

os.environ["UEKIT_NO_MAIN"] = "1"
sys.path.insert(0, r"D:\Repos\_arena_work\scripts")
import ue_import as K

ROOT = "/Game/Arena/Background"
TEX, MAT, MESH = ROOT + "/Textures", ROOT + "/Materials", ROOT + "/Meshes"
ASSETS = K.ASSETS
EAL, AT, MEL = K.EAL, K.AT, K.MEL
MP = unreal.MaterialProperty
log = K.log

TEXTURES = {
    "T_Rock051_C": ("Rock051/Rock051_1K-JPG_Color.jpg", "color"),
    "T_Moss002_C": ("Moss002/Moss002_1K-JPG_Color.jpg", "color"),
    "T_Grass004_C": ("Grass004/Grass004_1K-JPG_Color.jpg", "color"),
    "T_BG_WaterStreak": ("generated/T_BG_WaterStreak.png", "mask"),
    "T_BG_Mist": ("generated/T_BG_Mist.png", "alpha"),
}
MESHES = ["SM_BG_Cliffs", "SM_BG_ShoreRocks", "SM_BG_Trees", "SM_BG_Mountains", "SM_BG_Waterfall", "SM_BG_Foam",
          "SM_BG_Mist", "SM_BG_Tower", "SM_BG_Pavilion", "SM_BG_Bridge", "SM_BG_Island_A", "SM_BG_Island_B",
          "SM_BG_Island_C", "SM_BG_FoamRing"]
TRANSLUCENT = {"SM_BG_Waterfall", "SM_BG_Foam", "SM_BG_Mist", "SM_BG_FoamRing"}


def import_textures():
    tasks = []
    for name, (rel, _) in TEXTURES.items():
        if EAL.does_asset_exist(f"{TEX}/{name}") and os.environ.get("UEKIT_REIMPORT_TEX") != "1":
            continue        # no reimportar: así se conserva la textura ya compilada y no sale el damero al capturar
        t = unreal.AssetImportTask()
        t.filename = os.path.join(ASSETS, rel)
        t.destination_path, t.destination_name = TEX, name
        t.automated, t.replace_existing, t.save = True, True, False
        tasks.append(t)
    AT.import_asset_tasks(tasks)
    out = {}
    for name, (_, kind) in TEXTURES.items():
        tex = EAL.load_asset(f"{TEX}/{name}")
        # todas quedan como textura de color por defecto: así valen los TextureSample con sampler Color
        EAL.save_loaded_asset(tex)
        out[name] = tex
    log("bg textures ok")
    return out


def new_mat(name):
    path = f"{MAT}/{name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    return AT.create_asset(name, MAT, unreal.Material, unreal.MaterialFactoryNew())


def finish(m):
    MEL.layout_material_expressions(m)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    log(f"material {m.get_name()} ok")


def sample(g, name, tex, x):
    """TextureSampleParameter2D: con TextureSample simple la textura no se guardaba desde Python."""
    return g.tex(name, tex, unreal.MaterialSamplerType.SAMPLERTYPE_COLOR, x)


def triplanar(g, tex, size_cm, x=-1600):
    """Muestra una textura proyectada desde los tres ejes en espacio de mundo y mezcla por la normal."""
    wp = g.n(unreal.MaterialExpressionWorldPosition, x)
    p = g.mul(wp, "", const_b=1.0 / size_cm, x=x + 150)
    out = []
    for r, gg, b in ((True, True, False), (True, False, True), (False, True, True)):
        uv = g.n(unreal.MaterialExpressionComponentMask, x + 300, r=r, g=gg, b=b, a=False)
        g.c(p, "", uv, "")
        s = sample(g, f"Tri_{tex.get_name()}_{len(out)}", tex, x + 450)
        g.c(uv, "", s, "UVs")
        out.append(s)
    nrm = g.n(unreal.MaterialExpressionVertexNormalWS, x)
    ab = g.n(unreal.MaterialExpressionAbs, x + 150); g.c(nrm, "", ab, "")
    w = g.mul(g.mul(ab, "", ab, "", x=x + 300), "", g.mul(ab, "", ab, "", x=x + 300), "", x=x + 450)
    tot = g.n(unreal.MaterialExpressionDotProduct, x + 600)
    g.c(w, "", tot, "A"); g.c(g.const3([1, 1, 1]), "", tot, "B")
    wn = g.n(unreal.MaterialExpressionDivide, x + 750); g.c(w, "", wn, "A"); g.c(tot, "", wn, "B")
    sxy, sxz, syz = out
    acc = g.mul(syz, "RGB", wn, "R", x=x + 900)
    acc = g.add(acc, "", g.mul(sxz, "RGB", wn, "G", x=x + 900), "", x=x + 1050)
    acc = g.add(acc, "", g.mul(sxy, "RGB", wn, "B", x=x + 900), "", x=x + 1200)
    return acc, nrm


def build_rock(tex):
    m = new_mat("M_BG_Rock")
    m.set_editor_property("used_with_nanite", True)
    g = K.G(m)
    # UV de la malla (proyección de caja a escala de mundo hecha en Blender): más simple y fiable que el triplanar
    uv = g.n(unreal.MaterialExpressionTextureCoordinate, -1800)
    rock = sample(g, "Rock", tex["T_Rock051_C"], -1400)
    rock = g.mul(rock, "RGB", g.vec_param("RockTint", [0.92, 0.86, 0.78]), "")
    mo = sample(g, "Moss", tex["T_Moss002_C"], -1400)
    g.c(g.mul(uv, "", const_b=2.0), "", mo, "UVs")
    moss = g.mul(mo, "RGB", const_b=1.0)
    nrm = g.n(unreal.MaterialExpressionVertexNormalWS, -1600)
    vc = g.n(unreal.MaterialExpressionVertexColor, -1200)
    nz = g.n(unreal.MaterialExpressionNoise, -1200, scale=0.002, levels=4, output_min=0.0, output_max=1.0)
    mossmask = g.n(unreal.MaterialExpressionSaturate, -300)
    g.c(g.mul(g.add(g.mul(vc, "R", nz, ""), "", const_b=-0.15), "", const_b=3.0), "", mossmask, "")
    base = g.lerp(rock, "", g.mul(moss, "", const_b=0.8), "", mossmask, "")
    # hierba en lo que mira hacia arriba (cornisas, mesetas, lo alto de las islas)
    up = g.n(unreal.MaterialExpressionComponentMask, -1200, r=False, g=False, b=True, a=False)
    g.c(nrm, "", up, "")
    grassmask = g.n(unreal.MaterialExpressionSaturate, -300)
    g.c(g.mul(g.add(g.add(up, "", g.mul(nz, "", const_b=0.25), ""), "", const_b=-0.72), "", const_b=5.0), "", grassmask, "")
    grass = sample(g, "Grass", tex["T_Grass004_C"], -1100)
    g.c(g.mul(uv, "", const_b=1.6), "", grass, "UVs")
    base = g.lerp(base, "", g.mul(grass, "RGB", g.vec_param("GrassTint", [0.85, 0.95, 0.75]), ""), "", grassmask, "")
    g.out(base, MP.MP_BASE_COLOR)
    g.out(g.scalar_param("Roughness", 0.88), MP.MP_ROUGHNESS)
    finish(m)
    return m


def build_simple(name, color, rough=0.85, vary=0.0):
    m = new_mat(name)
    m.set_editor_property("used_with_nanite", True)
    g = K.G(m)
    c = g.vec_param("Color", color)
    if vary:
        vc = g.n(unreal.MaterialExpressionVertexColor, -1200)
        k = g.add(g.mul(vc, "G", const_b=vary), "", const_b=1 - vary / 2)
        c = g.mul(c, "", k, "")
    g.out(c, MP.MP_BASE_COLOR)
    g.out(g.scalar_param("Roughness", rough), MP.MP_ROUGHNESS)
    finish(m)
    return m


def build_mountain():
    m = new_mat("M_BG_Mountain")
    m.set_editor_property("used_with_nanite", True)
    g = K.G(m)
    wp = g.n(unreal.MaterialExpressionWorldPosition, -1500)
    z = g.n(unreal.MaterialExpressionComponentMask, -1300, r=False, g=False, b=True, a=False)
    g.c(wp, "", z, "")
    nrm = g.n(unreal.MaterialExpressionVertexNormalWS, -1500)
    up = g.n(unreal.MaterialExpressionComponentMask, -1300, r=False, g=False, b=True, a=False)
    g.c(nrm, "", up, "")
    snow = g.n(unreal.MaterialExpressionSaturate, -300)
    g.c(g.mul(g.add(g.add(g.mul(z, "", const_b=1 / 40000.0), "", g.mul(up, "", const_b=0.8), ""), "", const_b=-2.3),
              "", const_b=2.5), "", snow, "")
    c = g.lerp(g.vec_param("Rock", K.srgb_lin("#6E6A66")), "", g.vec_param("Snow", K.srgb_lin("#E8E6EE")), "", snow, "")
    g.out(c, MP.MP_BASE_COLOR)
    g.out(g.scalar_param("Roughness", 0.9), MP.MP_ROUGHNESS)
    finish(m)
    return m


def translucent(name):
    m = new_mat(name)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("two_sided", True)
    return m


def build_waterfall(tex):
    m = translucent("M_BG_Waterfall")
    g = K.G(m)
    uv = g.n(unreal.MaterialExpressionTextureCoordinate, -1800)
    t = g.n(unreal.MaterialExpressionTime, -1800)
    speed = g.scalar_param("FallSpeed", 0.55, -1800)
    u = g.n(unreal.MaterialExpressionComponentMask, -1600, r=True, g=False, b=False, a=False); g.c(uv, "", u, "")
    v = g.n(unreal.MaterialExpressionComponentMask, -1600, r=False, g=True, b=False, a=False); g.c(uv, "", v, "")
    pan = g.add(g.mul(v, "", const_b=2.5, x=-1450), "", g.mul(t, "", speed, "", x=-1450), "", x=-1300)
    pan2 = g.add(g.mul(v, "", const_b=1.3, x=-1450), "", g.mul(t, "", g.mul(speed, "", const_b=0.6), "", x=-1450), "", x=-1300)
    uv1 = g.n(unreal.MaterialExpressionAppendVector, -1150)
    g.c(g.mul(u, "", const_b=1.5), "", uv1, "A"); g.c(g.mul(pan, "", const_b=-1.0), "", uv1, "B")
    uv2 = g.n(unreal.MaterialExpressionAppendVector, -1150)
    g.c(g.add(g.mul(u, "", const_b=0.9), "", const_b=0.37), "", uv2, "A"); g.c(g.mul(pan2, "", const_b=-1.0), "", uv2, "B")
    s1 = sample(g, "Tex2", tex["T_BG_WaterStreak"], -1000); g.c(uv1, "", s1, "UVs")
    s2 = sample(g, "Tex3", tex["T_BG_WaterStreak"], -1000); g.c(uv2, "", s2, "UVs")
    streak = g.mul(s1, "R", s2, "R")
    # bordes laterales suaves y un poco más opaco abajo, donde rompe
    edge = g.n(unreal.MaterialExpressionSine, -800)
    g.c(g.mul(u, "", const_b=0.5), "", edge, "")
    edge = g.n(unreal.MaterialExpressionSaturate, -650, )
    sine = g.n(unreal.MaterialExpressionSine, -800)
    g.c(g.mul(u, "", const_b=0.5), "", sine, "")
    g.c(g.mul(sine, "", const_b=1.6), "", edge, "")
    op = g.mul(g.add(g.mul(streak, "", const_b=1.6), "", const_b=0.15), "", edge, "")
    op = g.mul(op, "", g.scalar_param("Opacity", 0.85), "")
    opc = g.n(unreal.MaterialExpressionSaturate, -150); g.c(op, "", opc, "")
    g.out(opc, MP.MP_OPACITY)
    col = g.lerp(g.vec_param("DeepColor", [0.55, 0.68, 0.7]), "", g.vec_param("FoamColor", [1.0, 0.97, 0.93]), "", streak, "")
    g.out(g.mul(col, "", g.scalar_param("Brightness", 1.4), ""), MP.MP_EMISSIVE_COLOR)
    finish(m)
    return m


def build_foam(tex):
    m = translucent("M_BG_Foam")
    g = K.G(m)
    uv = g.n(unreal.MaterialExpressionTextureCoordinate, -1800)
    t = g.n(unreal.MaterialExpressionTime, -1800)
    u = g.n(unreal.MaterialExpressionComponentMask, -1600, r=True, g=False, b=False, a=False); g.c(uv, "", u, "")
    v = g.n(unreal.MaterialExpressionComponentMask, -1600, r=False, g=True, b=False, a=False); g.c(uv, "", v, "")
    p = g.n(unreal.MaterialExpressionAppendVector, -1300)
    g.c(g.add(g.mul(u, "", const_b=6.0), "", g.mul(t, "", const_b=0.02), ""), "", p, "A")
    g.c(g.add(g.mul(v, "", const_b=1.5), "", g.mul(t, "", const_b=-0.25), ""), "", p, "B")
    s = sample(g, "Tex4", tex["T_BG_WaterStreak"], -1100); g.c(p, "", s, "UVs")
    fade = g.add(g.mul(v, "", const_b=-1.0), "", const_b=1.0)
    op = g.n(unreal.MaterialExpressionSaturate, -150)
    g.c(g.mul(g.mul(s, "R", fade, ""), "", g.scalar_param("Opacity", 1.3), ""), "", op, "")
    g.out(op, MP.MP_OPACITY)
    g.out(g.vec_param("Color", [1.2, 1.17, 1.12]), MP.MP_EMISSIVE_COLOR)
    finish(m)
    return m


def build_mist(tex):
    m = translucent("M_BG_Mist")
    g = K.G(m)
    uv = g.n(unreal.MaterialExpressionTextureCoordinate, -1800)
    s = sample(g, "Tex5", tex["T_BG_Mist"], -1200); g.c(uv, "", s, "UVs")
    df = g.n(unreal.MaterialExpressionDepthFade, -600)
    df.set_editor_property("fade_distance_default", 300.0)
    g.c(g.mul(s, "A", g.scalar_param("Opacity", 0.45), ""), "", df, "Opacity")
    g.out(df, MP.MP_OPACITY)
    g.out(g.vec_param("Color", [1.1, 1.05, 1.0]), MP.MP_EMISSIVE_COLOR)
    finish(m)
    return m


def build_water():
    """Agua translúcida iluminada por píxel: depth fade contra el fondo del lago, turquesa claro cerca de la
    plataforma, ondas que se apagan con la distancia y reflejos de Lumen (capa frontal de translucidez)."""
    m = new_mat("M_Arena_Water")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    # niebla por píxel: con niebla por vértice el plano de 6 km (4 vértices lejanos) salía blanco entero
    for k, v in (("screen_space_reflections", True), ("use_translucency_vertex_fog", False)):
        try:
            m.set_editor_property(k, v)
        except Exception as ex:
            log(f"water {k}: {ex}")
    g = K.G(m)
    # profundidad del agua bajo cada píxel (cm)
    sd = g.n(unreal.MaterialExpressionSceneDepth, -1800)
    pd = g.n(unreal.MaterialExpressionPixelDepth, -1800)
    dd = g.n(unreal.MaterialExpressionSubtract, -1650); g.c(sd, "", dd, "A"); g.c(pd, "", dd, "B")
    deep = g.n(unreal.MaterialExpressionSaturate, -1350)
    g.c(g.mul(dd, "", const_b=1 / 450.0), "", deep, "")
    # cercanía a la plataforma (radio en cm desde el origen)
    wp = g.n(unreal.MaterialExpressionWorldPosition, -1800)
    xy = g.n(unreal.MaterialExpressionComponentMask, -1650, r=True, g=True, b=False, a=False); g.c(wp, "", xy, "")
    rad = g.n(unreal.MaterialExpressionLength, -1500); g.c(xy, "", rad, "")
    near = g.n(unreal.MaterialExpressionSaturate, -1200)
    g.c(g.add(g.mul(rad, "", const_b=-1 / 1800.0), "", const_b=1.0 + 1500 / 1800.0), "", near, "")
    shallow_col = g.vec_param("ShallowColor", K.srgb_lin("#5ED3C8"))
    deep_col = g.vec_param("DeepColor", K.srgb_lin("#0D6A6A"))
    col = g.lerp(shallow_col, "", deep_col, "", deep, "")
    col = g.lerp(col, "", shallow_col, "", g.mul(near, "", const_b=0.3), "")
    g.out(col, MP.MP_BASE_COLOR)
    op = g.lerp(g.n(unreal.MaterialExpressionConstant, -900, r=0.45), "", g.n(unreal.MaterialExpressionConstant, -900, r=0.93), "", deep, "")
    g.out(op, MP.MP_OPACITY)
    g.out(g.scalar_param("Roughness", 0.05), MP.MP_ROUGHNESS)
    g.out(g.scalar_param("Specular", 0.5), MP.MP_SPECULAR)
    t = g.n(unreal.MaterialExpressionTime, -1800)
    pan = g.add(wp, "", g.mul(t, "", g.const3([30, 12, 0]), ""), "")
    n1 = g.n(unreal.MaterialExpressionNoise, -1100, scale=0.0016, levels=3, output_min=-1.0, output_max=1.0)
    g.c(pan, "", n1, "Position")
    n2 = g.n(unreal.MaterialExpressionNoise, -1100, scale=0.0019, levels=3, output_min=-1.0, output_max=1.0)
    g.c(g.add(pan, "", g.const3([137, 71, 0]), ""), "", n2, "Position")
    fade = g.n(unreal.MaterialExpressionSaturate, -900)
    g.c(g.add(g.mul(pd, "", const_b=-1 / 6000.0), "", const_b=1.0), "", fade, "")
    amp = g.mul(fade, "", const_b=0.025)
    nxy = g.n(unreal.MaterialExpressionAppendVector, -600)
    g.c(g.mul(n1, "", amp, ""), "", nxy, "A"); g.c(g.mul(n2, "", amp, ""), "", nxy, "B")
    n3 = g.n(unreal.MaterialExpressionAppendVector, -450)
    g.c(nxy, "", n3, "A"); g.c(g.n(unreal.MaterialExpressionConstant, -600, r=1.0), "", n3, "B")
    g.out(n3, MP.MP_NORMAL)
    finish(m)
    return m


def build_clouds():
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(["/Engine/EngineSky"], True)
    parent = unreal.load_asset("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst")
    if not parent:
        log("clouds: no se encontró el material de nubes del motor")
        return None
    for n in ("Cloud_GlobalCoverage", "Cloud_GlobalDensity"):
        log(f"clouds default {n}={MEL.get_material_instance_scalar_parameter_value(parent, n)}")
    mi = K.new_instance("MI_Arena_Clouds", parent, {"Cloud_AlbedoColor": [1.0, 0.86, 0.74]})
    cov = MEL.get_material_instance_scalar_parameter_value(parent, "Cloud_GlobalCoverage")
    den = MEL.get_material_instance_scalar_parameter_value(parent, "Cloud_GlobalDensity")
    # la cobertura por defecto (-0,2) ya deja claros entre nubes; solo se aligera la densidad
    MEL.set_material_instance_scalar_parameter_value(mi, "Cloud_GlobalDensity", den * 0.8)
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    return mi


def build_splash():
    """Salpicadura/bruma en la base de las cascadas: copia de la plantilla FountainLightweight de Niagara."""
    dst = ROOT + "/FX/NS_WaterfallSplash"
    if EAL.does_asset_exist(dst):
        return EAL.load_asset(dst)
    EAL.make_directory(ROOT + "/FX")
    # el commandlet no escanea el contenido de los plugins por defecto
    unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(["/Niagara"], True)
    src = "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight"
    sys_ = EAL.duplicate_asset(src, dst)
    if sys_:
        EAL.save_loaded_asset(sys_)
    log(f"splash system {sys_}")
    return sys_


def main():
    K.MAT_DIR = MAT          # las instancias del fondo van a su carpeta, no a la de la arena
    for d in (TEX, MAT, MESH):
        EAL.make_directory(d)
    tex = import_textures()
    foliage = build_simple("M_BG_Foliage", [0.06, 0.12, 0.04], 0.9, vary=0.5)
    mats = {
        "M_BG_Rock": build_rock(tex),
        "M_BG_Bark": K.new_instance("MI_BG_Bark", foliage, {"Color": K.srgb_lin("#4A3C30")}),
        "M_BG_LeafGreen": K.new_instance("MI_BG_LeafGreen", foliage, {"Color": K.srgb_lin("#4E7A3A")}),
        "M_BG_LeafLilac": K.new_instance("MI_BG_LeafLilac", foliage, {"Color": K.srgb_lin("#B59AD8")}),
        "M_BG_Mountain": build_mountain(),
        "M_BG_Waterfall": build_waterfall(tex),
        "M_BG_Foam": build_foam(tex),
        "M_BG_Mist": build_mist(tex),
        "M_BG_LakeBed": build_simple("M_BG_LakeBed", K.srgb_lin("#3E5A4E"), 0.95),
        "M_Arena_Marble": EAL.load_asset("/Game/Arena/Materials/M_Arena_Marble"),
        "M_Arena_Gold": EAL.load_asset("/Game/Arena/Materials/M_Arena_Gold"),
    }
    K.new_instance("MI_BG_MistBand", mats["M_BG_Mist"])
    MEL.set_material_instance_scalar_parameter_value(EAL.load_asset(MAT + "/MI_BG_MistBand"), "Opacity", 0.11)
    EAL.save_asset(MAT + "/MI_BG_MistBand")
    K.new_instance("MI_BG_FoamRing", mats["M_BG_Foam"])
    MEL.set_material_instance_scalar_parameter_value(EAL.load_asset(MAT + "/MI_BG_FoamRing"), "Opacity", 0.55)
    EAL.save_asset(MAT + "/MI_BG_FoamRing")
    build_water()
    build_clouds()
    build_splash()
    K.MESH_DIR = MESH
    meshes, _ = K.import_meshes(MESHES)
    for name, mesh in meshes.items():
        if name in TRANSLUCENT:
            ns = mesh.get_editor_property("nanite_settings")
            ns.enabled = False                       # Nanite no admite materiales translúcidos
            mesh.set_editor_property("nanite_settings", ns)
        # el bucle devuelve copias de los StaticMaterial: hay que guardar una lista nueva con las copias modificadas
        new_slots = []
        for s in mesh.get_editor_property("static_materials"):
            mm = mats.get(str(s.material_slot_name))
            if mm:
                s.material_interface = mm
            else:
                log(f"  slot sin material: {name}.{s.material_slot_name}")
            new_slots.append(s)
        mesh.set_editor_property("static_materials", new_slots)
        bs = mesh.get_editor_property("body_setup")
        if bs:
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
        EAL.save_loaded_asset(mesh)
        bb = mesh.get_bounding_box()
        sz = bb.max - bb.min
        log(f"bg mesh {name}: size_m=({sz.x / 100:.1f},{sz.y / 100:.1f},{sz.z / 100:.1f}) "
            f"nanite={mesh.get_editor_property('nanite_settings').enabled}")
    # copias antiguas que el ayudante guardó en la carpeta de la arena (ya no las usa ninguna malla)
    for old in ("MI_BG_Bark", "MI_BG_LeafGreen", "MI_BG_LeafLilac", "MI_BG_MistBand", "MI_Arena_Clouds"):
        p = "/Game/Arena/Materials/" + old
        if EAL.does_asset_exist(p):
            EAL.delete_asset(p)
    log("BG IMPORT DONE")


main()
