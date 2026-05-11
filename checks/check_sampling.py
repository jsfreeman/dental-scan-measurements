import trimesh
import pathlib

stl_path = pathlib.Path(__file__).parent.parent / "trial" / "Desktop Scanner" / "s1-86846A (Desktop).stl"
mesh = trimesh.load(str(stl_path), force="mesh")

N = 1000
points, face_idx = trimesh.sample.sample_surface(mesh, N)
print(f"OK: sampled {N} points from mesh surface")
print(f"  Shape : {points.shape}")
print(f"  First 5 points:")
for p in points[:5]:
    print(f"    {p}")
print(f"  Point cloud bounds: min={points.min(axis=0)}, max={points.max(axis=0)}")
