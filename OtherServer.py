#This code is executed on a different server due to PythonAnywhere not allowing most URLS to be accessed

import subprocess
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
        strava = StravaCZ(
            username=username,
            password=password,
            canteen_number = canteen_number
        )
    except AuthenticationError as e:
        return "0"
    return "1"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)