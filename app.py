import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db, close_db

app = Flask(__name__)
app.secret_key = 'buybox_secret_key_2026'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

app.teardown_appcontext(close_db)

@app.route('/')
def index():
    db = get_db()
    products = db.execute(
        "SELECT p.*, u.name as seller_name, "
        "(SELECT url FROM ProductImages WHERE product_id = p.id ORDER BY position LIMIT 1) as image_url "
        "FROM Products p JOIN Users u ON p.user_id = u.id "
        "WHERE p.status = 'active' ORDER BY p.created_at DESC LIMIT 4"
    ).fetchall()
    
    favorites = []
    if 'user_id' in session:
        fav_rows = db.execute("SELECT product_id FROM Favorites WHERE user_id = ?", (session['user_id'],)).fetchall()
        favorites = [row['product_id'] for row in fav_rows]

    stats = {
        'products_count': db.execute("SELECT COUNT(*) FROM Products WHERE status = 'active'").fetchone()[0],
        'users_count': db.execute("SELECT COUNT(*) FROM Users").fetchone()[0]
    }
    return render_template('index.html', products=products, stats=stats, favorites=favorites)

@app.route('/catalog')
def catalog():
    db = get_db()
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort', 'newest')

    sql = """
        SELECT p.*, u.name as seller_name, 
        (SELECT url FROM ProductImages WHERE product_id = p.id ORDER BY position LIMIT 1) as image_url 
        FROM Products p JOIN Users u ON p.user_id = u.id 
        WHERE p.status = 'active'
    """
    params = []

    if query:
        sql += " AND p.title LIKE ?"
        params.append(f"%{query}%")
    if category:
        sql += " AND p.category = ?"
        params.append(category)
    if min_price is not None:
        sql += " AND p.price >= ?"
        params.append(min_price)
    if max_price is not None:
        sql += " AND p.price <= ?"
        params.append(max_price)

    if sort == 'cheapest':
        sql += " ORDER BY p.price ASC"
    elif sort == 'expensive':
        sql += " ORDER BY p.price DESC"
    else:
        sql += " ORDER BY p.created_at DESC"

    products = db.execute(sql, params).fetchall()
    
    favorites = []
    if 'user_id' in session:
        fav_rows = db.execute("SELECT product_id FROM Favorites WHERE user_id = ?", (session['user_id'],)).fetchall()
        favorites = [row['product_id'] for row in fav_rows]

    return render_template('catalog.html', products=products, favorites=favorites, query=query, category=category)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    db = get_db()
    product = db.execute(
        "SELECT p.*, u.name as seller_name, u.username as seller_username, u.email as seller_email "
        "FROM Products p JOIN Users u ON p.user_id = u.id WHERE p.id = ?", 
        (product_id,)
    ).fetchone()
    
    if not product:
        return render_template('error.html', message="Товар не найден"), 404

    images = db.execute("SELECT url FROM ProductImages WHERE product_id = ? ORDER BY position", (product_id,)).fetchall()
    
    other_products = db.execute(
        "SELECT p.*, (SELECT url FROM ProductImages WHERE product_id = p.id ORDER BY position LIMIT 1) as image_url "
        "FROM Products p WHERE p.id != ? AND p.status = 'active' LIMIT 3", 
        (product_id,)
    ).fetchall()

    is_favorite = False
    if 'user_id' in session:
        fav = db.execute("SELECT * FROM Favorites WHERE user_id = ? AND product_id = ?", (session['user_id'], product_id)).fetchone()
        is_favorite = fav is not None

    return render_template('product.html', product=product, images=images, other_products=other_products, is_favorite=is_favorite)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        db = get_db()
        try:
            db.execute("INSERT INTO Users (name, username, email, password_hash) VALUES (?, ?, ?, ?)",
                       (name, username, email, password_hash))
            db.commit()
            flash('Регистрация прошла успешно. Войдите в аккаунт.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Пользователь с таким логином или email уже существует.', 'error')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        user = db.execute("SELECT * FROM Users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['username'] = user['username']
            return redirect(url_for('profile'))
        else:
            flash('Неверный логин или пароль.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user_id = session['user_id']
    user = db.execute("SELECT * FROM Users WHERE id = ?", (user_id,)).fetchone()
    
    active_products = db.execute(
        "SELECT p.*, (SELECT url FROM ProductImages WHERE product_id = p.id ORDER BY position LIMIT 1) as image_url "
        "FROM Products p WHERE p.user_id = ? AND p.status = 'active'", (user_id,)
    ).fetchall()

    archived_products = db.execute(
        "SELECT p.*, (SELECT url FROM ProductImages WHERE product_id = p.id ORDER BY position LIMIT 1) as image_url "
        "FROM Products p WHERE p.user_id = ? AND p.status = 'archived'", (user_id,)
    ).fetchall()

    return render_template('profile.html', user=user, active_products=active_products, archived_products=archived_products)

@app.route('/listing/new', methods=['GET', 'POST'])
def new_listing():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        condition = request.form['condition']
        city = request.form['city']
        user_id = session['user_id']

        db = get_db()
        cursor = db.execute(
            "INSERT INTO Products (user_id, title, description, price, category, condition, city, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'active')",
            (user_id, title, description, price, category, condition, city)
        )
        product_id = cursor.lastrowid

        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and photo.filename:
                filename = secure_filename(photo.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                photo.save(photo_path)
                db.execute("INSERT INTO ProductImages (product_id, url, position) VALUES (?, ?, 0)", 
                           (product_id, f"/static/uploads/{filename}"))

        db.commit()
        return redirect(url_for('profile'))

    return render_template('listing_form.html')

@app.route('/listing/<int:product_id>/delete', methods=['POST'])
def delete_listing(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    product = db.execute("SELECT * FROM Products WHERE id = ?", (product_id,)).fetchone()
    if product and product['user_id'] == session['user_id']:
        db.execute("DELETE FROM Products WHERE id = ?", (product_id,))
        db.commit()
    return redirect(url_for('profile'))

@app.route('/listing/<int:product_id>/archive', methods=['POST'])
def archive_listing(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    product = db.execute("SELECT * FROM Products WHERE id = ?", (product_id,)).fetchone()
    if product and product['user_id'] == session['user_id']:
        new_status = 'archived' if product['status'] == 'active' else 'active'
        db.execute("UPDATE Products SET status = ? WHERE id = ?", (new_status, product_id))
        db.commit()
    return redirect(url_for('profile'))

@app.route('/favorites')
def favorites_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    favorites = db.execute(
        "SELECT p.*, u.name as seller_name, "
        "(SELECT url FROM ProductImages WHERE product_id = p.id ORDER BY position LIMIT 1) as image_url "
        "FROM Favorites f JOIN Products p ON f.product_id = p.id "
        "JOIN Users u ON p.user_id = u.id WHERE f.user_id = ?",
        (session['user_id'],)
    ).fetchall()

    return render_template('favorites.html', favorites=favorites)

@app.route('/favorites/toggle/<int:product_id>', methods=['POST'])
def toggle_favorite(product_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    db = get_db()
    existing = db.execute("SELECT * FROM Favorites WHERE user_id = ? AND product_id = ?", (user_id, product_id)).fetchone()
    
    if existing:
        db.execute("DELETE FROM Favorites WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        is_favorite = False
    else:
        db.execute("INSERT INTO Favorites (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
        is_favorite = True
    db.commit()
    
    return jsonify({'is_favorite': is_favorite})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
