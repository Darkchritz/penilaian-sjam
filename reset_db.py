from app import app, db

with app.app_context():
    print("Mulai hapus semua tabel...")
    db.drop_all()
    print("Mulai bikin tabel baru dengan kpi1-kpi35...")
    db.create_all()
    print("Selesai! Database udah di-reset")
