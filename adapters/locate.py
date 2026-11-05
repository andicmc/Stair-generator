"""Find the library root (the folder holding ``core`` and ``adapters``). No Rhino imports.

Order: a configured path (absolute, or relative to the .gh file), the STAIRGEN_PATH
environment variable, then a search from the .gh folder and the Rhino file folder:
each folder, 2 parents, and sub-folders whose names contain "stair" (2 levels).
"""
import os

ENV_VAR = "STAIRGEN_PATH"
PACKAGES = ("core", "adapters")


def is_library(folder):
    return bool(folder) and all(os.path.isfile(os.path.join(folder, pkg, "__init__.py"))
                                for pkg in PACKAGES)


def _roots(files):
    roots = []
    for f in files:
        if not f:
            continue
        folder = os.path.dirname(os.path.abspath(f))
        for _ in range(3):
            if folder not in roots:
                roots.append(folder)
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
    return roots


def find_library(configured, gh_file, rhino_file, environ=None):
    """Return (folder or None, [places looked])."""
    environ = os.environ if environ is None else environ
    gh_dir = os.path.dirname(os.path.abspath(gh_file)) if gh_file else None
    looked = []

    def resolve(path, label):
        path = os.path.expandvars(os.path.expanduser(str(path).strip().strip('"')))
        if not os.path.isabs(path):
            if gh_dir is None:
                looked.append("{}: '{}' is relative but the .gh file is not saved".format(label, path))
                return None
            path = os.path.join(gh_dir, path)
        path = os.path.normpath(path)
        looked.append("{}: {}".format(label, path))
        return path if is_library(path) else None

    if configured and str(configured).strip():
        return resolve(configured, "configured path"), looked
    if environ.get(ENV_VAR, "").strip():
        return resolve(environ[ENV_VAR], ENV_VAR + " environment variable"), looked
    for root in _roots((gh_file, rhino_file)):
        looked.append("search: " + root)
        candidates = [root]
        for sub in _subdirs(root):
            candidates.append(sub)
            candidates += _subdirs(sub)
        for c in candidates:
            if is_library(c):
                return os.path.normpath(c), looked
    if not gh_file:
        looked.append("(the .gh file is not saved yet, so its folder could not be searched)")
    return None, looked


def _subdirs(folder):
    try:
        return [os.path.join(folder, n) for n in sorted(os.listdir(folder))
                if "stair" in n.lower() and os.path.isdir(os.path.join(folder, n))]
    except OSError:
        return []


def not_found_message(looked):
    return ("Stair library not found (folder with 'core' and 'adapters').\nPut it next to this "
            ".gh file, set LIBRARY_PATH in the script, or set the STAIRGEN_PATH environment "
            "variable.\nLooked in:\n  " + "\n  ".join(looked))
