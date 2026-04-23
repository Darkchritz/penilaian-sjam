from flask import Flask, render_template, request, redirect, session, jsonify, send_file, flash
import sqlite3, os, json, io
from datetime import datetime
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = 'ganti-ini-jadi-random-8w3h2k1j4h1k2j3h4k5j'

# ===== CONFIG BOBOT & INDIKATOR =====
INDIKATOR = {
    'Kedisiplinan': {'bobot': 20, 'items': ['Masuk kerja tepat waktu','Kehadiran 26 hari kerja','Patuh pada peraturan perusahaan','Penampilan sehari-hari']},
    'Produktivitas Kerja': {'bobot': 20, 'items': ['Mencapai target kerja','Keseriusan & sikap kerja positif','Menyelesaikan pekerjaan tepat waktu']},
    'Kehandalan': {'bobot': 15, 'items': ['Terampil & jarang salah','Pengetahuan lebih tentang pekerjaan','Inisiatif pengembangan target kerja','Memperbaiki kekurangan & memecahkan masalah']},
    'Kerjasama': {'bobot': 10, 'items': ['Antusias menerima tugas baru','Keterbukaan pada saran & ide','Sikap positif & kerjasama tim','Tidak ada komplain dengan rekan kerja']},
    'Tanggung Jawab': {'bobot': 15, 'items': ['Bertanggung jawab pada pekerjaan','Menerima kritik dengan baik','Menjaga inventaris kantor','Berpikir jauh ke depan']},
    'Kemampuan Beradaptasi': {'bobot': 10, 'items': ['Beradaptasi dengan perubahan','Antusias terhadap tantangan & ide baru','Mengatur ulang pekerjaan sesuai perubahan']},
    'Komunikasi': {'bobot': 10, 'items': ['Ramah dalam komunikasi','Menyampaikan masalah ke atasan','Membantu orang lain bila dibutuhkan']}
}

def get_grade(nilai):
    if nilai >= 95: return 'A+'
    elif nilai >= 90: return 'A'
    elif nilai >= 85: return 'B+'
    elif nilai >= 80: return 'B'
    elif nilai >= 75: return 'C+'
    elif nilai >= 70: return 'C'
    elif nilai >= 65: return 'D+'
    elif nilai >= 60: return 'D'
    else: return 'E'

def hitung_nilai(form_data):
    total_nilai = 0
    detail = {}
    for aspek, data in INDIKATOR.items():
        bobot = data['bobot']
        items = data['items']
        jumlah = sum([int(form_data.get(f"{aspek}_{i}", 0)) for i in range(len(items))])
        nilai_max = len(items) * 4
        skor_aspek = (jumlah / nilai_max) * bobot if nilai_max > 0 else 0
        total_nilai += skor_aspek
        detail[aspek] = round(skor_aspek, 2)
    nilai_akhir = round(total_nilai, 2)
    grade = get_grade(nilai_akhir)
    return nilai_akhir, grade, detail

