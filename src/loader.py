"""
Mesh loader — accepts STL and PLY files, returns a single trimesh.Trimesh object.
"""

import pathlib

import trimesh

# File extensions supported by this pipeline
SUPPORTED_EXTENSIONS = {".stl", ".ply"}


def load_mesh(path: str) -> trimesh.Trimesh:
    """
    Load an STL or PLY file and return a single merged mesh.

    Parameters
    ----------
    path : str
        Absolute or relative path to the mesh file.

    Returns
    -------
    trimesh.Trimesh

    Raises
    ------
    FileNotFoundError  — if the file does not exist.
    ValueError         — if the extension is unsupported or the file yields no geometry.
    """
    p = pathlib.Path(path)

    if not p.exists():
        raise FileNotFoundError(f"Mesh file not found: {path}")

    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{p.suffix}' for {path}. "
            f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    # force="mesh" merges scene graphs and multi-body files into one Trimesh
    mesh = trimesh.load(str(p), force="mesh")

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(
            f"Could not interpret {path} as a single mesh. "
            "The file may be empty or contain an unsupported geometry type."
        )

    if len(mesh.faces) == 0:
        raise ValueError(f"Mesh loaded from {path} contains no triangles.")

    return mesh
