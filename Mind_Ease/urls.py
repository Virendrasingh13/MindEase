from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('', include('therapists.urls')),
    path('', include('resources.urls')),
    path('', include('client.urls')),
    path('accounts/' , include('accounts.urls')),
    path('', include('bookings.urls')),
]


# to server the media files
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
