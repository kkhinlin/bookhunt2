from flask import Blueprint, request, jsonify
from models import db, Book, UserBooks
from recommendations import generate_new_recommendations  # Import the recommendation function

api = Blueprint('api', __name__)

@api.route('/api/past_reads', methods=['POST'])
def add_past_read():
    data = request.get_json()
    print(f"Received data: {data}")  # Debugging line to log the incoming request data

    book_title = data.get('book_title')  # User-provided title
    opinion = data.get('opinion', '')  # Opinion is optional

    if not book_title:
        return jsonify({'error': 'book_title is required'}), 400

    # Set the default status to 'read' if not provided
    status = 'read'

    # Check if the book exists by title
    book = Book.query.filter_by(title=book_title).first()

    if not book:
        # If the book doesn't exist, create a new book in the Book table
        book = Book(title=book_title)
        db.session.add(book)
        db.session.commit()

    # Check if the book is already in the UserBooks table
    user_book = UserBooks.query.filter_by(book_id=book.id).first()

    if user_book:
        # If it exists, update the status and opinion
        user_book.status = status
        user_book.opinion = opinion
        db.session.commit()
        return jsonify({'message': 'Book status and opinion updated successfully'}), 200
    else:
        # If it doesn't exist, add a new entry
        new_user_book = UserBooks(book_id=book.id, status=status, opinion=opinion)
        db.session.add(new_user_book)
        db.session.commit()
        return jsonify({'message': 'Past read added successfully'}), 201


@api.route('/api/past_reads', methods=['GET'])
def view_past_reads():
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    try:
        user_books_paginated = UserBooks.query.paginate(page=page, per_page=per_page, error_out=False)
    except Exception as e:
        return jsonify({'error': f'Error during pagination: {str(e)}'}), 500

    # Serialize paginated results
    result = []
    for user_book in user_books_paginated.items:
        # Get the book by ID
        book = Book.query.get(user_book.book_id)
        if book:
            result.append({
                'id': user_book.id,
                'book_title': book.title,  # Safely use the book title
                'status': user_book.status,
                'opinion': user_book.opinion
            })
        else:
            # If the book doesn't exist, handle it gracefully (optional)
            result.append({
                'id': user_book.id,
                'book_title': 'Unknown Title',  # Default value if the book is missing
                'status': user_book.status,
                'opinion': user_book.opinion
            })

    return jsonify({
        'items': result,
        'total': user_books_paginated.total,
        'pages': user_books_paginated.pages,
        'current_page': user_books_paginated.page
    }), 200


@api.route('/api/feedback', methods=['POST'])
def feedback():
    """
    Handles feedback for accepted or rejected books and connects accepted books to the reading list.
    """
    data = request.get_json()

    if not data or 'book_id' not in data or 'feedback' not in data:
        return jsonify({'error': 'Invalid data'}), 400

    book_id = data['book_id']
    feedback = data['feedback']  # 'accept', 'reject', or other types of feedback
    status = data.get("status", "pending")  # Default to "pending" if not provided

    # Check if the book already exists in the user's records
    user_book = UserBooks.query.filter_by(book_id=book_id).first()

    if user_book:
        user_book.feedback = feedback
        # Update the status if the feedback is 'accept'
        if feedback == 'accept' and user_book.status != 'to_read':
            user_book.status = 'to_read'
    else:
        # Create a new record if it doesn't exist
        user_book = UserBooks(
            book_id=book_id,
            feedback=feedback,
            status='to_read' if feedback == 'accept' else status
        )
        db.session.add(user_book)

    db.session.commit()

    return jsonify({'message': 'Feedback saved successfully!'})


@api.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """
    Get book recommendations excluding rejected books.
    """
    query = request.args.get('query', '')
    genre = request.args.get('genre', None)
    top_n = int(request.args.get('top_n', 10))

    # Fetch all books
    books = Book.query.all()
    user_books = UserBooks.query.all()  # Get all user books

    # Get rejected books
    rejected_books = [ub.book_id for ub in user_books if ub.feedback == 'reject']

    # Filter out rejected books
    valid_books = [book for book in books if book.id not in rejected_books]

    # Generate recommendations using the function from recommendations.py
    recommended_books = generate_new_recommendations(query, valid_books, user_books, genre, top_n)

    # Serialize recommendations
    recommendations = []
    for book in recommended_books:
        recommendations.append({
            'id': book.id,
            'title': book.title,
            'description': book.description
        })

    return jsonify({'recommendations': recommendations})