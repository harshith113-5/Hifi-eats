import logging
import sqlite3
import os
import threading
import time
import re
import random
import secrets
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from flask import Flask, render_template, jsonify, request, session, flash, redirect, url_for
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from functools import wraps


# Dynamically determine the database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'instance', 'HiFieats.db')

DEFAULT_CITY = "Bangalore City"  # Define the default city to check for "in range"

'''
reject = -1
approve = 1
pending = 0
'''
app = Flask(__name__)

IMAGE_FOLDER = 'static/images'

# Ensure the image folder exists
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

# Set the IMAGE_FOLDER in app.config
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = 'mysecrethifi'
def init_db():
    try:
        if not os.path.exists(DATABASE):
            os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
            app.logger.info(f"Database file not found at {DATABASE}, creating new one.")

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()

            # Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    location TEXT,
                    contact TEXT,
                    approved INTEGER NOT NULL DEFAULT 0
                )
            """)

            # Delivery Agent Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Delivery_Agent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    location TEXT,
                    contact TEXT,
                    approved INTEGER NOT NULL DEFAULT 0
                )
            """)

            # Contact Messages Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contact_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            """)

            # Delivery Agent Dashboard Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS DeliveryAgentPerformance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    orders_delivered INTEGER NOT NULL,
                    on_time_deliveries INTEGER NOT NULL,
                    customer_ratings REAL NOT NULL,
                    cancellation_rate REAL NOT NULL,
                    FOREIGN KEY (agent_id) REFERENCES Delivery_Agent (id)
                )
            """)

            # Order Feedback Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS OrderFeedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    orderId INTEGER NOT NULL,
                    customerId INTEGER NOT NULL,
                    rating INTEGER CHECK(rating BETWEEN 1 AND 5) NOT NULL,
                    review TEXT,
                    feedbackDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (orderId) REFERENCES orders (id) ON DELETE CASCADE,
                    FOREIGN KEY (customerId) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            # Delivery Data Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS DeliveryData (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    orderId INTEGER NOT NULL,
                    deliveryAgentId INTEGER NOT NULL,
                    pickupTime TIMESTAMP NOT NULL,
                    deliveryTime TIMESTAMP,
                    scheduledDeliveryTime TIMESTAMP NOT NULL,
                    status TEXT CHECK(status IN ('Pending', 'In Transit', 'Delivered', 'Cancelled')) NOT NULL,
                    FOREIGN KEY (orderId) REFERENCES orders (id) ON DELETE CASCADE,
                    FOREIGN KEY (deliveryAgentId) REFERENCES Delivery_Agent (id) ON DELETE CASCADE
                )
            """)

            # New Order Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Orders_Analysis(
                    orderId INTEGER PRIMARY KEY AUTOINCREMENT,
                    customerName TEXT NOT NULL,
                    productName TEXT NOT NULL,
                    orderDate TEXT NOT NULL
                )
            """)

            # Delivery Agent Report Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Delivery_Agent_Report (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Agent TEXT NOT NULL,
                    OrderId INTEGER,
                    IssueType TEXT NOT NULL,
                    IssueDetails TEXT NOT NULL,
                    FOREIGN KEY (OrderId) REFERENCES orders(id) ON DELETE CASCADE
                )
            """)

            # Assigned Orders Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assignedOrders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    orderId INTEGER NOT NULL,
                    customerName TEXT NOT NULL,
                    deliveryAgentId INTEGER NOT NULL,
                    status TEXT CHECK(status IN ('New', 'In Progress', 'Completed')) NOT NULL,
                    action TEXT NOT NULL,
                    FOREIGN KEY (orderId) REFERENCES Orders_Analysis (orderId) ON DELETE CASCADE,
                    FOREIGN KEY (customerName) REFERENCES users (username),
                    FOREIGN KEY (deliveryAgentId) REFERENCES Delivery_Agent (id)
                )
            """)

            # Triggers for Assigned Orders
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_timestamp_new
                AFTER INSERT ON assignedOrders
                WHEN NEW.status = 'New'
                BEGIN
                    UPDATE assignedOrders
                    SET TIMESTAMP = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END;
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_timestamp_completed
                AFTER UPDATE OF status ON assignedOrders
                WHEN NEW.status = 'Completed'
                BEGIN
                    UPDATE assignedOrders
                    SET TIMESTAMP = CURRENT_TIMESTAMP
                    WHERE id = NEW.id;
                END;
            """)

            # Table for orders (Team-2)
            cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        items TEXT NOT NULL,
                        location TEXT NOT NULL, 
                        total_price REAL NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            # Menu Items Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS menu_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    price REAL NOT NULL,
                    image_path TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'veg',
                    subcategory TEXT NOT NULL DEFAULT 'starter',
                    discount REAL NOT NULL DEFAULT 0.0
                )
            """)

            conn.commit()

    except sqlite3.OperationalError as e:
        print(f"Error initializing database: {e}")
    finally:
        conn.close()

init_db()

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'hifidelivery213@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'oiya zlhv irvc yowz'  # Replace with your app-specific password

import sqlite3

mail = Mail(app)
# Store OTPs in memory (can be changed to a database in production)
# otp_store = {}

# # Send OTP to the email
# def send_otp(email, otp):
#     try:
#         msg = Message('Your OTP Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
#         msg.body = f"Your OTP code is {otp}. It will expire in 10 minutes."
#         mail.send(msg)
#         print(f"OTP sent to {email}")
#     except Exception as e:
#         print(f"Error sending OTP: {e}")
#         return False
#     return True

# Functions for all functionalities.

# Initialize SQLite database

def get_db():
    """Establish a connection to the database."""
    try:
        if not os.path.exists(DATABASE):
            raise FileNotFoundError(f"Database file not found at {DATABASE}")
        # Allow SQLite to work in a multi-threaded environment
        return sqlite3.connect(DATABASE, check_same_thread=False)
    except Exception as e:
        app.logger.error(f"Error connecting to database: {e}")
        raise e

@app.route('/menu')
def index():
  """Render the menu page."""
  return render_template('menu.html')

@app.route('/api/menu', methods=['GET'])
def fetch_menu():
    """Fetches menu items from the SQLite database with optional filters."""
    category = request.args.get('category')
    subcategory = request.args.get('subcategory')

    try:
        conn = get_db()
        cursor = conn.cursor()

        query = 'SELECT id, name, description, price, image_path, category, subcategory, discount FROM menu_items WHERE 1=1'
        params = []

        if category:
            query += ' AND category = ?'
            params.append(category)

        if subcategory:
            query += ' AND subcategory = ?'
            params.append(subcategory)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        menu_items = [dict(zip([column[0] for column in cursor.description], row)) for row in rows]
        conn.close()
        return jsonify(menu_items)
    except Exception as e:
        app.logger.error(f"Error fetching menu items: {e}")
        return jsonify({'error': 'Failed to fetch menu items'}), 500

@app.route('/api/cart', methods=['POST'])
def add_to_cart():
    """Add an item to the cart."""
    item_id = request.json.get('id')
    quantity = request.json.get('quantity', 1)

    if 'cart' not in session:
        session['cart'] = []

    cart = session['cart']
    item_exists = next((item for item in cart if item['id'] == item_id), None)

    if item_exists:
        item_exists['quantity'] += quantity
    else:
        cart.append({'id': item_id, 'quantity': quantity})

    session.modified = True
    return jsonify({'message': 'Item added to cart'}), 200

@app.route('/cart', methods=['GET'])
def cart():
    """Render the cart page."""
    return render_template('cart.html')

@app.route('/api/confirm_order', methods=['POST'])
def confirm_order():
    """Saves the order and checks for address validity."""
    data = request.json
    cart = data['cartItems']
    location = data['location']
    total_price = data['total']

    # Check if "Bangalore City" exists in the location
    is_in_range = "Bangalore City" in location

    if not is_in_range:
        return jsonify({'error': 'Delivery address is out of range'}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()

        item_names = []
        for item in cart:
            item_id = item['id']
            cursor.execute('SELECT name FROM menu_items WHERE id = ?', (item_id,))
           # cursor.execute('INSERT INTO Orders_Analysis(item_name)VALUES(?)',(item))
            row = cursor.fetchone()
            if row:
                item_names.append(f"{row[0]} (x{item['quantity']})")
                
            
        items_str = ', '.join(item_names)

        # Insert the order into the database
        cursor.execute('INSERT INTO orders (items, location, total_price) VALUES (?, ?, ?)',
                       (items_str, location, total_price))
        conn.commit()
        order_id = cursor.lastrowid
        #Insert into Orders_Analysis database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        customerName=session['username']
        items = items_str.split(",")  # Split items
        cursor.execute("SELECT id FROM orders WHERE items = ? ORDER BY id DESC",(items_str,))
        r=cursor.fetchone()
        id=r[0]
        for item in items:
            match = re.match(r"(.*) \(x(\d+)\)", item.strip())  # Extract name & quantity
            if match:
                item_name, quantity = match.groups()
                quantity = int(quantity)
                print(customerName,id, item_name)
                for _ in range(quantity):
                    cursor.execute("INSERT INTO Orders_Analysis (customerName,orderId, productName,orderDate) VALUES (?, ?, ?,CURRENT_DATE)", 
                            (customerName,id, item_name))
            else:
                item_name, quantity = item.strip(), 1  # Default quantity = 1
                cursor.execute("INSERT INTO Orders_Analysis (customerName,orderId, productName,orderDate) VALUES (?, ?, ?,CURRENT_DATE)", 
                            (customerName,id, item_name))

       # Commit and close
        #conn.commit()
        conn.commit()
        conn.close()

        app.logger.info(f"Order {order_id} confirmed and saved to database.")
        #conn.close()
        return jsonify({'message': 'Order confirmed', 'order_id': order_id})
    except Exception as e:
        app.logger.error(f"Error saving order: {e}")
        return jsonify({'error': 'Failed to save order'}), 500
        
        

@app.route('/confirmOrder', methods=['GET'])
def confirm_order_page():
    """Render the order confirmation page."""
    return render_template('confirmOrder.html')

@app.route('/api/orders', methods=['GET'])
def fetch_orders():
    """Fetch all orders."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, items, location, total_price, timestamp FROM orders')
        rows = cursor.fetchall()
        conn.close()

        orders = [dict(zip([column[0] for column in cursor.description], row)) for row in rows]
        return jsonify(orders)
    except Exception as e:
        app.logger.error(f"Error fetching orders: {e}")
        return jsonify({'error': 'Failed to fetch orders'}), 500

