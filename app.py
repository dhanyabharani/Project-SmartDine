from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify, abort, send_file
import sqlite3, json, os, math, io, qrcode
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET','dev-secret-key')
DB = 'hotel_v3.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.executescript(open('schema.sql','r',encoding='utf-8').read())
    cur.execute('SELECT COUNT(*) as c FROM users')
    if cur.fetchone()['c'] == 0:
        cur.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)", ('admin','adminpass','admin'))
        cur.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)", ('cook','cookpass','cook'))
    cur.execute('SELECT COUNT(*) as c FROM menu_items')
    if cur.fetchone()['c'] == 0:
        demo = [
            ('Spring Rolls','Starters',50,'Veg',250,30),
            ('Paneer Tikka','Starters',80,'Veg',320,25),
            ('Veg Biryani','Main Course',120,'Veg',600,20),
            ('Chicken Biryani','Main Course',160,'Non-Veg',700,15),
            ('Masala Dosa','Main Course',70,'Veg',350,40),
            ('Gulab Jamun','Desserts',40,'Veg',250,50),
            ('Ice Cream','Desserts',50,'Veg',200,60)
        ]
        for row in demo:
            cur.execute('INSERT INTO menu_items (name,category,price,diet,calories,stock) VALUES (?,?,?,?,?,?)', row)
    db.commit()

def query_all(q, args=()):
    cur = get_db().execute(q, args)
    rows = cur.fetchall()
    cur.close()
    return rows

def query_one(q, args=()):
    cur = get_db().execute(q, args)
    row = cur.fetchone()
    cur.close()
    return row

@app.route('/')
def index():
    specials = query_all('SELECT name,price FROM menu_items LIMIT 4')
    return render_template('index.html', specials=specials)

@app.route('/api/menu')
def api_menu():
    rows = query_all('SELECT id,name,category,price,diet,calories,stock FROM menu_items WHERE stock>0 ORDER BY category')
    return jsonify([dict(r) for r in rows])

@app.route('/api/menu_full')
def api_menu_full():
    rows = query_all('SELECT id,name,category,price,diet,calories,stock FROM menu_items ORDER BY category')
    return jsonify([dict(r) for r in rows])

@app.route('/menu', methods=['GET','POST'])
def menu():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name','Guest').strip()
        table = request.form.get('table','0').strip()
        phone = request.form.get('phone','').strip()
        items_selected = []
        total = 0
        for row in query_all('SELECT id,name,price,stock FROM menu_items'):
            qty = int(request.form.get(f'qty_{row["id"]}', '0') or 0)
            if qty > 0:
                if row['stock'] < qty:
                    return f'Not enough stock for {row["name"]}. Available {row["stock"]}', 400
                items_selected.extend([row['name']] * qty)
                total += row['price'] * qty
        if not items_selected:
            return render_template('menu.html', items=query_all('SELECT * FROM menu_items WHERE stock>0'), categories=['All'], diets=['All'], error='Select at least one item', selected_category=request.args.get('category','All'), selected_diet=request.args.get('diet','All'))
        for row in query_all('SELECT id,name FROM menu_items'):
            qty = int(request.form.get(f'qty_{row["id"]}', '0') or 0)
            if qty > 0:
                db.execute('UPDATE menu_items SET stock = stock - ? WHERE id = ? AND stock>=?', (qty, row['id'], qty))
        loyalty = total // 50
        db.execute('INSERT INTO orders (customer_name,table_no,items,total,status,phone,loyalty_points) VALUES (?,?,?,?,?,?,?)', (name,table,json.dumps(items_selected),total,'Pending',phone,loyalty))
        db.commit()
        order_id = db.execute('SELECT last_insert_rowid() as id').fetchone()['id']
        return redirect(url_for('order_success', order_id=order_id))
    diet = request.args.get('diet','All')
    category = request.args.get('category','All')
    sql = 'SELECT * FROM menu_items WHERE stock>0'
    params = []
    if diet and diet != 'All':
        if diet == 'Low-Calorie':
            sql += ' AND calories <= ?'; params.append(400)
        else:
            sql += ' AND diet = ?'; params.append(diet)
    if category and category != 'All':
        sql += ' AND category = ?'; params.append(category)
    items = query_all(sql + ' ORDER BY category', tuple(params))
    categories = ['All','Starters','Main Course','Desserts']
    diets = ['All','Veg','Non-Veg','Jain','Low-Calorie']
    combos = [{'name':'Biryani + Ice Cream','items':['Veg Biryani','Ice Cream']},
              {'name':'Dosa + Gulab Jamun','items':['Masala Dosa','Gulab Jamun']}]
    return render_template('menu.html', items=items, categories=categories, diets=diets, combos=combos, selected_category=category, selected_diet=diet)

@app.route('/order_success/<int:order_id>')
def order_success(order_id):
    row = query_one('SELECT * FROM orders WHERE id=?', (order_id,))
    if not row: return 'Order not found',404
    items = json.loads(row['items'])
    return render_template('order_success.html', order=row, items=items)

@app.route('/pay/<int:order_id>')
def pay(order_id):
    row = query_one('SELECT * FROM orders WHERE id=?', (order_id,))
    if not row: abort(404)
    upi_uri = f'upi://pay?pa=hotel@upi&pn=TastyBites&am={row["total"]}'
    return render_template('pay.html', order=row, upi_uri=upi_uri)

@app.route('/qrcode')
def qrcode_image():
    data = request.args.get('data','hello')
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/simulate_payment/<int:order_id>', methods=['POST'])
def simulate_payment(order_id):
    db = get_db()
    row = query_one('SELECT * FROM orders WHERE id=?', (order_id,))
    if not row: abort(404)
    if row['paid'] == 1:
        return 'Already paid', 400
    amount = row['total']
    db.execute('UPDATE orders SET paid=1, status=? WHERE id=?', ('Paid', order_id))
    db.execute('INSERT INTO payments (order_id,amount) VALUES (?,?)', (order_id, amount))
    db.commit()
    return redirect(url_for('status', order_id=order_id))

