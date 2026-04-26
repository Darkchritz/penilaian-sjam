from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pandas as pd
import io
import os

from models import db, Karyawan, Penilaian

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sjam-penilaian-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
migrate = Migrate(app, db)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(npk):
    return Karyawan.query.get(npk)

@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        npk = request.form['npk']
        password = request.form['password']
        user = Karyawan.query.filter_by(npk=npk).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['user'] = {
                'npk': user.npk,
                'nama': user.nama,
                'role': user.role,
                'divisi': user.divisi,
                'cabang': user.cabang
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

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    
    if user.role == 'hrd':
        page = int(request.args.get('page', 1))
        per_page = 20
        pagination = Karyawan.query.filter(Karyawan.npk!= user.npk).paginate(page=page, per_page=per_page, error_out=False)
        karyawan = pagination.items
        total_pages = pagination.pages
        
        tahun_ini = datetime.now().year
        # Ambil semua penilaian Q1 tahun ini
        penilaian_q1 = Penilaian.query.filter_by(tahun=tahun_ini, periode='Q1').all()
        penilaian_dict = {p.npk: p for p in penilaian_q1}
        
        # Cek yang belum dinilai Q1
        belum_dinilai = Karyawan.query.filter(
            Karyawan.role == 'karyawan',
            ~Karyawan.npk.in_(db.session.query(Penilaian.npk).filter_by(periode='Q1', tahun=tahun_ini))
        ).all()
        
        karyawan_untuk_dinilai = Karyawan.query.filter(
            Karyawan.divisi == user.divisi,
            Karyawan.cabang == user.cabang,
            Karyawan.role.in_(['karyawan','kadiv']),
            Karyawan.npk!= user.npk
        ).order_by(Karyawan.role.desc(), Karyawan.nama).all()
        
        return render_template('dashboard_hrd.html',
                             user=user,
                             karyawan_list=karyawan_untuk_dinilai,  # <-- samain nama biar ga error
                             belum_dinilai=belum_dinilai,
                             page=page,
                             total_pages=total_pages,
                             penilaian_dict=penilaian_dict)  # <-- kirim full objek

    # bagian elif user.role == 'kadiv' dan 'karyawan' biarin dulu, nanti kita ubah nyusul

    elif user.role == 'karyawan':
        tahun_ini = datetime.now().year
        hasil = Penilaian.query.filter_by(npk=user.npk, tahun=tahun_ini, periode='Q1').first()
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
        tahun_ini = datetime.now().year
        hasil = Penilaian.query.filter_by(npk=user.npk, status='final', tahun=tahun_ini).order_by(Penilaian.tanggal_update.desc()).first()
        return render_template('dashboard_karyawan.html', user=user, hasil=hasil)
            
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
    if current_user.role!= 'hrd':
        return redirect('/')

    karyawan = Karyawan.query.filter(Karyawan.role.in_(['karyawan','kadiv'])).all()
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
    if current_user.role!= 'hrd':
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

        existing_npk = set([k.npk for k in Karyawan.query.all()])
        data_batch = []
        skip = 0
        
        for _, row in df.iterrows():
            if row['npk'] in existing_npk:
                skip += 1
                continue

            password = str(row['password']).strip() if 'password' in df.columns and str(row['password']).strip()!= '' else '123456'
            data_batch.append(Karyawan(
                npk=row['npk'],
                nama=row['nama'],
                password=generate_password_hash(password),
                role=row['role'],
                divisi=row['divisi'],
                cabang=row['cabang']
            ))
            existing_npk.add(row['npk'])

        if data_batch:
            db.session.bulk_save_objects(data_batch)
            db.session.commit()

        flash(f'Upload selesai! Baru: {len(data_batch)}, Skip duplikat: {skip}', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect('/dashboard')

@app.route('/export_hrd')
@login_required
def export_hrd():
    if current_user.role!= 'hrd':
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
