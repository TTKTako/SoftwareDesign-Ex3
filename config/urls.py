"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # allauth headless API — Google OAuth + session auth (FR-1.1, FR-1.2)
    # Endpoints live at /_allauth/browser/v1/auth/...
    path('_allauth/', include('allauth.headless.urls')),
    # allauth standard URLs — required so that reverse('google_callback') resolves
    # when allauth builds the OAuth redirect_uri for the Google provider.
    # With HEADLESS_ONLY=True the HTML login/signup pages are disabled;
    # only the provider callback URL (e.g. /accounts/google/login/callback/)
    # is actually used during the OAuth handshake.
    path('accounts/', include('allauth.urls')),
    # Cithara music API
    path('', include('music.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
