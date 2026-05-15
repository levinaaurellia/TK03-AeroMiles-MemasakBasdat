import bcrypt
from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from datetime import date
from datetime import datetime
from .decorators import role_required 

def login(request):

    # Jika sudah login
    if request.session.get('email'):

        if request.session.get('role') == 'staf':
            return redirect('dashboard_staf')

        return redirect('dashboard_member')

    if request.method == 'POST':

        email = request.POST.get('email')
        password = request.POST.get('password')

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT verifikasi_login(%s, %s)
            """, [email, password])

            result = cursor.fetchone()[0]

            if result != 'LOGIN BERHASIL':

                messages.error(
                    request,
                    result
                )

                return render(
                    request,
                    'guest/login.html'
                )

            # cek role staf
            cursor.execute("""
                SELECT email
                FROM STAF
                WHERE LOWER(email) = LOWER(%s)
            """, [email])

            if cursor.fetchone():

                request.session['email'] = email
                request.session['role'] = 'staf'

                return redirect('dashboard_staf')

            # cek role member
            cursor.execute("""
                SELECT email
                FROM MEMBER
                WHERE LOWER(email) = LOWER(%s)
            """, [email])

            if cursor.fetchone():

                request.session['email'] = email
                request.session['role'] = 'member'

                return redirect('dashboard_member')

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

        # hashing password
        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # PostgreSQL crypt() lebih kompatibel dengan $2a$
        hashed_password = hashed_password.replace('$2b$', '$2a$')

        with connection.cursor() as cursor:

            try:

                # Insert ke tabel PENGGUNA
                # trigger PostgreSQL akan cek duplicate email
                cursor.execute("""
                    INSERT INTO PENGGUNA (
                        email,
                        password,
                        salutation,
                        first_mid_name,
                        last_name,
                        country_code,
                        mobile_number,
                        tanggal_lahir,
                        kewarganegaraan
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    email,
                    hashed_password,
                    salutation,
                    first_mid_name,
                    last_name,
                    country_code,
                    mobile_number,
                    tanggal_lahir,
                    kewarganegaraan
                ])

                if role == 'member':

                    # Auto-generate nomor member
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM MEMBER
                    """)

                    count = cursor.fetchone()[0] + 1

                    nomor_member = f"M{count:04d}"

                    # Ambil tier terendah
                    cursor.execute("""
                        SELECT id_tier
                        FROM TIER
                        ORDER BY minimal_tier_miles ASC
                        LIMIT 1
                    """)

                    tier_row = cursor.fetchone()

                    id_tier = tier_row[0] if tier_row else None

                    cursor.execute("""
                        INSERT INTO MEMBER (
                            email,
                            nomor_member,
                            tanggal_bergabung,
                            id_tier,
                            award_miles,
                            total_miles
                        )
                        VALUES (%s, %s, %s, %s, 0, 0)
                    """, [
                        email,
                        nomor_member,
                        date.today(),
                        id_tier
                    ])

                elif role == 'staf':

                    kode_maskapai = request.POST.get('kode_maskapai')

                    # Auto-generate id staf
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM STAF
                    """)

                    count = cursor.fetchone()[0] + 1

                    id_staf = f"S{count:04d}"

                    cursor.execute("""
                        INSERT INTO STAF (
                            email,
                            id_staf,
                            kode_maskapai
                        )
                        VALUES (%s, %s, %s)
                    """, [
                        email,
                        id_staf,
                        kode_maskapai
                    ])

                messages.success(
                    request,
                    'Registrasi berhasil! Silakan login.'
                )

                return redirect('login')

            except Exception as e:

                error_message = str(e).split("CONTEXT")[0]

                messages.error(
                    request,
                    error_message
                )

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
                    new_hashed = new_hashed.replace('$2b$', '$2a$')
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

