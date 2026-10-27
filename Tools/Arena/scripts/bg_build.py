"""Fondo por capas de la Arena del Lago Élfico: genera las piezas en Blender, las exporta a FBX y escribe
bg_layout.json con la colocación (coordenadas de Blender, metros) que lee ue_background.py.

Uso:
  blender -b --factory-startup --python bg_build.py

Capas (de cerca a lejos): acantilados verticales en anfiteatro con rocas de orilla, cascadas (cortina, espuma,
bruma), construcciones élficas (torre, pabellón, puente), árboles en las cornisas, islas flotantes y montañas.
El desfiladero queda abierto hacia el sol (azimut 62°, como en el blockout).
"""
import bpy, bmesh, math, os, sys, json, random
from mathutils import Vector, Matrix, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib, kit_lib
importlib.reload(kit_lib)
from kit_lib import MB, lathe, sweep, chamfer_rect, leaf, ogive, finalize, collection, smoothstep, WORK, hex_rgb
import kit_build
from kit_build import oct_lathe, frame

EXPORT_DIR = os.path.join(WORK, "export")
GEN_DIR = os.path.join(WORK, "assets", "generated")
LAYOUT = os.path.join(WORK, "bg_layout.json")
BLEND = os.path.join(WORK, "background.blend")

SUN_AZ = 62.0
random.seed(11)

# cascadas: (azimut en grados, ancho en m) — repartidas para que se vean desde cam_hero (mira a ~84°)
# y desde la cámara de juego (mira a 0°)
WATERFALLS = [(101, 14), (117, 22), (139, 10), (33, 12), (0, 30), (336, 11), (205, 16)]
# garganta frente a la cámara de juego (mira a 0°): (azimut, semiancho en grados, cuánto baja, cuánto se retira)
GORGES = [(0.0, 7.0, 42.0, 45.0)]


# ---------------------------------------------------------------- utilidades
def angdist(a, b):
    d = (a - b) % 360.0
    return min(d, 360.0 - d)


def an(th, scale, seed, z=0.0):
    """Ruido periódico en el ángulo th (radianes), en [-1, 1]."""
    return noise.noise(Vector((math.cos(th) * scale + seed * 3.7, math.sin(th) * scale - seed * 1.3, z + seed)))


def placeholder(name, color):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = hex_rgb(color)
    return m


MATS = {}


def materials():
    MATS.update({
        "rock": placeholder("M_BG_Rock", "#8C8577"),
        "bark": placeholder("M_BG_Bark", "#5A4A3C"),
        "leaf": placeholder("M_BG_LeafGreen", "#4E7A3A"),
        "lilac": placeholder("M_BG_LeafLilac", "#B59AD8"),
        "mountain": placeholder("M_BG_Mountain", "#7A86A0"),
        "fall": placeholder("M_BG_Waterfall", "#F4F7F8"),
        "foam": placeholder("M_BG_Foam", "#FFFFFF"),
        "mist": placeholder("M_BG_Mist", "#FFFFFF"),
    })
    arena = kit_lib.build_materials()
    MATS["marble"], MATS["gold"] = arena["marble"], arena["gold"]


def no_wear(co, n):
    return (0.0, 0.2)


# ---------------------------------------------------------------- acantilados
NTH = 720


class Cliff:
    """Perfil del anfiteatro: radio de la base r0(θ), altura H(θ) y la cota de la meseta."""

    def __init__(self):
        self.r0, self.H, self.top = [], [], []
        for i in range(NTH):
            th = 2 * math.pi * i / NTH
            deg = math.degrees(th)
            g = 1.0 - smoothstep(9.0, 26.0, angdist(deg, SUN_AZ))          # desfiladero hacia el sol
            r0 = 178 + 30 * an(th, 2.0, 1) + 12 * an(th, 6.0, 2)
            H = 82 + 38 * an(th, 1.5, 3) + 14 * an(th, 5.0, 4)
            r0 = r0 * (1 - g) + (500 + 40 * an(th, 3.0, 5)) * g
            H = H * (1 - g) + (24 + 8 * an(th, 4.0, 6)) * g
            for az, hw, dz, dr in GORGES:                                  # garganta: rompe la pared frontal
                k = 1.0 - smoothstep(hw * 0.35, hw, angdist(deg, az))
                H -= dz * k
                r0 += dr * k
            for az, w in WATERFALLS:                                       # muesca por donde cae el agua
                k = 1.0 - smoothstep(0.5, 2.0 * w / 14.0, angdist(deg, az))
                H -= 9.0 * k
                r0 += 5.0 * k
            self.r0.append(r0)
            self.H.append(H)
            self.top.append([an(th, 9.0, 7), an(th, 4.0, 8)])

    def at(self, deg):
        i = int(round((deg % 360.0) / 360.0 * NTH)) % NTH
        return self.r0[i], self.H[i]

    def plateau_z(self, deg, dr):
        """Cota aproximada de la meseta a dr metros detrás del borde."""
        i = int(round((deg % 360.0) / 360.0 * NTH)) % NTH
        H, (n1, n2) = self.H[i], self.top[i]
        pts = [(1.5, H + 0.8), (5, H + 2.5 + 2 * n1), (25, H + 6 + 6 * n2), (80, H + 14 + 12 * n1)]
        for (r_a, z_a), (r_b, z_b) in zip(pts, pts[1:]):
            if dr <= r_b:
                f = (dr - r_a) / (r_b - r_a)
                return z_a + (z_b - z_a) * max(0.0, f)
        return pts[-1][1]


