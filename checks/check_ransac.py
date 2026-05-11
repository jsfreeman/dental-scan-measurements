import trimesh
import pathlib
import numpy as np
import pyransac3d as pyrsc

stl_path = pathlib.Path(__file__).parent.parent / "trial" / "Desktop Scanner" / "s1-86846A (Desktop).stl"
mesh = trimesh.load(str(stl_path), force="mesh")

points, _ = trimesh.sample.sample_surface(mesh, 10000)
print(f"Sampled {len(points)} points. Running RANSAC cylinder fit...")

cyl = pyrsc.Cylinder()
center, axis, radius, inliers = cyl.fit(points, thresh=0.3, maxIteration=2000)

print(f"OK: cylinder found")
print(f"  Center : {center}")
print(f"  Axis   : {axis}")
print(f"  Radius : {radius:.4f} mm")
print(f"  Inliers: {len(inliers)} / {len(points)} points ({100*len(inliers)/len(points):.1f}%)")