@app.route('/add_item', methods=['POST'])
def add_item():
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category = request.form.get('category')
        subcategory = request.form.get('subcategory')
        discount = request.form.get('discount', 0)
        image = request.files.get('image')

        # Validate numeric fields
        price = float(price)
        discount = float(discount)

        # Save the uploaded image
        if image and image.filename != '':
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image.save(image_path)
        else:
            return "Image is required!", 400

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO menu_items (name, description, price, image_path, category, subcategory, discount) VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (name, description, price, image_path, category, subcategory, discount))
            conn.commit()

        return redirect(url_for('menu_management'))
    except Exception as e:
        return f"Error adding item: {e}", 500
@app.route('/manage_orders')
def manage_orders():
    # Your logic to handle orders
    return render_template('orderassign.html')  # Or appropriate response
@app.route('/menu_management')
def menu_management():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM menu_items')
        items = cursor.fetchall()
    return render_template('menu_management.html', items=items, item=None)

# Edit Item
@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            if request.method == 'POST':
                name = request.form.get('name')
                description = request.form.get('description')
                price = float(request.form.get('price'))
                category = request.form.get('category')
                subcategory = request.form.get('subcategory')
                discount = float(request.form.get('discount', 0))
                image = request.files.get('image')

                if image:
                    image_filename = secure_filename(image.filename)
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                    image.save(image_path)
                    cursor.execute('UPDATE menu_items SET name=?, description=?, price=?, image_path=?, category=?, subcategory=?, discount=? WHERE id=?',
                                   (name, description, price, image_path, category, subcategory, discount, item_id))
                else:
                    cursor.execute('UPDATE menu_items SET name=?, description=?, price=?, category=?, subcategory=?, discount=? WHERE id=?',
                                   (name, description, price, category, subcategory, discount, item_id))
                conn.commit()
                return redirect(url_for('menu_management'))

            cursor.execute('SELECT * FROM menu_items WHERE id=?', (item_id,))
            item = cursor.fetchone()
        return render_template('menu_management.html', item=item, items=[])
    except Exception as e:
        return f"Error editing item: {e}", 500

# Delete Item
@app.route('/delete_item/<int:item_id>')
def delete_item(item_id):
    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM menu_items WHERE id=?', (item_id,))
            conn.commit()
        return redirect(url_for('menu_management'))
    except Exception as e:
        return f"Error deleting item: {e}", 500

# Order Assignment Page
@app.route('/orderassign', methods=['GET', 'POST'])
def orderassign():
    return render_template('orderassign.html')

