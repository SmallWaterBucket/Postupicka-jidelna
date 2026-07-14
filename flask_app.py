import datetime
import subprocess

from flask import Flask, session, render_template, url_for, request, redirect, flash, send_from_directory, g
import PIL
from PIL import Image, ImageOps
from cryptography.fernet import Fernet
import os.path, secrets
import os,requests, unicodedata, MySQLdb,re
from werkzeug.utils import secure_filename
from flask import json
from werkzeug.exceptions import HTTPException
from bs4 import BeautifulSoup
import random

#TODO:


#Add a posibility to add diferent canteens
# /add_canteen
# better design
# storing canteen in cookies
# adding full compat for iCanteen (maybe using the library for everything?)
# adding compat with different canteen systems

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

#==========================================================

app = Flask(__name__)

UPLOAD_FOLDER = '/home/jidelna/photos'
app.config['ALLOWED_EXTENSIONS'] = ['.jpg', '.jpeg', '.png']
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 4*1024 * 1024 #4MB
compress_limit = 0.5 # This is the number of MB above which an image will be compressed

path_passwords = "/home/jidelna/"

app.secret_key = open(f"{path_passwords}/secret.txt",'r').read().strip()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=1800
)

key = open(f"{path_passwords}/password.txt",'r').read().strip().encode()
cipher = Fernet(key)




@app.route('/', methods =["GET", "POST"])
def Main():

    
    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")


    if session.get("user") and session.get("password"):
        username = session.get("user")
        password = cipher.decrypt(session.get("password")).decode()
        credit = kredit(username, password)
        session['kredit'] = credit
        data = new_scrape(username, password)
        return render_template("NewMain.html", data = data, username=username, kredit = credit)
    else:
        data=scrape()


    return render_template("NewMain.html", data = data)

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
            message="Děkujeme, že jste přidali jídlo."
            submessage = " Zkontrolujeme ho do jednoho týdne a přidáme ho."
            img = "/image/Added_food.jpeg"
        case "File too big":
            message="Soubor příliš velký"
            submessage = f"Soubor, který jste přidali je větší než náš {int(app.config['MAX_CONTENT_LENGTH']) / (1024*1024)} MB limit."
            img = "/image/File_too_big.jpeg"
        case _:
            submessage = "How did you even find this?"
            message = "Go get a job."

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("message.html", username=username, kredit=kredit, message=message, submessage = submessage, link = link, link_text=link_text, img = img)

    return render_template("message.html", message=message, submessage = submessage, link = link, link_text=link_text, img = img)

@app.route('/search/<food>', methods = ["GET", "POST"])
def search(food):
    db = get_db()
    mycursor = db.cursor()
    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")
    mycursor.execute("SELECT id FROM Main where name = %s", (food,))
    answer = mycursor.fetchone()
    if answer:
        return redirect(f"/get_food/{answer[0]}")

    mycursor.execute("SELECT * FROM Main WHERE name LIKE %s OR SOUNDEX(name) = SOUNDEX(%s);", (f"%{food}%", food))

    answer = mycursor.fetchall()
    ret = []
    for item in answer:
        food_item = item[1]  # name column
        food_id = item[0]   # id column
        ret.append((food_item, food_id))

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("search.html", username=username, kredit=kredit, food=food, answers=ret)



    return render_template("search.html", food=food, answers=ret)

def get_db():
    if 'db' not in g:
        password = open(f"{path_passwords}/password_db.txt",'r').read()
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

    user_rating = ""
    if session.get("user") and session.get("password"):
        cursor.execute("SELECT rating FROM Ratings WHERE foodid = %s AND username = %s;", (id, session.get("user")))
        user_rating = cursor.fetchone()
        if user_rating:
            user_rating = user_rating[0]



    if request.method == "POST":
        new_rating = request.form.get("rating")
        if not user_rating:
            if not session.get("user"):
                username = "Anonymous"
            else:
                username = session.get("user")

            cursor.execute("insert into Ratings (foodid,rating,username) values (%s,%s,%s)", (id,new_rating,username))
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

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("food.html", username=username, kredit=kredit, image=image_url, name=name, rating=str(average), food_id=food_id, text=text, user_rating = user_rating)


    return render_template("food.html", image=image_url, name=name, rating=str(average), food_id=food_id, text=text, user_rating = user_rating)

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
            
            cursor.execute("insert into New (name,path,rating,isFood,username) values (%s,%s,%s,%s,%s)", (FoodName, os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)), rating, 1, username))
            db.commit()
            return get_message("Food submitted")
        else:
            return "Upload failed, image required!!!"
    foods = scrape()
    try:
        foods = foods[0][2]
    except:
        foods = []

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("add_food.html", username=username, kredit=kredit, foods=foods)

    return render_template("add_food.html", foods=foods)

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
    cursor.execute("SELECT * FROM New")
    result = cursor.fetchall()

    ret = []
    for item in result:
        food = item[1]
        id = item[0]
        ret.append((food, id))
    return render_template("NewFoods.html", foods=ret)

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
    
    id, name, path, average, isFood, username = result

    image_url = f"/image/{path.split('/')[-1]}"
    message = ""
