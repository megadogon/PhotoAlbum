import io
import os
from random import choice

from flask import Flask, render_template, request, session, send_file, abort
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


# таблица пользователей
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    surname = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return '<User {} {} {} {}>'.format(
            self.id, self.username, self.name, self.surname)


# таблица фотоалбомов
class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    user = db.relationship('User', backref=db.backref('albums', cascade="all"))
    title = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return '<Album {}>'.format(self.id)


# таблица категорий
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return '<Category {}>'.format(self.id)


# таблица фотографий
class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120))
    description = db.Column(db.Text)
    album_id = db.Column(db.Integer, db.ForeignKey('album.id', ondelete="CASCADE"), nullable=False)
    album = db.relationship('Album', backref=db.backref('photos', cascade="all"))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category', backref=db.backref('photos'))
    picture = db.Column(db.LargeBinary)
    mimetype = db.Column(db.String(80))
    filename = db.Column(db.String(250))

    def __repr__(self):
        return '<Photo {}>'.format(self.id)


# таблица голосов
class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete="CASCADE"), nullable=False)
    user = db.relationship('User', backref=db.backref('votes', cascade="all"))
    good_photo_id = db.Column(db.Integer, db.ForeignKey('photo.id', ondelete="CASCADE"), nullable=False)
    good_photo = db.relationship('Photo', foreign_keys=[good_photo_id], backref=db.backref('good_votes', cascade="all"))
    bad_photo_id = db.Column(db.Integer, db.ForeignKey('photo.id', ondelete="CASCADE"), nullable=False)
    bad_photo = db.relationship('Photo', foreign_keys=[bad_photo_id], backref=db.backref('bad_votes', cascade="all"))


# создание всех таблиц в базе данных
db.create_all()

# создание пользователя - администратора
if User.query.first() == None:
    admin = User(
        username='admin',
        name="Дмитрий",
        surname="Килиевич",
        email="dkiliyevich@mail.ru",
        password_hash=generate_password_hash('1234'))
    db.session.add(admin)
    db.session.commit()


# обработчик главной страницы
@app.route('/')
@app.route('/index')
def index():
    return redirect('/login')


# обработчик входа в систему
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        # проверка, что пользователь есть и его пароль совпадает
        if user and check_password_hash(user.password_hash, password):
            session['username'] = username
            session['user_id'] = user.id
            return redirect('/albums')

        errors = ['Неверное имя пользователя или пароль']
        return render_template('login.html', title='Авторизация', errors=errors)
    else:
        return render_template('login.html', title='Авторизация')


# обработчик регистрации
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

    # запоминанеие текущего пользователя в сессии
    db.session.add(user)
    db.session.commit()

    # авто-логин после регистрации
    session['username'] = user.username
    session['user_id'] = user.id
    return redirect('/albums')


# получение текущего пользователя
def getCurrentUser():
    if 'user_id' not in session:
        return None
    user_id = session['user_id']
    return User.query.filter_by(id=user_id).first()


# обработчик фотоальбомов
@app.route('/albums', methods=['GET'])
def albums():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # получение списка фотоальбомов текущего пользователя
    albums = Album.query.filter_by(user_id=user.id).order_by(Album.title).all()

    return render_template('albums.html', title='Мои альбомы', user=user, albums=albums)


# обработчик добавления фотоальбома
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
    return redirect("/album/" + str(album.id))


