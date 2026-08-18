"""
Главный контроллер приложения: координация фонового потока, трея и GUI.
"""

import os
import sys
import threading
import time
from typing import Optional

from .battery_reader import BatteryStatus, DeluxBatteryReader
from .config import AppConfig, ConfigManager
from .gui import MainWindow
from .notifier import BatteryNotifier
from .tray_icon import TrayIconManager


class DeluxBatteryApp:
    """Главный класс приложения мониторинга мыши."""

    def __init__(self, start_minimized: bool = False):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config

        # Если передан флаг командной строки, приоритет ему, иначе настройка из конфига
        self.start_minimized = (
            start_minimized or self.config.start_minimized
        )

        # Модули
        self.reader = DeluxBatteryReader()
        self.notifier = BatteryNotifier()

        # Потоки и события
        self._running = True
        self._refresh_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._tray_thread: Optional[threading.Thread] = None

        # Инициализация GUI
        self.gui = MainWindow(
            config_manager=self.config_manager,
            on_refresh_requested=self.trigger_refresh,
            on_test_notify_requested=self.trigger_test_notification,
            on_config_changed=self.on_config_changed,
            on_autostart_toggled=self.on_autostart_toggled,
        )

        # Инициализация трея
        self.tray = TrayIconManager(
            on_show_gui=self.show_gui,
            on_refresh=self.trigger_refresh,
            on_toggle_autostart=self.toggle_autostart,
            is_autostart_fn=self.config_manager.is_autostart_enabled,
            on_exit=self.exit_app,
        )

    def trigger_refresh(self):
        """Немедленный опрос батареи."""
        self._refresh_event.set()

    def trigger_test_notification(self):
        """Отправка тестового уведомления."""
        self.notifier.send_notification(
            title="🔔 Delux M800 Ultra — Тест",
            message="Тестовое уведомление: система оповещений о заряде мыши активна!",
            sound_type="default" if self.config.enable_sound else "none",
        )

    def on_config_changed(self, new_config: AppConfig):
        """Обновление настроек."""
        self.config = new_config
        # Пробуждаем поток для обновления интервала
        self._refresh_event.set()

    def on_autostart_toggled(self, enabled: bool):
        """Обновление статуса автозапуска."""
        pass

    def toggle_autostart(self):
        """Переключение автозапуска из меню трея."""
        current = self.config_manager.is_autostart_enabled()
        self.config_manager.set_autostart(not current)
        # Обновляем переключатель в GUI
        if self.gui.autostart_switch:
            if not current:
                self.gui.autostart_switch.select()
            else:
                self.gui.autostart_switch.deselect()

    def show_gui(self):
        """Показ окна настроек из трея."""
        # CustomTkinter требует вызова методов окна из главного потока
        self.gui.after(0, self.gui.show_window)

    def _polling_loop(self):
        """Фоновый цикл опроса батареи мыши."""
        while self._running:
            try:
                status = self.reader.read_battery_status()

                # Обновление GUI
                self.gui.after(0, lambda s=status: self.gui.update_battery_status(s))

                # Обновление трея
                self.tray.update_status(
                    percentage=status.percentage,
                    is_charging=status.is_charging,
                    is_connected=status.is_connected,
                )

                # Проверка порогов и отправка уведомлений
                self.notifier.check_and_notify(
                    percentage=status.percentage,
                    is_charging=status.is_charging,
                    is_connected=status.is_connected,
                    low_threshold=self.config.low_battery_threshold,
                    critical_threshold=self.config.critical_battery_threshold,
                    cooldown_minutes=self.config.notification_cooldown_minutes,
                    enable_notifications=self.config.enable_notifications,
                    enable_sound=self.config.enable_sound,
                    notify_on_full_charge=self.config.notify_on_full_charge,
                    notify_on_charge_started=self.config.notify_on_charge_started,
                )

            except Exception as e:
                print(f"[App] Ошибка в цикле опроса: {e}")

            # Ожидание следующего интервала или принудительного обновления
            interval = max(5, self.config.poll_interval_seconds)
            self._refresh_event.wait(timeout=interval)
            self._refresh_event.clear()

    def run(self):
        """Запуск приложения."""
        # 1. Запуск фонового потока опроса
        self._poll_thread = threading.Thread(
            target=self._polling_loop, daemon=True, name="BatteryPoller"
        )
        self._poll_thread.start()

        # 2. Запуск системного трея в отдельном потоке
        self._tray_thread = threading.Thread(
            target=self.tray.start, daemon=True, name="TrayIcon"
        )
        self._tray_thread.start()

        # 3. Начальный опрос
        self.trigger_refresh()

        # 4. Управление видимостью окна
        if self.start_minimized:
            self.gui.withdraw()
        else:
            self.gui.show_window()

        # 5. Запуск главного цикла GUI (в главном потоке)
        try:
            self.gui.mainloop()
        except KeyboardInterrupt:
            self.exit_app()

    def exit_app(self):
        """Корректное завершение работы приложения."""
        self._running = False
        self._refresh_event.set()
        self.tray.stop()
        try:
            self.gui.destroy()
        except Exception:
            pass
        sys.exit(0)
