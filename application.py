""" distribution code starts here"""
import os
import requests
import json

from flask import Flask, session, render_template, request, redirect, session
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from helper import login_required

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))
"""distribution code ends here"""

@app.route("/")
def index():
    session.clear()
    return render_template("enter-login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()

    """only rendering the registration form"""
    if request.method == "GET":
        return render_template("enter-register.html", action = "register")

    """actually registering"""
    # username not provided
    if request.form.get("name") == None:
        return render_template("alert-register.html", msg="Looks like you didn't select your username.")

    # password not provided
    if request.form.get("password") == None:
        return render_template("alert-register.html", msg="Looks like you didn't select your password.")
    
    # passcheck not provided
    if request.form.get("passcheck") == None:
        return render_template("alert-register.html", msg="You need to confirm your password.")

    # password and passcheck not identical
    if request.form.get("password") != request.form.get("passcheck"):
        return render_template("alert-register.html", msg="Your password and passcheck do not match.")

    # username already used
    name = request.form.get("name")
    if db.execute("SELECT * FROM users WHERE name = :name", {'name': name}).fetchone() != None:
        return render_template("alert-register.html", msg="Someone else already has this username. Choose another.")

    # all is good - register
    password = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)

    db.execute("INSERT INTO users (name, password) VALUES (:name, :password)",
               {"name": name, "password": password})
    db.commit()
    return redirect("/")
    # return f"User <b>{name}</b> successfully registered HAHAHAHA."

@app.route("/login", methods=["POST"])
def login():
    # forget previous user
    session.clear()

    """check login credentials"""
    # username not provided
    if request.form.get("name") == None:
        return render_template("alert-login.html", msg="Your username, please.")

    # password not provided
    if request.form.get("password") == None:
        return render_template("alert-login.html", msg="Your password, please.")

    # check password
    name = request.form.get("name")
    row = db.execute("SELECT * FROM users WHERE name = :name", {'name': name}).fetchone()
    if row is None or not check_password_hash(row["password"], request.form.get("password")):
        return render_template("alert-login.html", msg="Incorrect username/password")

    # remember the logged in user
    session["user_id"] = row["user_id"]
    session["username"] = row["name"]

    return redirect("/search")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    if request.method == "GET":
        return render_template("results.html", username=session["username"]);
    
    """query db for books"""
    if request.form.get("search") is None:
        return "no key to search by."
    
    search = "%" + request.form.get("search") + "%"
    rows = db.execute("SELECT * FROM books WHERE UPPER(title) LIKE UPPER(:search) OR UPPER(author) LIKE UPPER(:search) OR UPPER(isbn) LIKE UPPER(:search)",
        {'search': search}).fetchall()
    if len(rows) == 0:
        return render_template("results.html", rows=None, username=session["username"])
    return render_template("results.html", rows=rows, username=session["username"])

@app.route("/book/<string:book_id>")
@login_required
def book(book_id):
    # session update about the book
    session['reving_users'] = []
    session["book"] = db.execute("SELECT * FROM books WHERE book_id = :book_id", {'book_id': book_id}).fetchone()
    session['reviews'] = db.execute("SELECT name, text, rating FROM reviews r JOIN users u ON r.user_id = u.user_id  WHERE book_id = :book_id ORDER BY review_id DESC", 
        {'book_id': book_id}).fetchall()
    reving_users = db.execute("SELECT user_id FROM reviews WHERE book_id = :book_id", {'book_id': session['book']['book_id']}).fetchall()
    for user in reving_users:
        session['reving_users'].append(user.user_id)
    
    # user's permission to write a new review for the book
    if session['user_id'] in session['reving_users']:
        permission = False
    else:
        permission = True

    # get data from goodreads api and add it to session
    goodreads = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": os.getenv("GOODREADS_KEY"), "isbns": session['book']['isbn']})
    goodreads = goodreads.json()['books'][0]
    session['goodreads'] = goodreads
    
    return render_template("book.html", book=session["book"], reviews=session['reviews'], goodreads=session['goodreads'], permission=permission) 

@app.route("/book/<string:book_id>/addreview", methods=["GET", "POST"])
@login_required
def addreview(book_id): # no need to use book_id parameter, because all book info is in session
    # GET -> only rendering the review form
    if request.method == "GET":
        return render_template("addreview.html", book=session["book"], reviews=session['reviews'], goodreads=session['goodreads'])

    # POST -> adding the review to db
    if request.form.get("text") is None:
        return render_template("alert-review.html", msg="Write a word or two about the book.")
    
    if request.form.get("rating") is None:
        return render_template("alert-review.html", msg="Rate the book.")

    text = request.form.get("text")
    rating = request.form.get("rating")

    # only one review per book pre user!
    check = db.execute("SELECT * FROM reviews WHERE book_id = :book_id AND user_id = :user_id",
                        {'book_id': session['book']['book_id'], 'user_id': session['user_id']}).fetchone()
    if check is not None:
        return render_template("alert-review.html", msg="Only one review per book per user.")
    
    # finally commit to the db
    db.execute("INSERT INTO reviews (text, rating, book_id, user_id) VALUES (:text, :rating, :book_id, :user_id)", 
            {'text': text, 'rating': rating, 'book_id': session['book']['book_id'], 'user_id': session['user_id']})
    db.commit()
    
    return redirect(f"/book/{session['book']['book_id']}")
   
# api to access our data
@app.route("/api/<string:isbn>")
def api(isbn):
    # querying our db
    ourData = db.execute("SELECT title, author, year, isbn FROM books WHERE isbn = :isbn", {'isbn': isbn}).fetchone()
    if ourData is None:
        return json.dumps({
            "status": 404,
            "message": "No book with such ISBN in our database."
        }), 404

    # querying Goodreads
    goodreadsData = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": os.getenv("GOODREADS_KEY"), "isbns": isbn})
    goodreadsData = goodreadsData.json()['books'][0]
    print("gr data:", goodreadsData)
    
    # assembly our response
    return json.dumps({
        "author": ourData['author'],
        "title": ourData['title'],
        "year": ourData['year'],
        "isbn": ourData['isbn'],
        "review_count": goodreadsData['reviews_count'],
        "average_score": goodreadsData['average_rating']
    })