import datetime
import subprocess


from flask import Flask, session, render_template, url_for, request, redirect, flash, send_from_directory, g, make_response
import PIL, random, urllib.request, urllib.error, urllib.parse
from PIL import Image, ImageOps
from cryptography.fernet import Fernet
import os.path, secrets
import os,requests, unicodedata, MySQLdb,re
from werkzeug.utils import secure_filename
from flask import json
from werkzeug.exceptions import HTTPException
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from strava_cz import (
    StravaCZ,
    AuthenticationError,
    InvalidMealTypeError,
    InsufficientBalanceError,
    StravaAPIError,
    MealType,
    OrderType
)


#TODO:

# better design
# adding compat with different canteen systems
# -1 and [] weird inconsistencies in scrapes
# add alergens
# add more images and messages

#=========================================================
#MAYBE:

#add comments
#add likes/dislikes
#add warning about speaking about the food in the comments
#add a way to delete comments

#==========================================================
#DONE:

#- fix food rating; possibly fixed, testing needed; done 
#- better foods page; done
#- change text on login page; done
#- fix navbar sticking; done
#- better division of days on the main page; done
#- add a posibility to see whether the food is already in the database when accepting new food; needs testing; done
#- fix gramatical mistake on the /foods page; done
#- add the day of the week on the main page; done
#- remove a href tag from food image when selecting; done
#- change the way debug page works; done
#- add a counter to the foods page; done
#- redesign the login page too; done
#add username to all pages in navbar when logged in; done
#make logout work; done
#make ordering work again; done
#add proper login; in progress; done
#add your rating; done
#Make it work on Pythonanywhere again
#Fixed ratings
#Add navbar to /new_food
#Add compresion for images
# /add_canteen
# storing canteen in cookies
#Add a posibility to add diferent canteens
#Change rating to hodnoceni /foods
#Add colors to the food ratings everywhere
#add canteen field to /food_edit
#/suggestions, instead created a custom email and added it to contacts
#add user counter
# change / and / debug properly with session cookie and stuff; needs testing
# make images on /foods not pass through navbar
# Change the long db outputs to only what is needed
# Add an option to see foods from other canteens in the search menu
# change blank to ""
# desoupification
# Fix the chart passing through navbar

#==========================================================
# NEEDS TESTING:

# adding full compat for iCanteen (maybe using the library for everything?); kinda done, not really for older systems
# Strava get ordered foods
# fix the contacts

#==========================================================

app = Flask(__name__)

UPLOAD_FOLDER = '/home/ubuntu/photos'
app.config['ALLOWED_EXTENSIONS'] = ['.jpg', '.jpeg', '.png']
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 4*1024 * 1024 #4MB
ALLOWED_APPS = ["kredit.exe", "login.exe","get_ordered_foods.exe", "order.exe"]
SoupStrings = [ # usde to detect and remove soups in food names
    "polevka",
    "polévka",
    "zeleňačka",
    "zelenacka",
    "česnečka",
    "cesnecka",
    "vývar",
    "vyvar",
    "kapání",
    "kapani",
    "boršč",
    "borsc",
    "šči",
    "sci",
    "pórková",
    "porkova",
    "kulajda",
    "p.",
    "nevari",
    "nevaří",
    "neni",
    "není",
    "játr. kned",
    "jatr. kned",
    "játrový kned",
    "játrové kned"
]

SuffixStrings = [
    "ovoce",
    "voda",
    "čaj",
    "caj",
    "nápoj",
    "napoj",
    "sirup",
    "mléko",
    "mleko",
]
compress_limit = 0.5 # This is the number of MB above which an image will be compressed

path_passwords = "/home/ubuntu/passwords"

app.secret_key = open(f"{path_passwords}/secret.txt",'r').read().strip()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800
)
canteen_systems = [("iCanteen / strav.nasejidelna.cz", 2),("Strava.cz", 1),("Jidelna.cz", 0),("Kuchyňka / iKuch - DATAX", 0),("OELIX - XTG Systems", 0),("Primirest / Primiapp.cz", 0)] #0 - doesn't work, 1 - testing, 2 - mostly full support


key = open(f"{path_passwords}/password.txt",'r').read().strip().encode()
cipher = Fernet(key)




@app.route('/', methods =["GET", "POST"])
def Main():

    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")

    cookie = get_canteen_id_raw()
    if not cookie:
        if request.method == "POST":
            id = request.form.get("canteen_id")
            response = make_response(redirect(f"/canteen/{id}"))
            response.set_cookie(
                "id",
                id,
                max_age= 60 * 60 * 24 * 365
            )   

            return response

        return redirect("/canteens")
    else:
        return redirect(f"/canteen/{cookie}")


def add_visit(subpage):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("INSERT INTO Visits (subpage) VALUES (%s)", (subpage,))
    db.commit()

@app.after_request
def track_visit(response):
    if request.url_rule is None:
        return response
    if request.method == "GET" and not request.path.startswith("/image") and not request.path.startswith("/favicon.ico") and not request.path.startswith("/static") and not request.path.startswith("/iCanteen") and not request.path.startswith("/strava"):
        route = request.url_rule.rule
        if route.startswith("/canteen"):
            route = request.path
        else:
            route = route.split("/<",1)[0]
        add_visit(route)
    return response

