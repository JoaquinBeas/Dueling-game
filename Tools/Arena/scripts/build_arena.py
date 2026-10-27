"""Construye la Arena del Lago Ã‰lfico desde cero y guarda arena.blend.

Uso:
  blender -b --factory-startup --python build_arena.py -- [--render cam_hero,cam_top] [--out DIR] [--samples N]

1 u = 1 m, Z arriba, origen en el centro de la arena.
"""
import bpy, bmesh, math, random, sys, os, time
from mathutils import Vector, noise

# ---------------------------------------------------------------- constantes
WORK = r"D:\Repos\_arena_work"
BLEND_PATH = os.path.join(WORK, "arena.blend")

ARENA_R = 14.0          # radio de la plataforma
PLAY_R = 13.0           # radio jugable (nada dentro salvo el suelo)
ARENA_TOP = 0.6         # altura del suelo sobre el agua
STEP_W = 0.6            # huella de cada escalÃ³n
STEP_TOPS = [0.4, 0.2]  # alturas de los escalones que bajan al agua
INLAY_RADII = [3.0, 8.0, 12.0]
INLAY_W = 0.14

PILLAR_R = 15.6         # radio del anillo de pilares
PILLAR_SIZE = 1.0
PILLAR_H = 10.0
PAIR_CENTERS = [45, 135, 225, 315]   # grados, desde +X
PAIR_SPREAD = 20.0      # separaciÃ³n angular entre los dos pilares de un par
ARCH_SPRING = 6.4       # altura de arranque del arco

LAKE_SIZE = 1400.0
VALLEY_R0 = 170.0       # radio medio del pie de los acantilados
MOUNT_R = (1500.0, 3500.0)

SUN_ELEV = 11.0         # grados
GAP_SIGMA = 20.0        # grados: apertura del valle hacia el sol (el sol entra por ahí)
SUN_AZIM = 62.0         # grados desde +X (la cÃ¡mara hÃ©roe mira a +Y; el sol entra por la derecha y detrÃ¡s)

SPAWNS = [Vector((0, -5, ARENA_TOP)), Vector((0, 5, ARENA_TOP))]

PALETTE = {
    "marble": "#E9E1D0", "marble_shadow": "#B9AE98", "gold": "#C9A24A",
    "banner": "#1F4A3A", "water": "#3FB8B0", "water_deep": "#0E5A5E",
    "lilac": "#B59AD8", "leaf": "#4E7A3A", "rock": "#8C8577",
    "mountain": "#7A86A0", "peach": "#F6C9A0", "sky": "#8DB7E0",
    "white_water": "#F4F7F8", "bark": "#5A4A3C", "p1": "#3D6FD1", "p2": "#C8403A",
}
FOG_COLOR = "#F2D2B4"
FOG_DENSITY = 1.0 / 900.0   # 1/m
FOG_HEIGHT = 260.0          # m, caÃ­da en altura

random.seed(7)


# ---------------------------------------------------------------- utilidades
def hex_rgb(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, a)


def collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def mesh_object(name, verts, faces, col, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def from_bmesh(name, bm, col, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def cylinder_bm(r1, r2, h, segs=24, z0=0.0, bm=None, offset=Vector()):
    bm = bm or bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1, radius2=r2, depth=h,
                          matrix=__import__("mathutils").Matrix.Translation(offset + Vector((0, 0, z0 + h / 2))))
    return bm


def box_bm(sx, sy, sz, center, bm=None):
    from mathutils import Matrix
    bm = bm or bmesh.new()
    m = Matrix.Translation(center) @ Matrix.Diagonal((sx, sy, sz, 1))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return bm


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------- materiales
def fog_group():
    """Perspectiva atmosfÃ©rica: mezcla el shader con una emisiÃ³n de color niebla segÃºn distancia y altura."""
    if "AtmoFog" in bpy.data.node_groups:
        return bpy.data.node_groups["AtmoFog"]
    g = bpy.data.node_groups.new("AtmoFog", "ShaderNodeTree")
    g.interface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    g.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    n, l = g.nodes, g.links
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    cam = n.new("ShaderNodeCameraData")
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["Position"], sep.inputs[0])
    # densidad efectiva = D * exp(-max(z,0)/H)
    zc = n.new("ShaderNodeMath"); zc.operation = "MAXIMUM"; zc.inputs[1].default_value = 0.0
    l.new(sep.outputs["Z"], zc.inputs[0])
    zh = n.new("ShaderNodeMath"); zh.operation = "DIVIDE"; zh.inputs[1].default_value = -FOG_HEIGHT
    l.new(zc.outputs[0], zh.inputs[0])
    ez = n.new("ShaderNodeMath"); ez.operation = "EXPONENT"
    l.new(zh.outputs[0], ez.inputs[0])
    dd = n.new("ShaderNodeMath"); dd.operation = "MULTIPLY"; dd.inputs[1].default_value = -FOG_DENSITY
    l.new(cam.outputs["View Distance"], dd.inputs[0])
    m2 = n.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
    l.new(dd.outputs[0], m2.inputs[0]); l.new(ez.outputs[0], m2.inputs[1])
    ex = n.new("ShaderNodeMath"); ex.operation = "EXPONENT"
    l.new(m2.outputs[0], ex.inputs[0])
    inv = n.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    l.new(ex.outputs[0], inv.inputs[1])
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgb(FOG_COLOR)
    em.inputs["Strength"].default_value = 1.0
    em.name = "FogEmission"
    mix = n.new("ShaderNodeMixShader")
    l.new(inv.outputs[0], mix.inputs[0])
    l.new(gi.outputs[0], mix.inputs[1])
    l.new(em.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], go.inputs[0])
    return g


def make_mat(name, color, rough=0.5, metal=0.0, emit=0.0, alpha=1.0, fog=True, ior=1.45, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    out = nt.nodes["Material Output"]
    bsdf.inputs["Base Color"].default_value = hex_rgb(color)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["IOR"].default_value = ior
    if emit > 0:
        bsdf.inputs["Emission Color"].default_value = hex_rgb(color)
        bsdf.inputs["Emission Strength"].default_value = emit
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"
    if fog:
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = fog_group()
        nt.links.new(bsdf.outputs[0], grp.inputs[0])
        nt.links.new(grp.outputs[0], out.inputs["Surface"])
    m.diffuse_color = hex_rgb(color)
    return m


MATS = {}


def build_materials():
    P = PALETTE
    MATS["marble"] = make_mat("M_Marble", P["marble"], rough=0.32)
    MATS["marble_shadow"] = make_mat("M_MarbleShadow", P["marble_shadow"], rough=0.45)
    MATS["gold"] = make_mat("M_Gold", P["gold"], rough=0.22, metal=1.0)
    MATS["banner"] = make_mat("M_Banner", P["banner"], rough=0.8)
    MATS["water"] = make_mat("M_Water", "#2A9C98", rough=0.05, ior=1.33)
    MATS["lilac"] = make_mat("M_Lilac", P["lilac"], rough=0.8)
    MATS["leaf"] = make_mat("M_Leaf", P["leaf"], rough=0.8)
    MATS["rock"] = make_mat("M_Rock", P["rock"], rough=0.9)
    MATS["mountain"] = make_mat("M_Mountain", P["mountain"], rough=0.9)
    MATS["falls"] = make_mat("M_Waterfall", P["white_water"], rough=0.3, emit=0.15)
    MATS["bark"] = make_mat("M_Bark", P["bark"], rough=0.9)
    MATS["p1"] = make_mat("M_Player1", P["p1"], rough=0.5, fog=False)
    MATS["p2"] = make_mat("M_Player2", P["p2"], rough=0.5, fog=False)
    # agua: pequeÃ±as ondas por bump
    nt = MATS["water"].node_tree
    tex = nt.nodes.new("ShaderNodeTexNoise"); tex.inputs["Scale"].default_value = 0.6
    tex.inputs["Detail"].default_value = 6.0
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1, 3, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Object"], mp.inputs[0]); nt.links.new(mp.outputs[0], tex.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.08
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], nt.nodes["Principled BSDF"].inputs["Normal"])


