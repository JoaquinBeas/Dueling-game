"""Construye el kit modular élfico de la arena, guarda kit.blend y exporta cada pieza a FBX.

Uso:
  blender -b --factory-startup --python kit_build.py

Piezas (1 u = 1 m, Z arriba):
  SM_Arena_Pillar  pilar de haz de columnillas, pivote en el eje a nivel del agua (Z=0); el zócalo baja a -1 m
  SM_Arena_Arch    arco ojival con tracería y crestería; pivote en el punto medio entre los dos pilares, Z=0.
                   La luz va según X (pilares en X = ±PILLAR_SPACING/2), las caras miran a ±Y
  SM_Arena_Floor   suelo de losas en anillos + medallón; pivote en el centro de la arena a nivel del agua
  SM_Arena_Rim     borde perimetral con labio; mismo pivote que el suelo
  SM_Arena_Step    dos escalones que bajan al agua; mismo pivote que el suelo
  SM_Arena_Banner  estandarte; pivote en el punto de anclaje (centro de la barra), la tela cuelga hacia -Z
                   y la cara delantera mira a -Y
"""
import bpy, math, os, sys
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib, kit_lib
importlib.reload(kit_lib)
from kit_lib import (MB, lathe, sweep, chamfer_rect, leaf, ogive, ogive_rise, finalize, collection,
                     build_materials, default_wear, smoothstep, _n01, WORK)

KIT_BLEND = os.path.join(WORK, "kit.blend")
EXPORT_DIR = os.path.join(WORK, "export")

# ---------------------------------------------------------------- medidas compartidas con el blockout
PILLAR_RING_R = 15.6
PAIR_SPREAD = 20.0
PILLAR_SPACING = 2 * PILLAR_RING_R * math.sin(math.radians(PAIR_SPREAD / 2))   # 5.418 m entre ejes
SPRING = 6.65            # altura de arranque del arco (cara superior del ábaco)
ARCH_RATIO = 0.65        # radio del arco / luz (0.5 = medio punto, 1.0 = equilátero)
ARCH_W = PILLAR_SPACING - 0.72   # luz libre del intradós
ARCH_BAND = 0.34
ARCH_DEPTH = 0.56
FLOOR_TOP = 0.6

# índices de material en cada pieza
M_MARBLE, M_GOLD, M_TRIM, M_JOINT, M_BANNER = 0, 1, 2, 3, 4


