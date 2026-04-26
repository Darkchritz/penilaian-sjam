from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Karyawan(UserMixin, db.Model):
    __tablename__ = 'karyawan'
    
    npk = db.Column(db.String(20), primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # hrd, kadiv, karyawan
    divisi = db.Column(db.String(50), nullable=False)
    cabang = db.Column(db.String(50), nullable=False)

    def get_id(self):
        return self.npk

class Penilaian(db.Model):
    __tablename__ = 'penilaian'
    
    id = db.Column(db.Integer, primary_key=True)
    npk = db.Column(db.String(20), db.ForeignKey('karyawan.npk'), nullable=False)
    penilai_npk = db.Column(db.String(20), db.ForeignKey('karyawan.npk'), nullable=False)
    tahun = db.Column(db.Integer, nullable=False)
    periode = db.Column(db.String(10), default='Q1')  # <-- TAMBAH BARIS INI
    status = db.Column(db.String(10), default='draft') # draft, final
    tanggal_update = db.Column(db.DateTime, default=datetime.now)
    
    # KEDISIPLINAN
    kehadiran = db.Column(db.Integer, default=2)
    kepatuhan_aturan = db.Column(db.Integer, default=2)
    konsistensi = db.Column(db.Integer, default=2)
    kepatuhan_seragam = db.Column(db.Integer, default=2)
    disiplin_kebersihan = db.Column(db.Integer, default=2)
    
    # PRODUKTIVITAS KERJA
    efisiensi = db.Column(db.Integer, default=2)
    prioritas = db.Column(db.Integer, default=2)
    inovasi = db.Column(db.Integer, default=2)
    multitasking = db.Column(db.Integer, default=2)
    peningkatan_kinerja = db.Column(db.Integer, default=2)
    
    # KEHANDALAN
    terampil = db.Column(db.Integer, default=2)
    keputusan = db.Column(db.Integer, default=2)
    inisiatif = db.Column(db.Integer, default=2)
    penyelesaian_masalah = db.Column(db.Integer, default=2)
    responsif = db.Column(db.Integer, default=2)
    
    # KERJASAMA
    menanggapi_positif = db.Column(db.Integer, default=2)
    koordinasi = db.Column(db.Integer, default=2)
    sikap_positif = db.Column(db.Integer, default=2)
    tidak_komplain = db.Column(db.Integer, default=2)
    profesional = db.Column(db.Integer, default=2)
    
    # TANGGUNG JAWAB
    tanggung_jawab_kerja = db.Column(db.Integer, default=2)
    menerima_kesalahan = db.Column(db.Integer, default=2)
    inventaris = db.Column(db.Integer, default=2)
    tanpa_pengawasan = db.Column(db.Integer, default=2)
    mengelola_prioritas = db.Column(db.Integer, default=2)
    
    # KEMAMPUAN BERADAPTASI
    belajar_cepat = db.Column(db.Integer, default=2)
    strategi_kerja = db.Column(db.Integer, default=2)
    tantangan_baru = db.Column(db.Integer, default=2)
    ubah_cara_kerja = db.Column(db.Integer, default=2)
    solusi_alternatif = db.Column(db.Integer, default=2)
    
    # KOMUNIKASI
    keramahan = db.Column(db.Integer, default=2)
    kejelasan = db.Column(db.Integer, default=2)
    responsif_kom = db.Column(db.Integer, default=2)
    lapor_pelanggaran = db.Column(db.Integer, default=2)
    keterbukaan = db.Column(db.Integer, default=2)
    
    karyawan = db.relationship('Karyawan', foreign_keys=[npk], backref='penilaian_diterima')
    penilai = db.relationship('Karyawan', foreign_keys=[penilai_npk], backref='penilaian_diberikan')