# Fetch Approved Delivery Agents
@app.route('/get_agents', methods=['GET'])
def get_agents():
    conn = get_db_connection()
    agents = conn.execute('''SELECT a.id, a.username, a.location,
                            SUM(ap.orders_delivered) AS orders_delivered,
                            SUM(ap.on_time_deliveries) AS on_time_deliveries,
                            ROUND(AVG(ap.customer_ratings), 1) AS customer_ratings,
                            ROUND(AVG(ap.cancellation_rate), 3) AS cancellation_rate
                        FROM Delivery_Agent a
                        JOIN DeliveryAgentPerformance ap ON a.id = ap.agent_id
                        WHERE a.approved = 1
                        GROUP BY a.id, a.username, a.location;
                        ''').fetchall()
    conn.close()
    agent_data = [dict(agent) for agent in agents]
    return jsonify({'agents': agent_data})
# Assign Order
@app.route('/assign_order', methods=['POST'])
def assign_order():
    data = request.get_json()
    orderId = data['orderId']
    deliveryAgentId = data['deliveryAgentId']
    scheduledDeliveryTime = data['scheduledDeliveryTime']
    pickupTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = 'Pending'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    print(orderId)
    cursor.execute('''SELECT customerName FROM Orders_Analysis WHERE orderId=?''', (orderId,))
    customerName = cursor.fetchone()
    print(orderId)
    print(customerName)
    # Since fetchone() returns a tuple, you need to extract the first element
    if customerName:
        customerName = customerName[0]  # Extract the customerName from the tuple
    else:
        customerName = 'Jane_Smith'
    conn.execute('''INSERT INTO DeliveryData (orderId, deliveryAgentId, pickupTime, scheduledDeliveryTime, status)
                    VALUES (?, ?, ?, ?, ?)''',
                 (orderId, deliveryAgentId, pickupTime, scheduledDeliveryTime, status))
    conn.execute('''INSERT INTO assignedOrders(orderId,customerName,deliveryAgentId,status,action) VALUES(?,?,?,?,?)''',(orderId,customerName,deliveryAgentId,'New','Being Done'))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Order assigned successfully!'})
@app.route('/get_orders', methods=['GET'])
def get_orders():
    conn = get_db_connection()
    query = '''
        SELECT * 
        FROM orders 
        WHERE id NOT IN (SELECT orderId FROM DeliveryData)
    '''
    orders = conn.execute(query).fetchall()
    conn.close()
    # Convert rows to list of dictionaries for JSON response
    orders_list = [dict(order) for order in orders]
    return jsonify(orders_list)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'agent_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
# Login route
'''@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
           '''''' SELECT id, username, approved 
            FROM Delivery_Agent 
            WHERE username = ? AND password = ?
        '''''', (username, password))
        agent = cursor.fetchone()
        conn.close()

        if agent:
            if agent['approved'] == 1:  # Check if the agent is approved
                session['agent_id'] = agent['id']
                session['username'] = agent['username']
                return redirect(url_for('update_status_page'))
            else:
                return render_template('login.html', error="Your account is not approved yet")
        else:
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('agent_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))
'''
# Update status page route
@app.route('/update_status_page')
@login_required
def update_status_page():
    return render_template('update_status.html')

# Get deliveries route
@app.route('/get_deliveries')
@login_required
def get_deliveries():
    agent_id = session.get('agent_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, orderId, pickupTime, scheduledDeliveryTime, status
        FROM DeliveryData
        WHERE deliveryAgentId = ?
        ORDER BY scheduledDeliveryTime DESC
    ''', (agent_id,))

    deliveries = []
    for row in cursor.fetchall():
        deliveries.append({
            'id': row['id'],
            'orderId': row['orderid'],
            'pickupTime': row['pickupTime'],
            'scheduledTime': row['scheduledDeliveryTime'],
            'status': row['status'] or 'Pending'
        })

    conn.close()
    return jsonify(deliveries)

# Update delivery status route
@app.route('/update_status', methods=['POST'])
@login_required
def update_status():
    agent_id = session.get('agent_id')
    data = request.json
    delivery_id = data.get('delivery_id')
    new_status = data.get('status')

    if not delivery_id or not new_status:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify that the delivery belongs to the logged-in agent
        cursor.execute('''
            SELECT deliveryAgentId
            FROM DeliveryData 
            WHERE id = ?
        ''', (delivery_id,))
        result = cursor.fetchone()

        if not result or result['deliveryAgentId'] != agent_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        # Update the status of the delivery
        cursor.execute('''
            UPDATE DeliveryData
            SET status = ?
            WHERE id = ? AND deliveryAgentId = ?
        ''', (new_status, delivery_id, agent_id))

        conn.commit()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/deliveries')
def deliveries():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, orderid, deliveryAgentId, pickupTime, scheduledDeliveryTime, status 
        FROM DeliveryData
    ''')

    deliveries = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(deliveries)

# Render the HTML page
@app.route('/track_delivery')
def track_delivery():
    return render_template('track_delivery.html')


@app.route('/home') 
def start():
    return render_template('homepage.html')

# @app.route('/send_otp', methods=['POST'])
# def send_otp_route():
#     data = request.get_json()
#     email = data.get('email')

#     if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
#         return jsonify({'success': False, 'message': 'Invalid email format.'})

#     otp = str(random.randint(100000, 999999))
#     otp_store[email] = {'otp': otp, 'timestamp': time.time()}  # Store OTP with timestamp

#     if send_otp(email, otp):
#         return jsonify({'success': True, 'message': 'OTP sent to email.'})
#     else:
#         return jsonify({'success': False, 'message': 'Error sending OTP.'})

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        user = ''

        if not role or not username or not password:
            flash('Please provide all required fields (username, password, role).', 'danger')
            return redirect(url_for('login'))

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Querying based on role
            if role == 'deliveryagent':
                cursor.execute("""
                   SELECT * FROM Delivery_Agent  WHERE (contact = ? OR email = ?) AND password = ?
                """, (username,username, password))
                user = cursor.fetchone()

            elif role == 'customer':
                cursor.execute("""
                    SELECT * FROM users WHERE (contact = ? OR email = ?) AND password = ?
                """, (username,username, password))
                user = cursor.fetchone()

            elif role == 'admin' and username == 'admin@google.com' or '1234567890' and password == '123':
                flash('Login successful! Welcome back, Admin.', 'success')
                return redirect(url_for('admin'))  # Redirect to Admin dashboard
            
            else:
                flash('Invalid role selected. Please choose a valid role.', 'danger')
            if user:
                # Extract user details and set session variables
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['email'] = user[2]
                session['role'] = user[4]  # Role is assumed to be at index 4 for both tables
                session['location'] = user[5] if len(user) > 5 else 'Not Provided'
                session['contact'] = user[6] if len(user) > 6 else 'Not Provided'
                session['approved'] = user[7]

                if session['role'].lower() == 'deliveryagent' :
                    if session['approved'] == 1:
                        flash('Login successful! Welcome back, Delivery Agent.', 'success')
                        return redirect(url_for('delivery'))  # Redirect to Delivery Agent dashboard
                    elif session['approved'] == 0:
                        flash("Dear Delivery Agent ,Your approved status is still Pending",'danger')
                    else:
                        flash("Dear Delivery Agent, Your are Rejected by Admin",'danger')

                    return redirect(url_for('login'))  # Redirect to Delivery Agent dashboard
                
                elif session['role'].lower() == 'customer':

                    flash('Login successful! Welcome back, Customer.', 'success')
                    return redirect(url_for('start'))  # Redirect to Customer dashboard
            else:
                flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')