# ---------------------------------------------------------------- secciones
def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    ee = sc.eevee
    for attr, val in [("taa_render_samples", 64), ("use_raytracing", True), ("use_shadows", True),
                      ("shadow_ray_count", 2), ("shadow_step_count", 8), ("use_gtao", True),
                      ("fast_gi_distance", 30.0)]:
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    vs = sc.view_settings
    try:
        vs.view_transform = "AgX"
        vs.look = "AgX - Punchy"
    except TypeError:
        pass
    vs.exposure = 0.0


def build_arena():
    col = collection("Arena")
    # plataforma principal
    bm = cylinder_bm(ARENA_R, ARENA_R, ARENA_TOP + 2.0, segs=128, z0=-2.0)
    from_bmesh("Arena_Platform", bm, col, MATS["marble"])
    # escalones hacia el agua
    for i, top in enumerate(STEP_TOPS):
        r = ARENA_R + STEP_W * (i + 1)
        bm = cylinder_bm(r, r, top + 2.0, segs=128, z0=-2.0)
        from_bmesh(f"Arena_Step_{i}", bm, col, MATS["marble_shadow"] if i % 2 else MATS["marble"])
    # labio: banda perimetral mÃ¡s oscura (a ras de suelo, sin escalÃ³n que tropiece)
    lip = annulus("Arena_Lip", PLAY_R + 0.35, ARENA_R, ARENA_TOP + 0.004, col, MATS["marble_shadow"])
    # incrustaciones doradas
    z = ARENA_TOP + 0.006
    for r in INLAY_RADII:
        annulus(f"Inlay_Ring_{r:g}", r - INLAY_W / 2, r + INLAY_W / 2, z, col, MATS["gold"])
    annulus("Inlay_Ring_Edge", PLAY_R + 0.25, PLAY_R + 0.35, z, col, MATS["gold"])
    # radiales entre 3 y 12 m (16), las principales llegan al centro
    bm = bmesh.new()
    for k in range(16):
        a = math.radians(k * 22.5)
        r0 = INLAY_RADII[0] if k % 2 else 0.6
        r1 = INLAY_RADII[2] if k % 2 else PLAY_R + 0.3
        mid = (r0 + r1) / 2
        from mathutils import Matrix
        m = Matrix.Translation((math.cos(a) * mid, math.sin(a) * mid, z)) @ Matrix.Rotation(a, 4, "Z") \
            @ Matrix.Diagonal((r1 - r0, INLAY_W * 0.8, 0.004, 1))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    from_bmesh("Inlay_Radials", bm, col, MATS["gold"])
    # rombo central
    annulus("Inlay_Center", 0.0, 0.6, z, col, MATS["gold"], segs=8)


def annulus(name, r0, r1, z, col, mat, segs=128):
    verts, faces = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        verts += [(math.cos(a) * r0, math.sin(a) * r0, z), (math.cos(a) * r1, math.sin(a) * r1, z)]
    for i in range(segs):
        j = (i + 1) % segs
        faces.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j))
    return mesh_object(name, verts, faces, col, mat)


