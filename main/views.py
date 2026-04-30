import bcrypt
from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from datetime import date
from datetime import datetime
from .decorators import role_required

def login(request):
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

            input_bytes = password.encode('utf-8')
            db_bytes = user[1].encode('utf-8') if user else None

            # Cocokkan password
            if user and bcrypt.checkpw(input_bytes, db_bytes):
                
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

def register(request):
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
            
        # implementasi hashing password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
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

def logout(request):
    # Mengakhiri session pengguna
    request.session.flush()
    return redirect('login')

@role_required('member')
def dashboard_member(request):
    email_user = request.session.get('email')

    with connection.cursor() as cursor:
        # Mengambil ringkasan data untuk dashboard
        cursor.execute("""
            SELECT CONCAT(p.salutation, ' ', p.first_mid_name, ' ', p.last_name) AS nama_lengkap, p.tanggal_lahir,
            p.email, CONCAT(p.country_code, ' ', p.mobile_number) AS telepon, p.kewarganegaraan, t.nama AS tier, m.nomor_member, m.total_miles, m.award_miles
            FROM PENGGUNA p 
            JOIN MEMBER m ON p.email = m.email
            JOIN TIER t ON m.id_tier = t.id_tier
            WHERE p.email = %s
        """, [email_user])
        informasi = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))

        params = [email_user] * 4
        cursor.execute("""
            (SELECT 'Terima Transfer' AS jenis_transaksi, t.timestamp, t.jumlah AS miles
            FROM TRANSFER t
            WHERE t.email_member_2 = %s)
            UNION ALL
            (SELECT 'Kirim Transfer' AS jenis_transaksi, t.timestamp, t.jumlah AS miles
            FROM TRANSFER t
            WHERE t.email_member_1 = %s)
            UNION ALL
            (SELECT 'Redeem' AS jenis_transaksi, c.timestamp, h.miles AS miles
            FROM REDEEM c
            JOIN HADIAH h ON c.kode_hadiah = h.kode_hadiah
            WHERE c.email_member = %s)
            UNION ALL
            (SELECT 'Package' AS jenis_transaksi, cm.timestamp, ap.jumlah_award_miles AS miles
            FROM MEMBER_AWARD_MILES_PACKAGE cm
            JOIN AWARD_MILES_PACKAGE ap ON cm.id_award_miles_package = ap.id
            WHERE cm.email_member = %s)
            ORDER BY timestamp DESC
            LIMIT 5;
        """, params)
        transaksi = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    context = {
        'informasi': informasi,
        'transaksi': transaksi
    }
    return render(request, 'member/dashboard.html', context)

@role_required('staf')
def dashboard_staf(request):
    email_user = request.session.get('email')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT CONCAT(p.salutation, ' ', p.first_mid_name, ' ', p.last_name) AS nama_lengkap, p.tanggal_lahir,
            p.email, CONCAT(p.country_code, ' ', p.mobile_number) AS telepon, p.kewarganegaraan, s.id_staf, m.nama_maskapai
            FROM PENGGUNA p 
            JOIN STAF s ON p.email = s.email
            JOIN MASKAPAI m ON s.kode_maskapai = m.kode_maskapai
            WHERE p.email = %s
        """, [email_user])
        informasi = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))

        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status_penerimaan = 'Menunggu') AS total_menunggu,
                COUNT(*) FILTER (WHERE status_penerimaan = 'Disetujui' AND email_staf = %s) AS total_disetujui,
                COUNT(*) FILTER (WHERE status_penerimaan = 'Ditolak' AND email_staf = %s) AS total_ditolak
            FROM CLAIM_MISSING_MILES;
        """, [email_user, email_user])
        klaim = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))

    context = {
        'informasi': informasi,
        'klaim': klaim
    }
    return render(request, 'staf/dashboard.html', context)

