"""
URL configuration for aeromiles project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from main import views

urlpatterns = [
    # admin
    path('admin/', admin.site.urls),

    # guest
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('profil/', views.pengaturan_profil, name='pengaturan_profil'),

    # member
    path('kelola-member/', views.kelola_member, name='kelola_member'),
    path('member/dashboard/', views.dashboard_member, name='dashboard_member'),
    path('member/klaim-miles/', views.klaim_miles, name='klaim_miles'),
    path('member/transfer-miles/', views.transfer_miles, name='transfer_miles'),
    path('member/redeem/', views.redeem_view, name='redeem'),
    path('member/package/', views.package_view, name='package'),
    path('member/tier/', views.tier_view, name='tier'),
    path('member/redeem/proses/', views.proses_redeem, name='proses_redeem'),
    path('member/package/beli/', views.beli_package, name='beli_package'),

    # staf
    path('staf/dashboard/', views.dashboard_staf, name='dashboard_staf'),
    path('staf/kelola-hadiah/', views.kelola_hadiah, name='kelola_hadiah'),
    path('staf/kelola-mitra/', views.kelola_mitra, name='kelola_mitra'),
    path('staf/kelola-klaim/', views.kelola_klaim, name='kelola_klaim'),
    path('staf/laporan/', views.laporan_transaksi_view, name='laporan'),
    
    
    path('logout/', views.logout, name='logout'), 
    path('', RedirectView.as_view(url='/login/', permanent=False)),
]
