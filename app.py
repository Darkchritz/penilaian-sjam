from flask import Flask, render_template, request, redirect, session, send_file, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pandas as pd
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'ganti-ini-secret-key-yang-aman'

# ===== INISIALISASI DATABASE =====
def init_db():
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    
    # Tabel users - TAMBAH kolom cabang
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (npk TEXT PRIMARY KEY, 
                  nama TEXT, 
                  password TEXT, 
                  role TEXT, 
                  divisi TEXT,
                  cabang TEXT)''')
    
    # Tabel penilaian
    c.execute('''CREATE TABLE IF NOT EXISTS penilaian
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  npk TEXT, 
                  periode TEXT,
                  divisi TEXT,
                  tanggung_jawab INTEGER,
                  inisiatif INTEGER,
                  kerjasama INTEGER,
                  kedisiplinan INTEGER,
                  kemampuan INTEGER,
                  target INTEGER,
                  proses INTEGER,
                  inovasi INTEGER,
                  nilai_akhir REAL,
                  grade TEXT,
                  is_final INTEGER DEFAULT 0,
                  tgl_finalisasi TEXT)''')
    
    # Buat akun HRD default
    c.execute("SELECT * FROM users WHERE npk='HRD001'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", 
                 ('HRD001','HRD Admin',generate_password_hash('admin123'),'hrd','HRD','PUSAT'))
    conn.commit()
    conn.close()

init_db()

# ===== HELPER =====
def hitung_grade(nilai):
    if nilai >= 90: return 'A+'
    elif nilai >= 85: return 'A'
    elif nilai >= 80: return 'B+'
    elif nilai >= 75: return 'B'
    elif nilai >= 70: return 'C+'
    elif nilai >= 65: return 'C'
    elif nilai >= 60: return 'D'
    else: return 'E'

# ===== ROUTES =====
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    npk = request.form['npk']
    password = request.form['password']
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE npk=?", (npk,))
    user = c.fetchone()
    conn.close()
    if user and check_password_hash(user[2], password):
        session['user'] = {
            'npk': user[0], 
            'nama': user[1], 
            'role': user[3], 
            'divisi': user[4],
            'cabang': user[5]
        }
        return redirect('/dashboard')
    flash('NPK atau Password salah', 'error')
    return redirect('/')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_post():
    npk = request.form['npk'].strip()
    nama = request.form['nama'].strip()
    password = request.form['password']
    role = request.form['role']
    divisi = request.form['divisi'].strip()
    cabang = request.form['cabang'].strip()
    
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", 
                 (npk, nama, generate_password_hash(password), role, divisi, cabang))
        conn.commit()
        flash('Registrasi berhasil! Silakan login', 'success')
        return redirect('/')
    except sqlite3.IntegrityError:
        flash('NPK sudah terdaftar', 'error')
        return redirect('/register')
    finally:
        conn.close()

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/')
    user = session['user']
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    
    if user['role'] == 'kadiv':
        divisi = user['divisi']
        cabang = user['cabang']
        
        # Query: ambil karyawan + kadiv lain di divisi yang sama
        # Filter cabang jika cabang diawali SJAM
        if cabang.startswith('SJAM'):
            c.execute("""SELECT npk, nama, role FROM users 
                         WHERE divisi=? AND cabang=? AND npk!=? 
                         AND role IN ('karyawan','kadiv')""", 
                     (divisi, cabang, user['npk']))
        else:
            c.execute("""SELECT npk, nama, role FROM users 
                         WHERE divisi=? AND npk!=? 
                         AND role IN ('karyawan','kadiv')""", 
                     (divisi, user['npk']))
        
        orang_divisi = [{'npk': r[0], 'nama': r[1], 'role': r[2]} for r in c.fetchall()]

        # Cek siapa aja yang udah dinilai
        c.execute("SELECT npk, nilai_akhir, grade FROM penilaian WHERE divisi=? AND is_final=0", (divisi,))
        sudah_dinilai = []
        for r in c.fetchall():
            detail = next((k for k in orang_divisi if k['npk']==r[0]), None)
            if detail:
                sudah_dinilai.append({'npk': r[0], 'nilai_akhir': r[1], 'grade': r[2], 'nama': detail['nama'], 'role': detail['role']})

        npk_sudah = [k['npk'] for k in sudah_dinilai]
        
        # Tandai status tiap orang
        for k in orang_divisi:
            k['sudah_dinilai'] = k['npk'] in npk_sudah
            if k['sudah_dinilai']:
                detail = next((s for s in sudah_dinilai if s['npk']==k['npk']), {})
                k['nilai_akhir'] = detail.get('nilai_akhir')
                k['grade'] = detail.get('grade')

        belum_dinilai = [k for k in orang_divisi if not k['sudah_dinilai']]

        conn.close()
        return render_template('dashboard_kadiv.html',
                             user=user,
                             orang_divisi=orang_divisi,
                             sudah_dinilai=sudah_dinilai,
                             belum_dinilai=belum_dinilai)
    
    elif user['role'] == 'hrd':
        c.execute("SELECT npk, periode, divisi, nilai_akhir, grade, tgl_finalisasi FROM penilaian WHERE is_final=1 ORDER BY tgl_finalisasi DESC")
        data_final = [{'npk': r[0], 'periode': r[1], 'divisi': r[2], 'nilai_akhir': r[3], 'grade': r[4], 'tgl_finalisasi': r[5]} for r in c.fetchall()]
        
        for d in data_final:
            c.execute("SELECT nama FROM users WHERE npk=?", (d['npk'],))
            res = c.fetchone()
            d['nama'] = res[0] if res else 'Unknown'
        
        c.execute("SELECT npk, nama, divisi, role, cabang FROM users WHERE role IN ('karyawan','kadiv') ORDER BY divisi, nama")
        karyawan = [{'npk': r[0], 'nama': r[1], 'divisi': r[2], 'role': r[3], 'cabang': r[4]} for r in c.fetchall()]
        
        conn.close()
        return render_template('dashboard_hrd.html', user=user, data=data_final, karyawan=karyawan)
    
    else: # karyawan
        c.execute("SELECT * FROM penilaian WHERE npk=? AND is_final=1 ORDER BY periode DESC", (user['npk'],))
        data = []
        for r in c.fetchall():
            data.append({
                'periode': r[2], 'divisi': r[3], 'tanggung_jawab': r[4],
                'inisiatif': r[5], 'kerjasama': r[6], 'kedisiplinan': r[7],
                'kemampuan': r[8], 'target': r[9], 'proses': r[10],
                'inovasi': r[11], 'nilai_akhir': r[12], 'grade': r[13],
                'tgl_finalisasi': r[15]
            })
        conn.close()
        return render_template('dashboard_karyawan.html', user=user, data=data)

@app.route('/nilai/<npk>')
def nilai_form(npk):
    if 'user' not in session or session['user']['role']!= 'kadiv': return redirect('/')
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute("SELECT nama, divisi, role, cabang FROM users WHERE npk=?", (npk,))
    karyawan = c.fetchone()
    conn.close()
    if not karyawan: 
        flash('Data tidak ditemukan', 'error')
        return redirect('/dashboard')
    return render_template('nilai_form.html', 
                          npk=npk, 
                          nama=karyawan[0], 
                          divisi=karyawan[1],
                          role=karyawan[2],
                          cabang=karyawan[3],
                          user=session['user'])

@app.route('/simpan_nilai', methods=['POST'])
def simpan_nilai():
    if 'user' not in session or session['user']['role']!= 'kadiv': return redirect('/')
    npk = request.form['npk']
    divisi = request.form['divisi']
    
    # Ambil nilai KPI 1-8
    kpi = [int(request.form[f'kpi{i}']) for i in range(1,9)]
    nilai_akhir = sum(kpi) / len(kpi)
    grade = hitung_grade(nilai_akhir)
    periode = datetime.now().strftime('%Y-%m')
    
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    # Cek udah ada belum
    c.execute("SELECT id FROM penilaian WHERE npk=? AND is_final=0", (npk,))
    if c.fetchone():
        c.execute("""UPDATE penilaian SET 
                     tanggung_jawab=?, inisiatif=?, kerjasama=?, kedisiplinan=?,
                     kemampuan=?, target=?, proses=?, inovasi=?,
                     nilai_akhir=?, grade=?, periode=?
                     WHERE npk=? AND is_final=0""", 
                 (*kpi, nilai_akhir, grade, periode, npk))
    else:
        c.execute("""INSERT INTO penilaian 
                     (npk, periode, divisi, tanggung_jawab, inisiatif, kerjasama, kedisiplinan,
                      kemampuan, target, proses, inovasi, nilai_akhir, grade, is_final) 
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                 (npk, periode, divisi, *kpi, nilai_akhir, grade))
    conn.commit()
    conn.close()
    flash(f'Penilaian berhasil disimpan. Nilai: {nilai_akhir:.2f} Grade: {grade}', 'success')
    return redirect('/dashboard')

@app.route('/finalisasi_divisi', methods=['POST'])
def finalisasi_divisi():
    if 'user' not in session or session['user']['role']!= 'kadiv': return redirect('/')
    divisi = session['user']['divisi']
    tgl = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute("UPDATE penilaian SET is_final=1, tgl_finalisasi=? WHERE divisi=? AND is_final=0", (tgl, divisi))
    conn.commit()
    conn.close()
    flash(f'Penilaian divisi {divisi} berhasil difinalisasi', 'success')
    return redirect('/dashboard')

@app.route('/export_hrd')
def export_hrd():
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    conn = sqlite3.connect('penilaian.db')
    df = pd.read_sql_query("""
        SELECT p.npk, u.nama, u.divisi, u.cabang, p.periode, p.tanggung_jawab, p.inisiatif, 
               p.kerjasama, p.kedisiplinan, p.kemampuan, p.target, p.proses, p.inovasi,
               p.nilai_akhir, p.grade, p.tgl_finalisasi
        FROM penilaian p 
        JOIN users u ON p.npk = u.npk 
        WHERE p.is_final=1
        ORDER BY p.tgl_finalisasi DESC
    """, conn)
    conn.close()
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rekap Final')
    output.seek(0)
    
    return send_file(output, 
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, 
                     download_name=f'rekap_final_sjam_{datetime.now().strftime("%Y%m%d")}.xlsx')

# ===== CRUD KARYAWAN HRD =====
@app.route('/hrd/tambah_karyawan', methods=['POST'])
def tambah_karyawan():
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    npk = request.form['npk'].strip()
    nama = request.form['nama'].strip()
    password = request.form['password'].strip()
    divisi = request.form['divisi'].strip()
    role = request.form['role'].strip()
    cabang = request.form['cabang'].strip()
    
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", 
                 (npk, nama, generate_password_hash(password), role, divisi, cabang))
        conn.commit()
        flash(f'{nama} berhasil ditambahkan', 'success')
    except sqlite3.IntegrityError:
        flash(f'NPK {npk} sudah terdaftar', 'error')
    finally:
        conn.close()
    return redirect('/dashboard')

@app.route('/hrd/edit_karyawan/<npk_lama>', methods=['POST'])
def edit_karyawan(npk_lama):
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    npk_baru = request.form['npk'].strip()
    nama = request.form['nama'].strip()
    password = request.form['password'].strip()
    divisi = request.form['divisi'].strip()
    role = request.form['role'].strip()
    cabang = request.form['cabang'].strip()

    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    try:
        if npk_baru!= npk_lama:
            c.execute("SELECT npk FROM users WHERE npk=?", (npk_baru,))
            if c.fetchone():
                flash(f'NPK {npk_baru} sudah terdaftar', 'error')
                conn.close()
                return redirect('/dashboard')

        if password:
            c.execute("UPDATE users SET npk=?, nama=?, password=?, divisi=?, role=?, cabang=? WHERE npk=?",
                     (npk_baru, nama, generate_password_hash(password), divisi, role, cabang, npk_lama))
        else:
            c.execute("UPDATE users SET npk=?, nama=?, divisi=?, role=?, cabang=? WHERE npk=?",
                     (npk_baru, nama, divisi, role, cabang, npk_lama))

        if npk_baru!= npk_lama:
            c.execute("UPDATE penilaian SET npk=? WHERE npk=?", (npk_baru, npk_lama))

        conn.commit()
        flash(f'Data {nama} berhasil diupdate', 'success')
    except Exception as e:
        flash(f'Gagal update: {str(e)}', 'error')
    finally:
        conn.close()
    return redirect('/dashboard')

@app.route('/hrd/hapus_karyawan/<npk>', methods=['POST'])
def hapus_karyawan(npk):
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE npk=?", (npk,))
    c.execute("DELETE FROM penilaian WHERE npk=?", (npk,))
    conn.commit()
    conn.close()
    flash('Data karyawan berhasil dihapus', 'success')
    return redirect('/dashboard')

@app.route('/hrd/download_karyawan')
def download_karyawan():
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    conn = sqlite3.connect('penilaian.db')
    df = pd.read_sql_query("SELECT npk, nama, divisi, role, cabang FROM users WHERE role IN ('karyawan','kadiv')", conn)
    conn.close()
    
    # Tambah kolom password kosong buat template
    df['password'] = ''
    df = df[['npk','nama','password','role','divisi','cabang']] # urutin kolomnya
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template Karyawan')
    output.seek(0)
    
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='template_karyawan_sjam.xlsx')

@app.route('/hrd/upload_karyawan', methods=['POST'])
def upload_karyawan():
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    file = request.files['file']
    if file.filename == '':
        flash('Pilih file dulu', 'error')
        return redirect('/dashboard')
    
    try:
        df = pd.read_excel(file)
        required_cols = ['npk', 'nama', 'role', 'divisi', 'cabang']
        for col in required_cols:
            if col not in df.columns:
                flash(f'Kolom {col} tidak ditemukan. Header harus: npk, nama, password, role, divisi, cabang', 'error')
                return redirect('/dashboard')
        
        # Bersihin data dulu
        df = df.fillna('') # ganti NaN jadi string kosong
        df['npk'] = df['npk'].astype(str).str.strip()
        df['nama'] = df['nama'].astype(str).str.strip()
        df['role'] = df['role'].astype(str).str.strip()
        df['divisi'] = df['divisi'].astype(str).str.strip()
        df['cabang'] = df['cabang'].astype(str).str.strip()
        
        # Hapus baris yang NPK/Nama kosong
        df = df[(df['npk'] != '') & (df['nama'] != '') & (df['role'] != '') & (df['divisi'] != '') & (df['cabang'] != '')]
        
        if df.empty:
            flash('Tidak ada data valid di Excel', 'error')
            return redirect('/dashboard')
        
        # Limit 500 baris sekali upload biar ga timeout
        if len(df) > 500:
            flash('Maksimal 500 baris per upload. Pecah file Excel jadi beberapa bagian', 'error')
            return redirect('/dashboard')
        
        conn = sqlite3.connect('penilaian.db')
        c = conn.cursor()
        
        # Batch insert pake executemany - jauh lebih cepet
        data_batch = []
        for _, row in df.iterrows():
            password = str(row['password']).strip() if 'password' in df.columns and str(row['password']).strip() != '' else '123456'
            data_batch.append((
                row['npk'], 
                row['nama'], 
                generate_password_hash(password), 
                row['role'], 
                row['divisi'], 
                row['cabang']
            ))
        
        c.executemany("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)", data_batch)
        conn.commit()
        conn.close()
        flash(f'Upload berhasil! {len(data_batch)} data karyawan diproses', 'success')
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect('/dashboard')
        
        conn = sqlite3.connect('penilaian.db')
        c = conn.cursor()
        sukses = 0
        gagal = 0
        
        for idx, row in df.iterrows():
            try:
                # Bersihin data + handle NaN
                npk = str(row['npk']).strip() if pd.notna(row['npk']) else ''
                nama = str(row['nama']).strip() if pd.notna(row['nama']) else ''
                password = str(row['password']).strip() if 'password' in df.columns and pd.notna(row['password']) and str(row['password']).strip() != '' else '123456'
                role = str(row['role']).strip() if pd.notna(row['role']) else ''
                divisi = str(row['divisi']).strip() if pd.notna(row['divisi']) else ''
                cabang = str(row['cabang']).strip() if pd.notna(row['cabang']) else ''
                
                # Skip kalo data wajib kosong
                if not npk or not nama or not role or not divisi or not cabang:
                    gagal += 1
                    continue
                    
                c.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
                         (npk, nama, generate_password_hash(password), role, divisi, cabang))
                sukses += 1
            except Exception as e:
                gagal += 1
                continue
                
        conn.commit()
        conn.close()
        flash(f'Upload selesai! Berhasil: {sukses}, Gagal: {gagal}', 'success')
        
    except Exception as e:
        flash(f'Error baca file Excel: {str(e)}', 'error')
    
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
