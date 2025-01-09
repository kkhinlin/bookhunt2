import os
import requests
from dotenv import load_dotenv
from models import db, Book, Author, Genre
from app import app

# Load environment variables from .env
load_dotenv()

# Access the Google Books API key
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")


def fetch_books_from_google_books(query="fiction", max_results=1000, batch_size=40):
    """
    Fetches books from the Google Books API in batches.

    Args:
        query (str): The search term.
        max_results (int): The maximum number of books to fetch.
        batch_size (int): The number of books to fetch per API call.

    Returns:
        list: A list of books retrieved from the API.
    """
    books = []
    start_index = 0

    while len(books) < max_results:
        url = (
            f"https://www.googleapis.com/books/v1/volumes?q={query}&startIndex={start_index}&maxResults={batch_size}&key={GOOGLE_BOOKS_API_KEY}"
        )
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from Google Books API: {e}")
            break

        items = data.get("items", [])
        if not items:
            print("No more books found.")
            break

        books.extend(items)
        print(f"Fetched batch starting at index {start_index} with {len(items)} books.")
        start_index += batch_size

    return books[:max_results]


def save_books_to_db(books):
    """
    Saves a list of books to the database, including author, genre, and metadata.

    Args:
        books (list): A list of book dictionaries retrieved from the Google Books API.
    """
    with app.app_context():
        for book in books:
            volume_info = book.get("volumeInfo", {})
            title = volume_info.get("title")
            authors = volume_info.get("authors", [])
            description = volume_info.get("description", "No description available.")
            published_year = (
                volume_info.get("publishedDate", "").split("-")[0] if "publishedDate" in volume_info else None
            )

            # Handle authors
            author_id = None
            if authors:
                for author_name in authors:
                    author = Author.query.filter_by(name=author_name).first()
                    if not author:
                        author = Author(name=author_name)
                        db.session.add(author)
                        db.session.commit()
                    author_id = author.id

            # Handle genre (default to "Unknown")
            genre = Genre.query.filter_by(name="Unknown").first()
            if not genre:
                genre = Genre(name="Unknown")
                db.session.add(genre)
                db.session.commit()

            # Add book to database
            if title:
                existing_book = Book.query.filter_by(title=title).first()
                if not existing_book:
                    new_book = Book(
                        title=title,
                        description=description,
                        published_year=published_year,
                        author_id=author_id,
                        genre_id=genre.id,
                    )
                    db.session.add(new_book)

        db.session.commit()
        print(f"{len(books)} books saved to the database.")


if __name__ == "__main__":
    # Fetch and save books
    print("Fetching books from Google Books API...")
    books = fetch_books_from_google_books(query="fiction", max_results=1000, batch_size=40)
    if books:
        print(f"Fetched {len(books)} books. Saving to database...")
        save_books_to_db(books)
    else:
        print("No books found or failed to fetch books.")