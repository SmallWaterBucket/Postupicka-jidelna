#This code is executed on a different server due to PythonAnywhere not allowing most URLS to be accessed

import json
import subprocess, requests
from bs4 import BeautifulSoup
from flask import Flask, request, redirect, render_template
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

@app.route("/strava/get_ordered_foods/<username>,<password>,<dates>,<canteen_number>")
def strava_get_ordered_foods(username, password, dates, canteen_number):
    strava = strava_login_internal(username, password, canteen_number)
    ordered_indexes = []
    dates = dates.split('.')
    days = strava.menu.get_days()
    for i in range(len(dates)):
        ordered_indexes.append('')
        date_index = -1

        menu = strava.menu.get_by_date(dates[i])

        if menu:
            for meal_index in range(len(menu["meals"])):
                meal = menu["meals"][meal_index]
                if meal["ordered"]:
                    ordered_indexes[-1] = meal_index
    if len(ordered_indexes) < 1:
        return ""
    return ';'.join(ordered_indexes) + ";"

@app.route("/strava/order/<username>,<password>,<date>,<food>,<canteen_number>")
def strava_oder_food(username, password, date, food, canteen_number):
    strava = strava_login_internal(username, password, canteen_number)
    days = strava.menu.get_days()
    food = int(food)
    menu = strava.menu.get_by_date(date)
    if not menu:
        return "Date not found"
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)