import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
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
    id_karyawan = db.Column(db.Integer, db.ForeignKey('karyawan.id'))
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
    tanggal_update = db.Column(db.DateTime, default=datetime.utcnow)

    karyawan = db.relationship('Karyawan', backref='daftar_penilaian')

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

@app.route('/kadiv')
@login_required
def kadiv():
    if current_user.role.lower().strip() not in ['kadiv', 'kepala divisi']:
        return redirect(url_for('index'))

    karyawan_divisi = Karyawan.query.filter(
        Karyawan.divisi == current_user.divisi,
        Karyawan.npk!= current_user.npk
    ).all()

    belum_dinilai = []
    sudah_dinilai = []

    for k in karyawan_divisi:
        nilai = Penilaian.query.filter_by(
            id_karyawan=k.id,
            periode='Q1',
            tahun=2026,
            status='final'
        ).first()

        if nilai:
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
    user = current_user
    tahun_ini = datetime.now().year
    hasil = Penilaian.query.filter_by(id_karyawan=user.id, status='final', tahun=tahun_ini).order_by(Penilaian.tanggal_update.desc()).first()
    return render_template('dashboard_karyawan.html', user=user, hasil=hasil)

@app.route('/nilai/<int:id>', methods=['GET', 'POST'])
@login_required  # <-- WAJIB ADA
def nilai(id):
    if current_user.role.lower() not in ['kadiv', 'hrd']:
        flash('Akses ditolak', 'danger')
        return redirect(url_for('index'))
    
    karyawan = Karyawan.query.get_or_404(id)
    periode = request.args.get('periode', 'Q1')
    tahun_ini = datetime.now().year
    karyawan = Karyawan.query.get_or_404(id)

    penilaian = Penilaian.query.filter_by(
        id_karyawan=karyawan.id,
        tahun=tahun_ini,
        periode=periode
    ).first()

    return render_template('nilai_form.html',
                         karyawan=karyawan,
                         periode=periode,
                         penilaian=penilaian,
                         tahun_ini=tahun_ini)

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
    app.run()
