import trimesh
import pathlib

ply_path = pathlib.Path(__file__).parent.parent / "trial" / "Nexus - Photogrammetry1" / "s1-86846 (NEXUS).ply"
print(f"Loading: {ply_path}")

mesh = trimesh.load(str(ply_path), force="mesh")
print(f"OK: loaded mesh")
print(f"  Triangles : {len(mesh.faces):,}")
print(f"  Vertices  : {len(mesh.vertices):,}")
print(f"  Bounds    : min={mesh.bounds[0]}, max={mesh.bounds[1]}")
print(f"  Is watertight: {mesh.is_watertight}")
