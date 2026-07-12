from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import logout
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.shortcuts import redirect
from django.urls import include, path, re_path
from finance.views import payment_cancel_page, payment_success_page


def admin_root_redirect(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    return redirect('/admin/login/?next=/dashboard/')


def admin_logout_redirect(request):
    logout(request)
    return redirect('/admin/login/?next=/dashboard/')


urlpatterns = [
    path('admin/', admin_root_redirect),
    path('admin/logout/', admin_logout_redirect),
    path('admin/', admin.site.urls),

    path('api/accounts/', include('accounts.urls')),
    path('api/academics/', include('academics.urls')),
    path('api/finance/', include('finance.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/chat/', include('chat.urls')),
    path('dashboard/', include('dashboard.urls')),
    path(
        'payment/success/',
        payment_success_page,
        name='payment-success'
    ),
    path(
        'payment/cancel/',
        payment_cancel_page,
        name='payment-cancel'
    ),
]

if settings.DEBUG or settings.SERVE_STATIC_FILES:
    urlpatterns += [
        re_path(
            r'^static/(?P<path>.*)$',
            staticfiles_serve,
            {'insecure': True},
        ),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
