from django.contrib import admin

from .models import CounsellorAvailability


@admin.register(CounsellorAvailability)
class CounsellorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("counsellor", "date", "start_time", "end_time", "is_booked")
    list_filter = ("counsellor", "date", "is_booked")
    search_fields = (
        "counsellor__user__first_name",
        "counsellor__user__last_name",
        "date",
    )
    ordering = ("-date", "start_time")
