from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from datetime import date
from .decorators import role_required

def login_view(request):
    # Jika sudah login, cegah akses halaman login
    if request.session.get('email'):
        if request.session.get('role') == 'staf':
             return redirect('dashboard_staf')
        return redirect('dashboard_member')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        with connection.cursor() as cursor:
            # Cari data pengguna berdasarkan email
            cursor.execute("SELECT email, password FROM PENGGUNA WHERE email = %s", [email])
            user = cursor.fetchone()
            
            # Cocokkan password
            if user and password == user[1]: 
                
                # Cek apakah user adalah staf
                cursor.execute("SELECT email FROM STAF WHERE email = %s", [email])
                if cursor.fetchone():
                    request.session['email'] = email
                    request.session['role'] = 'staf'
                    return redirect('dashboard_staf')
                
                # Cek apakah user adalah member
                cursor.execute("SELECT email FROM MEMBER WHERE email = %s", [email])
                if cursor.fetchone():
                    request.session['email'] = email
                    request.session['role'] = 'member'
                    return redirect('dashboard_member')
                
            else:
                messages.error(request, 'Email atau password salah.')
                
    return render(request, 'guest/login.html')

def register_view(request):
    # Jika sudah login, cegah akses halaman register
    if request.session.get('email'):
        if request.session.get('role') == 'staf':
             return redirect('dashboard_staf')
        return redirect('dashboard_member')
    
    if request.method == 'POST':
        role = request.POST.get('role')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        salutation = request.POST.get('salutation')
        first_mid_name = request.POST.get('first_mid_name')
        last_name = request.POST.get('last_name')
        kewarganegaraan = request.POST.get('kewarganegaraan')
        country_code = request.POST.get('country_code')
        mobile_number = request.POST.get('mobile_number')
        tanggal_lahir = request.POST.get('tanggal_lahir')
        
        if password != confirm_password:
            messages.error(request, 'Password dan konfirmasi password tidak cocok.')
            return redirect('register')
            
        # Hash password sebelum disimpan
        # hashed_password = make_password(password) 
        hashed_password = password # TODO: implementasi hashing password
        
        with connection.cursor() as cursor:
            # Validasi duplikasi email
            cursor.execute("SELECT email FROM PENGGUNA WHERE email = %s", [email])
            if cursor.fetchone():
                messages.error(request, 'Email sudah terdaftar.')
                return redirect('register')
            
            try:
                # Insert ke tabel PENGGUNA
                cursor.execute("""
                    INSERT INTO PENGGUNA (email, password, salutation, first_mid_name, last_name, country_code, mobile_number, tanggal_lahir, kewarganegaraan)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [email, hashed_password, salutation, first_mid_name, last_name, country_code, mobile_number, tanggal_lahir, kewarganegaraan])
                
                # Insert ke tabel spesifik berdasarkan Role
                if role == 'member':
                    # Auto-generate Nomor Member format M[XXXX]
                    cursor.execute("SELECT COUNT(*) FROM MEMBER")
                    count = cursor.fetchone()[0] + 1
                    nomor_member = f"M{count:04d}"
                    
                    # Ambil ID tier terendah
                    cursor.execute("SELECT id_tier FROM TIER ORDER BY minimal_tier_miles ASC LIMIT 1")
                    tier_row = cursor.fetchone()
                    id_tier = tier_row[0] if tier_row else None
                    
                    cursor.execute("""
                        INSERT INTO MEMBER (email, nomor_member, tanggal_bergabung, id_tier, award_miles, total_miles)
                        VALUES (%s, %s, %s, %s, 0, 0)
                    """, [email, nomor_member, date.today(), id_tier])
                    
                elif role == 'staf':
                    kode_maskapai = request.POST.get('kode_maskapai')
                    
                    # Auto-generate ID Staf format S[XXXX]
                    cursor.execute("SELECT COUNT(*) FROM STAF")
                    count = cursor.fetchone()[0] + 1
                    id_staf = f"S{count:04d}"
                    
                    cursor.execute("""
                        INSERT INTO STAF (email, id_staf, kode_maskapai)
                        VALUES (%s, %s, %s)
                    """, [email, id_staf, kode_maskapai])
                    
                messages.success(request, 'Registrasi berhasil! Silakan login.')
                return redirect('login')
                
            except Exception as e:
                messages.error(request, f'Terjadi kesalahan: {str(e)}')
                return redirect('register')

    return render(request, 'guest/register.html')

def logout_view(request):
    # Mengakhiri session pengguna
    request.session.flush()
    return redirect('login')

@role_required('member')
def dashboard_member(request):
    with connection.cursor() as cursor:
        # Mengambil ringkasan data untuk dashboard
        cursor.execute("SELECT COUNT(*) FROM MITRA")
        total_mitra = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM HADIAH")
        total_hadiah = cursor.fetchone()[0]
        
    context = {
        'total_mitra': total_mitra,
        'total_hadiah': total_hadiah,
        # Tambahkan data staf spesifik jika diperlukan
    }
    return render(request, 'member/dashboard.html', context)

@role_required('staf')
def dashboard_staf(request):
    with connection.cursor() as cursor:
        # Mengambil ringkasan data untuk dashboard
        cursor.execute("SELECT COUNT(*) FROM MITRA")
        total_mitra = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM HADIAH")
        total_hadiah = cursor.fetchone()[0]
        
    context = {
        'total_mitra': total_mitra,
        'total_hadiah': total_hadiah,
        # Tambahkan data staf spesifik jika diperlukan
    }
    return render(request, 'staf/dashboard.html', context)

@role_required('staf')
def kelola_mitra(request):
    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'create':
                email = request.POST.get('email')
                nama = request.POST.get('nama')
                tanggal = request.POST.get('tanggal')
                
                # Sesuai deskripsi, sistem harus membuat entri PENYEDIA terlebih dahulu
                cursor.execute("INSERT INTO PENYEDIA DEFAULT VALUES RETURNING id")
                id_penyedia = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT INTO MITRA (email_mitra, id_penyedia, nama_mitra, tanggal_kerja_sama) 
                    VALUES (%s, %s, %s, %s)
                """, [email, id_penyedia, nama, tanggal])
                
            elif action == 'update':
                email = request.POST.get('email') # PK, tidak diubah tapi jadi acuan
                nama = request.POST.get('nama')
                tanggal = request.POST.get('tanggal')
                cursor.execute("""
                    UPDATE MITRA SET nama_mitra = %s, tanggal_kerja_sama = %s 
                    WHERE email_mitra = %s
                """, [nama, tanggal, email])
                
            elif action == 'delete':
                id_penyedia = request.POST.get('id_penyedia')
                # Menggunakan sifat ON DELETE CASCADE, menghapus PENYEDIA akan otomatis menghapus MITRA
                cursor.execute("DELETE FROM PENYEDIA WHERE id = %s", [id_penyedia])
            
            return redirect('kelola_mitra')

        # READ (GET)
        cursor.execute("SELECT email_mitra, nama_mitra, tanggal_kerja_sama, id_penyedia FROM MITRA")
        columns = [col[0] for col in cursor.description]
        mitra_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    return render(request, 'staf/manajemen_mitra.html', {'mitra_list': mitra_list})

