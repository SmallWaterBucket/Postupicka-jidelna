from flask import Flask, render_template,url_for, request, redirect, flash, send_from_directory
import os,requests, unicodedata, MySQLdb,re
from werkzeug.utils import secure_filename
from bs4 import BeautifulSoup


app = Flask(__name__)

UPLOAD_FOLDER = '/home/jidelna/mysite/static/images'
app.config['ALLOWED_EXTENSIONS'] = ['.jpg', '.jpeg', '.png']
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 4*1024 * 1024 #4MB

@app.route('/', methods =["GET", "POST"])
def hello_world():
    db = get_db()
    mycursor = db.cursor()

    if request.method == "POST":
        food = request.form.get("food_name")
        return redirect(f"/search/{food}")
    data=scrape()
    #for item in data:
    #    new_data.append((item,image_url))
    return render_template("main.html", data = data)

def get_image(food_name):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM Main WHERE NAME = %s;", (food_name,))
    result = cursor.fetchone()
    if not result:
        return "static/images/WhatsApp_Image_2026-01-16_at_19.21.37.jpeg" #"/static/images/Food_not_found.png"   #"/static/images/rohlik_1.jpg"
    id, name, path, average = result

    filename = path.split('/')[-1]
    image_url = url_for('static', filename=f'images/{filename}')
    return image_url

@app.route("/message/<message>")
def get_message(message):
    submessage = ""
    link = ""
    link_text = ""
    img = url_for('static', filename="images/Employment-Job-Application-791x1024-3681536362.png")

    match message:
        case "Food not found":
            message="Jídlo nenalezeno."
            link="/add_food"
            link_text = "Přidat ho?"
            img=get_image("Jidlo nenalezeno new")
        case "Food submitted":
            message="Děkujeme za to že jste přidali jídlo."
            submessage = " Zkontrolujeme ho do jednoho týdne a přidáme ho."
            img = url_for('static', filename=f'images/Added_food.jpeg')
        case "File too big":
            message="Soubor příliš velký"
            submessage = f"Soubor, který jste přidali je větší než náš {int(app.config['MAX_CONTENT_LENGTH']) / (1024*1024)} MB limit."
            img = url_for('static', filename=f'images/File_too_big.jpeg')
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
        food_item = food_item.replace(' ', '_')
        ret.append(food_item)

    return render_template("search.html", food=food, answers=ret)

def get_db():
    try:
        db.ping(reconnect=True)
    except:
        # Reconnect
        db = MySQLdb.connect(
        host="jidelna.mysql.eu.pythonanywhere-services.com",
        user="jidelna",
        passwd="efuio2Sd3Nj2", #toto heslo uz bylo zmeneno, takze to nebude fungovat
        database="jidelna$default"
        )
    return db


@app.route('/get_food/<food_name>', methods = ["GET", "POST"])
def get_food(food_name):
    db = get_db()
    mycursor = db.cursor()
    food_name = food_name.replace('_', ' ')
    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM Main WHERE NAME = %s;", (food_name,))
    #return str(cursor.fetchone())
    result = cursor.fetchone()
    if not result:
        return get_message("Food not found")

    # Example assuming (id, name, path, average)
    id, name, path, average = result
    average=float(average)
    if request.method == "POST":
        #return request.form.get("rating")
        new_rating = request.form.get("rating")
        cursor.execute("insert into Ratings (foodid,rating) values (%s,%s)", (id,new_rating))
        db.commit()
        cursor.execute("SELECT AVG(rating) AS AveragePrice FROM Ratings where foodid = %s;",(id,))
        ret = cursor.fetchall()

        cursor.execute("update Main SET average = %s where id = %s",(str(ret[0][0]),id,))
        average = str(ret[0][0])
        db.commit()

    # Extract just the filename if you stored full paths
    filename = path.split('/')[-1]
    image_url = url_for('static', filename=f'images/{filename}')
    favicon = url_for('static', filename="icon.png")
    return render_template("a.html", image=image_url, name=name, rating=str(average))


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
            if extension not in app.config['ALLOWED_EXTENSIONS']:
                return 'The uploaded file is not an image.'

            FoodName = request.form.get("food_name")
            rating = -1
            filename = secure_filename(file.filename)
            file.save(os.path.join(
                app.config['UPLOAD_FOLDER'],
                secure_filename(filename)))
            cursor = db.cursor()
            cursor.execute("insert into New (name,path,rating) values (%s,%s,%s)", (FoodName, os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename)), rating))
            db.commit()
            return get_message("Food submitted")#f"You submitted food \"{FoodName}\", the admin will review your submission in the future (Usually max one week)"
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
        food = food.replace(' ', '_')
        ret+=f"<p><a href=/new_food/{food}>{food}</p>"
    return ret

@app.route('/new_food/<food_name>', methods=["GET", "POST"])
def get_new_food(food_name):
    db = get_db()
    food_name = food_name.replace('_',' ')
    f = open("/home/jidelna/mysite/password.txt",'r')
    password = f.read()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM New WHERE name = %s;", (food_name,))
    result = cursor.fetchone()
    if not result:
        return "Not found"

    # Example assuming (id, name, path, average)
    id, name, path, average = result

    # Extract just the filename if you stored full paths
    filename = path.split('/')[-1]
    image_url = url_for('static', filename=f'images/{filename}')
    message = ""
    if request.method == "POST":
        EnteredPassword = request.form.get("password")
        if password == EnteredPassword:
            decision = request.form.get("decision")
            if decision == "accept":
                cursor.execute("insert into Main (name,path,average) values (%s,%s,%s)", (name, path, average))
            if decision == "deny":
                os.remove(f"/home/jidelna/mysite/static/images/{filename}")
            cursor.execute("delete from New where id = %s",(id,))
            db.commit()
            return f"Action successful"
        else:
            message = "Incorrect password"
    return render_template("accept_deny.html", image=image_url, name=name, rating=average, message=message)

@app.route('/debug')
def debug():
    return render_template("main.html",data=scrape())


def scrape():
    #page = requests.get("https://api.allorigins.win/raw?url=https://strav.nasejidelna.cz/0254/login")
    page = requests.get("https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=https://strav.nasejidelna.cz/0254/login")
    soup = BeautifulSoup(page.text, "html.parser")

    days = soup.find_all("div", class_="jidelnicekDen")

    data = [] # foods from Hlavni canteen, not modrany

    for day in days:
        #data.append(day.find_all("div", class_ = "jidelnicekTop semibold")[0].text.strip())
        date = day.find_all("div", class_ = "jidelnicekTop semibold")[0].text.strip()

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
                    #return repr(food)

                    #food = food.replace(", čaj, šťáva, ovoce, salát", "") nefacha ;(

                    # Generovany chatem GPT{
                    food = re.sub(r"[,\s\xa0]*čaj.*$", "", food, flags=re.IGNORECASE) # odstrani vse po ", caj"
                    food = re.sub(r"\s+", " ", food)
                    food = ' '.join(food.split())
                    #}

                    foods.append((food,get_image(food)))
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
        food_item = item[1]  # name column
        food_item = food_item.replace(' ', '_')
        ret.append(food_item)

    return render_template("foods.html", foods=ret)


@app.route('/about')
def about():
    return "Nothing here yet."

@app.route('/contacts')
def contacts():
    return "<a href=\"mailto:syzonenko.semen@postupicka.cz\">syzonenko.semen@postupicka.cz</a>"