def build_cliffs(cl, col):
    mb = MB()
    NZ = 44
    rows = []
    for i in range(NTH):
        th = 2 * math.pi * i / NTH
        ct, st = math.cos(th), math.sin(th)
        r0, H = cl.r0[i], cl.H[i]
        n1, n2 = cl.top[i]
        prof = []
        for k in range(NZ + 1):
            z = -5.0 + (H + 5.0) * k / NZ
            strata = 2.6 * noise.noise(Vector((ct * 9, st * 9, z / 3.2)))          # capas horizontales
            ribs = 2.2 * noise.noise(Vector((ct * 70, st * 70, z / 30.0)))         # grietas verticales
            big = 5.0 * noise.noise(Vector((ct * 3, st * 3, z / 22.0)))
            r = r0 + strata + ribs + big + 0.07 * z
            if z < 7:
                r -= (7 - z) * 1.6                                                 # talud que entra en el agua
            r -= 2.5 * smoothstep(H - 9, H, z)                                     # cornisa volada
            prof.append((r, z))
        prof += [(r0 + 1.5, H + 0.8), (r0 + 5, H + 2.5 + 2 * n1), (r0 + 25, H + 6 + 6 * n2),
                 (r0 + 80, H + 14 + 12 * n1), (r0 + 240, H + 30)]
        rows.append([mb.vert((r * ct, r * st, z)) for r, z in prof])
    n = len(rows[0])
    for i in range(NTH):
        A, B = rows[i], rows[(i + 1) % NTH]
        for k in range(n - 1):
            mb.face((A[k], A[k + 1], B[k + 1], B[k]))

    def wear(co, nrm):
        n1 = noise.noise(co * 0.04) * 0.5 + 0.5
        n2 = noise.noise(co * 0.15 + Vector((3, 1, 7))) * 0.5 + 0.5
        low = 1.0 - smoothstep(1.0, 14.0, co.z)
        moss = max(low * 0.9, smoothstep(0.55, 0.75, n1) * 0.6) * (0.6 + 0.4 * n2)
        return (min(1, moss), 0.2 + 0.5 * n2)
    # caras construidas mirando al lago (z x tangente); no se recalculan
    return finalize("SM_BG_Cliffs", mb, [MATS["rock"]], col, tile=8.0, smooth_angle=50, wear=wear, recalc=False)


def boulder(size, seed, subdiv=2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    mb = MB()
    idx = {}
    off = Vector((seed * 7.1, seed * 3.3, seed * 1.7))
    for v in bm.verts:
        p = v.co.copy()
        d = 1.0 + 0.35 * noise.noise(p * 1.3 + off) + 0.12 * noise.noise(p * 4.0 + off)
        p = Vector((p.x * d * size * 1.2, p.y * d * size, p.z * d * size * 0.7))
        if p.z < -0.2 * size:
            p.z = -0.2 * size + (p.z + 0.2 * size) * 0.3                         # base aplastada
        idx[v.index] = mb.vert(p)
    for f in bm.faces:
        mb.face([idx[v.index] for v in f.verts])
    bm.free()
    return mb


def build_shore_rocks(cl, col):
    mb = MB()
    for j in range(260):
        deg = random.uniform(0, 360)
        if angdist(deg, SUN_AZ) < 14:
            continue
        r0, _ = cl.at(deg)
        r = r0 - random.uniform(4, 22) ** 1.0
        s = random.uniform(1.2, 6.5) * (1.6 if random.random() < 0.15 else 1.0)
        th = math.radians(deg)
        m = Matrix.Translation((r * math.cos(th), r * math.sin(th), random.uniform(-1.5, 0.3))) \
            @ Matrix.Rotation(random.uniform(0, 6.28), 4, "Z")
        mb.merge(boulder(s, j), m)

    def wear(co, nrm):
        return (smoothstep(0.2, 0.8, nrm.z) * 0.9, 0.3)
    return finalize("SM_BG_ShoreRocks", mb, [MATS["rock"]], col, tile=4.0, smooth_angle=60, wear=wear)


# ---------------------------------------------------------------- árboles
def tree(height, lilac, seed):
    rnd = random.Random(seed)
    mb = MB()
    tr = height * 0.035
    mb.merge(lathe([(0, -1.5), (tr * 1.4, -1.5), (tr, height * 0.55), (tr * 0.5, height * 0.8), (0, height * 0.82)], 6))
    leafmat = 2 if lilac else 1
    # copa de muchos lóbulos: unos grandes que dan la masa y otros pequeños que rompen la silueta
    lobes = [(height * rnd.uniform(0.15, 0.22), 0.12) for _ in range(rnd.randint(3, 4))]
    lobes += [(height * rnd.uniform(0.07, 0.12), 0.26) for _ in range(rnd.randint(7, 11))]
    for k, (s, spread) in enumerate(lobes):
        a = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0.0, height * spread)
        z = height * rnd.uniform(0.55, 0.92)
        b = boulder(s, seed * 13 + k, subdiv=1)
        mb.merge(b, Matrix.Translation((rr * math.cos(a), rr * math.sin(a), z)), mat=leafmat)
    return mb


