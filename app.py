import os
import random
import sqlite3
import string
import smtplib
from email.message import EmailMessage
from pathlib import Path
import webbrowser
import threading
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "hobbypall.db"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "proiectul_meu_super_secret_hobbypall_2026")
app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "static" / "uploads" / "avatars")
app.config["EVENT_UPLOAD_FOLDER"] = str(BASE_DIR / "static" / "uploads" / "events")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["EVENT_UPLOAD_FOLDER"], exist_ok=True)

EVENT_TYPES = [
    "Sport",
    "Social",
    "Gaming",
    "Artă",
    "Muzică",
    "Lectură",
    "Outdoor",
    "Voluntariat",
    "Online",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row):
    return dict(row) if row else None


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as conn:
        user = conn.execute("SELECT * FROM utilizatori WHERE id_utilizator = ?", (user_id,)).fetchone()
    if not user:
        session.clear()
        return None
    return row_to_dict(user)


def sync_avatar_session(user):
    if user:
        session["avatar_type"] = user.get("avatar_type") or "emoji"
        session["avatar_url"] = user.get("avatar_url") or "🐼"


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS utilizatori (
                id_utilizator INTEGER PRIMARY KEY AUTOINCREMENT,
                nume TEXT NOT NULL,
                prenume TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                parola TEXT NOT NULL,
                varsta INTEGER NOT NULL,
                sex TEXT NOT NULL,
                admin INTEGER NOT NULL DEFAULT 0,
                confirmat INTEGER NOT NULL DEFAULT 1,
                avatar_type TEXT NOT NULL DEFAULT 'emoji',
                avatar_url TEXT NOT NULL DEFAULT '🐼',
                creat_la TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS evenimente (
                id_eveniment INTEGER PRIMARY KEY AUTOINCREMENT,
                titlu TEXT NOT NULL,
                descriere TEXT NOT NULL,
                tip TEXT NOT NULL,
                locatie TEXT NOT NULL,
                data_ora TEXT NOT NULL,
                durata_minute INTEGER NOT NULL,
                data_limita_inscriere TEXT NOT NULL,
                varsta_min INTEGER,
                varsta_max INTEGER,
                id_organizator INTEGER NOT NULL,
                nr_maxim_participanti INTEGER,
                imagine_url TEXT,
                creat_la TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_organizator) REFERENCES utilizatori(id_utilizator) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS inscrieri (
                id_inscriere INTEGER PRIMARY KEY AUTOINCREMENT,
                id_utilizator INTEGER NOT NULL,
                id_eveniment INTEGER NOT NULL,
                creat_la TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (id_utilizator, id_eveniment),
                FOREIGN KEY (id_utilizator) REFERENCES utilizatori(id_utilizator) ON DELETE CASCADE,
                FOREIGN KEY (id_eveniment) REFERENCES evenimente(id_eveniment) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS intrebari (
                id_intrebare INTEGER PRIMARY KEY AUTOINCREMENT,
                id_eveniment INTEGER NOT NULL,
                id_utilizator INTEGER NOT NULL,
                continut TEXT NOT NULL,
                raspuns_organizator TEXT,
                creat_la TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_eveniment) REFERENCES evenimente(id_eveniment) ON DELETE CASCADE,
                FOREIGN KEY (id_utilizator) REFERENCES utilizatori(id_utilizator) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS recenzii (
                id_recenzie INTEGER PRIMARY KEY AUTOINCREMENT,
                id_eveniment INTEGER NOT NULL,
                id_utilizator INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                continut TEXT NOT NULL,
                creat_la TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (id_eveniment, id_utilizator),
                FOREIGN KEY (id_eveniment) REFERENCES evenimente(id_eveniment) ON DELETE CASCADE,
                FOREIGN KEY (id_utilizator) REFERENCES utilizatori(id_utilizator) ON DELETE CASCADE
            );
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM utilizatori").fetchone()[0]
        if count == 0:
            conn.execute(
                """
                INSERT INTO utilizatori
                (nume, prenume, username, email, parola, varsta, sex, admin, confirmat, avatar_type, avatar_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Popescu",
                    "Ion",
                    "ionp",
                    "ion@example.com",
                    generate_password_hash("parola123"),
                    25,
                    "M",
                    1,
                    1,
                    "emoji",
                    "🐼",
                ),
            )
            conn.execute(
                """
                INSERT INTO evenimente
                (titlu, descriere, tip, locatie, data_ora, durata_minute, data_limita_inscriere,
                 varsta_min, varsta_max, id_organizator, nr_maxim_participanti, imagine_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Meci de Fotbal 5 la 5",
                    "Căutăm jucători pentru un meci amical de fotbal. Nivel mediu.",
                    "Sport",
                    "Teren Synthetic Arena",
                    "2026-06-15T18:00",
                    90,
                    "2026-06-14T12:00",
                    18,
                    45,
                    1,
                    10,
                    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=60",
                ),
            )
            conn.execute(
                """
                INSERT INTO evenimente
                (titlu, descriere, tip, locatie, data_ora, durata_minute, data_limita_inscriere,
                 varsta_min, varsta_max, id_organizator, nr_maxim_participanti, imagine_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Seară de Board Games",
                    "Catan, Ticket to Ride și multe altele. Veniți cu voie bună!",
                    "Social",
                    "Ludic Cafe",
                    "2026-06-20T19:00",
                    180,
                    "2026-06-19T20:00",
                    16,
                    99,
                    1,
                    8,
                    "https://images.unsplash.com/photo-1610890716171-6b1bb98ffd09?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=60",
                ),
            )
            conn.execute("INSERT INTO inscrieri (id_utilizator, id_eveniment) VALUES (1, 1)")
            conn.execute(
                """
                INSERT INTO intrebari (id_eveniment, id_utilizator, continut, raspuns_organizator)
                VALUES (1, 1, 'Se joacă dacă plouă?', 'Da, terenul este acoperit.')
                """
            )


def event_query(extra_where="", params=(), sortare="data_ora"):
    allowed_sort = {
        "data_ora": "e.data_ora",
        "tip": "e.tip",
        "locatie": "e.locatie",
    }
    order_by = allowed_sort.get(sortare, "e.data_ora")
    sql = f"""
        SELECT e.*, u.username AS organizator_username,
               COUNT(i.id_inscriere) AS locuri_ocupate
        FROM evenimente e
        JOIN utilizatori u ON u.id_utilizator = e.id_organizator
        LEFT JOIN inscrieri i ON i.id_eveniment = e.id_eveniment
        WHERE 1 = 1 {extra_where}
        GROUP BY e.id_eveniment
        ORDER BY {order_by} ASC
    """
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    events = [row_to_dict(row) for row in rows]
    for event in events:
        max_participants = event.get("nr_maxim_participanti")
        event["este_plin"] = max_participants is not None and event["locuri_ocupate"] >= max_participants
    return events


def send_reset_email(to_email, new_password):
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False

    message = EmailMessage()
    message["Subject"] = "HobbyPall - parolă nouă"
    message["From"] = os.environ.get("SMTP_FROM", "noreply@hobbypall.local")
    message["To"] = to_email
    message.set_content(f"Noua ta parolă HobbyPall este: {new_password}")

    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    with smtplib.SMTP(host, port) as server:
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(message)
    return True


@app.route("/")
def index():
    user = current_user()
    user_id = user["id_utilizator"] if user else None
    filtru = request.args.get("filtru")
    sortare = request.args.get("sortare", "data_ora")
    cautare = (request.args.get("q") or "").strip()
    titru_sectiune = "Evenimente"

    where = ""
    params = []
    if filtru == "create" and user_id:
        where += " AND e.id_organizator = ?"
        params.append(user_id)
        titru_sectiune = "Organizate de mine"
    elif filtru == "particip" and user_id:
        where += " AND e.id_eveniment IN (SELECT id_eveniment FROM inscrieri WHERE id_utilizator = ?)"
        params.append(user_id)
        titru_sectiune = "Particip"

    if cautare:
        like = f"%{cautare}%"
        where += " AND (e.titlu LIKE ? OR e.descriere LIKE ? OR e.tip LIKE ? OR e.locatie LIKE ?)"
        params.extend([like, like, like, like])
        titru_sectiune = f'Rezultate pentru "{cautare}"'

    evenimente = event_query(where, params, sortare)
    return render_template(
        "index.html",
        evenimente=evenimente,
        titru_sectiune=titru_sectiune,
        sortare_curenta=sortare,
        cautare=cautare,
    )


@app.route("/evenimente/mine")
def evenimente_mine():
    if not current_user():
        flash("Trebuie să fii autentificat.", "error")
        return redirect(url_for("login"))
    return redirect(url_for("index", filtru="create"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO utilizatori
                    (nume, prenume, username, email, parola, varsta, sex, admin, confirmat, avatar_type, avatar_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 'emoji', ?)
                    """,
                    (
                        request.form.get("nume", "").strip(),
                        request.form.get("prenume", "").strip(),
                        request.form.get("username", "").strip(),
                        request.form.get("email", "").strip().lower(),
                        generate_password_hash(request.form.get("parola", "")),
                        int(request.form.get("varsta") or 0),
                        request.form.get("sex", ""),
                        "🐼",
                    ),
                )
            flash("Cont creat și confirmat. Te poți autentifica.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Emailul sau username-ul există deja.", "error")
        except ValueError:
            flash("Vârsta trebuie să fie un număr valid.", "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identificator = request.form.get("email", "").strip().lower()
        parola = request.form.get("parola", "")
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM utilizatori WHERE lower(email) = ? OR lower(username) = ?",
                (identificator, identificator),
            ).fetchone()

        if not user or not check_password_hash(user["parola"], parola):
            flash("Email/username sau parolă incorectă.", "error")
        elif not user["confirmat"]:
            flash("Contul nu este confirmat.", "error")
        else:
            user_dict = row_to_dict(user)
            session["user_id"] = user["id_utilizator"]
            session["username"] = user["username"]
            session["este_admin"] = bool(user["admin"])
            sync_avatar_session(user_dict)
            flash(f"Salut, {user['nume']} {user['prenume']}!", "success")
            return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Deconectat.", "info")
    return redirect(url_for("index"))


@app.route("/profil")
def profil():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    with get_db() as conn:
        nr_create = conn.execute(
            "SELECT COUNT(*) FROM evenimente WHERE id_organizator = ?", (user["id_utilizator"],)
        ).fetchone()[0]
        nr_participari = conn.execute(
            "SELECT COUNT(*) FROM inscrieri WHERE id_utilizator = ?", (user["id_utilizator"],)
        ).fetchone()[0]
    return render_template("profil.html", user=user, nr_create=nr_create, nr_participari=nr_participari)


@app.route("/profil/update-avatar", methods=["POST"])
def update_avatar():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    avatar_type = user["avatar_type"]
    avatar_url = user["avatar_url"]
    selected_emoji = request.form.get("emoji")
    if selected_emoji:
        avatar_type = "emoji"
        avatar_url = selected_emoji
        flash("Avatar actualizat.", "success")
    elif "avatar_file" in request.files:
        file = request.files["avatar_file"]
        if file and file.filename:
            filename = secure_filename(f"user_{user['id_utilizator']}_{file.filename}")
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)
            avatar_type = "image"
            avatar_url = url_for("static", filename=f"uploads/avatars/{filename}")
            flash("Poza de profil a fost actualizată.", "success")

    with get_db() as conn:
        conn.execute(
            "UPDATE utilizatori SET avatar_type = ?, avatar_url = ? WHERE id_utilizator = ?",
            (avatar_type, avatar_url, user["id_utilizator"]),
        )
    user["avatar_type"] = avatar_type
    user["avatar_url"] = avatar_url
    sync_avatar_session(user)
    return redirect(url_for("profil"))


@app.route("/profil/update-details", methods=["POST"])
def update_details():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE utilizatori
                SET nume = ?, prenume = ?, email = ?, varsta = ?, sex = ?
                WHERE id_utilizator = ?
                """,
                (
                    request.form.get("nume", "").strip(),
                    request.form.get("prenume", "").strip(),
                    request.form.get("email", "").strip().lower(),
                    int(request.form.get("varsta") or 0),
                    request.form.get("sex", ""),
                    user["id_utilizator"],
                ),
            )
        flash("Informații salvate.", "success")
    except sqlite3.IntegrityError:
        flash("Emailul este deja folosit de alt cont.", "error")
    except ValueError:
        flash("Vârsta trebuie să fie validă.", "error")
    return redirect(url_for("profil"))


@app.route("/profil/schimba-parola", methods=["GET", "POST"])
def schimba_parola():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if request.method == "POST":
        parola_actuala = request.form.get("parola_actuala", "")
        parola_noua = request.form.get("parola_noua", "")
        confirmare = request.form.get("parola_noua_confirmare", "")
        if not check_password_hash(user["parola"], parola_actuala):
            flash("Parola actuală nu este corectă.", "error")
        elif len(parola_noua) < 6:
            flash("Parola nouă trebuie să aibă minim 6 caractere.", "error")
        elif parola_noua != confirmare:
            flash("Parolele noi nu coincid.", "error")
        else:
            with get_db() as conn:
                conn.execute(
                    "UPDATE utilizatori SET parola = ? WHERE id_utilizator = ?",
                    (generate_password_hash(parola_noua), user["id_utilizator"]),
                )
            flash("Parola a fost schimbată.", "success")
            return redirect(url_for("profil"))
    return render_template("schimba_parola.html")


@app.route("/recuperare-parola", methods=["GET", "POST"])
def recuperare_parola():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        with get_db() as conn:
            user = conn.execute("SELECT * FROM utilizatori WHERE lower(email) = ?", (email,)).fetchone()
            if not user:
                flash("Nu există un cont cu acest email.", "error")
                return render_template("recuperare_parola.html")

            new_password = "".join(random.choices(string.ascii_letters + string.digits, k=10))
            conn.execute(
                "UPDATE utilizatori SET parola = ? WHERE id_utilizator = ?",
                (generate_password_hash(new_password), user["id_utilizator"]),
            )

        try:
            email_sent = send_reset_email(email, new_password)
            if email_sent:
                flash("Ți-am trimis pe email noua parolă.", "success")
                return redirect(url_for("login"))
            flash("Emailul nu este configurat. Am afișat parola nouă mai jos.", "info")
            return render_template("recuperare_parola.html", generated_password=new_password)
        except Exception:
            flash("SMTP a eșuat. Am afișat parola nouă mai jos.", "error")
            return render_template("recuperare_parola.html", generated_password=new_password)
    return render_template("recuperare_parola.html")


@app.route("/profil/sterge-cont", methods=["POST"])
def sterge_cont():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    parola = request.form.get("parola_confirmare", "")
    if not check_password_hash(user["parola"], parola):
        flash("Parola nu este corectă. Contul nu a fost șters.", "error")
        return redirect(url_for("profil"))
    with get_db() as conn:
        conn.execute("DELETE FROM utilizatori WHERE id_utilizator = ?", (user["id_utilizator"],))
    session.clear()
    flash("Contul și datele asociate au fost șterse.", "success")
    return redirect(url_for("index"))


@app.route("/eveniment/nou", methods=["GET", "POST"])
def creeaza_eveniment():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if request.method == "POST":
        imagine_url = None
        file = request.files.get("imagine")
        if file and file.filename:
            filename = secure_filename(f"event_{user['id_utilizator']}_{file.filename}")
            filepath = os.path.join(app.config["EVENT_UPLOAD_FOLDER"], filename)
            file.save(filepath)
            imagine_url = url_for("static", filename=f"uploads/events/{filename}")

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO evenimente
                (titlu, descriere, tip, locatie, data_ora, durata_minute, data_limita_inscriere,
                 varsta_min, varsta_max, id_organizator, nr_maxim_participanti, imagine_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.form.get("titlu", "").strip(),
                    request.form.get("descriere", "").strip(),
                    request.form.get("tip", ""),
                    request.form.get("locatie", "").strip(),
                    request.form.get("data_ora", ""),
                    int(request.form.get("durata_minute") or 0),
                    request.form.get("data_limita_inscriere", ""),
                    int(request.form["varsta_min"]) if request.form.get("varsta_min") else None,
                    int(request.form["varsta_max"]) if request.form.get("varsta_max") else None,
                    user["id_utilizator"],
                    int(request.form["nr_maxim_participanti"]) if request.form.get("nr_maxim_participanti") else None,
                    imagine_url,
                ),
            )
        flash("Eveniment creat.", "success")
        return redirect(url_for("index"))
    return render_template("creeaza_eveniment.html", event_types=EVENT_TYPES)


@app.route("/eveniment/<int:id_eveniment>", methods=["GET", "POST"])
def detalii_eveniment(id_eveniment):
    user = current_user()
    with get_db() as conn:
        event = conn.execute(
            """
            SELECT e.*, u.username AS organizator_username, u.nume AS organizator_nume,
                   u.prenume AS organizator_prenume,
                   (SELECT COUNT(*) FROM inscrieri WHERE id_eveniment = e.id_eveniment) AS locuri_ocupate
            FROM evenimente e
            JOIN utilizatori u ON u.id_utilizator = e.id_organizator
            WHERE e.id_eveniment = ?
            """,
            (id_eveniment,),
        ).fetchone()
        if not event:
            flash("Evenimentul nu există.", "error")
            return redirect(url_for("index"))

        event = row_to_dict(event)
        if request.method == "POST":
            if not user:
                return redirect(url_for("login"))
            if user["id_utilizator"] == event["id_organizator"]:
                flash("Organizatorul nu poate adăuga întrebări propriului eveniment.", "error")
            else:
                continut = request.form.get("continut", "").strip()
                if continut:
                    conn.execute(
                        "INSERT INTO intrebari (id_eveniment, id_utilizator, continut) VALUES (?, ?, ?)",
                        (id_eveniment, user["id_utilizator"], continut),
                    )
                    flash("Întrebarea a fost trimisă.", "success")
            return redirect(url_for("detalii_eveniment", id_eveniment=id_eveniment))

        intrebari = conn.execute(
            """
            SELECT q.*, u.username, u.nume, u.prenume
            FROM intrebari q
            JOIN utilizatori u ON u.id_utilizator = q.id_utilizator
            WHERE q.id_eveniment = ?
            ORDER BY q.creat_la DESC
            """,
            (id_eveniment,),
        ).fetchall()
        participanti = conn.execute(
            """
            SELECT u.nume, u.prenume, u.varsta, u.sex, u.email, i.creat_la
            FROM inscrieri i
            JOIN utilizatori u ON u.id_utilizator = i.id_utilizator
            WHERE i.id_eveniment = ?
            ORDER BY i.creat_la DESC
            """,
            (id_eveniment,),
        ).fetchall()
        recenzii = conn.execute(
            """
            SELECT r.*, u.username, u.nume, u.prenume
            FROM recenzii r
            JOIN utilizatori u ON u.id_utilizator = r.id_utilizator
            WHERE r.id_eveniment = ?
            ORDER BY r.creat_la DESC
            """,
            (id_eveniment,),
        ).fetchall()
        este_inscris = False
        are_recenzie = False
        if user:
            este_inscris = (
                conn.execute(
                    "SELECT 1 FROM inscrieri WHERE id_eveniment = ? AND id_utilizator = ?",
                    (id_eveniment, user["id_utilizator"]),
                ).fetchone()
                is not None
            )
            are_recenzie = (
                conn.execute(
                    "SELECT 1 FROM recenzii WHERE id_eveniment = ? AND id_utilizator = ?",
                    (id_eveniment, user["id_utilizator"]),
                ).fetchone()
                is not None
            )

    event["este_plin"] = (
        event["nr_maxim_participanti"] is not None
        and event["locuri_ocupate"] >= event["nr_maxim_participanti"]
    )
    este_organizator = bool(user and event["id_organizator"] == user["id_utilizator"])
    return render_template(
        "detalii_eveniment.html",
        eveniment=event,
        intrebari=[row_to_dict(row) for row in intrebari],
        participanti=[row_to_dict(row) for row in participanti],
        recenzii=[row_to_dict(row) for row in recenzii],
        este_organizator=este_organizator,
        este_inscris=este_inscris,
        are_recenzie=are_recenzie,
    )


@app.route("/eveniment/<int:id_eveniment>/editeaza", methods=["GET", "POST"])
def editeaza_eveniment(id_eveniment):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    with get_db() as conn:
        event = conn.execute("SELECT * FROM evenimente WHERE id_eveniment = ?", (id_eveniment,)).fetchone()
        if not event:
            flash("Evenimentul nu există.", "error")
            return redirect(url_for("index"))
        if event["id_organizator"] != user["id_utilizator"]:
            flash("Doar organizatorul poate edita evenimentul.", "error")
            return redirect(url_for("detalii_eveniment", id_eveniment=id_eveniment))

        if request.method == "POST":
            imagine_url = event["imagine_url"]
            file = request.files.get("imagine")
            if file and file.filename:
                filename = secure_filename(f"event_{id_eveniment}_{file.filename}")
                filepath = os.path.join(app.config["EVENT_UPLOAD_FOLDER"], filename)
                file.save(filepath)
                imagine_url = url_for("static", filename=f"uploads/events/{filename}")

            conn.execute(
                """
                UPDATE evenimente
                SET titlu = ?, descriere = ?, tip = ?, locatie = ?, data_ora = ?, durata_minute = ?,
                    data_limita_inscriere = ?, varsta_min = ?, varsta_max = ?,
                    nr_maxim_participanti = ?, imagine_url = ?
                WHERE id_eveniment = ?
                """,
                (
                    request.form.get("titlu", "").strip(),
                    request.form.get("descriere", "").strip(),
                    request.form.get("tip", ""),
                    request.form.get("locatie", "").strip(),
                    request.form.get("data_ora", ""),
                    int(request.form.get("durata_minute") or 0),
                    request.form.get("data_limita_inscriere", ""),
                    int(request.form["varsta_min"]) if request.form.get("varsta_min") else None,
                    int(request.form["varsta_max"]) if request.form.get("varsta_max") else None,
                    int(request.form["nr_maxim_participanti"]) if request.form.get("nr_maxim_participanti") else None,
                    imagine_url,
                    id_eveniment,
                ),
            )
            flash("Eveniment actualizat.", "success")
            return redirect(url_for("detalii_eveniment", id_eveniment=id_eveniment))
    return render_template("editeaza_eveniment.html", eveniment=row_to_dict(event), event_types=EVENT_TYPES)


@app.route("/eveniment/<int:id_eveniment>/sterge", methods=["POST"])
def sterge_eveniment(id_eveniment):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    with get_db() as conn:
        event = conn.execute("SELECT * FROM evenimente WHERE id_eveniment = ?", (id_eveniment,)).fetchone()
        if not event:
            flash("Evenimentul nu există.", "error")
            return redirect(url_for("index"))
        if event["id_organizator"] != user["id_utilizator"]:
            flash("Doar organizatorul poate șterge evenimentul.", "error")
            return redirect(url_for("detalii_eveniment", id_eveniment=id_eveniment))
        conn.execute("DELETE FROM evenimente WHERE id_eveniment = ?", (id_eveniment,))
    flash("Evenimentul a fost șters.", "success")
    return redirect(url_for("index", filtru="create"))


@app.route("/participa/<int:id_eveniment>")
def participa(id_eveniment):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    with get_db() as conn:
        event = conn.execute(
            """
            SELECT e.*, (SELECT COUNT(*) FROM inscrieri WHERE id_eveniment = e.id_eveniment) AS locuri_ocupate
            FROM evenimente e WHERE e.id_eveniment = ?
            """,
            (id_eveniment,),
        ).fetchone()
        if not event:
            flash("Evenimentul nu există.", "error")
            return redirect(url_for("index"))
        if event["id_organizator"] == user["id_utilizator"]:
            flash("Nu te poți înscrie la propriul eveniment.", "error")
        elif event["nr_maxim_participanti"] is not None and event["locuri_ocupate"] >= event["nr_maxim_participanti"]:
            flash("Evenimentul este complet.", "error")
        elif event["varsta_min"] is not None and user["varsta"] < event["varsta_min"]:
            flash("Nu îndeplinești vârsta minimă recomandată.", "error")
        elif event["varsta_max"] is not None and user["varsta"] > event["varsta_max"]:
            flash("Nu te încadrezi în intervalul de vârstă recomandat.", "error")
        else:
            try:
                conn.execute(
                    "INSERT INTO inscrieri (id_utilizator, id_eveniment) VALUES (?, ?)",
                    (user["id_utilizator"], id_eveniment),
                )
                flash("Te-ai înscris. Datele tale au fost preluate automat din profil.", "success")
            except sqlite3.IntegrityError:
                flash("Ești deja înscris la acest eveniment.", "info")
    return redirect(url_for("detalii_eveniment", id_eveniment=id_eveniment))


@app.route("/intrebare/<int:id_intrebare>/raspunde", methods=["POST"])
def raspunde_intrebare(id_intrebare):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    id_eveniment = int(request.form.get("id_eveniment") or 0)
    raspuns = request.form.get("raspuns_organizator", "").strip()
    with get_db() as conn:
        event = conn.execute("SELECT * FROM evenimente WHERE id_eveniment = ?", (id_eveniment,)).fetchone()
        if event and event["id_organizator"] == user["id_utilizator"] and raspuns:
            conn.execute(
                "UPDATE intrebari SET raspuns_organizator = ? WHERE id_intrebare = ? AND id_eveniment = ?",
                (raspuns, id_intrebare, id_eveniment),
            )
            flash("Răspunsul a fost salvat.", "success")
        else:
            flash("Nu poți răspunde la această întrebare.", "error")
    return redirect(url_for("detalii_eveniment", id_eveniment=id_eveniment))


@app.route("/eveniment/<int:id_eveniment>/recenzie", methods=["POST"])
def adauga_recenzie(id_eveniment):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    rating = int(request.form.get("rating") or 0)
    continut = request.form.get("continut", "").strip()
    with get_db() as conn:
        event = conn.execute("SELECT * FROM evenimente WHERE id_eveniment = ?", (id_eveniment,)).fetchone()
        inscris = conn.execute(
            "SELECT 1 FROM inscrieri WHERE id_eveniment = ? AND id_utilizator = ?",
            (id_eveniment, user["id_utilizator"]),
        ).fetchone()
        if not event or event["id_organizator"] == user["id_utilizator"] or not inscris:
            flash("Doar participanții pot lăsa recenzii.", "error")
        elif not continut or rating < 1 or rating > 5:
            flash("Recenzia trebuie să conțină text și rating între 1 și 5.", "error")
        else:
            try:
                conn.execute(
                    "INSERT INTO recenzii (id_eveniment, id_utilizator, rating, continut) VALUES (?, ?, ?, ?)",
                    (id_eveniment, user["id_utilizator"], rating, continut),
                )
                flash("Recenzia a fost publicata.", "success")
            except sqlite3.IntegrityError:
                flash("Ai lăsat deja o recenzie pentru acest eveniment.", "info")
    return redirect(url_for("detalii_eveniment", id_eveniment=id_eveniment))


@app.route("/surpriza")
def surpriza():
    evenimente = event_query(sortare="data_ora")
    if not evenimente:
        flash("Nu există evenimente momentan.", "info")
        return redirect(url_for("index"))
    return render_template("surpriza.html", eveniment=random.choice(evenimente))


init_db()

if __name__ == "__main__":

    def _open_browser():
        url = "http://127.0.0.1:5000/"
        try:
            webbrowser.open_new(url)
        except Exception:
            pass

    threading.Timer(1.0, _open_browser).start()
    app.run(debug=True, use_reloader=False, port=5000)
