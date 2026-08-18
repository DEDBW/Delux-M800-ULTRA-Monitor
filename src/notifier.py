"""
Модуль для отправки нативных всплывающих уведомлений Windows и звуковых сигналов.
"""

import os
import sys
import time
import winsound
from typing import Optional
from winotify import Notification, audio


from .utils import get_resource_path


class BatteryNotifier:
    """Управление всплывающими уведомлениями о состоянии батареи."""

    APP_ID = "Delux M800 Ultra Monitor"

    def __init__(self, icon_path: Optional[str] = None):
        if not icon_path or not os.path.exists(icon_path):
            icon_path = get_resource_path(os.path.join("assets", "icon.ico"))

        self.icon_path = icon_path if os.path.exists(icon_path) else None

        # Переменные отслеживания состояния для предотвращения спама
        self._last_low_notified_pct: Optional[int] = None
        self._last_notified_time: float = 0.0
        self._was_charging: Optional[bool] = None
        self._full_charge_notified: bool = False

    def send_notification(
        self,
        title: str,
        message: str,
        sound_type: Optional[str] = "default",
        urgency: str = "normal",
    ) -> bool:
        """Отправка всплывающего уведомления Windows Toast."""
        try:
            toast = Notification(
                app_id=self.APP_ID,
                title=title,
                msg=message,
                icon=self.icon_path if self.icon_path else "",
            )

            # Настройка звука в Toast
            if sound_type == "warning":
                toast.set_audio(audio.Reminder, loop=False)
            elif sound_type == "critical":
                toast.set_audio(audio.LoopingAlarm, loop=False)
            elif sound_type == "none":
                toast.set_audio(audio.Silent, loop=False)
            else:
                toast.set_audio(audio.Default, loop=False)

            toast.show()
            return True
        except Exception as e:
            print(f"[Notifier] Ошибка отправки уведомления: {e}")
            return False

    def play_sound(self, sound_type: str = "warning"):
        """Воспроизведение системного звукового сигнала Windows."""
        try:
            if sound_type == "critical":
                winsound.MessageBeep(winsound.MB_ICONHAND)
            elif sound_type == "warning":
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            else:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    def check_and_notify(
        self,
        percentage: int,
        is_charging: bool,
        is_connected: bool,
        low_threshold: int = 20,
        critical_threshold: int = 10,
        cooldown_minutes: int = 30,
        enable_notifications: bool = True,
        enable_sound: bool = True,
        notify_on_full_charge: bool = True,
        notify_on_charge_started: bool = False,
    ):
        """
        Проверка изменения состояния и отправка уведомлений с защитой от спама.
        """
        if not is_connected or percentage <= 0:
            return

        now = time.time()
        cooldown_sec = cooldown_minutes * 60

        # Обработка смены режима зарядки
        if self._was_charging is not None:
            if not self._was_charging and is_charging:
                # Началась зарядка
                self._last_low_notified_pct = None
                self._full_charge_notified = False
                if enable_notifications and notify_on_charge_started:
                    self.send_notification(
                        title="Delux M800 Ultra - Зарядка",
                        message=f"Кабель подключен. Текущий заряд: {percentage}%",
                        sound_type="default" if enable_sound else "none",
                    )
            elif self._was_charging and not is_charging:
                # Отключили зарядку
                self._full_charge_notified = False

        self._was_charging = is_charging

        # Уведомление о 100% полном заряде
        if (
            is_charging
            and percentage >= 100
            and not self._full_charge_notified
            and enable_notifications
            and notify_on_full_charge
        ):
            self._full_charge_notified = True
            self.send_notification(
                title="Delux M800 Ultra - Зарядка завершена",
                message="Мышь полностью заряжена (100%). Можно отключить кабель.",
                sound_type="default" if enable_sound else "none",
            )
            if enable_sound:
                self.play_sound("info")
            return

        # Если мышь сейчас заряжается, не шлем предупреждения о разряде
        if is_charging:
            return

        # Проверка критического разряда
        if percentage <= critical_threshold:
            need_notify = False

            if self._last_low_notified_pct is None:
                need_notify = True
            elif self._last_low_notified_pct > critical_threshold:
                # Переход с низкого на критический
                need_notify = True
            elif (now - self._last_notified_time) >= cooldown_sec:
                # Прошел кулдаун
                need_notify = True

            if need_notify and enable_notifications:
                self._last_low_notified_pct = percentage
                self._last_notified_time = now
                self.send_notification(
                    title="⚠️ Delux M800 Ultra — КРИТИЧЕСКИЙ ЗАРЯД!",
                    message=f"Осталось всего {percentage}%! Мышь скоро отключится, подключите кабель!",
                    sound_type="critical" if enable_sound else "none",
                )
                if enable_sound:
                    self.play_sound("critical")
            return

        # Проверка обычного предупреждения о низком заряде
        if percentage <= low_threshold:
            need_notify = False

            if self._last_low_notified_pct is None:
                need_notify = True
            elif (
                self._last_low_notified_pct > percentage
                and (now - self._last_notified_time) >= 900
            ):
                # Процент упал еще ниже и прошло от 15 мин
                need_notify = True
            elif (now - self._last_notified_time) >= cooldown_sec:
                need_notify = True

            if need_notify and enable_notifications:
                self._last_low_notified_pct = percentage
                self._last_notified_time = now
                self.send_notification(
                    title="🪫 Delux M800 Ultra — Низкий заряд",
                    message=f"Уровень батареи: {percentage}%. Рекомендуется подключить мышь к зарядке.",
                    sound_type="warning" if enable_sound else "none",
                )
                if enable_sound:
                    self.play_sound("warning")
            return

        # Если уровень заряда выше порогов — сбрасываем состояние
        if percentage > low_threshold:
            self._last_low_notified_pct = None


if __name__ == "__main__":
    notifier = BatteryNotifier()
    print("Отправка тестового уведомления...")
    notifier.send_notification(
        title="Тест Delux M800 Ultra",
        message="Тестовое уведомление: программа мониторинга работает успешно!",
        sound_type="default",
    )
