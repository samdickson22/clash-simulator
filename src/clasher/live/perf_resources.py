"""Opt-in config splice around the sealed public root constructor."""
import json
from types import FunctionType, SimpleNamespace


def cached_resources(base):
    """Keep reconstruction/RNG order unchanged; isolate the serializer globals.

    Config is static for the lifetime of a Resources instance, as in Stage 5.
    Only its final JSON value is cached; all root-specific fields stay eager.
    """
    class CachedResources(base):
        def __init__(self):
            super().__init__()
            self.config_json = json.dumps(self.config)
            def dumps(payload):
                if payload.get('config') is not self.config or list(payload)[-1] != 'config':
                    raise ValueError('Config splice requires the static final config field')
                head = {key: value for key, value in payload.items() if key != 'config'}
                return json.dumps(head)[:-1]+', "config": '+self.config_json+'}'
            namespace = dict(base.root.__globals__, json=SimpleNamespace(dumps=dumps))
            self._cached_root = FunctionType(base.root.__code__, namespace,
                                            base.root.__name__, base.root.__defaults__,
                                            base.root.__closure__).__get__(self)

        def root(self, info, opponent, rng):
            return self._cached_root(info, opponent, rng)
    return CachedResources
