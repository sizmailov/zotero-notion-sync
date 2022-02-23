from __future__ import annotations

import os
from dataclasses import dataclass

from mashumaro.mixins.yaml import DataClassYAMLMixin


@dataclass
class Config(DataClassYAMLMixin):
    @dataclass
    class Notion(DataClassYAMLMixin):
        token: str
        database_id: str

    @dataclass
    class Zotero(DataClassYAMLMixin):
        token: str
        group_id: str

    notion: Notion
    zotero: Zotero

    @classmethod
    def read_config(cls, filename: os.PathLike) -> Config:
        with open(filename) as f:
            return cls.from_yaml(f.read())
