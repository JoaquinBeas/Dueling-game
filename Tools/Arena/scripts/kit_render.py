"""Render de prueba del kit: abre arena.blend (misma luz y cámaras del blockout), sustituye la arena y los
pilares del blockout por las piezas de kit.blend montadas en el anillo de 4 pares y renderiza.

Uso:
  blender -b --factory-startup --python kit_render.py -- [--render cam_hero,cam_kit_arch] [--samples N]
"""
import bpy, math, os, sys, time
from mathutils import Vector

WORK = r"D:\Repos\_arena_work"
OUT = os.path.join(WORK, "renders", "02_kit")
PILLAR_RING_R = 15.6
PAIR_CENTERS = [45, 135, 225, 315]
PAIR_SPREAD = 20.0
BANNER_Z = 5.45
BANNER_OFFSET = 0.52


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    which, samples = ["cam_hero", "cam_kit_pillar", "cam_kit_arch", "cam_kit_capital", "cam_gameplay", "cam_wide"], 64
    for i, a in enumerate(argv):
        if a == "--render":
            which = argv[i + 1].split(",")
        elif a == "--samples":
            samples = int(argv[i + 1])

    bpy.ops.wm.open_mainfile(filepath=os.path.join(WORK, "arena.blend"))
    sc = bpy.context.scene
    # fuera la arena y los pilares del blockout
    for cname in ("Arena", "Pillars"):
        c = bpy.data.collections.get(cname)
        if c:
            for ob in list(c.objects):
                bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.collections.remove(c)
    # traer las piezas del kit
    names = ["SM_Arena_Pillar", "SM_Arena_Arch", "SM_Arena_Floor", "SM_Arena_Rim", "SM_Arena_Step", "SM_Arena_Banner"]
    with bpy.data.libraries.load(os.path.join(WORK, "kit.blend"), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in names]
    proto = {o.name: o for o in dst.objects}
    col = bpy.data.collections.new("Kit_Assembly")
    sc.collection.children.link(col)
    # perspectiva atmosférica igual que el resto de la escena
    fog = bpy.data.node_groups.get("AtmoFog")
    for m in {m for o in proto.values() for m in o.data.materials}:
        nt = m.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        if fog:
            g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = fog
            nt.links.new(bsdf.outputs[0], g.inputs[0]); nt.links.new(g.outputs[0], out.inputs["Surface"])

    def inst(name, loc, rot_z):
        o = bpy.data.objects.new(name + "_inst", proto[name].data)
        o.location = loc
        o.rotation_euler = (0, 0, rot_z)
        col.objects.link(o)
        return o
    for n in ("SM_Arena_Floor", "SM_Arena_Rim", "SM_Arena_Step"):
        inst(n, (0, 0, 0), 0)
    for c in PAIR_CENTERS:
        for s in (-1, 1):
            a = math.radians(c + s * PAIR_SPREAD / 2)
            pos = Vector((math.cos(a), math.sin(a), 0)) * PILLAR_RING_R
            inst("SM_Arena_Pillar", pos, a)
            inward = -Vector((math.cos(a), math.sin(a), 0))
            inst("SM_Arena_Banner", pos + inward * BANNER_OFFSET + Vector((0, 0, BANNER_Z)), a - math.pi / 2)
        cr = math.radians(c)
        mid = Vector((math.cos(cr), math.sin(cr), 0)) * PILLAR_RING_R * math.cos(math.radians(PAIR_SPREAD / 2))
        inst("SM_Arena_Arch", mid, cr + math.pi / 2)

    # cámaras de detalle, mirando al par de 225° (de frente al sol, que entra desde 62°)
    cams = {o.name: o for o in bpy.data.objects if o.type == "CAMERA"}
    ccol = bpy.data.collections.get("Cameras") or sc.collection

    def cam(name, loc, target, lens):
        d = bpy.data.cameras.new(name); d.lens = lens; d.clip_start = 0.05; d.clip_end = 8000
        o = bpy.data.objects.new(name, d); o.location = loc
        ccol.objects.link(o); look_at(o, target); cams[name] = o
    a = math.radians(225 + PAIR_SPREAD / 2)
    ppos = Vector((math.cos(a), math.sin(a), 0)) * PILLAR_RING_R
    inward = -Vector((math.cos(a), math.sin(a), 0))
    side = Vector((-inward.y, inward.x, 0))
    cam("cam_kit_pillar", ppos + inward * 9.5 + side * 1.5 + Vector((0, 0, 2.6)), ppos + Vector((0, 0, 5.4)), 17)
    cam("cam_kit_capital", ppos + inward * 3.0 + side * 0.9 + Vector((0, 0, 5.2)), ppos + Vector((0, 0, 6.2)), 30)
    cr = math.radians(225)
    mid = Vector((math.cos(cr), math.sin(cr), 0)) * PILLAR_RING_R * math.cos(math.radians(PAIR_SPREAD / 2))
    cam("cam_kit_arch", mid - Vector((math.cos(cr), math.sin(cr), 0)) * 6.5 + Vector((0, 0, 6.4)), mid + Vector((0, 0, 8.3)), 26)

    os.makedirs(OUT, exist_ok=True)
    sc.eevee.taa_render_samples = samples
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "kit_test.blend"))
    for name in which:
        sc.camera = cams[name]
        sc.render.filepath = os.path.join(OUT, f"{name}.png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {name} {time.time() - t0:.1f}s")


main()
