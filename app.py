from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
import os
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sjam-penilaian-secret-2024')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        npk TEXT PRIMARY KEY,
        nama TEXT,
        password TEXT,
        role TEXT,
        divisi TEXT,
        cabang TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS penilaian (
        id SERIAL PRIMARY KEY,
        npk TEXT,
        nama TEXT,
        periode TEXT,
        divisi TEXT,
        cabang TEXT,
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
        penilai TEXT,
        tgl_finalisasi TEXT,
        status TEXT
    )''')

    c.execute("SELECT COUNT(*) as count FROM users WHERE role='hrd'")
    if c.fetchone()['count'] == 0:
        c.execute("INSERT INTO users (npk, nama, password, role, divisi, cabang) VALUES (%s,%s,%s,%s)",
                 ('HRD001','HRD Admin',generate_password_hash('admin123'),'hrd','HRD','PUSAT'))
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        npk = request.form['npk']
        password = request.form['password']
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE npk=%s", (npk,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user'] = {
                'npk': user['npk'],
                'nama': user['nama'],
                'role': user['role'],
                'divisi': user['divisi'],
                'cabang': user['cabang']
            }
            return redirect('/dashboard')
        flash('NPK atau Password salah!', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        npk = request.form['npk']
        nama = request.form['nama']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        divisi = request.form['divisi']
        cabang = request.form['cabang']

        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (npk, nama, password, role, divisi, cabang) VALUES (%s,%s,%s,%s,%s,%s)", (npk, nama, password, role, divisi, cabang))
            conn.commit()
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect('/login')
        except psycopg2.IntegrityError:
            flash('NPK sudah terdaftar!', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    with get_conn() as conn:
        c = conn.cursor()
        
        if user['role'] == 'hrd':
            page = int(request.args.get('page', 1))
            per_page = 20
            c.execute("SELECT COUNT(*) as count FROM users WHERE npk!=%s", (user['npk'],))
            total = c.fetchone()['count']
            total_pages = (total + per_page - 1) // per_page
            offset = (page - 1) * per_page
            c.execute("SELECT npk,nama,divisi,role,cabang FROM users WHERE npk!=%s ORDER BY role DESC, nama LIMIT %s OFFSET %s",
                      (user['npk'], per_page, offset))
            karyawan = c.fetchall()
            c.execute("SELECT npk,nama,divisi,cabang FROM users WHERE npk NOT IN (SELECT npk FROM penilaian WHERE status='final') AND role='karyawan'")
            belum_dinilai = c.fetchall()
            
            c.execute("SELECT npk, nama, divisi, role, cabang FROM users WHERE divisi=%s AND cabang=%s AND role IN ('karyawan','kadiv') AND npk!=%s ORDER BY role DESC, nama",
                     (user['divisi'], user['cabang'], user['npk']))
            karyawan_untuk_dinilai = c.fetchall()
            
            return render_template('dashboard_hrd.html',
                                 user=user,
                                 karyawan=karyawan,
                                 belum_dinilai=belum_dinilai,
                                 page=page,
                                 total_pages=total_pages,
                                 karyawan_untuk_dinilai=karyawan_untuk_dinilai)
        
        elif user['role'] == 'kadiv':
            c.execute("SELECT npk, nama, divisi, role, cabang FROM users WHERE divisi=%s AND cabang=%s AND role IN ('karyawan','kadiv') AND npk!=%s ORDER BY role DESC, nama",
                     (user['divisi'], user['cabang'], user['npk']))
            karyawan = c.fetchall()
            c.execute("SELECT p.*, u.nama FROM penilaian p JOIN users u ON p.npk=u.npk WHERE p.penilai=%s AND p.status='draft'",
                     (user['npk'],))
            draft = c.fetchall()
            return render_template('dashboard_kadiv.html', user=user, karyawan=karyawan, draft=draft)
        
        else:
            c.execute("SELECT p.*, u.nama as nama_penilai FROM penilaian p JOIN users u ON p.penilai=u.npk WHERE p.npk=%s AND p.status='final' ORDER BY p.tgl_finalisasi DESC",
                     (user['npk'],))
            hasil = c.fetchall()
            return render_template('dashboard_karyawan.html', user=user, hasil=hasil)
            
@app.route('/penilaian/<npk>')
def penilaian(npk):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    user = session['user']
    if user['role'] not in ['hrd', 'kadiv']:
        return "Akses ditolak", 403
    
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE npk=%s", (npk,))
        karyawan = c.fetchone()
        
        if not karyawan:
            return "Karyawan tidak ditemukan", 404
            
        c.execute("SELECT * FROM penilaian WHERE npk=%s AND penilai=%s AND status='draft'", (npk, user['npk']))
        draft = c.fetchone()
        
    return render_template('form_penilaian.html', user=user, karyawan=karyawan, draft=draft)

@app.route('/submit_nilai', methods=['POST'])
@login_required
def submit_nilai():
    if current_user.role == 'hrd':
        flash('HRD tidak bisa input nilai', 'error')
        return redirect(url_for('dashboard'))

    npk_dinilai = request.form.get('npk')
    action = request.form.get('action')

    # Ambil data karyawan yang dinilai
    karyawan = Karyawan.query.filter_by(npk=npk_dinilai).first()
    if not karyawan:
        flash('Karyawan tidak ditemukan', 'error')
        return redirect(url_for('dashboard'))

    # Validasi divisi
    if current_user.role == 'kadiv' and karyawan.divisi!= current_user.divisi:
        flash('Anda hanya bisa menilai karyawan di divisi Anda', 'error')
        return redirect(url_for('dashboard'))

    # Daftar 35 indikator baru sesuai Excel
    indikator_list = [
        # KEDISIPLINAN
        'kehadiran', 'kepatuhan_aturan', 'konsistensi', 'kepatuhan_seragam', 'disiplin_kebersihan',
        # PRODUKTIVITAS KERJA
        'efisiensi', 'prioritas', 'inovasi', 'multitasking', 'peningkatan_kinerja',
        # KEHANDALAN
        'terampil', 'keputusan', 'inisiatif', 'penyelesaian_masalah', 'responsif',
        # KERJASAMA
        'menanggapi_positif', 'koordinasi', 'sikap_positif', 'tidak_komplain', 'profesional',
        # TANGGUNG JAWAB
        'tanggung_jawab_kerja', 'menerima_kesalahan', 'inventaris', 'tanpa_pengawasan', 'mengelola_prioritas',
        # KEMAMPUAN BERADAPTASI
        'belajar_cepat', 'strategi_kerja', 'tantangan_baru', 'ubah_cara_kerja', 'solusi_alternatif',
        # KOMUNIKASI
        'keramahan', 'kejelasan', 'responsif_kom', 'lapor_pelanggaran', 'keterbukaan'
    ]

    # Ambil nilai dari form
    data_nilai = {}
    for ind in indikator_list:
        data_nilai[ind] = int(request.form.get(ind, 2)) # default 2 = Cukup

    # Cek sudah ada penilaian draft/final atau belum
    penilaian = Penilaian.query.filter_by(npk=npk_dinilai, tahun=datetime.now().year).first()

    if action == 'draft':
        if penilaian:
            # Update draft yang ada
            for ind in indikator_list:
                setattr(penilaian, ind, data_nilai[ind])
            penilaian.status = 'draft'
            penilaian.tanggal_update = datetime.now()
        else:
            # Buat draft baru
            penilaian = Penilaian(
                npk=npk_dinilai,
                penilai_npk=current_user.npk,
                tahun=datetime.now().year,
                status='draft',
                **data_nilai
            )
            db.session.add(penilaian)

        db.session.commit()
        flash('Draft berhasil disimpan', 'success')

    elif action == 'final':
        if penilaian and penilaian.status == 'final':
            flash('Penilaian sudah difinalisasi, tidak bisa diubah', 'error')
        else:
            if penilaian:
                # Update jadi final
                for ind in indikator_list:
                    setattr(penilaian, ind, data_nilai[ind])
                penilaian.status = 'final'
                penilaian.tanggal_update = datetime.now()
            else:
                # Buat final baru
                penilaian = Penilaian(
                    npk=npk_dinilai,
                    penilai_npk=current_user.npk,
                    tahun=datetime.now().year,
                    status='final',
                    **data_nilai
                )
                db.session.add(penilaian)

            db.session.commit()
            flash('Penilaian berhasil difinalisasi', 'success')

    return redirect(url_for('dashboard'))

@app.route('/finalisasi/<int:id>')
def finalisasi(id):
    if 'user' not in session or session['user']['role']!= 'kadiv':
        return redirect('/')

    user = session['user']
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT divisi, cabang FROM penilaian WHERE id=%s", (id,))
    data = c.fetchone()
    if not data or data['divisi']!= user['divisi'] or data['cabang']!= user['cabang']:
        conn.close()
        flash('Tidak bisa finalisasi data divisi/cabang lain!', 'error')
        return redirect('/dashboard')

    c.execute("UPDATE penilaian SET status='final' WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash('Penilaian berhasil difinalisasi!', 'success')
    return redirect('/dashboard')

@app.route('/hapus_draft/<int:id>')
def hapus_draft(id):
    if 'user' not in session or session['user']['role']!= 'kadiv':
        return redirect('/')

    user = session['user']
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT divisi, cabang FROM penilaian WHERE id=%s AND status='draft'", (id,))
    data = c.fetchone()

    if not data or data['divisi']!= user['divisi'] or data['cabang']!= user['cabang']:
        conn.close()
        flash('Tidak bisa hapus data divisi/cabang lain!', 'error')
        return redirect('/dashboard')

    c.execute("DELETE FROM penilaian WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash('Draft dihapus!', 'success')
    return redirect('/dashboard')

@app.route('/hrd/tambah_karyawan', methods=['POST'])
def tambah_karyawan():
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

    npk = request.form['npk']
    nama = request.form['nama']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']
    divisi = request.form['divisi']
    cabang = request.form['cabang']

    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (npk, nama, password, role, divisi, cabang) VALUES (%s,%s,%s,%s,%s,%s)", (npk, nama, password, role, divisi, cabang))
        conn.commit()
        flash('Karyawan berhasil ditambahkan!', 'success')
    except psycopg2.IntegrityError:
        flash('NPK sudah terdaftar!', 'error')
    finally:
        conn.close()
    return redirect('/dashboard')

@app.route('/hrd/edit_karyawan/<npk>', methods=['POST'])
def edit_karyawan(npk):
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

    nama = request.form['nama']
    role = request.form['role']
    divisi = request.form['divisi']
    cabang = request.form['cabang']
    password = request.form.get('password', '')

    conn = get_conn()
    c = conn.cursor()
    if password:
        c.execute("UPDATE users SET nama=%s, password=%s, role=%s, divisi=%s, cabang=%s WHERE npk=%s",
                 (nama, generate_password_hash(password), role, divisi, cabang, npk))
    else:
        c.execute("UPDATE users SET nama=%s, role=%s, divisi=%s, cabang=%s WHERE npk=%s",
                 (nama, role, divisi, cabang, npk))
    conn.commit()
    conn.close()
    flash('Data karyawan diupdate!', 'success')
    return redirect('/dashboard')

@app.route('/hrd/hapus_karyawan/<npk>', methods=['POST'])
def hapus_karyawan(npk):
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE npk=%s", (npk,))
    c.execute("DELETE FROM penilaian WHERE npk=%s", (npk,))
    conn.commit()
    conn.close()
    flash('Karyawan & data penilaian dihapus!', 'success')
    return redirect('/dashboard')

@app.route('/hrd/download_karyawan')
def download_karyawan():
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

    conn = get_conn()
    df = pd.read_sql_query("SELECT npk, nama, divisi, role, cabang FROM users WHERE role IN ('karyawan','kadiv')", conn)
    conn.close()

    df['password'] = ''
    df = df[['npk','nama','password','role','divisi','cabang']]

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
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

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

        df = df.fillna('')
        df['npk'] = df['npk'].astype(str).str.strip()
        df['nama'] = df['nama'].astype(str).str.strip()
        df['role'] = df['role'].astype(str).str.strip()
        df['divisi'] = df['divisi'].astype(str).str.strip()
        df['cabang'] = df['cabang'].astype(str).str.strip()

        df = df[(df['npk']!= '') & (df['nama']!= '') & (df['role']!= '') & (df['divisi']!= '') & (df['cabang']!= '')]

        if df.empty:
            flash('Tidak ada data valid di Excel', 'error')
            return redirect('/dashboard')

        if len(df) > 500:
            flash('Maksimal 500 baris per upload. Pecah file Excel jadi beberapa bagian', 'error')
            return redirect('/dashboard')

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT npk FROM users")
        existing_npk = set([r['npk'] for r in c.fetchall()])

        data_batch = []
        skip = 0
        for _, row in df.iterrows():
            if row['npk'] in existing_npk:
                skip += 1
                continue

            password = str(row['password']).strip() if 'password' in df.columns and str(row['password']).strip()!= '' else '123456'
            data_batch.append((
                row['npk'],
                row['nama'],
                generate_password_hash(password),
                row['role'],
                row['divisi'],
                row['cabang']
            ))
            existing_npk.add(row['npk'])

        if data_batch:
            c.executemany("INSERT INTO users (npk, nama, password, role, divisi, cabang) VALUES (%s,%s,%s,%s,%s,%s)", data_batch)

        conn.commit()
        conn.close()
        flash(f'Upload selesai! Baru: {len(data_batch)}, Skip duplikat: {skip}', 'success')

    except Exception as e:
        flash(f'Error: {str(e)}', 'error')

    return redirect('/dashboard')

@app.route('/export_hrd')
def export_hrd():
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM penilaian WHERE status='final'", conn)
    conn.close()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rekap Final')
    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='rekap_final_sjam.xlsx')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