@app.route("/statistics")
def statistics():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) AS visits FROM Visits;")
    total_visits = cursor.fetchone()[0]
    cursor.execute("SELECT MONTHNAME(date) AS month, COUNT(*) AS visits FROM Visits WHERE YEAR(date) = YEAR(CURRENT_DATE) GROUP BY MONTH(date), MONTHNAME(date) ORDER BY MONTH(date);")
    monthly_stats = cursor.fetchall()
    cursor.execute("SELECT subpage, COUNT(*) AS visits FROM Visits GROUP BY subpage ORDER BY visits DESC")
    subpage_stats = cursor.fetchall()
    cursor.execute("SELECT canteen_id, COUNT(*) AS foods FROM Main GROUP BY canteen_id ORDER BY foods DESC")
    old_food_stats = cursor.fetchall()
    canteen_stats = []
    for canteen_id, foods in old_food_stats:
        canteen_stats.append((f"{canteen_id_to_name(canteen_id)} (id: {canteen_id})", foods))
    commits = subprocess.check_output(
        ["git", "-C", "/home/ubuntu/Postupicka-jidelna", "rev-list", "--count", "HEAD"]
    ).decode().strip()
    return render_template("Statistics.html", total=total_visits, monthly_stats=monthly_stats, subpage_stats = subpage_stats,canteen_stats = canteen_stats,logo = get_image_id(get_canteen_id()), commits = commits)


@app.route("/message/<message>")
def get_message(message):
    submessage = ""
    link = ""
    title = "Zpráva"
    link_text = ""
    img = "/image/Employment-Job-Application-791x1024-3681536362.png"

    match message:
        case "Food not found":
            message="Jídlo nenalezeno."
            title="Jídlo nenalezeno"
            link="/add_food"
            link_text = "Přidat ho?"
            img=get_image("Jidlo nenalezeno new")
        case "Food submitted":
            message="Děkujeme, že jste přidali jídlo."
            title = "Děkujeme"
            submessage = " Zkontrolujeme ho do jednoho týdne a přidáme ho."
            img = "/image/Added_food.jpeg"
        case "File too big":
            message="Soubor příliš velký"
            title = "Chyba :/"
            submessage = f"Soubor, který jste přidali je větší než náš {int(app.config['MAX_CONTENT_LENGTH']) / (1024*1024)} MB limit."
            img = "/image/File_too_big.jpeg"
        case "Login doesn't work":
            message = "Přihlašování v současnosti není funkční. Pokud se tento problém nevřeší do 3 dní prosím kontaktujte mě:"
            title = "Chyba :/"
            link = "/contacts"
            link_text = "kontaktovat vývojáře"
            img =get_image("Jidlo nenalezeno new")
        case _:
            submessage = "How did you even find this?"
            message = "Go get a job."

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("message.html", title = title, username=username, kredit=kredit, message=message, submessage = submessage, link = link, link_text=link_text, img = img, logo = get_image_id(get_canteen_id()))

    return render_template("message.html", title = title, message=message, submessage = submessage, link = link, link_text=link_text, img = img, logo = get_image_id(get_canteen_id()))

@app.route('/search/<food>', methods = ["GET", "POST"])
def search(food):
    db = get_db()
    mycursor = db.cursor()
    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")
    canteen_id = get_canteen_id()
    mycursor.execute("SELECT id FROM Main where name = %s and canteen_id = %s", (food, canteen_id))
    answer = mycursor.fetchone()
    if answer:
        return redirect(f"/get_food/{answer[0]}")

    mycursor.execute("SELECT id,name FROM Main WHERE (name LIKE %s OR SOUNDEX(name) = SOUNDEX(%s)) AND canteen_id = %s;", (f"%{food}%", food, canteen_id))

    answer = mycursor.fetchall()
    ret = []
    for food_id, food_name in answer:
        ret.append((food_name, food_id))

    mycursor.execute("SELECT name,id FROM Main WHERE (name LIKE %s OR SOUNDEX(name) = SOUNDEX(%s)) AND canteen_id != %s AND canteen_id != -1;", (f"%{food}%", food, canteen_id))
    other_canteen_foods = mycursor.fetchall()

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("search.html", username=username, kredit=kredit, food=food, answers=ret, logo = get_image_id(canteen_id))
    
    return render_template("search.html", food=food, answers=ret, other_canteen_foods = other_canteen_foods, logo = get_image_id(canteen_id))

