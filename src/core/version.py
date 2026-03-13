"""Auto-generated at build time. Fallback reads git tag at runtime."""
import subprocess

_VERSION = None


def get_version():
    global _VERSION
    if _VERSION is not None:
        return _VERSION
    try:
        from core._build_version import BUILD_VERSION
        _VERSION = BUILD_VERSION
        return _VERSION
    except ImportError:
        pass
    try:
        r = subprocess.run(["git", "describe", "--tags", "--always"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            _VERSION = r.stdout.strip()
            return _VERSION
    except Exception:
        pass
    _VERSION = "unknown"
    return _VERSION
