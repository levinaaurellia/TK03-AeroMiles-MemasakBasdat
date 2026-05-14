from django.shortcuts import redirect
from functools import wraps

def role_required(*allowed_roles):
    """
    Decorator untuk memeriksa apakah pengguna yang login memiliki role yang diizinkan.
    Jika tidak ada email di session (belum login), arahkan ke halaman login.
    Jika role tidak sesuai, arahkan ke dashboard masing-masing.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Cek apakah pengguna sudah login
            email = request.session.get('email')
            if not email:
                return redirect('login')

            # 2. Cek apakah role pengguna ada di daftar role yang diizinkan
            user_role = request.session.get('role')
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            # 3. Jika role tidak sesuai, redirect ke tempat yang aman (dashboard masing-masing)
            if user_role == 'staf':
                return redirect('dashboard_staf')
            elif user_role == 'member':
                return redirect('dashboard_member')
            else:
                # Jika role tidak dikenali (ga mungkin, tapi buat jaga-jaga)
                return redirect('login')

        return _wrapped_view
    return decorator