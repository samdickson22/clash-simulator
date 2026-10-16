"""Externally pinned owner-verifier policy; seals cannot nominate their verifier."""
from dataclasses import dataclass
import hashlib
from importlib.machinery import PathFinder
import inspect
from pathlib import Path
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ModulePin:
    name: str
    path: str
    sha256: str | None  # None only for a pinned, non-executable namespace directory.


@dataclass(frozen=True)
class VerifierTrustPolicy:
    """Trusted launcher code supplies this complete reviewed import closure.

    This policy is independent of selection, calibration and runtime JSON. The
    owner must enumerate every project import and its package initializers;
    interpreter/third-party dependencies belong to deployment qualification.
    """
    entrypoint: str
    modules: tuple

    def check(self, entrypoint=None):
        if entrypoint is not None and entrypoint != self.entrypoint:
            raise ValueError('Verifier differs from externally pinned deployment policy')
        if type(self.modules) is not tuple or not self.modules:
            raise ValueError('Immutable complete verifier import pins required')
        pins = {pin.name: pin for pin in self.modules if type(pin) is ModulePin}
        if len(pins) != len(self.modules) or self.entrypoint.split(':')[0] not in pins:
            raise ValueError('Complete unique verifier import pins required')
        for name, pin in pins.items():
            if pin.sha256 is not None and digest(pin.path) != pin.sha256:
                raise ValueError('Verifier/import SHA mismatch before invocation: '+name)
            parent = name.rpartition('.')[0]
            if parent and parent not in pins:
                raise ValueError('Verifier package initializer is not pinned: '+parent)
            search = ([str(Path(pins[parent].path).resolve() if pins[parent].sha256 is None
                           else Path(pins[parent].path).resolve().parent)] if parent else None)
            spec = PathFinder.find_spec(name, search)
            if pin.sha256 is None:
                if (spec is None or spec.origin is not None or
                        tuple(Path(p).resolve() for p in spec.submodule_search_locations or ()) !=
                        (Path(pin.path).resolve(),)):
                    raise ValueError('Verifier namespace resolution differs from deployment policy: '+name)
                loaded = sys.modules.get(name)
                if loaded is not None and (getattr(loaded, '__file__', None) is not None or
                        tuple(Path(p).resolve() for p in getattr(loaded, '__path__', ())) !=
                        (Path(pin.path).resolve(),)):
                    raise ValueError('Loaded verifier namespace differs from deployment policy: '+name)
                continue
            if spec is None or spec.origin is None or Path(spec.origin).resolve() != Path(pin.path).resolve():
                raise ValueError('Verifier/import resolution differs from deployment policy: '+name)
            loaded = sys.modules.get(name)
            if loaded is not None and Path(getattr(loaded, '__file__', '')).resolve() != Path(pin.path).resolve():
                raise ValueError('Loaded verifier/import differs from deployment policy: '+name)
            if loaded is not None and tuple(Path(p).resolve() for p in getattr(loaded, '__path__', ())) != tuple(
                    Path(p).resolve() for p in spec.submodule_search_locations or ()):
                raise ValueError('Loaded verifier package path differs from deployment policy: '+name)

    def check_callable(self, verifier):
        entrypoint = verifier.__module__+':'+verifier.__qualname__
        self.check(entrypoint)
        pin = next(pin for pin in self.modules if pin.name == verifier.__module__)
        source = inspect.getsourcefile(verifier)
        if source is None or Path(source).resolve() != Path(pin.path).resolve():
            raise ValueError('Verifier callable source differs from deployment policy')

    def hashes(self):
        return tuple(sorted((str(Path(pin.path).resolve()), pin.sha256) for pin in self.modules
                            if pin.sha256 is not None))

    def namespaces(self):
        return tuple((pin.name, str(Path(pin.path).resolve())) for pin in self.modules if pin.sha256 is None)


# No final callback or deployment policy has been supplied. Install neither a
# permissive reader nor the obsolete pre-Amendment12 joint-evidence driver.
TRUSTED_OWNER_POLICY = None


def require_policy(policy=None):
    policy = TRUSTED_OWNER_POLICY if policy is None else policy
    if type(policy) is not VerifierTrustPolicy:
        raise ValueError('Externally pinned owner verifier/import policy required')
    return policy