def build_lake():
    col = collection("Lake")
    s = LAKE_SIZE / 2
    mesh_object("Lake_Water", [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [(0, 1, 2, 3)], col, MATS["water"])
    # fondo del lago para dar color de profundidad cerca de la arena
    s2 = 120
    mesh_object("Lake_Bed", [(-s2, -s2, -3), (s2, -s2, -3), (s2, s2, -3), (-s2, s2, -3)], [(0, 1, 2, 3)], col,
                MATS["rock"])


def ogive_arch(name, p_a, p_b, spring, depth, band, col, mat):
    """Arco ojival equilÃ¡tero entre dos puntos de apoyo (caras interiores de los pilares)."""
    span_vec = p_b - p_a
    w = span_vec.length
    u = span_vec.normalized()
    nrm = Vector((-u.y, u.x, 0))
    R = w  # equilÃ¡tero
    steps = 16
    inner, outer = [], []
    # mitad izquierda: arco centrado en p_b, de Ã¡ngulo 180Âº a 120Âº
    for i in range(steps + 1):
        t = math.radians(180 - 60 * i / steps)
        for (lst, rr) in ((inner, R), (outer, R + band)):
            x = w + math.cos(t) * rr
            y = math.sin(t) * rr
            lst.append((x, y))
    right_in, right_out = [], []
    for i in range(steps + 1):
        t = math.radians(60 - 60 * i / steps)
        for (lst, rr) in ((right_in, R), (right_out, R + band)):
            lst.append((math.cos(t) * rr, math.sin(t) * rr))
    # outer apex: intersecciones aproximadas; recortamos las coordenadas x fuera del vano extendido
    inner += right_in[1:]
    outer += right_out[1:]
    verts, faces = [], []
    n = len(inner)
    for half in (-depth / 2, depth / 2):
        for (x, y), (xo, yo) in zip(inner, outer):
            xo = max(-band, min(w + band, xo))
            for (xx, yy) in ((x, y), (xo, yo)):
                pos = p_a + u * xx + nrm * half + Vector((0, 0, spring + yy))
                verts.append(tuple(pos))
    # Ã­ndices: capa c, punto i, (inner=0, outer=1)
    idx = lambda c, i, o: c * n * 2 + i * 2 + o
    for i in range(n - 1):
        for c in (0, 1):
            faces.append((idx(c, i, 0), idx(c, i + 1, 0), idx(c, i + 1, 1), idx(c, i, 1)))
        faces.append((idx(0, i, 0), idx(1, i, 0), idx(1, i + 1, 0), idx(0, i + 1, 0)))
        faces.append((idx(0, i, 1), idx(0, i + 1, 1), idx(1, i + 1, 1), idx(1, i, 1)))
    return mesh_object(name, verts, faces, col, mat)


def build_pillars():
    col = collection("Pillars")
    from mathutils import Matrix
    for p, c in enumerate(PAIR_CENTERS):
        pts = []
        for s in (-1, 1):
            a = math.radians(c + s * PAIR_SPREAD / 2)
            pos = Vector((math.cos(a) * PILLAR_R, math.sin(a) * PILLAR_R, 0))
            pts.append((pos, a))
            bm = bmesh.new()
            rot = Matrix.Rotation(a, 4, "Z")
            def part(sx, sy, z0, z1, scale=1.0):
                m = Matrix.Translation(pos + Vector((0, 0, (z0 + z1) / 2))) @ rot @ Matrix.Diagonal((sx, sy, z1 - z0, 1))
                bmesh.ops.create_cube(bm, size=1.0, matrix=m)
            part(1.6, 1.6, -1.5, 0.9)                 # zÃ³calo que sale del agua
            part(1.3, 1.3, 0.9, 1.5)                  # basa
            part(PILLAR_SIZE, PILLAR_SIZE, 1.5, PILLAR_H)  # fuste
            part(1.25, 1.25, ARCH_SPRING - 0.35, ARCH_SPRING)  # capitel
            part(1.2, 1.2, PILLAR_H, PILLAR_H + 0.4)  # remate
            bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=0.55, radius2=0.0, depth=2.2,
                                  matrix=Matrix.Translation(pos + Vector((0, 0, PILLAR_H + 1.5))) @ rot @ Matrix.Rotation(math.pi / 4, 4, "Z"))
            from_bmesh(f"Pillar_{p}_{'ab'[s > 0]}", bm, col, MATS["marble"])
            # estandarte en la cara interior
            inward = Vector((-math.cos(a), -math.sin(a), 0))
            tang = Vector((-math.sin(a), math.cos(a), 0))
            base = pos + inward * (PILLAR_SIZE / 2 + 0.03)
            bw, top, bot = 0.42, ARCH_SPRING - 0.7, 2.6
            vv = [base + tang * -bw + Vector((0, 0, top)), base + tang * bw + Vector((0, 0, top)),
                  base + tang * bw + Vector((0, 0, bot + 0.5)), base + Vector((0, 0, bot)),
                  base + tang * -bw + Vector((0, 0, bot + 0.5))]
            mesh_object(f"Banner_{p}_{'ab'[s > 0]}", [tuple(v) for v in vv], [(4, 3, 2, 1, 0)], col, MATS["banner"])
            # hoja dorada simple (rombo) sobre el estandarte
            cz = (top + bot) / 2 + 0.4
            lv = [base + inward * 0.01 + Vector((0, 0, cz + 1.0)), base + inward * 0.01 + tang * 0.2 + Vector((0, 0, cz)),
                  base + inward * 0.01 + Vector((0, 0, cz - 1.0)), base + inward * 0.01 + tang * -0.2 + Vector((0, 0, cz))]
            mesh_object(f"BannerLeaf_{p}_{'ab'[s > 0]}", [tuple(v) for v in lv], [(3, 2, 1, 0)], col, MATS["gold"])
        # arco entre las caras interiores del par
        (pa, aa), (pb, ab) = pts
        u = (pb - pa).normalized()
        fa = pa + u * (PILLAR_SIZE / 2)
        fb = pb - u * (PILLAR_SIZE / 2)
        ogive_arch(f"Arch_{p}", fa, fb, ARCH_SPRING, 0.8, 0.45, col, MATS["marble"])
        # dintel superior que une los dos pilares
        mid = (pa + pb) / 2
        w = (pb - pa).length + 1.2
        bm = box_bm(1, 1, 1, Vector())
        ob = from_bmesh(f"Lintel_{p}", bm, col, MATS["marble"])
        ob.location = mid + Vector((0, 0, PILLAR_H - 0.2))
        ob.scale = (w, 0.9, 0.6)
        ob.rotation_euler = (0, 0, math.atan2(u.y, u.x))


