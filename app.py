import os
import webbrowser
from flask import Flask, render_template, request, redirect, url_for, flash, session
from supabase import create_client, Client
from dotenv import load_dotenv
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "proiectul_meu_super_secret_hobbypall_2026")

# Conexiunea oficială cu Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ ATENȚIE: Credențialele Supabase lipsesc din fișierul .env!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 1. PAGINA HOME (INDEX) - Cu Verificare Locuri și Ordonare Recentă
# ==========================================
@app.route('/')
def index():
    evenimente = []
    titru_sectiune = "🌐 Toate Evenimentele Disponibile"
    
    user_id = session.get('user_id')
    filtru = request.args.get('filtru') 
    sortare = request.args.get('sortare', 'data_ora') 

    if sortare not in ['data_ora', 'tip', 'locatie']:
        sortare = 'data_ora'

    try:
        # 1. Preluăm evenimentele în funcție de filtru
        if user_id and filtru == 'create':
            # .order('id_eveniment', descending=True) asigură afișarea de la cel mai recent la cel mai vechi
            response = supabase.table('evenimente').select("*").eq('id_organizator', user_id).order('id_eveniment', desc=True).execute()
            evenimente = response.data
            titru_sectiune = "👑 Evenimentele Organizate de Mine"
            
        elif user_id and filtru == 'particip':
            response_inscrieri = supabase.table('inscrieri').select('evenimente(*)').eq('id_utilizator', user_id).execute()
            if response_inscrieri.data:
                evenimente = [ins['evenimente'] for ins in response_inscrieri.data if ins.get('evenimente')]
                evenimente = sorted(evenimente, key=lambda x: x.get(sortare) if x.get(sortare) is not None else "")
            titru_sectiune = "📋 Evenimentele la care participi"
            
        else:
            response = supabase.table('evenimente').select("*").order(sortare).execute()
            evenimente = response.data
            titru_sectiune = "🌐 Toate Evenimentele Disponibile"

        # 2. Calculăm dinamic locurile ocupate pentru fiecare eveniment afișat
        for ev in evenimente:
            id_ev = ev['id_eveniment']
            res_nr = supabase.table('inscrieri').select('id_utilizator', count='exact').eq('id_eveniment', id_ev).execute()
            
            nr_actual = res_nr.count if res_nr.count is not None else 0
            limita = ev.get('nr_maxim_participanti')

            ev['locuri_ocupate'] = nr_actual
            
            if limita and nr_actual >= limita:
                ev['este_plin'] = True
            else:
                ev['este_plin'] = False

    except Exception as e:
        print(f"Eroare la citirea datelor: {e}")
        evenimente = []
        
    return render_template('index.html', evenimente=evenimente, titru_sectiune=titru_sectiune, sortare_curenta=sortare)

@app.route('/evenimente/mine')
def evenimente_mine():
    if not session.get('user_id'):
        flash("Trebuie să fii autentificat pentru a vedea evenimentele tale.", "error")
        return redirect(url_for('login'))
    return redirect(url_for('index', filtru='create'))