# обработчик удаления фотоальбома
@app.route('/delete_album/<int:album_id>', methods=['GET'])
def delete_album(album_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # поиск фотоальбома, проверка, что он принадлежит текущему пользователю
    album = Album.query.filter_by(user_id=user.id, id=album_id).first_or_404()

    db.session.delete(album)
    db.session.commit()
    return redirect("/albums")


# подсчет рейтинга всех фото
def calc_rating(photos):
    for photo in photos:
        photo.good = len(photo.good_votes)
        photo.bad = len(photo.bad_votes)
        photo.rating = photo.good - photo.bad


# обработчик фотоальбома
@app.route('/album/<int:album_id>', methods=['GET', 'POST'])
def album(album_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # поиск фотоальбома, проверка, что он принадлежит текущему пользователю
    album = Album.query.filter_by(user_id=user.id, id=album_id).first_or_404()

    if request.method == 'POST':
        # изменение фотоальбома
        title = request.form['title']
        album.title = title
        db.session.commit()
        return redirect("/album/" + str(album_id))
    else:
        # отображение фотоальбома
        # получение всех потографий фотоальбома
        photos = Photo.query.filter_by(album_id=album_id).order_by(Photo.id).all()
        # подсчет рейтинга
        calc_rating(photos)
        # получение всех категорий
        categories = Category.query.order_by(Category.title).all()
        return render_template('album.html', title='Мой альбом', user=user, album=album, photos=photos,
                               categories=categories)


# обработчик категории
@app.route('/category/<int:category_id>', methods=['GET', 'POST'])
def category(category_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    if request.method == 'POST':
        # только администратор может редактировать категорию
        if user.id != 1:
            abort(403)  # ошибка - в доступе отказано

        title = request.form['title']
        category = Category.query.filter_by(id=category_id).first_or_404()
        category.title = title
        db.session.commit()
        return redirect("/categories")
    else:
        # просмотр списка всех категорий для голосования
        category = Category.query.filter_by(id=category_id).first_or_404()
        return render_template('category.html', title='Категория', user=user, category=category)


# допустипые для скачивания файлы, только графические
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])


# проверка, что это допустимый файл
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# обработчик добавления фотографии
@app.route('/add_photo/<int:album_id>', methods=['POST'])
def add_photo(album_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # проверка, что альбом принадлежит текущему пользователю
    Album.query.filter_by(user_id=user.id, id=album_id).first_or_404()

    file = request.files['file']

    if file and allowed_file(file.filename):
        # делаем безопасное имя файла
        filename = secure_filename(file.filename)
        # файл, куда сохранять
        fullfilename = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        # сохранение файла, который прислал пользователь
        file.save(fullfilename)

        # чтение файла
        with open(fullfilename, "rb") as f:
            data = f.read()

        # удаление файла
        os.remove(fullfilename)

        # создание фотографии в базе данных
        photo = Photo(
            album_id=album_id,
            picture=data,
            mimetype=file.content_type,
            filename=filename
        )

        db.session.add(photo)
        db.session.commit()

    return redirect("/album/" + str(album_id) + "#" + str(photo.id))


# обработчик получения фотографии
@app.route('/photo_img/<int:photo_id>', methods=['GET'])
def photo_img(photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # получение фото, проверка, что такое есть.
    photo = Photo.query.filter_by(id=photo_id).first_or_404()

    # отправление фотографии, как графический файл для отображения в браузере
    return send_file(
        io.BytesIO(photo.picture),
        mimetype=photo.mimetype,
        as_attachment=True,
        attachment_filename=photo.filename)


# обработчик списка категорий
@app.route('/categories', methods=['GET'])
def categories():
    user = getCurrentUser()
    if not user:
        return redirect('/login')
    categories = Category.query.order_by(Category.title).all()
    return render_template('categories.html', title='Категории', user=user, categories=categories)


# обработчик выхода из системы
@app.route('/logout')
def logout():
    session.pop('username', 0)
    session.pop('user_id', 0)
    return redirect('/login')


# обработчик добавления категории
@app.route('/add_category', methods=['POST'])
def add_category():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # только администратор может добавлять категории
    if user.id != 1:
        abort(403)  # ошибка - в доступе отказано

    title = request.form['title']
    category = Category(
        title=title)

    db.session.add(category)
    db.session.commit()
    return redirect("/categories")


# обработчик удаления категории
@app.route('/delete_category/<int:category_id>', methods=['GET'])
def delete_category(category_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # только администратор может удалять категорию
    if user.id != 1:
        abort(403)  # ошибка - в доступе отказано

    category = Category.query.filter_by(id=category_id).first()
    db.session.delete(category)
    db.session.commit()
    return redirect("/categories")


# обработчик редактирования фотографии
@app.route('/edit_photo/<int:photo_id>', methods=['POST'])
def edit_photo(photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # поиск пото, проверка, что она есть
    photo = Photo.query.filter_by(id=photo_id).first_or_404()
    # проверка, что фото принадлежит текущему пользователю
    if photo.album.user_id != user.id:
        abort(404)

    photo.title = request.form['title']
    photo.description = request.form['description']

    category_id = request.form['category_id']
    if category_id == "None":
        category_id = None
    # если у фотографии изменилась категория, то удалить рейтинг фотографии
    if photo.category_id != category_id:
        photo.category_id = category_id
        Vote.query.filter_by(good_photo_id=photo_id).delete()
        Vote.query.filter_by(bad_photo_id=photo_id).delete()

    db.session.commit()
    return redirect("/album/" + str(photo.album_id) + "#" + str(photo_id))


# обработчик удаления фотографии
@app.route('/delete_photo/<int:photo_id>', methods=['GET'])
def delete_photo(photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # поиск фото
    photo = Photo.query.filter_by(id=photo_id).first_or_404()
    album = photo.album
    # только пользователь, который добавил фото может ее удалять
    if album.user_id != user.id:
        abort(404)

    db.session.delete(photo)
    db.session.commit()
    return redirect("/album/" + str(album.id))


# обработчик голосования
@app.route('/vote/<int:category_id>', methods=['GET'])
def vote(category_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # поиск категории
    category = Category.query.filter_by(id=category_id).first_or_404()
    # все фото в категории
    photos = category.photos

    if len(photos) >= 2:
        # выбор двух случайных разных фото
        photo1 = choice(photos)
        photos.remove(photo1)
        photo2 = choice(photos)
        error = None
    else:
        error = 'В категории недостаточно фотографий для голосования'
        photo1 = None
        photo2 = None

    return render_template('vote.html', title='Голосование',
                           user=user,
                           category=category,
                           photo1=photo1,
                           photo2=photo2,
                           error=error)


# обработчик голосования
@app.route('/set_vote/<int:good_photo_id>/<int:bad_photo_id>', methods=['GET'])
def set_vote(good_photo_id, bad_photo_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # поиск фото для определения категории
    photo1 = Photo.query.filter_by(id=good_photo_id).first()
    photo2 = Photo.query.filter_by(id=bad_photo_id).first()

    if photo1.category_id != photo2.category_id:
        abort(403)  # можно голосовать только за фотографии в одной категории

    # удаление старого голосования текущего пользователя за эти две фото
    Vote.query.filter_by(user_id=user.id, good_photo_id=good_photo_id, bad_photo_id=bad_photo_id).delete()
    Vote.query.filter_by(user_id=user.id, good_photo_id=bad_photo_id, bad_photo_id=good_photo_id).delete()

    # добавление нового голоса
    vote = Vote(
        user_id=user.id,
        good_photo_id=good_photo_id,
        bad_photo_id=bad_photo_id
    )
    db.session.add(vote)
    db.session.commit()
    return redirect('/vote/' + str(photo1.category_id))


# обработчик категорий рейтинга
@app.route('/rating', methods=['GET'])
def rating():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    categories = Category.query.order_by(Category.title).all()
    categories = [category for category in categories if len(category.photos) >= 2]

    return render_template('rating.html', title='Рейтинг', user=user, categories=categories)


# обработчик топ-10
@app.route('/top/<int:category_id>', methods=['GET'])
def top(category_id):
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    # ищем категорию
    category = Category.query.filter_by(id=category_id).first_or_404()

    # список всех фотографий в категории
    photos = category.photos
    calc_rating(photos)

    # сортируем по рейтингу
    l1 = []
    for photo in photos:
        l1.append((-photo.rating, photo.id, photo))
    l1.sort()
    photos = [item[2] for item in l1]

    # оставляем первые 10 фото
    if len(photos) > 10:
        photos = photos[0:10]

    # подсчитываем места
    for i in range(len(photos)):
        photos[i].place = i + 1

    return render_template('top.html', title='Топ-10', user=user, category=category, photos=photos)


# обработчик профиля
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user = getCurrentUser()
    if not user:
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        surname = request.form['surname']
        user.name = name
        user.surname = surname
        db.session.commit()
        return redirect('/profile')
    else:
        return render_template('profile.html', title='Профиль', user=user)


# запуск web-сервера
if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')
