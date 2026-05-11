import subprocess, sys

packages = {
    "trimesh":     "trimesh",
    "numpy":       "numpy",
    "scipy":       "scipy",
    "pyransac3d":  "pyransac3d",
    "pandas":      "pandas",
    "yaml":        "pyyaml",
}

for module, pip_name in packages.items():
    try:
        mod = __import__(module)
        version = getattr(mod, "__version__", "unknown")
        print(f"OK:   {module} {version}")
    except ImportError:
        print(f"MISSING: {module} — installing {pip_name}...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_name],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            mod = __import__(module)
            version = getattr(mod, "__version__", "unknown")
            print(f"OK:   {module} {version} (just installed)")
        else:
            print(f"FAIL: could not install {pip_name}")
            print(result.stderr[-500:])