def pengaturan_profil(request):
    email_user = request.session.get('email')
    role_user = request.session.get('role')
    
    if not email_user: 
        return redirect('login')

    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'update_profil':
                # GABUNGKAN NAMA DEPAN DAN TENGAH SEBELUM DISIMPAN
                nama_depan = request.POST.get('first_name', '').strip()
                nama_tengah = request.POST.get('mid_name', '').strip()
                first_mid_name = f"{nama_depan} {nama_tengah}".strip()
                
                cursor.execute("""
                    UPDATE PENGGUNA SET salutation=%s, first_mid_name=%s, last_name=%s, 
                    country_code=%s, mobile_number=%s, kewarganegaraan=%s, tanggal_lahir=%s
                    WHERE email=%s
                """, [
                    request.POST.get('salutation'), first_mid_name, request.POST.get('last_name'), 
                    request.POST.get('country_code'), request.POST.get('mobile_number'), 
                    request.POST.get('kewarganegaraan'), request.POST.get('tanggal_lahir'), email_user
                ])
                
                if role_user == 'staf':
                    cursor.execute("UPDATE STAF SET kode_maskapai=%s WHERE email=%s", 
                                 [request.POST.get('kode_maskapai'), email_user])
                
                messages.success(request, 'Profil berhasil diperbarui!')

            elif action == 'ubah_password':
                pw_lama = request.POST.get('password_lama')
                pw_baru = request.POST.get('password_baru')
                konfirmasi_pw = request.POST.get('konfirmasi_password')
                
                # CEK APAKAH KONFIRMASI PASSWORD SAMA
                if pw_baru != konfirmasi_pw:
                    messages.error(request, 'Konfirmasi password baru tidak cocok!')
                    return redirect('pengaturan_profil')
                
                cursor.execute("SELECT password FROM PENGGUNA WHERE email=%s", [email_user])
                hashed_pw = cursor.fetchone()[0]
                
                if bcrypt.checkpw(pw_lama.encode('utf-8'), hashed_pw.encode('utf-8')):
                    new_hashed = bcrypt.hashpw(pw_baru.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    cursor.execute("UPDATE PENGGUNA SET password=%s WHERE email=%s", [new_hashed, email_user])
                    messages.success(request, 'Password berhasil diubah!')
                else:
                    messages.error(request, 'Password lama salah.')
            
            return redirect('pengaturan_profil')

        # READ: Ambil data untuk ditampilkan di form
        if role_user == 'member':
            cursor.execute("""
                SELECT p.*, m.nomor_member, m.tanggal_bergabung 
                FROM PENGGUNA p JOIN MEMBER m ON p.email = m.email WHERE p.email = %s
            """, [email_user])
        else:
            cursor.execute("""
                SELECT p.*, s.id_staf, s.kode_maskapai 
                FROM PENGGUNA p JOIN STAF s ON p.email = s.email WHERE p.email = %s
            """, [email_user])
        
        user_data = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
        
        # MEMISAHKAN NAMA DEPAN DAN TENGAH UNTUK DITAMPILKAN DI FORM 
        if user_data.get('first_mid_name'):
            # Potong nama berdasarkan spasi pertama saja
            nama_split = user_data['first_mid_name'].split(' ', 1)
            user_data['nama_depan_saja'] = nama_split[0]
            # Jika ada nama tengah, masukkan ke variabel terpisah
            user_data['nama_tengah_saja'] = nama_split[1] if len(nama_split) > 1 else ''
        else:
            user_data['nama_depan_saja'] = ''
            user_data['nama_tengah_saja'] = ''
        
        cursor.execute("SELECT kode_maskapai, nama_maskapai FROM MASKAPAI")
        maskapai_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    return render(request, 'profil.html', {'user': user_data, 'role': role_user, 'maskapai_list': maskapai_list})

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
        mitra_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
    return render(request, 'staf/kelola_mitra.html', {'mitra_list': mitra_list})

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
        cursor.execute("""
            WITH INFO_PENYEDIA AS (
                (SELECT id_penyedia, 'airline' as jenis_penyedia, nama_maskapai AS nama_penyedia
                FROM MASKAPAI)
                UNION
                (SELECT id_penyedia, 'partner' as jenis_penyedia, nama_mitra AS nama_penyedia
                FROM MITRA)
            )
            SELECT h.kode_hadiah, h.nama, h.deskripsi, ip.jenis_penyedia, ip.nama_penyedia, h.miles, h.valid_start_date, h.program_end
            FROM HADIAH h
            JOIN INFO_PENYEDIA ip ON h.id_penyedia = ip.id_penyedia
            ORDER BY kode_hadiah
        """)
        hadiah_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
        # Ambil daftar penyedia untuk dropdown Create
        cursor.execute("""
            (SELECT id_penyedia, 'airline' as jenis_penyedia, nama_maskapai AS nama_penyedia
            FROM MASKAPAI)
            UNION
            (SELECT id_penyedia, 'partner' as jenis_penyedia, nama_mitra AS nama_penyedia
            FROM MITRA)
            ORDER BY id_penyedia
        """)
        penyedia_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    context = {
        'hadiah_list': hadiah_list,
        'penyedia_list': penyedia_list
    }

    return render(request, 'staf/kelola_hadiah.html', context)

@role_required('member')
def klaim_miles(request):
    email_user = request.session.get('email')

    status_filter = request.GET.get('status', 'semua')

    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'create':
                kode_maskapai = request.POST.get('kode_maskapai')
                kelas_kabin = request.POST.get('kelas_kabin')
                bandara_asal = request.POST.get('bandara_asal')
                bandara_tujuan = request.POST.get('bandara_tujuan')
                tanggal_penerbangan = request.POST.get('tanggal_penerbangan')
                flight_number = request.POST.get('flight_number')
                nomor_tiket = request.POST.get('nomor_tiket')
                pnr = request.POST.get('pnr')

                # Generate ID klaim
                cursor.execute("SELECT MAX(id) FROM CLAIM_MISSING_MILES")
                id_klaim = int(cursor.fetchone()[0]) + 1

                cursor.execute("""
                    INSERT INTO CLAIM_MISSING_MILES id, email_member, maskapai, bandara_asal, bandara_tujuan, tanggal_penerbangan, flight_number, nomor_tiket, kelas_kabin, pnr, status_penerimaan, timestamp
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, [id_klaim, email_user, kode_maskapai, bandara_asal, bandara_tujuan, tanggal_penerbangan, flight_number, nomor_tiket, kelas_kabin, pnr, "Menunggu"])

            elif action == 'update':
                kode_maskapai = request.POST.get('kode_maskapai')
                kelas_kabin = request.POST.get('kelas_kabin')
                bandara_asal = request.POST.get('bandara_asal')
                bandara_tujuan = request.POST.get('bandara_tujuan')
                tanggal_penerbangan = request.POST.get('tanggal_penerbangan')
                flight_number = request.POST.get('flight_number')
                nomor_tiket = request.POST.get('nomor_tiket')
                pnr = request.POST.get('pnr')
                id_klaim = request.POST.get('id_klaim')

                cursor.execute("""
                    UPDATE CLAIM_MISSING_MILES SET maskapai=%s, kelas_kabin=%s, bandara_asal=%s, bandara_tujuan=%s, tanggal_penerbangan=%s, flight_number=%s, 
                    nomor_tiket=%s, pnr=%s
                    WHERE id=%s
                """, [kode_maskapai, kelas_kabin, bandara_asal, bandara_tujuan, tanggal_penerbangan, flight_number, nomor_tiket, pnr, id_klaim])

            elif action == 'delete':
                id_klaim = request.POST.get('id_klaim')
                cursor.execute("DELETE FROM CLAIM_MISSING_MILES WHERE id=%s", [id_klaim])

            return redirect('klaim_miles')
        
        # READ (GET)
        # Mengambil klaim hanya milik member yang sedang login
        if status_filter in ['menunggu', 'disetujui', 'ditolak']:
            cursor.execute("""
                SELECT c.id, c.maskapai AS kode_maskapai, c.bandara_asal, c.bandara_tujuan, c.tanggal_penerbangan, c.flight_number, c.nomor_tiket, c.pnr, c.kelas_kabin, c.status_penerimaan, c.timestamp AS tanggal_pengajuan, m.nama_maskapai,
                    ba.iata_code AS iata_code_asal, ba.nama AS nama_bandara_asal, ba.kota AS kota_asal, ba.negara AS negara_asal,
                    bt.iata_code AS iata_code_tujuan, bt.nama AS nama_bandara_tujuan, bt.kota AS kota_tujuan, bt.negara AS negara_tujuan
                FROM CLAIM_MISSING_MILES c
                JOIN MASKAPAI m ON c.maskapai = m.kode_maskapai
                JOIN BANDARA ba ON c.bandara_asal = ba.iata_code
                JOIN BANDARA bt ON c.bandara_tujuan = bt.iata_code
                WHERE email_member = %s AND status_penerimaan = %s
                ORDER BY tanggal_penerbangan DESC 
            """, [email_user, status_filter.title()])
        else:
            cursor.execute("""
                SELECT c.id, c.maskapai AS kode_maskapai, c.bandara_asal, c.bandara_tujuan, c.tanggal_penerbangan, c.flight_number, c.nomor_tiket, c.pnr, c.kelas_kabin, c.status_penerimaan, c.timestamp AS tanggal_pengajuan, m.nama_maskapai,
                    ba.iata_code AS iata_code_asal, ba.nama AS nama_bandara_asal, ba.kota AS kota_asal, ba.negara AS negara_asal,
                    bt.iata_code AS iata_code_tujuan, bt.nama AS nama_bandara_tujuan, bt.kota AS kota_tujuan, bt.negara AS negara_tujuan
                FROM CLAIM_MISSING_MILES c
                JOIN MASKAPAI m ON c.maskapai = m.kode_maskapai
                JOIN BANDARA ba ON c.bandara_asal = ba.iata_code
                JOIN BANDARA bt ON c.bandara_tujuan = bt.iata_code
                WHERE email_member = %s
                ORDER BY tanggal_penerbangan DESC
            """, [email_user])

        claim_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT kode_maskapai, nama_maskapai
            FROM MASKAPAI
        """)
        maskapai_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT *
            FROM BANDARA
        """)
        bandara_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    context = {
        'claim_list': claim_list,
        'maskapai_list': maskapai_list,
        'bandara_list': bandara_list,
        'current_status': status_filter
    }
        
    return render(request, 'member/klaim_miles.html', context)

@role_required('staf')
def kelola_klaim(request):
    email_user = request.session.get('email')

    status_filter = request.GET.get('status', 'semua')
    maskapai_filter = request.GET.get('maskapai', 'semua')
    tanggal_urut = request.GET.get('tanggal', 'terbaru')

    query = """
        SELECT id, CONCAT(first_mid_name, ' ', last_name) AS nama_member, email_member, maskapai, bandara_asal, bandara_tujuan, 
               tanggal_penerbangan, flight_number, kelas_kabin, 
               status_penerimaan, timestamp as tanggal_pengajuan
        FROM CLAIM_MISSING_MILES c
        JOIN PENGGUNA p ON c.email_member = p.email
        WHERE 1=1
    """
    params = []

    if status_filter != "semua":
        query += " AND status_penerimaan = %s"
        params.append(status_filter.title())

    if maskapai_filter != 'semua':
        query += " AND maskapai = %s"
        params.append(maskapai_filter)
    
    if tanggal_urut == 'terlama':
        query += " ORDER BY timestamp ASC"
    else:
        query += " ORDER BY timestamp DESC"

    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')
            id_klaim = request.POST.get('id_klaim')

            if action == "setujui":
                cursor.execute("""
                    UPDATE CLAIM_MISSING_MILES
                    SET status_penerimaan="Disetujui", email_staf=%s 
                    WHERE id = %s
                """, [email_user, id_klaim])
            
            elif action == "tolak":
                cursor.execute("""
                    UPDATE CLAIM_MISSING_MILES
                    SET status_penerimaan="Ditolak", email_staf=%s 
                    WHERE id = %s
                """, [email_user, id_klaim])
            
            return redirect('klaim_miles')
            
        cursor.execute(query, params)
        claim_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT m.kode_maskapai, m.nama_maskapai
            FROM CLAIM_MISSING_MILES c
            JOIN MASKAPAI m ON c.maskapai = m.kode_maskapai
            ORDER BY m.kode_maskapai
        """)
        maskapai_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    context = {
        "claim_list": claim_list,
        "maskapai_list": maskapai_list,
        "current_status": status_filter,
        "current_maskapai": maskapai_filter,
        "current_tanggal": tanggal_urut
    }

    return render(request, 'staf/kelola_klaim.html', context)

