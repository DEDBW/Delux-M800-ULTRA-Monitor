"""
Модуль системного трея с динамической генерацией иконки заряда.
"""

from typing import Callable, Optional
from PIL import Image, ImageDraw, ImageFont
import pystray


def create_battery_image(
    percentage: int,
    is_charging: bool = False,
    is_connected: bool = True,
    size: int = 64,
) -> Image.Image:
    """
    Динамическая генерация иконки батареи 64x64 для системного трея.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if not is_connected:
        # Иконка "Отключено / Спит"
        # Контур батарейки
        draw.rounded_rectangle([8, 16, 52, 48], radius=6, outline=(160, 160, 160, 255), width=3)
        draw.rounded_rectangle([52, 26, 56, 38], radius=2, fill=(160, 160, 160, 255))
        # Вопросительный знак или крестик
        draw.line([24, 24, 36, 40], fill=(220, 80, 80, 255), width=3)
        draw.line([36, 24, 24, 40], fill=(220, 80, 80, 255), width=3)
        return img

    # Определение цвета
    if is_charging:
        fill_color = (0, 206, 209, 255)  # Бирюзовый для зарядки
        border_color = (255, 255, 255, 255)
    elif percentage > 40:
        fill_color = (46, 213, 115, 255)  # Зеленый
        border_color = (255, 255, 255, 255)
    elif percentage > 20:
        fill_color = (255, 165, 2, 255)  # Оранжевый / желтый
        border_color = (255, 255, 255, 255)
    else:
        fill_color = (255, 71, 87, 255)  # Красный
        border_color = (255, 255, 255, 255)

    # Внешний контур батарейки (горизонтальная)
    # Тело батарейки: [4, 14, 52, 50]
    draw.rounded_rectangle([4, 14, 52, 50], radius=8, outline=border_color, width=4)
    # Плюсовой контакт: [53, 24, 58, 40]
    draw.rounded_rectangle([53, 25, 59, 39], radius=2, fill=border_color)

    # Внутреннее заполнение
    inner_left = 9
    inner_top = 19
    inner_right_max = 47
    inner_bottom = 45

    max_width = inner_right_max - inner_left
    fill_width = int(max_width * (max(5, min(100, percentage)) / 100.0))
    current_right = inner_left + fill_width

    draw.rounded_rectangle(
        [inner_left, inner_top, current_right, inner_bottom],
        radius=4,
        fill=fill_color,
    )

    # Если заряжается — рисуем символ молнии по центру
    if is_charging:
        # Молния
        pts = [
            (32, 10),
            (22, 34),
            (30, 34),
            (26, 54),
            (42, 30),
            (34, 30),
            (38, 10),
        ]
        draw.polygon(pts, fill=(255, 255, 255, 255), outline=(0, 0, 0, 200))
    else:
        # Текстовое число процента внутри или поверх (жирный шрифт)
        text = str(percentage)
        try:
            # Пробуем стандартный шрифт Windows
            font = ImageFont.truetype("arialbd.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        tx = 4 + (48 - tw) // 2
        ty = 14 + (36 - th) // 2 - 2

        # Тень текста
        draw.text((tx + 1, ty + 1), text, font=font, fill=(0, 0, 0, 240))
        draw.text((tx - 1, ty - 1), text, font=font, fill=(0, 0, 0, 240))
        draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

    return img


class TrayIconManager:
    """Управление иконкой в системном трее Windows."""

    def __init__(
        self,
        on_show_gui: Callable[[], None],
        on_refresh: Callable[[], None],
        on_toggle_autostart: Callable[[], None],
        is_autostart_fn: Callable[[], bool],
        on_exit: Callable[[], None],
    ):
        self.on_show_gui = on_show_gui
        self.on_refresh = on_refresh
        self.on_toggle_autostart = on_toggle_autostart
        self.is_autostart_fn = is_autostart_fn
        self.on_exit = on_exit

        self.current_percentage = 0
        self.is_charging = False
        self.is_connected = False

        self.icon: Optional[pystray.Icon] = None

    def _build_menu(self) -> pystray.Menu:
        """Создание контекстного меню трея."""
        if self.is_connected:
            status_text = f"Delux M800 Ultra: {self.current_percentage}%"
            if self.is_charging:
                status_text += " (Заряжается)"
        else:
            status_text = "Delux M800 Ultra: Не подключено"

        return pystray.Menu(
            pystray.MenuItem(status_text, lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Открыть настройки", self.on_show_gui, default=True),
            pystray.MenuItem(
                "Автозапуск с Windows",
                self.on_toggle_autostart,
                checked=lambda item: self.is_autostart_fn(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self.on_exit),
        )

    def update_status(
        self,
        percentage: int,
        is_charging: bool,
        is_connected: bool,
    ):
        """Обновление иконки, подсказки и меню в трее."""
        self.current_percentage = percentage
        self.is_charging = is_charging
        self.is_connected = is_connected

        if not self.icon:
            return

        # Обновляем картинку
        new_img = create_battery_image(percentage, is_charging, is_connected)
        self.icon.icon = new_img

        # Обновляем подсказку (tooltip)
        if is_connected:
            charge_str = " (Заряжается)" if is_charging else ""
            self.icon.title = f"Delux M800 Ultra: {percentage}%{charge_str}"
        else:
            self.icon.title = "Delux M800 Ultra: Не подключено"

        # Обновляем меню
        self.icon.menu = self._build_menu()

    def start(self):
        """Запуск иконки в трее."""
        initial_img = create_battery_image(89, False, True)
        self.icon = pystray.Icon(
            name="DeluxBatteryMonitor",
            icon=initial_img,
            title="Delux M800 Ultra Battery Monitor",
            menu=self._build_menu(),
        )
        self.icon.run()

    def stop(self):
        """Остановка и скрытие иконки из трея."""
        if self.icon:
            self.icon.stop()


if __name__ == "__main__":
    # Тест генерации картинок
    img_89 = create_battery_image(89, False, True)
    img_89.save("test_icon_89.png")
    img_chg = create_battery_image(50, True, True)
    img_chg.save("test_icon_chg.png")
    img_low = create_battery_image(15, False, True)
    img_low.save("test_icon_low.png")
    print("Иконки успешно сгенерированы!")