def init_db():
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (npk TEXT PRIMARY KEY, nama TEXT, password TEXT, role TEXT, divisi TEXT, cabang TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS penilaian
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, npk TEXT, periode TEXT,
                  nilai_akhir REAL, grade TEXT, detail_json TEXT, tgl_finalisasi TEXT, divisi TEXT)''')
    c.execute("INSERT OR IGNORE INTO users VALUES ('KD001','Kepala Divisi','123','kadiv','IT','Jakarta')")
    c.execute("INSERT OR IGNORE INTO users VALUES ('HRD01','Admin HRD','123','hrd','HRD','Jakarta')")
    c.execute("INSERT OR IGNORE INTO users VALUES ('K001','Budi','123','karyawan','IT','Jakarta')")
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        npk = request.form['npk']
        password = request.form['password']
        conn = sqlite3.connect('penilaian.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE npk=? AND password=?", (npk, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user'] = {'npk': user[0], 'nama': user[1], 'role': user[3], 'divisi': user[4], 'cabang': user[5]}
            return redirect('/dashboard')
        else:
            flash('NPK atau Password salah', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        npk = request.form['npk']
        nama = request.form['nama']
        password = request.form['password']
        divisi = request.form['divisi']
        cabang = request.form['cabang']

        conn = sqlite3.connect('penilaian.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (npk, nama, password, 'karyawan', divisi, cabang))
            conn.commit()
            flash('Registrasi berhasil! Silakan login', 'success')
            return redirect('/')
        except sqlite3.IntegrityError:
            flash('NPK sudah terdaftar', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/')
    user = session['user']
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()

    if user['role'] == 'kadiv':
        c.execute("SELECT npk, nama FROM users WHERE role='karyawan' AND divisi=?", (user['divisi'],))
        karyawan = c.fetchall()
        conn.close()
        return render_template('dashboard_kadiv.html', user=user, karyawan=karyawan, indikator=INDIKATOR)

    elif user['role'] == 'hrd':
        c.execute("SELECT p.*, u.nama, u.divisi FROM penilaian p JOIN users u ON p.npk=u.npk ORDER BY p.tgl_finalisasi DESC")
        data = [{'npk':r[1],'periode':r[2],'nilai_akhir':r[3],'grade':r[4],'tgl_finalisasi':r[6],'nama':r[7],'divisi':r[8],'detail':json.loads(r[5])} for r in c.fetchall()]
        conn.close()
        return render_template('dashboard_hrd.html', data=data)

    else: # karyawan
        c.execute("SELECT * FROM penilaian WHERE npk=? ORDER BY periode DESC", (user['npk'],))
        hasil = [{'periode':r[2],'nilai_akhir':r[3],'grade':r[4],'tgl_finalisasi':r[6],'keterangan':json.loads(r[5])} for r in c.fetchall()]
        conn.close()
        return render_template('dashboard_karyawan.html', user=user, hasil=hasil)

@app.route('/finalisasi', methods=['POST'])
def finalisasi():
    if 'user' not in session or session['user']['role']!= 'kadiv': return redirect('/')
    npk_karyawan = request.form['npk_karyawan']
    periode = request.form['periode']
    nilai_akhir, grade, detail = hitung_nilai(request.form)
    conn = sqlite3.connect('penilaian.db')
    c = conn.cursor()
    c.execute("INSERT INTO penilaian (npk, periode, nilai_akhir, grade, detail_json, tgl_finalisasi, divisi) VALUES (?,?,?,?,?,?,?)",
              (npk_karyawan, periode, nilai_akhir, grade, json.dumps(detail), datetime.now().strftime('%Y-%m-%d %H:%M'), session['user']['divisi']))
    conn.commit()
    conn.close()
    return redirect('/dashboard')

@app.route('/download_template')
def download_template():
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    df = pd.DataFrame(columns=['npk', 'nama', 'password', 'divisi', 'cabang'])
    df.loc[0] = ['K002', 'Contoh Nama', '123', 'IT', 'Makassar']
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template')
    output.seek(0)
    return send_file(output, download_name='template_karyawan.xlsx', as_attachment=True)

@app.route('/upload_karyawan', methods=['POST'])
def upload_karyawan():
    if 'user' not in session or session['user']['role']!= 'hrd': return redirect('/')
    file = request.files['file']
    if file.filename == '':
        flash('Tidak ada file dipilih', 'error')
        return redirect('/dashboard')

    try:
        df = pd.read_excel(file)
        conn = sqlite3.connect('penilaian.db')
        c = conn.cursor()
        sukses = 0
        for _, row in df.iterrows():
            try:
                c.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
                         (str(row['npk']), row['nama'], str(row['password']), 'karyawan', row['divisi'], row['cabang']))
                sukses += 1
            except: pass
        conn.commit()
        conn.close()
        flash(f'Berhasil upload {sukses} data karyawan', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