def build_trees(cl, col):
    mb = MB()
    count = 0
    for j in range(1400):
        deg = random.uniform(0, 360)
        d_gap = angdist(deg, SUN_AZ)
        if d_gap < 8:
            continue
        # más densos junto al borde
        dr = 4 + random.random() ** 2.2 * 70
        r0, H = cl.at(deg)
        th = math.radians(deg)
        r = r0 + dr
        z = cl.plateau_z(deg, dr)
        h = random.uniform(9, 22)
        lilac = random.random() < 0.33
        t = tree(h, lilac, j)
        mb.merge(t, Matrix.Translation((r * math.cos(th), r * math.sin(th), z)) @ Matrix.Rotation(random.uniform(0, 6.28), 4, "Z"))
        count += 1
        if count >= 650:
            break

    def wear(co, nrm):
        return (0.0, noise.noise(co * 0.02) * 0.5 + 0.5)        # G: variación de tono entre copas
    return finalize("SM_BG_Trees", mb, [MATS["bark"], MATS["leaf"], MATS["lilac"]], col, tile=4.0,
                    smooth_angle=70, wear=wear)


# ---------------------------------------------------------------- cascadas
def build_waterfall_pieces(col):
    # cortina unidad: 1 m de ancho, cae de z=0 a z=-1, se separa de la pared hacia -Y (la escala Y da el vuelo)
    mb = MB()
    NU, NV = 8, 28
    grid = []
    for j in range(NV + 1):
        t = j / NV
        y = -(1 - (1 - t) ** 2.2)
        row = []
        for i in range(NU + 1):
            u = i / NU
            x = (u - 0.5) * (1 + 0.25 * t)                           # se abre al caer
            row.append(mb.vert((x, y, -t)))
        grid.append(row)
    for j in range(NV):
        for i in range(NU):
            mb.face((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1]))
    fall = finalize("SM_BG_Waterfall", mb, [MATS["fall"]], col, smooth_angle=89, wear=no_wear,
                    uv_mode=lambda co, n: (co.x / (1 + 0.25 * -co.z) + 0.5, -co.z))
    # espuma: disco de radio 1 con UV radial (u = ángulo, v = radio)
    mb = MB()
    NA, NR = 32, 5
    rings = []
    for k in range(NR + 1):
        rr = k / NR
        rings.append([mb.vert((rr * math.cos(2 * math.pi * a / NA), rr * math.sin(2 * math.pi * a / NA),
                               0.15 * (1 - rr * rr))) for a in range(NA)])
    for k in range(NR):
        for a in range(NA):
            b = (a + 1) % NA
            mb.face((rings[k][a], rings[k][b], rings[k + 1][b], rings[k + 1][a]))
    foam = finalize("SM_BG_Foam", mb, [MATS["foam"]], col, smooth_angle=89, wear=no_wear,
                    uv_mode=lambda co, n: ((math.atan2(co.y, co.x) / (2 * math.pi)) % 1.0, math.hypot(co.x, co.y)))
    # bruma: tres tarjetas verticales cruzadas de 1x1 m (base en z=0)
    mb = MB()
    for k in range(3):
        a = k * math.pi / 3
        dx, dy = math.cos(a) * 0.5, math.sin(a) * 0.5
        v = [mb.vert((-dx, -dy, 0)), mb.vert((dx, dy, 0)), mb.vert((dx, dy, 1)), mb.vert((-dx, -dy, 1))]
        mb.face(v)
    mist = finalize("SM_BG_Mist", mb, [MATS["mist"]], col, smooth_angle=89, wear=no_wear,
                    uv_mode=lambda co, n: (1.0 if 0 <= math.atan2(co.y, co.x) < math.pi else 0.0, co.z))
    return fall, foam, mist