@role_required('member')
def transfer_miles(request):
    email_user = request.session.get('email')

    with connection.cursor() as cursor:
        cursor.execute("SELECT award_miles FROM MEMBER WHERE email = %s", [email_user])
        award_miles = cursor.fetchone()[0]

        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'create':
                email_penerima = request.POST.get('email_penerima')

                if email_penerima == email_user:
                    messages.error(request, 'Transfer kepada diri sendiri tidak diperbolehkan.')
                    return redirect('transfer_miles')

                cursor.execute("SELECT email, password FROM PENGGUNA WHERE email = %s", [email_penerima])
                user = cursor.fetchone()

                if not user:
                    messages.error(request, 'Email penerima tidak ditemukan.')
                    return redirect('transfer_miles')
                
                jumlah_miles = int(request.POST.get('jumlah_miles'))
                catatan = request.POST.get('catatan') or None

                if award_miles < jumlah_miles:
                    messages.error(request, 'Award miles tidak cukup.')
                    return redirect('transfer_miles')
                
                cursor.execute("""
                    INSERT INTO TRANSFER VALUES (%s, %s, NOW(), %s, %s)
                """, [email_user, email_penerima, jumlah_miles, catatan])

                cursor.execute("""
                    UPDATE MEMBER
                    SET award_miles = award_miles - %s
                    WHERE email = %s
                """, [award_miles, email_user])

                cursor.execute("""
                    UPDATE MEMBER
                    SET award_miles = award_miles + %s
                    WHERE email = %s
                """, [award_miles, email_penerima])

                messages.success(request, 'Transfer miles berhasil dilakukan!')
                return redirect('transfer_miles')

        cursor.execute("""
            (SELECT t.timestamp, CONCAT(p.first_mid_name, ' ', p.last_name) AS nama_member, p.email, t.jumlah, t.catatan, 'Kirim' AS tipe
            FROM TRANSFER t
            JOIN PENGGUNA p ON t.email_member_2 = p.email
            WHERE t.email_member_1 = %s)
            UNION
            (SELECT t.timestamp, CONCAT(p.first_mid_name, ' ', p.last_name) AS nama_member, p.email, t.jumlah, t.catatan, 'Terima' AS tipe
            FROM TRANSFER t
            JOIN PENGGUNA p ON t.email_member_1 = p.email
            WHERE t.email_member_2 = %s)
            ORDER BY timestamp
        """, [email_user, email_user])
        transfer_list = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    context = {
        "award_miles": award_miles,
        "transfer_list": transfer_list
    }

    return render(request, 'member/transfer_miles.html', context)

