from django import forms
from django.core.exceptions import ValidationError
from .models import Slot, SlotStatus, Driver, Automobile
from datetime import time as dtime


# Слот
class SlotBulkForm(forms.ModelForm):

    # Несколько времен через запятую (дополнительные слоты)
    bulk_times = forms.CharField(
        label="Несколько времен через запятую",
        required=False,
        help_text="Пример: 09:00, 11:00, 14:00",
    )

    class Meta:
        model = Slot
        fields = ["date", "time", "status", "bulk_times"]

    def clean(self):
        cleaned = super().clean()
        bulk = (cleaned.get("bulk_times") or "").strip()
        date = cleaned.get("date")
        main_time = cleaned.get("time")

        # Парсим дополнительные времена, если заданы
        times = []
        if bulk:
            for part in bulk.split(","):
                t = part.strip()
                if not t:
                    continue
                try:
                    h, m = [int(x) for x in t.split(":")]
                    times.append(dtime(h, m))
                except Exception:
                    raise ValidationError(
                        {
                            "bulk_times": "Неверный формат времени. Используйте HH:MM, например 09:00"
                        }
                    )

        # Запомним распарсенные времена и основной time
        self._parsed_times = times
        self._main_time = main_time

        # Предупредим, если какие-то из дополнительных уже есть
        if date and times:
            existing = set(
                Slot.objects.filter(date=date, time__in=times).values_list(
                    "time", flat=True
                )
            )
            if existing:
                bad = ", ".join(sorted(t.strftime("%H:%M") for t in existing))
                self.add_error(
                    "bulk_times", f"Эти времена уже существуют и будут пропущены: {bad}"
                )
        return cleaned

    def save(self, commit=True):

        # 1) Сохраняем основной слот обычным путём
        instance = super().save(commit=commit)

        # 2) Если указаны дополнительные времена - создаём дополнительные слоты
        date = self.cleaned_data.get("date")
        status = self.cleaned_data.get("status") or SlotStatus.FREE
        extras = []

        for t in getattr(self, "_parsed_times", []):

            # Не дублируем основной time
            if self._main_time and t == self._main_time:
                continue
            extras.append(Slot(date=date, time=t, status=status))

        if extras:

            # Пропустим конфликты на уровне БД (если пара уже есть)
            Slot.objects.bulk_create(extras, ignore_conflicts=True)
        return instance


# Водитель
class DriverAdminForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ["first_name", "last_name", "phone", "car"]

    def __init__(self, *args, **kwargs):

        # Фильтрация списка автомобилей чтобы показать только свободные
        super().__init__(*args, **kwargs)
        used_ids = Driver.objects.values_list("car_id", flat=True)
        qs = Automobile.objects.exclude(id__in=used_ids)

        # Если редактируем существующего водителя то его авто разрешаем
        if self.instance and self.instance.pk and self.instance.car_id:
            qs = qs | Automobile.objects.filter(pk=self.instance.car_id)
        self.fields["car"].queryset = qs.order_by("plate_number")