def build_foam_ring(col):
    """Anillo de espuma alrededor de los escalones (r 15,1 a 17,5 m): v = 0 en el contacto, 1 hacia fuera."""
    mb = MB()
    NA, NR, R0, R1 = 128, 4, 15.1, 17.5
    rings = []
    for k in range(NR + 1):
        r = R0 + (R1 - R0) * k / NR
        rings.append([mb.vert((r * math.cos(2 * math.pi * a / NA), r * math.sin(2 * math.pi * a / NA), 0.0))
                      for a in range(NA)])
    for k in range(NR):
        for a in range(NA):
            b = (a + 1) % NA
            mb.face((rings[k][a], rings[k][b], rings[k + 1][b], rings[k + 1][a]))
    return finalize("SM_BG_FoamRing", mb, [MATS["foam"]], col, smooth_angle=89, wear=no_wear, recalc=False,
                    uv_mode=lambda co, n: ((math.atan2(co.y, co.x) / (2 * math.pi)) % 1.0 * 24.0,
                                           (math.hypot(co.x, co.y) - R0) / (R1 - R0)))


# ---------------------------------------------------------------- construcciones élficas
M, G_ = 0, 1


def build_tower(col):
    mb = MB()
    mb.merge(oct_lathe([(0, -6), (3.3, -6), (3.3, 2.6), (3.0, 3.0), (0, 3.0)]))
    mb.merge(lathe([(0, 3), (2.4, 3), (2.25, 12), (2.1, 18.5), (0, 18.5)], 16))
    for z in (8.0, 14.0):
        mb.merge(lathe([(2.2, z), (2.42, z), (2.42, z + 0.3), (2.2, z + 0.3)], 16, mat=G_))
    mb.merge(lathe([(0, 18.4), (2.1, 18.4), (2.9, 19.4), (3.1, 19.6), (3.1, 20.3), (0, 20.3)], 16))
    mb.merge(lathe([(0, 20.3), (1.75, 20.3), (1.7, 25.0), (0, 25.0)], 16))
    mb.merge(oct_lathe([(1.5, 25.0), (1.85, 25.0), (1.85, 25.35), (1.5, 25.35)], G_))
    mb.merge(oct_lathe([(0, 25.35), (2.15, 25.35), (2.15, 25.8), (0, 25.8)]))
    S0, S1, SR = 25.8, 37.5, 1.95
    mb.merge(oct_lathe([(0, S0), (SR, S0), (0.05, S1), (0, S1)]))
    for k in range(4):
        a = math.pi / 8 + k * math.pi / 2
        ed = Vector((math.cos(a), math.sin(a), 0))
        up = (Vector((0, 0, S1 - S0)) - ed * (SR - 0.05)).normalized()
        out = (ed - up * ed.dot(up)).normalized()
        for j in range(5):
            t = 0.12 + 0.17 * j
            r = SR * (1 - t)
            X = (up * 0.64 + out * 0.77).normalized()
            mb.merge(leaf(1.3 * (1 - 0.12 * j), 0.65 * (1 - 0.12 * j), thick=0.12, bulge=0.1, curl=2.5, nu=6, nv=2),
                     frame(X, out, ed * (r - 0.04) + out * 0.1 + Vector((0, 0, S0 + (S1 - S0) * t))))
    mb.merge(lathe([(0, S1 - 0.3), (0.16, S1 - 0.1), (0.22, S1 + 0.3), (0.12, S1 + 0.8), (0, S1 + 1.6)], 8, mat=G_))
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        p = Vector((2.75 * math.cos(a), 2.75 * math.sin(a), 0))
        mb.merge(oct_lathe([(0, 20.3), (0.25, 20.3), (0.25, 22.0), (0, 24.2)]), Matrix.Translation(p))
    return finalize("SM_BG_Tower", mb, [MATS["marble"], MATS["gold"]], col, tile=2.0, wear=lambda c, n: (0.0, 0.25))


