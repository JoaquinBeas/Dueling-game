"""Utilidades del kit modular élfico: geometría procedural, UVs, vertex color de desgaste y materiales.

Convenciones del kit:
- 1 u Blender = 1 m, Z arriba.
- Cada pieza tiene el pivote en su base (Z = 0), salvo SM_Arena_Banner, que cuelga de su punto de anclaje.
- Floor, Rim y Step comparten pivote: el centro de la arena a nivel del agua (se colocan todas en el origen).
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, noise

WORK = r"D:\Repos\_arena_work"
ASSETS = os.path.join(WORK, "assets")

PALETTE = {
    "marble": "#E9E1D0", "marble_shadow": "#B9AE98", "gold": "#C9A24A",
    "banner": "#1F4A3A", "moss": "#4E6A34",
}


def hex_rgb(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, a)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def collection(name, parent=None):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if col.name not in parent.children:
        parent.children.link(col)
    return col


# ---------------------------------------------------------------- constructor de mallas
class MB:
    """Acumula vértices y caras (con índice de material y UV opcional) antes de crear la malla."""

    def __init__(self):
        self.v, self.f, self.fm, self.fuv = [], [], [], []

    def vert(self, co):
        self.v.append(Vector(co))
        return len(self.v) - 1

    def face(self, idx, mat=0, uvs=None):
        self.f.append(tuple(idx))
        self.fm.append(mat)
        self.fuv.append(uvs)

    def merge(self, other, matrix=None, mat=None):
        off = len(self.v)
        m = matrix or Matrix.Identity(4)
        self.v += [m @ p for p in other.v]
        for f, fm, uv in zip(other.f, other.fm, other.fuv):
            self.f.append(tuple(i + off for i in f))
            self.fm.append(fm if mat is None else mat)
            self.fuv.append(uv)
        return self

    def transformed(self, matrix):
        return MB().merge(self, matrix)


def lathe(profile, segs, a0=0.0, a1=2 * math.pi, closed_profile=True, mat=0, cap=None, phase=0.0):
    """Revoluciona un perfil [(r, z), ...] alrededor de Z. Si el rango no es completo, tapa los extremos."""
    mb = MB()
    full = abs((a1 - a0) - 2 * math.pi) < 1e-6
    cols = segs if full else segs + 1
    rings = []
    for i in range(cols):
        a = a0 + (a1 - a0) * i / segs + phase
        ca, sa = math.cos(a), math.sin(a)
        rings.append([mb.vert((r * ca, r * sa, z)) for r, z in profile])
    n = len(profile)
    pe = n if closed_profile else n - 1
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % cols]
        for j in range(pe):
            k = (j + 1) % n
            mb.face((A[j], B[j], B[k], A[k]), mat)
    if not full and (cap if cap is not None else closed_profile):
        mb.face(tuple(reversed(rings[0])), mat)
        mb.face(tuple(rings[-1]), mat)
    return mb


def sweep(path, profile, binormal=Vector((0, 1, 0)), closed=False, mat=0, caps=True, miter=True):
    """Barre un perfil 2D cerrado [(a, b)] a lo largo de una polilínea.
    a va según la normal n = t x binormal (en el plano de la curva), b según el binormal."""
    mb = MB()
    N = len(path)
    rings = []
    for i in range(N):
        p = Vector(path[i])
        tp = (p - Vector(path[i - 1])) if (i > 0 or closed) else (Vector(path[1]) - p)
        tn = (Vector(path[(i + 1) % N]) - p) if (i < N - 1 or closed) else (p - Vector(path[i - 1]))
        tp.normalize(); tn.normalize()
        t = (tp + tn)
        if t.length < 1e-6:
            t = tn
        t.normalize()
        n = t.cross(binormal).normalized()
        scale = 1.0
        if miter:
            n_prev = tp.cross(binormal).normalized()
            scale = 1.0 / max(0.35, n.dot(n_prev))
        rings.append([mb.vert(p + n * (a * scale) + binormal * b) for a, b in profile])
    m = len(profile)
    segs = N if closed else N - 1
    for i in range(segs):
        A, B = rings[i], rings[(i + 1) % N]
        for j in range(m):
            k = (j + 1) % m
            mb.face((A[j], A[k], B[k], B[j]), mat)
    if caps and not closed:
        mb.face(tuple(rings[0]), mat)
        mb.face(tuple(reversed(rings[-1])), mat)
    return mb


def chamfer_rect(hw, hd, c):
    """Perfil rectangular (semiancho hw según a, semifondo hd según b) con chaflán c."""
    c = min(c, hw * 0.45, hd * 0.45)
    return [(-hw + c, -hd), (hw - c, -hd), (hw, -hd + c), (hw, hd - c),
            (hw - c, hd), (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c)]


def leaf(L, W, thick=0.02, bulge=0.03, curl=0.0, twist=0.0, nu=10, nv=4, mat=0, lobes=0, lobe_amp=0.0):
    """Hoja élfica alargada y cerrada: nace en el origen y crece según +X; la cara 'top' mira a +Z.
    curl: curvatura total en radianes (positivo = se enrosca hacia +Z)."""
    mb = MB()
    # espina integrada con curvatura creciente (la punta se enrosca más)
    spine, frames = [], []
    p, ds = Vector((0, 0, 0)), L / nu
    for i in range(nu + 1):
        u = i / nu
        th = curl * u * u
        spine.append(p.copy())
        frames.append(th)
        p = p + Vector((math.cos(th), 0, math.sin(th))) * ds
    top, bot = [], []
    for i in range(nu + 1):
        u = i / nu
        th = frames[i]
        tng = Vector((math.cos(th), 0, math.sin(th)))
        nrm = Vector((-math.sin(th), 0, math.cos(th)))
        hw = 0.5 * W * (math.sin(math.pi * min(1.0, u ** 0.75)) ** 0.9) * (1.0 - 0.25 * u)
        if lobes:
            hw *= 1.0 + lobe_amp * math.sin(u * math.pi * lobes * 2) ** 2
        if i == nu:
            hw = 0.0
        rt, rb = [], []
        for j in range(nv + 1):
            v = -1 + 2 * j / nv
            side = Vector((0, 1, 0))
            if twist:
                side = Matrix.Rotation(twist * u, 3, tng) @ side
            dome = bulge * (1 - v * v) * math.sin(math.pi * u) - 0.4 * bulge * math.exp(-(v * 5) ** 2) * math.sin(math.pi * u)
            th_k = thick * (0.3 + 0.7 * (1 - v * v)) * (1 - 0.7 * u)
            base = spine[i] + side * (v * hw)
            rt.append(mb.vert(base + nrm * (dome + th_k * 0.5)))
            rb.append(mb.vert(base + nrm * (dome - th_k * 0.5)))
        top.append(rt); bot.append(rb)
    for i in range(nu):
        for j in range(nv):
            mb.face((top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1]), mat)
            mb.face((bot[i][j], bot[i][j + 1], bot[i + 1][j + 1], bot[i + 1][j]), mat)
    for i in range(nu):  # bordes
        mb.face((top[i][0], bot[i][0], bot[i + 1][0], top[i + 1][0]), mat)
        mb.face((top[i][nv], top[i + 1][nv], bot[i + 1][nv], bot[i][nv]), mat)
    mb.face(tuple(top[0][j] for j in range(nv + 1)) + tuple(bot[0][j] for j in reversed(range(nv + 1))), mat)
    return mb


def ogive(w, ratio, offset=0.0, steps=24):
    """Arco apuntado de luz w (de -w/2 a w/2) con radio = ratio*w; offset desplaza el radio (anillos concéntricos).
    Devuelve puntos (x, z) desde el arranque izquierdo hasta el derecho pasando por la clave."""
    r = ratio * w
    cx = -w / 2 + r            # centro del arco izquierdo
    R = r + offset
    th_a = math.acos(max(-1, min(1, -cx / R)))
    left = [(cx + R * math.cos(math.pi - (math.pi - th_a) * i / steps), R * math.sin(math.pi - (math.pi - th_a) * i / steps))
            for i in range(steps + 1)]
    right = [(-x, z) for x, z in reversed(left[:-1])]
    return left + right


def ogive_rise(w, ratio):
    r = ratio * w
    return math.sqrt(r * r - (r - w / 2) ** 2)


# ---------------------------------------------------------------- objeto final
def finalize(name, mb, mats, col, tile=2.0, smooth_angle=35.0, wear=None, uv_mode="box", recalc=True):
    """Crea el objeto: limpia dobles, recalcula normales, UVs (proyección de caja a escala de mundo),
    sombreado por ángulo y canal de vertex color 'Wear' (R = musgo, G = suciedad/desgaste)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in mb.v], [], mb.f)
    me.update()
    for poly, mi in zip(me.polygons, mb.fm):
        poly.material_index = mi
    # uv personalizadas por cara (si se dieron)
    uvl = me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    if recalc:   # en mallas abiertas (anillo de acantilados, terreno) la orientación ya viene bien construida
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.active
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda k: abs(n[k]))
        for lp in f.loops:
            co = lp.vert.co
            if callable(uv_mode):
                lp[uv].uv = uv_mode(co, n)
            elif uv_mode == "planar_xy":
                lp[uv].uv = (co.x / tile, co.y / tile)
            elif ax == 2:
                lp[uv].uv = (co.x / tile * (1 if n.z > 0 else -1), co.y / tile)
            elif ax == 0:
                lp[uv].uv = (co.y / tile * (1 if n.x > 0 else -1), co.z / tile)
            else:
                lp[uv].uv = (-co.x / tile * (1 if n.y > 0 else -1), co.z / tile)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    # vertex color de desgaste
    ca = me.color_attributes.new("Wear", "BYTE_COLOR", "CORNER")
    me.color_attributes.active_color = ca
    me.color_attributes.render_color_index = 0
    wear = wear or default_wear
    vnorm = [v.normal for v in me.vertices]
    cache = {}
    for lp in me.loops:
        vi = lp.vertex_index
        if vi not in cache:
            cache[vi] = wear(me.vertices[vi].co, vnorm[vi])
        r, g = cache[vi]
        ca.data[lp.index].color = (r, g, 0.0, 1.0)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def _n01(p, s=1.0, off=(0, 0, 0)):
    return noise.noise(Vector(p) * s + Vector(off)) * 0.5 + 0.5


