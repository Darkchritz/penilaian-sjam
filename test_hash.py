from app import app, db
from werkzeug.security import generate_password_hash, check_password_hash
from app import Karyawan # ganti 'app' sesuai nama file app.py lu

with app.app_context():
    print("=== TEST 1: Generate + Check langsung ===")
    h = generate_password_hash('123456', method='pbkdf2:sha256')
    print("Hash:", h)
    print("Check:", check_password_hash(h, '123456'))
    
    print("\n=== TEST 2: Ambil dari DB ===")
    user = Karyawan.query.filter_by(npk=2014122128).first()
    if user:
        print("User ketemu:", user.nama)
        print("Hash di DB:", user.password)
        print("Panjang hash DB:", len(user.password))
        print("Check DB:", check_password_hash(user.password, '123456'))
        print("Check DB strip:", check_password_hash(user.password.strip(), '123456'))
    else:
        print("User ga ketemu")