def build_pavilion(col):
    mb = MB()
    mb.merge(lathe([(0, -4), (6.4, -4), (6.4, 0.4), (5.9, 0.45), (5.9, 0.8), (5.4, 0.85), (5.4, 1.1), (0, 1.1)], 32))
    NCOL, RC = 8, 4.6
    for k in range(NCOL):
        a = 2 * math.pi * k / NCOL
        m = Matrix.Translation((RC * math.cos(a), RC * math.sin(a), 0))
        mb.merge(lathe([(0, 1.1), (0.45, 1.1), (0.45, 1.4), (0.3, 1.6), (0.28, 7.4), (0.42, 7.8), (0.48, 8.0), (0, 8.0)], 12), m)
    # arcos apuntados entre columnas
    chord = 2 * RC * math.sin(math.pi / NCOL)
    for k in range(NCOL):
        a0 = 2 * math.pi * k / NCOL
        a1 = 2 * math.pi * (k + 1) / NCOL
        p0 = Vector((RC * math.cos(a0), RC * math.sin(a0), 0))
        p1 = Vector((RC * math.cos(a1), RC * math.sin(a1), 0))
        mid = (p0 + p1) / 2
        u = (p1 - p0).normalized()
        pts = [Vector((x, 0, z + 5.6)) for x, z in ogive(chord - 0.6, 0.62, 0.15, 14)]
        rot = Matrix((u, Vector((0, 0, 1)).cross(u), Vector((0, 0, 1)))).transposed().to_4x4()
        rot.translation = mid
        mb.merge(sweep(pts, chamfer_rect(0.16, 0.22, 0.05), Vector((0, 1, 0))), rot)
    mb.merge(lathe([(4.1, 8.0), (5.1, 8.0), (5.25, 8.3), (5.25, 8.7), (4.1, 8.7)], 32))
    mb.merge(lathe([(4.9, 8.7), (5.0, 8.7), (5.0, 8.9), (4.9, 8.9)], 32, mat=G_))
    dome = [(0, 8.7)]
    for i in range(13):                                           # cúpula apuntada
        t = i / 12
        ang = t * math.radians(75)
        r = 4.95 * (math.cos(ang) - math.cos(math.radians(75)) * t) / 1.0
        dome.append((max(0.0, r), 8.9 + 6.2 * math.sin(ang) ** 1.1 + 1.2 * t ** 3))
    dome.append((0, dome[-1][1]))
    mb.merge(lathe(dome, 32))
    top = dome[-1][1]
    mb.merge(lathe([(0, top - 0.2), (0.35, top), (0.3, top + 0.8), (0.18, top + 1.2), (0.22, top + 1.5), (0, top + 2.6)], 10, mat=G_))
    return finalize("SM_BG_Pavilion", mb, [MATS["marble"], MATS["gold"]], col, tile=2.0, wear=lambda c, n: (0.0, 0.25))


def build_bridge(col):
    """Puente-arco de 40 m (luz según X) con pila en cada extremo; el tablero queda en z = 0."""
    mb = MB()
    L, Wd = 40.0, 4.2
    Y = Vector((0, 1, 0))
    deck = [Vector((x, 0, -0.5 + 1.6 * (1 - (2 * x / L) ** 2))) for x in [(-L / 2) + L * i / 32 for i in range(33)]]
    mb.merge(sweep(deck, chamfer_rect(0.5, Wd / 2, 0.12), Y))
    arch = [Vector((x, 0, z - 13.5)) for x, z in ogive(L - 6, 0.72, 0.6, 24)]
    mb.merge(sweep(arch, chamfer_rect(0.6, 1.6, 0.15), Y))
    for i in range(1, 16):                                         # montantes entre arco y tablero
        x = -L / 2 + 3 + (L - 6) * i / 16
        za = min(p.z for p in arch if abs(p.x - x) < 1.5) if any(abs(p.x - x) < 1.5 for p in arch) else -10
        zd = -0.5 + 1.6 * (1 - (2 * x / L) ** 2) - 0.5
        if zd - za > 0.6:
            mb.merge(lathe([(0, za), (0.22, za), (0.22, zd), (0, zd)], 8), Matrix.Translation((x, 0, 0)))
    for s in (-1, 1):                                              # barandillas y pilas
        rail = [Vector((p.x, s * (Wd / 2 - 0.15), p.z + 1.1)) for p in deck]
        mb.merge(sweep(rail, chamfer_rect(0.08, 0.1, 0.03), Y))
        for i in range(0, 33, 2):
            p = deck[i]
            mb.merge(lathe([(0, p.z + 0.4), (0.09, p.z + 0.4), (0.09, p.z + 1.1), (0, p.z + 1.1)], 6),
                     Matrix.Translation((p.x, s * (Wd / 2 - 0.15), 0)))
        mb.merge(oct_lathe([(0, -30), (2.6, -30), (2.6, 0.6), (2.0, 1.2), (0, 1.2)]),
                 Matrix.Translation((s * L / 2, 0, 0)))
        mb.merge(oct_lathe([(0, 1.2), (0.5, 1.2), (0.5, 3.2), (0, 5.4)]), Matrix.Translation((s * L / 2, s * 1.6, 0)))
        mb.merge(lathe([(0, 5.2), (0.12, 5.3), (0, 6.0)], 8, mat=G_), Matrix.Translation((s * L / 2, s * 1.6, 0)))
    return finalize("SM_BG_Bridge", mb, [MATS["marble"], MATS["gold"]], col, tile=2.0, wear=lambda c, n: (0.0, 0.3))