def build_spawns():
    col = collection("Spawns")
    for i, (p, mk) in enumerate(zip(SPAWNS, ("p1", "p2"))):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.3)
        for v in bm.verts:
            v.co.z += 1.2 if v.co.z > 0 else 0.0
            v.co.z += 0.3
        ob = from_bmesh(f"Mannequin_P{i + 1}", bm, col, MATS[mk], smooth=True)
        ob.location = p
        other = SPAWNS[1 - i]
        d = other - p
        ob.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.pi / 2)
        e = bpy.data.objects.new(f"Spawn_P{i + 1}", None)
        e.empty_display_type = "ARROWS"
        e.location = p
        e.rotation_euler = ob.rotation_euler
        col.objects.link(e)


# -- valle
def cliff_r0(x, y):
    return VALLEY_R0 + 35 * noise.noise(Vector((x / 160, y / 160, 3.1)))


def sun_gap(x, y, depth=0.85):
    """1 lejos del sol, 1-depth en la dirección del sol: abre el valle para que entre la luz."""
    t = math.degrees(math.atan2(y, x))
    d = (t - SUN_AZIM + 180) % 360 - 180
    return 1 - depth * math.exp(-(d / GAP_SIGMA) ** 2)


def valley_h(x, y):
    r = math.hypot(x, y) + 1e-6
    g = sun_gap(x, y, 0.93)
    r0 = VALLEY_R0 + 35 * noise.noise(Vector((x / r * 1.6, y / r * 1.6, 3.1)))
    cliff = smoothstep(r0, r0 + 22, r)
    top = 62 + 38 * noise.noise(Vector((x / 140, y / 140, 7.7)))
    h = -6 + cliff * (top * g + 6)
    h += cliff * 6 * noise.noise(Vector((x / 25, y / 25, 1.3)))
    # mesetas que suben hacia fuera
    h += smoothstep(r0 + 60, 900, r) * (90 + 60 * noise.noise(Vector((x / 300, y / 300, 5.0)))) * g
    return h, r0


def valley_r0(theta):
    x, y = math.cos(theta), math.sin(theta)
    return VALLEY_R0 + 35 * noise.noise(Vector((x * 1.6, y * 1.6, 3.1)))


def polar_grid(name, rs, nt, hfun, col, mat):
    verts, faces = [], []
    for r in rs:
        for j in range(nt):
            t = 2 * math.pi * j / nt
            x, y = math.cos(t) * r, math.sin(t) * r
            verts.append((x, y, hfun(x, y)))
    for i in range(len(rs) - 1):
        for j in range(nt):
            j2 = (j + 1) % nt
            faces.append((i * nt + j, i * nt + j2, (i + 1) * nt + j2, (i + 1) * nt + j))
    return mesh_object(name, verts, faces, col, mat, smooth=True)