def get_db_connection():
    conn = sqlite3.connect(DATABASE)  # Timeout to avoid lock
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/performance')
def performance():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    agent_id = session['user_id']
    print(agent_id)

    # Ensure get_db_connection() works and returns a valid connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM DeliveryAgentPerformance
            WHERE agent_id = ? 
            ORDER BY year DESC, month DESC
        """, (agent_id,))

        performance_data = cursor.fetchall()
        month = []
        orders_delivered = []
        on_time_deliveries = []
        customer_ratings = []
        cancellation_rate = []

        print(performance_data)
        if not performance_data:
            return render_template('sample.html', bar_chart_filename=None,
                                line_chart_filename=None,
                                performance_table_data=[])
        for i in performance_data:
            print(i[2], i[4], i[5], i[6], i[7])  # Adjust indices based on your data
            month.append(i[2])
            orders_delivered.append(i[4])
            on_time_deliveries.append(i[5])
            customer_ratings.append(i[6])
            cancellation_rate.append(i[7])

        if not month or not orders_delivered or not on_time_deliveries or not customer_ratings or not cancellation_rate:
            return render_template('sample.html', bar_chart_filename=None,
                                line_chart_filename=None,
                                performance_table_data=[])

        # Correct month order for sorting
        months_order = ['January', 'February', 'March', 'April', 'May', 'June', 
                        'July', 'August', 'September', 'October', 'November', 'December']
        
        # Sort by month names (mapping months to their respective index)
        month_data = sorted(zip(month, orders_delivered, on_time_deliveries, customer_ratings, cancellation_rate),
                            key=lambda x: months_order.index(x[0]))
        sorted_months, sorted_orders, sorted_on_time, sorted_ratings, sorted_cancellations = zip(*month_data)

        performance_table_data = [
            {"month": month, "orders": orders, "on_time": on_time, "ratings": ratings, "cancellations": cancellations}
            for month, orders, on_time, ratings, cancellations in zip(sorted_months, sorted_orders, sorted_on_time, sorted_ratings, sorted_cancellations)
        ]
        
        # Bar Chart
        bar_chart_filename = f"performance_bar_chart_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        bar_chart_path = os.path.join(app.config['IMAGE_FOLDER'], bar_chart_filename)
        plt.figure(figsize=(10, 6))
        plt.bar(sorted_months, sorted_orders, color='skyblue')
        plt.xlabel('Month', fontsize=12)
        plt.ylabel('Deliveries', fontsize=12)
        plt.title('Monthly Deliveries Performance (Bar Chart)', fontsize=14)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(bar_chart_path)
        plt.close()

        # Line Chart
        line_chart_filename = f"performance_line_chart_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        line_chart_path = os.path.join(app.config['IMAGE_FOLDER'], line_chart_filename)
        plt.figure(figsize=(10, 6))
        plt.plot(sorted_months, sorted_orders, marker='o', color='skyblue', label='Orders Delivered')
        plt.xlabel('Month', fontsize=12)
        plt.ylabel('Deliveries', fontsize=12)
        plt.title('Monthly Deliveries Performance (Line Chart)', fontsize=14)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(line_chart_path)
        plt.close()

        # Render the template with both charts' filenames
        return render_template('sample.html', bar_chart_filename=bar_chart_filename,
                               line_chart_filename=line_chart_filename,
                               performance_table_data=performance_table_data)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form['email']
        role = request.form['role']
        location = request.form['location']
        contact = request.form['contact']

        print(f'Role received: {role}')

        # Validating password: must be at least 8 characters with at least one number and one special character
        password_pattern = re.compile(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
        if not password_pattern.match(password):
            flash('Password must be at least 8 characters long and include at least one number and one special character.', 'danger')
            return render_template('register.html')

        # Validate mobile number: must be exactly 10 digits
        if not re.fullmatch(r'\d{10}', contact):
            flash('Mobile number must be exactly 10 digits.', 'danger')
            return render_template('register.html')

        # Validate password confirmation
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                print("Connection opened successfully.")

                # Check for duplicate email or contact in both tables
                cursor.execute("""
                    SELECT 1 FROM Delivery_Agent WHERE email = ? OR contact = ?
                    UNION
                    SELECT 1 FROM users WHERE email = ? OR contact = ?
                """, (email, contact, email, contact))
                if cursor.fetchone():
                    flash('Email or mobile number already exists. Please use a different one.', 'danger')
                    return render_template('register.html')
                

                if role.lower() == "deliveryagent":
                    cursor.execute("""
                        INSERT INTO Delivery_Agent (username, password, email, role, location, contact)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (username, password, email, role, location, contact))
                else:
                    cursor.execute("""
                        INSERT INTO users (username, password, email, role, location, contact)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (username, password, email, role, location, contact))
                conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.OperationalError as e:
            flash(f'Database is currently locked: {e}', 'danger')
        except sqlite3.IntegrityError:
            flash('Username or email already exists. Please use another.', 'danger')
        except Exception as e:
            flash(f'Error during Registration: {e}', 'danger')

    return render_template('register.html')  # Ensure register.html is your registration page

@app.route('/info')
def info():
    return render_template('info.html')

@app.route('/save_multiple_address')
def save_multiple_address():
    return render_template('savemultipleaddress.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        message = request.form['message']
        print(name)
        try:
            # Connect to the database
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                # Perform a case-insensitive check using COLLATE NOCASE
                cursor.execute('select * from users where email = ?',(email,))
                user = cursor.fetchone()

                if user:
                    # Insert the contact message into the 'contact_messages' table
                    cursor.execute('''
                        INSERT INTO contact_messages (name, email, message)
                        VALUES (?, ?, ?)
                    ''', (name, email, message))
                    conn.commit()
                    flash("Feedback taken successfully", "success")
                else:
                    flash("Email  does not exist", "danger")

        except sqlite3.Error as e:
            flash(f"An error occurred: {str(e)}", "danger")

    return render_template('contact.html')


# @app.route('/forgot')
# def forgot():
#     return render_template('forgot.html')
#forgot password
@app.route('/forgot')
def forgot():
    return render_template('forgot.html')

# Route for handling recovery form submission
@app.route('/recovery', methods=['GET', 'POST'])
def recovery():
    if request.method == 'POST':
        email = request.form['email']
        
        # Connect to the database to check if the email exists
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        
        if user:
            # Generate a unique token for the recovery link
            token = secrets.token_urlsafe(16)  # Generate a random token
            
            # Create the recovery URL
            recovery_link = url_for('forgot_password', token=token, _external=True)
            
            # Send the recovery email with the link
            msg = Message('Password Recovery Link', recipients=[email],sender='hifidelivery213@gmail.com')
            msg.body = f'Click the link to reset your password: {recovery_link}'
            mail.send(msg)
            
            # Redirect to the confirmation page (forgot.html)
            return render_template('recovery.html', message="A recovery link has been sent to your email address.")
        else:
            conn.close()
            return render_template('recovery.html', error="Invalid email address. Please try again.")
    
    return render_template('recovery.html')

# Route to show the forgot password page when clicking the recovery link
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    token = request.args.get('token')  # Get the token from the URL
    if request.method == 'POST':
        identifier = request.form.get('identifier')  # Can be email or username
        new_password = request.form.get('new_password')
        re_new_password = request.form.get('re_new_password')

        if new_password != re_new_password:
            flash('Passwords do not match. Please try again.', 'error')
            return redirect(url_for('forgot_password', token=token))

        # Hash the new password before storing it (optional but recommended for security)
        hashed_password = new_password  # Replace with hash function if needed

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        try:
            # Update password for the user identified by email or username
            cursor.execute(
                "UPDATE users SET password=? WHERE email=? OR username=?", 
                (hashed_password, identifier, identifier)
            )
            conn.commit()

            # Check if any row was updated
            if cursor.rowcount == 0:
                flash('No user found with the provided email or username.', 'error')
                return redirect(url_for('forgot_password', token=token))

            flash('Password reset successful. Please log in with your new password.', 'success')
            return redirect(url_for('login'))  # Replace 'login' with your login route
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('forgot_password', token=token))
        finally:
            conn.close()

    return render_template('forgot.html')  # The page where users reset their password
#forgot password end
@app.route('/admin', methods=['GET'])
def admin():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Total Users
            cursor.execute("SELECT COUNT(*) AS total_users FROM users")
            total_users = cursor.fetchone()["total_users"]

            # Total Orders
            cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
            total_orders = cursor.fetchone()["total_orders"]

            # Total Revenue
            cursor.execute("""
            SELECT SUM(total_price) AS total_revenue
            FROM orders
            """)
            total_revenue = cursor.fetchone()["total_revenue"]

            # Handle None values for revenue
            total_revenue = round(total_revenue or 0, 2)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        total_users = total_orders = 0
        total_revenue = 0.0

    # Pass data to the admin template
    return render_template(
        'admin.html',
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue
    )

@app.route('/delivery', methods=['GET'])
def delivery():
    # Check if the user is logged in and is a delivery agent
    if 'role' not in session or session['role'].lower() != 'deliveryagent':
        flash('You need to log in as a delivery agent to view this page.', 'danger')
        return redirect(url_for('login'))
    
    delivery_agent_id = session['user_id']
    
    # Fetch new orders assigned to this delivery agent from the 'assignedOrders' table
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT orderId FROM assignedOrders 
            WHERE deliveryAgentId = ? AND status = 'New'
        """, (delivery_agent_id,))
        new_orders = cursor.fetchall()
    # Pass the new orders to the template
    return render_template('deliveryagent.html', new_orders=new_orders)
