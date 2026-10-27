"""Importa el kit élfico en Unreal: texturas -> /Game/Arena/Textures, materiales -> /Game/Arena/Materials,
mallas FBX -> /Game/Arena/Meshes (Nanite activado, colisión desde los UCX_).

Uso (desde PowerShell):
  UnrealEditor-Cmd.exe DuelingGame.uproject -run=pythonscript -script=ue_import.py -EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities
"""
import os
import unreal

WORK = r"D:\Repos\_arena_work"
ASSETS = os.path.join(WORK, "assets")
EXPORT = os.path.join(WORK, "export")
TEX_DIR, MAT_DIR, MESH_DIR = "/Game/Arena/Textures", "/Game/Arena/Materials", "/Game/Arena/Meshes"

AT = unreal.AssetToolsHelpers.get_asset_tools()
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary


def log(msg):
    unreal.log_warning("UEKIT " + msg)


def srgb_lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def lc(rgb, a=1.0):
    return unreal.LinearColor(rgb[0], rgb[1], rgb[2], a)


# ---------------------------------------------------------------- texturas
TEXTURES = {
    # nombre del asset: (archivo, tipo)
    "T_Marble014_C": ("Marble014/Marble014_2K-JPG_Color.jpg", "color"),
    "T_Marble014_N": ("Marble014/Marble014_2K-JPG_NormalDX.jpg", "normal"),
    "T_Marble014_R": ("Marble014/Marble014_2K-JPG_Roughness.jpg", "mask"),
    "T_Metal034_C": ("Metal034/Metal034_2K-JPG_Color.jpg", "color"),
    "T_Metal034_N": ("Metal034/Metal034_2K-JPG_NormalDX.jpg", "normal"),
    "T_Metal034_R": ("Metal034/Metal034_2K-JPG_Roughness.jpg", "mask"),
}


def import_textures():
    tasks = []
    for name, (rel, _) in TEXTURES.items():
        t = unreal.AssetImportTask()
        t.filename = os.path.join(ASSETS, rel)
        t.destination_path = TEX_DIR
        t.destination_name = name
        t.automated = True
        t.replace_existing = True
        t.save = False
        tasks.append(t)
    AT.import_asset_tasks(tasks)
    out = {}
    for name, (_, kind) in TEXTURES.items():
        tex = EAL.load_asset(f"{TEX_DIR}/{name}")
        if kind == "normal":
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
            tex.set_editor_property("srgb", False)
        elif kind == "mask":
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
            tex.set_editor_property("srgb", False)
        EAL.save_loaded_asset(tex)
        out[name] = tex
        log(f"texture {name} {tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()} {kind}")
    return out


# ---------------------------------------------------------------- materiales
class G:
    """Ayudante para montar grafos de material con posiciones automáticas."""

    def __init__(self, mat):
        self.m, self.y = mat, 0

    def n(self, cls, x=-600, **props):
        e = MEL.create_material_expression(self.m, cls, x, self.y)
        self.y += 140
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    def c(self, a, a_out, b, b_in):
        MEL.connect_material_expressions(a, a_out, b, b_in)

    def out(self, e, prop, o=""):
        MEL.connect_material_property(e, o, prop)

    def const3(self, rgb, x=-900):
        return self.n(unreal.MaterialExpressionConstant3Vector, x, constant=lc(rgb))

    def scalar_param(self, name, val, x=-900):
        return self.n(unreal.MaterialExpressionScalarParameter, x, parameter_name=name, default_value=val)

    def vec_param(self, name, rgb, x=-900):
        return self.n(unreal.MaterialExpressionVectorParameter, x, parameter_name=name, default_value=lc(rgb))

    def tex(self, name, tex, sampler, x=-1200):
        return self.n(unreal.MaterialExpressionTextureSampleParameter2D, x, parameter_name=name, texture=tex,
                      sampler_type=sampler)

    def lerp(self, a, ao, b, bo, alpha, alo, x=-300):
        e = self.n(unreal.MaterialExpressionLinearInterpolate, x)
        self.c(a, ao, e, "A"); self.c(b, bo, e, "B"); self.c(alpha, alo, e, "Alpha")
        return e

    def mul(self, a, ao, b=None, bo="", const_b=None, x=-300):
        e = self.n(unreal.MaterialExpressionMultiply, x)
        self.c(a, ao, e, "A")
        if b is not None:
            self.c(b, bo, e, "B")
        else:
            e.set_editor_property("const_b", const_b)
        return e

    def add(self, a, ao, b=None, bo="", const_b=None, x=-300):
        e = self.n(unreal.MaterialExpressionAdd, x)
        self.c(a, ao, e, "A")
        if b is not None:
            self.c(b, bo, e, "B")
        else:
            e.set_editor_property("const_b", const_b)
        return e

    def remap(self, a, ao, lo, hi, x=-300):
        """lo + a*(hi-lo)"""
        return self.add(self.mul(a, ao, const_b=hi - lo, x=x), "", const_b=lo, x=x + 150)


