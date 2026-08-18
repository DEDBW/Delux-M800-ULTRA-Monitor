"""
Точка входа в приложение Delux M800 Ultra Battery Monitor.
"""

import argparse
import ctypes
import os
import sys

# Проверка единственного экземпляра приложения через Windows Mutex
MUTEX_NAME = "Global\\DeluxM800UltraBatteryMonitor_SingleInstance_Mutex"


def ensure_single_instance():
    """Гарантирует, что запущен только один экземпляр программы."""
    try:
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        ERROR_ALREADY_EXISTS = 183
        if last_error == ERROR_ALREADY_EXISTS:
            print("[Main] Приложение уже запущено в фоне.")
            sys.exit(0)
        return mutex
    except Exception as e:
        print(f"[Main] Ошибка проверки единственного экземпляра: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Delux M800 Ultra Battery Monitor"
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Запустить приложение свернутым в трей",
    )
    args = parser.parse_args()

    # Защита от дубликатов
    mutex = ensure_single_instance()

    from src.app import DeluxBatteryApp

    app = DeluxBatteryApp(start_minimized=args.minimized)
    app.run()


if __name__ == "__main__":
    main()
