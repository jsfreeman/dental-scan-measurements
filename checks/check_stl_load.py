import trimesh
import pathlib

stl_path = pathlib.Path(__file__).parent.parent / "trial" / "Desktop Scanner" / "s1-86846A (Desktop).stl"
print(f"Loading: {stl_path}")

mesh = trimesh.load(str(stl_path), force="mesh")
print(f"OK: loaded mesh")
print(f"  Triangles : {len(mesh.faces):,}")
print(f"  Vertices  : {len(mesh.vertices):,}")
print(f"  Bounds    : min={mesh.bounds[0]}, max={mesh.bounds[1]}")
print(f"  Is watertight: {mesh.is_watertight}")
