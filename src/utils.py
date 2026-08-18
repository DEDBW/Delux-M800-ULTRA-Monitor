"""
Вспомогательные утилиты для корректного поиска ресурсов и путей.
"""

import os
import sys


def get_resource_path(relative_path: str) -> str:
    """
    Возвращает абсолютный путь к ресурсу.
    Корректно работает как в режиме разработки, так и внутри собранного PyInstaller .exe.
    """
    if hasattr(sys, "_MEIPASS"):
        # Режим скомпилированного .exe (PyInstaller распаковывает данные в _MEIPASS)
        base_path = sys._MEIPASS
    else:
        # Режим запуска скрипта из исходников
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.normpath(os.path.join(base_path, relative_path))
