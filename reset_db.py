from app import app, db
# Import semua model biar SQLAlchemy tau tabel apa aja yang harus di-create
from app import Karyawan, Penilaian, AksesPenilaian 

with app.app_context():
    print("Drop semua tabel...")
    db.drop_all()
    print("Create semua tabel...")
    db.create_all()
    print("Selesai! Database udah di-reset.")