@role_required('staf')
def kelola_hadiah(request):
    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'create':
                nama = request.POST.get('nama')
                miles = request.POST.get('miles')
                deskripsi = request.POST.get('deskripsi')
                id_penyedia = request.POST.get('id_penyedia')
                valid_start = request.POST.get('valid_start')
                program_end = request.POST.get('program_end')
                
                # Simulasi auto-increment kode RWD-[XXX] jika trigger DB belum ada
                cursor.execute("SELECT COUNT(*) FROM HADIAH")
                count = cursor.fetchone()[0] + 1
                kode_hadiah = f"RWD-{count:03d}"
                
                cursor.execute("""
                    INSERT INTO HADIAH (kode_hadiah, nama, miles, deskripsi, valid_start_date, program_end, id_penyedia)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, [kode_hadiah, nama, miles, deskripsi, valid_start, program_end, id_penyedia])
                
            elif action == 'update':
                kode_hadiah = request.POST.get('kode_hadiah')
                nama = request.POST.get('nama')
                miles = request.POST.get('miles')
                deskripsi = request.POST.get('deskripsi')
                valid_start = request.POST.get('valid_start')
                program_end = request.POST.get('program_end')
                
                cursor.execute("""
                    UPDATE HADIAH SET nama=%s, miles=%s, deskripsi=%s, valid_start_date=%s, program_end=%s 
                    WHERE kode_hadiah=%s
                """, [nama, miles, deskripsi, valid_start, program_end, kode_hadiah])
                
            elif action == 'delete':
                kode_hadiah = request.POST.get('kode_hadiah')
                cursor.execute("DELETE FROM HADIAH WHERE kode_hadiah=%s", [kode_hadiah])
                
            return redirect('kelola_hadiah')

        # READ (GET)
        cursor.execute("SELECT kode_hadiah, nama, miles, deskripsi, valid_start_date, program_end, id_penyedia FROM HADIAH")
        columns = [col[0] for col in cursor.description]
        hadiah_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Ambil daftar penyedia untuk dropdown Create
        cursor.execute("SELECT id FROM PENYEDIA")
        penyedia_list = [row[0] for row in cursor.fetchall()]
        
    return render(request, 'staf/manajemen_hadiah.html', {
        'hadiah_list': hadiah_list, 
        'penyedia_list': penyedia_list
    })
