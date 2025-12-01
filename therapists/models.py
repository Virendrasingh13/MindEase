from datetime import datetime

from django.db import models
from django.utils import timezone

from accounts.models import Counsellor


class CounsellorAvailability(models.Model):
    """Represents a single time slot that a counsellor has marked as available."""

    counsellor = models.ForeignKey(
        Counsellor,
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=45)
    is_booked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("counsellor", "date", "start_time")
        ordering = ["date", "start_time"]
        indexes = [
            models.Index(fields=["counsellor", "date"]),
            models.Index(fields=["counsellor", "is_booked"]),
        ]

    def __str__(self):
        return (
            f"{self.counsellor.user.get_full_name()} - "
            f"{self.date} {self.start_time.strftime('%H:%M')}"
        )

    @property
    def is_future_slot(self):
        combined = timezone.make_aware(datetime.combine(self.date, self.start_time))
        return combined >= timezone.now()
