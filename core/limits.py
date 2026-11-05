"""Read config/code_limits.json. Every limit comes from here, never from code."""
import copy
import json
import os

CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "config",
                                            "code_limits.json"))


class Limits(object):
    """One section of the limits file; ``value(name)`` and ``source(name)``."""

    def __init__(self, section, overrides=None):
        self._items = copy.deepcopy(section)
        for name, value in (overrides or {}).items():
            if isinstance(value, dict) and "value" in value:
                self._items[name] = value
            else:
                self._items[name] = {"value": value, "source": "override"}

    def value(self, name):
        try:
            return self._items[name]["value"]
        except KeyError:
            raise KeyError("limit '{}' is not in config/code_limits.json".format(name))

    def source(self, name):
        return self._items.get(name, {}).get("source", "")

    def has(self, name):
        return name in self._items

    def items(self):
        return {k: v["value"] for k, v in self._items.items()}


def load_limits(section, path=None, overrides=None):
    with open(path or CONFIG_PATH) as f:
        data = json.load(f)
    if section not in data:
        raise KeyError("section '{}' is not in {}".format(section, path or CONFIG_PATH))
    return Limits(data[section], overrides)