def build_valley():
    col = collection("Valley")
    rs = []
    r = 130.0
    while r < 1700:
        rs.append(r)
        r += 2.5 if r < 280 else (6 if r < 500 else 25)
    polar_grid("Valley_Terrain", rs, 360, lambda x, y: valley_h(x, y)[0], col, MATS["rock"])

    # cascadas sobre la cara de los acantilados (hacia donde mira la cÃ¡mara hÃ©roe, +Y)
    falls = [(93, 16), (101, 9), (110, 22), (121, 12), (133, 18), (147, 10), (162, 14), (22, 12), (14, 8)]
    for k, (deg, width) in enumerate(falls):
        t = math.radians(deg)
        r0 = valley_r0(t)
        dirv = Vector((math.cos(t), math.sin(t), 0))
        tang = Vector((-dirv.y, dirv.x, 0))
        top_r = r0 + 24
        top_z = valley_h(*(dirv * top_r).xy)[0] - 1.0
        verts = []
        for s in (-1, 1):
            verts.append(tuple(dirv * (r0 - 4) + tang * s * width / 2 * 1.15 + Vector((0, 0, -0.5))))
        for s in (1, -1):
            verts.append(tuple(dirv * (top_r - 1.0) + tang * s * width / 2 + Vector((0, 0, top_z))))
        mesh_object(f"Waterfall_{k}", verts, [(0, 1, 2, 3)], col, MATS["falls"])
        # espuma en la base (disco blanco bajo)
        bm = cylinder_bm(width * 0.7, width * 0.55, 3.0, segs=20, z0=-0.5)
        ob = from_bmesh(f"WaterfallFoam_{k}", bm, col, MATS["falls"])
        ob.location = dirv * (r0 - 6)
        ob.scale = (1.0, 0.45, 1.0)
        ob.rotation_euler = (0, 0, t + math.pi / 2)

    # torres Ã©lficas en las laderas y cimas
    from mathutils import Matrix
    towers = [(50, 40, 34), (66, 70, 46), (84, 30, 28), (100, 55, 52), (118, 35, 30), (136, 60, 40),
              (160, 45, 32), (25, 50, 36), (200, 40, 30), (330, 45, 34)]
    for k, (deg, dr, h) in enumerate(towers):
        t = math.radians(deg)
        r = valley_r0(t) + dr
        x, y = math.cos(t) * r, math.sin(t) * r
        z = valley_h(x, y)[0] - 2
        bm = bmesh.new()
        base = Vector((x, y, z))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=3.2, radius2=2.4, depth=h,
                              matrix=Matrix.Translation(base + Vector((0, 0, h / 2))))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=3.4, radius2=0.0, depth=h * 0.45,
                              matrix=Matrix.Translation(base + Vector((0, 0, h + h * 0.225))))
        # torreta lateral
        side = base + Vector((4.2 * math.cos(t + 1.6), 4.2 * math.sin(t + 1.6), 0))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=1.4, radius2=1.1, depth=h * 0.65,
                              matrix=Matrix.Translation(side + Vector((0, 0, h * 0.325))))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=1.6, radius2=0.0, depth=h * 0.3,
                              matrix=Matrix.Translation(side + Vector((0, 0, h * 0.65 + h * 0.15))))
        from_bmesh(f"ElvenTower_{k}", bm, col, MATS["marble"])

    # Ã¡rboles (duplicados enlazados)
    tcol = collection("Trees")
    crowns = {}
    for kind, mat in (("green", MATS["leaf"]), ("lilac", MATS["lilac"])):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
        crowns[kind] = bpy.data.meshes.new(f"TreeCrown_{kind}")
        bm.to_mesh(crowns[kind]); bm.free()
        crowns[kind].materials.append(mat)
        crowns[kind].shade_smooth()
    trunk = bpy.data.meshes.new("TreeTrunk")
    bm = cylinder_bm(0.18, 0.12, 1.0, segs=8)
    bm.to_mesh(trunk); bm.free()
    trunk.materials.append(MATS["bark"])
    placed = 0
    tries = 0
    while placed < 900 and tries < 20000:
        tries += 1
        t = random.uniform(0, 2 * math.pi)
        r0 = valley_r0(t)
        r = random.uniform(r0 + 20, r0 + 260)
        x, y = math.cos(t) * r, math.sin(t) * r
        z, _ = valley_h(x, y)
        if z < 4:
            continue
        # cÃºmulos: densidad por ruido
        if noise.noise(Vector((x / 60, y / 60, 9.0))) < -0.1:
            continue
        s = random.uniform(4.0, 8.0)
        lilac = random.random() < 0.28
        cr = bpy.data.objects.new("Tree", crowns["lilac" if lilac else "green"])
        cr.location = (x, y, z + s * 1.4)
        cr.scale = (s, s, s * random.uniform(0.75, 1.0))
        tcol.objects.link(cr)
        tr = bpy.data.objects.new("Trunk", trunk)
        tr.location = (x, y, z - 1)
        tr.scale = (s, s, s * 1.4)
        tcol.objects.link(tr)
        placed += 1
    print("trees", placed)


