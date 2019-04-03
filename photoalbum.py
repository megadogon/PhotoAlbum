import io
import os
from random import choice

from flask import Flask, render_template, request, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect, secure_filename
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = "upload"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(80), unique=False, nullable=False)
    surname = db.Column(db.String(80), unique=False, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), unique=False, nullable=False)

    def __repr__(self):
        return '<User {} {} {} {}>'.format(
            self.id, self.username, self.name, self.surname)


class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    user = db.relationship('User', backref=db.backref('albums', cascade="all"))
    title = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return '<Album {}>'.format(self.id)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return '<Category {}>'.format(self.id)


class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id', ondelete="CASCADE"), nullable=False)
    album = db.relationship('Album', backref=db.backref('photos', cascade="all"))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category', backref=db.backref('photos'))
    picture = db.Column(db.LargeBinary)
    mimetype = db.Column(db.String(80))
    filename = db.Column(db.String(250))

    def __repr__(self):
        return '<Photo {}>'.format(self.id)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id', ondelete="CASCADE"), nullable=False)
    photo = db.relationship('Photo', backref=db.backref('comments', cascade="all"))
    text = db.Column(db.Text())

    def __repr__(self):
        return '<Comment {}>'.format(self.id)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    user = db.relationship('User', backref=db.backref('votes', cascade="all"))
    good_photo_id = db.Column(db.Integer, db.ForeignKey('photo.id', ondelete="CASCADE"), nullable=False)
    good_photo = db.relationship('Photo', foreign_keys=[good_photo_id],
                                 backref=db.backref('good_photos', cascade="all"))
    bad_photo_id = db.Column(db.Integer, db.ForeignKey('photo.id', ondelete="CASCADE"), nullable=False)
    bad_photo = db.relationship('Photo', foreign_keys=[bad_photo_id], backref=db.backref('bad_photos', cascade="all"))


db.create_all()

if User.query.first() == None:
    admin = User(
        username='admin',
        name="Дмитрий",
        surname="Килиевич",
        email="dkiliyevich@mail.ru",
        password_hash=generate_password_hash('q'))
    db.session.add(admin)
    db.session.commit()


@app.route('/')
@app.route('/index')
def index():
    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['username'] = username
            session['user_id'] = user.id
            return redirect('/my_albums')

        errors = ['Неверное имя пользователя или пароль']
        return render_template('login.html', title='Авторизация', errors=errors)
    else:
        return render_template('login.html', title='Авторизация')


@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if request.method == 'GET':
        return render_template('registration.html', title='Регистрация')
    elif request.method == 'POST':
        username = request.form['username']
        name = request.form['name']
        surname = request.form['surname']
        email = request.form['email']
        password1 = request.form['password1']
        password2 = request.form['password2']

        errors = []
        if password1 != password2:
            errors.append('Пароли не совпадают')
        if User.query.filter_by(username=username).first():
            errors.append('Пользователь с таким именем уже существует')
        if User.query.filter_by(email=email).first():
            errors.append('Пользователь с таким e-mail уже существует')
        if len(errors) > 0:
            return render_template('registration.html', title='Регистрация', errors=errors,
                                   username=username,
                                   name=name,
                                   surname=surname,
                                   email=email)

        user = User(
            username=username,
            name=name,
            surname=surname,
            email=email,
            password_hash=generate_password_hash(password1),
        )

    db.session.add(user)
    db.session.commit()

    # авто-логин после регистрации
    session['username'] = user.username
    session['user_id'] = user.id
    return redirect('/my_albums')


def getCurrentUser():
    if 'user_id' not in session:
        return None
    user_id = session['user_id']
    return User.query.filter_by(id=user_id).first()


@app.route('/my_albums', methods=['GET'])
def my_albums():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    albums = Album.query.filter_by(user_id=user.id).order_by(Album.title).all()

    return render_template('my_albums.html', title='Мои альбомы', user=user, albums=albums)


@app.route('/add_album', methods=['POST'])
def add_album():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    title = request.form['title']
    album = Album(
        title=title,
        user_id=user.id)

    db.session.add(album)
    db.session.commit()
    return redirect("/my_album/" + str(album.id))