def get_db():
    if 'db' not in g:
        password = open(f"{path_passwords}/password_db.txt",'r').read().strip()
        g.db = MySQLdb.connect(
            host="127.0.0.1",
            user="jidelna",
            passwd=password,
            database="jidelna"
        )
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.route('/get_food/<food_id>', methods = ["GET", "POST"])
def get_food(food_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM Main WHERE id = %s;", (food_id,))
    result = cursor.fetchone()

    if not result:
        return get_message("Food not found")

    id, name, path, average, isFood, canteen_id, author = result
    average=float(average)

    user_rating = ""
    if session.get("user") and session.get("password"):
        cursor.execute("SELECT rating FROM Ratings WHERE foodid = %s AND username = %s;", (id, session.get("user")))
        user_rating = cursor.fetchone()
        if user_rating:
            user_rating = user_rating[0]



    if request.method == "POST":
        if canteen_id != -1:
            new_rating = request.form.get("rating")
            if not user_rating:
                if not session.get("user"):
                    username = "Anonymous"
                else:
                    username = session.get("user")

                cursor.execute("insert into Ratings (foodid,rating,username) values (%s,%s,%s)", (id,new_rating,username))
                db.commit()
            cursor.execute("SELECT AVG(rating) AS AverageRating FROM Ratings where foodid = %s;",(id,))
            ret = cursor.fetchall()

            cursor.execute("update Main SET average = %s where id = %s",(str(ret[0][0]),id,))
            average = str(ret[0][0])
            db.commit()
        
    text = ""
    if not isFood:
        text = "Toto není jídlo ze školní jídelny."

    image_url = get_image_id(food_id)

    isCanteen = canteen_id == -1

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("food.html", username=username, kredit=kredit, image=image_url, name=name, rating=float(average), food_id=food_id, text=text, user_rating = user_rating, canteen_name = canteen_id_to_name(canteen_id), isCanteen = isCanteen, logo = get_image_id(canteen_id), canteen_id = canteen_id)


    return render_template("food.html", image=image_url, name=name, rating=float(average), food_id=food_id, text=text, user_rating = user_rating, canteen_name = canteen_id_to_name(canteen_id), isCanteen = isCanteen, logo = get_image_id(canteen_id), canteen_id = canteen_id)

def canteen_id_to_name(canteen_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT name FROM Main WHERE id = %s;", (canteen_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return "Neznámá jídelna"

@app.route("/image/<filename>")
def get_image_page(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def get_image(image):
    if not image:
        return ""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT path FROM Main WHERE NAME = %s;", (image,))
    path = cursor.fetchone()
    if not path:
        return "/image/WhatsApp_Image_2026-01-16_at_19.21.37.jpg"

    path = path[0]
    filename = path.split('/')[-1]
    image_url = f"/image/{filename}"
    return image_url

def get_image_id(id):
    if not id:
        return ""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT path FROM Main WHERE id = %s;", (id,))
    path = cursor.fetchone()
    if not path:
        return "/image/WhatsApp_Image_2026-01-16_at_19.21.37.jpg"

    path = path[0]
    filename = path.split('/')[-1]
    image_url = f"/image/{filename}"
    return image_url


@app.errorhandler(413)
def request_entity_too_large(error):
    return get_message("File too big")


@app.route('/add_food', methods =["GET", "POST"])
def add_food():
    db = get_db()
    canteen_id = get_canteen_id_raw()
    if not canteen_id:
        return redirect("/canteens")
    logo = ""
    if canteen_id:
        logo = get_image_id(canteen_id)
    if request.method == "POST":
        file = request.files["file"]
        if file:
            extension = os.path.splitext(file.filename)[1]
            filename = secure_filename(file.filename)
            if extension not in app.config['ALLOWED_EXTENSIONS']:
                return 'The uploaded file is not an image.'
            if os.path.isfile(f"{app.config['UPLOAD_FOLDER']}/{file.filename}"):
                rnd = random.randrange(0, 100000)
                filename = f"{rnd}{extension}"
                while os.path.isfile(filename):
                    rnd = random.randrange(0, 100000)
                    filename = f"{rnd}{extension}"
            FoodName = request.form.get("food_name")
            if not FoodName:
                return "Prosim uvedte nazev jidla"
            rating = request.form.get("rating")
            
            path = os.path.join(
                app.config['UPLOAD_FOLDER'],
                secure_filename(filename))
            
            file.save(path)
            if os.path.getsize(path) > compress_limit * 1024 * 1024:  # If the file is larger than 1MB, compress it
                try:
                    mycompress(app.config['UPLOAD_FOLDER'], filename)
                except Exception as e:
                    return f"Exception {e}"


            cursor = db.cursor()
            if not rating:
                rating = -1

            username = "Anonymous"
            if session.get("user") and session.get("password"):
                username = session.get("user")
            
            

            cursor.execute("insert into New (name,path,rating,isFood,username,canteen_id) values (%s,%s,%s,%s,%s,%s)", (FoodName, os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)), rating, 1, username, canteen_id))
            db.commit()
            return get_message("Food submitted")
        else:
            return "Upload failed, image required!!!"
    foods = decide_scrape()
    try:
        foods = foods[0][2]
    except:
        foods = []

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("add_food.html", username=username, kredit=kredit, foods=foods, logo = logo)

    return render_template("add_food.html", foods=foods, logo = logo)

def mycompress(path,file):
    print(f"Compressing {file} ...")
    filename,ext = os.path.splitext(file)
    foo = Image.open(path+"//"+file)
    foo = ImageOps.exif_transpose(foo)
    width, height = foo.size

    foo = foo.resize((round(width*0.5),round(height*0.5)), Image.Resampling.LANCZOS)

    foo.save(f"{path}//{filename}{ext}", optimize= True, quality= 75)
    return 0


@app.route('/favicon.ico')
def favicon_route():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'icon.png')

@app.route('/new_foods/')
def list_new_foods():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT name,id FROM New")
    result = cursor.fetchall()

    return render_template("NewFoods.html", foods= result, logo = get_image_id(get_canteen_id()))

@app.route('/new_food/<food_id>', methods=["GET", "POST"])
def get_new_food(food_id):
    db = get_db()
    f = open(f"{path_passwords}/password_admin.txt",'r')
    password = f.read()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM New WHERE id = %s;", (food_id,))
    result = cursor.fetchone()

    if not result:
        return "Not found"
    
    id, name, path, average, isFood, username, canteen_id = result

    image_url = f"/image/{path.split('/')[-1]}"
    message = ""