def build_islands():
    col = collection("FloatingIslands")
    from mathutils import Matrix
    islands = [(78, 330, 165, 26), (100, 500, 265, 54), (124, 320, 150, 22), (50, 620, 300, 46),
               (142, 540, 245, 34), (28, 400, 175, 20)]
    for k, (deg, dist, alt, size) in enumerate(islands):
        t = math.radians(deg)
        c = Vector((math.cos(t) * dist, math.sin(t) * dist, alt))
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=0.0, radius2=size, depth=size * 1.5,
                              matrix=Matrix.Translation(c + Vector((0, 0, -size * 0.75))))
        for v in bm.verts:
            v.co += Vector(noise.noise_vector(v.co / (size * 0.5))) * size * 0.18
        rock = from_bmesh(f"Island_{k}_Rock", bm, col, MATS["rock"])
        bm = cylinder_bm(size * 1.02, size * 0.98, size * 0.12, segs=14, z0=-size * 0.06, offset=c)
        from_bmesh(f"Island_{k}_Top", bm, col, MATS["leaf"])
        bm = bmesh.new()
        for (ox, oy, h, r) in [(0, 0, size * 1.3, size * 0.12), (size * 0.35, size * 0.2, size * 0.8, size * 0.08),
                               (-size * 0.3, size * 0.3, size * 0.7, size * 0.07), (size * 0.1, -size * 0.4, size * 0.6, size * 0.06)]:
            p = c + Vector((ox, oy, size * 0.05))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r * 0.8, depth=h,
                                  matrix=Matrix.Translation(p + Vector((0, 0, h / 2))))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r * 1.1, radius2=0, depth=h * 0.45,
                                  matrix=Matrix.Translation(p + Vector((0, 0, h + h * 0.225))))
        from_bmesh(f"Island_{k}_Castle", bm, col, MATS["marble"])
        # hilo de agua cayendo del borde
        edge = c + Vector((math.cos(t + math.pi) * size * 0.9, math.sin(t + math.pi) * size * 0.9, 0))
        tang = Vector((-math.sin(t), math.cos(t), 0)) * size * 0.06
        L = size * 2.5
        vv = [edge - tang, edge + tang, edge + tang * 0.4 + Vector((0, 0, -L)), edge - tang * 0.4 + Vector((0, 0, -L))]
        mesh_object(f"Island_{k}_Fall", [tuple(v) for v in vv], [(0, 1, 2, 3)], col, MATS["falls"])


def build_mountains():
    col = collection("Mountains")
    r0, r1 = MOUNT_R
    rs = [r0 + (r1 - r0) * (i / 40) ** 1.2 for i in range(41)]

    def h(x, y):
        r = math.hypot(x, y)
        p = Vector((x / 700, y / 700, 2.0))
        ridge = 1 - abs(noise.noise(p))
        ridge2 = 1 - abs(noise.noise(p * 2.3 + Vector((5, 5, 5))))
        v = ridge ** 2 * 750 + ridge2 ** 3 * 260
        return (v * smoothstep(r0, r0 + 600, r)) * sun_gap(x, y, 0.75) + 60
    polar_grid("Mountains", rs, 300, h, col, MATS["mountain"])


