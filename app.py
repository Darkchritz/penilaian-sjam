import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import io
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sjam-penilaian-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = "strong"  # TAMBAHIN INI

class Karyawan(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    npk = db.Column(db.Integer, unique=True, nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    divisi = db.Column(db.String(50), nullable=False)
    cabang = db.Column(db.String(100), nullable=False)

    # TAMBAHIN INI: biar session cuma simpen id doang
    def get_id(self):
        return str(self.id)

class Penilaian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_karyawan = db.Column(db.Integer, db.ForeignKey('karyawan.id')) # ini udah bener
    tahun = db.Column(db.Integer)
    periode = db.Column(db.String(2))
    penilai_npk = db.Column(db.Integer)
    tanggung_jawab = db.Column(db.Integer)
    inisiatif = db.Column(db.Integer)
    kerjasama = db.Column(db.Integer)
    kedisiplinan = db.Column(db.Integer)
    kemampuan = db.Column(db.Integer)
    target = db.Column(db.Integer)
    proses = db.Column(db.Integer)
    inovasi = db.Column(db.Integer)
    status = db.Column(db.String(10), default='draft')
    tanggal_update = db.Column(db.DateTime, default=datetime.utcnow) # DITAMBAHIN

    # TAMBAHIN INI
    karyawan = db.relationship('Karyawan', backref='daftar_penilaian')

@login_manager.user_loader
def load_user(user_id):
    try:
        return Karyawan.query.get(int(user_id))
    except (ValueError, TypeError):
        return None # Kalo user_id bukan angka, anggap aja logout

@app.route('/')
@login_required
def index():
    if current_user.role == 'HRD':
        return redirect(url_for('hrd'))
    elif current_user.role == 'Kepala Divisi':
        return redirect(url_for('kadiv'))
    else:
        return redirect(url_for('karyawan'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            npk_input = request.form['npk']
            password_input = request.form['password']

            # WAJIB cast ke int karena npk di DB Integer
            user = Karyawan.query.filter_by(npk=int(npk_input)).first()

            if user and check_password_hash(user.password, password_input):
                login_user(user)
                return redirect(url_for('dashboard')) # ganti sesuai route lu
            else:
                flash('NPK atau Password salah', 'danger')

        except ValueError:
            flash('NPK harus angka', 'danger')
        except Exception as e:
            print(f"ERROR LOGIN: {e}") # biar muncul di log Railway
            flash('Terjadi error di server', 'danger')

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

        try:
            user_baru = Karyawan(npk=npk, nama=nama, password=password, role=role, divisi=divisi, cabang=cabang)
            db.session.add(user_baru)
            db.session.commit()
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect('/login')
        except:
            db.session.rollback()
            flash('NPK sudah terdaftar!', 'error')
    return render_template('register.html')

@app.route('/hrd')
@login_required
def hrd():
    if current_user.role != 'HRD':  # Cuma HRD yang lolos
        return redirect(url_for('index'))  # lempar ke / biar dicek role lagi
    
    user = current_user
    page = int(request.args.get('page', 1))
    per_page = 20
    tahun_ini = datetime.now().year
    periode_aktif = request.args.get('periode', 'Q1')

    # Master Karyawan - semua
    pagination = Karyawan.query.filter(Karyawan.npk!= user.npk).paginate(page=page, per_page=per_page, error_out=False)
    semua_karyawan = pagination.items
    total_pages = pagination.pages
    total_karyawan = pagination.total

    # Data buat tabel Penilaian - khusus divisi HRD aja
    karyawan_hrd = Karyawan.query.filter(
        Karyawan.divisi == user.divisi,
        Karyawan.cabang == user.cabang,
        Karyawan.role.in_(['karyawan','kadiv']),
        Karyawan.npk!= user.npk
    ).order_by(Karyawan.role.desc(), Karyawan.nama).all()

    penilaian_q1 = Penilaian.query.filter_by(tahun=tahun_ini, periode=periode_aktif).all()
    # DIUBAH: p.npk -> p.id_karyawan
    penilaian_dict = {p.id_karyawan: p for p in penilaian_q1}

    # DIUBAH: p.npk -> p.id_karyawan, k.npk -> k.id
    sudah_dinilai_id = [p.id_karyawan for p in penilaian_q1]
    belum_dinilai = [k for k in karyawan_hrd if k.id not in sudah_dinilai_id]

    # TAMBAHIN INI: buat tabel penilaian
    karyawan_untuk_dinilai = karyawan_hrd

    return render_template('dashboard_hrd.html',
                         user=user,
                         karyawan=semua_karyawan,
                         karyawan_hrd=karyawan_hrd,
                         karyawan_untuk_dinilai=karyawan_untuk_dinilai, # <-- INI YANG PENTING
                         belum_dinilai=belum_dinilai,
                         page=page,
                         total_pages=total_pages,
                         total_karyawan=total_karyawan,
                         penilaian_dict=penilaian_dict,
                         # DIUBAH: p.npk -> p.id_karyawan
                         status_penilaian={p.id_karyawan: p.status for p in penilaian_q1},
                         periode_aktif=periode_aktif,
                         tahun_ini=tahun_ini)

@app.route('/kadiv')
@login_required
def kadiv():
    print(f"[KADIV DEBUG] NPK:{current_user.npk} ROLE:'{current_user.role}'")
    if current_user.role != 'Kepala Divisi':
        return redirect(url_for('index'))
    
    # Kosongin dulu, biar tau errornya di query atau di template
    return render_template('kadiv.html', 
                           user=current_user,
                           belum_dinilai=[],
                           sudah_dinilai=[])

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    tahun_ini = datetime.now().year

    if user.role == 'HRD':  # GANTI JADI HURUF BESAR
        return redirect(url_for('hrd'))

    elif user.role == 'karyawan':
        # DIUBAH: npk=user.npk -> id_karyawan=user.id
        hasil = Penilaian.query.filter_by(id_karyawan=user.id, tahun=tahun_ini, periode='Q1').first()
        return render_template('dashboard_karyawan.html', user=user, hasil=hasil)

    elif user.role == 'kadiv':
        karyawan = Karyawan.query.filter(
            Karyawan.divisi == user.divisi,
            Karyawan.cabang == user.cabang,
            Karyawan.role.in_(['karyawan','kadiv']),
            Karyawan.npk!= user.npk
        ).order_by(Karyawan.role.desc(), Karyawan.nama).all()

        draft = Penilaian.query.filter_by(penilai_npk=user.npk, status='draft').all()
        return render_template('dashboard_kadiv.html', user=user, karyawan=karyawan, draft=draft)

    else:
        # DIUBAH: npk=user.npk -> id_karyawan=user.id
        hasil = Penilaian.query.filter_by(id_karyawan=user.id, status='final', tahun=tahun_ini).order_by(Penilaian.tanggal_update.desc()).first()
        return render_template('dashboard_karyawan.html', user=user, hasil=hasil)

@app.route('/nilai/<int:id>') # <-- balik ke id
@login_required
def nilai(id):
    if current_user.role!= 'hrd':
        return redirect(url_for('login'))

    periode = request.args.get('periode', 'Q1')
    tahun_ini = datetime.now().year

    karyawan = Karyawan.query.get_or_404(id) # <-- get by id

    penilaian = Penilaian.query.filter_by(
        id_karyawan=karyawan.id, # <-- pake id_karyawan
        tahun=tahun_ini,
        periode=periode
    ).first()

    return render_template('nilai_form.html',
                         karyawan=karyawan,
                         periode=periode,
                         penilaian=penilaian,
                         tahun_ini=tahun_ini)

@app.route('/penilaian/<npk>')
@login_required
def penilaian(npk):
    if current_user.role not in ['hrd', 'kadiv']:
        return "Akses ditolak", 403

    karyawan = Karyawan.query.filter_by(npk=npk).first()
    if not karyawan:
        return "Karyawan tidak ditemukan", 404

    draft = Penilaian.query.filter_by(npk=npk, penilai_npk=current_user.npk, status='draft').first()

    return render_template('form_penilaian.html', user=current_user, karyawan=karyawan, draft=draft)

@app.route('/submit_nilai', methods=['POST'])
@login_required
def submit_nilai():

    npk_dinilai = request.form.get('npk')
    action = request.form.get('action')

    karyawan = Karyawan.query.filter_by(npk=npk_dinilai).first()
    if not karyawan:
        flash('Karyawan tidak ditemukan', 'error')
        return redirect(url_for('dashboard'))

    if current_user.role == 'kadiv' and karyawan.divisi!= current_user.divisi:
        flash('Anda hanya bisa menilai karyawan di divisi Anda', 'error')
        return redirect(url_for('dashboard'))

    indikator_list = [
        'kehadiran', 'kepatuhan_aturan', 'konsistensi', 'kepatuhan_seragam', 'disiplin_kebersihan',
        'efisiensi', 'prioritas', 'inovasi', 'multitasking', 'peningkatan_kinerja',
        'terampil', 'keputusan', 'inisiatif', 'penyelesaian_masalah', 'responsif',
        'menanggapi_positif', 'koordinasi', 'sikap_positif', 'tidak_komplain', 'profesional',
        'tanggung_jawab_kerja', 'menerima_kesalahan', 'inventaris', 'tanpa_pengawasan', 'mengelola_prioritas',
        'belajar_cepat', 'strategi_kerja', 'tantangan_baru', 'ubah_cara_kerja', 'solusi_alternatif',
        'keramahan', 'kejelasan', 'responsif_kom', 'lapor_pelanggaran', 'keterbukaan'
    ]

    data_nilai = {}
    for ind in indikator_list:
        data_nilai[ind] = int(request.form.get(ind, 3)) # <-- UBAH DARI 2 JADI 3

    penilaian = Penilaian.query.filter_by(npk=npk_dinilai, tahun=datetime.now().year).first()

    if action == 'draft':
        if penilaian:
            for ind in indikator_list:
                setattr(penilaian, ind, data_nilai[ind])
            penilaian.status = 'draft'
            penilaian.tanggal_update = datetime.now()
        else:
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
                for ind in indikator_list:
                    setattr(penilaian, ind, data_nilai[ind])
                penilaian.status = 'final'
                penilaian.tanggal_update = datetime.now()
            else:
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
@login_required
def finalisasi(id):
    if current_user.role!= 'kadiv':
        return redirect('/')

    penilaian = Penilaian.query.get(id)
    if not penilaian or penilaian.karyawan.divisi!= current_user.divisi or penilaian.karyawan.cabang!= current_user.cabang:
        flash('Tidak bisa finalisasi data divisi/cabang lain!', 'error')
        return redirect('/dashboard')

    penilaian.status = 'final'
    db.session.commit()
    flash('Penilaian berhasil difinalisasi!', 'success')
    return redirect('/dashboard')

@app.route('/hapus_draft/<int:id>')
@login_required
def hapus_draft(id):
    if current_user.role!= 'kadiv':
        return redirect('/')

    penilaian = Penilaian.query.filter_by(id=id, status='draft').first()
    if not penilaian or penilaian.karyawan.divisi!= current_user.divisi or penilaian.karyawan.cabang!= current_user.cabang:
        flash('Tidak bisa hapus data divisi/cabang lain!', 'error')
        return redirect('/dashboard')

    db.session.delete(penilaian)
    db.session.commit()
    flash('Draft dihapus!', 'success')
    return redirect('/dashboard')

@app.route('/simpan_nilai/<npk>/<periode>', methods=['POST'])
@login_required
def simpan_nilai(npk, periode):
    if current_user.role!= 'hrd':
        return redirect(url_for('login'))

    karyawan = Karyawan.query.filter_by(npk=npk).first_or_404()
    tahun_ini = datetime.now().year

    # Ambil/bikin record penilaian
    # DIUBAH: npk=npk -> id_karyawan=karyawan.id
    p = Penilaian.query.filter_by(id_karyawan=karyawan.id, tahun=tahun_ini, periode=periode).first()
    if not p:
        # DIUBAH: npk=npk -> id_karyawan=karyawan.id
        p = Penilaian(id_karyawan=karyawan.id, tahun=tahun_ini, periode=periode, penilai_npk=current_user.npk)

    # Simpan 8 KPI
    p.tanggung_jawab = int(request.form.get('kpi1', 0))
    p.inisiatif = int(request.form.get('kpi2', 0))
    p.kerjasama = int(request.form.get('kpi3', 0))
    p.kedisiplinan = int(request.form.get('kpi4', 0))
    p.kemampuan = int(request.form.get('kpi5', 0))
    p.target = int(request.form.get('kpi6', 0))
    p.proses = int(request.form.get('kpi7', 0))
    p.inovasi = int(request.form.get('kpi8', 0))
    p.status = 'draft' # atau 'final' kalo mau langsung final
    p.tanggal_update = datetime.utcnow() # DITAMBAHIN

    db.session.add(p)
    db.session.commit()

    return redirect(url_for('hrd'))

@app.route('/hrd/tambah_karyawan', methods=['POST'])
@login_required
def tambah_karyawan():
    if current_user.role!= 'hrd':
        return redirect('/')

    npk = request.form['npk']
    nama = request.form['nama']
    password = generate_password_hash(request.form['password'])
    role = request.form['role']
    divisi = request.form['divisi']
    cabang = request.form['cabang']

    try:
        user_baru = Karyawan(npk=npk, nama=nama, password=password, role=role, divisi=divisi, cabang=cabang)
        db.session.add(user_baru)
        db.session.commit()
        flash('Karyawan berhasil ditambahkan!', 'success')
    except:
        db.session.rollback()
        flash('NPK sudah terdaftar!', 'error')
    return redirect('/dashboard')

@app.route('/hrd/edit_karyawan/<npk>', methods=['POST'])
@login_required
def edit_karyawan(npk):
    if current_user.role!= 'hrd':
        return redirect('/')

    karyawan = Karyawan.query.filter_by(npk=npk).first()
    if not karyawan:
        flash('Karyawan tidak ditemukan', 'error')
        return redirect('/dashboard')

    karyawan.nama = request.form['nama']
    karyawan.role = request.form['role']
    karyawan.divisi = request.form['divisi']
    karyawan.cabang = request.form['cabang']
    password = request.form.get('password', '')
    if password:
        karyawan.password = generate_password_hash(password)

    db.session.commit()
    flash('Data karyawan diupdate!', 'success')
    return redirect('/dashboard')

@app.route('/hrd/hapus_karyawan/<npk>', methods=['POST'])
@login_required
def hapus_karyawan(npk):
    if current_user.role!= 'hrd':
        return redirect('/')

    karyawan = Karyawan.query.filter_by(npk=npk).first()
    if karyawan:
        Penilaian.query.filter_by(npk=npk).delete()
        db.session.delete(karyawan)
        db.session.commit()
        flash('Karyawan & data penilaian dihapus!', 'success')
    return redirect('/dashboard')

@app.route('/hrd/download_karyawan')
@login_required
def download_karyawan():
    if current_user.role != 'HRD':
        flash('Akses ditolak', 'danger')
        return redirect('/')

    karyawan = Karyawan.query.filter(Karyawan.role.in_(['karyawan','kadiv'])).all()
    
    # FIX: handle kalo data kosong
    if not karyawan:
        df = pd.DataFrame(columns=['npk','nama','password','role','divisi','cabang'])
    else:
        df = pd.DataFrame([{
            'npk': k.npk, 'nama': k.nama, 'divisi': k.divisi, 
            'role': k.role, 'cabang': k.cabang, 'password': ''
        } for k in karyawan])
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
@login_required
def upload_karyawan():
    if current_user.role!= 'HRD':
        return redirect('/')

    file = request.files['file']
    if file.filename == '':
        flash('Pilih file dulu', 'error')
        return redirect(url_for('hrd'))

    try:
        df = pd.read_excel(file)
        print(f"[UPLOAD] Jumlah baris Excel terbaca: {len(df)}")

        required_cols = ['npk', 'nama', 'role', 'divisi', 'cabang']
        for col in required_cols:
            if col not in df.columns:
                flash(f'Kolom {col} tidak ditemukan. Header harus: npk, nama, password, role, divisi, cabang', 'error')
                return redirect(url_for('hrd'))

        df = df.fillna('')
        df['npk'] = df['npk'].apply(lambda x: int(float(x)) if str(x).strip()!= '' else '')
        print(f"[UPLOAD] 5 NPK pertama setelah convert: {df['npk'].head(5).tolist()}")

        df['nama'] = df['nama'].astype(str).str.strip()
        df['role'] = df['role'].astype(str).str.strip()
        df['divisi'] = df['divisi'].astype(str).str.strip()
        df['cabang'] = df['cabang'].astype(str).str.strip()

        df = df[(df['npk']!= '') & (df['nama']!= '') & (df['role']!= '') & (df['divisi']!= '') & (df['cabang']!= '')]
        print(f"[UPLOAD] Baris valid setelah filter: {len(df)}")

        if df.empty:
            flash('Tidak ada data valid di Excel', 'error')
            return redirect(url_for('hrd'))

        # FIX 1: Ambil semua NPK yang udah ada SEKALIGUS biar ga query di loop
        npk_list = df['npk'].tolist()
        existing_karyawan = Karyawan.query.filter(Karyawan.npk.in_(npk_list)).all()
        existing_npk_dict = {k.npk: k for k in existing_karyawan}
        print(f"[UPLOAD] NPK yang sudah ada di DB: {len(existing_npk_dict)}")

        data_baru = []
        data_update = 0

        # FIX 2: Matikan autoflush selama loop
        with db.session.no_autoflush:
            for _, row in df.iterrows():
                npk = row['npk']
                password = str(row['password']).strip() if 'password' in df.columns and str(row['password']).strip()!= '' else '123456'

                if npk in existing_npk_dict:
                    # UPDATE
                    existing = existing_npk_dict[npk]
                    existing.nama = row['nama']
                    existing.password = generate_password_hash(password)
                    existing.role = row['role']
                    existing.divisi = row['divisi']
                    existing.cabang = row['cabang']
                    data_update += 1
                else:
                    # INSERT
                    data_baru.append(Karyawan(
                        npk=npk,
                        nama=row['nama'],
                        password=generate_password_hash(password),
                        role=row['role'],
                        divisi=row['divisi'],
                        cabang=row['cabang']
                    ))

        if data_baru:
            db.session.add_all(data_baru)

        print(f"[UPLOAD] SEBELUM COMMIT - Baru: {len(data_baru)}, Update: {data_update}")
        db.session.commit()
        print(f"[UPLOAD] COMMIT BERHASIL")
        flash(f'Upload selesai! Data baru: {len(data_baru)}, Data diupdate: {data_update}', 'success')

    except Exception as e:
        db.session.rollback()
        print(f"[UPLOAD] ERROR: {str(e)}")
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('hrd'))

@app.route('/cek_total')
@login_required
def cek_total():
    if current_user.role != 'HRD': return 'Akses ditolak'
    total = Karyawan.query.count()
    npk_list = [k.npk for k in Karyawan.query.order_by(Karyawan.npk.desc()).limit(5).all()]
    return f'Total DB: {total} <br> 5 NPK terakhir: {npk_list}'
    
@app.route('/export_hrd')
@login_required
def export_hrd():
    if current_user.role!= 'HRD':
        return redirect('/')

    penilaian = Penilaian.query.filter_by(status='final').all()
    df = pd.DataFrame([{
        'id': p.id, 'npk': p.npk, 'penilai_npk': p.penilai_npk, 'tahun': p.tahun,
        'status': p.status, 'tanggal_update': p.tanggal_update,
        'kehadiran': p.kehadiran, 'kepatuhan_aturan': p.kepatuhan_aturan, 'konsistensi': p.konsistensi,
        'kepatuhan_seragam': p.kepatuhan_seragam, 'disiplin_kebersihan': p.disiplin_kebersihan,
        'efisiensi': p.efisiensi, 'prioritas': p.prioritas, 'inovasi': p.inovasi,
        'multitasking': p.multitasking, 'peningkatan_kinerja': p.peningkatan_kinerja,
        'terampil': p.terampil, 'keputusan': p.keputusan, 'inisiatif': p.inisiatif,
        'penyelesaian_masalah': p.penyelesaian_masalah, 'responsif': p.responsif,
        'menanggapi_positif': p.menanggapi_positif, 'koordinasi': p.koordinasi,
        'sikap_positif': p.sikap_positif, 'tidak_komplain': p.tidak_komplain, 'profesional': p.profesional,
        'tanggung_jawab_kerja': p.tanggung_jawab_kerja, 'menerima_kesalahan': p.menerima_kesalahan,
        'inventaris': p.inventaris, 'tanpa_pengawasan': p.tanpa_pengawasan, 'mengelola_prioritas': p.mengelola_prioritas,
        'belajar_cepat': p.belajar_cepat, 'strategi_kerja': p.strategi_kerja, 'tantangan_baru': p.tantangan_baru,
        'ubah_cara_kerja': p.ubah_cara_kerja, 'solusi_alternatif': p.solusi_alternatif,
        'keramahan': p.keramahan, 'kejelasan': p.kejelasan, 'responsif_kom': p.responsif_kom,
        'lapor_pelanggaran': p.lapor_pelanggaran, 'keterbukaan': p.keterbukaan
    } for p in penilaian])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rekap Final')
    output.seek(0)

    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='rekap_final_sjam.xlsx')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect('/login')

from werkzeug.security import generate_password_hash

with app.app_context():
    # db.drop_all()  # HAPUS BARIS INI AJA
    # print("Semua tabel di-drop")

    db.create_all()
    print("Tabel dicek/dibikin kalo belum ada")

    # Bikin user default kalo belum ada
    if not Karyawan.query.filter_by(npk=123).first():
        admin = Karyawan(npk=123, nama='Admin', password=generate_password_hash('123456'), role='HRD', divisi='HRD', cabang='PUSAT/MD')
        db.session.add(admin)
    
    if not Karyawan.query.filter_by(npk=2018032349).first():
        wendy = Karyawan(npk=2018032349, nama='Wendy Wangsaharja', password=generate_password_hash('123456'), role='HRD', divisi='HRD', cabang='PUSAT/MD')
        db.session.add(wendy)
    
    db.session.commit()
    print("User default dicek/dibikin")

if __name__ == '__main__':
    app.run()
