"""
Модуль для взаимодействия с мышью Delux M800 Ultra по протоколу HID.
"""

from dataclasses import dataclass
import time
from typing import Optional
import hid  # type: ignore


@dataclass
class BatteryStatus:
    percentage: int
    is_charging: bool
    is_connected: bool
    is_wireless: bool
    timestamp: float
    raw_response: Optional[list] = None


class DeluxBatteryReader:
    """Класс для опроса статуса батареи мыши Delux M800 Ultra через HID."""

    # Поддерживаемые Vendor ID и Product ID
    SUPPORTED_DEVICES = [
        {"vid": 0x320F, "pid": 0x225B},  # Delux M800 Ultra Receiver / Wired
        {"vid": 0x320F, "pid": 0x225A},
        {"vid": 0x320F, "pid": 0x225C},
    ]

    TARGET_USAGE_PAGE = 0xFF1C
    TARGET_USAGE = 0x0092

    def __init__(self):
        self._last_status: Optional[BatteryStatus] = None
        self._device_path: Optional[bytes] = None

    def _calc_checksum(self, buf: bytearray) -> bytearray:
        """Расчет 16-битной контрольной суммы пакета Delux."""
        s = sum(buf[3:64])
        buf[1] = s & 0xFF
        buf[2] = (s >> 8) & 0xFF
        return buf

    def _build_request_packet(self) -> bytes:
        """Формирование 64-байтового пакета запроса статуса питания."""
        pkt = bytearray(64)
        pkt[0] = 0x04  # Report / Command ID
        pkt[3] = 0x1A  # Команда чтения статуса питания
        pkt[4] = 0x06  # Ожидаемая длина ответа
        pkt[5] = 0x00
        pkt[6] = 0x00
        pkt[7] = 0x00
        return bytes(self._calc_checksum(pkt))

    def find_target_device_path(self) -> Optional[bytes]:
        """Поиск пути к нужному HID-интерфейсу мыши/приемника."""
        try:
            for dev_info in hid.enumerate():
                vid = dev_info.get("vendor_id", 0)
                pid = dev_info.get("product_id", 0)
                up = dev_info.get("usage_page", 0)
                u = dev_info.get("usage", 0)

                # Проверяем совпадение VID/PID и UsagePage
                is_supported_vid_pid = any(
                    d["vid"] == vid and d["pid"] == pid for d in self.SUPPORTED_DEVICES
                )

                if is_supported_vid_pid:
                    if up == self.TARGET_USAGE_PAGE and u == self.TARGET_USAGE:
                        return dev_info["path"]
                    # Если UsagePage не указан или равен 0 (на некоторых версиях Windows)
                    elif (
                        dev_info.get("interface_number") == 1
                        and b"Col04" in dev_info.get("path", b"")
                    ):
                        return dev_info["path"]

            # Если конкретный интерфейс не найден по UsagePage, попробуем перебрать интерфейсы VID 0x320F
            for dev_info in hid.enumerate(0x320F, 0x225B):
                if dev_info.get("interface_number") == 1:
                    return dev_info["path"]

        except Exception as e:
            print(f"[BatteryReader] Ошибка при перечислении устройств: {e}")

        return None

    def read_battery_status(self, timeout_ms: int = 600) -> BatteryStatus:
        """
        Опрос мыши и получение текущего процента заряда и статуса.
        """
        now = time.time()
        path = self.find_target_device_path()

        if not path:
            return BatteryStatus(
                percentage=(
                    self._last_status.percentage if self._last_status else 0
                ),
                is_charging=False,
                is_connected=False,
                is_wireless=True,
                timestamp=now,
            )

        dev = None
        try:
            dev = hid.device()
            dev.open_path(path)

            req = self._build_request_packet()
            written = dev.write(req)

            if written <= 0:
                raise IOError("Не удалось отправить пакет запроса")

            dev.set_nonblocking(False)
            res = dev.read(64, timeout_ms=timeout_ms)

            if not res or len(res) < 12:
                # Мышь может быть в режиме сна, но приемник подключен
                if self._last_status:
                    return BatteryStatus(
                        percentage=self._last_status.percentage,
                        is_charging=self._last_status.is_charging,
                        is_connected=True,
                        is_wireless=self._last_status.is_wireless,
                        timestamp=now,
                    )
                return BatteryStatus(
                    percentage=0,
                    is_charging=False,
                    is_connected=False,
                    is_wireless=True,
                    timestamp=now,
                )

            # Байт 8: Процент заряда (0-100)
            # Байт 9: Статус зарядки (1 = Заряжается, 0 = Разряжается)
            # Байт 11: Режим (0 = 2.4G, 1 = Проводной и т.д.)
            battery_pct = min(100, max(0, int(res[8])))
            is_charging = bool(res[9] == 1)
            is_wireless = bool(res[11] == 0)

            # Если мышь вернула 0% при активном приемнике (иногда при выходе из сна)
            if (
                battery_pct == 0
                and self._last_status
                and self._last_status.percentage > 0
            ):
                # Сохраняем предыдущий процент, если текущий кажется невалидным нулем
                pass
            else:
                self._last_status = BatteryStatus(
                    percentage=battery_pct,
                    is_charging=is_charging,
                    is_connected=True,
                    is_wireless=is_wireless,
                    timestamp=now,
                    raw_response=list(res[:16]),
                )

            return self._last_status

        except Exception as e:
            # При ошибке чтения возвращаем статус с флагом is_connected=False
            return BatteryStatus(
                percentage=(
                    self._last_status.percentage if self._last_status else 0
                ),
                is_charging=(
                    self._last_status.is_charging
                    if self._last_status
                    else False
                ),
                is_connected=False,
                is_wireless=(
                    self._last_status.is_wireless if self._last_status else True
                ),
                timestamp=now,
            )
        finally:
            if dev:
                try:
                    dev.close()
                except Exception:
                    pass


if __name__ == "__main__":
    reader = DeluxBatteryReader()
    print("Чтение заряда Delux M800 Ultra...")
    status = reader.read_battery_status()
    print(f"Подключено: {status.is_connected}")
    print(f"Заряд: {status.percentage}%")
    print(f"Заряжается: {status.is_charging}")
    print(f"Беспроводной режим: {status.is_wireless}")
    if status.raw_response:
        print(f"Raw data: {status.raw_response}")
