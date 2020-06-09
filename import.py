import csv
import os

from flask import Flask, session, render_template, request
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

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

def main():

  # create the tables
  print("creating tables...")
  db.execute("CREATE TABLE users (user_id SERIAL PRIMARY KEY, name VARCHAR NOT NULL, password VARCHAR NOT NULL)")
  db.execute("CREATE TABLE books (book_id SERIAL PRIMARY KEY, isbn VARCHAR NOT NULL,  title VARCHAR NOT NULL, author VARCHAR NOT NULL, year INTEGER NOT NULL)")
  db.execute("CREATE TABLE  reviews (review_id SERIAL PRIMARY KEY, book_id INTEGER NOT NULL, user_id INTEGER NOT NULL, rating INTEGER NOT NULL, text TEXT NOT NULL)")
  # db.commit()
  print("...tables created.")

  # import books from books.csv
  print("importing books...")
  with open("books.csv") as file:
    books = csv.reader(file)
    next(books)
    for isbn, title, author, year in books:
      year = int(year)
      db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
                    {"isbn": isbn, "title": title, "author": author, "year": year})
    db.commit()
  print("...books imported.")

if __name__ == "__main__":
  main()