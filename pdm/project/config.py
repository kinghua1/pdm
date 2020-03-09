from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Dict, Iterable

import appdirs
import tomlkit

from pdm.exceptions import NoConfigError
from pdm.utils import get_pypi_source


class Config(MutableMapping):
    """A dict-like object for configuration key and values"""

    HOME_CONFIG = Path.home() / ".pdm" / "config.toml"
    CONFIG_ITEMS = {
        # config name: (config_description, not_for_project)
        "cache_dir": ("The root directory of cached files", True),
        "python.path": ("The Python interpreter path", False),
        "python.use_pyenv": ("Use the pyenv interpreter", False),
        "pypi.url": (
            "The URL of PyPI mirror, defaults to https://pypi.org/simple",
            False,
        ),
        "pypi.verify_ssl": ("Verify SSL certificate when query PyPI", False),
    }
    DEFAULT_CONFIG = {
        "cache_dir": appdirs.user_cache_dir("pdm"),
        "python.use_pyenv": True,
    }
    DEFAULT_CONFIG.update(get_pypi_source())

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._data = self.DEFAULT_CONFIG.copy()
        self._dirty = {}

        self._project_config_file = self.project_root / ".pdm.toml"
        self._home_config_file = self.HOME_CONFIG / "config.toml"
        self._project_config = self.load_config(self._project_config_file)
        self._home_config = self.load_config(self._home_config_file)
        # First load user config, then project config
        for config in (self._home_config, self._project_config):
            self._data.update(dict(config))

    def load_config(self, file_path: Path) -> Dict[str, Any]:
        def get_item(sub_data):
            result = {}
            for k, v in sub_data.items():
                if getattr(v, "items", None) is not None:
                    result.update(
                        {f"{k}.{sub_k}": sub_v for sub_k, sub_v in get_item(v).items()}
                    )
                else:
                    result.update({k: v})
            return result

        if not file_path.is_file():
            return {}
        return get_item(dict(tomlkit.parse(file_path.read_text("utf-8"))))

    def save_config(self, for_proejct: bool = True) -> None:
        not_for_project_keys = [k for k in self._dirty if self.CONFIG_ITEMS[k][1]]
        if not_for_project_keys and for_proejct:
            raise ValueError(
                "Config item {} can not be saved in project config.".format(
                    ",".join(not_for_project_keys)
                )
            )
        data = self._project_config if for_proejct else self._home_config
        data.update(self._dirty)
        file_path = self._project_config_file if for_proejct else self._home_config_file
        file_path.parent.mkdir(exist_ok=True)
        toml_data = {}
        for key, value in data.items():
            *parts, last = key.split(".")
            temp = toml_data
            for part in parts:
                temp = temp.setdefault(part, {})
            temp[last] = value

        with file_path.open("w", encoding="utf-8") as fp:
            fp.write(tomlkit.dumps(toml_data))
        self._dirty.clear()

    def __getitem__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError:
            raise NoConfigError(key) from None

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in self.CONFIG_ITEMS:
            raise NoConfigError(key)
        if isinstance(value, str):
            if value.lower() == "false":
                value = False
            elif value.lower() == "true":
                value = True
        self._dirty[key] = value
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterable[str]:
        return iter(self._data)

    def __delitem__(self, key) -> None:
        raise NotImplementedError