def new_material(name):
    path = f"{MAT_DIR}/{name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    m = AT.create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("used_with_nanite", True)
    return m


def finish(m):
    MEL.layout_material_expressions(m)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    log(f"material {m.get_name()} ok")


def wind_offset(g, x=-1500):
    """WPO de viento para el estandarte: oscila según el Y local, crece hacia abajo (V de la UV)."""
    uv = g.n(unreal.MaterialExpressionTextureCoordinate, x)
    v = g.n(unreal.MaterialExpressionComponentMask, x + 150, r=False, g=True, b=False, a=False)
    g.c(uv, "", v, "")
    vv = g.mul(v, "", v, "", x=x + 300)                       # máscara: 0 arriba, 1 en la punta
    t = g.n(unreal.MaterialExpressionTime, x)
    speed = g.scalar_param("WindSpeed", 0.35, x)
    obj = g.n(unreal.MaterialExpressionObjectPositionWS, x)
    seed = g.n(unreal.MaterialExpressionDotProduct, x + 150)
    g.c(obj, "", seed, "A"); g.c(g.const3([0.0013, 0.0017, 0.0]), "", seed, "B")
    ph = g.add(g.mul(t, "", speed, "", x=x + 150), "", seed, "", x=x + 300)
    ph = g.add(ph, "", g.mul(v, "", const_b=0.6, x=x + 300), "", x=x + 450)
    s1 = g.n(unreal.MaterialExpressionSine, x + 600); g.c(ph, "", s1, "")
    ph2 = g.add(g.mul(ph, "", const_b=1.7, x=x + 600), "", const_b=0.3, x=x + 750)
    s2 = g.n(unreal.MaterialExpressionSine, x + 900); g.c(ph2, "", s2, "")
    amp = g.scalar_param("WindStrength", 7.0, x + 600)        # cm en la punta
    wy = g.mul(g.mul(s1, "", amp, "", x=x + 900), "", vv, "", x=x + 1050)
    wx = g.mul(g.mul(s2, "", const_b=1.5, x=x + 1050), "", vv, "", x=x + 1200)
    loc = g.n(unreal.MaterialExpressionAppendVector, x + 1200)
    g.c(wx, "", loc, "A"); g.c(wy, "", loc, "B")
    loc3 = g.n(unreal.MaterialExpressionAppendVector, x + 1350)
    g.c(loc, "", loc3, "A"); g.c(g.n(unreal.MaterialExpressionConstant, x + 1200, r=0.0), "", loc3, "B")
    tr = g.n(unreal.MaterialExpressionTransform, x + 1500,
             transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
             transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    g.c(loc3, "", tr, "")
    return tr


def build_marble(tex):
    m = new_material("M_Arena_Marble")
    g = G(m)
    S = unreal.MaterialSamplerType
    col = g.tex("Color", tex["T_Marble014_C"], S.SAMPLERTYPE_COLOR)
    rough = g.tex("Roughness", tex["T_Marble014_R"], S.SAMPLERTYPE_MASKS)
    nrm = g.tex("Normal", tex["T_Marble014_N"], S.SAMPLERTYPE_NORMAL)
    # vetas más suaves y tono marfil (igual que en Blender)
    soft = g.lerp(col, "RGB", g.const3([0.70, 0.64, 0.55]), "", g.n(unreal.MaterialExpressionConstant, -900, r=0.42), "")
    base = g.mul(soft, "", g.const3([1.18, 1.14, 1.08]), "")
    base = g.mul(base, "", g.vec_param("Tint", [1, 1, 1]), "")
    vc = g.n(unreal.MaterialExpressionVertexColor, -1200)
    noise = g.n(unreal.MaterialExpressionNoise, -1200, scale=0.035, levels=4, output_min=0.0, output_max=1.0,
                quality=1)
    mossraw = g.mul(vc, "R", noise, "")
    moss = g.n(unreal.MaterialExpressionSaturate, -150)
    g.c(g.mul(g.add(mossraw, "", const_b=-0.12), "", const_b=1 / 0.22), "", moss, "")
    mossamt = g.mul(moss, "", g.scalar_param("MossAmount", 1.0), "")
    base = g.lerp(base, "", g.vec_param("MossColor", srgb_lin("#4E6A34")), "", mossamt, "")
    grime = g.lerp(g.const3([1, 1, 1]), "", g.const3([0.62, 0.56, 0.47]), "",
                   g.mul(vc, "G", const_b=0.55), "")
    g.out(g.mul(base, "", grime, ""), unreal.MaterialProperty.MP_BASE_COLOR)
    r = g.remap(rough, "R", 0.32, 0.60)
    r = g.lerp(r, "", g.n(unreal.MaterialExpressionConstant, -900, r=0.9), "", mossamt, "")
    g.out(r, unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(nrm, unreal.MaterialProperty.MP_NORMAL, "RGB")
    finish(m)
    return m


def build_gold(tex):
    m = new_material("M_Arena_Gold")
    g = G(m)
    S = unreal.MaterialSamplerType
    col = g.tex("Color", tex["T_Metal034_C"], S.SAMPLERTYPE_COLOR)
    rough = g.tex("Roughness", tex["T_Metal034_R"], S.SAMPLERTYPE_MASKS)
    nrm = g.tex("Normal", tex["T_Metal034_N"], S.SAMPLERTYPE_NORMAL)
    old = g.lerp(col, "RGB", g.vec_param("OldGold", srgb_lin("#C9A24A")), "",
                 g.n(unreal.MaterialExpressionConstant, -900, r=0.65), "")
    vc = g.n(unreal.MaterialExpressionVertexColor, -1200)
    dirt = g.lerp(g.const3([1, 1, 1]), "", g.const3([0.35, 0.28, 0.16]), "", g.mul(vc, "G", const_b=0.5), "")
    g.out(g.mul(old, "", dirt, ""), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.n(unreal.MaterialExpressionConstant, -300, r=1.0), unreal.MaterialProperty.MP_METALLIC)
    g.out(g.remap(rough, "R", 0.34, 0.55), unreal.MaterialProperty.MP_ROUGHNESS)
    # normal más suave: lerp hacia (0,0,1)
    nrm_soft = g.lerp(nrm, "RGB", g.const3([0, 0, 1]), "", g.n(unreal.MaterialExpressionConstant, -600, r=0.6), "")
    g.out(nrm_soft, unreal.MaterialProperty.MP_NORMAL)
    # viento opcional (para el oro cosido al estandarte, que debe moverse con la tela)
    sw = g.n(unreal.MaterialExpressionStaticSwitchParameter, -150, parameter_name="UseWind", default_value=False)
    g.c(wind_offset(g), "", sw, "True")
    g.c(g.const3([0, 0, 0]), "", sw, "False")
    g.out(sw, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    finish(m)
    return m


def build_banner():
    m = new_material("M_Arena_Banner")
    m.set_editor_property("two_sided", True)
    g = G(m)
    noise = g.n(unreal.MaterialExpressionNoise, -1200, scale=0.08, levels=3, output_min=0.0, output_max=1.0)
    c = g.lerp(g.vec_param("DarkGreen", srgb_lin("#173A2D")), "", g.vec_param("LightGreen", srgb_lin("#2A5E48")), "",
               noise, "")
    g.out(c, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.n(unreal.MaterialExpressionConstant, -300, r=0.85), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(wind_offset(g), unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    finish(m)
    return m


def build_water():
    m = new_material("M_Arena_WaterTemp")
    g = G(m)
    # agua provisional: opaca, casi espejo, color turquesa; ondas suaves con normal de ruido panorámico
    g.out(g.vec_param("WaterColor", srgb_lin("#12807A")), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.scalar_param("Roughness", 0.05), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.scalar_param("Specular", 0.3), unreal.MaterialProperty.MP_SPECULAR)
    pos = g.n(unreal.MaterialExpressionWorldPosition, -1500)
    t = g.n(unreal.MaterialExpressionTime, -1500)
    pan = g.add(pos, "", g.mul(t, "", g.const3([30, 12, 0]), ""), "")
    noise = g.n(unreal.MaterialExpressionNoise, -900, scale=0.0016, levels=3, output_min=-1.0, output_max=1.0)
    g.c(pan, "", noise, "Position")
    noise2 = g.n(unreal.MaterialExpressionNoise, -900, scale=0.0019, levels=3, output_min=-1.0, output_max=1.0)
    g.c(g.add(pan, "", g.const3([137, 71, 0]), ""), "", noise2, "Position")
    # las ondas se apagan con la distancia (evita el ruido de pixel en el horizonte)
    depth = g.n(unreal.MaterialExpressionPixelDepth, -1200)
    fade = g.n(unreal.MaterialExpressionSaturate, -900)
    g.c(g.add(g.mul(depth, "", const_b=-1 / 6000.0), "", const_b=1.0), "", fade, "")
    amp = g.mul(fade, "", const_b=0.02)
    xy = g.n(unreal.MaterialExpressionAppendVector, -300)
    g.c(g.mul(noise, "", amp, ""), "", xy, "A"); g.c(g.mul(noise2, "", amp, ""), "", xy, "B")
    n3 = g.n(unreal.MaterialExpressionAppendVector, -150)
    g.c(xy, "", n3, "A"); g.c(g.n(unreal.MaterialExpressionConstant, -300, r=1.0), "", n3, "B")
    g.out(n3, unreal.MaterialProperty.MP_NORMAL)
    finish(m)
    return m


def new_instance(name, parent, vectors=None, switches=None):
    path = f"{MAT_DIR}/{name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    mi = AT.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    for k, v in (vectors or {}).items():
        MEL.set_material_instance_vector_parameter_value(mi, k, lc(v))
    for k, v in (switches or {}).items():
        MEL.set_material_instance_static_switch_parameter_value(mi, k, v)
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    log(f"instance {name} ok")
    return mi


# ---------------------------------------------------------------- mallas
PIECES = ["SM_Arena_Pillar", "SM_Arena_Arch", "SM_Arena_Floor", "SM_Arena_Rim", "SM_Arena_Step", "SM_Arena_Banner",
          "SM_Arena_PillarOrnament", "SM_Arena_ArchOrnament"]


def import_meshes(pieces=None):
    pieces = pieces or PIECES
    # el importador FBX clásico respeta los UCX_ y las opciones de abajo
    try:
        unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX False")
    except Exception as e:
        log(f"no se pudo desactivar Interchange FBX: {e}")
    tasks = []
    for name in pieces:
        ui = unreal.FbxImportUI()
        ui.set_editor_property("import_mesh", True)
        ui.set_editor_property("import_as_skeletal", False)
        ui.set_editor_property("import_materials", False)
        ui.set_editor_property("import_textures", False)
        ui.set_editor_property("import_animations", False)
        ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
        sm = ui.static_mesh_import_data
        sm.set_editor_property("combine_meshes", True)
        sm.set_editor_property("auto_generate_collision", False)
        sm.set_editor_property("one_convex_hull_per_ucx", True)
        sm.set_editor_property("build_nanite", True)
        sm.set_editor_property("generate_lightmap_u_vs", True)
        sm.set_editor_property("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE)
        sm.set_editor_property("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
        sm.set_editor_property("import_uniform_scale", 1.0)
        sm.set_editor_property("convert_scene", True)
        t = unreal.AssetImportTask()
        t.filename = os.path.join(EXPORT, name + ".fbx")
        t.destination_path = MESH_DIR
        t.destination_name = name
        t.automated = True
        t.replace_existing = True
        t.save = False
        t.options = ui
        tasks.append(t)
    AT.import_asset_tasks(tasks)
    sms = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    meshes = {}
    for name in pieces:
        mesh = EAL.load_asset(f"{MESH_DIR}/{name}")
        if not mesh:
            log(f"MESH MISSING {name}")
            continue
        ns = mesh.get_editor_property("nanite_settings")
        if not ns.enabled:
            ns.enabled = True
            mesh.set_editor_property("nanite_settings", ns)
        meshes[name] = mesh
    return meshes, sms


def assign_and_report(meshes, sms, mats):
    slot_map = {
        "M_Arena_Marble": mats["marble"], "M_Arena_MarbleTrim": mats["trim"], "M_Arena_MarbleJoint": mats["joint"],
        "M_Arena_Gold": mats["gold"], "M_Arena_Banner": mats["banner"],
    }
    for name, mesh in meshes.items():
        slots = mesh.get_editor_property("static_materials")
        new_slots = []
        for s in slots:
            key = str(s.material_slot_name)
            m = slot_map.get(key)
            if name == "SM_Arena_Banner" and key == "M_Arena_Gold":
                m = mats["gold_banner"]
            if m is None:
                log(f"  slot sin material conocido: {name}.{key}")
            else:
                s.material_interface = m
            new_slots.append(s)
        mesh.set_editor_property("static_materials", new_slots)
        # sin UCX: borde y escalones usan la malla como colisión (se pisan); arco y estandarte también,
        # aunque el estandarte se coloca sin colisión en el nivel
        bs = mesh.get_editor_property("body_setup")
        if bs and not len(bs.get_editor_property("agg_geom").get_editor_property("convex_elems")):
            bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
        EAL.save_loaded_asset(mesh)
        bb = mesh.get_bounding_box()
        size = bb.max - bb.min
        try:
            agg = mesh.get_editor_property("body_setup").get_editor_property("agg_geom")
            ncol = f"convex={len(agg.get_editor_property('convex_elems'))} box={len(agg.get_editor_property('box_elems'))}"
        except Exception as e:
            ncol = f"? ({e})"
        ns = mesh.get_editor_property("nanite_settings")
        log(f"mesh {name}: size_cm=({size.x:.0f},{size.y:.0f},{size.z:.0f}) min=({bb.min.x:.0f},{bb.min.y:.0f},{bb.min.z:.0f}) "
            f"nanite={ns.enabled} simple_collision={ncol} slots={[str(s.material_slot_name) for s in new_slots]}")


def main():
    for d in (TEX_DIR, MAT_DIR, MESH_DIR):
        EAL.make_directory(d)
    tex = import_textures()
    marble = build_marble(tex)
    gold = build_gold(tex)
    mats = {
        "marble": marble,
        "trim": new_instance("MI_Arena_MarbleTrim", marble, {"Tint": [1.08, 1.08, 1.06]}),
        "joint": new_instance("MI_Arena_MarbleJoint", marble, {"Tint": [0.62, 0.57, 0.5]}),
        "gold": gold,
        "gold_banner": new_instance("MI_Arena_GoldBanner", gold, switches={"UseWind": True}),
        "banner": build_banner(),
    }
    build_water()
    meshes, sms = import_meshes()
    assign_and_report(meshes, sms, mats)
    log("IMPORT DONE")


# ue_bg_import.py importa este módulo para reutilizar sus ayudantes sin volver a importar el kit
if os.environ.get("UEKIT_NO_MAIN") != "1":
    main()