@app.route('/delete_album/<int:album_id>', methods=['GET'])
def delete_album(album_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')
    album = Album.query.filter_by(user_id=user.id, id=album_id).first_or_404()
    db.session.delete(album)
    db.session.commit()
    return redirect("/my_albums")


@app.route('/my_album/<int:album_id>', methods=['GET'])
def my_album(album_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    album = Album.query.filter_by(user_id=user.id, id=album_id).first_or_404()
    photos = Photo.query.filter_by(id=user.id).order_by(Photo.id).all()

    for i in range(len(photos)):
        photo = photos[i]
        photo.index = i
        if i == 0:
            photo.active = "active"
        else:
            photo.active = ""

    return render_template('my_album.html', title='Мои альбомы', user=user, album=album, photos=photos)


@app.route('/edit_album/<int:album_id>', methods=['POST'])
def edit_album(album_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')
    title = request.form['title']
    album = Album.query.filter_by(user_id=user.id, id=album_id).first_or_404()
    album.title = title
    db.session.commit()
    return redirect("/my_album/" + str(album_id))


ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/add_photo/<int:album_id>', methods=['POST'])
def add_photo(album_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    Album.query.filter_by(user_id=user.id, id=album_id).first_or_404()

    file = request.files['file']

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        fullfilename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(fullfilename)

        with open(fullfilename, "rb") as f:
            data = f.read()

        os.remove(fullfilename)

        photo = Photo(
            album_id=album_id,
            picture=data,
            mimetype=file.content_type,
            filename=filename
        )

        db.session.add(photo)
        db.session.commit()

    return redirect("/photo/" + str(photo.id))


@app.route('/photo_img/<int:photo_id>', methods=['GET'])
def photo_img(photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    photo = Photo.query.filter_by(id=photo_id).first_or_404()

    return send_file(
        io.BytesIO(photo.picture),
        mimetype=photo.mimetype,
        as_attachment=True,
        attachment_filename=photo.filename)


@app.route('/photo/<int:photo_id>', methods=['GET'])
def photo(photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')
    photo = Photo.query.filter_by(id=photo_id).first_or_404()
    album = photo.album
    comments = Comment.query.filter_by(photo_id=photo_id).order_by(Comment.id).all()
    categories = Category.query.order_by(Category.title).all()
    return render_template('my_photo.html', user=user, album=album, photo=photo, comments=comments,
                           categories=categories)


@app.route('/add_comment/<int:photo_id>', methods=['POST'])
def add_comment(photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    text = request.form['text']
    comment = Comment(
        photo_id=photo_id,
        text=text
    )

    db.session.add(comment)
    db.session.commit()
    return redirect("/photo/" + str(photo_id))


@app.route('/delete_comment/<int:comment_id>', methods=['GET'])
def delete_comment(comment_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    comment = Comment.query.filter_by(id=comment_id).first()
    photo_id = comment.photo_id

    db.session.delete(comment)
    db.session.commit()
    return redirect("/photo/" + str(photo_id))


@app.route('/categories', methods=['GET'])
def categories():
    user = getCurrentUser()
    if not user:
        return redirect('/login')
    categories = Category.query.order_by(Category.title).all()
    return render_template('categories.html', title='Категории', user=user, categories=categories)


@app.route('/logout')
def logout():
    session.pop('username', 0)
    session.pop('user_id', 0)
    return redirect('/login')


@app.route('/add_category', methods=['POST'])
def add_category():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    title = request.form['title']
    category = Category(
        title=title)

    db.session.add(category)
    db.session.commit()
    return redirect("/categories")


@app.route('/delete_category/<int:category_id>', methods=['GET'])
def delete_category(category_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')
    category = Category.query.filter_by(id=category_id).first()
    db.session.delete(category)
    db.session.commit()
    return redirect("/categories")


@app.route('/set_category/<int:photo_id>', methods=['POST'])
def set_category(photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')
    category_id = request.form['category_id']
    photo = Photo.query.filter_by(id=photo_id).first()
    if category_id == "None":
        photo.category_id = None
    else:
        photo.category_id = category_id
    db.session.commit()
    return redirect("/photo/" + str(photo_id))


@app.route('/vote/<int:category_id>', methods=['GET'])
def vote(category_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    category = Category.query.filter_by(id=category_id).first_or_404()
    photos = Photo.query.filter_by(category_id=category_id).all()
    photo1 = choice(photos)
    photos.remove(photo1)
    photo2 = choice(photos)
    return render_template('vote.html', title='Голосование', user=user, category=category, photo1=photo1, photo2=photo2)


@app.route('/set_vote/<int:good_photo_id>/<int:bad_photo_id>', methods=['GET'])
def set_vote(good_photo_id, bad_photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    Vote.query.filter_by(user_id=user.id, good_photo_id=good_photo_id, bad_photo_id=bad_photo_id).delete()
    Vote.query.filter_by(user_id=user.id, good_photo_id=bad_photo_id, bad_photo_id=good_photo_id).delete()

    photo = Photo.query.filter_by(id=good_photo_id).first()

    vote = Vote(
        user_id=user.id,
        good_photo_id=good_photo_id,
        bad_photo_id=bad_photo_id
    )
    db.session.add(vote)
    db.session.commit()
    return redirect('/vote/' + str(photo.category_id))


@app.route('/rating', methods=['GET'])
def rating():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    best_photo = None
    max_rating = 0

    photos = Photo.query.all()
    for photo in photos:
        good_votes = Vote.query.filter_by(good_photo_id=photo.id).all()
        bad_votes = Vote.query.filter_by(bad_photo_id=photo.id).all()
        rating = len(good_votes) - len(bad_votes)
        if not best_photo or rating > max_rating:
            best_photo = photo

    return render_template('rating.html', title='Рейтинг', user=user, photo=best_photo)


if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')