def redeem_view(request):
    email = request.session.get('email')

    with connection.cursor() as cursor:

        # ✅ ambil award miles user
        cursor.execute("""
            SELECT award_miles 
            FROM MEMBER 
            WHERE email = %s
        """, [email])
        award_miles = cursor.fetchone()[0]

        # ✅ katalog hadiah (FIX JOIN SESUAI ERD)
        cursor.execute("""
            SELECT h.kode_hadiah, h.nama, h.miles, h.deskripsi,
                   h.valid_start_date, h.program_end,
                   m.nama_maskapai
            FROM HADIAH h
            JOIN PENYEDIA p ON h.id_penyedia = p.id
            LEFT JOIN MASKAPAI m ON m.id_penyedia = p.id
            WHERE h.program_end >= CURRENT_DATE
            ORDER BY h.kode_hadiah
        """)
        katalog = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

        # ✅ riwayat redeem
        cursor.execute("""
            SELECT h.nama, r.timestamp, h.miles
            FROM REDEEM r
            JOIN HADIAH h ON r.kode_hadiah = h.kode_hadiah
            WHERE r.email_member = %s
            ORDER BY r.timestamp DESC
        """, [email])
        riwayat = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

    return render(request, 'member/redeem.html', {
        'award_miles': award_miles,
        'katalog': katalog,
        'riwayat': riwayat
    })

