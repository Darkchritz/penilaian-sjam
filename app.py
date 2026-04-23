from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3, pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
import gspread, os, json
from google.oauth2.service_account import Credentials
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'ganti-ini-jadi-random'

SHEET_NAME = os.environ.get('SHEET_NAME', 'Penilaian SJA')

def get_db():
    conn = sqlite3.connect('data.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (npk TEXT PRIMARY KEY, password TEXT, nama TEXT, role TEXT, divisi TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS hasil_akhir 
                 (id INTEGER PRIMARY KEY, npk TEXT, periode TEXT, nilai_akhir REAL, 
                  grade TEXT, keterangan TEXT, status TEXT, tgl_finalisasi TEXT)''')
    users = [
        ('KD001', generate_password_hash('123'), 'Budi Kadiv', 'kadiv', 'Operasional'),
        ('K001', generate_password_hash('123'), 'Ani Staff', 'karyawan', 'Operasional'),
        ('HRD01', generate_password_hash('123'), 'Admin HRD', 'hrd', 'HRD')
    ]
    c.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)", users)
    conn.commit()
    conn.close()

def get_gsheet():
    scopes = ['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
    if 'CREDS_JSON' in os.environ:
        creds_dict = json.loads(os.environ['CREDS_JSON'])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file('creds.json', scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def hitung_grade(nilai):
    if nilai >= 95: return 'A+'
    elif nilai >= 85: return 'A'
    elif nilai >= 75: return 'B'
    elif nilai >= 65: return 'C'
    elif nilai >= 50: return 'D'
    else: return 'E'

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        npk, password = request.form['npk'], request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE npk = ?', (npk,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user'] = dict(user)
            if user['role'] == 'hrd': return redirect('/dashboard_hrd')
            elif user['role'] == 'kadiv': return redirect('/dashboard_kadiv')
            else: return redirect('/dashboard_karyawan')
    return render_template('login.html')

@app.route('/dashboard_kadiv')
def dashboard_kadiv():
    if 'user' not in session or session['user']['role'] != 'kadiv': return redirect('/')
    return render_template('dashboard_kadiv.html', user=session['user'])

@app.route('/finalisasi', methods=['POST'])
def finalisasi():
    if 'user' not in session or session['user']['role'] != 'kadiv': return redirect('/')
    data = request.form
    nilai_akhir = float(data['nilai_akhir'])
    grade = hitung_grade(nilai_akhir)
    conn = get_db()
    conn.execute('''INSERT INTO hasil_akhir (npk, periode, nilai_akhir, grade, keterangan, status, tgl_finalisasi) 
                    VALUES (?,?,?,?,?,?,?)''', 
                 (data['npk'], data['periode'], nilai_akhir, grade, data['keterangan'], 
                  'Final', datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()
    try:
        sheet = get_gsheet()
        sheet.append_row([data['npk'], data['periode'], nilai_akhir, grade, data['keterangan'], 'Final'])
    except Exception as e:
        print("GSheet error:", e)
    return redirect('/dashboard_kadiv')

@app.route('/dashboard_hrd')
def dashboard_hrd():
    if 'user' not in session or session['user']['role'] != 'hrd': return redirect('/')
    conn = get_db()
    df = pd.read_sql_query('''
        SELECT h.npk, u.nama, u.divisi, h.periode, h.nilai_akhir, h.grade, h.status 
        FROM hasil_akhir h JOIN users u ON h.npk = u.npk
    ''', conn)
    conn.close()
    return render_template('dashboard_hrd.html', data=df.to_dict('records'))

@app.route('/dashboard_karyawan')
def dashboard_karyawan():
    if 'user' not in session: return redirect('/')
    npk = session['user']['npk']
    conn = get_db()
    hasil = conn.execute('SELECT * FROM hasil_akhir WHERE npk = ? ORDER BY periode DESC', (npk,)).fetchall()
    conn.close()
    return render_template('dashboard_karyawan.html', user=session['user'], hasil=hasil)

@app.route('/export_excel')
def export_excel():
    if 'user' not in session or session['user']['role'] != 'hrd': return redirect('/')
    conn = get_db()
    df = pd.read_sql_query('SELECT * FROM hasil_akhir', conn)
    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Rekap')
    output.seek(0)
    return send_file(output, download_name='rekap_penilaian.xlsx', as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