# ==========================================
# 2. PAGINA ȘI LOGICA DE ÎNREGISTRARE
# ==========================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nume = request.form.get('nume')
        prenume = request.form.get('prenume')
        username = request.form.get('username')
        email = request.form.get('email')
        parola = request.form.get('parola') 
        varsta = int(request.form.get('varsta'))
        sex = request.form.get('sex')

        try:
            date_utilizator = {
                "nume": nume,
                "prenume": prenume,
                "username": username,
                "email": email,
                "parola": parola,
                "varsta": varsta,
                "sex": sex,
                "confirmat": True,
                "admin": False
            }
            
            supabase.table('utilizatori').insert(date_utilizator).execute()
            flash("Contul a fost creat cu succes! Te poți autentifica.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f"Eroare la înregistrare: {e}", "error")
            return render_template('register.html')

    return render_template('register.html')

# ==========================================
# 3. PAGINA ȘI LOGICA DE AUTENTIFICARE
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identificator = request.form.get('email') 
        parola = request.form.get('parola')

        try:
            response = supabase.table('utilizatori')\
                .select('*')\
                .or_(f"email.eq.{identificator},username.eq.{identificator}")\
                .execute()
            
            utilizatori_gasiti = response.data

            if utilizatori_gasiti and utilizatori_gasiti[0]['parola'] == parola:
                user = utilizatori_gasiti[0]
                
                session['user_id'] = user['id_utilizator']
                session['username'] = user['username']
                session['este_admin'] = user.get('admin', False)
                
                flash(f"Bine ai revenit, {user['prenume']}!", "success")
                return redirect(url_for('index'))
            else:
                flash("Date de autentificare incorecte!", "error")
                
        except Exception as e:
            flash(f"Eroare la autentificare: {e}", "error")

    return render_template('login.html')

# ==========================================
# 4. PAGINA DE CREARE EVENIMENT (HOST)
# ==========================================
@app.route('/eveniment/nou', methods=['GET', 'POST'])
def creeaza_eveniment():
    if not session.get('user_id'):
        flash("Trebuie să fii autentificat pentru a organiza un eveniment!", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            date_eveniment = {
                "titlu": request.form.get('titlu'),
                "descriere": request.form.get('descriere'),
                "tip": request.form.get('tip'),
                "locatie": request.form.get('locatie'),
                "data_ora": request.form.get('data_ora'),
                "durata_minute": int(request.form.get('durata_minute')),
                "data_limita_inscriere": request.form.get('data_limita_inscriere'),
                "varsta_min": int(request.form.get('varsta_min')) if request.form.get('varsta_min') else None,
                "varsta_max": int(request.form.get('varsta_max')) if request.form.get('varsta_max') else None,
                "id_organizator": session.get('user_id'), 
                "nr_maxim_participanti": int(request.form.get('nr_maxim_participanti')) if request.form.get('nr_maxim_participanti') else None
            }
            supabase.table('evenimente').insert(date_eveniment).execute()
            flash("Evenimentul a fost creat cu succes!", "success")
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f"Eroare la crearea evenimentului: {e}", "error")

    return render_template('creeaza_eveniment.html')

# ==========================================
# 5. LOGICA DE DECONECTARE (LOGOUT)
# ==========================================
@app.route('/logout')
def logout():
    session.clear() 
    flash("Te-ai deconectat cu succes.", "info")
    return redirect(url_for('index'))

# ==========================================
# 6. PAGINA DE DETALII EVENIMENT - Întrebări, Răspunsuri și Participanți
# ==========================================
@app.route('/eveniment/<int:id_eveniment>', methods=['GET', 'POST'])
def detalii_eveniment(id_eveniment):
    if not session.get('user_id'):
        flash("Trebuie să fii autentificat pentru a vedea detaliile!", "error")
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    if request.method == 'POST':
        continut = request.form.get('continut')
        if continut:
            try:
                date_intrebare = {
                    "id_eveniment": id_eveniment,
                    "id_utilizator": user_id,
                    "continut": continut
                }
                supabase.table('intrebari_evenimente').insert(date_intrebare).execute()
                flash("Mesajul tău a fost trimis cu succes!", "success")
            except Exception as e:
                flash(f"Eroare la trimiterea mesajului: {e}", "error")
        return redirect(url_for('detalii_eveniment', id_eveniment=id_eveniment))

    try:
        res_ev = supabase.table('evenimente').select('*').eq('id_eveniment', id_eveniment).execute()
        if not res_ev.data:
            flash("Evenimentul nu a fost găsit!", "error")
            return redirect(url_for('index'))
        
        eveniment = res_ev.data[0]

        # Includem detaliile de profil ale autorilor întrebărilor (username, nume, prenume)
        res_intr = supabase.table('intrebari_evenimente')\
            .select('*, utilizatori(username, nume, prenume)')\
            .eq('id_eveniment', id_eveniment)\
            .order('id_intrebare', desc=False)\
            .execute()
        intrebari = res_intr.data

        # Verificăm dacă utilizatorul curent deține acest eveniment
        este_organizator = (eveniment['id_organizator'] == user_id)
        participanti = []

        # Dacă este organizator, interogăm baza de date pentru lista completă de contacte
        if este_organizator:
            res_part = supabase.table('inscrieri')\
                .select('utilizatori(nume, prenume, email, varsta)')\
                .eq('id_eveniment', id_eveniment)\
                .execute()
            
            if res_part.data:
                participanti = [p['utilizatori'] for p in res_part.data if p.get('utilizatori')]

    except Exception as e:
        flash(f"Eroare la încărcarea paginii: {e}", "error")
        return redirect(url_for('index'))

    return render_template(
        'detalii_eveniment.html', 
        eveniment=eveniment, 
        intrebari=intrebari, 
        este_organizator=este_organizator, 
        participanti=participanti
    )

# ==========================================
# 6.1 PROCESAREA RĂSPUNSULUI OFICIAL (ORGANIZATOR)
# ==========================================
@app.route('/intrebare/raspunde/<int:id_intrebare>', methods=['POST'])
def raspunde_intrebare(id_intrebare):
    user_id = session.get('user_id')
    raspuns = request.form.get('raspuns_organizator')
    id_eveniment = request.form.get('id_eveniment')

    if not user_id or not raspuns:
        flash("Acțiune neautorizată sau text lipsă!", "error")
        return redirect(url_for('index'))

    try:
        supabase.table('intrebari_evenimente')\
            .update({"raspuns_organizator": raspuns})\
            .eq('id_intrebare', id_intrebare)\
            .execute()
        flash("Răspunsul tău oficial a fost adăugat!", "success")
    except Exception as e:
        flash(f"Eroare la salvarea răspunsului: {e}", "error")

    return redirect(url_for('detalii_eveniment', id_eveniment=id_eveniment))

# ==========================================
# 7. LOGICA SIMPLĂ DE ÎNSCRIERE LA EVENIMENT (PARTICIPĂ)
# ==========================================
@app.route('/participa/<int:id_eveniment>')
def participa(id_eveniment):
    user_id = session.get('user_id')
    
    if not user_id:
        flash("Trebuie să fii autentificat pentru a participa la un eveniment!", "error")
        return redirect(url_for('login'))

    try:
        verificare = supabase.table('inscrieri')\
            .select('*')\
            .eq('id_utilizator', user_id)\
            .eq('id_eveniment', id_eveniment)\
            .execute()
            
        if verificare.data:
            flash("Ești deja înscris la acest eveniment!", "info")
            return redirect(url_for('detalii_eveniment', id_eveniment=id_eveniment))

        date_inscriere = {
            "id_utilizator": user_id,
            "id_eveniment": id_eveniment
        }
        
        supabase.table('inscrieri').insert(date_inscriere).execute()
        flash("Te-ai înscris cu succes la eveniment!", "success")
        
    except Exception as e:
        flash(f"Eroare la înscriere: {e}", "error")
        return redirect(url_for('index'))
        
    return redirect(url_for('detalii_eveniment', id_eveniment=id_eveniment))

# ==========================================
# 7.1 PAGINA DE PROFIL UTILIZATOR ȘI STATISTICI
# ==========================================
@app.route('/profil')
def profil():
    if not session.get('user_id'):
        flash("Trebuie să fii autentificat pentru a-ți vedea profilul!", "error")
        return redirect(url_for('login'))

    user_id = session.get('user_id')

    try:
        # 1. Preluăm datele complete ale utilizatorului din Supabase
        res_user = supabase.table('utilizatori').select('*').eq('id_utilizator', user_id).execute()
        if not res_user.data:
            flash("Utilizatorul nu a fost găsit!", "error")
            return redirect(url_for('index'))
        
        date_profil = res_user.data[0]

        # 2. Statistici: Numărăm câte evenimente a creat
        res_create = supabase.table('evenimente').select('id_eveniment', count='exact').eq('id_organizator', user_id).execute()
        nr_create = res_create.count if res_create.count is not None else len(res_create.data)

        # 3. Statistici: Numărăm la câte evenimente s-a înscris în tabelul 'inscrieri'
        res_participari = supabase.table('inscrieri').select('id_inscriere', count='exact').eq('id_utilizator', user_id).execute()
        nr_participari = res_participari.count if res_participari.count is not None else len(res_participari.data)

    except Exception as e:
        print(f"Eroare la încărcarea profilului: {e}")
        flash("A apărut o eroare la încărcarea profilului.", "error")
        return redirect(url_for('index'))

    return render_template('profil.html', user=date_profil, nr_create=nr_create, nr_participari=nr_participari)

# ==========================================
# 7.2 LOGICA DE SCHIMBARE A PAROLEI
# ==========================================
@app.route('/profil/schimba-parola', methods=['GET', 'POST'])
def schimba_parola():
    if not session.get('user_id'):
        flash("Trebuie să fii autentificat pentru a schimba parola!", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        parola_actuala = request.form.get('parola_actuala')
        parola_noua = request.form.get('parola_noua')
        parola_noua_confirmare = request.form.get('parola_noua_confirmare')
        user_id = session.get('user_id')

        # 1. Validare primară: coincid cele două parole noi?
        if parola_noua != parola_noua_confirmare:
            flash("Parola nouă și confirmarea nu coincid!", "error")
            return render_template('schimba_parola.html')

        try:
            # 2. Preluăm parola curentă din Supabase pentru a o verifica
            res_user = supabase.table('utilizatori').select('parola').eq('id_utilizator', user_id).execute()
            
            if res_user.data and res_user.data[0]['parola'] == parola_actuala:
                # 3. Dacă parola actuală e corectă, facem update cu cea nouă
                supabase.table('utilizatori')\
                    .update({"parola": parola_noua})\
                    .eq('id_utilizator', user_id)\
                    .execute()
                
                flash("Parola a fost modificată cu succes!", "success")
                return redirect(url_for('profil'))
            else:
                flash("Parola actuală introdusă este incorectă!", "error")
                
        except Exception as e:
            print(f"Eroare la schimbarea parolei: {e}")
            flash("A apărut o eroare neașteptată. Încearcă din nou.", "error")

    return render_template('schimba_parola.html')

# ==========================================
# 8. FUNCȚIE AJUTĂTOARE PENTRU TRIMITERE E-MAIL
# ==========================================
def trimite_email_recuperare(email_destinatar, parola_noua):
    email_expediator = os.environ.get("EMAIL_EXPEDIATOR")
    parola_aplicatie = os.environ.get("EMAIL_PAROLA_APLICATIE")

    if not email_expediator or not parola_aplicatie:
        print("⚠️ Configurația pentru trimiterea e-mailului lipsește din .env!")
        return False

    # Structurăm mesajul e-mailului
    mesaj = MIMEMultipart()
    mesaj['From'] = email_expediator
    mesaj['To'] = email_destinatar
    mesaj['Subject'] = "🔒 Resetare Parolă HobbyPall"

    corp_email = f"""
    Salutare,
    
    Am primit o cerere de resetare a parolei pentru contul tău de pe HobbyPall.
    Noua ta parolă temporară este: {parola_noua}
    Te rugăm să te autentifici folosind această parolă și să o schimbi imediat din secțiunea 'Profilul Meu' pentru siguranța contului tău.

    O zi excelentă,
    Echipa HobbyPall 🎯
    """
    mesaj.attach(MIMEText(corp_email, 'plain', 'utf-8'))

    try:
        # Ne conectăm la serverul securizat SMTP al Google (port 587)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Securizăm conexiunea
        server.login(email_expediator, parola_aplicatie)
        server.sendmail(email_expediator, email_destinatar, mesaj.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Eroare SMTP la trimiterea e-mailului: {e}")
        return False

# ==========================================
# 8.1 RUTA PENTRU SOLICITARE RECUPERARE PAROLĂ
# ==========================================
@app.route('/recuperare-parola', methods=['GET', 'POST'])
def recuperare_parola():
    if request.method == 'POST':
        email = request.form.get('email')

        try:
            # 1. Verificăm dacă e-mailul există în baza noastră de date
            res_user = supabase.table('utilizatori').select('id_utilizator').eq('email', email).execute()
            
            if res_user.data:
                user_id = res_user.data[0]['id_utilizator']
                caractere = string.ascii_letters + string.digits
                parola_aleatorie = ''.join(random.choice(caractere) for _ in range(8))
                if trimite_email_recuperare(email, parola_aleatorie):
                    supabase.table('utilizatori')\
                        .update({"parola": parola_aleatorie})\
                        .eq('id_utilizator', user_id)\
                        .execute()
                    
                    flash("O parolă nouă a fost trimisă pe adresa ta de e-mail!", "success")
                    return redirect(url_for('login'))
                else:
                    flash("A apărut o eroare la trimiterea e-mailului. Contactează administratorul.", "error")
            else:
                flash("Dacă adresa de e-mail este înregistrată, vei primi un mesaj în scurt timp.", "info")
                return redirect(url_for('login'))

        except Exception as e:
            print(f"Eroare la recuperarea parolei: {e}")
            flash("A apărut o eroare neașteptată.", "error")

    return render_template('recuperare_parola.html')

if __name__ == '__main__':
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        webbrowser.open("http://127.0.0.1:5000/")
    
    app.run(debug=True, port=5000)