def proses_redeem(request):
    if request.method == 'POST':
        email = request.session.get('email')
        kode_hadiah = request.POST.get('kode_hadiah')

        with connection.cursor() as cursor:

            # ambil miles hadiah
            cursor.execute("""
                SELECT miles FROM HADIAH WHERE kode_hadiah = %s
            """, [kode_hadiah])
            miles = cursor.fetchone()[0]

            # ambil miles user
            cursor.execute("""
                SELECT award_miles FROM MEMBER WHERE email = %s
            """, [email])
            user_miles = cursor.fetchone()[0]

            if user_miles >= miles:

                # insert redeem
                cursor.execute("""
                    INSERT INTO REDEEM (email_member, kode_hadiah, timestamp)
                    VALUES (%s, %s, NOW())
                """, [email, kode_hadiah])

                # update miles
                cursor.execute("""
                    UPDATE MEMBER
                    SET award_miles = award_miles - %s
                    WHERE email = %s
                """, [miles, email])

        return redirect('redeem')
    
def package_view(request):
    email = request.session.get('email')

    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT award_miles FROM MEMBER WHERE email = %s
        """, [email])
        award_miles = cursor.fetchone()[0]

        cursor.execute("""
            SELECT id, jumlah_award_miles, harga_paket
            FROM AWARD_MILES_PACKAGE
            ORDER BY jumlah_award_miles
        """)
        packages = [
            dict(zip([col[0] for col in cursor.description], row))
            for row in cursor.fetchall()
        ]

    return render(request, 'member/package.html', {
        'award_miles': award_miles,
        'packages': packages
    })
    
def beli_package(request):
    if request.method == 'POST':
        email = request.session.get('email')
        id_package = request.POST.get('id_package')

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT jumlah_award_miles, harga_paket 
                FROM AWARD_MILES_PACKAGE 
                WHERE id = %s
            """, [id_package])
            miles, harga = cursor.fetchone()

            cursor.execute("""
                INSERT INTO MEMBER_AWARD_MILES_PACKAGE 
                (email_member, id_package, timestamp)
                VALUES (%s, %s, NOW())
            """, [email, id_package])

            cursor.execute("""
                UPDATE MEMBER
                SET award_miles = award_miles + %s
                WHERE email = %s
            """, [miles, email])

        return redirect('package')

