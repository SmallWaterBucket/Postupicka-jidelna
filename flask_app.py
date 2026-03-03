import datetime

from flask import Flask, render_template,url_for, request, redirect, flash, send_from_directory, g
import os.path
import os,requests, unicodedata, MySQLdb,re
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup
import random


app = Flask(__name__)

UPLOAD_FOLDER = '/home/jidelna/photos'
app.config['ALLOWED_EXTENSIONS'] = ['.jpg', '.jpeg', '.png']
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 4*1024 * 1024 #4MB

@app.route('/', methods =["GET", "POST"])
def Main():
    db = get_db()
    mycursor = db.cursor()

    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")
    data=scrape()
    return render_template("main.html", data = data)

@app.route("/message/<message>")
def get_message(message):
    submessage = ""
    link = ""
    link_text = ""
    img = "/image/Employment-Job-Application-791x1024-3681536362.png"

    match message:
        case "Food not found":
            message="Jídlo nenalezeno."
            link="/add_food"
            link_text = "Přidat ho?"
            img=get_image("Jidlo nenalezeno new")
        case "Food submitted":
            message="Děkujeme za to že jste přidali jídlo."
            submessage = " Zkontrolujeme ho do jednoho týdne a přidáme ho."
            img = "/image/Added_food.jpeg"
        case "File too big":
            message="Soubor příliš velký"
            submessage = f"Soubor, který jste přidali je větší než náš {int(app.config['MAX_CONTENT_LENGTH']) / (1024*1024)} MB limit."
            img = "/image/File_too_big.jpeg"
        case _:
            submessage = "How did you even find this?"
            message = "Go get a job."

    return render_template("message.html", message=message, submessage = submessage, link = link, link_text=link_text, img = img)

@app.route('/search/<food>', methods = ["GET", "POST"])
def search(food):
    db = get_db()
    mycursor = db.cursor()
    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")
    mycursor.execute("SELECT * FROM Main where name = %s", (food,))
    answer = mycursor.fetchone()
    if answer:
        return redirect(f"/get_food/{food}")

    mycursor.execute("SELECT * FROM Main WHERE name LIKE %s OR SOUNDEX(name) = SOUNDEX(%s);", (f"%{food}%", food))

    answer = mycursor.fetchall()
    ret = []
    for item in answer:
        food_item = item[1]  # name column
        food_id = item[0]   # id column
        ret.append((food_item, food_id))

    return render_template("search.html", food=food, answers=ret)

def get_db():
    if 'db' not in g:
        password = open("/home/jidelna/password_db.txt",'r').read()
        g.db = MySQLdb.connect(
            host="jidelna.mysql.eu.pythonanywhere-services.com",
            user="jidelna",
            passwd=password,
            database="jidelna$default"
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

    id, name, path, average, isFood = result
    average=float(average)
    if request.method == "POST":
        new_rating = request.form.get("rating")
        cursor.execute("insert into Ratings (foodid,rating) values (%s,%s)", (id,new_rating))
        db.commit()
        cursor.execute("SELECT AVG(rating) AS AveragePrice FROM Ratings where foodid = %s;",(id,))
        ret = cursor.fetchall()

        cursor.execute("update Main SET average = %s where id = %s",(str(ret[0][0]),id,))
        average = str(ret[0][0])
        db.commit()
    
    if average == -1:
        average = "Žádné hodnocení"
        
    text = ""
    if not isFood:
        text = "Toto není jídlo ze školní jídelny."

    image_url = get_image(name)
    return render_template("food.html", image=image_url, name=name, rating=str(average), food_id=food_id, text=text)

@app.route("/image/<filename>")
def get_image_page(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def get_image(image):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM Main WHERE NAME = %s;", (image,))
    result = cursor.fetchone()
    if not result:
        return "/image/WhatsApp_Image_2026-01-16_at_19.21.37.jpeg"
    id, name, path, average, isFood = result
    filename = path.split('/')[-1]
    image_url = f"/image/{filename}"
    return image_url


@app.errorhandler(413)
def request_entity_too_large(error):
    return get_message("File too big")


@app.route('/add_food', methods =["GET", "POST"])
def add_food():
    db = get_db()
    mycursor = db.cursor()
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
            rating = -1

            file.save(os.path.join(
                app.config['UPLOAD_FOLDER'],
                secure_filename(filename)))
            cursor = db.cursor()
            cursor.execute("insert into New (name,path,rating,isFood) values (%s,%s,%s,%s)", (FoodName, os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)), rating, 1))
            db.commit()
            return get_message("Food submitted")
        else:
            return "Upload failed, image required!!!"
    foods = scrape()
    foods = foods[0][1]
    return render_template("add_food.html",foods=foods)