# ---------------------------------------------------------------- islas flotantes
def build_island(name, R, depth, seed, ntrees, col):
    rnd = random.Random(seed)
    mb = MB()
    NA = 64
    off = seed * 5.0
    edge = [R * (1 + 0.2 * noise.noise(Vector((math.cos(2 * math.pi * a / NA) * 1.5 + off, math.sin(2 * math.pi * a / NA) * 1.5, 0))))
            for a in range(NA)]
    rings = []
    NT = 6
    for k in range(NT + 1):                                        # cara superior (hierba por orientación)
        f = k / NT
        ring = []
        for a in range(NA):
            th = 2 * math.pi * a / NA
            r = edge[a] * f
            z = 2.5 * (1 - f * f) + 1.2 * noise.noise(Vector((math.cos(th) * r * 0.1 + off, math.sin(th) * r * 0.1, 3)))
            ring.append(mb.vert((r * math.cos(th), r * math.sin(th), z)))
        rings.append(ring)
    NB = 12
    for k in range(1, NB + 1):                                     # panza de roca colgante
        f = k / NB
        ring = []
        for a in range(NA):
            th = 2 * math.pi * a / NA
            lump = 1 + 0.25 * noise.noise(Vector((math.cos(th) * 2 + off, math.sin(th) * 2, f * 3)))
            r = edge[a] * (1 - f ** 0.75) * lump + 0.02
            z = -depth * f ** 1.25 * (1 + 0.15 * noise.noise(Vector((math.cos(th) * 3, math.sin(th) * 3 + off, 1))))
            ring.append(mb.vert((r * math.cos(th), r * math.sin(th), z)))
        rings.append(ring)
    # orden de los anillos: centro arriba -> borde -> panza -> punta
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for a in range(NA):
            b = (a + 1) % NA
            mb.face((A[a], A[b], B[b], B[a]))
    # estalactitas
    for j in range(int(R / 2)):
        th = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0.1, 0.6) * R
        z0 = -depth * (1 - (rr / R)) ** 1.3 * 0.9
        L = rnd.uniform(0.15, 0.45) * depth
        mb.merge(lathe([(0, 0.5), (R * 0.07, 0.5), (R * 0.03, -L * 0.6), (0, -L)], 6),
                 Matrix.Translation((rr * math.cos(th), rr * math.sin(th), z0)))
    # raíces colgantes desde el borde
    for j in range(int(R * 0.6)):
        a = rnd.randrange(NA)
        th = 2 * math.pi * a / NA
        r = edge[a] * 0.95
        L = rnd.uniform(0.25, 0.7) * depth
        sway = rnd.uniform(-1, 1) * 0.15 * L
        pts = [Vector(((r + sway * t) * math.cos(th) - 0.1 * t * L * math.sin(th) * 0.3,
                       (r + sway * t) * math.sin(th), -L * t ** 1.1 - 0.5)) for t in [i / 8 for i in range(9)]]
        rad = max(0.08, R * 0.006)
        prof = [(rad * math.cos(2 * math.pi * q / 5), rad * math.sin(2 * math.pi * q / 5)) for q in range(5)]
        mb.merge(sweep(pts, prof, Vector((-math.sin(th), math.cos(th), 0)), mat=1))
    # árboles en lo alto
    for j in range(ntrees):
        th = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0.15, 0.75) * R
        h = rnd.uniform(0.12, 0.25) * R
        start = len(mb.fm)
        mb.merge(tree(h, rnd.random() < 0.4, seed * 100 + j), Matrix.Translation((rr * math.cos(th), rr * math.sin(th), 1.0)))
        for i in range(start, len(mb.fm)):        # árbol: 0 corteza, 1 verde, 2 lila -> ranuras 1, 2, 3 de la isla
            mb.fm[i] += 1

    def wear(co, nrm):
        return (smoothstep(0.3, 0.7, nrm.z) * 0.5, 0.3)
    # ranuras: 0 roca, 1 corteza (raíces y troncos), 2 hoja verde, 3 hoja lila
    return finalize(name, mb, [MATS["rock"], MATS["bark"], MATS["leaf"], MATS["lilac"]], col, tile=6.0,
                    smooth_angle=55, wear=wear)


# ---------------------------------------------------------------- montañas
def build_mountains(col):
    mb = MB()
    NA, NR = 360, 34
    rs = [1300 + (3900 - 1300) * (k / (NR - 1)) ** 1.3 for k in range(NR)]
    rows = []
    for a in range(NA):
        th = 2 * math.pi * a / NA
        deg = math.degrees(th)
        gap = 1.0 - smoothstep(6.0, 22.0, angdist(deg, SUN_AZ))
        row = []
        for k, r in enumerate(rs):
            x, y = r * math.cos(th), r * math.sin(th)
            env = smoothstep(1300, 2300, r) * (1 - smoothstep(3500, 3900, r))
            rid = noise.ridged_multi_fractal(Vector((x / 1100, y / 1100, 0.3)), 1.0, 2.1, 6, 1.0, 2.0)
            h = 60 + 950 * env * max(0.0, rid - 0.35) + 120 * env * (noise.noise(Vector((x / 400, y / 400, 2))) * 0.5 + 0.5)
            if gap > 0:
                h = h * (1 - gap) + min(h, 260 + 0.12 * (r - 1300)) * gap
            if k == NR - 1:
                h = -80
            row.append(mb.vert((x, y, h)))
        rows.append(row)
    for a in range(NA):
        A, B = rows[a], rows[(a + 1) % NA]
        for k in range(NR - 1):
            mb.face((A[k], A[k + 1], B[k + 1], B[k]))          # normal hacia arriba
    return finalize("SM_BG_Mountains", mb, [MATS["mountain"]], col, tile=200.0, smooth_angle=60, wear=no_wear,
                    recalc=False)