#------------------------------------------------------------------------------
    cursor.execute("SELECT * FROM Main WHERE name = %s and canteen_id = %s;", (name, canteen_id))
    Main_result = cursor.fetchone()
    text = ""
    if Main_result:
        text = "Toto jídlo už je v databázi."

    isCanteen = canteen_id == -1

    if request.method == "POST":
        EnteredPassword = request.form.get("password")
        if password == EnteredPassword:
            decision = request.form.get("decision")
            if decision == "accept":
                cursor.execute("insert into Main (name,path,average,isFood, canteen_id, author) values (%s,%s,%s,%s,%s, %s)", (name, path, average, isFood, canteen_id, username))
                cursor.execute("SELECT id FROM Main WHERE name = %s AND path = %s;", (name, path))
                new_id = cursor.fetchone()[0]
                if average != -1:
                    cursor.execute("insert into Ratings (foodid,rating, username) values (%s,%s,%s)", (new_id, average, username))
            if decision == "deny":
                try:
                    os.remove(path)
                except:
                    pass
            cursor.execute("delete from New where id = %s",(id,))
            db.commit()
            if decision == "accept":
                return redirect(f"/get_food/{new_id}")
            else:
                return redirect("/new_foods")
        else:
            message = "Incorrect password"
    return render_template("accept_deny.html", image=image_url, name=name, rating=average, message=message, food_id=food_id, text=text, isCanteen=isCanteen, logo = get_image_id(canteen_id))

def test_url(url):
    try:
        page = requests.get(
            "https://sparkling-sun-0a6e.humanhumanovic.workers.dev/",
            params={"url": url},
            timeout=10
        )
        return page.status_code == 200

    except requests.RequestException:
        return False
    return False

@app.route('/login', methods=["GET", "POST"])
def login():

    canteen_id = get_canteen_id_raw()
    if not canteen_id:
        return redirect("/canteens")
    
    canteen_system_id = canteen_id_to_system(canteen_id)
    canteen_system_name, support = canteen_systems[int(canteen_system_id)]
    if support == 0:
        return render_template("System_not_supported.html", canteen_system_name = canteen_system_name)

    username = ""
    password = ""
    if request.method == "POST":
        if "password" in request.form:
            username = request.form.get("username")
            password = request.form.get("password")
            if decide_login(username, password).strip() != "1":
                return render_template("Login.html", message="Špatné přihlašovací údaje", canteen_system_name = canteen_system_name, support = support)

            session['user'] = username
            session['password'] = cipher.encrypt(password.encode())
            session['kredit'] = decide_kredit(username, password)
            return redirect("/")
            
    return render_template("Login.html", message="", logo = get_image_id(canteen_id), canteen_system_name = canteen_system_name, support = support)
    


@app.route("/statement")
def statement():
    return render_template("statement.html")



@app.route('/order', methods=["POST"])
def order():
    data = request.json
    username = data.get("username")
    password = cipher.decrypt(session.get("password")).decode()
    food = data.get("food")
    day = data.get("day")
    date = datetime.datetime.strptime(day, "%d.%m.%Y").strftime("%Y-%m-%d")

    ret = decide_order(username, password, date, food).strip()
    print(ret)
    credit = decide_kredit(username, password)
    return {"credit": credit, "return": ret}


def get_canteen_id():
    try:
        cookie = request.cookies.get("id")
    except:
        cookie = 220
    if not cookie:
        return 220
    return cookie

def get_canteen_id_raw():
    try:
        cookie = request.cookies.get("id")
    except:
        cookie = ''
    return cookie


@app.route('/foods')
def all_foods():
    db = get_db()
    mycursor = db.cursor()
    
    canteen_id = get_canteen_id_raw()

    if not canteen_id:
        return redirect("/canteens")

    mycursor.execute("SELECT id,name,average FROM Main where canteen_id = %s;",(canteen_id,))

    answer = mycursor.fetchall()
    ret = []
    for item in answer:
        id,name,average = item
        average = float(average)
        image_url = get_image_id(id)
        ret.append((name,id,image_url,average))

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("foods.html", username=username, kredit=kredit, foods=ret)

    logo = ""
    if canteen_id:
        logo = get_image_id(canteen_id)

    return render_template("foods.html", foods=ret, logo=logo)


@app.route('/about')
def about():
    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("About.html", username=username, kredit=kredit)
    
    return render_template("About.html")

@app.route('/contacts')
def contacts():

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("Contacts.html", username=username, kredit=kredit)

    return render_template("Contacts.html")

@app.route('/food_edit/<food_id>', methods=["GET", "POST"])
def food_edit(food_id):
    db = get_db()
    f = open(f"{path_passwords}/password_admin.txt",'r')
    password = f.read()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Main WHERE id = %s;", (food_id,))
    result = cursor.fetchone()

    if not result:
        return "Not found"
    
    id, name, path, average, isFood, canteen_id, author = result

    cursor.execute("SELECT name,id FROM Main WHERE canteen_id = -1;")
    canteens = cursor.fetchall()

    image_url = get_image_id(food_id)
    message = ""
    if request.method == "POST":
        EnteredPassword = request.form.get("password")
        if password == EnteredPassword:
            decision = request.form.get("decision")
            if decision == "delete":
                cursor.execute("delete from Main where id = %s",(id,))
                filename = path.split('/')[-1]
                path = f"{UPLOAD_FOLDER}/{filename}"
                if os.path.isfile(path):
                    os.remove(path)
            else:
                new_name = request.form.get("food_name")
                new_path = request.form.get("path")
                isFood = request.form.get("isFood")
                canteen_id = request.form.get("canteen")
                if isFood == "isFood":
                    isFood = 1
                else:
                    isFood = 0
                cursor.execute("update Main set name = %s, path = %s, isFood = %s, canteen_id = %s where id = %s",(new_name, new_path, isFood, canteen_id,id,))
            db.commit()
            return redirect(f"/get_food/{id}")
        else:
            message = "Incorrect password"
    return render_template("food_edit.html", image=image_url, name=name, rating=average, message=message, food_id=food_id, isFood=isFood, logo = get_image_id(canteen_id), canteen_id = canteen_id, canteens = canteens)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route('/add_canteen', methods =["GET", "POST"])
