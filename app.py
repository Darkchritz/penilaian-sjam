import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import io
import pandas as pd
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy import cast, String
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import login_required, current_user

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sjam-penilaian-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from datetime import timedelta
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=0) # matiin auto-login
app.config['SESSION_PERMANENT'] = False

def hitung_grade(nilai):
    if nilai <= 20: return 'E'
    elif nilai <= 30: return 'E+'
    elif nilai <= 40: return 'D'
    elif nilai <= 50: return 'D+'
    elif nilai <= 60: return 'C'
    elif nilai <= 70: return 'C+'
    elif nilai <= 80: return 'B'
    elif nilai <= 85: return 'B+'
    elif nilai <= 90: return 'A'
    else: return 'A+' # 91-100

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = "strong"

class Karyawan(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    npk = db.Column(db.Integer, unique=True, nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    divisi = db.Column(db.String(50), nullable=False)
    cabang = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return str(self.id)

class Penilaian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    penilai_npk = db.Column(db.Integer, db.ForeignKey('karyawan.npk'), nullable=False) # ganti dari String(20)
    npk = db.Column(db.Integer, db.ForeignKey('karyawan.npk'), nullable=False) # ganti dari String(20)
    periode = db.Column(db.String(2), nullable=False) # Q1, Q2, Q3, Q4
    tahun = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), default='draft') # draft / final

    # 35 KPI sesuai Excel - semua skala 0-5
    kehadiran = db.Column(db.Integer, default=0) # KEDISIPLINAN - kpi1
    kepatuhan_aturan = db.Column(db.Integer, default=0) # kpi2
    konsistensi = db.Column(db.Integer, default=0) # kpi3
    kepatuhan_seragam = db.Column(db.Integer, default=0) # kpi4
    disiplin_kebersihan = db.Column(db.Integer, default=0)# kpi5

    efisiensi = db.Column(db.Integer, default=0) # PRODUKTIVITAS - kpi6
    prioritas = db.Column(db.Integer, default=0) # kpi7
    inovasi = db.Column(db.Integer, default=0) # kpi8
    multitasking = db.Column(db.Integer, default=0) # kpi9
    peningkatan_kinerja = db.Column(db.Integer, default=0)# kpi10

    terampil = db.Column(db.Integer, default=0) # KEHANDALAN - kpi11
    keputusan = db.Column(db.Integer, default=0) # kpi12
    inisiatif = db.Column(db.Integer, default=0) # kpi13
    penyelesaian_masalah = db.Column(db.Integer, default=0)# kpi14
    responsif = db.Column(db.Integer, default=0) # kpi15

    menanggapi_positif = db.Column(db.Integer, default=0) # KERJASAMA - kpi16
    koordinasi = db.Column(db.Integer, default=0) # kpi17
    sikap_positif = db.Column(db.Integer, default=0) # kpi18
    tidak_komplain = db.Column(db.Integer, default=0) # kpi19
    profesional = db.Column(db.Integer, default=0) # kpi20

    tanggung_jawab_kerja = db.Column(db.Integer, default=0)# TANGGUNG JAWAB - kpi21
    menerima_kesalahan = db.Column(db.Integer, default=0) # kpi22
    inventaris = db.Column(db.Integer, default=0) # kpi23
    tanpa_pengawasan = db.Column(db.Integer, default=0) # kpi24
    mengelola_prioritas = db.Column(db.Integer, default=0)# kpi25

    belajar_cepat = db.Column(db.Integer, default=0) # ADAPTASI - kpi26
    strategi_kerja = db.Column(db.Integer, default=0) # kpi27
    tantangan_baru = db.Column(db.Integer, default=0) # kpi28
    ubah_cara_kerja = db.Column(db.Integer, default=0) # kpi29
    solusi_alternatif = db.Column(db.Integer, default=0) # kpi30

    keramahan = db.Column(db.Integer, default=0) # KOMUNIKASI - kpi31
    kejelasan = db.Column(db.Integer, default=0) # kpi32
    responsif_kom = db.Column(db.Integer, default=0) # kpi33
    lapor_pelanggaran = db.Column(db.Integer, default=0) # kpi34
    keterbukaan = db.Column(db.Integer, default=0) # kpi35

    nilai_akhir = db.Column(db.Float, default=0) # 0-100
    grade = db.Column(db.String(2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    karyawan = db.relationship('Karyawan', foreign_keys=[npk], backref='penilaian_diterima')
    penilai = db.relationship('Karyawan', foreign_keys=[penilai_npk], backref='penilaian_diberikan')

class AksesPenilaian(db.Model):
    __tablename__ = 'akses_penilaian'
    id = db.Column(db.Integer, primary_key=True)
    id_kadiv = db.Column(db.Integer, db.ForeignKey('karyawan.id'), nullable=False)
    divisi_target = db.Column(db.String(50), nullable=False)
    cabang_target = db.Column(db.String(50), nullable=False)
    id_karyawan_target = db.Column(db.Integer, db.ForeignKey('karyawan.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('karyawan.id'), nullable=False)
    tanggal_assign = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    kadiv = db.relationship('Karyawan', foreign_keys=[id_kadiv], backref='akses_diberikan')
    admin_hrd = db.relationship('Karyawan', foreign_keys=[assigned_by])
    karyawan_target = db.relationship('Karyawan', foreign_keys=[id_karyawan_target])

    # TAMBAH id_karyawan_target KE CONSTRAINT
    __table_args__ = (db.UniqueConstraint('id_kadiv', 'divisi_target', 'cabang_target', 'id_karyawan_target', name='uq_kadiv_divisi_cabang_karyawan'),)

@login_manager.user_loader
def load_user(user_id):
    try:
        return Karyawan.query.get(int(user_id))
    except (ValueError, TypeError):
        return None

@app.route('/')
@login_required
def index():
    db.session.refresh(current_user)
    role = current_user.role.lower().strip()
    if role == 'hrd':
        return redirect(url_for('hrd'))
    elif role in ['kepala divisi', 'kadiv']:
        return redirect(url_for('kadiv'))
    elif role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('dashboard_karyawan'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            npk_input = request.form['npk']
            password_input = request.form['password']
            remember = True if request.form.get('remember') else False # tambah ini

            print(f"DEBUG NPK DARI FORM: '{npk_input}'") # cek ada spasi ga

            user = Karyawan.query.filter_by(npk=npk_input.strip()).first()

            print(f"DEBUG USER KETEMU: {user}") # kalau None berarti query gagal

            if user:
                print(f"DEBUG HASH DI DB: {user.password}")
                cek = check_password_hash(user.password, password_input)
                print(f"DEBUG HASIL CHECK_PASSWORD: {cek}")

                if cek:
                    login_user(user, remember=remember) # tambah remember=remember
                    return redirect(url_for('index'))

            flash('NPK atau Password salah', 'danger')
        except Exception as e:
            print(f"ERROR LOGIN: {e}")
            flash('Terjadi error di server', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        try:
            npk = int(request.form['npk'])
            nama = request.form['nama']
            password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
            role = request.form['role'].lower()
            divisi = request.form['divisi']
            cabang = request.form['cabang']

            user_baru = Karyawan(npk=npk, nama=nama, password=password, role=role, divisi=divisi, cabang=cabang)
            db.session.add(user_baru)
            db.session.commit()
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect('/login')
        except IntegrityError:
            db.session.rollback()
            flash('NPK sudah terdaftar!', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    return render_template('register.html')

@app.route('/hrd')
@login_required
def hrd():
    if current_user.role.lower()!= 'hrd':
        return redirect(url_for('index'))

    user = current_user
    page = int(request.args.get('page', 1))
    per_page = 20
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'npk')
    order = request.args.get('order', 'asc')
    
    # Tambahin ini: tahun aktif penilaian
    tahun_aktif = 2026  # Ganti sesuai tahun yang lagi dipake. Nanti bisa dibikin dinamis dari DB

    query_karyawan = Karyawan.query.filter(Karyawan.npk!= user.npk)

    if search:
        query_karyawan = query_karyawan.filter(
            db.or_(
                Karyawan.nama.ilike(f'%{search}%'),
                Karyawan.npk.cast(db.String).ilike(f'%{search}%')
            )
        )

    kolom_valid = {
        'npk': Karyawan.npk,
        'nama': Karyawan.nama,
        'divisi': Karyawan.divisi,
        'cabang': Karyawan.cabang
    }
    kolom_sort = kolom_valid.get(sort_by, Karyawan.npk)

    if order == 'desc':
        query_karyawan = query_karyawan.order_by(kolom_sort.desc())
    else:
        query_karyawan = query_karyawan.order_by(kolom_sort.asc())

    pagination = query_karyawan.paginate(page=page, per_page=per_page, error_out=False)
    semua_karyawan = pagination.items
    total_pages = pagination.pages
    total_karyawan = pagination.total

    return render_template('dashboard_hrd.html',
                         user=user,
                         karyawan=semua_karyawan,
                         page=page,
                         total_pages=total_pages,
                         total_karyawan=total_karyawan,
                         search=search,
                         sort_by=sort_by,
                         order=order,
                         tahun_aktif=tahun_aktif)  # <-- Tambahin ini

@app.route('/admin/reset_penilaian/<npk>/<periode>/<int:tahun>', methods=['POST'])
@login_required
def admin_reset_penilaian(npk, periode, tahun):
    if current_user.role.lower() != 'hrd':
        return jsonify({'status': 'error', 'message': 'Akses ditolak'}), 403

    # Cari data penilaian final
    p = Penilaian.query.filter(
        Penilaian.npk == str(npk),                    # aman buat string/int
        Penilaian.periode.ilike(periode.strip()),     # case-insensitive Q1/q1
        Penilaian.tahun == tahun,
        Penilaian.status.ilike('final')               # status final, case-insensitive
    ).first()
    
    if not p:
        return jsonify({
            'status': 'error', 
            'message': f'Penilaian NPK {npk} periode {periode} {tahun} dengan status final tidak ditemukan'
        }), 404

    karyawan = Karyawan.query.filter_by(npk=str(npk)).first()
    nama = karyawan.nama if karyawan else npk
    
    try:
        db.session.delete(p)
        db.session.commit()
        return jsonify({
            'status': 'success', 
            'message': f'Penilaian {nama} periode {periode} {tahun} berhasil direset'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error', 
            'message': f'Gagal reset: {str(e)}'
        }), 500

@app.route('/admin/set_tahun_aktif/<int:tahun>', methods=['POST'])
@login_required
def set_tahun_aktif(tahun):
    if current_user.role.lower() != 'hrd':
        return jsonify({'status': 'error', 'message': 'Akses ditolak'}), 403
    
    config = Config.query.filter_by(key='tahun_aktif').first()
    if config:
        config.value = str(tahun)
    else:
        config = Config(key='tahun_aktif', value=str(tahun))
        db.session.add(config)
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': f'Tahun aktif diganti ke {tahun}'})
    
@app.route('/hrd/kelola_akses_kadiv', methods=['GET', 'POST'])
@login_required
def kelola_akses_kadiv():
    if current_user.role!= 'hrd':
        flash('Akses ditolak', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            id_kadiv = request.form.get('id_kadiv')
            divisi_target = request.form.get('divisi_target')
            cabang_target = request.form.get('cabang_target')
            id_karyawan_target = request.form.get('id_karyawan_target')

            if not id_kadiv:
                return jsonify({'status': 'error', 'message': 'Pilih Kadiv dulu'}), 400

            id_kadiv = int(id_kadiv)
            if id_karyawan_target == '' or id_karyawan_target is None:
                id_karyawan_target = None
            else:
                id_karyawan_target = int(id_karyawan_target)

            cek = AksesPenilaian.query.filter_by(
                id_kadiv=id_kadiv,
                divisi_target=divisi_target,
                cabang_target=cabang_target,
                id_karyawan_target=id_karyawan_target
            ).first()

            if cek:
                if not cek.is_active:
                    cek.is_active = True
                    cek.assigned_by = current_user.id
                    db.session.commit()
                    return jsonify({'status': 'success', 'message': 'Akses berhasil diaktifkan kembali'})
                else:
                    return jsonify({'status': 'error', 'message': 'Akses sudah ada'})
            else:
                akses_baru = AksesPenilaian(
                    id_kadiv=id_kadiv,
                    divisi_target=divisi_target,
                    cabang_target=cabang_target,
                    id_karyawan_target=id_karyawan_target,
                    assigned_by=current_user.id,
                    is_active=True
                )
                db.session.add(akses_baru)
                db.session.commit()
                return jsonify({'status': 'success', 'message': 'Akses berhasil ditambahkan'})

        except Exception as e:
            print(f"ERROR POST AKSES: {e}")
            db.session.rollback()
            return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

    # GET
    list_kadiv = Karyawan.query.filter_by(role='kadiv').all()

    list_divisi = db.session.query(Karyawan.divisi).distinct().all()
    list_divisi = [d[0] if d[0] else '-' for d in list_divisi]
    list_divisi = sorted(list(set(list_divisi)))

    list_cabang = db.session.query(Karyawan.cabang).distinct().all()
    list_cabang = [c[0] if c[0] else '-' for c in list_cabang]
    list_cabang = sorted(list(set(list_cabang)))

    list_karyawan = Karyawan.query.order_by(Karyawan.nama).all()

    akses_per_kadiv = {}
    for kadiv in list_kadiv:
        akses_per_kadiv[kadiv.id] = AksesPenilaian.query.filter_by(
            id_kadiv=kadiv.id,
            is_active=True
        ).all()

    return render_template('hrd_kelola_akses.html',
                           list_kadiv=list_kadiv,
                           list_divisi=list_divisi,
                           list_cabang=list_cabang,
                           list_karyawan=list_karyawan,
                           akses_per_kadiv=akses_per_kadiv)

@app.route('/api/karyawan')
@login_required
def api_karyawan():
    divisi = request.args.get('divisi')
    cabang = request.args.get('cabang')
    if current_user.role.lower()!= 'hrd':
        return jsonify([])

    karyawan = Karyawan.query.filter_by(divisi=divisi, cabang=cabang, role='karyawan').all()
    return jsonify([{'id': k.id, 'nama': k.nama, 'npk': k.npk} for k in karyawan])

@app.route('/hrd/tambah_akses_kadiv', methods=['POST'])
@login_required
def tambah_akses_kadiv():
    if current_user.role.lower()!= 'hrd':
        return jsonify({'status': 'error', 'message': 'Akses ditolak'}), 403

    id_kadiv = request.form.get('id_kadiv')
    divisi_target = request.form.get('divisi_target')
    cabang_target = request.form.get('cabang_target')
    id_karyawan = request.form.get('id_karyawan_target')

    existing = AksesPenilaian.query.filter_by(
        id_kadiv=id_kadiv,
        divisi_target=divisi_target,
        cabang_target=cabang_target,
        id_karyawan_target=id_karyawan_target,
        is_active=True
    ).first()

    if existing:
        return jsonify({'status': 'error', 'message': 'Akses sudah ada'}), 400

    akses_baru = AksesPenilaian(
        id_kadiv=id_kadiv,
        divisi_target=divisi_target,
        cabang_target=cabang_target,
        id_karyawan_target=id_karyawan_target,
        assigned_by=current_user.id
    )
    db.session.add(akses_baru)
    db.session.commit()

    return jsonify({'status': 'success', 'message': 'Akses berhasil ditambahkan'})

@app.route('/hrd/hapus_akses_kadiv', methods=['POST'])
@login_required
def hapus_akses_kadiv():
    if current_user.role.lower()!= 'hrd':
        return jsonify({'status': 'error', 'message': 'Akses ditolak'}), 403

    id_kadiv = request.form.get('id_kadiv')
    divisi_target = request.form.get('divisi_target')
    cabang_target = request.form.get('cabang_target')

    akses = AksesPenilaian.query.filter_by(
        id_kadiv=id_kadiv,
        divisi_target=divisi_target,
        cabang_target=cabang_target,
        is_active=True
    ).first()

    if akses:
        akses.is_active = False
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Akses berhasil dihapus'})

    return jsonify({'status': 'error', 'message': 'Akses tidak ditemukan'}), 404

@app.route('/kadiv')
@login_required
def kadiv():
    if current_user.role.lower().strip() not in ['kadiv', 'kepala divisi', 'super kadiv']:
        return redirect(url_for('index'))

    tahun_ini = datetime.now().year
    periode = request.args.get('periode', 'Q1')
    page_belum = request.args.get('page_belum', 1, type=int)
    page_sudah = request.args.get('page_sudah', 1, type=int)
    per_page = 8 # 8 orang per halaman

    print(f"=== DEBUG KADIV ===")
    print(f"Login sebagai: {current_user.nama} | NPK: {current_user.npk} | Role: {current_user.role} | Divisi: {current_user.divisi} | Cabang: {current_user.cabang} | Periode: {periode}")

    if current_user.role.lower().strip() == 'super kadiv':
        base_query = Karyawan.query.filter(Karyawan.role == 'karyawan')
        print(f"Super Kadiv: Total karyawan = {base_query.count()}")
    else:
        # Cek apakah Kadiv HO/PUSAT
        list_pusat = ['HO', 'PUSAT MD', 'SJAM HO', 'PUSAT / MD']
        is_pusat = current_user.cabang.strip().upper() in list_pusat
        print(f"Is Pusat/HO: {is_pusat}")

        if is_pusat:
            # Kadiv HO: tetap 1 divisi doang, tapi semua cabang HO
            base_query = Karyawan.query.filter(
                Karyawan.divisi == current_user.divisi,
                Karyawan.cabang.in_(list_pusat),
                Karyawan.npk!= current_user.npk # ganti dari id
            )
            print(f"Kadiv HO: Total bawahan 1 divisi = {base_query.count()}")
        else:
            # KADIV CABANG: HAPUS FILTER DIVISI, KUNCI CABANG AJA
            base_query = Karyawan.query.filter(
                Karyawan.cabang == current_user.cabang,
                Karyawan.npk!= current_user.npk # ganti dari id
            )
            print(f"Kadiv Cabang: Total bawahan semua divisi = {base_query.count()} orang")

    # UBAH: id_karyawan -> npk
    subquery_final = Penilaian.query.with_entities(Penilaian.npk).filter_by(
        periode=periode,
        tahun=tahun_ini,
        status='final'
    ).distinct()

    belum_query = base_query.filter(
    Karyawan.npk.isnot(None),
    ~Karyawan.npk.in_(subquery_final)
)
    sudah_query = base_query.filter(
    Karyawan.npk.isnot(None),
    Karyawan.npk.in_(subquery_final)
)

    belum_paginate = belum_query.paginate(page=page_belum, per_page=per_page, error_out=False)
    sudah_paginate = sudah_query.paginate(page=page_sudah, per_page=per_page, error_out=False)

    # UBAH: id_karyawan -> npk, id_penilai -> penilai_npk
    for k in sudah_paginate.items:
        nilai = Penilaian.query.filter_by(
            npk=k.npk, # ganti dari id_karyawan=k.id
            periode=periode,
            tahun=tahun_ini,
            status='final'
        ).first()
        k.nilai_akhir = nilai.nilai_akhir if nilai else 0
        k.grade = nilai.grade if nilai else '-'
        k.penilaian_id = nilai.id if nilai else None
        k.penilaian_status = nilai.status if nilai else None
        # FIX: ganti id_penilai -> penilai_npk
        penilai = Karyawan.query.filter_by(npk=nilai.penilai_npk).first() if nilai else None # ganti dari get(nilai.id_penilai)
        k.dinilai_oleh = penilai.nama if penilai else '-'

    print(f"Total belum_dinilai: {belum_paginate.total} | sudah_dinilai: {sudah_paginate.total}")
    print("=== END DEBUG ===")

    return render_template('dashboard_kadiv.html',
                           user=current_user,
                           belum_paginate=belum_paginate,
                           sudah_paginate=sudah_paginate,
                           periode=periode,
                           tahun=tahun_ini)

@app.route('/nilai/<npk>')
@login_required
def nilai_form(npk): # ganti nama fungsi dari 'nilai' jadi 'nilai_form'
    karyawan = Karyawan.query.filter_by(npk=npk).first_or_404()
    tahun = request.args.get('tahun', datetime.now().year, type=int)
    periode = request.args.get('periode', 'Q1')

    nilai = Penilaian.query.filter_by(npk=npk, tahun=tahun, periode=periode).first()

    return render_template('nilai_form.html',
                           karyawan=karyawan,
                           tahun=tahun,
                           periode=periode,
                           nilai=nilai)

@app.route('/lihat_penilaian/<int:id>')
@login_required
def lihat_penilaian(id):
    p = Penilaian.query.get_or_404(id)
    if p.penilai_npk!= current_user.npk and current_user.role.lower()!= 'hrd':
        return "Akses ditolak", 403
    k = Karyawan.query.filter_by(npk=p.npk).first()
    return render_template('nilai_form.html',
                         nilai=p,
                         karyawan=k,
                         readonly=True,
                         periode=p.periode,
                         tahun=p.tahun)

@app.route('/dashboard_karyawan')
@login_required
def dashboard_karyawan():
    if current_user.role.lower()!= 'karyawan':
        return redirect(url_for('index'))

    user = current_user
    tahun_ini = datetime.now().year

    # Ambil semua penilaian Q1-Q4 tahun ini
    hasil_q1 = Penilaian.query.filter_by(npk=user.npk, status='final', tahun=tahun_ini, periode='Q1').first()
    hasil_q2 = Penilaian.query.filter_by(npk=user.npk, status='final', tahun=tahun_ini, periode='Q2').first()
    hasil_q3 = Penilaian.query.filter_by(npk=user.npk, status='final', tahun=tahun_ini, periode='Q3').first()
    hasil_q4 = Penilaian.query.filter_by(npk=user.npk, status='final', tahun=tahun_ini, periode='Q4').first()

    # Hitung total grade tahunan
    hasil_list = [h for h in [hasil_q1, hasil_q2, hasil_q3, hasil_q4] if h]
    if hasil_list:
        total_nilai = sum([h.nilai_akhir for h in hasil_list])
        nilai_total = round(total_nilai / len(hasil_list), 2)
        grade_total = hitung_grade(nilai_total)
    else:
        nilai_total = None
        grade_total = None

    return render_template('dashboard_karyawan.html',
                         user=user,
                         hasil_q1=hasil_q1,
                         hasil_q2=hasil_q2,
                         hasil_q3=hasil_q3,
                         hasil_q4=hasil_q4,
                         hasil_list=hasil_list, # <-- TAMBAH INI
                         nilai_total=nilai_total,
                         grade_total=grade_total,
                         tahun=tahun_ini)

@app.route('/nilai/<int:id>', methods=['GET', 'POST'])
@login_required
def nilai(id):
    if current_user.role.lower() not in ['kadiv', 'kepala divisi', 'hrd', 'super kadiv']:
        flash('Akses ditolak', 'danger')
        return redirect(url_for('index'))

    karyawan = Karyawan.query.get_or_404(id)

    # Default: boleh liat semua. Cek akses cuma buat POST
    boleh_nilai = True
    if current_user.role.lower().strip() in ['kadiv', 'kepala divisi']:
        list_pusat = ['HO', 'PUSAT MD', 'SJAM HO', 'PUSAT / MD']
        is_pusat = current_user.cabang.strip().upper() in list_pusat

        # Kadiv ga bisa nilai diri sendiri
        if current_user.id == karyawan.id:
            boleh_nilai = False
        else:
            if is_pusat:
                # Kadiv HO: harus 1 divisi + karyawan di HO
                boleh_nilai = current_user.divisi == karyawan.divisi and karyawan.cabang.strip().upper() in list_pusat
            else:
                # KADIV CABANG: CUKUP 1 CABANG AJA
                boleh_nilai = current_user.cabang == karyawan.cabang

        # BLOK CUMA PAS SIMPAN/POST. GET BOLEH BUKA SEMUA
        if request.method == 'POST' and not boleh_nilai:
            flash(f'Anda tidak memiliki akses untuk menilai {karyawan.nama}', 'danger')
            return redirect(url_for('kadiv'))

    periode = request.args.get('periode', request.form.get('periode', 'Q1'))
    tahun = int(request.args.get('tahun', request.form.get('tahun', datetime.now().year)))

    nilai = Penilaian.query.filter_by(
        npk=karyawan.npk,
        periode=periode,
        tahun=tahun
    ).first()

    if request.method == 'POST':
        if nilai and nilai.status == 'final':
            flash('Penilaian sudah final, tidak bisa diubah', 'error')
            return redirect(url_for('nilai', id=id, periode=periode, tahun=tahun))

        if not nilai:
            nilai = Penilaian(
                npk=karyawan.npk,
                penilai_npk=current_user.npk,
                periode=periode,
                tahun=tahun
            )
            db.session.add(nilai)

        # Kadiv skip kpi1 & kpi2 biar ga nimpa data HRD
        for i in range(1, 36):
            key = f'kpi{i}'
            if current_user.role.lower() in ['kadiv', 'kepala divisi'] and key in ['kpi1', 'kpi2']:
                continue
            setattr(nilai, key, int(request.form.get(key, 0)))

        total = 0
        bobot_map = {
            **{f'kpi{i}': 4.00 for i in range(1, 6)},
            **{f'kpi{i}': 4.00 for i in range(6, 11)},
            **{f'kpi{i}': 3.00 for i in range(11, 16)},
            **{f'kpi{i}': 2.00 for i in range(16, 21)},
            **{f'kpi{i}': 3.00 for i in range(21, 26)},
            **{f'kpi{i}': 2.00 for i in range(26, 31)},
            **{f'kpi{i}': 2.00 for i in range(31, 36)},
        }
        for kpi, bobot in bobot_map.items():
            nilai_kpi = getattr(nilai, kpi, 0) or 0
            total += (nilai_kpi / 5) * bobot
        nilai.nilai_akhir = round(total, 2)
        nilai.grade = hitung_grade(nilai.nilai_akhir)
        nilai.updated_at = datetime.utcnow()
        nilai.penilai_npk = current_user.npk

        if request.form.get('action') == 'final':
            nilai.status = 'final'
            flash(f'Penilaian {karyawan.nama} difinalisasi. Nilai: {nilai.nilai_akhir} - Grade {nilai.grade}', 'success')
        else:
            nilai.status = 'draft'
            flash(f'Draft penilaian {karyawan.nama} disimpan', 'success')

        db.session.commit()

        if current_user.role.lower() == 'hrd':
            return redirect(url_for('hrd'))
        else:
            return redirect(url_for('kadiv'))

    return render_template('nilai_form.html',
                         karyawan=karyawan,
                         nilai=nilai,
                         periode=periode,
                         tahun=tahun,
                         boleh_nilai=boleh_nilai)

@app.route('/submit_nilai', methods=['POST'])
@login_required
def submit_nilai():
    npk_karyawan = request.form.get('npk') # ganti dari request.form['npk']
    periode = request.form.get('periode')
    tahun = int(request.form.get('tahun', 0))
    action = request.form.get('action', 'draft')

    if not npk_karyawan: # tambah ini biar ketauan kalo npk kosong
        flash('NPK tidak ditemukan', 'danger')
        return redirect(url_for('kadiv'))

    p = Penilaian.query.filter_by(npk=npk_karyawan, periode=periode, tahun=tahun).first()
    if not p:
        p = Penilaian(
            npk=npk_karyawan,
            penilai_npk=current_user.npk,
            periode=periode,
            tahun=tahun,
            status='draft'
        )
        db.session.add(p)

    # UPDATE KPI: Kadiv cuma bisa ubah KPI3-35. KPI1&KPI2 skip kalo role kadiv
    kpi_keys = [
        'kehadiran', 'kepatuhan_aturan', 'konsistensi', 'kepatuhan_seragam', 'disiplin_kebersihan',
        'efisiensi', 'prioritas', 'inovasi', 'multitasking', 'peningkatan_kinerja',
        'terampil', 'keputusan', 'inisiatif', 'penyelesaian_masalah', 'responsif',
        'menanggapi_positif', 'koordinasi', 'sikap_positif', 'tidak_komplain', 'profesional',
        'tanggung_jawab_kerja', 'menerima_kesalahan', 'inventaris', 'tanpa_pengawasan', 'mengelola_prioritas',
        'belajar_cepat', 'strategi_kerja', 'tantangan_baru', 'ubah_cara_kerja', 'solusi_alternatif',
        'keramahan', 'kejelasan', 'responsif_kom', 'lapor_pelanggaran', 'keterbukaan'
    ]

    for key in kpi_keys:
        # Kalo Kadiv, skip kehadiran & kepatuhan_aturan biar ga nimpa data HRD
        if current_user.role.lower() in ['kadiv', 'kepala divisi'] and key in ['kehadiran', 'kepatuhan_aturan']:
            continue
        val = request.form.get(key)
        setattr(p, key, int(val) if val not in [None, ''] else None)

    # HITUNG NILAI & GRADE SELALU, DRAFT ATAU FINAL
    total = 0
    bobot_map = {
        'kehadiran': 4.00, 'kepatuhan_aturan': 4.00, 'konsistensi': 4.00, 'kepatuhan_seragam': 4.00, 'disiplin_kebersihan': 4.00,
        'efisiensi': 4.00, 'prioritas': 4.00, 'inovasi': 4.00, 'multitasking': 4.00, 'peningkatan_kinerja': 4.00,
        'terampil': 3.00, 'keputusan': 3.00, 'inisiatif': 3.00, 'penyelesaian_masalah': 3.00, 'responsif': 3.00,
        'menanggapi_positif': 2.00, 'koordinasi': 2.00, 'sikap_positif': 2.00, 'tidak_komplain': 2.00, 'profesional': 2.00,
        'tanggung_jawab_kerja': 3.00, 'menerima_kesalahan': 3.00, 'inventaris': 3.00, 'tanpa_pengawasan': 3.00, 'mengelola_prioritas': 3.00,
        'belajar_cepat': 2.00, 'strategi_kerja': 2.00, 'tantangan_baru': 2.00, 'ubah_cara_kerja': 2.00, 'solusi_alternatif': 2.00,
        'keramahan': 2.00, 'kejelasan': 2.00, 'responsif_kom': 2.00, 'lapor_pelanggaran': 2.00, 'keterbukaan': 2.00,
    }
    for kpi, bobot in bobot_map.items():
        nilai_kpi = getattr(p, kpi, 0) or 0
        total += (nilai_kpi / 5) * bobot
    p.nilai_akhir = round(total, 2)
    p.grade = hitung_grade(p.nilai_akhir)

    # Set status + penilai_npk terakhir yang edit
    p.status = action
    p.penilai_npk = current_user.npk
    p.updated_at = datetime.utcnow()

    db.session.commit()
    flash(f'Penilaian {periode} berhasil disimpan!', 'success')

    if current_user.role.lower() == 'hrd':
        return redirect(url_for('hrd'))
    return redirect(url_for('kadiv'))

@app.route('/hrd/input_disiplin', methods=['GET', 'POST'])
@login_required
def input_disiplin():
    if current_user.role.lower()!= 'hrd':
        return redirect(url_for('kadiv'))

    periode = request.args.get('periode', 'Q1')
    tahun = request.args.get('tahun', datetime.now().year, type=int)
    search = request.args.get('search', '').strip()

    if request.method == 'POST':
        # HANDLE UPLOAD EXCEL
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                flash('File belum dipilih', 'danger')
                return redirect(url_for('input_disiplin', periode=periode, tahun=tahun))

            try:
                df = pd.read_excel(file)
                # Validasi kolom wajib: NPK, KPI1, KPI2
                if not all(col in df.columns for col in ['NPK', 'KPI1', 'KPI2']):
                    flash('Format Excel salah. Wajib ada kolom: NPK, KPI1, KPI2', 'danger')
                    return redirect(url_for('input_disiplin', periode=periode, tahun=tahun))

                sukses = 0
                gagal = 0
                for _, row in df.iterrows():
                    try:
                        npk = str(row['NPK']).strip()
                        kpi1 = int(row['KPI1'])
                        kpi2 = int(row['KPI2'])

                        if not (0 <= kpi1 <= 5 and 0 <= kpi2 <= 5):
                            gagal += 1
                            continue

                        karyawan = Karyawan.query.filter_by(npk=npk).first()
                        if not karyawan:
                            gagal += 1
                            continue

                        p = Penilaian.query.filter_by(npk=karyawan.npk, periode=periode, tahun=tahun).first()
                        if not p:
                            p = Penilaian(
                                npk=karyawan.npk,
                                penilai_npk=current_user.npk,
                                periode=periode,
                                tahun=tahun,
                                status='draft'
                            )
                            db.session.add(p)

                        p.kpi1 = kpi1
                        p.kpi2 = kpi2

                        # Hitung ulang grade
                        total = 0
                        bobot_map = {
                            **{f'kpi{i}': 4.00 for i in range(1, 6)},
                            **{f'kpi{i}': 4.00 for i in range(6, 11)},
                            **{f'kpi{i}': 3.00 for i in range(11, 16)},
                            **{f'kpi{i}': 2.00 for i in range(16, 21)},
                            **{f'kpi{i}': 3.00 for i in range(21, 26)},
                            **{f'kpi{i}': 2.00 for i in range(26, 31)},
                            **{f'kpi{i}': 2.00 for i in range(31, 36)},
                        }
                        for kpi, bobot in bobot_map.items():
                            nilai_kpi = getattr(p, kpi, 0) or 0
                            total += (nilai_kpi / 5) * bobot
                        p.nilai_akhir = round(total, 2)
                        p.grade = hitung_grade(p.nilai_akhir)
                        p.penilai_npk = current_user.npk
                        p.updated_at = datetime.utcnow()
                        sukses += 1
                    except:
                        gagal += 1
                        continue

                db.session.commit()
                flash(f'Upload selesai. Sukses: {sukses}, Gagal: {gagal}', 'success' if gagal == 0 else 'warning')
                return redirect(url_for('input_disiplin', periode=periode, tahun=tahun))
            except Exception as e:
                flash(f'Gagal baca Excel: {str(e)}', 'danger')
                return redirect(url_for('input_disiplin', periode=periode, tahun=tahun))

        # HANDLE INPUT MANUAL
        else:
            periode = request.form['periode']
            tahun = int(request.form['tahun'])

            for key, value in request.form.items():
                if key.startswith('kpi1_') or key.startswith('kpi2_'):
                    _, npk_karyawan = key.split('_')
                    npk_karyawan = int(npk_karyawan)

                    p = Penilaian.query.filter_by(npk=npk_karyawan, periode=periode, tahun=tahun).first()
                    if not p:
                        karyawan = Karyawan.query.filter_by(npk=npk_karyawan).first()
                        if not karyawan: continue
                        p = Penilaian(
                            npk=npk_karyawan,
                            penilai_npk=current_user.npk,
                            periode=periode,
                            tahun=tahun,
                            status='draft'
                        )
                        db.session.add(p)

                    if key.startswith('kpi1_'):
                        p.kpi1 = int(value or 0)
                    else:
                        p.kpi2 = int(value or 0)

                    # Update grade setiap ada perubahan
                    total = 0
                    bobot_map = {
                        **{f'kpi{i}': 4.00 for i in range(1, 6)},
                        **{f'kpi{i}': 4.00 for i in range(6, 11)},
                        **{f'kpi{i}': 3.00 for i in range(11, 16)},
                        **{f'kpi{i}': 2.00 for i in range(16, 21)},
                        **{f'kpi{i}': 3.00 for i in range(21, 26)},
                        **{f'kpi{i}': 2.00 for i in range(26, 31)},
                        **{f'kpi{i}': 2.00 for i in range(31, 36)},
                    }
                    for kpi, bobot in bobot_map.items():
                        nilai_kpi = getattr(p, kpi, 0) or 0
                        total += (nilai_kpi / 5) * bobot
                    p.nilai_akhir = round(total, 2)
                    p.grade = hitung_grade(p.nilai_akhir)
                    p.penilai_npk = current_user.npk
                    p.updated_at = datetime.utcnow()

            db.session.commit()
            flash(f'Data Kedisiplinan {periode} {tahun} berhasil disimpan!', 'success')
            return redirect(url_for('input_disiplin', periode=periode, tahun=tahun, search=search))

        # GET: query karyawan + search
    search = request.args.get('search', '')
    query = Karyawan.query

    if search:
        query = query.filter(
            db.or_(
                Karyawan.nama.ilike(f'%{search}%'),
                cast(Karyawan.npk, String).ilike(f'%{search}%')
            )
        )

    karyawan_list = query.order_by(Karyawan.divisi, Karyawan.nama).all()

    nilai_map = {}
    for n in Penilaian.query.filter_by(periode=periode, tahun=tahun).all():
        nilai_map[n.npk] = n

    return render_template('hrd_input_disiplin.html',
                           karyawan_list=karyawan_list,
                           nilai_map=nilai_map,
                           periode=periode,
                           tahun=tahun,
                           search=search)

@app.route('/hrd/download_template_disiplin')
@login_required
def download_template_disiplin():
    if current_user.role.lower()!= 'hrd':
        return redirect(url_for('index'))

    # Bikin template kosong
    data = {'NPK': ['2018032349', '12345678'], 'KPI1': [5, 4], 'KPI2': [5, 4]}
    df = pd.DataFrame(data)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='template_kedisiplinan.xlsx'
    )

@app.route('/tambah-karyawan', methods=['GET', 'POST'])
@login_required
def tambah_karyawan():
    if current_user.role.lower()!= 'hrd':
        flash('Akses ditolak', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            npk = int(request.form['npk'])
            nama = request.form['nama'].strip()
            role = request.form['role'].lower().strip()
            divisi = request.form['divisi'].strip()
            cabang = request.form['cabang'].strip() # WAJIB
            password = request.form.get('password', '123456').strip()

            if Karyawan.query.filter_by(npk=npk).first():
                flash(f'NPK {npk} sudah terdaftar', 'danger')
                return redirect(url_for('tambah_karyawan')) # FIX 2: ke dirinya sendiri

            karyawan = Karyawan(
                npk=npk,
                nama=nama,
                password=generate_password_hash(password, method='pbkdf2:sha256'),
                role=role,
                divisi=divisi,
                cabang=cabang
            )
            db.session.add(karyawan)
            db.session.commit()
            flash('Karyawan berhasil ditambah', 'success')
            return redirect(url_for('hrd')) # FIX 3: ke hrd, bukan daftar_karyawan

        except IntegrityError:
            db.session.rollback()
            flash('Gagal: NPK sudah ada atau ada data kosong', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('tambah_karyawan.html')

@app.route('/hrd/edit_karyawan/<int:npk>', methods=['POST'])
@login_required
def edit_karyawan(npk):
    if current_user.role.lower()!= 'hrd':
        return redirect('/')

    karyawan = Karyawan.query.filter_by(npk=npk).first()
    if not karyawan:
        flash('Karyawan tidak ditemukan', 'error')
        return redirect(url_for('hrd'))

    karyawan.nama = request.form['nama']
    karyawan.role = request.form['role'].lower()
    karyawan.divisi = request.form['divisi']
    karyawan.cabang = request.form['cabang']

    password = request.form.get('password', '').strip()
    if password:
        karyawan.password = generate_password_hash(password, method='pbkdf2:sha256')

    db.session.commit()
    flash('Data karyawan diupdate!', 'success')
    return redirect(url_for('hrd'))

@app.route('/hrd/hapus_karyawan/<int:npk>', methods=['POST'])
@login_required
def hapus_karyawan(npk):
    if current_user.role.lower()!= 'hrd':
        return redirect('/')

    karyawan = Karyawan.query.filter_by(npk=npk).first()
    if karyawan:
        Penilaian.query.filter_by(npk=karyawan.npk).delete()
        db.session.delete(karyawan)
        db.session.commit()
        flash('Karyawan & data penilaian dihapus!', 'success')
    return redirect(url_for('hrd'))

@app.route('/hrd/download_karyawan')
@login_required
def download_karyawan():
    if current_user.role.lower()!= 'hrd':
        flash('Akses ditolak', 'danger')
        return redirect('/')

    karyawan = Karyawan.query.filter(Karyawan.role.in_(['karyawan','kadiv'])).all()

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
    if current_user.role.lower()!= 'hrd':
        return redirect('/')

    file = request.files['file']
    if file.filename == '':
        flash('Pilih file dulu', 'error')
        return redirect(url_for('hrd'))

    try:
        df = pd.read_excel(file)
        required_cols = ['npk', 'nama', 'role', 'divisi', 'cabang']
        for col in required_cols:
            if col not in df.columns:
                flash(f'Kolom {col} tidak ditemukan. Header harus: npk, nama, password, role, divisi, cabang', 'error')
                return redirect(url_for('hrd'))

        df = df.fillna('')
        df['npk'] = df['npk'].apply(lambda x: int(float(x)) if str(x).strip()!= '' else '')
        df['nama'] = df['nama'].astype(str).str.strip()
        df['role'] = df['role'].astype(str).str.strip().str.lower()
        df['divisi'] = df['divisi'].astype(str).str.strip()
        df['cabang'] = df['cabang'].astype(str).str.strip()

        df = df[(df['npk']!= '') & (df['nama']!= '') & (df['role']!= '') & (df['divisi']!= '') & (df['cabang']!= '')]

        if df.empty:
            flash('Tidak ada data valid di Excel', 'error')
            return redirect(url_for('hrd'))

        npk_list = df['npk'].tolist()
        existing_karyawan = Karyawan.query.filter(Karyawan.npk.in_(npk_list)).all()
        existing_npk_dict = {k.npk: k for k in existing_karyawan}

        data_baru = []
        data_update = 0

        with db.session.no_autoflush:
            for _, row in df.iterrows():
                npk = row['npk']
                password = str(row['password']).strip() if 'password' in df.columns and str(row['password']).strip()!= '' else '123456'

                if npk in existing_npk_dict:
                    existing = existing_npk_dict[npk]
                    existing.nama = row['nama']
                    existing.password = generate_password_hash(password, method='pbkdf2:sha256')
                    existing.role = row['role']
                    existing.divisi = row['divisi']
                    existing.cabang = row['cabang']
                    data_update += 1
                else:
                    data_baru.append(Karyawan(
                        npk=npk,
                        nama=row['nama'],
                        password=generate_password_hash(password, method='pbkdf2:sha256'),
                        role=row['role'],
                        divisi=row['divisi'],
                        cabang=row['cabang']
                    ))

        if data_baru:
            db.session.add_all(data_baru)

        db.session.commit()
        flash(f'Upload selesai! Data baru: {len(data_baru)}, Data diupdate: {data_update}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('hrd'))

@app.route('/reset-kadiv/<int:npk>')
@login_required
def reset_kadiv(npk):
    if current_user.role.lower()!= 'hrd':
        return "Akses ditolak", 403

    user = Karyawan.query.filter_by(npk=npk).first()
    if not user:
        return f"NPK {npk} ga ketemu di DB"

    user.password = generate_password_hash('123456', method='pbkdf2:sha256')
    db.session.commit()
    return f"Done. {user.nama} - {user.npk} bisa login pake 123456. Role: {user.role}"

@app.route('/nilai_saya')
@login_required
def nilai_saya():
    tahun_ini = datetime.now().year

    # Ambil semua nilai final buat user yang login
    list_nilai = Penilaian.query.filter_by(
        npk=current_user.npk,
        tahun=tahun_ini,
        status='final'
    ).order_by(Penilaian.periode.desc()).all()

    # Ambil nama penilai buat ditampilin
    for n in list_nilai:
        penilai = Karyawan.query.filter_by(npk=n.penilai_npk).first()
        n.nama_penilai = penilai.nama if penilai else 'N/A'
        n.jabatan_penilai = penilai.role if penilai else '-'

    return render_template('nilai_saya.html',
                           user=current_user,
                           list_nilai=list_nilai,
                           tahun=tahun_ini)

@app.route('/cek-penilaian/<int:npk>')
@login_required
def cek_penilaian(npk):
    p = Penilaian.query.filter_by(npk=npk, periode='Q1', tahun=2026).first()

    if not p:
        return f"Belum ada data penilaian buat npk={npk}"

    return f"""
    ID Penilaian: {p.id}<br>
    npk: {p.npk}<br>
    penilai_npk: {p.penilai_npk}<br>
    NPK Login lu sekarang: {current_user.npk}<br>
    status: {p.status}<br>
    periode: {p.periode}<br>
    tahun: {p.tahun}<br>
    nilai_akhir: {p.nilai_akhir}<br>
    <br>
    Syarat masuk 'Sudah Dinilai':<br>
    1. penilai_npk == {current_user.npk}? {p.penilai_npk == current_user.npk}<br>
    2. status == 'final'? {p.status == 'final'}<br>
    """

@app.route('/fix-id-penilai')
@login_required
def fix_id_penilai():
    p = Penilaian.query.get(2) # ID Penilaian dari debug tadi
    p.penilai_npk = current_user.npk
    db.session.commit()
    return f"Udah di-fix. penilai_npk sekarang = {p.penilai_npk}"

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect('/login')

@app.route('/export_rekap')
@login_required
def export_rekap():
    if current_user.role.lower().strip() not in ['admin', 'super kadiv', 'kadiv', 'kepala divisi', 'hrd']:
        return "Akses ditolak", 403

    tahun_ini = datetime.now().year
    periode = request.args.get('periode', 'Q1')

    # Ambil data penilaian + join karyawan yg dinilai
    data_penilaian = db.session.query(Penilaian, Karyawan)\
       .join(Karyawan, Penilaian.npk == Karyawan.npk)\
       .filter(Penilaian.status == 'final', Penilaian.tahun == tahun_ini, Penilaian.periode == periode)\
       .all()

    if not data_penilaian:
        flash(f'Data rekap {periode} kosong', 'error')
        return redirect(url_for('hrd'))

    hasil = []
    for p, k in data_penilaian: # p = Penilaian, k = Karyawan yg dinilai
        penilai = Karyawan.query.filter_by(npk=p.penilai_npk).first() if p.penilai_npk else None
        hasil.append({
            'NPK': k.npk,
            'Nama': k.nama,
            'Divisi': k.divisi,
            'Cabang': k.cabang,
            'Role': k.role,
            'Periode': p.periode,
            'Tahun': p.tahun,
            'Nilai Akhir': p.nilai_akhir,
            'Grade': p.grade,
            'Dinilai Oleh': penilai.nama if penilai else '-',
            'NPK Penilai': penilai.npk if penilai else '-' # INI YANG KEMARIN KOSONG
        })

    df = pd.DataFrame(hasil)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=f'Rekap {periode}')
    output.seek(0)

    filename = f"Rekap_Penilaian_{periode}_{tahun_ini}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

with app.app_context():
    db.create_all()
    if not Karyawan.query.filter_by(npk=123).first():
        admin = Karyawan(npk=123, nama='Admin', password=generate_password_hash('123456', method='pbkdf2:sha256'), role='hrd', divisi='HRD', cabang='PUSAT/MD')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
