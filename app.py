from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import pandas as pd
import sqlite3
import os
import io
import hashlib
from datetime import datetime
import xlsxwriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'salesiq_secret_2026'

UPLOAD_FOLDER = 'uploads'
DB_PATH       = 'data/sales.db'
ALLOWED_EXT   = {'xlsx','xls','csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('data', exist_ok=True)

# ── EMAIL CONFIG ──
EMAIL_CONFIG = {
    'expediteur':   'dieynabasamb903@gmail.com',
    'mot_de_passe': 'nxyafghrjdhbsvts',
    'smtp_server':  'smtp.gmail.com',
    'smtp_port':    587,
}

# ── DB ──
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT DEFAULT '',
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, produit TEXT, categorie TEXT,
        quantite REAL, prix REAL, cout REAL,
        ville TEXT, vendeur TEXT, client TEXT,
        mode_paiement TEXT, statut TEXT,
        montant REAL, benefice REAL,
        fichier_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS fichiers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT, nb_lignes INTEGER,
        importe_le TEXT, user_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS objectifs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        ca_mensuel REAL DEFAULT 0,
        seuil_baisse REAL DEFAULT 20,
        seuil_produit_faible INTEGER DEFAULT 3
    )''')
    # Admin par defaut avec id=1
    pw = hashlib.sha256('admin123'.encode()).hexdigest()
    existing = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        c.execute("INSERT INTO users (id,username,password,created_at) VALUES (1,?,?,?)",
                  ('admin', pw, datetime.now().strftime('%Y-%m-%d %H:%M')))
    # Migration email
    try:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
    except:
        pass
    conn.commit()
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def allowed_file(f):
    return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXT

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── EMAIL ──
def envoyer_email(stats, nom_fichier, user_id):
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        if not stats or not user_id:
            return
        conn = sqlite3.connect(DB_PATH)
        user = conn.execute("SELECT email,username FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        if not user or not user[0] or '@' not in user[0]:
            print(f"Pas d'email pour user_id={user_id}")
            return
        dest, uname = user[0], user[1]
        k   = stats['kpis']
        fmt = lambda n: f"{int(n):,}".replace(',', ' ')
        html = f"""<html><body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:20px">
        <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.08)">
          <div style="background:#2563eb;padding:24px;text-align:center">
            <h1 style="color:white;margin:0;font-size:20px">SalesIQ — Rapport d'Import</h1>
            <p style="color:#bfdbfe;margin:6px 0 0">Bonjour {uname} — {nom_fichier}</p>
          </div>
          <div style="padding:28px">
            <table style="width:100%;border-collapse:collapse">
              <tr style="background:#f8fafc"><td style="padding:10px 14px;border:1px solid #e2e8f0;font-weight:bold">Chiffre d'Affaires</td><td style="padding:10px 14px;border:1px solid #e2e8f0;color:#2563eb;font-weight:bold">{fmt(k['total_ca'])} FCFA</td></tr>
              <tr><td style="padding:10px 14px;border:1px solid #e2e8f0;font-weight:bold">Benefice</td><td style="padding:10px 14px;border:1px solid #e2e8f0;color:#059669;font-weight:bold">{fmt(k['total_benefice'])} FCFA</td></tr>
              <tr style="background:#f8fafc"><td style="padding:10px 14px;border:1px solid #e2e8f0;font-weight:bold">Marge</td><td style="padding:10px 14px;border:1px solid #e2e8f0">{k['marge_pct']:.1f}%</td></tr>
              <tr><td style="padding:10px 14px;border:1px solid #e2e8f0;font-weight:bold">Unites Vendues</td><td style="padding:10px 14px;border:1px solid #e2e8f0">{fmt(k['total_ventes'])}</td></tr>
              <tr style="background:#f8fafc"><td style="padding:10px 14px;border:1px solid #e2e8f0;font-weight:bold">Top Produit</td><td style="padding:10px 14px;border:1px solid #e2e8f0">{k['top_produit']}</td></tr>
            </table>
          </div>
          <div style="background:#f8fafc;padding:14px;text-align:center;color:#94a3b8;font-size:11px">SalesIQ — {datetime.now().strftime('%d/%m/%Y a %H:%M')}</div>
        </div></body></html>"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"SalesIQ — Rapport : {nom_fichier}"
        msg['From']    = EMAIL_CONFIG['expediteur']
        msg['To']      = dest
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as s:
            s.starttls()
            s.login(EMAIL_CONFIG['expediteur'], EMAIL_CONFIG['mot_de_passe'])
            s.sendmail(EMAIL_CONFIG['expediteur'], dest, msg.as_string())
        print(f"Email envoye a {dest}")
    except Exception as e:
        print(f"Erreur email: {e}")

# ── AUTH ──
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        d = request.get_json()
        conn = sqlite3.connect(DB_PATH)
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?",
                            (d.get('username','').strip(), hash_pw(d.get('password','').strip()))).fetchone()
        conn.close()
        if user:
            session['user_id']  = user[0]
            session['username'] = user[1]
            return jsonify({'success': True, 'username': user[1]})
        return jsonify({'error': 'Identifiants incorrects'}), 401
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    d = request.get_json()
    username = d.get('username','').strip()
    password = d.get('password','').strip()
    email    = d.get('email','').strip()
    if not username or not password or not email:
        return jsonify({'error': 'Tous les champs sont obligatoires'}), 400
    if '@' not in email:
        return jsonify({'error': 'Email invalide'}), 400
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO users (username,password,email,created_at) VALUES (?,?,?,?)",
                     (username, hash_pw(password), email, datetime.now().strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': "Nom d'utilisateur deja pris"}), 400

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username'))

# ── UPLOAD + MAPPING ──
SYNONYMES = {
    'date':          ['date','dat','jour','day','fecha','journee','invoice_date','order_date','sale_date'],
    'produit':       ['produit','product','article','designation','libelle','item','nom_produit','sku','goods','producto','articulo'],
    'categorie':     ['categ','category','famille','type','groupe','class','department','familia'],
    'quantite':      ['qte','qty','quant','quantite','quantité','nombre','nbre','nb','quantity','amount','count','units','pieces','pcs','cantidad'],
    'prix':          ['prix','price','unit_price','tarif','pu','prix_vente','selling_price','sale_price','precio','fcfa','montant_unit'],
    'cout':          ['cout','cost','achat','prix_achat','coût','purchase_price','buying_price','costo'],
    'ville':         ['ville','city','region','localite','zone','agence','town','location','area','place','ciudad'],
    'vendeur':       ['vendeur','vendor','agent','commercial','representant','employe','seller','salesperson','sales_rep','staff'],
    'client':        ['client','customer','acheteur','nom_client','buyer','consumer','purchaser'],
    'mode_paiement': ['paiement','payment','mode','moyen','reglement','pay_method','orange_money','wave','mobile_money'],
    'statut':        ['statut','status','etat','state','condition'],
}

def auto_detect(colonnes):
    mapping = {}
    for col in colonnes:
        col_lower = col.lower().strip().replace(' ','_').replace('-','_')
        mapping[col] = ''
        for champ, syns in SYNONYMES.items():
            if any(s in col_lower for s in syns):
                mapping[col] = champ
                break
    return mapping

def load_df(filepath):
    ext = filepath.rsplit('.',1)[1].lower()
    if ext == 'csv':
        try:
            df = pd.read_csv(filepath, sep=';')
            if df.shape[1] == 1:
                df = pd.read_csv(filepath, sep=',')
        except:
            df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)
    return df

def save_to_db(df, filename, user_id):
    for col in ['produit','categorie','quantite','prix','cout','ville','vendeur','client','mode_paiement','statut','date']:
        if col not in df.columns:
            df[col] = 'N/A' if col not in ['quantite','prix','cout'] else 0
    df['quantite'] = pd.to_numeric(df['quantite'], errors='coerce').fillna(0)
    df['prix']     = pd.to_numeric(df['prix'],     errors='coerce').fillna(0)
    df['cout']     = pd.to_numeric(df['cout'],     errors='coerce').fillna(0)
    df['montant']  = df['quantite'] * df['prix']
    df['benefice'] = df['quantite'] * (df['prix'] - df['cout'])
    try:
        df['date'] = pd.to_datetime(df['date'], dayfirst=True).dt.strftime('%Y-%m-%d')
    except:
        df['date'] = df['date'].astype(str)
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.execute("INSERT INTO fichiers (nom,nb_lignes,importe_le,user_id) VALUES (?,?,?,?)",
                        (filename, len(df), datetime.now().strftime('%Y-%m-%d %H:%M'), user_id))
    fid = cur.lastrowid
    conn.commit()
    df['fichier_id'] = fid
    cols = ['date','produit','categorie','quantite','prix','cout','ville','vendeur','client','mode_paiement','statut','montant','benefice','fichier_id']
    df[cols].to_sql('sales', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()
    return fid

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier'}), 400
    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({'error': 'Format non supporte (.xlsx ou .csv)'}), 400
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        df = load_df(filepath)
        colonnes     = df.columns.tolist()
        mapping_auto = auto_detect(colonnes)
        apercu       = df.head(3).fillna('').astype(str).to_dict('records')
        session['pending_file']     = filepath
        session['pending_filename'] = filename
        session['pending_rows']     = len(df)
        return jsonify({
            'need_mapping':  True,
            'colonnes':      colonnes,
            'apercu':        apercu,
            'mapping_auto':  mapping_auto,
            'rows':          len(df)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/confirmer_mapping', methods=['POST'])
@login_required
def confirmer_mapping():
    try:
        data     = request.get_json()
        mapping  = data.get('mapping', {})
        filepath = session.get('pending_file')
        filename = session.get('pending_filename')
        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': 'Fichier introuvable — veuillez reimporter'}), 400
        df = load_df(filepath)
        df = df.rename(columns={col: champ for col, champ in mapping.items() if champ})
        fid   = save_to_db(df, filename, session['user_id'])
        stats = get_stats(fichier_id=fid, user_id=session['user_id'])
        import threading
        threading.Thread(target=envoyer_email, args=(stats, filename, session['user_id']), daemon=True).start()
        return jsonify({'success': True, 'stats': stats, 'rows': len(df), 'fichier_id': fid, 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── STATS ──
def get_stats(ville=None, produit=None, categorie=None, vendeur=None,
              mode_paiement=None, statut=None,
              date_debut=None, date_fin=None, fichier_id=None, user_id=None):
    conn  = sqlite3.connect(DB_PATH)
    query = 'SELECT s.* FROM sales s JOIN fichiers f ON s.fichier_id=f.id WHERE 1=1'
    params = []
    if user_id:       query += ' AND f.user_id=?';      params.append(user_id)
    if ville:         query += ' AND s.ville=?';         params.append(ville)
    if produit:       query += ' AND s.produit=?';       params.append(produit)
    if categorie:     query += ' AND s.categorie=?';     params.append(categorie)
    if vendeur:       query += ' AND s.vendeur=?';       params.append(vendeur)
    if mode_paiement: query += ' AND s.mode_paiement=?'; params.append(mode_paiement)
    if statut:        query += ' AND s.statut=?';        params.append(statut)
    if date_debut:    query += ' AND s.date>=?';         params.append(date_debut)
    if date_fin:      query += ' AND s.date<=?';         params.append(date_fin)
    if fichier_id:    query += ' AND s.fichier_id=?';    params.append(fichier_id)
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    if df.empty: return None
    total_ca       = float(df['montant'].sum())
    total_ben      = float(df['benefice'].sum())
    total_ventes   = int(df['quantite'].sum())
    nb_trans       = len(df)
    panier_moyen   = total_ca / nb_trans if nb_trans > 0 else 0
    marge_pct      = (total_ben / total_ca * 100) if total_ca > 0 else 0
    top_prod       = df.groupby('produit')['quantite'].sum().idxmax()
    def agg(col):
        return df.groupby(col).agg(quantite=('quantite','sum'), ca=('montant','sum'), benefice=('benefice','sum')).reset_index().sort_values('ca', ascending=False).to_dict('records')
    df['date_dt'] = pd.to_datetime(df['date'], errors='coerce')
    df['mois']    = df['date_dt'].dt.to_period('M').astype(str)
    par_mois = df.groupby('mois').agg(ca=('montant','sum'), quantite=('quantite','sum')).reset_index().sort_values('mois')
    par_date = df.groupby('date').agg(ca=('montant','sum')).reset_index().sort_values('date')
    def uniq(col):
        return sorted(df[col].dropna().replace('N/A', pd.NA).dropna().unique().tolist())
    raw_cols = ['date','produit','categorie','quantite','prix','cout','ville','vendeur','client','mode_paiement','statut','montant','benefice']
    for c in raw_cols:
        if c not in df.columns: df[c] = 'N/A'
    return {
        'kpis': {'total_ca':total_ca,'total_benefice':total_ben,'total_ventes':total_ventes,
                 'nb_transactions':nb_trans,'panier_moyen':panier_moyen,'marge_pct':marge_pct,'top_produit':top_prod},
        'par_produit':   agg('produit'),
        'par_ville':     agg('ville'),
        'par_categorie': agg('categorie'),
        'par_vendeur':   agg('vendeur'),
        'par_paiement':  agg('mode_paiement'),
        'par_mois':      par_mois.to_dict('records'),
        'par_date':      par_date.to_dict('records'),
        'raw':           df[raw_cols].head(200).to_dict('records'),
        'villes':        uniq('ville'),
        'produits':      uniq('produit'),
    }

@app.route('/stats')
@login_required
def stats():
    data = get_stats(
        request.args.get('ville'), request.args.get('produit'),
        request.args.get('categorie'), request.args.get('vendeur'),
        request.args.get('mode_paiement'), request.args.get('statut'),
        request.args.get('date_debut'), request.args.get('date_fin'),
        request.args.get('fichier_id'), session['user_id'])
    if not data: return jsonify({'error': 'Aucune donnee'}), 404
    return jsonify(data)

# ── OBJECTIFS ──
@app.route('/objectifs', methods=['GET','POST'])
@login_required
def objectifs():
    conn = sqlite3.connect(DB_PATH)
    if request.method == 'POST':
        d = request.get_json()
        conn.execute('''INSERT INTO objectifs (user_id,ca_mensuel,seuil_baisse,seuil_produit_faible)
                        VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                        ca_mensuel=excluded.ca_mensuel, seuil_baisse=excluded.seuil_baisse,
                        seuil_produit_faible=excluded.seuil_produit_faible''',
                     (session['user_id'], float(d.get('ca_mensuel',0)),
                      float(d.get('seuil_baisse',20)), int(d.get('seuil_produit_faible',3))))
        conn.commit(); conn.close()
        return jsonify({'success': True})
    row = conn.execute("SELECT * FROM objectifs WHERE user_id=?", (session['user_id'],)).fetchone()
    conn.close()
    if row: return jsonify({'ca_mensuel':row[2],'seuil_baisse':row[3],'seuil_produit_faible':row[4]})
    return jsonify({'ca_mensuel':0,'seuil_baisse':20,'seuil_produit_faible':3})

# ── ALERTES ──
@app.route('/alertes')
@login_required
def alertes():
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql('SELECT s.* FROM sales s JOIN fichiers f ON s.fichier_id=f.id WHERE f.user_id=?',
                       conn, params=[session['user_id']])
    obj  = conn.execute("SELECT * FROM objectifs WHERE user_id=?", (session['user_id'],)).fetchone()
    conn.close()
    if df.empty: return jsonify([])
    alerts = []
    ca_obj = obj[2] if obj else 0
    seuil_baisse = obj[3] if obj else 20
    seuil_faible = obj[4] if obj else 3
    df['date_dt'] = pd.to_datetime(df['date'], errors='coerce')
    df['mois']    = df['date_dt'].dt.to_period('M').astype(str)
    par_mois = df.groupby('mois')['montant'].sum().reset_index().sort_values('mois')
    if len(par_mois) >= 2:
        ca_av = float(par_mois.iloc[-2]['montant']); ca_ac = float(par_mois.iloc[-1]['montant'])
        m_ac  = par_mois.iloc[-1]['mois']; m_av = par_mois.iloc[-2]['mois']
        if ca_av > 0:
            v = (ca_ac - ca_av) / ca_av * 100
            if v <= -seuil_baisse:
                alerts.append({'type':'danger','icon':'BAISSE','titre':'Baisse des ventes','message':f"CA {m_ac} ({int(ca_ac):,} FCFA) a baisse de {abs(v):.1f}% vs {m_av}"})
            elif v > 0:
                alerts.append({'type':'success','icon':'HAUSSE','titre':'Hausse des ventes','message':f"CA {m_ac} a augmente de {v:.1f}% vs {m_av}"})
    if ca_obj > 0 and len(par_mois) >= 1:
        ca_d = float(par_mois.iloc[-1]['montant']); m_d = par_mois.iloc[-1]['mois']
        pct  = ca_d / ca_obj * 100
        if pct >= 100:
            alerts.append({'type':'success','icon':'BRAVO','titre':'Objectif atteint !','message':f"Tu as atteint {pct:.0f}% de ton objectif en {m_d}"})
        elif pct >= 75:
            alerts.append({'type':'warning','icon':'BIENT','titre':'Objectif presque atteint','message':f"Tu es a {pct:.0f}% de ton objectif"})
        else:
            alerts.append({'type':'danger','icon':'ALERT','titre':'Objectif en danger','message':f"Seulement {pct:.0f}% de l'objectif atteint"})
    pp = df.groupby('produit')['quantite'].sum()
    pf = pp[pp <= seuil_faible].index.tolist()
    if pf:
        alerts.append({'type':'warning','icon':'STOCK','titre':'Produits peu vendus','message':f"{len(pf)} produit(s) vendu(s) moins de {seuil_faible} fois : {', '.join(pf[:3])}"})
    pv = df.groupby('ville')['montant'].sum()
    if len(pv):
        alerts.append({'type':'info','icon':'TOP','titre':'Meilleure ville','message':f"{pv.idxmax()} avec {int(pv.max()):,} FCFA de CA"})
    return jsonify(alerts)

# ── HISTORIQUE ──
@app.route('/historique')
@login_required
def historique():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT f.id,f.nom,f.nb_lignes,f.importe_le,u.username FROM fichiers f JOIN users u ON f.user_id=u.id WHERE f.user_id=? ORDER BY f.id DESC",
        (session['user_id'],)).fetchall()
    conn.close()
    return jsonify([{'id':r[0],'nom':r[1],'nb_lignes':r[2],'importe_le':r[3],'user':r[4]} for r in rows])

@app.route('/historique/delete/<int:fid>', methods=['DELETE'])
@login_required
def delete_fichier(fid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM sales WHERE fichier_id=?', (fid,))
    conn.execute('DELETE FROM fichiers WHERE id=? AND user_id=?', (fid, session['user_id']))
    conn.commit(); conn.close()
    return jsonify({'success': True})

# ── COMPARER ──
@app.route('/comparer')
@login_required
def comparer():
    s1 = get_stats(date_debut=request.args.get('p1_debut'), date_fin=request.args.get('p1_fin'), user_id=session['user_id'])
    s2 = get_stats(date_debut=request.args.get('p2_debut'), date_fin=request.args.get('p2_fin'), user_id=session['user_id'])
    if not s1 or not s2: return jsonify({'error': 'Donnees insuffisantes'}), 404
    def delta(a,b): return round((a-b)/b*100,1) if b!=0 else 0
    return jsonify({
        'periode1':{'label':f"{request.args.get('p1_debut')} au {request.args.get('p1_fin')}","kpis":s1['kpis']},
        'periode2':{'label':f"{request.args.get('p2_debut')} au {request.args.get('p2_fin')}","kpis":s2['kpis']},
        'delta':{'ca':delta(s1['kpis']['total_ca'],s2['kpis']['total_ca']),
                 'benefice':delta(s1['kpis']['total_benefice'],s2['kpis']['total_benefice']),
                 'ventes':delta(s1['kpis']['total_ventes'],s2['kpis']['total_ventes']),
                 'transactions':delta(s1['kpis']['nb_transactions'],s2['kpis']['nb_transactions'])}
    })

# ── CLIENTS ──
@app.route('/clients')
@login_required
def clients():
    fid  = request.args.get('fichier_id')
    conn = sqlite3.connect(DB_PATH)
    query = 'SELECT s.* FROM sales s JOIN fichiers f ON s.fichier_id=f.id WHERE f.user_id=?'
    params = [session['user_id']]
    if fid: query += ' AND s.fichier_id=?'; params.append(fid)
    df = pd.read_sql(query, conn, params=params); conn.close()
    if df.empty or 'client' not in df.columns: return jsonify([])
    df = df[df['client'].notna() & (df['client'] != 'N/A') & (df['client'] != '')]
    if df.empty: return jsonify([])
    pc = df.groupby('client').agg(nb_achats=('id','count'), ca_total=('montant','sum'),
         benefice=('benefice','sum'), qte_totale=('quantite','sum'),
         derniere_date=('date','max')).reset_index().sort_values('ca_total', ascending=False)
    pc['panier_moyen'] = (pc['ca_total']/pc['nb_achats']).round(0)
    pc['ca_total']     = pc['ca_total'].round(0)
    pc['benefice']     = pc['benefice'].round(0)
    return jsonify(pc.to_dict('records'))

@app.route('/clients/<path:nom>/achats')
@login_required
def client_achats(nom):
    fid  = request.args.get('fichier_id')
    conn = sqlite3.connect(DB_PATH)
    query = 'SELECT s.* FROM sales s JOIN fichiers f ON s.fichier_id=f.id WHERE f.user_id=? AND s.client=?'
    params = [session['user_id'], nom]
    if fid: query += ' AND s.fichier_id=?'; params.append(fid)
    df = pd.read_sql(query, conn, params=params); conn.close()
    cols = ['date','produit','categorie','quantite','prix','montant','benefice','ville','vendeur','mode_paiement','statut']
    for c in cols:
        if c not in df.columns: df[c] = 'N/A'
    return jsonify(df[cols].sort_values('date', ascending=False).head(50).to_dict('records'))

# ── VENDEURS ──
@app.route('/vendeurs')
@login_required
def vendeurs():
    fid  = request.args.get('fichier_id')
    conn = sqlite3.connect(DB_PATH)
    query = 'SELECT s.* FROM sales s JOIN fichiers f ON s.fichier_id=f.id WHERE f.user_id=?'
    params = [session['user_id']]
    if fid: query += ' AND s.fichier_id=?'; params.append(fid)
    df = pd.read_sql(query, conn, params=params); conn.close()
    if df.empty or 'vendeur' not in df.columns: return jsonify([])
    df = df[df['vendeur'].notna() & (df['vendeur'] != 'N/A') & (df['vendeur'] != '')]
    if df.empty: return jsonify([])
    pv = df.groupby('vendeur').agg(nb_ventes=('id','count'), ca_total=('montant','sum'),
         benefice=('benefice','sum'), qte_totale=('quantite','sum'),
         nb_clients=('client','nunique')).reset_index().sort_values('ca_total', ascending=False)
    pv['panier_moyen'] = (pv['ca_total']/pv['nb_ventes']).round(0)
    pv['ca_total']     = pv['ca_total'].round(0)
    pv['benefice']     = pv['benefice'].round(0)
    return jsonify(pv.to_dict('records'))

# ── SAISIE ──
# ── FACTURATION ──
def get_next_facture_num(user_id):
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT COUNT(*) FROM fichiers WHERE user_id=? AND nom LIKE 'FAC-%'",
        (user_id,)).fetchone()
    conn.close()
    num = (row[0] or 0) + 1
    return f"FAC-{datetime.now().year}-{num:03d}"

@app.route('/factures', methods=['GET'])
@login_required
def get_factures():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id,nom,nb_lignes,importe_le FROM fichiers WHERE user_id=? AND nom LIKE 'FAC-%' ORDER BY id DESC",
        (session['user_id'],)).fetchall()
    conn.close()
    result = []
    for r in rows:
        conn2 = sqlite3.connect(DB_PATH)
        lignes = conn2.execute(
            "SELECT produit,quantite,prix,montant,client,statut,ville,mode_paiement FROM sales WHERE fichier_id=?",
            (r[0],)).fetchall()
        conn2.close()
        total = sum(l[3] for l in lignes)
        client = lignes[0][4] if lignes else 'N/A'
        statut = lignes[0][5] if lignes else 'N/A'
        result.append({
            'id': r[0], 'numero': r[1], 'date': r[3][:10] if r[3] else '',
            'client': client, 'total': round(total, 0),
            'nb_articles': len(lignes), 'statut': statut,
            'lignes': [{'produit':l[0],'quantite':l[1],'prix':l[2],'montant':l[3]} for l in lignes]
        })
    return jsonify(result)

@app.route('/factures/creer', methods=['POST'])
@login_required
def creer_facture():
    d = request.get_json()
    try:
        num_facture = get_next_facture_num(session['user_id'])
        date_f      = d.get('date', datetime.now().strftime('%Y-%m-%d'))
        client      = d.get('client', 'N/A')
        ville       = d.get('ville', 'N/A')
        vendeur     = d.get('vendeur', 'N/A')
        paiement    = d.get('mode_paiement', 'Cash')
        statut      = d.get('statut', 'Paye')
        lignes      = d.get('lignes', [])
        if not lignes:
            return jsonify({'error': 'Aucun produit dans la facture'}), 400
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.execute(
            "INSERT INTO fichiers (nom,nb_lignes,importe_le,user_id) VALUES (?,?,?,?)",
            (num_facture, len(lignes), datetime.now().strftime('%Y-%m-%d %H:%M'), session['user_id']))
        fid = cur.lastrowid
        sql = ("INSERT INTO sales (date,produit,categorie,quantite,prix,cout,ville,vendeur,client,"
               "mode_paiement,statut,montant,benefice,fichier_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        for ligne in lignes:
            q = float(ligne.get('quantite', 1))
            p = float(ligne.get('prix', 0))
            c = float(ligne.get('cout', 0))
            conn.execute(sql, (date_f, ligne.get('produit',''), ligne.get('categorie','N/A'),
                q, p, c, ville, vendeur, client, paiement, statut, q*p, q*(p-c), fid))
        conn.commit(); conn.close()
        return jsonify({'success': True, 'fichier_id': fid, 'numero': num_facture})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/factures/<int:fid>/pdf')
@login_required
def facture_pdf(fid):
    conn  = sqlite3.connect(DB_PATH)
    fiche = conn.execute(
        "SELECT f.*,u.username FROM fichiers f JOIN users u ON f.user_id=u.id WHERE f.id=? AND f.user_id=?",
        (fid, session['user_id'])).fetchone()
    if not fiche: conn.close(); return jsonify({'error': 'Facture introuvable'}), 404
    lignes = conn.execute(
        "SELECT produit,categorie,quantite,prix,cout,montant,benefice,client,ville,vendeur,mode_paiement,statut,date FROM sales WHERE fichier_id=?",
        (fid,)).fetchall()
    conn.close()
    if not lignes: return jsonify({'error': 'Facture vide'}), 404

    num_facture = fiche[1]
    date_f      = lignes[0][12][:10] if lignes[0][12] else datetime.now().strftime('%Y-%m-%d')
    client      = lignes[0][7] or 'N/A'
    ville       = lignes[0][8] or 'N/A'
    vendeur     = lignes[0][9] or 'N/A'
    paiement    = lignes[0][10] or 'N/A'
    statut      = lignes[0][11] or 'N/A'
    total       = sum(l[5] for l in lignes)
    total_ben   = sum(l[6] for l in lignes)

    output = io.BytesIO()
    doc    = SimpleDocTemplate(output, pagesize=A4,
             rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    c_blue  = colors.HexColor('#2563eb')
    c_dark  = colors.HexColor('#1a1f2e')
    c_light = colors.HexColor('#f8fafc')
    c_green = colors.HexColor('#059669')
    c_grey  = colors.HexColor('#64748b')

    elements = []

    # EN-TETE
    header_data = [[
        Paragraph(f'<font size="22" color="#2563eb"><b>SalesIQ</b></font>', styles['Normal']),
        Paragraph(f'<font size="11" color="#64748b">Analyse Intelligente des Ventes</font>', styles['Normal']),
    ]]
    header_t = Table(header_data, colWidths=[9*cm, 8*cm])
    header_t.setStyle(TableStyle([('ALIGN',(1,0),(1,0),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    elements.append(header_t)
    elements.append(Spacer(1, 0.3*cm))

    # Ligne separatrice
    line = Table([['']], colWidths=[17*cm], rowHeights=[3])
    line.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),c_blue), ('LINEABOVE',(0,0),(-1,-1),0,colors.white)]))
    elements.append(line)
    elements.append(Spacer(1, 0.5*cm))

    # FACTURE TITRE + INFOS
    statut_color = '#059669' if 'pay' in statut.lower() else '#d97706' if 'att' in statut.lower() else '#dc2626'
    info_data = [
        [Paragraph(f'<font size="18" color="#1a1f2e"><b>FACTURE</b></font>', styles['Normal']),
         Paragraph(f'<font size="11" color="#64748b">Numero : </font><font size="11" color="#2563eb"><b>{num_facture}</b></font>', styles['Normal'])],
        ['',
         Paragraph(f'<font size="11" color="#64748b">Date : </font><font size="11"><b>{date_f}</b></font>', styles['Normal'])],
        ['',
         Paragraph(f'<font size="11" color="#64748b">Statut : </font><font size="11" color="{statut_color}"><b>{statut}</b></font>', styles['Normal'])],
    ]
    info_t = Table(info_data, colWidths=[9*cm, 8*cm])
    info_t.setStyle(TableStyle([('ALIGN',(1,0),(1,-1),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'TOP')]))
    elements.append(info_t)
    elements.append(Spacer(1, 0.5*cm))

    # INFOS CLIENT / VENDEUR
    client_data = [
        [Paragraph('<font size="9" color="#64748b"><b>FACTURE A</b></font>', styles['Normal']),
         Paragraph('<font size="9" color="#64748b"><b>EMIS PAR</b></font>', styles['Normal'])],
        [Paragraph(f'<font size="12" color="#1a1f2e"><b>{client}</b></font>', styles['Normal']),
         Paragraph(f'<font size="12" color="#1a1f2e"><b>{session["username"]}</b></font>', styles['Normal'])],
        [Paragraph(f'<font size="10" color="#64748b">{ville}</font>', styles['Normal']),
         Paragraph(f'<font size="10" color="#64748b">Vendeur : {vendeur}</font>', styles['Normal'])],
        [Paragraph(f'<font size="10" color="#64748b">Mode : {paiement}</font>', styles['Normal']),
         Paragraph(f'<font size="10" color="#64748b">SalesIQ Platform</font>', styles['Normal'])],
    ]
    client_t = Table(client_data, colWidths=[8.5*cm, 8.5*cm])
    client_t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),c_light),
        ('PADDING',(0,0),(-1,-1),8),
        ('ROUNDEDCORNERS',[4]),
        ('BOX',(0,0),(-1,-1),1,colors.HexColor('#e2e8f0')),
        ('LINEAFTER',(0,0),(0,-1),1,colors.HexColor('#e2e8f0')),
    ]))
    elements.append(client_t)
    elements.append(Spacer(1, 0.6*cm))

    # TABLEAU PRODUITS
    prod_header = ['Produit', 'Categorie', 'Qte', 'Prix Unit.', 'Total']
    prod_data   = [prod_header]
    for l in lignes:
        prod_data.append([
            Paragraph(f'<b>{l[0]}</b>', styles['Normal']),
            l[1] if l[1] != 'N/A' else '—',
            str(int(l[2])),
            f"{int(l[3]):,} FCFA".replace(',', ' '),
            Paragraph(f'<font color="#2563eb"><b>{int(l[5]):,} FCFA</b></font>'.replace(',', ' '), styles['Normal']),
        ])

    prod_t = Table(prod_data, colWidths=[5*cm, 3.5*cm, 2*cm, 3*cm, 3.5*cm])
    prod_t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),c_blue),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),10),
        ('ALIGN',(2,0),(-1,-1),'RIGHT'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[c_light, colors.white]),
        ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#e2e8f0')),
        ('PADDING',(0,0),(-1,-1),8),
    ]))
    elements.append(prod_t)
    elements.append(Spacer(1, 0.4*cm))

    # TOTAUX
    total_data = [
        ['', 'Sous-total HT', f"{int(total):,} FCFA".replace(',', ' ')],
        ['', f'Benefice', f"{int(total_ben):,} FCFA".replace(',', ' ')],
    ]
    total_t = Table(total_data, colWidths=[8*cm, 5*cm, 4*cm])
    total_t.setStyle(TableStyle([
        ('ALIGN',(1,0),(-1,-1),'RIGHT'),
        ('FONTSIZE',(0,0),(-1,-1),10),
        ('TEXTCOLOR',(2,1),(2,1),c_green),
        ('PADDING',(0,0),(-1,-1),6),
    ]))
    elements.append(total_t)

    # LIGNE + GRAND TOTAL
    elements.append(Spacer(1, 0.2*cm))
    grand_total_data = [['', 'TOTAL A PAYER', f"{int(total):,} FCFA".replace(',', ' ')]]
    gt = Table(grand_total_data, colWidths=[8*cm, 5*cm, 4*cm])
    gt.setStyle(TableStyle([
        ('BACKGROUND',(1,0),(-1,0),c_blue),
        ('TEXTCOLOR',(1,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),12),
        ('ALIGN',(1,0),(-1,-1),'RIGHT'),
        ('PADDING',(0,0),(-1,-1),10),
        ('ROUNDEDCORNERS',[4]),
    ]))
    elements.append(gt)
    elements.append(Spacer(1, 0.8*cm))

    # PIED DE PAGE
    footer = Table([[
        Paragraph(f'<font size="9" color="#94a3b8">Facture generee par SalesIQ — {datetime.now().strftime("%d/%m/%Y a %H:%M")}</font>', styles['Normal']),
        Paragraph(f'<font size="9" color="#94a3b8">{num_facture}</font>', styles['Normal']),
    ]], colWidths=[12*cm, 5*cm])
    footer.setStyle(TableStyle([
        ('LINEABOVE',(0,0),(-1,0),1,colors.HexColor('#e2e8f0')),
        ('ALIGN',(1,0),(1,0),'RIGHT'),
        ('PADDING',(0,0),(-1,-1),6),
    ]))
    elements.append(footer)

    doc.build(elements)
    output.seek(0)
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name=f'{num_facture}.pdf')

@app.route('/factures/<int:fid>/delete', methods=['DELETE'])
@login_required
def delete_facture(fid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM sales WHERE fichier_id=?', (fid,))
    conn.execute('DELETE FROM fichiers WHERE id=? AND user_id=?', (fid, session['user_id']))
    conn.commit(); conn.close()
    return jsonify({'success': True})

# ── CARTE ──
@app.route('/carte')
@login_required
def carte():
    fid  = request.args.get('fichier_id')
    conn = sqlite3.connect(DB_PATH)
    query = 'SELECT s.* FROM sales s JOIN fichiers f ON s.fichier_id=f.id WHERE f.user_id=?'
    params = [session['user_id']]
    if fid: query += ' AND s.fichier_id=?'; params.append(fid)
    df = pd.read_sql(query, conn, params=params); conn.close()
    if df.empty: return jsonify([])
    pv = df.groupby('ville').agg(ca=('montant','sum'), quantite=('quantite','sum'),
         nb_transactions=('id','count'), benefice=('benefice','sum')).reset_index().sort_values('ca', ascending=False)
    pv['ca'] = pv['ca'].round(0); pv['benefice'] = pv['benefice'].round(0)
    total_ca = pv['ca'].sum()
    pv['pct'] = (pv['ca'] / total_ca * 100).round(1)
    return jsonify(pv.to_dict('records'))

# ── PREVISIONS ──
@app.route('/previsions')
@login_required
def previsions():
    fid  = request.args.get('fichier_id')
    conn = sqlite3.connect(DB_PATH)
    query = 'SELECT s.* FROM sales s JOIN fichiers f ON s.fichier_id=f.id WHERE f.user_id=?'
    params = [session['user_id']]
    if fid: query += ' AND s.fichier_id=?'; params.append(fid)
    df = pd.read_sql(query, conn, params=params); conn.close()
    if df.empty: return jsonify({'error': 'Aucune donnee'}), 400
    df['date_dt'] = pd.to_datetime(df['date'], errors='coerce')
    df['mois']    = df['date_dt'].dt.to_period('M').astype(str)
    pm = df.groupby('mois').agg(ca=('montant','sum'), quantite=('quantite','sum'),
         benefice=('benefice','sum')).reset_index().sort_values('mois')
    if len(pm) < 2: return jsonify({'error': 'Minimum 2 mois requis'}), 400
    vals = pm['ca'].tolist(); n = len(vals)
    mx = (n-1)/2; my = sum(vals)/n
    num = sum((i-mx)*(vals[i]-my) for i in range(n))
    den = sum((i-mx)**2 for i in range(n))
    pente = num/den if den != 0 else 0
    intercept = my - pente*mx
    base = sum(vals[-2:])/2
    from pandas import Period
    periode = Period(pm.iloc[-1]['mois'], 'M')
    mois_f  = [str(periode+i) for i in range(1,4)]
    prev_ca = [round(0.6*(intercept+pente*(n+i-1))+0.4*base, 0) for i in range(1,4)]
    variation = (vals[-1]-vals[0])/vals[0]*100 if vals[0] != 0 else 0
    return jsonify({
        'historique': {'mois':pm['mois'].tolist(), 'ca':[round(v,0) for v in vals],
                       'quantite':pm['quantite'].tolist(), 'benefice':[round(v,0) for v in pm['benefice'].tolist()]},
        'previsions': {'mois':mois_f, 'ca':prev_ca},
        'tendance':   'hausse' if pente>0 else 'baisse' if pente<0 else 'stable',
        'variation':  round(variation,1),
        'meilleur_mois': pm.loc[pm['ca'].idxmax(),'mois'],
        'pire_mois':     pm.loc[pm['ca'].idxmin(),'mois'],
    })

# ── EXPORTS ──
@app.route('/export/excel')
@login_required
def export_excel():
    fid   = request.args.get('fichier_id')
    stats = get_stats(fichier_id=fid, user_id=session['user_id'])
    if not stats: return jsonify({'error': 'Aucune donnee'}), 404
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output)
    ft = wb.add_format({'bold':True,'font_color':'#FFF','bg_color':'#2563eb','align':'center','font_size':13})
    fh = wb.add_format({'bold':True,'font_color':'#FFF','bg_color':'#1e40af','border':1})
    fn = wb.add_format({'num_format':'#,##0','border':1})
    fm = wb.add_format({'num_format':'#,##0 FCFA','border':1})
    fx = wb.add_format({'border':1})
    def sheet(name, headers, rows_data):
        ws = wb.add_worksheet(name)
        ws.set_column(0, len(headers)-1, 20)
        ws.merge_range(0,0,0,len(headers)-1, name.upper(), ft)
        for i,h in enumerate(headers): ws.write(1,i,h,fh)
        for r,row in enumerate(rows_data):
            for c,val in enumerate(row):
                fmt = fm if isinstance(val,float) and c>0 else fn if isinstance(val,(int,float)) else fx
                ws.write(r+2,c,val,fmt)
    k = stats['kpis']
    ws1 = wb.add_worksheet('Resume')
    ws1.set_column('A:B',28)
    ws1.merge_range('A1:B1','RAPPORT DE VENTES',ft)
    for i,(label,val) in enumerate([("Chiffre d'Affaires",k['total_ca']),('Benefice',k['total_benefice']),
        ('Marge %',round(k['marge_pct'],1)),('Unites',k['total_ventes']),('Transactions',k['nb_transactions']),
        ('Top Produit',k['top_produit'])]):
        ws1.write(i+2,0,label); ws1.write(i+2,1,val)
    sheet('Par Produit',['Produit','Quantite','CA','Benefice'],
          [[r['produit'],r['quantite'],r['ca'],r['benefice']] for r in stats['par_produit']])
    sheet('Par Ville',['Ville','Quantite','CA'],
          [[r['ville'],r['quantite'],r['ca']] for r in stats['par_ville']])
    wb.close(); output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='rapport_ventes.xlsx')

@app.route('/export/pdf')
@login_required
def export_pdf():
    fid   = request.args.get('fichier_id')
    stats = get_stats(fichier_id=fid, user_id=session['user_id'])
    if not stats: return jsonify({'error': 'Aucune donnee'}), 404
    output = io.BytesIO()
    doc    = SimpleDocTemplate(output, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    st = ParagraphStyle('t', parent=styles['Title'], fontSize=20, textColor=colors.HexColor('#1a1f2e'), alignment=TA_CENTER)
    sh = ParagraphStyle('h', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#2563eb'), spaceBefore=12)
    elements = []
    k = stats['kpis']
    elements.append(Paragraph('Rapport de Ventes', st))
    elements.append(Paragraph(f"Genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.4*cm))
    elements.append(Paragraph('Indicateurs Cles', sh))
    kd = [['Indicateur','Valeur'],
          ["Chiffre d'Affaires",f"{k['total_ca']:,.0f} FCFA"],
          ['Benefice',f"{k['total_benefice']:,.0f} FCFA"],
          ['Marge',f"{k['marge_pct']:.1f}%"],
          ['Unites Vendues',f"{k['total_ventes']:,}"],
          ['Top Produit',k['top_produit']]]
    t = Table(kd, colWidths=[9*cm,8*cm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2563eb')),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),0.5,colors.grey),('PADDING',(0,0),(-1,-1),6),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f4ff'),colors.white])]))
    elements.append(t)
    doc.build(elements); output.seek(0)
    return send_file(output, mimetype='application/pdf', as_attachment=True, download_name='rapport_ventes.pdf')

if __name__ == '__main__':
    print("Demarrage de SalesIQ...")
    init_db()
    print("Base de donnees OK")
    print("Login: admin / admin123")
    print("Ouvre http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)