# ---------------------------------------------------------------- texturas generadas
def save_texture(name, size, fn):
    os.makedirs(GEN_DIR, exist_ok=True)
    img = bpy.data.images.new(name, size, size, alpha=True)
    px = [0.0] * (size * size * 4)
    for y in range(size):
        v = y / size
        for x in range(size):
            u = x / size
            r, g, b, a = fn(u, v)
            i = (y * size + x) * 4
            px[i:i + 4] = (r, g, b, a)
    img.pixels = px
    img.filepath_raw = os.path.join(GEN_DIR, name + ".png")
    img.file_format = "PNG"
    img.save()
    return img.filepath_raw


def streak(u, v):
    # vetas verticales que repiten en v (para desplazarlas hacia abajo sin costura)
    c, s = math.cos(2 * math.pi * v), math.sin(2 * math.pi * v)
    p = Vector((u * 14.0, c * 1.2, s * 1.2))
    n = noise.fractal(p, 0.6, 2.0, 5) * 0.5 + 0.5
    fine = noise.noise(Vector((u * 60, c * 3, s * 3))) * 0.5 + 0.5
    val = max(0.0, min(1.0, 0.25 + 0.9 * n * (0.6 + 0.4 * fine)))
    return (val, val, val, 1.0)


def mist(u, v):
    d = math.hypot(u - 0.5, v - 0.5) * 2
    fall = max(0.0, 1 - d) ** 1.6
    n = noise.fractal(Vector((u * 4, v * 4, 0.7)), 0.7, 2.0, 4) * 0.5 + 0.5
    a = max(0.0, min(1.0, fall * (0.4 + 0.8 * n)))
    return (1.0, 1.0, 1.0, a)


# ---------------------------------------------------------------- colocación
def P(x, y, z):
    return [round(x, 3), round(y, 3), round(z, 3)]