@app.route('/status/<int:order_id>')
def status(order_id):
    row = query_one('SELECT * FROM orders WHERE id=?', (order_id,))
    if not row: return 'Order not found',404
    items = json.loads(row['items'])
    return render_template('status.html', order=row, items=items)

@app.route('/feedback/<int:order_id>', methods=['GET','POST'])
def feedback(order_id):
    if request.method == 'POST':
        rating = int(request.form.get('rating',5))
        comment = request.form.get('comment','')
        db = get_db()
        db.execute('INSERT INTO feedback (order_id,rating,comment) VALUES (?,?,?)', (order_id,rating,comment))
        db.commit()
        return redirect(url_for('index'))
    return render_template('feedback.html', order_id=order_id)

@app.route('/cook_login', methods=['GET','POST'])
def cook_login():
    if request.method == 'POST':
        u = request.form.get('username'); p = request.form.get('password')
        row = query_one('SELECT * FROM users WHERE username=? AND password=? AND role="cook"', (u,p))
        if row:
            session['user'] = u; session['role'] = 'cook'
            return redirect(url_for('cook_dashboard'))
        return render_template('login.html', cook=True, error='Invalid cook credentials')
    return render_template('login.html', cook=True)

@app.route('/cook_dashboard')
def cook_dashboard():
    if session.get('role') != 'cook': return redirect(url_for('cook_login'))
    rows = query_all('SELECT * FROM orders ORDER BY created_at DESC')
    orders = []
    for r in rows:
        d = dict(r); d['items_list'] = json.loads(r['items']); orders.append(d)
    low = query_all('SELECT * FROM menu_items WHERE stock <= 5 ORDER BY stock ASC')
    return render_template('cook.html', orders=orders, low=low)

@app.route('/cook_update/<int:order_id>')
def cook_update(order_id):
    if session.get('role') != 'cook': return redirect(url_for('cook_login'))
    db = get_db(); db.execute('UPDATE orders SET status = ? WHERE id = ?', ('Ready', order_id)); db.commit()
    return redirect(url_for('cook_dashboard'))

@app.route('/cook_restock', methods=['POST'])
def cook_restock():
    if session.get('role') != 'cook': return redirect(url_for('cook_login'))
    item_id = request.form.get('item_id')
    amount = int(request.form.get('amount',0))
    if not item_id or amount<=0:
        return redirect(url_for('cook_dashboard'))
    db = get_db(); db.execute('UPDATE menu_items SET stock = stock + ? WHERE id = ?', (amount, item_id)); db.commit()
    return redirect(url_for('cook_dashboard'))

@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        u = request.form.get('username'); p = request.form.get('password')
        row = query_one('SELECT * FROM users WHERE username=? AND password=? AND role="admin"', (u,p))
        if row:
            session['user'] = u; session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        return render_template('login.html', admin=True, error='Invalid admin credentials')
    return render_template('login.html', admin=True)

@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html')

@app.route('/admin_add_item', methods=['POST'])
def admin_add_item():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    name = request.form.get('name'); category = request.form.get('category'); price = int(request.form.get('price',0))
    diet = request.form.get('diet'); calories = int(request.form.get('calories',0)); stock = int(request.form.get('stock',0))
    db = get_db()
    db.execute('INSERT INTO menu_items (name,category,price,diet,calories,stock) VALUES (?,?,?,?,?,?)', (name,category,price,diet,calories,stock))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_delete_item/<int:item_id>', methods=['POST'])
def admin_delete_item(item_id):
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    db = get_db(); db.execute('DELETE FROM menu_items WHERE id=?', (item_id,)); db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin_update_stock', methods=['POST'])
def admin_update_stock():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    item_id = int(request.form.get('item_id')); new_stock = int(request.form.get('stock',0))
    db = get_db(); db.execute('UPDATE menu_items SET stock=? WHERE id=?', (new_stock,item_id)); db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/api/sales')
def api_sales():
    rows = query_all('SELECT date(created_at) as d, SUM(total) as total FROM orders GROUP BY date(created_at) ORDER BY d')
    labels = [r['d'] for r in rows]; values=[r['total'] for r in rows]
    return jsonify({'labels':labels,'values':values})

@app.route('/api/popular')
def api_popular():
    rows = query_all('SELECT items FROM orders')
    counts={}
    for r in rows:
        for it in json.loads(r['items']):
            counts[it]=counts.get(it,0)+1
    items_sorted = sorted(counts.items(), key=lambda x:x[1], reverse=True)[:10]
    labels=[i[0] for i in items_sorted]; values=[i[1] for i in items_sorted]
    return jsonify({'labels':labels,'values':values})

@app.route('/api/inventory')
def api_inventory():
    rows = query_all('SELECT id,name,stock FROM menu_items ORDER BY name')
    items = [dict(r) for r in rows]
    return jsonify(items)

@app.route('/api/orders_recent')
def api_orders_recent():
    rows = query_all('SELECT id,customer_name,table_no,items,total,status,created_at FROM orders ORDER BY created_at DESC LIMIT 20')
    items = []
    for r in rows:
        d = dict(r); d['items'] = json.loads(d['items']); items.append(d)
    return jsonify(items)

@app.route('/api/payments')
def api_payments():
    rows = query_all('SELECT p.id,p.order_id,p.amount,p.paid_at,o.customer_name FROM payments p JOIN orders o ON o.id=p.order_id ORDER BY p.paid_at DESC LIMIT 20')
    return jsonify([dict(r) for r in rows])

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