#---------------------------------------
@app.route('/accept_order', methods=['POST'])
def accept_order():
    data = request.get_json()
    order_id = data.get('orderId')

    if not order_id:
        return jsonify({'success': False, 'error': 'Missing order ID'})

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE assignedOrders 
                SET status = 'In Progress' 
                WHERE orderId = ? AND status = 'New'
            """, (order_id,))
            cursor.execute("UPDATE DeliveryData SET status = 'In Transit' WHERE orderId = ?", (order_id,))
            conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
# Route to handle rejection of an order
@app.route('/reject_order', methods=['POST'])
def reject_order():
    data = request.get_json()
    order_id = data.get('orderId')

    if not order_id:
        return jsonify({'success': False, 'error': 'Missing order ID'})

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM assignedOrders WHERE orderId = ?", (order_id,))
            conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/deliverystatus')
def delivery_status():
    return render_template('deliverystatus.html')

@app.route('/deliveryissue')
def delivery_issue():
    return render_template('deliveryissue.html')

# @app.route('/recovery')
# def recovery():
#     return render_template('recovery.html')

@app.route('/update_details', methods=['GET', 'POST'])
def update_details():
    if 'user_id' not in session:
        flash('Please log in to update your details.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        new_role = request.form['role']
        new_location = request.form['location']
        new_contact = request.form['contact']

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            # Fetch the current role
            cursor.execute('SELECT role FROM users WHERE id = ?', (user_id,))
            current_role = cursor.fetchone()[0]

            if current_role == new_role:
                # If the role hasn't changed, update the existing record in the `users` table
                cursor.execute('''
                    UPDATE users
                    SET username = ?, email = ?, role = ?, location = ?, contact = ?
                    WHERE id = ?
                ''', (new_username, new_email, new_role, new_location, new_contact, user_id))
            else:
                # If the role has changed, move the details to the appropriate table
                if current_role == 'customer':
                    # Move the user details to the `delivery` table
                    cursor.execute('''
                        INSERT INTO Delivery_Agent (id, username, email, role, location, contact)
                        SELECT id, username, email, ?, ?, ? FROM users WHERE id = ?
                    ''', (new_role, new_location, new_contact, user_id))
                else:
                    # Move the delivery details to the `users` table
                    cursor.execute('''
                        INSERT INTO users (id, username, email, role, location, contact)
                        SELECT id, username, email, ?, ?, ? FROM Delivery_Agent WHERE id = ?
                    ''', (new_role, new_location, new_contact, user_id))

                # Remove the old record from the previous table
                if current_role == 'user':
                    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                else:
                    cursor.execute('DELETE FROM delivery WHERE id = ?', (user_id,))

            conn.commit()
            flash('Details updated successfully!', 'success')

            # Update session values
            session['username'] = new_username
            session['email'] = new_email
            session['role'] = new_role
            session['location'] = new_location
            session['contact'] = new_contact

            return redirect(url_for('start'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists. Please choose another.', 'danger')
        finally:
            conn.close()

    # Fetch current user details for the form
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT username, email, role, location, contact FROM users WHERE id = ?', (user_id,))
    user_details = cursor.fetchone()
    conn.close()

    return render_template('profile.html', user={
        'username': user_details[0],
        'email': user_details[1],
        'role': user_details[2],
        'location': user_details[3],
        'contact': user_details[4]
    })

@app.route('/viewprofile')
def viewprofile():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.', 'danger')
        return redirect(url_for('login'))

    user_details = {
        'username': session.get('username'),
        'email': session.get('email'),
        'role': session.get('role'),
        'location': session.get('location'),
        'contact': session.get('contact'),
    }

    return render_template('viewprofile.html', user=user_details)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

# @app.route('/forgot_password', methods=['GET', 'POST'])
# def forgot_password():
#     if request.method == 'POST':
#         identifier = request.form.get('identifier')
#         new_password = request.form.get('new_password')
#         re_new_password = request.form.get('re_new_password')
#         print(f'identifier:{identifier}\nnew_password:{new_password}\nre-new-password:{re_new_password}')
#         if new_password != re_new_password:
#             flash('Passwords do not match. Please try again.', 'error')
#             return redirect(url_for('forgot_password'))
#         flash('Password reset successful. Please log in with your new password.', 'success')
#         return redirect(url_for('start'))

#     return render_template(url_for('forgot'))

@app.route('/admin/approvals', methods=['GET'])
def admin_approvals():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Access restricted to administrators.', 'danger')
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, role, contact FROM users WHERE approved = 0')
    pending_users = cursor.fetchall()
    conn.close()

    return render_template('approvals.html', pending_users=pending_users)

@app.route('/admin/approve_user/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Access restricted to administrators.', 'danger')
        return redirect(url_for('login'))

    action = request.form['action']  # 'approve' or 'reject'
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    if action == 'approve':
        cursor.execute('UPDATE users SET approved = 1 WHERE id = ?', (user_id,))
        flash('User approved successfully.', 'success')
    elif action == 'reject':
        cursor.execute('UPDATE users SET approved = -1 WHERE id = ?', (user_id,))
        flash('User rejected successfully.', 'danger')
    conn.commit()
    conn.close()

    return redirect(url_for('admin_approvals'))

@app.route('/submit_agent_issue',methods=['POST'])
def submit_agent_issue():
    if request.method == 'POST':
        agent_name = request.form['agent_name']
        order_id = request.form['order_id']
        issue_type = request.form['issue_type']
        details = request.form['details']
        print(agent_name,order_id,issue_type,details)

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Delivery_Agent_Report(Agent, OrderId, IssueType,IssueDetails)
                    VALUES (?, ?, ?, ?)
                """, (agent_name,order_id,issue_type,details))
                conn.commit()
                print("Done 1")

            flash('Reported successfully', 'success')
            return redirect(url_for('delivery'))
        except sqlite3.OperationalError:
            flash('Database is currently locked. Please try again later.', 'danger')
            return redirect(url_for('delivery_issue'))