def layout(cl):
    L = {"note": "Coordenadas de Blender en metros (Z arriba). ue_background.py convierte a Unreal (Y reflejado, cm).",
         "static": [], "waterfalls": [], "islands": []}
    for n in ("SM_BG_Cliffs", "SM_BG_ShoreRocks", "SM_BG_Trees", "SM_BG_Mountains"):
        L["static"].append({"mesh": n, "loc": P(0, 0, 0), "yaw": 0.0, "scale": [1, 1, 1]})
    # cascadas en las muescas
    for i, (az, w) in enumerate(WATERFALLS):
        r0, H = cl.at(az)
        th = math.radians(az)
        top = H + 0.5
        rt = r0 + 1.5
        L["waterfalls"].append({
            "name": f"Waterfall_{i}", "loc": P(rt * math.cos(th), rt * math.sin(th), top), "yaw": az - 90.0,
            "width": w, "height": top, "throw": 9.0 + top * 0.08,
            "base": P((r0 - 5) * math.cos(th), (r0 - 5) * math.sin(th), 0.1)})
    # construcciones: torres junto a cascadas, pabellón en un saliente, puente sobre una muesca
    def on_top(az, dr, mesh, yaw_off=0.0, extra_z=0.0, scale=1.0):
        r0, H = cl.at(az)
        th = math.radians(az)
        r = r0 + dr
        L["static"].append({"mesh": mesh, "loc": P(r * math.cos(th), r * math.sin(th), cl.plateau_z(az, dr) + extra_z - 0.5),
                            "yaw": az + yaw_off, "scale": [scale] * 3})
    on_top(97.0, 14, "SM_BG_Tower")
    on_top(121.5, 16, "SM_BG_Tower", scale=1.15)
    on_top(126.0, 30, "SM_BG_Tower", scale=0.8)
    on_top(143.0, 12, "SM_BG_Pavilion")
    on_top(29.0, 12, "SM_BG_Tower", scale=0.9)
    on_top(16.5, 20, "SM_BG_Pavilion", scale=1.1)
    on_top(341.0, 14, "SM_BG_Tower")
    on_top(208.0, 15, "SM_BG_Tower", scale=1.2)
    on_top(77.0, 14, "SM_BG_Tower", scale=0.85)                 # a la entrada del desfiladero
    for az in (117, 336):                                         # puentes sobre dos cascadas
        r0, H = cl.at(az)
        _, Hl = cl.at(az - 4)
        th = math.radians(az)
        r = r0 + 6
        L["static"].append({"mesh": "SM_BG_Bridge", "loc": P(r * math.cos(th), r * math.sin(th), Hl + 1.5),
                            "yaw": az + 90.0, "scale": [1, 1, 1]})
    # islas flotantes: tamaños muy distintos; la grande, cercana y a la izquierda del encuadre héroe
    islands = [
        ("SM_BG_Island_A", 1.0, 80, 230, 72, [("SM_BG_Tower", 6, 30, 1.0), ("SM_BG_Tower", -14, 200, 0.7),
                                               ("SM_BG_Pavilion", 18, 120, 0.9)]),
        ("SM_BG_Island_B", 1.0, 47, 620, 240, [("SM_BG_Tower", 4, 0, 0.8)]),
        ("SM_BG_Island_C", 1.0, 150, 520, 210, [("SM_BG_Tower", 2, 0, 0.5)]),
        ("SM_BG_Island_B", 0.6, 28, 650, 300, [("SM_BG_Tower", 3, 0, 0.5)]),
        ("SM_BG_Island_C", 1.4, 352, 420, 175, [("SM_BG_Pavilion", 0, 0, 0.7)]),
        ("SM_BG_Island_C", 0.7, 200, 380, 160, []),
    ]
    for mesh, s, az, dist, h, builds in islands:
        th = math.radians(az)
        cx, cy = dist * math.cos(th), dist * math.sin(th)
        yaw = random.uniform(0, 360)
        isl = {"mesh": mesh, "loc": P(cx, cy, h), "yaw": yaw, "scale": [s, s, s], "buildings": []}
        R = {"SM_BG_Island_A": 38, "SM_BG_Island_B": 20, "SM_BG_Island_C": 10}[mesh] * s
        for bmesh_, rr, ang, bs in builds:
            a = math.radians(ang + yaw)
            isl["buildings"].append({"mesh": bmesh_, "loc": P(cx + rr * s * math.cos(a), cy + rr * s * math.sin(a), h + 1.2 * s),
                                     "yaw": ang, "scale": [bs * s] * 3})
        # hilo de agua desde el borde
        a = math.radians(yaw + 75)
        isl["thread"] = {"loc": P(cx + R * 0.92 * math.cos(a), cy + R * 0.92 * math.sin(a), h + 0.5),
                         "yaw": yaw + 75 - 90, "width": max(2.5, R * 0.2), "height": min(h * 0.4, 70.0)}
        L["islands"].append(isl)
    # bandas de bruma al pie de los acantilados, sobre todo frente a la cámara de juego (0°)
    L["mists"] = []
    for az in [-18, 0, 18, 101, 117]:
        r0, _ = cl.at(az)
        th = math.radians(az)
        r = r0 - 18
        L["mists"].append({"loc": P(r * math.cos(th), r * math.sin(th), 0.0), "yaw": az + 15.0,
                           "scale": [70.0, 70.0, 28.0 if abs(((az + 180) % 360) - 180) < 40 else 20.0]})
    # espuma al pie de la plataforma (el anillo se coloca en el origen)
    L["static"].append({"mesh": "SM_BG_FoamRing", "loc": P(0, 0, 0.02), "yaw": 0.0, "scale": [1, 1, 1]})
    with open(LAYOUT, "w", encoding="utf-8") as f:
        json.dump(L, f, indent=1, ensure_ascii=False)
    return L


# ---------------------------------------------------------------- principal
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    materials()
    col = collection("Background")
    cl = Cliff()
    objs = [build_cliffs(cl, col), build_shore_rocks(cl, col), build_trees(cl, col), build_mountains(col)]
    objs += list(build_waterfall_pieces(col))
    objs.append(build_foam_ring(col))
    objs += [build_tower(col), build_pavilion(col), build_bridge(col)]
    objs += [build_island("SM_BG_Island_A", 38, 55, 3, 9, col), build_island("SM_BG_Island_B", 20, 30, 5, 4, col),
             build_island("SM_BG_Island_C", 10, 16, 7, 1, col)]
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for ob in objs:
        kit_build.clean_unused_slots(ob)
        kit_build.export_fbx([ob], os.path.join(EXPORT_DIR, ob.name + ".fbx"))
        d = ob.dimensions
        print(f"PIECE {ob.name}: tris={kit_build.tri_count(ob)} dims={d.x:.1f}x{d.y:.1f}x{d.z:.1f} "
              f"mats={[m.name for m in ob.data.materials]}")
    layout(cl)
    print("LAYOUT", LAYOUT)
    print("TEX", save_texture("T_BG_WaterStreak", 256, streak))
    print("TEX", save_texture("T_BG_Mist", 128, mist))
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("SAVED", BLEND)


main()
