from flask import Flask, render_template, request, redirect, session, send_file, flash
import sqlite3, io, os, pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sjam-penilaian-secret-2024')

def init_db():
    conn = sqlite3.connect('penilaian.db')
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        tgl_finalisasi TEXT,
        status TEXT
    )''')

    c.execute("SELECT COUNT(*) FROM users WHERE role='hrd'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
                 ('HRD001','HRD Admin',generate_password_hash('admin123'),'hrd','HRD','PUSAT'))
    conn.commit()
    conn.close()

init_db()

def hitung_nilai(tanggung_jawab, inisiatif, kerjasama, kedisiplinan, kemampuan, target, proses, inovasi):
    total = tanggung_jawab + inisiatif + kerjasama + kedisiplinan + kemampuan + target + proses + inovasi
    rata = total / 8
    if rata >= 90: grade = 'A'
    elif rata >= 80: grade = 'B'
    elif rata >= 70: grade = 'C'
    elif rata >= 60: grade = 'D'
    else: grade = 'E'
    return round(rata, 2), grade

@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
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

        conn = sqlite3.connect('penilaian.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (npk, nama, password, role, divisi, cabang))
            conn.commit()
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash('NPK sudah terdaftar!', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    user = session['user']
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()

    if user['role'] == 'hrd':
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page

        c.execute("SELECT COUNT(*) FROM users WHERE role IN ('karyawan','kadiv')")
        total_karyawan = c.fetchone()[0]
        total_pages = (total_karyawan + per_page - 1) // per_page

        c.execute("SELECT npk, nama, divisi, role, cabang FROM users WHERE role IN ('karyawan','kadiv') ORDER BY cabang, divisi, nama LIMIT? OFFSET?",
                 (per_page, offset))
        karyawan = [{'npk':r[0],'nama':r[1],'divisi':r[2],'role':r[3],'cabang':r[4]} for r in c.fetchall()]

        c.execute("""
            SELECT u.npk, u.nama, u.divisi, u.cabang
            FROM users u
            LEFT JOIN penilaian p ON u.npk = p.npk AND p.status = 'final'
            WHERE u.role IN ('karyawan','kadiv') AND p.id IS NULL
            ORDER BY u.cabang, u.divisi, u.nama
        """)
        belum_dinilai = [{'npk':r[0],'nama':r[1],'divisi':r[2],'cabang':r[3]} for r in c.fetchall()]

        conn.close()
        return render_template('dashboard_hrd.html',
                             user=user,
                             karyawan=karyawan,
                             belum_dinilai=belum_dinilai,
                             page=page,
                             total_pages=total_pages)

    elif user['role'] == 'kadiv':
        c.execute("SELECT npk, nama, divisi, role, cabang FROM users WHERE divisi=? AND cabang=? AND role IN ('karyawan','kadiv') AND npk!=? ORDER BY role DESC, nama",
                 (user['divisi'], user['cabang'], user['npk']))

        karyawan = [{'npk':r[0],'nama':r[1],'divisi':r[2],'role':r[3],'cabang':r[4]} for r in c.fetchall()]

        c.execute("SELECT * FROM penilaian WHERE status='draft' AND divisi=? AND cabang=? ORDER BY tgl_finalisasi DESC",
                 (user['divisi'], user['cabang']))

        draft = [{'id':r[0],'npk':r[1],'nama':r[2],'periode':r[3],'divisi':r[4],'cabang':r[5]} for r in c.fetchall()]
        conn.close()
        return render_template('dashboard_kadiv.html', user=user, karyawan=karyawan, draft=draft)

    else:
        c.execute("SELECT * FROM penilaian WHERE npk=? AND status='final' ORDER BY tgl_finalisasi DESC", (user['npk'],))
        data = [{'periode':r[3],'tanggung_jawab':r[6],'inisiatif':r[7],'kerjasama':r[8],'kedisiplinan':r[9],'kemampuan':r[10],'target':r[11],'proses':r[12],'inovasi':r[13],'nilai_akhir':r[14],'grade':r[15],'tgl_finalisasi':r[16]} for r in c.fetchall()]
        conn.close()
        return render_template('dashboard_karyawan.html', user=user, data=data)

@app.route('/nilai/<npk>', methods=['GET','POST'])
def nilai(npk):
    if 'user' not in session or session['user']['role']!= 'kadiv':
        return redirect('/')

    user = session['user']
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE npk=? AND divisi=? AND cabang=?", (npk, user['divisi'], user['cabang']))
    karyawan = c.fetchone()
    if not karyawan:
        conn.close()
        flash('Karyawan tidak ditemukan atau beda divisi/cabang!', 'error')
        return redirect('/dashboard')

    if request.method == 'POST':
        periode = request.form['periode']
        tj = int(request.form['tanggung_jawab'])
        inis = int(request.form['inisiatif'])
        kerja = int(request.form['kerjasama'])
        disiplin = int(request.form['kedisiplinan'])
        mampu = int(request.form['kemampuan'])
        tgt = int(request.form['target'])
        pros = int(request.form['proses'])
        inov = int(request.form['inovasi'])

        nilai_akhir, grade = hitung_nilai(tj, inis, kerja, disiplin, mampu, tgt, pros, inov)
        tgl = datetime.now().strftime('%Y-%m-%d %H:%M')

        c.execute("""INSERT INTO penilaian
            (npk,nama,periode,divisi,cabang,tanggung_jawab,inisiatif,kerjasama,kedisiplinan,kemampuan,target,proses,inovasi,nilai_akhir,grade,tgl_finalisasi,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (npk, karyawan[1], periode, karyawan[4], karyawan[5], tj, inis, kerja, disiplin, mampu, tgt, pros, inov, nilai_akhir, grade, tgl, 'draft'))
        conn.commit()
        conn.close()
        flash('Penilaian disimpan sebagai draft!', 'success')
        return redirect('/dashboard')

    conn.close()
    return render_template('form_nilai.html', user=user, karyawan={'npk':karyawan[0],'nama':karyawan[1],'divisi':karyawan[4],'cabang':karyawan[5]})

@app.route('/finalisasi/<int:id>')
def finalisasi(id):
    if 'user' not in session or session['user']['role']!= 'kadiv':
        return redirect('/')

    user = session['user']
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()

    c.execute("SELECT divisi, cabang FROM penilaian WHERE id=?", (id,))
    data = c.fetchone()
    if not data or data[0]!= user['divisi'] or data[1]!= user['cabang']:
        conn.close()
        flash('Tidak bisa finalisasi data divisi/cabang lain!', 'error')
        return redirect('/dashboard')

    c.execute("UPDATE penilaian SET status='final' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Penilaian berhasil difinalisasi!', 'success')
    return redirect('/dashboard')

@app.route('/hapus_draft/<int:id>')
def hapus_draft(id):
    if 'user' not in session or session['user']['role']!= 'kadiv':
        return redirect('/')

    user = session['user']
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute("SELECT divisi, cabang FROM penilaian WHERE id=? AND status='draft'", (id,))
    data = c.fetchone()

    if not data or data[0]!= user['divisi'] or data[1]!= user['cabang']:
        conn.close()
        flash('Tidak bisa hapus data divisi/cabang lain!', 'error')
        return redirect('/dashboard')

    c.execute("DELETE FROM penilaian WHERE id=?", (id,))
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

    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (npk, nama, password, role, divisi, cabang))
        conn.commit()
        flash('Karyawan berhasil ditambahkan!', 'success')
    except sqlite3.IntegrityError:
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

    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    if password:
        c.execute("UPDATE users SET nama=?, password=?, role=?, divisi=?, cabang=? WHERE npk=?",
                 (nama, generate_password_hash(password), role, divisi, cabang, npk))
    else:
        c.execute("UPDATE users SET nama=?, role=?, divisi=?, cabang=? WHERE npk=?",
                 (nama, role, divisi, cabang, npk))
    conn.commit()
    conn.close()
    flash('Data karyawan diupdate!', 'success')
    return redirect('/dashboard')

@app.route('/hrd/hapus_karyawan/<npk>', methods=['POST'])
def hapus_karyawan(npk):
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE npk=?", (npk,))
    c.execute("DELETE FROM penilaian WHERE npk=?", (npk,))
    conn.commit()
    conn.close()
    flash('Karyawan & data penilaian dihapus!', 'success')
    return redirect('/dashboard')

@app.route('/hrd/download_karyawan')
def download_karyawan():
    if 'user' not in session or session['user']['role']!= 'hrd':
        return redirect('/')

    conn = sqlite3.connect('penilaian.db')
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

        conn = sqlite3.connect('penilaian.db')
        c = conn.cursor()

        c.execute("SELECT npk FROM users")
        existing_npk = set([r[0] for r in c.fetchall()])

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
            c.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", data_batch)

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

    conn = sqlite3.connect('penilaian.db')
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