def tier_view(request):
    email = request.session.get('email')

    with connection.cursor() as cursor:

        # ambil data member
        cursor.execute("""
            SELECT award_miles, id_tier
            FROM MEMBER
            WHERE email = %s
        """, [email])
        award_miles, current_tier = cursor.fetchone()

        # ambil semua tier
        cursor.execute("""
            SELECT id_tier, nama, minimal_frekuensi_terbang, minimal_tier_miles
            FROM TIER
            ORDER BY minimal_tier_miles
        """)
        tiers = [
            dict(zip([col[0] for col in cursor.description], row))
            for row in cursor.fetchall()
        ]

    # ================= BENEFITS =================
    for t in tiers:
        if t['nama'].lower() == 'bronze':
            t['benefits'] = [
                'Akumulasi miles dasar',
                'Akses penawaran member'
            ]
        elif t['nama'].lower() == 'silver':
            t['benefits'] = [
                'Bonus miles 25%',
                'Priority check-in',
                'Akses lounge partner'
            ]
        elif t['nama'].lower() == 'gold':
            t['benefits'] = [
                'Bonus miles 50%',
                'Priority boarding',
                'Akses lounge premium',
                'Extra bagasi 10kg'
            ]
        elif t['nama'].lower() == 'platinum':
            t['benefits'] = [
                'Bonus miles 100%',
                'Upgrade gratis (jika tersedia)',
                'Akses lounge first class',
                'Extra bagasi 20kg',
                'Dedicated hotline'
            ]

    next_tier = None
    for t in tiers:
        if award_miles < t['minimal_tier_miles']:
            next_tier = t
            break

    progress = 0
    if next_tier:
        progress = int((award_miles / next_tier['minimal_tier_miles']) * 100)

    return render(request, 'member/tier.html', {
        'tiers': tiers,
        'current_tier': current_tier,
        'award_miles': award_miles,
        'next_tier': next_tier,
        'progress': progress
    })