@app.route('/favicon.ico')
def favicon_route():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'icon.png')

@app.route('/new_foods/')
def list_new_foods():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM New")
    result = cursor.fetchall()

    ret = ""
    for item in result:
        food = item[1]
        id = item[0]
        ret+=f"<p><a href=/new_food/{id}>{food}</p>"
    return ret

@app.route('/new_food/<food_id>', methods=["GET", "POST"])
def get_new_food(food_id):
    db = get_db()
    f = open("/home/jidelna/password_admin.txt",'r')
    password = f.read()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM New WHERE id = %s;", (food_id,))
    result = cursor.fetchone()

    if not result:
        return "Not found"
    
    id, name, path, average, isFood = result

    image_url = f"/image/{path.split('/')[-1]}"
    message = ""
    if request.method == "POST":
        EnteredPassword = request.form.get("password")
        if password == EnteredPassword:
            decision = request.form.get("decision")
            if decision == "accept":
                cursor.execute("insert into Main (name,path,average,isFood) values (%s,%s,%s,%s)", (name, path, average, isFood))
            if decision == "deny":
                os.remove(path)
            cursor.execute("delete from New where id = %s",(id,))
            db.commit()
            return f"Action successful"
        else:
            message = "Incorrect password"
    return render_template("accept_deny.html", image=image_url, name=name, rating=average, message=message, food_id=food_id)


@app.route('/debug')
def debug():
    db = get_db()
    mycursor = db.cursor()
    data = new_scrape()
    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")
    return render_template("NewMain.html", data = data)

def scrape():
    #page = requests.get("https://api.allorigins.win/raw?url=https://strav.nasejidelna.cz/0254/login")
    page = requests.get("https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=https://strav.nasejidelna.cz/0254/login")
    soup = BeautifulSoup(page.text, "html.parser")

    days = soup.find_all("div", class_="jidelnicekDen")

    data = [] # foods from Hlavni canteen, not modrany

    today = datetime.datetime.now().strftime("%d.%m.%Y")


    #date = datetime.datetime(date.year, date.month, date.day + 2)

    for day in days:
        #date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].text.strip()
        date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].get("id").split("-")[1:]
        date = ".".join(date)
        #disabled = date - today <= 2
        
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

                    foods.append((food,get_image(food)))
        data.append((date,foods))

    return data



def new_scrape():
    #page = requests.get("https://api.allorigins.win/raw?url=https://strav.nasejidelna.cz/0254/login")
    page = requests.get("https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=https://strav.nasejidelna.cz/0254/login")
    soup = BeautifulSoup(page.text, "html.parser")

    days = soup.find_all("div", class_="jidelnicekDen")

    data = [] # foods from Hlavni canteen, not modrany

    today = datetime.datetime.now().date()


    #date = datetime.datetime(date.year, date.month, date.day + 2)

    for day in days:
        #date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].text.strip()
        date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].get("id").split("-")[1:]
        date = ".".join(date)
        date = datetime.datetime.strptime(date, "%Y.%m.%d").date()
        disabled = (date - today).days <= 2
        
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

                    foods.append((food,get_image(food), disabled))
        data.append((date,foods))

    return data





@app.route('/foods')
def all_foods():
    db = get_db()
    mycursor = db.cursor()

    mycursor.execute("SELECT * FROM Main")

    answer = mycursor.fetchall()
    ret = []
    for item in answer:
        food_item = item[1], item[0]  # name column, id column
        ret.append(food_item)

    return render_template("foods.html", foods=ret)


@app.route('/about')
def about():
    return render_template("About.html")

@app.route('/contacts')
def contacts():
    return render_template("Contacts.html")

@app.route('/food_edit/<food_id>', methods=["GET", "POST"])
def food_edit(food_id):
    db = get_db()
    f = open("/home/jidelna/password_admin.txt",'r')
    password = f.read()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM Main WHERE id = %s;", (food_id,))
    result = cursor.fetchone()

    if not result:
        return "Not found"
    
    id, name, path, average, isFood = result

    image_url = get_image(name)
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
                if isFood == "isFood":
                    isFood = 1
                else:
                    isFood = 0
                cursor.execute("update Main set name = %s, path = %s, isFood = %s where id = %s",(new_name, new_path, isFood, id,))
            db.commit()
            return f"Action successful"
        else:
            message = "Incorrect password"
    return render_template("food_edit.html", image=image_url, name=name, rating=average, message=message, food_id=food_id, isFood=isFood)