def add_canteen():
    db = get_db()
    if request.method == "POST":
        file = request.files["file"]
        if file:
            extension = os.path.splitext(file.filename)[1]
            filename = secure_filename(file.filename)
            if extension not in app.config['ALLOWED_EXTENSIONS']:
                return 'The uploaded file is not an image.'
            if os.path.isfile(f"{app.config['UPLOAD_FOLDER']}/{file.filename}"):
                rnd = random.randrange(0, 100000)
                filename = f"{rnd}{extension}"
                while os.path.isfile(filename):
                    rnd = random.randrange(0, 100000)
                    filename = f"{rnd}{extension}"

            canteen_system = request.form.get("canteen_system")
            canteen_name= request.form.get("canteen_name")
            canteen_url = request.form.get("canteen_url")

            if not canteen_name:
                return "Prosim uvedte nazev jidelny"

            path = os.path.join(
                app.config['UPLOAD_FOLDER'],
                secure_filename(filename))
            
            file.save(path)
            if os.path.getsize(path) > compress_limit * 1024 * 1024:  # If the file is larger than 1MB, compress it
                try:
                    mycompress(app.config['UPLOAD_FOLDER'], filename)
                except Exception as e:
                    return f"Exception {e}"


            cursor = db.cursor()
            
            cursor.execute("insert into New (name,path,rating,isFood,username,canteen_id) values (%s,%s,%s,%s,%s,%s)", (canteen_name, os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)), canteen_system, 0, canteen_url , -1))
            db.commit()
            return get_message("Food submitted")
        else:
            return "Upload failed, image required!!!"

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("AddCanteen.html", username=username, kredit=kredit, canteen_systems = canteen_systems)

    return render_template("AddCanteen.html", canteen_systems = canteen_systems)

@app.route("/canteens", methods =["GET", "POST"])
def canteens():
    if request.method == "POST":
        id = request.form.get("canteen_id")
        session.clear()
        response = make_response(redirect(f"/canteen/{id}"))
        response.set_cookie(
            "id",
            id,
            max_age= 60 * 60 * 24 * 365
        )   
        return response
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT name,id FROM Main WHERE canteen_id = -1")
    ret = cursor.fetchall()
    return render_template("Canteens.html", canteens=ret)

@app.route("/canteen/<canteen_id>", methods =["GET", "POST"])
def canteen(canteen_id):

    message = ""

    if session.get("user") and session.get("password"):
        username = session.get("user")
        password = cipher.decrypt(session.get("password")).decode()
        credit = decide_kredit(username, password)
        session['kredit'] = credit
        data = decide_scrape_logged_in(username, password)
        if data == -1:
            data = []
            message = "Nepodařilo se nám načíst jídelníček."
        response = make_response(render_template("NewMain.html", data = data, message = message, supported=True, username=username, kredit = credit, canteen_name = canteen_id_to_name(canteen_id), logo = get_image_id(canteen_id), canteen_id = canteen_id))
    else:
        data=decide_scrape()
        if data == -1:
            data = []
            message = "Nepodařilo se nám načíst jídelníček."
        canteen_system_id = canteen_id_to_system(canteen_id)
        canteen_system_name, support = canteen_systems[int(canteen_system_id)]
        response = make_response(render_template("NewMain.html", data=data, message = message, supported = support == 2,canteen_id=canteen_id, canteen_name=canteen_id_to_name(canteen_id), logo = get_image_id(canteen_id)))


    response.set_cookie(
        "id",
        canteen_id,
        max_age= 60 * 60 * 24 * 365
    )
    return response