from django.shortcuts import render
from django.db import connection


def laporan_transaksi_view(request):
    tipe = request.GET.get('tipe', '').lower()
    tab = request.GET.get('tab', 'riwayat')

    with connection.cursor() as cursor:

        # =========================
        # RIWAYAT TRANSAKSI
        # =========================
        query = """
        SELECT * FROM (

            SELECT 
                'Transfer' AS tipe,
                email_member_1 AS email,
                jumlah AS miles,
                timestamp
            FROM TRANSFER

            UNION ALL

            SELECT 
                'Redeem' AS tipe,
                email_member AS email,
                0 AS miles,
                timestamp
            FROM REDEEM

            UNION ALL

            SELECT 
                'Claim' AS tipe,
                email_member AS email,
                0 AS miles,
                timestamp
            FROM CLAIM_MISSING_MILES
            WHERE status_penerimaan = 'Disetujui'

            UNION ALL

            SELECT 
                'Package' AS tipe,
                email_member AS email,
                0 AS miles,
                timestamp
            FROM MEMBER_AWARD_MILES_PACKAGE

        ) AS transaksi
        """

        if tipe and tipe != 'semua':
            query += " WHERE LOWER(tipe) = %s"
            cursor.execute(query, [tipe])
        else:
            cursor.execute(query)

        rows = cursor.fetchall()

    transaksi = [
        {
            'tipe': r[0],
            'email': r[1],
            'miles': r[2],
            'waktu': r[3],
        }
        for r in rows
    ]

    # =========================
    # SUMMARY
    # =========================
    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT COALESCE(SUM(total_miles), 0)
            FROM MEMBER
        """)
        total_miles = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM REDEEM
            WHERE EXTRACT(MONTH FROM timestamp) = EXTRACT(MONTH FROM CURRENT_DATE)
        """)
        total_redeem = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM CLAIM_MISSING_MILES
            WHERE status_penerimaan = 'Disetujui'
        """)
        total_klaim = cursor.fetchone()[0]

    # =========================
    # TOP MEMBER (AKTIVITAS)
    # =========================
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT email, COUNT(*) AS total_transaksi
            FROM (
                SELECT email_member_1 AS email FROM TRANSFER
                UNION ALL
                SELECT email_member FROM REDEEM
            ) t
            GROUP BY email
            ORDER BY total_transaksi DESC
            LIMIT 10
        """)
        top_rows = cursor.fetchall()

    top_member = [
        {
            'rank': i + 1,
            'email': r[0],
            'total_transaksi': r[1],
        }
        for i, r in enumerate(top_rows)
    ]

    return render(request, 'staf/laporan.html', {
        'transaksi': transaksi,
        'top_member': top_member,
        'total_miles': total_miles,
        'total_redeem': total_redeem,
        'total_klaim': total_klaim,
        'selected_tipe': tipe,
        'tab': tab,
    })