#This code is executed on a different server due to PythonAnywhere not allowing most URLS to be accessed

import subprocess, requests
from bs4 import BeautifulSoup
from flask import Flask, request, redirect
from strava_cz import (
    StravaCZ,
    AuthenticationError,
    InvalidMealTypeError,
    InsufficientBalanceError,
    StravaAPIError,
    MealType,
    OrderType
)

app = Flask(__name__)

ALLOWED_APPS = ["kredit.exe", "login.exe","get_ordered_foods.exe", "order.exe"]

@app.route("/")
def main():
   return redirect('https://jidelna.eu.pythonanywhere.com')


@app.route("/iCanteen/<app>/<path:url>")
def credit(app, url):
    if app not in ALLOWED_APPS:
       return "App not allowed"
    args = url.split(',')

    result = subprocess.run(
        [f"/home/ubuntu/{app}", *args],
        capture_output=True,
        text=True
    )
    return result.stdout



@app.route("/strava/login/<username>,<password>,<canteen_number>")
def strava_login(username, password, canteen_number):
    try:
        strava_login_internal(username,password,canteen_number)
    except AuthenticationError as e:
        return "0"
    return "1"

@app.route("/strava/kredit/<username>,<password>,<canteen_number>")
def strava_kredit(username, password, canteen_number):
    strava = strava_login_internal(username, password, canteen_number)
    return str(strava.user.balance)

@app.route("/strava/scrape/<canteen_number>")
def Strava_scrape(canteen_number):

    #page = requests.get(f"https://sparkling-sun-0a6e.humanhumanovic.workers.dev/?url=app.strava.cz/jidelnicky?jidelna={canteen_number}")

    url = "https://app.strava.cz/api/jidelnickyPage"
    page = requests.post(
        url,
        json={ 
            "cislo": canteen_number,
            "lang": "CZ" 
        }
    )
    soup = BeautifulSoup(page.text, "html.parser")

    days = soup.find_all("div", class_="relative rounded-2xl border border-edge bg-surface-100 px-1.5 py-4 tablet:px-4 tablet:py-5 desktop:px-6")

    data = []

    for day in days:
        date = day.get('id')
        
        foods = []

        food_containers = day.find_all("div", class_="space-y-0.5")
        for food in food_containers:
            actual_food = food.find("span", class_="mx-auto")
            food_type = actual_food.find("span", class_="first-letter:uppercase tablet:inline-block")
            food_name = actual_food.find_all("span")[-1]
            if food_type!="Doplněk " and food_type!="Polévka ":
                foods.append(food_name)
        data.append((date,foods))
    return data




def strava_login_internal(username, password, canteen_number):
    strava = StravaCZ(
            username=username,
            password=password,
            canteen_number = canteen_number
        )
    return strava

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)