@app.route("/canteen_id_to_url/<canteen_id>")
def canteen_id_to_url(canteen_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT author FROM Main WHERE id = %s;", (canteen_id,))
    ret = cursor.fetchone()
    return str(ret[0])

def canteen_id_to_system(canteen_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT average FROM Main WHERE id = %s;", (canteen_id,))
    ret = cursor.fetchone()
    return int(ret[0])

@app.route("/blank")
def blank():
    return ""




#Deciding part
@app.route("/decide_login/<username>,<password>")
def decide_login(username,password):
    canteen_id = get_canteen_id()
    canteen_system = canteen_id_to_system(canteen_id)
    match canteen_system:
        case 0: #iCanteen
            return iCanteen_try_login(username,password,canteen_id)
        case 1: #Strava.cz
            return Strava_try_login(username,password)
        case _:
            return "-1"
        

def decide_kredit(username,password):
    canteen_id = get_canteen_id()
    canteen_system = canteen_id_to_system(canteen_id)
    match canteen_system:
        case 0: #iCanteen
            return iCanteen_kredit(username,password,canteen_id)
        case 1: #Strava.cz
            return Strava_kredit(username,password)
        case _:
            return "-1"


def decide_scrape():
    canteen_id = get_canteen_id()
    canteen_system = canteen_id_to_system(canteen_id)
    match canteen_system:
            case 0: #iCanteen
                ret = iCanteen_scrape()
            case 1: #Strava.cz
                ret = Strava_scrape()
            case _:
                return -1
    return construct_data_for_main_page(ret)

def decide_scrape_logged_in(username, password):
    canteen_id = get_canteen_id()
    canteen_system = canteen_id_to_system(canteen_id)
    match canteen_system:
            case 0: #iCanteen
                ret = iCanteen_scrape()
            case 1: #Strava.cz
                ret = Strava_scrape()
            case _:
                return -1
    return construct_data_for_main_page_logged_in(username,password,ret)

def decide_get_ordered_foods(username,password,dates):
    canteen_id = get_canteen_id()
    canteen_system = canteen_id_to_system(canteen_id)
    match canteen_system:
            case 0: #iCanteen
                ret = iCanteen_get_orderd_food(username,password,dates)
            case 1: #Strava.cz
                ret = Strava_get_ordered_food(username, password, dates)
            case _:
                return -1
    return ret

def decide_order(username, password, date, food): # date format: %d.%m.%Y
    canteen_id = get_canteen_id()
    canteen_system = canteen_id_to_system(canteen_id)
    match canteen_system:
            case 0: #iCanteen
                ret = iCanteen_order_food(username, password, date, food)
            case 1: #Strava.cz
                #datetime_date = datetime.datetime.strptime(date,"%d.%m.%Y")
                #date = datetime_date.strftime("%Y-%m-%d") # strava-cz-python requires this format
                ret = Strava_order_food(username, password, date, food)
            case _:
                return -1
    return ret
    

def construct_data_for_main_page(days):
    data = []
    if days == [] or days == -1:
        return days
    for date, food_list in days:
        datetime_date = datetime.datetime.strptime(date,"%d.%m.%Y")
        date_str = f"{date_to_czech_day_of_the_week(datetime_date)} {date}"
        foods = []
        for food in food_list:
            food_id = -2
            db = get_db()
            mycursor = db.cursor()
            mycursor.execute("SELECT id FROM Main where name = %s", (food,))
            id = mycursor.fetchone()
            if id:
                food_id = id[0]
            user_rating = ""

            mycursor.execute(f"SELECT average FROM Main WHERE id = %s;", (food_id,))
            rating = mycursor.fetchone()
            if rating:
                rating = rating[0]
                if rating == '-1':
                    rating = ""
                else:
                    rating = float(rating)
            foods.append((food, food_id, get_image_id(food_id), True, -1, rating, user_rating)) #food,food_id,image,disabled, my_id, rating, user_rating
        data.append((date, date_str,foods, -2))
    
    return data

@app.route("/test/<username>,<password>,<days>")
def construct_data_for_main_page_logged_in(username, password, days):
    if days == [] or days == -1:
        return days
    if not password:
        return [["Error", ["Password not provided"]]]
    data = [] 
    chosen_food_dates = []

    today = datetime.datetime.now().date()
    #days = iCanteen_scrape()
    for day,food_list in days:
        date = datetime.datetime.strptime(day, "%d.%m.%Y")
        date = date.strftime("%Y-%m-%d")
        chosen_food_dates.append(date)
    #return str(chosen_food_dates)
    chosen_foods_str = decide_get_ordered_foods(username, password, chosen_food_dates)
    chosen_foods = chosen_foods_str.split(";")
    chosen_foods = chosen_foods[:-1]
    #return str(chosen_foods)

    
    day_index = 0
    for day,food_list in days:
        datetime_day = datetime.datetime.strptime(day,"%d.%m.%Y").date()

        disabled = (datetime_day - today).days < 2

        #chosen_food_date = datetime.datetime.strftime(date, "%Y-%m-%d")

        date_str = f"{date_to_czech_day_of_the_week(datetime_day)} {day}"

        chosen_food = ""

        if chosen_foods[day_index]:
            chosen_food = int(chosen_foods[day_index])
        else:
            chosen_food = ""

        date = datetime_day.strftime("%d.%m.%Y")

        foods = []

        my_id = 0
        for food in food_list:
            food_id = -2
            db = get_db()
            mycursor = db.cursor()
            mycursor.execute("SELECT id FROM Main where name = %s", (food,))
            answer = mycursor.fetchone()
            if answer:
                food_id = answer[0]
            user_rating = ""
            if session.get("user") and session.get("password"):
                mycursor.execute("SELECT rating FROM Ratings WHERE foodid = %s AND username = %s;", (food_id, session.get("user")))
                user_rating = mycursor.fetchone()
                if user_rating:
                    user_rating = float(user_rating[0])
            mycursor.execute(f"SELECT average FROM Main WHERE id = %s;", (food_id,))
            rating = mycursor.fetchone()
            if rating:
                rating = rating[0]
                if rating == '-1':
                    rating = ""
                else:
                    rating = float(rating)
            foods.append((food, food_id, get_image_id(food_id), disabled, my_id, rating, user_rating)) #food,food_id,image,disabled, my_id, rating, user_rating
            my_id+=1
        data.append((date,date_str,foods, chosen_food))
        day_index+=1
    return data








# iCanteen requests functions


@app.route("/iCanteen/kredit/<username>,<password>,<canteen_id>")
def iCanteen_kredit(username, password, canteen_id = None):
    if canteen_id is None:
        canteen_id = get_canteen_id()
    canteen_id = canteen_id_to_url(canteen_id)
    #page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://jidelna.qzz.io/iCanteen/kredit.exe/{username},{password},{canteen_id}")
    #page = requests.get(f"http://152.70.41.16.nip.io:8080/credit/{username},{password}")
    #return page.text
    response = iCanteen("kredit.exe",f"{username},{password},{canteen_id}")
    return response

def iCanteen_try_login(username, password, canteen_id = None):
    if canteen_id is None:
        canteen_id = get_canteen_id()
    canteen_id = canteen_id_to_url(canteen_id)
    #page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://jidelna.qzz.io/iCanteen/login.exe/{username},{password},{canteen_id}")
    #return str(page.text)
    response = iCanteen("login.exe",f"{username},{password},{canteen_id}")
    return str(response)

@app.route("/iCanteen/ordered_foods/<username>,<password>,<dates>,<canteen_id>")
def iCanteen_get_orderd_food(username, password, dates, canteen_id = None):
    if canteen_id is None:
        canteen_id = get_canteen_id()
    dates = ".".join(dates)
    canteen_id = canteen_id_to_url(canteen_id)
    #page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://jidelna.qzz.io/iCanteen/get_ordered_foods.exe/{username},{password},{dates},{canteen_id}")
    #return page.text
    response = iCanteen("get_ordered_foods.exe",f"{username},{password},{dates},{canteen_id}")
    return response

@app.route("/iCanteen/ordered_foods_debug/<username>,<password>,<dates>,<canteen_id>")
def iCanteen_get_orderd_food_debug(username, password, dates, canteen_id):
    if canteen_id is None:
        canteen_id = get_canteen_id()
    canteen_id = canteen_id_to_url(canteen_id)
    #page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://jidelna.qzz.io/iCanteen/get_ordered_foods.exe/{username},{password},{dates},{canteen_id}")
    #return page.text
    response = iCanteen("get_ordered_foods.exe",f"{username},{password},{dates},{canteen_id}")
    return response

@app.route("/iCanteen/order_request/<username>,<password>,<date>,<food_id>,<canteen_id>")
def iCanteen_order_food(username, password, date, food_id,canteen_id = None):
    if canteen_id is None:
        canteen_id = get_canteen_id()
    canteen_id = canteen_id_to_url(canteen_id)
    #page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://jidelna.qzz.io/iCanteen/order.exe/{username},{password},{date},{food_id},{canteen_id}")
    #return page.text
    response = iCanteen("order.exe",f"{username},{password},{date},{food_id},{canteen_id}")
    return response

@app.route("/iCanteen/<app>/<path:url>")
def iCanteen(app, url):
    if app not in ALLOWED_APPS:
       return "App not allowed"
    args = url.split(',')

    result = subprocess.run(
        [f"/home/ubuntu/{app}", *args],
        capture_output=True,
        text=True
    )
    return result.stdout


def iCanteen_scrape(): #day,day_str,foods,chosen_food

    if not test_url(canteen_id_to_url(get_canteen_id())):
        return -1
    
    page = requests.get(canteen_id_to_url(get_canteen_id()))
    soup = BeautifulSoup(page.text, "html.parser")

    days = soup.find_all("div", class_="jidelnicekDen")

    data = [] # foods from Hlavni canteen, not modrany


    #date = datetime.datetime(date.year, date.month, date.day + 2)

    for day in days:
        date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].text.strip().split("\xa0")[-1]
        
        foods = []

        food_containers = day.find_all("div", class_="container")
        for food in food_containers:
            if food.find_all("span", style="color:green;")[0].text.strip() == "Hlavní":
                food = food.text.strip().replace("\n","").strip()
                food = unicodedata.normalize("NFKC", food).replace("\xa0", " ").strip()
                if "Polévka" not in food:
                    if "(" in food:
                        food = food[16:food.index("(") - 1]
                    else:
                        food = food[16:len(food) - 1]

                    # Generovany chatem GPT{
                    food = re.sub(r"[,\s\xa0]*čaj.*$", "", food, flags=re.IGNORECASE) # odstrani vse po ", caj"
                    food = re.sub(r"\s+", " ", food)
                    food = ' '.join(food.split())
                    #}
                    foods.append(food)
        data.append((date, foods)) # -2

    return data







#Strava.cz connecting functions:


@app.route("/strava/login/<username>,<password>")
def Strava_try_login(username, password):
    canteen_number = canteen_id_to_url(get_canteen_id())
    try:
        strava_login_internal(username,password,canteen_number)
    except AuthenticationError as e:
        return "0"
    return "1"

@app.route("/strava/kredit/<username>,<password>")
def Strava_kredit(username, password):
    canteen_number = canteen_id_to_url(get_canteen_id())
    strava = strava_login_internal(username, password, canteen_number)
    return str(strava.user.balance)

# I didn't have the patience to try and debug unsoup and function used by it so I made ChatGPT fix it. I provided it with the criteria and the general algorithm.
# I acquired said criteria by seeing paterns myself in canteens that have incorrect soup placement
def is_soup_string(text):
    text = text.lower()

    for soup_str in SoupStrings:
        soup_str = soup_str.lower()

        if soup_str == "p.":
            if re.search(r"\bp\.", text):
                return True

        elif re.search(rf"\b{re.escape(soup_str)}\b", text):
            return True

    return False


def first_letter(text):
    return next(
        (c for c in text if c.isalpha()),
        None
    )


def split_meal(meal):
    return [
        part.strip()
        for part in (
            meal
            .replace(";", ",")
            .replace("/", ",")
            .split(",")
        )
        if part.strip()
    ]


def unsoup(meals):
    if not meals:
        return []

    split_meals = [
        split_meal(meal)
        for meal in meals
    ]

    handled = [False] * len(split_meals)

    # =================================================
    # 1. SOUP STRINGS
    # =================================================

    for meal_idx, parts in enumerate(split_meals):

        soup_start = None

        for i, part in enumerate(parts):
            if is_soup_string(part):
                soup_start = i
                break

        if soup_start is None:
            continue

        # At minimum, remove the component containing
        # the soup identifier.
        soup_end = soup_start + 1

        # Look for a LOWERCASE -> UPPERCASE boundary.
        #
        # Example:
        #
        # Hovězí vývar, játrové knedlíčky, Filé
        #                                  ^
        #
        # In this case the first two components are soup.
        #
        # IMPORTANT:
        # If there is NO uppercase boundary, we do NOT
        # consume the entire rest of the meal.

        for i in range(soup_start + 1, len(parts)):

            letter = first_letter(parts[i])

            if letter and letter.isupper():
                soup_end = i
                break

        split_meals[meal_idx] = parts[soup_end:]
        handled[meal_idx] = True

    # =================================================
    # 2. LOWERCASE -> UPPERCASE BOUNDARY
    # =================================================

    for meal_idx, parts in enumerate(split_meals):

        if handled[meal_idx]:
            continue

        for i in range(len(parts) - 1):

            a = first_letter(parts[i])
            b = first_letter(parts[i + 1])

            if (
                a
                and b
                and a.islower()
                and b.isupper()
            ):
                split_meals[meal_idx] = parts[i + 1:]
                handled[meal_idx] = True
                break

    # =================================================
    # 3. REPEATED START
    # =================================================

    # Only use this rule if there are at least two
    # UNHANDLED meals.

    unhandled_indices = [
        i for i in range(len(split_meals))
        if not handled[i]
    ]

    if len(unhandled_indices) >= 2:

        common_prefix = 0

        max_prefix = min(
            len(split_meals[i])
            for i in unhandled_indices
        )

        for pos in range(max_prefix):

            values = [
                split_meals[i][pos].lower()
                for i in unhandled_indices
            ]

            if len(set(values)) == 1:
                common_prefix = pos + 1
            else:
                break

        # Don't remove the entire meal.
        if common_prefix:

            can_remove = all(
                len(split_meals[i]) > common_prefix
                for i in unhandled_indices
            )

            if can_remove:
                for i in unhandled_indices:
                    split_meals[i] = split_meals[i][common_prefix:]

    # =================================================
    # 4. COMMON SUFFIXES
    # =================================================

    if len(split_meals) >= 2:

        while all(
            len(meal) > 1
            and meal[-1].lower() in SuffixStrings
            for meal in split_meals
        ):
            split_meals = [
                meal[:-1]
                for meal in split_meals
            ]

    return [
        ", ".join(parts)
        for parts in split_meals
    ]


def Strava_scrape(): 
    canteen_number = canteen_id_to_url(get_canteen_id())

    url = "https://app.strava.cz/api/jidelnickyPage"
    
    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Content-Type": "text/plain;charset=UTF-8",
        "Origin": "https://app.strava.cz",
        "Referer": f"https://app.strava.cz/jidelnicky?jidelna={canteen_number}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    }
    
    payload = {
        "cislo": str(canteen_number),
        "lang": "CZ"
    }
    
    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(payload),
        timeout=15
    )
    
    response.raise_for_status()
    
    data = response.json()
    
    days = []
    
    for key, meals in data["meals"].items():
        if not key.startswith("table"):
            continue
        
        if not meals:
            continue
        
        date = meals[0]["datum"]

        soup = False

        mymeals = []
        #print(date)
        for meal in meals:
            druh = meal["druh"].lower()
            nazev = meal["nazev"].lower()
            polevka = meal["polevka"].lower()
            druh_popis = meal["druh_popis"].lower()
            druh_chod = meal["druh_chod"].lower()
            if druh != 'p' and druh != 'po' and druh != 'do' and nazev and "oběd" not in nazev and "obed" not in nazev and polevka != "a" and "polevka" not in druh_popis and "polévka" not in druh_popis and "doplnek" not in druh_popis and "doplněk" not in druh_popis and "přesníd" not in druh_popis and "presnid" not in druh_popis and "presnid" not in druh_chod and "přesníd" not in druh_chod and "svačin" not in druh_popis and "svacin" not in druh_popis and "xx" not in nazev: # The great filter
                #print(f"meal name: {meal['nazev']}")
                mymeals.append(meal["nazev"])

        mymeals = unsoup(mymeals)

        #for meal in mymeals:
        #    print(meal)
    
        days.append((date,mymeals))
    return days
        

