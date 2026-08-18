"""
Модуль управления конфигурацией и автозапуском в Windows.
"""

import json
import os
import subprocess
import sys
import winreg
from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class AppConfig:
    low_battery_threshold: int = 20  # Порог предупреждения (%)
    critical_battery_threshold: int = 10  # Критический порог (%)
    poll_interval_seconds: int = 60  # Интервал проверки (сек)
    enable_notifications: bool = True  # Включены ли всплывающие уведомления
    enable_sound: bool = True  # Звук при уведомлении
    notify_on_full_charge: bool = True  # Уведомлять при 100% заряде
    notify_on_charge_started: bool = False  # Уведомлять при подключении к зарядке
    start_minimized: bool = True  # Запуск в трей
    notification_cooldown_minutes: int = 30  # Минимальный интервал повтора


class ConfigManager:
    """Управление настройками и автозапуском в Windows (через системную папку Автозагрузка и реестр)."""

    APP_NAME = "DeluxBatteryMonitor"
    REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def __init__(self, config_dir: str = None):
        if not config_dir:
            app_data = os.environ.get(
                "LOCALAPPDATA",
                os.path.expanduser(r"~\AppData\Local"),
            )
            self.config_dir = os.path.join(app_data, "DeluxBatteryMonitor")
        else:
            self.config_dir = config_dir

        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.config = self.load_config()

    def get_startup_folder_path(self) -> str:
        """Возвращает путь к системной папке автозагрузки пользователя."""
        appdata = os.environ.get("APPDATA", os.path.expanduser(r"~\AppData\Roaming"))
        return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")

    def get_startup_shortcut_path(self) -> str:
        """Возвращает путь к файлу ярлыка автозагрузки."""
        return os.path.join(self.get_startup_folder_path(), f"{self.APP_NAME}.lnk")

    def load_config(self) -> AppConfig:
        """Загрузка конфигурации из файла или создание по умолчанию."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    valid_keys = AppConfig.__annotations__.keys()
                    filtered = {k: v for k, v in data.items() if k in valid_keys}
                    return AppConfig(**filtered)
            except Exception as e:
                print(f"[Config] Ошибка чтения конфига: {e}. Используем настройки по умолчанию.")

        config = AppConfig()
        self.save_config(config)
        return config

    def save_config(self, config: AppConfig = None) -> bool:
        """Сохранение конфигурации в JSON файл."""
        if config is not None:
            self.config = config
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.config), f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[Config] Ошибка сохранения конфига: {e}")
            return False

    def is_autostart_enabled(self) -> bool:
        """Проверка наличия автозапуска (в папке Startup или реестре)."""
        # 1. Проверяем ярлык в папке Автозагрузка
        if os.path.exists(self.get_startup_shortcut_path()):
            return True

        # 2. Проверяем реестр (на случай старой записи)
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.REG_KEY, 0, winreg.KEY_READ
            ) as key:
                winreg.QueryValueEx(key, self.APP_NAME)
                return True
        except Exception:
            pass

        return False

    def set_autostart(self, enable: bool) -> bool:
        """
        Включение или отключение автозапуска.
        Использует создание ярлыка в папке Startup (наиболее надежно и не вызывает ложных срабатываний антивируса).
        """
        shortcut_path = self.get_startup_shortcut_path()

        if not enable:
            # Удаляем ярлык из автозагрузки
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                except Exception as e:
                    print(f"[Config] Ошибка удаления ярлыка: {e}")

            # Удаляем из реестра, если там было
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, self.REG_KEY, 0, winreg.KEY_WRITE
                ) as key:
                    winreg.DeleteValue(key, self.APP_NAME)
            except Exception:
                pass

            return True

        # Включение автозапуска через создание ярлыка
        try:
            if getattr(sys, "frozen", False):
                # Скомпилированный exe
                target = sys.executable
                args = "--minimized"
                icon = sys.executable
            else:
                # Режим Python скрипта
                main_py = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "main.py")
                )
                pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                if not os.path.exists(pythonw):
                    pythonw = sys.executable
                target = pythonw
                args = f'"{main_py}" --minimized'
                icon = ""

            # Создаем ярлык через PowerShell WScript.Shell
            ps_script = (
                f'$ws = New-Object -ComObject WScript.Shell; '
                f'$s = $ws.CreateShortcut("{shortcut_path}"); '
                f'$s.TargetPath = "{target}"; '
                f'$s.Arguments = "{args}"; '
                f'$s.WorkingDirectory = "{os.path.dirname(target)}"; '
                f'if ("{icon}") {{ $s.IconLocation = "{icon}" }}; '
                f'$s.Save()'
            )

            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                creationflags=0x08000000 if os.name == "nt" else 0,  # CREATE_NO_WINDOW
            )
            return True

        except Exception as e:
            print(f"[Config] Ошибка создания ярлыка автозапуска: {e}")
            return False


if __name__ == "__main__":
    cm = ConfigManager()
    print("Конфигурация:", cm.config)
    print("Путь к конфигу:", cm.config_file)
    print("Автозапуск включен:", cm.is_autostart_enabled())
