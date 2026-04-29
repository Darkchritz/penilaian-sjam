   from app import app, db
   from app import Karyawan, Penilaian, AksesPenilaian 

   with app.app_context():
       print("Drop semua tabel...")
       db.drop_all()
       print("Create semua tabel...")
       db.create_all()
       print("Selesai!")
