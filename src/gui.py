"""
Графический интерфейс настроек и мониторинга мыши Delux M800 Ultra.
"""

from datetime import datetime
import os
import sys
import threading
from typing import Callable, Optional
import customtkinter as ctk
from PIL import Image

from .battery_reader import BatteryStatus
from .config import AppConfig, ConfigManager
from .utils import get_resource_path


class MainWindow(ctk.CTk):
    """Главное окно приложения с визуализацией заряда и настройками."""

    def __init__(
        self,
        config_manager: ConfigManager,
        on_refresh_requested: Callable[[], None],
        on_test_notify_requested: Callable[[], None],
        on_config_changed: Callable[[AppConfig], None],
        on_autostart_toggled: Callable[[bool], None],
    ):
        super().__init__()

        self.config_manager = config_manager
        self.config = config_manager.config
        self.on_refresh_requested = on_refresh_requested
        self.on_test_notify_requested = on_test_notify_requested
        self.on_config_changed = on_config_changed
        self.on_autostart_toggled = on_autostart_toggled

        # Настройки окна
        self.title("Delux M800 Ultra — Монитор заряда")
        self.geometry("640x720")
        self.minsize(600, 680)

        # Тема оформления
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        # Иконка окна
        self.icon_path = get_resource_path(os.path.join("assets", "icon.ico"))
        self.mouse_img_path = get_resource_path(os.path.join("assets", "mouse.png"))

        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception:
                pass

        # Перехват закрытия окна (сворачивание в трей)
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self._create_widgets()

    def _create_widgets(self):
        """Создание элементов интерфейса."""
        # Главный скроллируемый контейнер
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="#121317", corner_radius=0)
        self.scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # 1. Заголовок
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#181a20", corner_radius=12)
        header_frame.pack(fill="x", padx=16, pady=(16, 10))

        title_label = ctk.CTkLabel(
            header_frame,
            text="DELUX M800 ULTRA",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#FFFFFF",
        )
        title_label.pack(anchor="w", padx=16, pady=(12, 2))

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Мониторинг заряда аккумулятора и уведомления",
            font=ctk.CTkFont(size=12),
            text_color="#8E9297",
        )
        subtitle_label.pack(anchor="w", padx=16, pady=(0, 12))

        # 2. Карточка статуса батареи
        self.status_card = ctk.CTkFrame(self.scroll_frame, fg_color="#1c1f26", corner_radius=12)
        self.status_card.pack(fill="x", padx=16, pady=10)

        # Внутренний контейнер для картинки и данных
        content_box = ctk.CTkFrame(self.status_card, fg_color="transparent")
        content_box.pack(fill="x", padx=16, pady=16)

        # Картинка мыши
        if os.path.exists(self.mouse_img_path):
            try:
                pil_img = Image.open(self.mouse_img_path)
                # Ресайз с сохранением пропорций
                w, h = pil_img.size
                ratio = 130 / h
                nw, nh = int(w * ratio), int(h * ratio)
                self.mouse_photo = ctk.CTkImage(pil_img, size=(nw, nh))
                self.mouse_img_label = ctk.CTkLabel(content_box, image=self.mouse_photo, text="")
                self.mouse_img_label.pack(side="left", padx=(0, 20))
            except Exception as e:
                print(f"[GUI] Ошибка загрузки изображения мыши: {e}")

        # Блок информации справа от картинки
        info_box = ctk.CTkFrame(content_box, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True)

        # Бейдж подключения
        self.badge_frame = ctk.CTkFrame(info_box, fg_color="#222730", corner_radius=6)
        self.badge_frame.pack(anchor="w", pady=(0, 8))

        self.badge_label = ctk.CTkLabel(
            self.badge_frame,
            text="● Опрос мыши...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#fbc531",
        )
        self.badge_label.pack(padx=8, pady=3)

        # Большой процент
        self.percent_label = ctk.CTkLabel(
            info_box,
            text="--%",
            font=ctk.CTkFont(size=44, weight="bold"),
            text_color="#50e45f",
        )
        self.percent_label.pack(anchor="w", pady=0)

        # Статус (Заряжается / 2.4G)
        self.state_label = ctk.CTkLabel(
            info_box,
            text="Подключение...",
            font=ctk.CTkFont(size=14),
            text_color="#B0B3B8",
        )
        self.state_label.pack(anchor="w", pady=(0, 8))

        # Полоса заряда (Progress Bar)
        self.progress_bar = ctk.CTkProgressBar(
            self.status_card,
            height=14,
            corner_radius=7,
            progress_color="#50e45f",
            fg_color="#2c303b",
        )
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 12))
        self.progress_bar.set(0.0)

        # Нижняя плашка карточки (время обновления и кнопка)
        bottom_status = ctk.CTkFrame(self.status_card, fg_color="transparent")
        bottom_status.pack(fill="x", padx=16, pady=(0, 12))

        self.last_update_label = ctk.CTkLabel(
            bottom_status,
            text="Последнее обновление: --:--:--",
            font=ctk.CTkFont(size=11),
            text_color="#6C727F",
        )
        self.last_update_label.pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            bottom_status,
            text="🔄 Обновить",
            width=100,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_refresh_click,
        )
        self.refresh_btn.pack(side="right")

        # 3. Карточка настроек уведомлений
        notif_card = ctk.CTkFrame(self.scroll_frame, fg_color="#1c1f26", corner_radius=12)
        notif_card.pack(fill="x", padx=16, pady=10)

        card_title = ctk.CTkLabel(
            notif_card,
            text="Настройки уведомлений",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF",
        )
        card_title.pack(anchor="w", padx=16, pady=(14, 10))

        # Ползунок: Порог предупреждения (%)
        low_row = ctk.CTkFrame(notif_card, fg_color="transparent")
        low_row.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            low_row,
            text="Предупреждение о низком заряде:",
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        self.low_val_label = ctk.CTkLabel(
            low_row,
            text=f"{self.config.low_battery_threshold}%",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#50e45f",
        )
        self.low_val_label.pack(side="right")

        self.low_slider = ctk.CTkSlider(
            notif_card,
            from_=1,
            to=100,
            number_of_steps=99,
            command=self._on_low_slider_change,
        )
        self.low_slider.set(self.config.low_battery_threshold)
        self.low_slider.pack(fill="x", padx=16, pady=(0, 10))
        self._disable_slider_scroll(self.low_slider)

        # Ползунок: Критический порог (%)
        crit_row = ctk.CTkFrame(notif_card, fg_color="transparent")
        crit_row.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            crit_row,
            text="Критический заряд (срочная зарядка):",
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        self.crit_val_label = ctk.CTkLabel(
            crit_row,
            text=f"{self.config.critical_battery_threshold}%",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ff4757",
        )
        self.crit_val_label.pack(side="right")

        self.crit_slider = ctk.CTkSlider(
            notif_card,
            from_=1,
            to=100,
            number_of_steps=99,
            command=self._on_crit_slider_change,
        )
        self.crit_slider.set(self.config.critical_battery_threshold)
        self.crit_slider.pack(fill="x", padx=16, pady=(0, 12))
        self._disable_slider_scroll(self.crit_slider)

        # Интервал опроса
        poll_row = ctk.CTkFrame(notif_card, fg_color="transparent")
        poll_row.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(
            poll_row,
            text="Частота проверки заряда:",
            font=ctk.CTkFont(size=13),
        ).pack(side="left")

        self.poll_options = {
            "30 сек": 30,
            "1 мин": 60,
            "2 мин": 120,
            "5 мин": 300,
            "10 мин": 600,
        }
        # Находим текущий выбор
        cur_str = "1 мин"
        for k, v in self.poll_options.items():
            if v == self.config.poll_interval_seconds:
                cur_str = k
                break

        self.poll_menu = ctk.CTkOptionMenu(
            poll_row,
            values=list(self.poll_options.keys()),
            command=self._on_poll_interval_change,
            width=110,
        )
        self.poll_menu.set(cur_str)
        self.poll_menu.pack(side="right")

        # Переключатели (Switches)
        self.notif_switch = self._add_switch(
            notif_card,
            "Всплывающие уведомления Windows (Toast)",
            self.config.enable_notifications,
            self._on_notif_toggle,
        )

        self.sound_switch = self._add_switch(
            notif_card,
            "Звуковой сигнал при уведомлении",
            self.config.enable_sound,
            self._on_sound_toggle,
        )

        self.full_chg_switch = self._add_switch(
            notif_card,
            "Уведомлять при 100% полном заряде",
            self.config.notify_on_full_charge,
            self._on_full_chg_toggle,
        )

        # Тестовое уведомление
        test_row = ctk.CTkFrame(notif_card, fg_color="transparent")
        test_row.pack(fill="x", padx=16, pady=(10, 16))

        self.test_btn = ctk.CTkButton(
            test_row,
            text="🔔 Проверить тестовое уведомление",
            fg_color="#2b303c",
            hover_color="#3a4152",
            font=ctk.CTkFont(size=12),
            command=self.on_test_notify_requested,
        )
        self.test_btn.pack(fill="x")

        # 4. Карточка параметров запуска
        app_card = ctk.CTkFrame(self.scroll_frame, fg_color="#1c1f26", corner_radius=12)
        app_card.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(
            app_card,
            text="Параметры запуска",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#FFFFFF",
        ).pack(anchor="w", padx=16, pady=(14, 10))

        # Автозапуск
        self.autostart_switch = self._add_switch(
            app_card,
            "Запускать автоматически вместе с Windows",
            self.config_manager.is_autostart_enabled(),
            self._on_autostart_switch_toggle,
        )

        # Запуск в трей
        self.minimized_switch = self._add_switch(
            app_card,
            "Запускать в фоновом режиме (в трей)",
            self.config.start_minimized,
            self._on_minimized_toggle,
        )

        # Кнопка сворачивания в трей
        tray_btn_row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        tray_btn_row.pack(fill="x", padx=16, pady=(10, 20))

        hide_btn = ctk.CTkButton(
            tray_btn_row,
            text="Свернуть в системный трей",
            height=36,
            fg_color="#262b36",
            hover_color="#333a4a",
            font=ctk.CTkFont(size=13),
            command=self.hide_to_tray,
        )
        hide_btn.pack(fill="x")

    def _add_switch(
        self, parent, text: str, initial_val: bool, command: Callable
    ) -> ctk.CTkSwitch:
        """Вспомогательный метод для создания стилизованного переключателя."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=6)

        ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=13)).pack(side="left")

        switch = ctk.CTkSwitch(
            row,
            text="",
            command=command,
            width=46,
            progress_color="#50e45f",
        )
        if initial_val:
            switch.select()
        else:
            switch.deselect()
        switch.pack(side="right")
        return switch

    def _disable_slider_scroll(self, slider: ctk.CTkSlider):
        """Отключает изменение слайдера колёсиком, но прокрутка окна продолжает работать."""
        canvas = slider._canvas
        scroll_canvas = self.scroll_frame._parent_canvas
        # Снимаем внутреннюю привязку MouseWheel с tkinter Canvas слайдера
        canvas.unbind("<MouseWheel>")
        # Вместо блокировки — перенаправляем прокрутку на скролл-контейнер окна
        def _forward_scroll(event):
            scroll_canvas.yview_scroll(-int(event.delta / 6), "units")
            return "break"
        canvas.bind("<MouseWheel>", _forward_scroll)

    def _on_low_slider_change(self, value):
        val_int = int(value)
        self.low_val_label.configure(text=f"{val_int}%")
        self.config.low_battery_threshold = val_int
        self.config_manager.save_config(self.config)
        self.on_config_changed(self.config)

    def _on_crit_slider_change(self, value):
        val_int = int(value)
        self.crit_val_label.configure(text=f"{val_int}%")
        self.config.critical_battery_threshold = val_int
        self.config_manager.save_config(self.config)
        self.on_config_changed(self.config)

    def _on_poll_interval_change(self, choice):
        seconds = self.poll_options.get(choice, 60)
        self.config.poll_interval_seconds = seconds
        self.config_manager.save_config(self.config)
        self.on_config_changed(self.config)

    def _on_notif_toggle(self):
        self.config.enable_notifications = bool(self.notif_switch.get())
        self.config_manager.save_config(self.config)
        self.on_config_changed(self.config)

    def _on_sound_toggle(self):
        self.config.enable_sound = bool(self.sound_switch.get())
        self.config_manager.save_config(self.config)
        self.on_config_changed(self.config)

    def _on_full_chg_toggle(self):
        self.config.notify_on_full_charge = bool(self.full_chg_switch.get())
        self.config_manager.save_config(self.config)
        self.on_config_changed(self.config)

    def _on_minimized_toggle(self):
        self.config.start_minimized = bool(self.minimized_switch.get())
        self.config_manager.save_config(self.config)
        self.on_config_changed(self.config)

    def _on_autostart_switch_toggle(self):
        enabled = bool(self.autostart_switch.get())
        self.config_manager.set_autostart(enabled)
        self.on_autostart_toggled(enabled)

    def _on_refresh_click(self):
        self.refresh_btn.configure(state="disabled", text="Опрос...")
        self.on_refresh_requested()
        self.after(
            1000,
            lambda: self.refresh_btn.configure(
                state="normal", text="🔄 Обновить"
            ),
        )

    def update_battery_status(self, status: BatteryStatus):
        """Обновление визуализации заряда на форме."""
        pct = status.percentage
        is_chg = status.is_charging
        is_conn = status.is_connected

        # Дата/время обновления
        now_str = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.configure(
            text=f"Последнее обновление: {now_str}"
        )

        if not is_conn:
            self.badge_label.configure(
                text="○ Мышь не обнаружена", text_color="#ff4757"
            )
            self.percent_label.configure(text="--%", text_color="#747d8c")
            self.state_label.configure(
                text="Проверьте 2.4G приемник или включите мышь",
                text_color="#8E9297",
            )
            self.progress_bar.set(0.0)
            self.progress_bar.configure(progress_color="#57606f")
            return

        # Подключено
        self.badge_label.configure(
            text="● Подключено (2.4G Mode)", text_color="#50e45f"
        )
        self.percent_label.configure(text=f"{pct}%")
        self.progress_bar.set(pct / 100.0)

        # Выбор цвета и статуса
        if is_chg:
            color = "#00d2d3"
            self.state_label.configure(
                text="⚡ Мышь заряжается по кабелю", text_color=color
            )
            self.percent_label.configure(text_color=color)
            self.progress_bar.configure(progress_color=color)
        elif pct <= self.config.critical_battery_threshold:
            color = "#ff4757"
            self.state_label.configure(
                text="⚠️ Критический заряд! Требуется подключить кабель",
                text_color=color,
            )
            self.percent_label.configure(text_color=color)
            self.progress_bar.configure(progress_color=color)
        elif pct <= self.config.low_battery_threshold:
            color = "#ffa502"
            self.state_label.configure(
                text="🪫 Низкий заряд батареи", text_color=color
            )
            self.percent_label.configure(text_color=color)
            self.progress_bar.configure(progress_color=color)
        else:
            color = "#50e45f"
            self.state_label.configure(
                text="🔋 Работает от аккумулятора", text_color="#B0B3B8"
            )
            self.percent_label.configure(text_color=color)
            self.progress_bar.configure(progress_color=color)

    def show_window(self):
        """Отображение и поднятие окна на передний план."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide_to_tray(self):
        """Сворачивание окна в трей."""
        self.withdraw()
