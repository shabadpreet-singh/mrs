from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import pickle
import requests
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)


# MovieReview model for storing ratings and comments
class MovieReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_title = db.Column(db.String(255), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    user = db.relationship('User', backref=db.backref('reviews', lazy=True))
    
with app.app_context():
    db.create_all()


# Load the data and similarity matrix
movies_dict = pickle.load(open('movie_dict.pkl', 'rb'))
similarity = pickle.load(open('similarity.pkl', 'rb'))

OMDB_API_KEY = '318bca14'

def get_movie_details(title):
    url = f"http://www.omdbapi.com/?t={title}&apikey={OMDB_API_KEY}"
    response = requests.get(url)
    data = response.json()
    if data['Response'] == 'True':
        return {
            'title': data['Title'],
            'poster': data['Poster'],
            'rating': data.get('imdbRating', 'N/A'),
            'plot': data.get('Plot', 'N/A'),
            'cast': data.get('Actors', 'N/A'),
            'director': data.get('Director', 'N/A'),
            'runtime': data.get('Runtime', 'N/A'),
            'genre': data.get('Genre', 'N/A'),
            'link': f"https://www.imdb.com/title/{data['imdbID']}/"
        }
    return None

@app.route('/')
def index():
    movie_title = session.get('current_movie', '')
    recommendations = []
    if movie_title:
        response = requests.post('http://127.0.0.1:5000/recommend', json={'movie': movie_title})
        if response.status_code == 200:
            recommendations = response.json()
    return render_template('index.html', movieTitle=movie_title, recommendations=recommendations)

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    movie = data.get('movie')
    if movie:
        session['current_movie'] = movie
        titles = list(movies_dict['title'].values())
        if movie in titles:
            movie_index = titles.index(movie)
            distances = similarity[movie_index]
            movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]
            recommendations = [titles[i[0]] for i in movies_list]
            movies_details = [get_movie_details(title) for title in recommendations]
            return jsonify(movies_details)
        else:
            return jsonify([])
    return jsonify([])

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('query', '')
    titles = list(movies_dict['title'].values())
    suggestions = [title for title in titles if query.lower() in title.lower()]
    return jsonify(suggestions[:10])

@app.route('/submit_review', methods=['POST'])
def submit_review():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    movie_title = request.form.get('movie_title')
    rating = int(request.form.get('rating', 0))
    comment = request.form.get('comment', '')
 
    # Debugging statements
    print(f"Movie Title: {movie_title}")
    print(f"Rating: {rating}")
    print(f"Comment: {comment}")

    if not movie_title:
        return "Movie title is required.", 400

    new_review = MovieReview(user_id=user_id, movie_title=movie_title, rating=rating, comment=comment)
    db.session.add(new_review)
    db.session.commit()

    return redirect(url_for('movie_details', title=movie_title))


@app.route('/movie_details')
def movie_details():
    title = request.args.get('title')
    if not title:
        return "Movie title is required.", 400

    response = requests.get(f'http://www.omdbapi.com/?t={title}&apikey={OMDB_API_KEY}')
    movie = response.json()
    if movie['Response'] == 'False':
        return "Movie not found.", 404
    
    reviews = MovieReview.query.filter_by(movie_title=title).all()
    
    return render_template('movie_details.html', movie=movie, reviews=reviews)


@app.route('/clear_session')
def clear_session():
    session.pop('current_movie', None)
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        return 'Invalid username or password', 401
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if the username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('register.html', message="User is already registered.")
        
        # Create new user if username does not exist
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