def build_sky_and_light():
    sc = bpy.context.scene
    world = bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    sky = nt.nodes.new("ShaderNodeTexSky")
    types = [e.identifier for e in sky.bl_rna.properties["sky_type"].enum_items]
    print("sky types", types)
    for pref in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING"):
        if pref in types:
            sky.sky_type = pref
            break
    sky.sun_elevation = math.radians(SUN_ELEV)
    # Nishita: sun_rotation 0 => sol en +Y, gira en sentido horario visto desde arriba
    sky.sun_rotation = math.radians(90 - SUN_AZIM)
    for attr, val in (("altitude", 300.0), ("air_density", 1.0), ("dust_density", 2.5), ("aerosol_density", 2.5),
                      ("ozone_density", 1.0), ("sun_disc", True), ("sun_size", math.radians(1.2)),
                      ("sun_intensity", 0.6)):
        if hasattr(sky, attr):
            try:
                setattr(sky, attr, val)
            except Exception as ex:
                print("sky attr", attr, ex)
    # tinte cálido de atardecer sobre el cielo físico
    tint = nt.nodes.new("ShaderNodeMix"); tint.data_type = "RGBA"; tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 0.55
    tint.inputs["B"].default_value = (1.0, 0.72, 0.5, 1.0)
    nt.links.new(sky.outputs[0], tint.inputs["A"])
    nt.links.new(tint.outputs["Result"], bg.inputs[0])
    bg.inputs["Strength"].default_value = 0.25

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 4.5
    sun_data.angle = math.radians(1.5)
    sun_data.color = hex_rgb("#FFC58A")[:3]
    sun = bpy.data.objects.new("Sun", sun_data)
    collection("Lighting").objects.link(sun)
    e, a = math.radians(SUN_ELEV), math.radians(SUN_AZIM)
    sdir = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    sun.rotation_euler = (-sdir).to_track_quat("-Z", "Y").to_euler()
    if hasattr(sun_data, "use_shadow_jitter"):
        sun_data.use_shadow_jitter = True


def build_cameras():
    col = collection("Cameras")
    cams = {}

    def cam(name, loc, target, lens=24, ortho=None):
        d = bpy.data.cameras.new(name)
        d.lens = lens
        d.clip_start = 0.1
        d.clip_end = 8000
        if ortho:
            d.type = "ORTHO"
            d.ortho_scale = ortho
        ob = bpy.data.objects.new(name, d)
        ob.location = loc
        col.objects.link(ob)
        look_at(ob, target)
        cams[name] = ob
        return ob

    cam("cam_hero", (-3.0, -12.5, ARENA_TOP + 1.7), (3, 40, 8), lens=20)
    p1, p2 = SPAWNS
    cam("cam_gameplay", p1 + Vector((0, -3.5, 1.8 + 0.6)), p2 + Vector((0, 0, 1.2)), lens=24)
    top = cam("cam_top", (0, 0, 40), (0, 0, 0), ortho=60)
    top.rotation_euler = (0, 0, 0)
    cam("cam_wide", (55, -80, 42), (-5, 120, 40), lens=22)
    bpy.context.scene.camera = cams["cam_hero"]
    return cams


def render(cams, which, outdir, samples):
    sc = bpy.context.scene
    os.makedirs(outdir, exist_ok=True)
    if hasattr(sc.eevee, "taa_render_samples"):
        sc.eevee.taa_render_samples = samples
    times = {}
    for name in which:
        sc.camera = cams[name]
        sc.render.filepath = os.path.join(outdir, f"{name}.png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        times[name] = time.time() - t0
        print(f"RENDERED {name} {times[name]:.1f}s -> {sc.render.filepath}")
    return times


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    which = []
    outdir = os.path.join(WORK, "renders", "01_blockout")
    samples = 64
    for i, a in enumerate(argv):
        if a == "--render":
            which = argv[i + 1].split(",")
        elif a == "--out":
            outdir = argv[i + 1]
        elif a == "--samples":
            samples = int(argv[i + 1])
    t0 = time.time()
    setup()
    build_materials()
    build_arena()
    build_lake()
    build_pillars()
    build_spawns()
    build_valley()
    build_islands()
    build_mountains()
    build_sky_and_light()
    cams = build_cameras()
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"BUILD {time.time() - t0:.1f}s saved {BLEND_PATH}")
    if which == ["all"]:
        which = list(cams)
    if which:
        render(cams, which, outdir, samples)


main()
