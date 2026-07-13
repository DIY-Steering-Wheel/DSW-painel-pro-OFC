from __future__ import annotations

from pathlib import Path


def search_default_folder():
    return None


def install(folder, plugin_dir: Path):
    return (
        "O Forza não precisa de alteração em arquivos. Ative Data Out no jogo, "
        "use o IP do computador receptor e configure a porta UDP 9999."
    )