@app.route('/agent_issues', methods=['GET'])
def agent_issues():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Fetch data from Delivery_Agent_Report
            cursor.execute('SELECT * FROM Delivery_Agent_Report')  
            agent_issues = cursor.fetchall()

            # Fetch data from contact_messages
            cursor.execute('SELECT id, name, email, message FROM contact_messages')  
            customer_feedback = cursor.fetchall()

        # Pass both datasets to the template
        return render_template('agent_issues.html', 
                               agent_issues=agent_issues, 
                               customer_feedback=customer_feedback)

    except sqlite3.OperationalError:
        flash('Database is currently locked. Please try again later.', 'danger')
        return redirect(url_for('delivery'))

# Function to get assigned orders for the delivery agent
def get_assigned_orders(delivery_agent_id):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT o.orderId, o.customerName, u.contact AS phone, u.location AS address, a.status, a.action, a.deliveryAgentId
            FROM Orders_Analysis o
            JOIN assignedOrders a ON o.orderId = a.orderId
            JOIN users u ON a.customerName = u.username
            WHERE a.deliveryAgentId = ?;
        """, (delivery_agent_id,))
        orders = cursor.fetchall()
        conn.close()
        print(orders)  # Debugging purpose
        return orders
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        return []

@app.route('/view_orders')
def view_orders():
    
    delivery_agent_id = session['user_id']
    
    if not delivery_agent_id:
        return "Error: Delivery Agent ID is required", 400

    # Fetch orders assigned to the logged-in delivery agent
    orders = get_assigned_orders(delivery_agent_id)
    if not orders:
        return "No orders found", 404
    
    return render_template('deliverystatus.html', orders=orders)



# Utility function to fetch orders by status
def get_orders_by_status(agent_id,status=None):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Fetch orders based on delivery agent ID and status
        if status:
            cursor.execute("""
            SELECT o.orderId, o.customerName, u.contact AS phone, u.location AS address, a.status, a.action, a.deliveryAgentId
            FROM Orders_Analysis o
            JOIN assignedOrders a ON o.orderId = a.orderId
            JOIN users u ON a.customerName = u.username
            WHERE a.deliveryAgentId = ? and a.status = ?;
        """, (agent_id,status))
        else:
            cursor.execute("""
            SELECT o.orderId, o.customerName, u.contact AS phone, u.location AS address, a.status, a.action, a.deliveryAgentId
            FROM Orders_Analysis o
            JOIN assignedOrders a ON o.orderId = a.orderId
            JOIN users u ON a.customerName = u.username
            WHERE a.deliveryAgentId = ?;
        """, (agent_id,))
        
        orders = cursor.fetchall()
        return orders
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        conn.close()

# Route to filter orders based on their status
@app.route('/status_of_order', methods=['GET'])
def status():
    delivery_agent_id = session['user_id']
    status_filter = request.args.get('status')  # Get the 'status' parameter from the request
    orders = get_orders_by_status(delivery_agent_id,status_filter)  # Fetch orders from the database
    
    if not orders:
        flash("No orders found for the given status.", "info")  # Display a flash message for no results
        orders = []  # Pass an empty list to avoid rendering issues
    
    return render_template('deliverystatus.html', orders=orders)


def get_all_users():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()  # Fetch all rows
    conn.close()
    return users

@app.route('/delete_user', methods=['POST'])
def delete_user():
    user_id = request.form.get('delete_user')  # Get user ID from the button value

    if user_id:
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            # Delete the user from the database
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            flash("User deleted successfully!", "success")
        except Exception as e:
            flash(f"Error deleting user: {str(e)}", "danger")
    else:
        flash("Invalid user ID. Unable to delete user.", "warning")

    return redirect('/manageuser')  # Redirect back to the management page

# Function to fetch all delivery agents
def get_all_delivery_agents():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Delivery_Agent")
    agents = cursor.fetchall()  # Fetch all rows
    conn.close()
    return agents

@app.route('/manageuser')
def view_users_agents():
    # Fetch users and delivery agents
    users = get_all_users()
    agents = get_all_delivery_agents()

    # Pass the data to the template
    return render_template('manageuser.html', users=users, agents=agents)
'''
@app.route('/assign_order', methods=['POST'])
def assign_order():
    data = request.get_json()
    orderId = data['orderId']
    deliveryAgentId = data['deliveryAgentId']
    scheduledDeliveryTime = data['scheduledDeliveryTime']
    pickupTime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = 'Pending'

    conn = get_db_connection()
    conn.execute(''''''INSERT INTO DeliveryData (orderId, deliveryAgentId, pickupTime, scheduledDeliveryTime, status)
                    VALUES (?, ?, ?, ?, ?)'''''',
                 (orderId, deliveryAgentId, pickupTime, scheduledDeliveryTime, status))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Order assigned successfully!'})

@app.route('/get_orders', methods=['GET'])
def get_orders():
    conn = get_db_connection()
    query = ''''''
        SELECT * 
        FROM orders 
        WHERE id NOT IN (SELECT orderId FROM DeliveryData)
    ''''''
    orders = conn.execute(query).fetchall()
    conn.close()
    # Convert rows to list of dictionaries for JSON response
    orders_list = [dict(order) for order in orders]
    return jsonify(orders_list)
'''
# Login required decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'agent_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/update_agent_status', methods=['POST'])
def update_agent_status():
    agent_id = request.form.get('update_agent')  # Get agent ID from button
    new_status = request.form.get(f'status_{agent_id}')  # Get status for the agent

    # Debugging print statements (remove in production)
    print(f"Agent ID: {agent_id}")
    print(f"New Status: {new_status}")

    if agent_id and new_status is not None:
        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            # Update the agent's status
            cursor.execute("""
                UPDATE Delivery_Agent
                SET approved = ?
                WHERE id = ?
            """, (new_status, agent_id))
            conn.commit()
            conn.close()
            flash("Delivery agent status updated successfully!", "success")
        except Exception as e:
            print(f"Error: {e}")  # Debugging
            flash(f"Error updating delivery agent status: {str(e)}", "danger")
    else:
        flash("Invalid input. Unable to update delivery agent status.", "warning")

    return redirect('/manageuser')  # Redirect back to the management page

@app.route('/items_analysis_admin')
def items_analysis_admin():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Adjusted query to count orders
            cursor.execute('''
            SELECT mi.id, mi.name, mi.price, mi.category, mi.subcategory, mi.discount,
            COUNT(o.orderId) AS times_ordered
            FROM menu_items mi
            LEFT JOIN Orders_Analysis o ON mi.name = o.productName  -- Match items with orders
            GROUP BY mi.id
            ORDER BY times_ordered DESC;
            ''')
            items = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        items = []

    return render_template('items_analysis.html', items=items)

@app.route('/customer-rating')
def customer_rating():
    # Check if the user is logged in
    if 'username' not in session:
        return redirect('/login')
    
    username = session['username']
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        # Fetch completed orders for the logged-in customer
        query = """
            SELECT ao.orderId, o.items, o.timestamp, o.total_price
            FROM assignedOrders ao
            JOIN orders o ON ao.orderId = o.id
            WHERE ao.customerName = ? AND ao.status = 'Completed'
        """
        cursor = conn.execute(query, (username,))
        orders = cursor.fetchall()

        # Prepare data for the template
        order_data = []
        for order in orders:
            # Fetch existing feedback for each order
            feedback_query = """
                SELECT rating, review FROM OrderFeedback 
                WHERE orderId = ? AND customerId = (SELECT id FROM users WHERE username = ?)
            """
            feedback_cursor = conn.execute(feedback_query, (order['orderId'], username))
            feedback = feedback_cursor.fetchone()
            order_data.append({
                'order_id': order['orderId'],
                'product_name': order['items'],
                'order_date': order['timestamp'],
                'price': order['total_price'],
                'feedback': feedback  # Pass feedback to template
            })
    finally:
        conn.close()  # Ensure the connection is closed

    return render_template('customer-rating.html', orders=order_data)
@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    username = session['username']
    data = request.get_json()

    # Extract feedback details from the request
    order_id = data.get('order_id')
    rating = data.get('rating')
    review = data.get('review')

    if not order_id or not rating or not review:
        return jsonify({'error': 'Incomplete feedback data'}), 400

    conn = sqlite3.connect(DATABASE)
    try:
        # Get the customer ID
        cursor = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
        customer = cursor.fetchone()
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        customer_id = customer[0]

        # Save feedback to the database
        cursor.execute("""
            INSERT INTO OrderFeedback (orderId, customerId, rating, review)
            VALUES (?, ?, ?, ?)
        """, (order_id, customer_id, rating, review))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'message': 'Feedback submitted successfully'}), 200


@app.route('/view_ratings')
def order_ratings():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Simple query to fetch data from OrderFeedback table without any ordering
            cursor.execute('''
            SELECT id, orderId, customerId, rating, review, feedbackDate
            FROM OrderFeedback;
            ''')
            feedback_data = cursor.fetchall()  # Fetch all rows
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        feedback_data = []

    return render_template('view-ratings.html',  feedback_data=feedback_data)

import matplotlib.pyplot as plt
import os

@app.route('/customer_demographics', methods=['GET'])
def customer_demographics():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Fetch customer count and order frequency grouped by location
            cursor.execute('''
                SELECT 
                    location, 
                    COUNT(DISTINCT id) AS customer_count,
                    COUNT(o.orderId) AS order_frequency
                FROM users u
                LEFT JOIN Orders_Analysis o ON u.username = o.customerName
                WHERE u.role = 'customer'
                GROUP BY location
                ORDER BY order_frequency DESC
            ''')
            demographics_data = [
                {"location": row["location"], "customer_count": row["customer_count"], "order_frequency": row["order_frequency"]}
                for row in cursor.fetchall()
            ]

        # Extract data for the chart
        locations = [row['location'] for row in demographics_data]
        customer_counts = [row['customer_count'] for row in demographics_data]
        order_frequencies = [row['order_frequency'] for row in demographics_data]

        # Generate a grouped bar chart
        fig, ax = plt.subplots(figsize=(10, 6))
        bar_width = 0.4
        index = range(len(locations))
        
        # Bar chart for customer count
        ax.bar(index, customer_counts, bar_width, label='Customer Count', color='skyblue')
        # Bar chart for order frequency
        ax.bar([i + bar_width for i in index], order_frequencies, bar_width, label='Order Frequency', color='orange')

        # Chart details
        ax.set_xlabel('Locations', fontsize=12)
        ax.set_ylabel('Count', fontsize=12)
        ax.set_title('Customer Demographics and Order Frequency by Location', fontsize=14)
        ax.set_xticks([i + bar_width / 2 for i in index])
        ax.set_xticklabels(locations, rotation=45, ha='right', fontsize=10)
        ax.legend()

        # Save the chart as an image
        chart_filename = f"customer_demographics_chart_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
        chart_path = os.path.join(app.config['IMAGE_FOLDER'], chart_filename)
        plt.tight_layout()
        plt.savefig(chart_path)
        plt.close()
        
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "danger")
        demographics_data = []
        chart_filename = None

    return render_template('customerdemographics.html', demographics_data=demographics_data, chart_filename=chart_filename)

@app.route('/sales_trends', methods=['GET'])
def sales_trends():
    if request.method == 'GET' and 'period' not in request.args:
        # Render the frontend page
        return render_template('sales_trends.html')

    # Handle API request for trends data
    period = request.args.get('period', 'daily')  # Default to daily
    if period not in ['daily', 'weekly', 'monthly']:
        return jsonify({"error": "Invalid period. Choose daily, weekly, or monthly."}), 400

    # Define SQL query based on the selected period
    today = datetime.now()
    if period == 'daily':
        date_filter = today - timedelta(days=7)  # Last 7 days
        group_by = "DATE(orderDate)"  # Group by exact date
    elif period == 'weekly':
        date_filter = today - timedelta(weeks=4)  # Last 4 weeks
        group_by = "strftime('%Y-%W', orderDate)"  # Group by week
    elif period == 'monthly':
        date_filter = today - timedelta(days=365)  # Last year
        group_by = "strftime('%Y-%m', orderDate)"  # Group by month

    query = f"""
        SELECT 
            {group_by} AS period,
            COUNT(Orders_Analysis.orderId) AS totalOrders,
            SUM(menu_items.price * (1 - menu_items.discount / 100.0)) AS totalRevenue
        FROM Orders_Analysis
        INNER JOIN menu_items ON Orders_Analysis.productName = menu_items.name
        WHERE orderDate >= ?
        GROUP BY period
        ORDER BY period
    """

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # print("Query:", query)  # Debugging the query
            print("Date Filter:", date_filter.strftime('%Y-%m-%d'))  # Debugging the date filter
            cursor.execute(query, (date_filter.strftime('%Y-%m-%d'),))
            result = cursor.fetchall()

            # Format data for JSON response
            trends = [
                {
                    "label": row["period"],
                    "totalOrders": row["totalOrders"],
                    "totalRevenue": row["totalRevenue"]
                } for row in result
            ]
            print("Trends Data:", trends)  # Debugging the trends data
        return jsonify(trends)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    
@app.route('/delivery_kpi', methods=['GET', 'POST'])
def delivery_kpi():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch overall KPIs
    cursor.execute("""
        SELECT 
            AVG((strftime('%s', deliveryTime) - strftime('%s', pickupTime)) / 60.0) AS avg_delivery_time,
            SUM(CASE 
                    WHEN strftime('%s', deliveryTime) <= strftime('%s', scheduledDeliveryTime) THEN 1 
                    ELSE 0 
                END) * 100.0 / COUNT(*) AS on_time_delivery_rate,
            COUNT(*) AS total_deliveries
        FROM DeliveryData
        WHERE status = 'Delivered'
    """)
    overall_kpi = cursor.fetchone()

    # Fetch monthly KPIs
    cursor.execute("""
        SELECT 
            strftime('%Y-%m', deliveryTime) AS month,
            AVG((strftime('%s', deliveryTime) - strftime('%s', pickupTime)) / 60.0) AS avg_delivery_time,
            SUM(CASE 
                    WHEN strftime('%s', deliveryTime) <= strftime('%s', scheduledDeliveryTime) THEN 1 
                    ELSE 0 
                END) * 100.0 / COUNT(*) AS on_time_delivery_rate,
            COUNT(*) AS total_deliveries
        FROM DeliveryData
        WHERE status = 'Delivered'
        GROUP BY month
        ORDER BY month
    """)
    monthly_kpis = cursor.fetchall()

    conn.close()

    if request.method == 'POST':
        return jsonify({
            "overall": {
                "avg_delivery_time": overall_kpi[0],
                "on_time_delivery_rate": overall_kpi[1],
                "total_deliveries": overall_kpi[2]
            },
            "monthly": [
                {
                    "month": row[0],
                    "avg_delivery_time": row[1],
                    "on_time_delivery_rate": row[2],
                    "total_deliveries": row[3]
                } for row in monthly_kpis
            ]
        })

    return render_template('delivery_kpi.html')
@app.route('/update_status_of_order', methods=['POST'])
def update_status_of_order():
    try:
        data = request.get_json()
        order_id = data.get("order_id")
        
        if not order_id:
            return jsonify({"error": "Invalid order ID"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update order status to 'Completed'
        cursor.execute("UPDATE assignedOrders SET status = 'Completed' WHERE orderId = ?", (order_id,))
        cursor.execute("UPDATE DeliveryData SET status = 'Delivered' WHERE orderId = ?", (order_id,))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "order_id": order_id, "new_status": "Completed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/ordersummary')
def ordersummary():
    conn = get_db_connection()
    name=session["username"]
    print(name)
    cursor = conn.cursor()
    query = '''
        SELECT DISTINCT r.*,o.customerName,ao.status
        FROM orders r
		JOIN Orders_Analysis o on r.id=o.orderID  
		JOIN assignedOrders ao on o.orderId=ao.orderId
		WHERE o.customerName= ?
    '''
    orders = cursor.execute(query,(name,)).fetchall()
    
    conn.close()
    # Convert rows to list of dictionaries for JSON response
    orders_list = [dict(order) for order in orders]
    return render_template('orderhistory.html', orders=orders_list)
@app.route('/order_summary')
def order_summary():
    conn = get_db_connection()
    name=session["username"]
    print(name)
    cursor = conn.cursor()
    query = '''
        SELECT DISTINCT r.*,o.customerName,ao.status
        FROM orders r
		JOIN Orders_Analysis o on r.id=o.orderID  
		JOIN assignedOrders ao on ao.status='Completed'
		WHERE o.customerName= ? ORDER BY r.id DESC
    '''
    orders = cursor.execute(query,(name,)).fetchone()
    print(orders)
    conn.close()
    # Convert rows to list of dictionaries for JSON response
    orders_list = [dict(orders)]
    print(orders_list)
    return render_template('ordersummary.html', orders=orders_list)
if __name__ == '__main__':
    app.run(debug=True) 
