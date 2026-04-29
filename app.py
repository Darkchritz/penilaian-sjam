import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import io
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sjam-penilaian-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    else: return 'A+'  # 91-100

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
    id_karyawan = db.Column(db.Integer, db.ForeignKey('karyawan.id'), nullable=False)
    periode = db.Column(db.String(2), nullable=False)  # Q1, Q2, Q3, Q4
    tahun = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), default='draft')  # draft / final
    
    # 35 KPI sesuai Excel - semua skala 0-5
    kpi1 = db.Column(db.Integer, default=0)   # KEDISIPLINAN
    kpi2 = db.Column(db.Integer, default=0)
    kpi3 = db.Column(db.Integer, default=0)
    kpi4 = db.Column(db.Integer, default=0)
    kpi5 = db.Column(db.Integer, default=0)
    
    kpi6 = db.Column(db.Integer, default=0)   # PRODUKTIVITAS
    kpi7 = db.Column(db.Integer, default=0)
    kpi8 = db.Column(db.Integer, default=0)
    kpi9 = db.Column(db.Integer, default=0)
    kpi10 = db.Column(db.Integer, default=0)
    
    kpi11 = db.Column(db.Integer, default=0)  # KEHANDALAN
    kpi12 = db.Column(db.Integer, default=0)
    kpi13 = db.Column(db.Integer, default=0)
    kpi14 = db.Column(db.Integer, default=0)
    kpi15 = db.Column(db.Integer, default=0)
    
    kpi16 = db.Column(db.Integer, default=0)  # KERJASAMA
    kpi17 = db.Column(db.Integer, default=0)
    kpi18 = db.Column(db.Integer, default=0)
    kpi19 = db.Column(db.Integer, default=0)
    kpi20 = db.Column(db.Integer, default=0)
    
    kpi21 = db.Column(db.Integer, default=0)  # TANGGUNG JAWAB
    kpi22 = db.Column(db.Integer, default=0)
    kpi23 = db.Column(db.Integer, default=0)
    kpi24 = db.Column(db.Integer, default=0)
    kpi25 = db.Column(db.Integer, default=0)
    
    kpi26 = db.Column(db.Integer, default=0)  # ADAPTASI
    kpi27 = db.Column(db.Integer, default=0)
    kpi28 = db.Column(db.Integer, default=0)
    kpi29 = db.Column(db.Integer, default=0)
    kpi30 = db.Column(db.Integer, default=0)
    
    kpi31 = db.Column(db.Integer, default=0)  # KOMUNIKASI
    kpi32 = db.Column(db.Integer, default=0)
    kpi33 = db.Column(db.Integer, default=0)
    kpi34 = db.Column(db.Integer, default=0)
    kpi35 = db.Column(db.Integer, default=0)
    
    nilai_akhir = db.Column(db.Float, default=0)  # 0-100
    grade = db.Column(db.String(2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    __table_args__ = (db.UniqueConstraint('id_kadiv', 'divisi_target', 'cabang_target', name='uq_kadiv_divisi_cabang'),)

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
    if request.method == 'POST':
        try:
            npk_input = request.form['npk']
            password_input = request.form['password']
            user = Karyawan.query.filter_by(npk=int(npk_input)).first()

            if user and check_password_hash(user.password, password_input):
                login_user(user)
                return redirect(url_for('index'))
            else:
                flash('NPK atau Password salah', 'danger')
        except ValueError:
            flash('NPK harus angka', 'danger')
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
            password = generate_password_hash(request.form['password'])
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
    tahun_ini = datetime.now().year
    periode_aktif = request.args.get('periode', 'Q1')
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'npk')
    order = request.args.get('order', 'asc')

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

    # FIX: Hapus filter cabang + role, HRD bisa nilai semua di divisi HRD
    karyawan_hrd = Karyawan.query.filter(
        Karyawan.divisi == user.divisi,
        Karyawan.npk!= user.npk
    ).order_by(Karyawan.role.desc(), Karyawan.nama).all()

    penilaian_q1 = Penilaian.query.filter_by(tahun=tahun_ini, periode=periode_aktif).all()
    penilaian_dict = {p.id_karyawan: p for p in penilaian_q1}

    sudah_dinilai_id = [p.id_karyawan for p in penilaian_q1]
    belum_dinilai = [k for k in karyawan_hrd if k.id not in sudah_dinilai_id]

    return render_template('dashboard_hrd.html',
                         user=user,
                         karyawan=semua_karyawan,
                         karyawan_hrd=karyawan_hrd,
                         karyawan_untuk_dinilai=karyawan_hrd,
                         belum_dinilai=belum_dinilai,
                         page=page,
                         total_pages=total_pages,
                         total_karyawan=total_karyawan,
                         penilaian_dict=penilaian_dict,
                         status_penilaian={p.id_karyawan: p.status for p in penilaian_q1},
                         periode_aktif=periode_aktif,
                         tahun_ini=tahun_ini,
                         search=search,
                         sort_by=sort_by,
                         order=order)

@app.route('/hrd/kelola_akses_kadiv')
@login_required
def kelola_akses_kadiv():
    if current_user.role.lower()!= 'hrd':
        flash('Akses ditolak', 'danger')
        return redirect(url_for('index'))
    
    list_kadiv = Karyawan.query.filter(Karyawan.role.in_(['kepala divisi', 'kadiv', 'super kadiv'])).order_by(Karyawan.nama).all()
    list_divisi = db.session.query(Karyawan.divisi).distinct().all()
    list_cabang = db.session.query(Karyawan.cabang).distinct().all()
    semua_akses = AksesPenilaian.query.filter_by(is_active=True).all()
    
    akses_per_kadiv = {}
    for akses in semua_akses:
        if akses.id_kadiv not in akses_per_kadiv:
            akses_per_kadiv[akses.id_kadiv] = []
        akses_per_kadiv[akses.id_kadiv].append(f"{akses.divisi_target} - {akses.cabang_target}")
    
    return render_template('hrd_kelola_akses.html', 
                         list_kadiv=list_kadiv,
                         list_divisi=[d[0] for d in list_divisi],
                         list_cabang=[c[0] for c in list_cabang],
                         akses_per_kadiv=akses_per_kadiv)
    
@app.route('/api/karyawan')
@login_required
def api_karyawan():
    divisi = request.args.get('divisi')
    cabang = request.args.get('cabang')
    if current_user.role.lower() != 'hrd':
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
        id_karyawan_target=id_karyawan if id_karyawan else None,
        is_active=True
    ).first()
    
    if existing:
        return jsonify({'status': 'error', 'message': 'Akses sudah ada'}), 400
    
    akses_baru = AksesPenilaian(
        id_kadiv=id_kadiv,
        divisi_target=divisi_target,
        cabang_target=cabang_target,
        id_karyawan_target=id_karyawan if id_karyawan else None,
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

### EDIT - UPDATE ROUTE KADIV
@app.route('/kadiv')
@login_required
def kadiv():
    if current_user.role.lower().strip() not in ['kadiv', 'kepala divisi', 'super kadiv']:
        return redirect(url_for('index'))

    tahun_ini = datetime.now().year
    
    ### CEK AKSES DARI TABEL AKSES_PENILAIAN
    if current_user.role.lower().strip() == 'super kadiv':
        karyawan_divisi = Karyawan.query.filter(
            Karyawan.role == 'karyawan'
        ).all()
    else:
        akses = AksesPenilaian.query.filter_by(id_kadiv=current_user.id, is_active=True).all()
        if not akses:
            karyawan_divisi = []
        else:
            filter_or = []
            for a in akses:
                if a.id_karyawan_target:
                filter_or.append(Karyawan.id == a.id_karyawan_target)    
            else:
                filter_or.append(db.and_(Karyawan.divisi == a.divisi_target, Karyawan.cabang == a.cabang_target))
            
            karyawan_divisi = Karyawan.query.filter(
                Karyawan.role=='karyawan', 
                db.or_(*filter_or)
            ).all()
    ### END CEK AKSES

    belum_dinilai = []
    sudah_dinilai = []

    for k in karyawan_divisi:
        nilai = Penilaian.query.filter_by(
            id_karyawan=k.id,
            periode='Q1',
            tahun=tahun_ini
        ).first()

        k.nilai_akhir = nilai.nilai_akhir if nilai else 0
        k.grade = nilai.grade if nilai else '-'
        k.status_nilai = nilai.status if nilai else None

        if nilai and nilai.status == 'final':
            sudah_dinilai.append(k)
        else:
            belum_dinilai.append(k)

    return render_template('dashboard_kadiv.html',
                           user=current_user,
                           belum_dinilai=belum_dinilai,
                           sudah_dinilai=sudah_dinilai)

@app.route('/dashboard_karyawan')
@login_required
def dashboard_karyawan():
    if current_user.role.lower() != 'karyawan':
        return redirect(url_for('index'))
    
    user = current_user
    tahun_ini = datetime.now().year
    
    # Ambil semua penilaian Q1-Q4 tahun ini
    hasil_q1 = Penilaian.query.filter_by(id_karyawan=user.id, status='final', tahun=tahun_ini, periode='Q1').first()
    hasil_q2 = Penilaian.query.filter_by(id_karyawan=user.id, status='final', tahun=tahun_ini, periode='Q2').first()
    hasil_q3 = Penilaian.query.filter_by(id_karyawan=user.id, status='final', tahun=tahun_ini, periode='Q3').first()
    hasil_q4 = Penilaian.query.filter_by(id_karyawan=user.id, status='final', tahun=tahun_ini, periode='Q4').first()
    
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
                         hasil_list=hasil_list,  # <-- TAMBAH INI
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
    if current_user.role.lower().strip() in ['kadiv', 'kepala divisi']:
        punya_akses = AksesPenilaian.query.filter_by(
            id_kadiv=current_user.id,
            divisi_target=karyawan.divisi,
            cabang_target=karyawan.cabang,
            is_active=True
        ).first()
        
        if not punya_akses:
            flash(f'Anda tidak memiliki akses untuk menilai {karyawan.nama}', 'danger')
            return redirect(url_for('kadiv'))
    periode = request.args.get('periode', request.form.get('periode', 'Q1'))
    tahun = int(request.args.get('tahun', request.form.get('tahun', datetime.now().year)))
    
    # Ambil data penilaian existing buat periode ini
    penilaian = Penilaian.query.filter_by(
        id_karyawan=karyawan.id, 
        periode=periode, 
        tahun=tahun
    ).first()

    if request.method == 'POST':
        if penilaian and penilaian.status == 'final':
            flash('Penilaian sudah final, tidak bisa diubah', 'error')
            return redirect(url_for('nilai', id=id, periode=periode, tahun=tahun))
        
        if not penilaian:
            penilaian = Penilaian(
                id_karyawan=karyawan.id,
                periode=periode,
                tahun=tahun
            )
            db.session.add(penilaian)
        
        # Simpan semua KPI 1-35
        total_skor = 0
        for i in range(1, 36):
            val = int(request.form.get(f'kpi{i}', 0))
            setattr(penilaian, f'kpi{i}', val)
            total_skor += val
        
        # Hitung nilai akhir: total 35 KPI * 5 = 175 poin max = 100%
        penilaian.nilai_akhir = round(total_skor / 175 * 100, 2)
        penilaian.grade = hitung_grade(penilaian.nilai_akhir)
        penilaian.updated_at = datetime.utcnow()
        
        # Cek kalo ada tombol "Simpan Final" 
        if request.form.get('action') == 'final':
            penilaian.status = 'final'
            flash(f'Penilaian {karyawan.nama} difinalisasi. Nilai: {penilaian.nilai_akhir} - Grade {penilaian.grade}', 'success')
        else:
            penilaian.status = 'draft'
            flash(f'Draft penilaian {karyawan.nama} disimpan', 'success')
        
        db.session.commit()
        
        # Balik ke dashboard sesuai role
        if current_user.role.lower() == 'hrd':
            return redirect(url_for('hrd'))
        else:
            return redirect(url_for('kadiv'))

    return render_template('nilai_form.html', 
                         karyawan=karyawan, 
                         penilaian=penilaian,
                         periode=periode,
                         tahun=tahun)

@app.route('/simpan_nilai/<int:id_karyawan>/<periode>', methods=['POST'])
@login_required
def simpan_nilai(id_karyawan, periode):
    if current_user.role.lower()!= 'hrd':
        return redirect(url_for('login'))

    karyawan = Karyawan.query.get_or_404(id_karyawan)
    tahun_ini = datetime.now().year

    p = Penilaian.query.filter_by(id_karyawan=karyawan.id, tahun=tahun_ini, periode=periode).first()
    if not p:
        p = Penilaian(id_karyawan=karyawan.id, tahun=tahun_ini, periode=periode, penilai_npk=current_user.npk)

    p.tanggung_jawab = int(request.form.get('kpi1', 0))
    p.inisiatif = int(request.form.get('kpi2', 0))
    p.kerjasama = int(request.form.get('kpi3', 0))
    p.kedisiplinan = int(request.form.get('kpi4', 0))
    p.kemampuan = int(request.form.get('kpi5', 0))
    p.target = int(request.form.get('kpi6', 0))
    p.proses = int(request.form.get('kpi7', 0))
    p.inovasi = int(request.form.get('kpi8', 0))
    p.status = 'draft'
    p.tanggal_update = datetime.utcnow()

    db.session.add(p)
    db.session.commit()
    flash('Nilai berhasil disimpan', 'success')
    return redirect(url_for('hrd'))

# FIX 1: TAMBAH GET + LOGIN_REQUIRED + CABANG + PASSWORD
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
                password=generate_password_hash(password),
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
        karyawan.password = generate_password_hash(password)

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
        Penilaian.query.filter_by(id_karyawan=karyawan.id).delete()
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
                    existing.password = generate_password_hash(password)
                    existing.role = row['role']
                    existing.divisi = row['divisi']
                    existing.cabang = row['cabang']
                    data_update += 1
                else:
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

        db.session.commit()
        flash(f'Upload selesai! Data baru: {len(data_baru)}, Data diupdate: {data_update}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('hrd'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect('/login')

with app.app_context():
    db.create_all()
    if not Karyawan.query.filter_by(npk=123).first():
        admin = Karyawan(npk=123, nama='Admin', password=generate_password_hash('123456'), role='hrd', divisi='HRD', cabang='PUSAT/MD')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("DB reset done")
    app.run(debug=True)