#------------------------------------------------------------------------------
    cursor.execute("SELECT * FROM Main WHERE name = %s;", (name,))
    Main_result = cursor.fetchone()
    text = ""
    if Main_result:
        text = "Toto jídlo už je v databázi."

    if request.method == "POST":
        EnteredPassword = request.form.get("password")
        if password == EnteredPassword:
            decision = request.form.get("decision")
            if decision == "accept":
                cursor.execute("insert into Main (name,path,average,isFood) values (%s,%s,%s,%s)", (name, path, average, isFood))
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
    return render_template("accept_deny.html", image=image_url, name=name, rating=average, message=message, food_id=food_id, text=text)


@app.route('/login', methods=["GET", "POST"])
def login():
    username = ""
    password = ""
    if request.method == "POST":
        if "password" in request.form:
            username = request.form.get("username")
            password = request.form.get("password")
            if try_login(username, password) == "0\n":
                return render_template("Login.html", message="Špatné přihlašovací údaje")

            session['user'] = username
            session['password'] = cipher.encrypt(password.encode())
            session['kredit'] = kredit(username, password)
            return redirect("/")
            
    return render_template("Login.html", message="")
    


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

    ret = order_food(username, password, date, food)
    print(ret)
    credit = kredit(username, password)
    return {"credit": credit}

def scrape(): #day,day_str,foods,chosen_food
    #page = requests.get("https://api.allorigins.win/raw?url=https://strav.nasejidelna.cz/0254/login")
    page = requests.get("https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=https://strav.nasejidelna.cz/0254/login")
    soup = BeautifulSoup(page.text, "html.parser")

    days = soup.find_all("div", class_="jidelnicekDen")

    data = [] # foods from Hlavni canteen, not modrany

    today = datetime.datetime.now().strftime("%d.%m.%Y")


    #date = datetime.datetime(date.year, date.month, date.day + 2)

    for day in days:
        date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].text.strip()
        #date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].get("id").split("-")[1:]
        #date = ".".join(date)
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
                    food_id = -1
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
                            user_rating = user_rating[0]

                    mycursor.execute(f"SELECT average FROM Main WHERE id = %s;", (food_id,))
                    rating = mycursor.fetchone()
                    if rating:
                        rating = rating[0]
                        if rating == '-1':
                            rating = ""
                    
                    foods.append((food, food_id, get_image(food), True, -1, rating, user_rating)) #food,food_id,image,disabled, my_id, rating, user_rating
        data.append((date, date,foods, -2))

    return data


