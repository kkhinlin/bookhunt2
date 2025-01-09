from transformers import BertTokenizer, BertModel
import torch
from models import db, Book, UserBooks
import random
import numpy as np

# Initialize the BERT tokenizer and model
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model = BertModel.from_pretrained('bert-base-uncased')

def get_bert_embeddings(text):
    """Generate BERT embeddings for the input text."""
    # Tokenize the input text and convert it into input tensors
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=512)
    
    # Get the model's output
    with torch.no_grad():
        outputs = model(**inputs)

    # Extract the embeddings from the [CLS] token
    embeddings = outputs.last_hidden_state[:, 0, :].squeeze().numpy()
    return embeddings

def cosine_similarity(embeddings1, embeddings2):
    """Calculate the cosine similarity between two embedding vectors."""
    if embeddings1 is None or embeddings2 is None:
        return 0
    dot_product = np.dot(embeddings1, embeddings2)
    norm1 = np.linalg.norm(embeddings1)
    norm2 = np.linalg.norm(embeddings2)
    return dot_product / (norm1 * norm2) if norm1 and norm2 else 0

def get_recommendations(query, books, user_books, genre=None, top_n=10):
    """
    Generate book recommendations based on the user's query, considering the book descriptions, genre, etc.
    
    Args:
        query (str): Search query from the user.
        books (list): List of books to recommend from.
        user_books (list): Books that the user has already read or interacted with.
        genre (str, optional): Genre to filter recommendations.
        top_n (int, optional): Number of top recommendations to return.
        
    Returns:
        list: A list of recommended books.
    """
    if not query:
        return []

    # Process the query with BERT
    query_embeddings = get_bert_embeddings(query)

    # Generate a list of books with similarity scores
    recommendations = []

    for book in books:
        # Skip books the user has already read or interacted with
        if book.id in [ub.book_id for ub in user_books]:
            continue

        # Filter by genre if applicable
        if genre and genre != book.genre:
            continue

        # Ensure the book has a valid description (fallback to default description if missing)
        description = book.description if book.description else "No description available"

        # Get BERT embeddings for the book description
        book_embeddings = get_bert_embeddings(description)

        # Compute cosine similarity between the query and book description embeddings
        similarity = cosine_similarity(query_embeddings, book_embeddings)

        # Optionally consider book's number of pages or subjects in recommendations
        if book.number_of_pages:
            similarity += np.log(book.number_of_pages + 1) / 500  # Apply a logarithmic scale to number of pages
        
        if book.subjects:
            # Boost similarity if the book's subjects match the query
            for subject in book.subjects:
                if subject.lower() in query.lower():
                    similarity += 0.1  # Small boost for subject match

        # Add the book and its adjusted similarity score to the recommendations
        recommendations.append((book, similarity))

    # Sort the books by similarity score and return only the top recommendation
    recommendations.sort(key=lambda x: x[1], reverse=True)

    # Return only the top recommendation (just one book)
    return [recommendations[0][0]] if recommendations else []

def record_feedback(book, feedback):
    """
    Record feedback on a book (e.g., liked or rejected).
    
    Args:
        book (Book): Book being reviewed.
        feedback (str): User's feedback ('like', 'reject', etc.)
    """
    user_book = UserBooks.query.filter_by(book_id=book.id).first()

    if user_book:
        user_book.feedback = feedback
    else:
        # Set a default status for new entries, e.g., 'pending'
        user_book = UserBooks(book_id=book.id, feedback=feedback, status='pending')  # Ensure status is set
        db.session.add(user_book)

    db.session.commit()

def generate_new_recommendations(query, books, user_books, genre=None, top_n=10):
    """
    Generate new recommendations, avoiding books that have been rejected.
    
    Args:
        query (str): Search query to base recommendations on.
        books (list): List of available books for recommendations.
        user_books (list): Books already read or interacted with.
        genre (str, optional): Genre to filter recommendations.
        top_n (int, optional): Number of top recommendations to return.
        
    Returns:
        list: A list of new recommended books.
    """
    # If a book has been rejected previously, avoid it
    rejected_books = [ub.book_id for ub in user_books if ub.feedback == 'reject']

    # Filter out the rejected books from the recommendations
    valid_books = [book for book in books if book.id not in rejected_books]

    # Generate new recommendations with updated filtering
    return get_recommendations(query, valid_books, genre, top_n)
