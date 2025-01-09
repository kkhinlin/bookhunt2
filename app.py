from flask import Flask, request, jsonify, render_template
from models import db, Book, Review, Genre, Author, UserBooks
from schemas import BookSchema, ReviewSchema, GenreSchema, AuthorSchema
from config import Config
from recommendations import get_recommendations, record_feedback
from routes import api
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(Config)

# Initialize the database
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Initialize Marshmallow schemas
book_schema = BookSchema()
books_schema = BookSchema(many=True)
review_schema = ReviewSchema()
reviews_schema = ReviewSchema(many=True)
genre_schema = GenreSchema()
genres_schema = GenreSchema(many=True)
author_schema = AuthorSchema()

# Use app context to create tables at startup
with app.app_context():
    db.create_all()

# Register the API blueprint
app.register_blueprint(api)

# API Routes
@app.route('/api/books', methods=['GET'])
def get_books():
    books = Book.query.all()
    return books_schema.jsonify(books)

@app.route('/api/books/<string:book_id>', methods=['GET'])
def get_book(book_id):
    book = Book.query.get_or_404(book_id)
    return book_schema.jsonify(book)

# Reviews Routes
@app.route('/api/reviews', methods=['POST'])
def add_review():
    data = request.get_json()
    book_id = data.get('book_id')
    rating = data.get('rating')
    comment = data.get('comment', '')
    
    review = Review(book_id=book_id, rating=rating, comment=comment)
    db.session.add(review)
    db.session.commit()
    
    return review_schema.jsonify(review), 201

@app.route('/api/reviews/book/<string:book_id>', methods=['GET'])
def get_reviews(book_id):
    reviews = Review.query.filter_by(book_id=book_id).all()
    return reviews_schema.jsonify(reviews)

# Genres Routes
@app.route('/api/genres', methods=['GET'])
def get_genres():
    genres = Genre.query.all()
    return genres_schema.jsonify(genres)

# Authors Routes
@app.route('/api/authors/<string:author_id>', methods=['GET'])
def get_author(author_id):
    author = Author.query.get_or_404(author_id)
    return author_schema.jsonify(author)

# Book Recommendation Route
@app.route('/api/recommend', methods=['GET'])
def recommend_books():
    query = request.args.get('query', '').strip()
    genre = request.args.get('genre', '')  
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    user_books = UserBooks.query.filter_by(status="read").all()
    books = Book.query.all()
    
    recommended_books = get_recommendations(query, books, user_books, genre)
    
    if not recommended_books:
        return jsonify({"message": "No recommendations found"}), 404
    
    return books_schema.jsonify(recommended_books)

# Feedback Route
# Feedback Route
@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    """
    Handles feedback for accepted or rejected books and updates the reading list if necessary.
    """
    data = request.get_json()
    book_id = data.get('book_id')
    feedback = data.get('feedback')  # 'accept' or 'reject'

    if not book_id or not feedback:
        return jsonify({"error": "Book ID and feedback are required"}), 400

    # Record feedback
    record_feedback(book_id, feedback)

    # If feedback is 'accept', add the book to the reading list
    if feedback == 'accept':
        # Check if the book is already in the reading list
        existing_entry = UserBooks.query.filter_by(book_id=book_id, status="to_read").first()
        if not existing_entry:
            # Add the book to the reading list
            new_entry = UserBooks(
                book_id=book_id,
                status="to_read",  # Mark as "to read"
                opinion=None  # No opinion yet
            )
            db.session.add(new_entry)
            db.session.commit()

    return jsonify({"message": "Feedback recorded and reading list updated successfully"}), 200

# Frontend Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/recommendations', methods=['GET'])
def recommendations_page():
    query = request.args.get('query', '').strip()
    genre = request.args.get('genre', '').strip()

    print(f"Query: {query}, Genre: {genre}")  # For debugging

    # If no query is provided, just show the input form
    if not query:
        return render_template('recommendations.html', book=None, query=query, genre=genre)

    # Get past books the user has interacted with
    user_books = UserBooks.query.filter_by(status="read").all()
    books = Book.query.all()

    # Generate recommendations if query is provided
    recommended_books = get_recommendations(query, books, user_books, genre)

    if not recommended_books:
        # Render no recommendations page if no books found
        return render_template('no_recommendations.html', query=query, genre=genre)

    # Debugging: Print the number of recommended books
    print(f"Number of recommendations: {len(recommended_books)}")

    # Pass only the top recommendation (first book in the list)
    recommended_book = recommended_books[0] if recommended_books else None

    return render_template('recommendations.html', book=recommended_book, query=query, genre=genre)

@app.route('/past_reads', methods=['GET', 'POST'])
def past_reads_page():
    if request.method == 'POST':
        data = request.get_json()
        book_title = data.get('book_title')  # Use 'book_title' instead of 'book_id'
        opinion = data.get('opinion', '')

        if not book_title:
            return jsonify({"error": "Book title is required"}), 400

        # Find the book by title
        book = Book.query.filter_by(title=book_title).first()

        if not book:
            return jsonify({"error": "Book not found"}), 404

        # Check if the book already exists in the user's past reads
        existing_user_book = UserBooks.query.filter_by(book_id=book.id, status="read").first()

        if existing_user_book:
            existing_user_book.opinion = opinion
            db.session.commit()
            return jsonify({"message": "Opinion updated successfully"}), 200
        else:
            user_book = UserBooks(book_id=book.id, status="read", opinion=opinion)
            db.session.add(user_book)
            db.session.commit()
            return jsonify({"message": "Past read added successfully"}), 201

    # If it's a GET request, show the past reads
    user_books = UserBooks.query.filter_by(status="read").all()
    # Add book title to each user_book
    past_reads = []
    for user_book in user_books:
        book = Book.query.get(user_book.book_id)
        if book:
            past_reads.append({
                'book_title': book.title,
                'status': user_book.status,
                'opinion': user_book.opinion
            })

    return render_template('past_reads.html', past_reads=past_reads)

# Reading List Page
@app.route('/reading_list', methods=['GET'])
def reading_list_page():
    user_books = UserBooks.query.filter_by(status="reading").all()
    reading_list = []
    
    for user_book in user_books:
        book = db.session.get(Book, user_book.book_id)  # Use Session.get()
        if book:
            reading_list.append({
                'title': book.title,
                'author': book.author if book.author else "Unknown Author",
                'genre': book.genre if book.genre else "Unknown Genre",
            })
    
    return render_template('reading_list.html', reading_list=reading_list)

@app.route('/book/<string:book_id>', methods=['GET'])
def book_details(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('book_details.html', book=book)

#lol
if __name__ == '__main__':
    app.run(debug=True)