@app.route("/new_scrape/<username>,<password>")
def new_scrape(username, password):
    #page = requests.get("https://api.allorigins.win/raw?url=https://strav.nasejidelna.cz/0254/login")
    page = requests.get("https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=https://strav.nasejidelna.cz/0254/login")
    soup = BeautifulSoup(page.text, "html.parser")

    days = soup.find_all("div", class_="jidelnicekDen")

    data = [] # foods from Hlavni canteen, not modrany
    chosen_food_dates = []

    today = datetime.datetime.now().date()
    if password:
        for day in days:
            date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].get("id").split("-")[1:]
            date = ".".join(date)
            date = datetime.datetime.strptime(date, "%Y.%m.%d").date()

            chosen_food_date = datetime.datetime.strftime(date, "%Y-%m-%d")
            chosen_food_dates.append(chosen_food_date)
        #return str(chosen_food_dates)
        chosen_foods_str = get_orderd_food(username, password, chosen_food_dates)
        chosen_foods = chosen_foods_str.split(";")
        chosen_foods = chosen_foods[:-1]
        #return str(chosen_foods)
        
    

    
    day_index = 0
    for day in days:
        str_date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].text.strip()
        date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].get("id").split("-")[1:]
        date = ".".join(date)
        date = datetime.datetime.strptime(date, "%Y.%m.%d").date()
        disabled = (date - today).days < 2


        chosen_food_date = datetime.datetime.strftime(date, "%Y-%m-%d")
        chosen_food = ""
        if password:
            if chosen_foods[day_index]:
                chosen_food = int(chosen_foods[day_index])
            else:
                chosen_food = ""

        date = date.strftime("%d.%m.%Y")



        foods = []

        food_containers = day.find_all("div", class_="container")
        my_id = -1
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
                    food_id = -1
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
                            user_rating = user_rating[0]

                    mycursor.execute(f"SELECT average FROM Main WHERE id = %s;", (food_id,))
                    rating = mycursor.fetchone()
                    if rating:
                        rating = rating[0]
                        if rating == '-1':
                            rating = ""


                    foods.append((food, food_id, get_image(food), disabled, my_id, rating, user_rating)) #food,food_id,image,disabled, my_id, rating, user_rating
            my_id+=1
        data.append((date,str_date,foods, chosen_food))
        day_index+=1
    return data





@app.route('/foods')
def all_foods():
    db = get_db()
    mycursor = db.cursor()

    mycursor.execute("SELECT * FROM Main")

    answer = mycursor.fetchall()
    ret = []
    for item in answer:
        filename = os.path.split(item[2])[-1]
        image_url = f"/image/{filename}"
        food_item = item[1], item[0], image_url, item[3]  # food, food_id,image,rating
        ret.append(food_item)

    if session.get("user") and session.get("password"):
        username = session.get("user")
        kredit = session.get("kredit")
        return render_template("foods.html", username=username, kredit=kredit, foods=ret)

    return render_template("foods.html", foods=ret)


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
            return redirect(f"/get_food/{id}")
        else:
            message = "Incorrect password"
    return render_template("food_edit.html", image=image_url, name=name, rating=average, message=message, food_id=food_id, isFood=isFood)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/canteens", methods =["GET", "POST"])
def canteens():
    if request.method == "POST":
        id = request.form.get("canteen")
        return redirect(f"/canteen/{id}")
    ret = [("Postupicka",0)]
    return render_template("Canteens.html", canteens=ret)

@app.route("/canteen/<id>", methods =["GET", "POST"])
def canteen(id):
    data = scrape()
    return render_template("NewMain.html", data=data, canteen=id)
    #if request.method == "POST":
    #    food = request.form.get("food_name")
    #    return redirect(f"/search/{food}")


    #if session.get("user") and session.get("password"):
    #    username = session.get("user")
    #    password = cipher.decrypt(session.get("password")).decode()
    #    credit = kredit(username, password)
    #    session['kredit'] = credit
    #    data = new_scrape(username, password)
    #    return render_template("NewMain.html", data = data, username=username, kredit = credit)
    #else:
    #    data=scrape()




@app.route("/kredit/<username>,<password>")
def kredit(username, password):
    page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://152.70.41.16.nip.io:8080/kredit.exe/{username},{password}")
    #page = requests.get(f"http://152.70.41.16.nip.io:8080/credit/{username},{password}")
    return page.text

def try_login(username, password):
    page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://152.70.41.16.nip.io:8080/login.exe/{username},{password}")
    return str(page.text)

@app.route("/ordered_foods/<username>,<password>,<dates>")
def get_orderd_food(username, password, dates):
    dates = ".".join(dates)
    page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://152.70.41.16.nip.io:8080/get_ordered_foods.exe/{username},{password},{dates}")
    return page.text

@app.route("/ordered_foods_debug/<username>,<password>,<dates>")
def get_orderd_food_debug(username, password, dates):
    page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://152.70.41.16.nip.io:8080/get_ordered_foods.exe/{username},{password},{dates}")
    return page.text

@app.route("/order_request/<username>,<password>,<date>,<food_id>")
def order_food(username, password, date, food_id):
    page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=http://152.70.41.16.nip.io:8080/order.exe/{username},{password},{date},{food_id}")

#if __name__ == "__main__":
#    app.run(host="0.0.0.0", port=8080)