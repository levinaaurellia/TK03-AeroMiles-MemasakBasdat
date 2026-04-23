from django.shortcuts import render, redirect
from django.db import connection

def login_view(request):
    return render(request, 'guest/login.html')

def register_view(request):
    return render(request, 'guest/register.html')

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