def default_wear(co, nrm, z_ground=0.0, z_top=10.0):
    """Musgo en la base (cerca del agua) y en superficies que miran arriba; suciedad en manchas, más abajo."""
    n1 = _n01(co, 0.9, (3.1, 7.7, 1.3))
    n2 = _n01(co, 2.7, (11.0, 2.0, 5.0))
    low = 1.0 - smoothstep(z_ground - 0.4, z_ground + 1.8, co.z)
    up = max(0.0, nrm.z)
    moss = low * smoothstep(0.35, 0.65, n1 + 0.15) * (0.55 + 0.45 * n2)
    moss += up * 0.45 * smoothstep(0.55, 0.78, n2) * (1.0 - smoothstep(z_top * 0.6, z_top, co.z) * 0.5)
    grime = 0.15 + 0.6 * smoothstep(0.45, 0.85, n1) * (1.0 - 0.5 * smoothstep(0.0, z_top, co.z))
    return (min(1.0, moss), min(1.0, grime))


# ---------------------------------------------------------------- materiales
def _img(path, non_color=False):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def _tex(nt, path, non_color=False, uvnode=None):
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = _img(path, non_color)
    if uvnode is not None:
        nt.links.new(uvnode.outputs[0], t.inputs["Vector"])
    return t


def mat_marble(name, tint=(1, 1, 1), shadow=0.0):
    """Mármol marfil (ambientCG Marble014) con musgo y suciedad del vertex color 'Wear'."""
    d = os.path.join(ASSETS, "Marble014")
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    uv = N.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    col = _tex(nt, os.path.join(d, "Marble014_2K-JPG_Color.jpg"), uvnode=uv)
    rough = _tex(nt, os.path.join(d, "Marble014_2K-JPG_Roughness.jpg"), True, uv)
    nrm = _tex(nt, os.path.join(d, "Marble014_2K-JPG_NormalGL.jpg"), True, uv)
    # aclarar hacia marfil: el color de la textura es algo gris; mezclamos con el tono de paleta
    # suavizar el contraste de las vetas (la textura original es muy parda para el marfil de la paleta)
    soft = N.new("ShaderNodeMix"); soft.data_type = "RGBA"
    soft.inputs["Factor"].default_value = 0.42
    L.new(col.outputs[0], soft.inputs["A"]); soft.inputs["B"].default_value = (0.70, 0.64, 0.55, 1)
    base = N.new("ShaderNodeMix"); base.data_type = "RGBA"; base.blend_type = "MULTIPLY"
    base.inputs["Factor"].default_value = 1.0
    L.new(soft.outputs["Result"], base.inputs["A"])
    base.inputs["B"].default_value = (1.18 * tint[0], 1.14 * tint[1], 1.08 * tint[2], 1)
    if shadow:
        sh = N.new("ShaderNodeMix"); sh.data_type = "RGBA"; sh.blend_type = "MULTIPLY"
        sh.inputs["Factor"].default_value = shadow
        L.new(base.outputs["Result"], sh.inputs["A"]); sh.inputs["B"].default_value = hex_rgb(PALETTE["marble_shadow"])
        base = sh
    vc = N.new("ShaderNodeVertexColor"); vc.layer_name = "Wear"
    sep = N.new("ShaderNodeSeparateColor")
    L.new(vc.outputs["Color"], sep.inputs[0])
    # musgo con ruptura de ruido para que no se vea el degradado por vértice
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 3.5; nz.inputs["Detail"].default_value = 8
    tc = N.new("ShaderNodeTexCoord"); L.new(tc.outputs["Object"], nz.inputs["Vector"])
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    L.new(sep.outputs["Red"], mul.inputs[0]); L.new(nz.outputs["Fac"], mul.inputs[1])
    ramp = N.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.12; ramp.inputs["From Max"].default_value = 0.34
    L.new(mul.outputs[0], ramp.inputs["Value"])
    moss = N.new("ShaderNodeMix"); moss.data_type = "RGBA"
    L.new(ramp.outputs[0], moss.inputs["Factor"])
    L.new(base.outputs["Result"], moss.inputs["A"]); moss.inputs["B"].default_value = hex_rgb(PALETTE["moss"])
    grime = N.new("ShaderNodeMix"); grime.data_type = "RGBA"; grime.blend_type = "MULTIPLY"
    gfac = N.new("ShaderNodeMath"); gfac.operation = "MULTIPLY"; gfac.inputs[1].default_value = 0.55
    L.new(sep.outputs["Green"], gfac.inputs[0])
    L.new(gfac.outputs[0], grime.inputs["Factor"])
    L.new(moss.outputs["Result"], grime.inputs["A"]); grime.inputs["B"].default_value = (0.62, 0.56, 0.47, 1)
    L.new(grime.outputs["Result"], bsdf.inputs["Base Color"])
    # rugosidad: mármol semipulido, musgo mate
    rmap = N.new("ShaderNodeMapRange")
    rmap.inputs["To Min"].default_value = 0.32; rmap.inputs["To Max"].default_value = 0.6
    L.new(rough.outputs[0], rmap.inputs["Value"])
    rmix = N.new("ShaderNodeMix")
    L.new(ramp.outputs[0], rmix.inputs["Factor"]); L.new(rmap.outputs[0], rmix.inputs["A"])
    rmix.inputs["B"].default_value = 0.9
    L.new(rmix.outputs["Result"], bsdf.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.7
    L.new(nrm.outputs[0], nm.inputs["Color"]); L.new(nm.outputs[0], bsdf.inputs["Normal"])
    m.diffuse_color = hex_rgb(PALETTE["marble"])
    return m


def mat_gold(name):
    """Oro viejo (ambientCG Metal034) apagado hacia la paleta y ensuciado por 'Wear'.G."""
    d = os.path.join(ASSETS, "Metal034")
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    uv = N.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    col = _tex(nt, os.path.join(d, "Metal034_2K-JPG_Color.jpg"), uvnode=uv)
    rough = _tex(nt, os.path.join(d, "Metal034_2K-JPG_Roughness.jpg"), True, uv)
    nrm = _tex(nt, os.path.join(d, "Metal034_2K-JPG_NormalGL.jpg"), True, uv)
    old = N.new("ShaderNodeMix"); old.data_type = "RGBA"
    old.inputs["Factor"].default_value = 0.65
    L.new(col.outputs[0], old.inputs["A"]); old.inputs["B"].default_value = hex_rgb(PALETTE["gold"])
    vc = N.new("ShaderNodeVertexColor"); vc.layer_name = "Wear"
    sep = N.new("ShaderNodeSeparateColor"); L.new(vc.outputs["Color"], sep.inputs[0])
    dirt = N.new("ShaderNodeMix"); dirt.data_type = "RGBA"; dirt.blend_type = "MULTIPLY"
    gf = N.new("ShaderNodeMath"); gf.operation = "MULTIPLY"; gf.inputs[1].default_value = 0.5
    L.new(sep.outputs["Green"], gf.inputs[0]); L.new(gf.outputs[0], dirt.inputs["Factor"])
    L.new(old.outputs["Result"], dirt.inputs["A"]); dirt.inputs["B"].default_value = (0.35, 0.28, 0.16, 1)
    L.new(dirt.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    rmap = N.new("ShaderNodeMapRange")
    rmap.inputs["To Min"].default_value = 0.22; rmap.inputs["To Max"].default_value = 0.45
    L.new(rough.outputs[0], rmap.inputs["Value"]); L.new(rmap.outputs[0], bsdf.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.4
    L.new(nrm.outputs[0], nm.inputs["Color"]); L.new(nm.outputs[0], bsdf.inputs["Normal"])
    m.diffuse_color = hex_rgb(PALETTE["gold"])
    return m


def mat_banner(name):
    """Tela verde con trama fina (procedural) y brillo de terciopelo; se ve por las dos caras."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.use_backface_culling = False
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]
    uv = N.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 6; nz.inputs["Detail"].default_value = 4
    L.new(uv.outputs[0], nz.inputs["Vector"])
    c = N.new("ShaderNodeMix"); c.data_type = "RGBA"
    L.new(nz.outputs["Fac"], c.inputs["Factor"])
    c.inputs["A"].default_value = hex_rgb("#173A2D"); c.inputs["B"].default_value = hex_rgb("#2A5E48")
    L.new(c.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    for key in ("Sheen Weight", "Sheen"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = 0.6
            break
    wave = N.new("ShaderNodeTexWave"); wave.inputs["Scale"].default_value = 160
    wave.wave_type = "BANDS"; wave.bands_direction = "X"
    L.new(uv.outputs[0], wave.inputs["Vector"])
    wave2 = N.new("ShaderNodeTexWave"); wave2.inputs["Scale"].default_value = 160
    wave2.wave_type = "BANDS"; wave2.bands_direction = "Y"
    L.new(uv.outputs[0], wave2.inputs["Vector"])
    add = N.new("ShaderNodeMath"); add.operation = "ADD"
    L.new(wave.outputs["Fac"], add.inputs[0]); L.new(wave2.outputs["Fac"], add.inputs[1])
    bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.08
    L.new(add.outputs[0], bump.inputs["Height"]); L.new(bump.outputs[0], bsdf.inputs["Normal"])
    m.diffuse_color = hex_rgb(PALETTE["banner"])
    return m


def build_materials():
    return {
        "marble": mat_marble("M_Arena_Marble"),
        "trim": mat_marble("M_Arena_MarbleTrim", tint=(1.08, 1.08, 1.06)),
        "joint": mat_marble("M_Arena_MarbleJoint", shadow=0.85),
        "gold": mat_gold("M_Arena_Gold"),
        "banner": mat_banner("M_Arena_Banner"),
    }