def kelola_member(request):
    email_user = request.session.get('email')
    role_user = request.session.get('role')

    if not email_user or role_user != 'staf':
        return redirect('login') 

    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'tambah_member':
                try:
                    # 1. Hash Password
                    pw_raw = request.POST.get('password')
                    hashed_pw = bcrypt.hashpw(pw_raw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    hashed_pw = hashed_pw.replace('$2b$', '$2a$')
                    
                    # 2. Gabung Nama
                    nama_depan = request.POST.get('first_name', '').strip()
                    nama_tengah = request.POST.get('mid_name', '').strip()
                    first_mid_name = f"{nama_depan} {nama_tengah}".strip()
                    
                    # 3. Insert ke PENGGUNA
                    cursor.execute("""
                        INSERT INTO PENGGUNA (email, password, salutation, first_mid_name, last_name, 
                        country_code, mobile_number, tanggal_lahir, kewarganegaraan) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, [
                        request.POST.get('email'), hashed_pw, request.POST.get('salutation'), 
                        first_mid_name, request.POST.get('last_name'), request.POST.get('country_code'), 
                        request.POST.get('mobile_number'), request.POST.get('tanggal_lahir'), 
                        request.POST.get('kewarganegaraan')
                    ])
                    
                    # 4. Insert ke MEMBER (Nomor member otomatis di-generate oleh database)
                    tanggal_hari_ini = datetime.today().strftime('%Y-%m-%d')
                    
                    cursor.execute("SELECT id_tier FROM TIER ORDER BY id_tier ASC LIMIT 1")
                    id_tier_awal = cursor.fetchone()[0]
                    
                    cursor.execute("""
                        INSERT INTO MEMBER (tanggal_bergabung, total_miles, award_miles, id_tier, email) 
                        VALUES (%s, 0, 0, %s, %s)
                    """, [tanggal_hari_ini, id_tier_awal, request.POST.get('email')])
                    
                    messages.success(request, 'Member baru berhasil ditambahkan!')
                except Exception as e:
                    # Menampilkan error aslinya supaya kita tahu kalau ada salah
                    messages.error(request, f'Gagal menambahkan member: {str(e)}')

            elif action == 'edit_member':
                email_edit = request.POST.get('email_edit')
                
                nama_depan = request.POST.get('first_name_edit', '').strip()
                nama_tengah = request.POST.get('mid_name_edit', '').strip()
                first_mid_name = f"{nama_depan} {nama_tengah}".strip()
                
                cursor.execute("""
                    UPDATE PENGGUNA SET salutation=%s, first_mid_name=%s, last_name=%s, 
                    country_code=%s, mobile_number=%s, kewarganegaraan=%s, tanggal_lahir=%s
                    WHERE email=%s
                """, [
                    request.POST.get('salutation_edit'), first_mid_name, request.POST.get('last_name_edit'), 
                    request.POST.get('country_code_edit'), request.POST.get('mobile_number_edit'), 
                    request.POST.get('kewarganegaraan_edit'), request.POST.get('tanggal_lahir_edit'), email_edit
                ])
                
                # Update MEMBER (menggunakan id_tier_edit dari <select>)
                cursor.execute("UPDATE MEMBER SET id_tier=%s WHERE email=%s", 
                               [request.POST.get('tier_edit'), email_edit])
                
                messages.success(request, 'Data member berhasil diperbarui!')

            elif action == 'hapus_member':
                email_hapus = request.POST.get('email_hapus')
                try:
                    # 1. Hapus data dari tabel MEMBER dulu (Anak)
                    cursor.execute("DELETE FROM MEMBER WHERE email=%s", [email_hapus])
                    
                    # 2. Baru hapus data dari tabel PENGGUNA (Ibu)
                    cursor.execute("DELETE FROM PENGGUNA WHERE email=%s", [email_hapus])
                    
                    messages.success(request, 'Member berhasil dihapus!')
                except Exception as e:
                    # Biar aman kalau misal masih nyangkut di tabel lain (Klaim, Transfer, dll)
                    messages.error(request, f'Gagal menghapus member: {str(e)}')
                
            return redirect('kelola_member')

        # --- READ: Ambil Data Member & Join ke TIER ---
        query_member = """
            SELECT m.nomor_member, p.salutation, p.first_mid_name, p.last_name, p.email, 
                   t.nama AS nama_tier, m.id_tier, m.total_miles, m.award_miles, m.tanggal_bergabung,
                   p.country_code, p.mobile_number, p.tanggal_lahir, p.kewarganegaraan
            FROM MEMBER m
            JOIN PENGGUNA p ON m.email = p.email
            JOIN TIER t ON m.id_tier = t.id_tier
            ORDER BY m.nomor_member ASC
        """
        cursor.execute(query_member)
        
        columns = [col[0] for col in cursor.description]
        members_data = []
        for row in cursor.fetchall():
            member_dict = dict(zip(columns, row))
            member_dict['nama_lengkap'] = f"{member_dict['salutation']} {member_dict['first_mid_name']} {member_dict['last_name']}"
            
            nama_split = member_dict['first_mid_name'].split(' ', 1)
            member_dict['nama_depan_saja'] = nama_split[0] if nama_split else ''
            member_dict['nama_tengah_saja'] = nama_split[1] if len(nama_split) > 1 else ''
            
            members_data.append(member_dict)
            
        cursor.execute("SELECT id_tier, nama FROM TIER ORDER BY id_tier ASC")
        tier_list = [{'id_tier': row[0], 'nama': row[1]} for row in cursor.fetchall()]

    return render(request, 'staf/kelola_member.html', {
        'members': members_data, 
        'tier_list': tier_list
    })

def identitas_saya(request):
    # Ambil email dan role dari session login
    email_user = request.session.get('email')
    role_user = request.session.get('role')

    # Keamanan 1: Pastikan yang masuk halaman ini HANYA role 'member'
    if not email_user or role_user != 'member':
        return redirect('login') 

    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'tambah_identitas':
                try:
                    cursor.execute("""
                        INSERT INTO IDENTITAS (nomor, email_member, tanggal_habis, tanggal_terbit, negara_penerbit, jenis)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, [
                        request.POST.get('nomor_dokumen'),
                        email_user, # Otomatis pakai email member yang sedang login
                        request.POST.get('tanggal_habis'),
                        request.POST.get('tanggal_terbit'),
                        request.POST.get('negara_penerbit'),
                        request.POST.get('jenis_dokumen')
                    ])
                    messages.success(request, 'Identitas baru berhasil ditambahkan!')
                except Exception as e:
                    # Error kalau nomor dokumen sudah ada di database (Primary Key constraint)
                    messages.error(request, 'Gagal menambahkan identitas: Nomor dokumen sudah terdaftar.')

            elif action == 'edit_identitas':
                try:
                    # Keamanan 2: UPDATE harus menyertakan email_member agar tidak bisa mengedit data orang lain
                    cursor.execute("""
                        UPDATE IDENTITAS 
                        SET jenis=%s, negara_penerbit=%s, tanggal_terbit=%s, tanggal_habis=%s
                        WHERE nomor=%s AND email_member=%s
                    """, [
                        request.POST.get('jenis_dokumen'),
                        request.POST.get('negara_penerbit'),
                        request.POST.get('tanggal_terbit'),
                        request.POST.get('tanggal_habis'),
                        request.POST.get('nomor_dokumen'), # Dari input readonly
                        email_user 
                    ])
                    messages.success(request, 'Identitas berhasil diperbarui!')
                except Exception as e:
                    messages.error(request, f'Gagal mengedit identitas: {str(e)}')

            elif action == 'hapus_identitas':
                try:
                    # Keamanan 3: DELETE harus menyertakan email_member
                    cursor.execute("DELETE FROM IDENTITAS WHERE nomor=%s AND email_member=%s", [
                        request.POST.get('nomor_dokumen_hapus'),
                        email_user
                    ])
                    messages.success(request, 'Identitas berhasil dihapus!')
                except Exception as e:
                    messages.error(request, f'Gagal menghapus identitas: {str(e)}')

            return redirect('identitas_saya')

        # --- READ: Ambil Data Identitas khusus milik Member yang sedang login ---
        cursor.execute("""
            SELECT nomor, jenis, negara_penerbit, tanggal_terbit, tanggal_habis
            FROM IDENTITAS
            WHERE email_member = %s
            ORDER BY tanggal_habis DESC
        """, [email_user])
        
        columns = [col[0] for col in cursor.description]
        identitas_list = []
        hari_ini = datetime.today().date()
        
        for row in cursor.fetchall():
            identitas_dict = dict(zip(columns, row))
            
            # Ubah nama key agar cocok dengan variabel di file HTML
            identitas_dict['nomor_dokumen'] = identitas_dict.pop('nomor')
            identitas_dict['jenis_dokumen'] = identitas_dict.pop('jenis')
            
            # Logika Cek Status Kedaluwarsa
            tgl_habis = identitas_dict['tanggal_habis']
            if tgl_habis and tgl_habis < hari_ini:
                identitas_dict['status'] = 'Kedaluwarsa'
            else:
                identitas_dict['status'] = 'Aktif'
                
            identitas_list.append(identitas_dict)

    return render(request, 'member/identitas_saya.html', {
        'identitas_list': identitas_list
    })

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

                try:
                    # Generate ID klaim
                    cursor.execute("SELECT MAX(id) FROM CLAIM_MISSING_MILES")
                    max_id = cursor.fetchone()[0]
                    id_klaim = int(max_id) + 1 if max_id else 1

                    cursor.execute("""
                        INSERT INTO CLAIM_MISSING_MILES (id, email_member, maskapai, bandara_asal, bandara_tujuan, tanggal_penerbangan, flight_number, nomor_tiket, kelas_kabin, pnr, status_penerimaan, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, [id_klaim, email_user, kode_maskapai, bandara_asal, bandara_tujuan, tanggal_penerbangan, flight_number, nomor_tiket, kelas_kabin, pnr, "Menunggu"])
                    
                    messages.success(request, "Klaim berhasil diajukan!")
                except Exception as e:
                    error_message = str(e).split("CONTEXT")[0]
                    messages.error(request, error_message)

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

    status_filter = request.GET.get('status', '')
    maskapai_filter = request.GET.get('maskapai', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    query = """
        SELECT id, CONCAT(first_mid_name, ' ', last_name) AS nama_member, email_member, maskapai, bandara_asal, bandara_tujuan, 
               tanggal_penerbangan, flight_number, kelas_kabin, 
               status_penerimaan, timestamp as tanggal_pengajuan
        FROM CLAIM_MISSING_MILES c
        JOIN PENGGUNA p ON c.email_member = p.email
        WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND status_penerimaan = %s"
        params.append(status_filter.title())

    if maskapai_filter:
        query += " AND maskapai = %s"
        params.append(maskapai_filter)
    
    if start_date and end_date:
        query += " AND DATE(timestamp) BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    
    # Urutkan hasil klaim berdasarkan tanggal pengajuan terbaru
    query += " ORDER BY timestamp DESC"

    with connection.cursor() as cursor:
        if request.method == 'POST':
            action = request.POST.get('action')
            id_klaim = request.POST.get('id_klaim')

            try:
                if action == "setujui":
                    cursor.execute("""
                        UPDATE CLAIM_MISSING_MILES
                        SET status_penerimaan = 'Disetujui', email_staf = %s 
                        WHERE id = %s
                    """, [email_user, id_klaim])
                    
                    notices = connection.connection.notices
                    if notices:
                        for notice in notices:
                            messages.success(request, str(notice))
                        connection.connection.notices.clear()
                    else:
                        messages.success(request, "Klaim berhasil disetujui.")
                
                elif action == "tolak":
                    cursor.execute("""
                        UPDATE CLAIM_MISSING_MILES
                        SET status_penerimaan = 'Ditolak', email_staf = %s 
                        WHERE id = %s
                    """, [email_user, id_klaim])
                    messages.warning(request, "Klaim telah ditolak.")

            except Exception as e:
                messages.error(request, f"Gagal memproses klaim: {str(e)}")
            
            return redirect('kelola_klaim')
            
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
        "current_start_date": start_date,
        "current_end_date": end_date
    }

    return render(request, 'staf/kelola_klaim.html', context)

@role_required('member')
def transfer_miles(request):
    email_user = request.session.get('email')

    with connection.cursor() as cursor:

        # ambil award miles user
        cursor.execute("""
            SELECT award_miles
            FROM MEMBER
            WHERE email = %s
        """, [email_user])

        award_miles = cursor.fetchone()[0]

        # trigger
        if request.method == 'POST':

            action = request.POST.get('action')

            if action == 'create':

                email_penerima = request.POST.get('email_penerima')
                jumlah_miles = int(request.POST.get('jumlah_miles'))
                catatan = request.POST.get('catatan') or None

                if action == 'create':

                    email_penerima = request.POST.get('email_penerima')
                    jumlah_miles = int(request.POST.get('jumlah_miles'))
                    catatan = request.POST.get('catatan') or None

                    try:
                        # Tetap pertahankan validasi apakah email penerima itu ada di database
                        cursor.execute("""
                            SELECT email
                            FROM MEMBER
                            WHERE email = %s
                        """, [email_penerima])

                        penerima = cursor.fetchone()

                        if not penerima:
                            messages.error(request, 'Email penerima tidak ditemukan.')
                            return redirect('transfer_miles')
                        
                        # Kalau sudah valid, langsung eksekusi INSERT ke tabel TRANSFER.
                        # Validasi saldo akan dilakukan di trigger DB trg_cek_saldo_transfer
                        # update saldo pengirim & penerima akan dilakukan di trigger DB trg_proses_transfer_miles
                        cursor.execute("""
                            INSERT INTO TRANSFER (
                                email_member_1,
                                email_member_2,
                                timestamp,
                                jumlah,
                                catatan
                            )
                            VALUES (%s, %s, NOW(), %s, %s)
                        """, [
                            email_user,
                            email_penerima,
                            jumlah_miles,
                            catatan
                        ])

                        messages.success(request, 'Transfer miles berhasil dilakukan!')
                        return redirect('transfer_miles')

                    except Exception as e:
                        error_message = str(e).split("CONTEXT")[0]
                        messages.error(request, error_message)
                        return redirect('transfer_miles')
                
        cursor.execute("""
            (SELECT 
                t.timestamp,
                CONCAT(p.first_mid_name, ' ', p.last_name) AS nama_member,
                p.email,
                t.jumlah,
                t.catatan,
                'Kirim' AS tipe
            FROM TRANSFER t
            JOIN PENGGUNA p 
                ON t.email_member_2 = p.email
            WHERE t.email_member_1 = %s)

            UNION

            (SELECT 
                t.timestamp,
                CONCAT(p.first_mid_name, ' ', p.last_name) AS nama_member,
                p.email,
                t.jumlah,
                t.catatan,
                'Terima' AS tipe
            FROM TRANSFER t
            JOIN PENGGUNA p 
                ON t.email_member_1 = p.email
            WHERE t.email_member_2 = %s)

            ORDER BY timestamp DESC
        """, [email_user, email_user])

        transfer_list = [
            dict(zip([col[0] for col in cursor.description], row))
            for row in cursor.fetchall()
        ]

    context = {
        "award_miles": award_miles,
        "transfer_list": transfer_list
    }

    return render(
        request,
        'member/transfer_miles.html',
        context
    )

def redeem_view(request):
    email = request.session.get('email')

    with connection.cursor() as cursor:

        # ambil award miles user
        cursor.execute("""
            SELECT award_miles 
            FROM MEMBER 
            WHERE email = %s
        """, [email])
        award_miles = cursor.fetchone()[0]

        # katalog hadiah (FIX JOIN SESUAI ERD)
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

        # riwayat redeem
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
            try:
                # hanya insert ke tabel REDEEM, update award miles akan otomatis karena trigger DB
                cursor.execute("""
                    INSERT INTO REDEEM (email_member, kode_hadiah, timestamp)
                    VALUES (%s, %s, NOW())
                """, [email, kode_hadiah])
                
                messages.success(request, 'Redeem hadiah berhasil!')
            except Exception as e:
                error_message = str(e).split("CONTEXT")[0]
                messages.error(request, error_message)

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
            try:
                # hanya dilakukan insert, update award miles akan otomatis karena trigger DB
                cursor.execute("""
                    INSERT INTO MEMBER_AWARD_MILES_PACKAGE 
                    (email_member, id_award_miles_package, timestamp)
                    VALUES (%s, %s, NOW())
                """, [email, id_package])

                messages.success(request, 'Pembelian package berhasil!')
            except Exception as e:
                error_message = str(e).split("CONTEXT")[0]
                messages.error(request, error_message)

        return redirect('package')

def tier_view(request):
    email = request.session.get('email')

    with connection.cursor() as cursor:

        cursor.execute("""
            SELECT total_miles, id_tier
            FROM MEMBER
            WHERE email = %s
        """, [email])
        total_miles, current_tier = cursor.fetchone()

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
        if total_miles < t['minimal_tier_miles']:
            next_tier = t
            break

    progress = 0
    if next_tier:
        progress = int((total_miles / next_tier['minimal_tier_miles']) * 100)

    return render(request, 'member/tier.html', {
        'tiers': tiers,
        'current_tier': current_tier,
        'total_miles': total_miles, 
        'next_tier': next_tier,
        'progress': progress
    })

def laporan_transaksi_view(request):
    tipe = request.GET.get('tipe', '').lower()
    tab = request.GET.get('tab', 'riwayat')

    # =========================
    # QUERY UTAMA (LEDGER)
    # =========================
    base_query = """
        SELECT * FROM (

            -- TRANSFER KELUAR
            SELECT 
                'transfer' AS tipe,
                email_member_1 AS email,
                -jumlah AS miles,
                timestamp
            FROM TRANSFER

            UNION ALL

            -- TRANSFER MASUK
            SELECT 
                'transfer' AS tipe,
                email_member_2 AS email,
                jumlah AS miles,
                timestamp
            FROM TRANSFER

            UNION ALL

            -- REDEEM
            SELECT 
                'redeem' AS tipe,
                r.email_member AS email,
                -h.miles AS miles,
                r.timestamp
            FROM REDEEM r
            JOIN HADIAH h 
                ON r.kode_hadiah = h.kode_hadiah

            UNION ALL

            -- CLAIM (hanya disetujui)
            SELECT 
                'claim' AS tipe,
                email_member AS email,
                1000 AS miles,
                timestamp
            FROM CLAIM_MISSING_MILES
            WHERE status_penerimaan = 'Disetujui'

            UNION ALL

            -- PACKAGE
            SELECT 
                'package' AS tipe,
                m.email_member AS email,
                a.jumlah_award_miles AS miles,
                m.timestamp
            FROM MEMBER_AWARD_MILES_PACKAGE m
            JOIN AWARD_MILES_PACKAGE a 
                ON m.id_award_miles_package = a.id

        ) AS transaksi
    """
    
    if tipe and tipe != 'semua':
        final_query = f"""
            SELECT * FROM (
                {base_query}
            ) AS filtered
            WHERE LOWER(tipe) = %s
            ORDER BY timestamp DESC
        """
        params = [tipe]
    else:
        final_query = f"""
            {base_query}
            ORDER BY timestamp DESC
        """
        params = []

    with connection.cursor() as cursor:
        cursor.execute(final_query, params)
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

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COALESCE(SUM(miles),0)
            FROM (

                SELECT -jumlah AS miles FROM TRANSFER
                UNION ALL
                SELECT jumlah FROM TRANSFER

                UNION ALL
                SELECT -h.miles 
                FROM REDEEM r 
                JOIN HADIAH h ON r.kode_hadiah = h.kode_hadiah

                UNION ALL
                SELECT 1000 
                FROM CLAIM_MISSING_MILES 
                WHERE status_penerimaan = 'Disetujui'

                UNION ALL
                SELECT a.jumlah_award_miles
                FROM MEMBER_AWARD_MILES_PACKAGE m
                JOIN AWARD_MILES_PACKAGE a 
                ON m.id_award_miles_package = a.id

            ) x
        """)
        total_miles = cursor.fetchone()[0]

        # total redeem bulan ini
        cursor.execute("""
            SELECT COUNT(*)
            FROM REDEEM
            WHERE DATE_TRUNC('month', timestamp) = DATE_TRUNC('month', CURRENT_DATE)
        """)
        total_redeem = cursor.fetchone()[0]

        # total claim disetujui
        cursor.execute("""
            SELECT COUNT(*)
            FROM CLAIM_MISSING_MILES
            WHERE status_penerimaan = 'Disetujui'
        """)
        total_klaim = cursor.fetchone()[0]

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT email, COUNT(*) AS total_transaksi
            FROM (

                SELECT email_member_1 AS email FROM TRANSFER
                UNION ALL
                SELECT email_member_2 FROM TRANSFER

                UNION ALL
                SELECT email_member FROM REDEEM

                UNION ALL
                SELECT email_member 
                FROM CLAIM_MISSING_MILES 
                WHERE status_penerimaan = 'Disetujui'

                UNION ALL
                SELECT email_member 
                FROM MEMBER_AWARD_MILES_PACKAGE

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
    
def hapus_transaksi(request):
    if request.method == "POST":
        email = request.POST.get('email')
        waktu = request.POST.get('timestamp')
        tipe = request.POST.get('tipe')

        with connection.cursor() as cursor:

            if tipe == "Transfer":
                cursor.execute("""
                    DELETE FROM TRANSFER
                    WHERE email_member_1 = %s AND timestamp = %s
                """, [email, waktu])

            elif tipe == "Redeem":
                cursor.execute("""
                    DELETE FROM REDEEM
                    WHERE email_member = %s AND timestamp = %s
                """, [email, waktu])

            elif tipe == "Claim":
                cursor.execute("""
                    DELETE FROM CLAIM_MISSING_MILES
                    WHERE email_member = %s AND timestamp = %s
                """, [email, waktu])

            elif tipe == "Package":
                cursor.execute("""
                    DELETE FROM MEMBER_AWARD_MILES_PACKAGE
                    WHERE email_member = %s AND timestamp = %s
                """, [email, waktu])

        return redirect('laporan_transaksi')