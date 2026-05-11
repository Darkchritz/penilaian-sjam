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
    periode = db.Column(db.String(10), default='Q1')
    status = db.Column(db.String(10), default='draft') # draft, final
    tanggal_update = db.Column(db.DateTime, default=datetime.now)
    
    # KEDISIPLINAN
    kehadiran = db.Column(db.Integer, default=2) # KPI1 - diisi HRD
    kepatuhan_aturan = db.Column(db.Integer, default=2) # KPI2 - diisi HRD
    konsistensi = db.Column(db.Integer, nullable=True) # KPI3
    kepatuhan_seragam = db.Column(db.Integer, nullable=True) # KPI4
    disiplin_kebersihan = db.Column(db.Integer, nullable=True) # KPI5
    
    # PRODUKTIVITAS KERJA
    efisiensi = db.Column(db.Integer, nullable=True) # KPI6
    prioritas = db.Column(db.Integer, nullable=True) # KPI7
    inovasi = db.Column(db.Integer, nullable=True) # KPI8
    multitasking = db.Column(db.Integer, nullable=True) # KPI9
    peningkatan_kinerja = db.Column(db.Integer, nullable=True) # KPI10
    
    # KEHANDALAN
    terampil = db.Column(db.Integer, nullable=True) # KPI11
    keputusan = db.Column(db.Integer, nullable=True) # KPI12
    inisiatif = db.Column(db.Integer, nullable=True) # KPI13
    penyelesaian_masalah = db.Column(db.Integer, nullable=True) # KPI14
    responsif = db.Column(db.Integer, nullable=True) # KPI15
    
    # KERJASAMA
    menanggapi_positif = db.Column(db.Integer, nullable=True) # KPI16
    koordinasi = db.Column(db.Integer, nullable=True) # KPI17
    sikap_positif = db.Column(db.Integer, nullable=True) # KPI18
    tidak_komplain = db.Column(db.Integer, nullable=True) # KPI19
    profesional = db.Column(db.Integer, nullable=True) # KPI20
    
    # TANGGUNG JAWAB
    tanggung_jawab_kerja = db.Column(db.Integer, nullable=True) # KPI21
    menerima_kesalahan = db.Column(db.Integer, nullable=True) # KPI22
    inventaris = db.Column(db.Integer, nullable=True) # KPI23
    tanpa_pengawasan = db.Column(db.Integer, nullable=True) # KPI24
    mengelola_prioritas = db.Column(db.Integer, nullable=True) # KPI25
    
    # KEMAMPUAN BERADAPTASI
    belajar_cepat = db.Column(db.Integer, nullable=True) # KPI26
    strategi_kerja = db.Column(db.Integer, nullable=True) # KPI27
    tantangan_baru = db.Column(db.Integer, nullable=True) # KPI28
    ubah_cara_kerja = db.Column(db.Integer, nullable=True) # KPI29
    solusi_alternatif = db.Column(db.Integer, nullable=True) # KPI30
    
    # KOMUNIKASI
    keramahan = db.Column(db.Integer, nullable=True) # KPI31
    kejelasan = db.Column(db.Integer, nullable=True) # KPI32
    responsif_kom = db.Column(db.Integer, nullable=True) # KPI33
    lapor_pelanggaran = db.Column(db.Integer, nullable=True) # KPI34
    keterbukaan = db.Column(db.Integer, nullable=True) # KPI35
    
    karyawan = db.relationship('Karyawan', foreign_keys=[npk], backref='penilaian_diterima')
    penilai = db.relationship('Karyawan', foreign_keys=[penilai_npk], backref='penilaian_diberikan')