def frame(x_axis, z_hint, origin):
    """Matriz con eje X dado y Z lo más parecido a z_hint (ortonormal, dextrógira)."""
    X = Vector(x_axis).normalized()
    Y = Vector(z_hint).cross(X).normalized()
    Z = X.cross(Y)
    m = Matrix((X, Y, Z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def oct_lathe(profile, mat=M_MARBLE):
    return lathe(profile, 8, phase=math.pi / 8, mat=mat)


# ================================================================= PILAR
def build_pillar(mats, col):
    mb = MB()
    orn = MB()     # crochets, hojas y florones: malla aparte que se coloca sin proyectar sombra
    # zócalo octogonal que sale del agua
    mb.merge(oct_lathe([(0, -1.0), (0.86, -1.0), (0.86, 0.38), (0.80, 0.46), (0.70, 0.52), (0.70, 0.56), (0, 0.56)]))
    # basa moldurada: toro - escocia - toro
    mb.merge(lathe([(0, 0.56), (0.66, 0.56), (0.66, 0.62), (0.63, 0.66), (0.65, 0.70), (0.655, 0.75), (0.63, 0.80),
                    (0.58, 0.83), (0.52, 0.86), (0.50, 0.92), (0.53, 0.96), (0.55, 0.99), (0.545, 1.04), (0.50, 1.07),
                    (0.45, 1.10), (0.43, 1.15), (0, 1.15)], 32))
    z0, z1 = 1.15, 5.80
    # fuste: núcleo + 8 columnillas finas
    mb.merge(lathe([(0, z0), (0.30, z0), (0.30, z1), (0, z1)], 16))
    for k in range(8):
        a = k * math.pi / 4
        c = lathe([(0, z0), (0.088, z0), (0.088, z1), (0, z1)], 10)
        cb = lathe([(0, z0), (0.115, z0), (0.115, z0 + 0.05), (0.095, z0 + 0.09), (0.088, z0 + 0.12), (0, z0 + 0.12)], 10)
        m = Matrix.Translation((0.335 * math.cos(a), 0.335 * math.sin(a), 0))
        mb.merge(c, m).merge(cb, m)
    # anillo a media altura (como en los pilares góticos con fustes en haz)
    zr = 3.45
    mb.merge(lathe([(0.30, zr - 0.08), (0.44, zr - 0.08), (0.47, zr - 0.04), (0.47, zr + 0.04), (0.44, zr + 0.08),
                    (0.30, zr + 0.08)], 32))
    # astrágalo dorado
    ast = [(0.44 + 0.035 * math.cos(t), 5.80 + 0.035 * math.sin(t)) for t in [i * math.pi / 4 for i in range(8)]]
    mb.merge(lathe(ast, 32, mat=M_GOLD))
    # capitel: campana
    mb.merge(lathe([(0, 5.82), (0.41, 5.82), (0.42, 5.95), (0.46, 6.12), (0.53, 6.30), (0.60, 6.42), (0.62, 6.46),
                    (0, 6.46)], 24))
    # hojas del capitel: dos coronas alternadas que se curvan hacia fuera
    for tier, (zb, L, W, curl, n, off) in enumerate([(5.84, 0.62, 0.24, 1.6, 12, 0.0), (5.98, 0.48, 0.20, 2.4, 12, 0.5)]):
        for k in range(n):
            a = (k + off) * 2 * math.pi / n
            radial = Vector((math.cos(a), math.sin(a), 0))
            lean = math.radians(16 + 6 * tier)
            X = Vector((0, 0, 1)) * math.cos(lean) + radial * math.sin(lean)
            m = frame(X, radial, radial * (0.40 + 0.02 * tier) + Vector((0, 0, zb)))
            orn.merge(leaf(L, W, thick=0.03, bulge=0.035, curl=curl, nu=9, nv=4), m)
    # filigrana dorada: nervio fino sobre cada hoja de la corona alta
    for k in range(12):
        a = (k + 0.5) * 2 * math.pi / 12
        radial = Vector((math.cos(a), math.sin(a), 0))
        X = Vector((0, 0, 1)) * math.cos(math.radians(22)) + radial * math.sin(math.radians(22))
        m = frame(X, radial, radial * 0.445 + Vector((0, 0, 6.02)))
        orn.merge(leaf(0.40, 0.05, thick=0.012, bulge=0.06, curl=2.4, nu=8, nv=2, mat=M_GOLD), m)
    # ábaco octogonal (aquí arranca el arco)
    mb.merge(oct_lathe([(0, 6.46), (0.66, 6.46), (0.73, 6.51), (0.73, 6.60), (0.69, SPRING), (0, SPRING)]))
    # cuerpo superior y pináculo
    mb.merge(oct_lathe([(0, SPRING), (0.36, SPRING), (0.36, 8.20), (0, 8.20)]))
    mb.merge(oct_lathe([(0.30, 8.20), (0.40, 8.20), (0.40, 8.28), (0.30, 8.28)], M_GOLD))
    mb.merge(oct_lathe([(0, 8.28), (0.44, 8.28), (0.47, 8.33), (0.47, 8.40), (0.40, 8.44), (0, 8.44)]))
    SPIRE0, SPIRE1, SPIRE_R = 8.44, 10.35, 0.37
    mb.merge(oct_lathe([(0, SPIRE0), (SPIRE_R, SPIRE0), (0.02, SPIRE1), (0, SPIRE1)]))
    # crochets en 4 aristas del chapitel
    for k in range(4):
        a = math.pi / 8 + k * math.pi / 2          # aristas del octógono (lathe con fase π/8)
        edge_dir = Vector((math.cos(a), math.sin(a), 0))
        up = (Vector((0, 0, SPIRE1 - SPIRE0)) - edge_dir * (SPIRE_R - 0.02)).normalized()
        out = (edge_dir - up * edge_dir.dot(up)).normalized()
        for j in range(4):
            t = 0.18 + 0.2 * j
            z = SPIRE0 + (SPIRE1 - SPIRE0) * t
            r = SPIRE_R * (1 - t) + 0.02 * t
            X = (up * math.cos(math.radians(50)) + out * math.sin(math.radians(50))).normalized()
            m = frame(X, out, edge_dir * (r - 0.01) + out * 0.03 + Vector((0, 0, z)))
            sc = 1.0 - 0.15 * j
            orn.merge(leaf(0.34 * sc, 0.17 * sc, thick=0.035, bulge=0.025, curl=2.6, nu=7, nv=3), m)
    # florón dorado en la punta
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        radial = Vector((math.cos(a), math.sin(a), 0))
        X = (Vector((0, 0, 1)) + radial * 0.35).normalized()
        orn.merge(leaf(0.24, 0.11, thick=0.02, bulge=0.02, curl=2.2, nu=7, nv=2, mat=M_GOLD),
                 frame(X, radial, Vector((0, 0, SPIRE1 - 0.12)) + radial * 0.02))
    mb.merge(lathe([(0, SPIRE1 - 0.05), (0.035, SPIRE1 - 0.02), (0.05, SPIRE1 + 0.08), (0.03, SPIRE1 + 0.2),
                    (0, SPIRE1 + 0.36)], 10, mat=M_GOLD))
    # pinaculillos en las diagonales del ábaco (dejan libre el apoyo del arco, que va según ±Y)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        p = Vector((0.575 * math.cos(a), 0.575 * math.sin(a), 0))
        sp = oct_lathe([(0, SPRING), (0.085, SPRING), (0.085, 7.25), (0.1, 7.28), (0.1, 7.33), (0.085, 7.35), (0, 7.95)])
        mb.merge(sp, Matrix.Translation(p))
        for kk in range(4):
            aa = kk * math.pi / 2 + math.pi / 4
            rr = Vector((math.cos(aa), math.sin(aa), 0))
            orn.merge(leaf(0.12, 0.06, thick=0.015, bulge=0.01, curl=2.4, nu=5, nv=2),
                     frame((Vector((0, 0, 1)) + rr * 0.3).normalized(), rr, p + rr * 0.06 + Vector((0, 0, 7.5))))

    def wear(co, n):
        return default_wear(co, n, z_ground=0.0, z_top=10.5)
    ob = finalize("SM_Arena_Pillar", mb, [mats["marble"], mats["gold"]], col, tile=2.0, wear=wear)
    finalize("SM_Arena_PillarOrnament", orn, [mats["marble"], mats["gold"]], col, tile=2.0, wear=wear)
    # colisión simple: zócalo + fuste
    ucx = []
    for i, (hx, z0_, z1_) in enumerate([(0.86, -1.0, 1.15), (0.5, 1.15, 10.4)]):
        b = MB()
        vs = [b.vert((sx * hx, sy * hx, z)) for z in (z0_, z1_) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            b.face([vs[j] for j in f])
        ucx.append(collision_object(f"UCX_SM_Arena_Pillar_{i:02d}", b, col))
    return ob, ucx


def collision_object(name, mb, col):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in mb.v], [], mb.f)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.display_type = "WIRE"
    ob.hide_render = True
    col.objects.link(ob)
    return ob


# ================================================================= ARCO
def build_arch(mats, col):
    mb = MB()
    orn = MB()     # crochets, hojas y florones: malla aparte que se coloca sin proyectar sombra
    w, r_ratio = ARCH_W, ARCH_RATIO
    Y = Vector((0, 1, 0))

    def to3(pts, dz=SPRING):
        return [Vector((x, 0, z + dz)) for x, z in pts]

    # anillo principal, orden interior escalonado y moldura de capa (guardapolvo)
    ring = to3(ogive(w, r_ratio, ARCH_BAND / 2, 28))
    mb.merge(sweep(ring, chamfer_rect(ARCH_BAND / 2, ARCH_DEPTH / 2, 0.05), Y))
    inner = to3(ogive(w, r_ratio, -0.06, 28))
    mb.merge(sweep(inner, chamfer_rect(0.07, 0.17, 0.03), Y))
    hood_off = ARCH_BAND + 0.07
    hood = to3(ogive(w, r_ratio, hood_off, 28))
    mb.merge(sweep(hood, chamfer_rect(0.075, 0.20, 0.03), Y))
    # filete dorado en ambas caras del anillo
    for side in (-1, 1):
        prof = [(a, b + side * (ARCH_DEPTH / 2 + 0.004)) for a, b in chamfer_rect(0.022, 0.006, 0.003)]
        mb.merge(sweep(ring, prof, Y, mat=M_GOLD))

    # ---- tracería
    bar = chamfer_rect(0.045, 0.10, 0.02)
    w2 = w / 2
    for sx in (-1, 1):
        sub = [(x + sx * w2 / 2, z) for x, z in ogive(w2, r_ratio, 0.045, 18)]
        mb.merge(sweep(to3(sub), bar, Y))
    sub_rise = ogive_rise(w2, r_ratio) + 0.045
    # vejiga (mandorla) apuntada bajo la clave
    rise = ogive_rise(w, r_ratio)
    vz0, vz1, va = 1.72, rise - 0.07, 0.44
    h = (vz1 - vz0) / 2
    zc = (vz0 + vz1) / 2
    R = (va * va + h * h) / (2 * va)
    d = R - va
    amax = math.asin(h / R)
    ves = []
    n = 16
    for i in range(n + 1):     # mitad derecha, de abajo arriba (centro a la izquierda)
        t = -amax + 2 * amax * i / n
        ves.append((-d + R * math.cos(t), zc + R * math.sin(t)))
    for i in range(1, n):      # mitad izquierda, de arriba abajo
        t = -amax + 2 * amax * i / n
        ves.append((d - R * math.cos(t), zc - R * math.sin(t)))
    mb.merge(sweep(to3(ves[::-1]), bar, Y, closed=True))
    # tallo central desde el colgante hasta la vejiga
    stem = [(0, -0.02 + (vz0 + 0.02) * i / 6) for i in range(7)]
    mb.merge(sweep(to3(stem), chamfer_rect(0.04, 0.09, 0.02), Y))
    # zarcillos en espiral que nacen de la clave de cada subarco
    for sx in (-1, 1):
        S = Vector((sx * w2 / 2, sub_rise))
        C = Vector((sx * 0.95, 1.85))
        R0 = (S - C).length
        th0 = math.atan2(S.y - C.y, S.x - C.x)
        pts = []
        turns = 1.35
        steps = 40
        for i in range(steps + 1):
            u = i / steps
            th = th0 + sx * 2 * math.pi * turns * u     # sube por fuera y se enrosca hacia dentro
            rr = R0 * math.exp(-1.45 * u * turns)
            pts.append((C.x + rr * math.cos(th), C.y + rr * math.sin(th)))
        prof = chamfer_rect(0.032, 0.075, 0.015)
        mb.merge(sweep(to3(pts), prof, Y))
        # hojitas doradas a lo largo del zarcillo
        for j, u in enumerate((0.22, 0.5)):
            i = int(u * steps)
            p0, p1 = Vector((pts[i][0], 0, pts[i][1] + SPRING)), Vector((pts[i + 1][0], 0, pts[i + 1][1] + SPRING))
            t = (p1 - p0).normalized()
            out = t.cross(Y) * sx
            for side in (-1, 1):
                X = (t * 0.5 + out * 0.85).normalized()
                m = frame(X, Y * side, p0 + Y * side * 0.03)
                orn.merge(leaf(0.22 - 0.05 * j, 0.09, thick=0.012, bulge=0.012, curl=0.6, nu=6, nv=2, mat=M_GOLD), m)
    # hoja dorada dentro de la vejiga (por las dos caras)
    for side in (-1, 1):
        m = frame(Vector((0, 0, 1)), Y * side, Vector((0, side * 0.002, SPRING + vz0 + 0.12)))
        orn.merge(leaf(vz1 - vz0 - 0.32, 0.36, thick=0.03, bulge=0.025, curl=0.0, nu=10, nv=4, mat=M_GOLD), m)
    # colgante bajo el encuentro de los subarcos
    mb.merge(lathe([(0, SPRING + 0.05), (0.09, SPRING + 0.04), (0.11, SPRING - 0.06), (0.10, SPRING - 0.18),
                    (0.06, SPRING - 0.30), (0.03, SPRING - 0.40), (0, SPRING - 0.42)], 12))
    mb.merge(lathe([(0, SPRING - 0.40), (0.03, SPRING - 0.41), (0.035, SPRING - 0.47), (0, SPRING - 0.58)], 8, mat=M_GOLD))
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        radial = Vector((math.cos(a), math.sin(a), 0))
        X = (Vector((0, 0, -1)) + radial * 0.5).normalized()
        orn.merge(leaf(0.22, 0.1, thick=0.018, bulge=0.015, curl=1.6, nu=6, nv=2),
                 frame(X, radial, radial * 0.08 + Vector((0, 0, SPRING - 0.02))))

    # ---- crestería: crochets a lo largo del guardapolvo y florón en la clave
    hood_pts = hood
    lens = [0.0]
    for i in range(1, len(hood_pts)):
        lens.append(lens[-1] + (hood_pts[i] - hood_pts[i - 1]).length)
    total = lens[-1]

    def at(s):
        for i in range(1, len(lens)):
            if lens[i] >= s:
                f = (s - lens[i - 1]) / (lens[i] - lens[i - 1])
                p = hood_pts[i - 1].lerp(hood_pts[i], f)
                t = (hood_pts[i] - hood_pts[i - 1]).normalized()
                return p, t
        return hood_pts[-1], (hood_pts[-1] - hood_pts[-2]).normalized()
    spacing = 0.42
    s = 0.9
    while s < total / 2 - 0.35:
        for side in (0, 1):
            ss = s if side == 0 else total - s
            p, t = at(ss)
            if side == 1:
                t = -t                       # siempre apuntando hacia la clave
            n_out = t.cross(Y) if side == 0 else -t.cross(Y)
            if n_out.z < 0 and abs(p.x) > 0.01:
                n_out = -n_out
            base = p + n_out * 0.07
            X = (t * math.cos(math.radians(40)) + n_out * math.sin(math.radians(40))).normalized()
            orn.merge(leaf(0.42, 0.24, thick=0.045, bulge=0.03, curl=2.4, nu=8, nv=3), frame(X, n_out, base))
        s += spacing
    apex = max(hood_pts, key=lambda p: p.z)
    top = apex.z + 0.07
    mb.merge(lathe([(0, top - 0.1), (0.07, top - 0.1), (0.07, top + 0.1), (0.05, top + 0.25), (0.06, top + 0.32),
                    (0.04, top + 0.36), (0.03, top + 0.6), (0, top + 0.62)], 10))
    for tier, (zt, L, cu) in enumerate([(top + 0.12, 0.34, 2.3), (top + 0.36, 0.22, 2.0)]):
        for k in range(4):
            a = k * math.pi / 2 + tier * math.pi / 4
            radial = Vector((math.cos(a), math.sin(a), 0))
            X = (Vector((0, 0, 1)) * 0.6 + radial).normalized()
            orn.merge(leaf(L, L * 0.48, thick=0.025, bulge=0.02, curl=cu, nu=8, nv=3,
                          mat=M_GOLD if tier else M_MARBLE), frame(X, radial, radial * 0.05 + Vector((0, 0, zt))))
    mb.merge(lathe([(0, top + 0.58), (0.035, top + 0.62), (0.045, top + 0.7), (0, top + 0.86)], 8, mat=M_GOLD))

    def wear(co, n):
        return default_wear(co, n, z_ground=SPRING - 4.0, z_top=SPRING + 4.0)
    finalize("SM_Arena_ArchOrnament", orn, [mats["marble"], mats["gold"]], col, tile=2.0, wear=wear)
    return finalize("SM_Arena_Arch", mb, [mats["marble"], mats["gold"]], col, tile=2.0, wear=wear)


# ================================================================= SUELO
def slab(r0, r1, a0, a1, top, bot=0.47, c=0.012, mat=M_MARBLE):
    segs = max(2, int(math.ceil((a1 - a0) * r1 / 0.45)))
    prof = [(r0, bot), (r1, bot), (r1, top - c), (r1 - c, top), (r0 + c, top), (r0, top - c)]
    return lathe(prof, segs, a0, a1, mat=mat)


def build_floor(mats, col):
    mb = MB()
    g = 0.012
    top = FLOOR_TOP
    # base de mortero (se ve oscura en las juntas)
    mb.merge(lathe([(0, -1.6), (13.3, -1.6), (13.3, top - 0.015), (0, top - 0.015)], 64, mat=M_JOINT))
    # losa central del medallón
    mb.merge(lathe([(0, 0.47), (0.95 - g, 0.47), (0.95 - g, top - 0.01), (0.95 - g - 0.01, top), (0, top)], 40))
    rings = [(0.95, 2.34, 8, False, True), (2.46, 5.2, 16, True, False), (5.2, 7.95, 24, False, True),
             (8.05, 10.6, 32, True, False), (10.6, 13.24, 40, False, True)]
    # (r0, r1, n, gold_inside, gold_outside): los bordes contra oro no llevan junta radial
    for i, (r0, r1, n, gin, gout) in enumerate(rings):
        rr0 = r0 if gin else r0 + g
        rr1 = r1 if gout else r1 - g
        off = (i % 2) * 0.5
        for k in range(n):
            a0 = (k + off) * 2 * math.pi / n
            a1 = (k + 1 + off) * 2 * math.pi / n
            rm = (rr0 + rr1) / 2
            mb.merge(slab(rr0, rr1, a0 + g / rm, a1 - g / rm, top))
    # bandas doradas (incrustaciones como geometría separada, a 3 mm sobre la losa)
    for r0, r1 in ((2.34, 2.46), (7.95, 8.05), (13.24, 13.30), (0.93, 0.97)):
        mb.merge(lathe([(r0, top - 0.02), (r1, top - 0.02), (r1, top + 0.003), (r0, top + 0.003)], 128, mat=M_GOLD))
    # roseta dorada del medallón: 8 hojas largas + 8 cortas
    for k in range(16):
        a = k * math.pi / 8
        L = 0.62 if k % 2 == 0 else 0.4
        m = Matrix.Translation((0, 0, top)) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Translation((0.2, 0, 0))
        mb.merge(leaf(L, 0.2 if k % 2 == 0 else 0.13, thick=0.006, bulge=0.0, curl=0.0, nu=8, nv=2, mat=M_GOLD), m)
    # hojas grandes en el anillo del medallón, con un par de hojitas laterales
    for k in range(8):
        a = (k + 0.5) * math.pi / 4
        R = Matrix.Translation((0, 0, top)) @ Matrix.Rotation(a, 4, "Z")
        mb.merge(leaf(1.05, 0.30, thick=0.006, bulge=0.0, nu=10, nv=2, mat=M_GOLD), R @ Matrix.Translation((1.12, 0, 0)))
    # hojas en la banda de 8 m, alineadas con los pares de arcos (45°, 135°, ...)
    for k in range(8):
        a = math.radians(45 * k)
        R = Matrix.Translation((0, 0, top)) @ Matrix.Rotation(a, 4, "Z")
        for s in (-1, 1):
            mb.merge(leaf(0.75, 0.22, thick=0.006, nu=8, nv=2, mat=M_GOLD),
                     R @ Matrix.Translation((8.0, 0, 0)) @ Matrix.Rotation(s * math.pi / 2, 4, "Z") @ Matrix.Translation((0.06, 0, 0)))

    def wear(co, n):
        r = math.hypot(co.x, co.y)
        n1 = _n01(co, 0.7, (5, 1, 9)); n2 = _n01(co, 3.3, (2, 8, 4))
        edge = smoothstep(9.0, 13.2, r)
        in_joint = 1.0 if co.z < FLOOR_TOP - 0.02 else 0.0
        moss = edge * 0.75 * smoothstep(0.5, 0.72, n1) + in_joint * 0.6 * n2 * (0.4 + 0.6 * edge)
        grime = 0.12 + 0.45 * smoothstep(0.45, 0.85, n2) * (0.5 + 0.5 * edge)
        return (min(1, moss), min(1, grime))
    ob = finalize("SM_Arena_Floor", mb, [mats["marble"], mats["gold"], mats["trim"], mats["joint"]], col,
                  tile=2.5, wear=wear, uv_mode="planar_xy")
    # colisión: cilindro convexo
    b = lathe([(0, -1.6), (13.3, -1.6), (13.3, top), (0, top)], 32)
    ucx = collision_object("UCX_SM_Arena_Floor_00", b, col)
    return ob, [ucx]


def build_rim(mats, col):
    mb = MB()
    prof = [(13.30, 0.30), (13.98, 0.30), (13.98, 0.50), (14.04, 0.53), (14.08, 0.58), (14.07, 0.63), (14.03, 0.66),
            (13.97, 0.67), (13.34, 0.67), (13.30, 0.645)]
    n, g = 48, 0.008
    for k in range(n):
        a0, a1 = k * 2 * math.pi / n, (k + 1) * 2 * math.pi / n
        mb.merge(lathe(prof, 4, a0 + g / 13.7, a1 - g / 13.7, mat=0))

    def wear(co, n_):
        m, gr = default_wear(co, n_, z_ground=0.0, z_top=1.0)
        return (m * 0.6, gr * 0.7)
    return finalize("SM_Arena_Rim", mb, [mats["trim"]], col, tile=2.0, wear=wear)


def build_step(mats, col):
    mb = MB()
    steps = [
        [(14.0, -1.2), (14.58, -1.2), (14.58, 0.33), (14.63, 0.35), (14.66, 0.38), (14.64, 0.41), (14.60, 0.42), (14.0, 0.42)],
        [(14.6, -1.2), (15.20, -1.2), (15.20, 0.13), (15.25, 0.15), (15.28, 0.18), (15.26, 0.21), (15.22, 0.22), (14.6, 0.22)],
    ]
    g = 0.008
    for i, prof in enumerate(steps):
        n = 40
        rm = prof[1][0]
        off = 0.5 * i
        for k in range(n):
            a0, a1 = (k + off) * 2 * math.pi / n, (k + 1 + off) * 2 * math.pi / n
            mb.merge(lathe(prof, 5, a0 + g / rm, a1 - g / rm))

    def wear(co, n_):
        return default_wear(co, n_, z_ground=0.15, z_top=1.0)
    return finalize("SM_Arena_Step", mb, [mats["marble"]], col, tile=2.0, wear=wear)


# ================================================================= ESTANDARTE
BANNER_W, BANNER_L, BANNER_TIP = 1.0, 3.0, 0.38


def banner_surf(u, v):
    """Punto de la tela (u en [0,1] de izquierda a derecha, v en [0,1] de arriba abajo). Delante = -Y."""
    tip = BANNER_TIP * (1 - abs(2 * u - 1))
    x = (u - 0.5) * BANNER_W * (1 - 0.05 * math.sin(math.pi * v))
    z = -0.06 - v * (BANNER_L + tip)
    folds = (0.05 * math.sin(2 * math.pi * 2.5 * u + 1.4 * v) + 0.015 * math.sin(2 * math.pi * 6 * u - 2 * v)) \
        * smoothstep(0.0, 0.3, v)
    belly = -0.05 * math.sin(math.pi * u) * math.sin(math.pi * min(1, v * 1.1))
    sway = 0.06 * v * v
    return Vector((x, folds + belly + sway, z))


def banner_normal(u, v, e=1e-3):
    du = banner_surf(min(1, u + e), v) - banner_surf(max(0, u - e), v)
    dv = banner_surf(u, min(1, v + e)) - banner_surf(u, max(0, v - e))
    n = dv.cross(du).normalized()
    return n if n.y < 0 else -n          # normal delantera (hacia -Y)


def build_banner(mats, col):
    mb = MB()
    nu, nv, th = 16, 44, 0.008
    front, back = [], []
    for j in range(nv + 1):
        v = j / nv
        rf, rb = [], []
        for i in range(nu + 1):
            u = i / nu
            p = banner_surf(u, v)
            nrm = banner_normal(u, v)
            rf.append(mb.vert(p + nrm * th / 2))
            rb.append(mb.vert(p - nrm * th / 2))
        front.append(rf); back.append(rb)
    for j in range(nv):
        for i in range(nu):
            mb.face((front[j][i], front[j][i + 1], front[j + 1][i + 1], front[j + 1][i]), M_BANNER)
            mb.face((back[j][i], back[j + 1][i], back[j + 1][i + 1], back[j][i + 1]), M_BANNER)
    for j in range(nv):
        mb.face((front[j][0], front[j + 1][0], back[j + 1][0], back[j][0]), M_BANNER)
        mb.face((front[j][nu], back[j][nu], back[j + 1][nu], front[j + 1][nu]), M_BANNER)
    for i in range(nu):
        mb.face((front[0][i], back[0][i], back[0][i + 1], front[0][i + 1]), M_BANNER)
        mb.face((front[nv][i], front[nv][i + 1], back[nv][i + 1], back[nv][i]), M_BANNER)

    # ribete dorado en los bordes, por delante y por detrás
    def trim_strip(path_uv, width=0.045):
        for side in (-1, 1):
            rows = []
            for k, (u, v) in enumerate(path_uv):
                p = banner_surf(u, v)
                nrm = banner_normal(u, v) * (1 if side == -1 else -1)
                k2 = min(len(path_uv) - 1, k + 1); k1 = max(0, k - 1)
                tan = (banner_surf(*path_uv[k2]) - banner_surf(*path_uv[k1])).normalized()
                inward = nrm.cross(tan).normalized()
                c = Vector((0.5 * BANNER_W, 0, 0)) * 0 + banner_surf(0.5, 0.45)
                if inward.dot(c - p) < 0:
                    inward = -inward
                base = p + nrm * (th / 2 + 0.002)
                rows.append((mb.vert(base), mb.vert(base + inward * width),
                             mb.vert(base + nrm * 0.003), mb.vert(base + inward * width + nrm * 0.003)))
            for k in range(len(rows) - 1):
                a, b = rows[k], rows[k + 1]
                mb.face((a[2], b[2], b[3], a[3]), M_GOLD)
                mb.face((a[0], a[1], b[1], b[0]), M_GOLD)
                mb.face((a[0], b[0], b[2], a[2]), M_GOLD)
                mb.face((a[1], a[3], b[3], b[1]), M_GOLD)
    trim_strip([(0.0, j / 30) for j in range(31)])
    trim_strip([(1.0, j / 30) for j in range(31)])
    trim_strip([(i / 12 * 0.5, 1.0) for i in range(13)])
    trim_strip([(0.5 + i / 12 * 0.5, 1.0) for i in range(13)])

    # emblema: hoja dorada vertical con dos hojas laterales, delante y detrás
    def emblem(lmb, cx, cz, angle, side):
        """Proyecta una hoja plana sobre la tela: la hoja crece hacia arriba desde (cx, cz bajo la barra)."""
        out = MB()
        rot = Matrix.Rotation(angle, 3, "Z")
        for p in lmb.v:
            q = rot @ Vector((p.x, p.y, 0))
            x = cx + q.y
            zd = cz - q.x                     # la hoja crece hacia arriba (zdown disminuye)
            u = max(0, min(1, x / BANNER_W + 0.5))
            v = max(0, min(1, zd / BANNER_L))
            nrm = banner_normal(u, v) * (1 if side == -1 else -1)
            out.v.append(banner_surf(u, v) + nrm * (th / 2 + 0.003 + max(0.0, p.z + 0.004)))
        out.f, out.fm, out.fuv = list(lmb.f), [M_GOLD] * len(lmb.f), [None] * len(lmb.f)
        if side == 1:
            out.f = [tuple(reversed(f)) for f in out.f]
        return out
    big = leaf(0.95, 0.36, thick=0.004, bulge=0.002, nu=12, nv=4)
    small = leaf(0.45, 0.17, thick=0.004, bulge=0.002, nu=8, nv=2)
    stem = leaf(0.5, 0.035, thick=0.004, bulge=0.0, nu=6, nv=2)
    for side in (-1, 1):
        mb.merge(emblem(big, 0.0, 1.55, 0.0, side))
        mb.merge(emblem(stem, 0.0, 2.05, 0.0, side))
        for s in (-1, 1):
            mb.merge(emblem(small, s * 0.03, 1.72, s * math.radians(-40), side))
    # barra dorada con remates
    rod = lathe([(0, -0.7), (0.03, -0.7), (0.03, 0.7), (0, 0.7)], 12, mat=M_GOLD)
    mb.merge(rod, Matrix.Rotation(math.pi / 2, 4, "Y"))
    knob = lathe([(0, 0), (0.045, 0.01), (0.055, 0.05), (0.04, 0.09), (0.02, 0.12), (0, 0.17)], 10, mat=M_GOLD)
    for s in (-1, 1):
        mb.merge(knob, Matrix.Translation((s * 0.7, 0, 0)) @ Matrix.Rotation(s * math.pi / 2, 4, "Y"))
    # soporte que une la barra al pilar (por detrás de la tela, hacia +Y)
    for s in (-1, 1):
        arm = lathe([(0, 0), (0.018, 0), (0.018, 0.12), (0.045, 0.12), (0.045, 0.135), (0, 0.135)], 8, mat=M_GOLD)
        mb.merge(arm, Matrix.Translation((s * 0.3, 0, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "X"))

    def uvmap(co, n):
        return (co.x / BANNER_W + 0.5, 1.0 + co.z / (BANNER_L + BANNER_TIP))

    def wear(co, n):
        return (0.0, 0.2 + 0.4 * smoothstep(-1.5, -3.4, co.z))
    return finalize("SM_Arena_Banner", mb, [mats["marble"], mats["gold"], mats["trim"], mats["joint"], mats["banner"]],
                    col, smooth_angle=60, wear=wear, uv_mode=uvmap)


# ================================================================= principal
def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def clean_unused_slots(ob):
    """Quita ranuras de material que la pieza no usa (para que el FBX no arrastre materiales vacíos)."""
    used = sorted({p.material_index for p in ob.data.polygons})
    mats = [ob.data.materials[i] for i in used]
    remap = {old: new for new, old in enumerate(used)}
    idx = [remap[p.material_index] for p in ob.data.polygons]
    ob.data.materials.clear()
    for m in mats:
        ob.data.materials.append(m)
    for p, i in zip(ob.data.polygons, idx):
        p.material_index = i


def export_fbx(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH"},
        # ejes por defecto de Blender (-Z adelante, Y arriba): el importador de Unreal los convierte a Z arriba
        # y la reimportación en Blender sale sin rotación. FBX_SCALE_NONE con la escena en metros escribe
        # UnitScaleFactor=100, y Unreal importa 1 m = 100 uu (FBX_SCALE_UNITS lo dejaba 100 veces pequeño).
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE", bake_space_transform=False,
        axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE", use_mesh_modifiers=True,
        colors_type="LINEAR", use_tspace=True, add_leaf_bones=False, path_mode="STRIP", embed_textures=False)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    mats = build_materials()
    col = collection("Kit")
    colc = collection("Kit_Collision")
    pieces = {}
    pillar, ucx_p = build_pillar(mats, colc)
    pillar.users_collection[0].objects.unlink(pillar); col.objects.link(pillar)
    pieces["SM_Arena_Pillar"] = (pillar, ucx_p)
    pieces["SM_Arena_Arch"] = (build_arch(mats, col), [])
    floor, ucx_f = build_floor(mats, colc)
    floor.users_collection[0].objects.unlink(floor); col.objects.link(floor)
    pieces["SM_Arena_Floor"] = (floor, ucx_f)
    pieces["SM_Arena_Rim"] = (build_rim(mats, col), [])
    pieces["SM_Arena_Step"] = (build_step(mats, col), [])
    pieces["SM_Arena_Banner"] = (build_banner(mats, col), [])
    for n in ("SM_Arena_PillarOrnament", "SM_Arena_ArchOrnament"):
        ob = bpy.data.objects[n]
        if ob.users_collection[0] != col:
            ob.users_collection[0].objects.unlink(ob); col.objects.link(ob)
        pieces[n] = (ob, [])
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for name, (ob, ucx) in pieces.items():
        clean_unused_slots(ob)
        export_fbx([ob] + ucx, os.path.join(EXPORT_DIR, name + ".fbx"))
        dims = ob.dimensions
        print(f"PIECE {name}: tris={tri_count(ob)} dims={dims.x:.2f}x{dims.y:.2f}x{dims.z:.2f} "
              f"mats={[m.name for m in ob.data.materials]} ucx={len(ucx)}")
    bpy.ops.wm.save_as_mainfile(filepath=KIT_BLEND)
    print("SAVED", KIT_BLEND)


if __name__ == "__main__":
    main()
