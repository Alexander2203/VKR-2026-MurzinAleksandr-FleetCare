from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Automobile,
    Driver,
    Slot,
    Appointment,
    Notification,
    AppointmentStatus,
    SlotStatus,
)
from .forms import SlotBulkForm, DriverAdminForm


# Авто
@admin.register(Automobile)
class AutomobileAdmin(admin.ModelAdmin):
    list_display = (
        "plate_number",
        "make",
        "model",
        "last_service_mileage",
        "service_interval_km",
        "next_service_mileage",
    )
    search_fields = ("plate_number", "make", "model")
    list_filter = ("make",)
    readonly_fields = ("next_service_mileage",)
    fieldsets = (
        ("Основное", {"fields": ("plate_number", "make", "model")}),
        (
            "ТО",
            {
                "fields": (
                    "last_service_mileage",
                    "service_interval_km",
                    "next_service_mileage",
                )
            },
        ),
    )


# Водитель
@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):

    # Форма с фильтрацией свободных авто
    form = DriverAdminForm
    list_display = ("last_name", "first_name", "phone", "car")
    search_fields = ("last_name", "first_name", "phone", "car__plate_number")


# Слот
@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):

    # Поддержка множественного создания слотов через поле bulk_times
    form = SlotBulkForm
    list_display = ("date", "time", "status")
    list_filter = ("status", "date")
    search_fields = ("date", "time")
    actions = ["mark_free", "mark_busy"]

    @admin.action(description="Пометить выбранные слоты как свободные")
    def mark_free(self, request, queryset):
        queryset.update(status=SlotStatus.FREE)

    @admin.action(description="Пометить выбранные слоты как занятые")
    def mark_busy(self, request, queryset):
        queryset.update(status=SlotStatus.BUSY)


# Запись
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("slot_date", "slot_time", "driver", "car", "status_badge")
    list_filter = ("status", "slot__date")
    search_fields = ("driver__last_name", "driver__first_name", "car__plate_number")
    autocomplete_fields = ("slot", "driver", "car")
    actions = ["cancel_by_manager"]

    def slot_date(self, obj):
        return obj.slot.date

    slot_date.short_description = "Дата"

    def slot_time(self, obj):
        return obj.slot.time

    slot_time.short_description = "Время"

    def status_badge(self, obj):
        color = {
            "active": "green",
            "cancelled_manager": "tomato",
            "cancelled_user": "gray",
        }.get(obj.status, "black")
        return format_html(
            '<b style="color:{}">{}</b>', color, obj.get_status_display()
        )

    status_badge.short_description = "Статус"

    @admin.action(description="Отменить выбранные записи менеджером")
    def cancel_by_manager(self, request, queryset):

        # Массовая отмена с уведомлением
        for ap in queryset.select_related("slot", "driver"):
            ap.status = AppointmentStatus.CANCELLED_MANAGER
            ap.save()


# Уведомление
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "driver", "short_text")
    list_filter = ("created_at",)
    search_fields = ("driver__last_name", "driver__first_name", "text")

    def short_text(self, obj):
        return (obj.text or "")[:60]

    short_text.short_description = "Текст"