@app.route("/strava/get_ordered_food/<username>,<password>,<dates>") # lets hope this works :crying: :hope:
def Strava_get_ordered_food(username, password, dates):
    canteen_number = canteen_id_to_url(get_canteen_id())
    strava = strava_login_internal(username, password, canteen_number)

    strava.menu.fetch()

    ordered_indexes = []
    for i in range(len(dates)):
        ordered_indexes.append('')

        menu = strava.menu.get_by_date(dates[i])

        if menu:
            for meal_index in range(len(menu["meals"])):
                meal = menu["meals"][meal_index]
                if meal["ordered"]:
                    ordered_indexes[-1] = meal_index
    if len(ordered_indexes) < 1:
        return ""
    return ';'.join(ordered_indexes) + ";"

@app.route("/strava/order/<username>,<password>,<date>,<food>")
def Strava_order_food(username, password, date, food):
    canteen_number = canteen_id_to_url(get_canteen_id())
    strava = StravaCZ(
            username=username,
            password=password,
            canteen_number = canteen_number
        )
    #strava = strava_login_internal(username, password, canteen_number)
    food = int(food)
    date_time = datetime.datetime.strptime(date, "%Y-%m-%d")
    strava.menu.fetch()

    menu = strava.menu.get_by_date(date_time)
    if not menu:
        return f"Date \"{str(date)}\" not found"
    id = menu['meals'][food]['id']
    strava.menu.order_meals(id)
    ordered = strava.menu.is_ordered(id)
    return str(ordered)



def strava_login_internal(username, password, canteen_number):
    strava = StravaCZ(
            username=username,
            password=password,
            canteen_number = canteen_number
        )
    return strava



def date_to_czech_day_of_the_week(date):
    day_num = date.weekday()
    match day_num:
        case 0:
            return "pondělí"
        case 1:
            return "úterý"
        case 2:
            return "středa"
        case 3:
            return "čtvrtek"
        case 4:
            return "pátek"
        case 5:
            return "sobota"
        case 6:
            return "neděle"
        case _:
            return "What?"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)