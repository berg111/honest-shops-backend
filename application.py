import os
from flask import Flask, render_template, request, url_for, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_mail import Mail, Message
import requests
from dotenv import load_dotenv
from all_shops import ALL_SHOPS

from sqlalchemy.sql import func

basedir = os.path.abspath(os.path.dirname(__file__))

application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
db = SQLAlchemy(application)
cors = CORS(application)

load_dotenv()
GOOGLE_PLACES_API_KEY = os.getenv('GOOGLE_PLACES_API_KEY')
SERVER_EMAIL = os.getenv('SERVER_EMAIL')
CONTACT_RECIPIENT = os.getenv('CONTACT_RECIPIENT')

application.config['MAIL_SERVER'] = 'smtp.gmail.com'
application.config['MAIL_PORT'] = 587  # TLS port
application.config['MAIL_USE_TLS'] = True
application.config['MAIL_USE_SSL'] = False
application.config['MAIL_USERNAME'] = SERVER_EMAIL  # Your Gmail address
application.config['MAIL_PASSWORD'] = os.getenv('GOOGLE_EMAIL_APP_PASS')  # The app password you generated
application.config['MAIL_DEFAULT_SENDER'] = ('Honest Shops SERVER', SERVER_EMAIL)  # Default sender name and Gmail address

mail = Mail(application)


class State(db.Model):
    __tablename__ = 'state'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(25), nullable=False)

    def __repr__(self):
        return f'<State {self.name}>'
    
    def json(self):
        return {
            "id": self.id,
            "name": self.name,
        }

class Address(db.Model):
    __tablename__ = 'address'

    id = db.Column(db.Integer, primary_key=True)
    address_1 = db.Column(db.String(100), nullable=False)
    address_2 = db.Column(db.String(100), nullable=True)
    address_3 = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state_id =  db.Column(
        db.Integer,
        db.ForeignKey('state.id'),
        nullable=False,
    )
    postal_code = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Address {self.address_1}>'
    
    def json(self):
        return {
            "id": self.id,
            "address_1": self.address_1,
            "address_2": self.address_2,
            "address_3": self.address_3,
            "city": self.city,
            "state_id": self.state_id,
            "postal_code": self.postal_code,
        }

class Shop(db.Model):
    __tablename__ = 'shop'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address_id = db.Column(
        db.Integer,
        db.ForeignKey('address.id'),
        nullable=False,
    )
    is_verified = db.Column(db.Boolean, nullable=False)

    def __repr__(self):
        return f'<Shop {self.name}>'
    
    def json(self):
        return {
            "id": self.id,
            "name": self.name,
            "address_id": self.address_id,
            "is_verified": self.is_verified,
        }

@application.route('/')
def index():
    shops = Shop.query.all()
    addresses = Address.query.all()
    states = State.query.all()
    return render_template('index.html', shops=shops, addresses=addresses, states=states)

@application.route('/create/state/', methods=('GET', 'POST'))
def create_state():
    if request.method == 'POST':
        name = request.form['name']
        state = State(name=name)
        db.session.add(state)
        db.session.commit()
        return redirect(url_for('index'))
    
    return render_template('create_state.html')

@application.route('/create/address/', methods=('GET', 'POST'))
def create_address():
    if request.method == 'POST':
        address_1 = request.form['address_1']
        address_2 = request.form['address_2']
        address_3 = request.form['address_3']
        city = request.form['city']
        state_id = request.form['state_id']
        postal_code = int(request.form['postal_code'])
        # TODO: add geoencoding and lat / longitude
        address = Address(address_1=address_1,
                          address_2=address_2,
                          address_3=address_3,
                          city=city,
                          state_id=state_id,
                          postal_code=postal_code,)
        db.session.add(address)
        db.session.commit()
        return redirect(url_for('index'))
    
    return render_template('create_address.html')

@application.route('/create/shop/', methods=('GET', 'POST'))
def create_shop():
    if request.method == 'POST':
        name = request.form['name']
        address_id = request.form['address_id']
        is_verified = request.form['is_verified']
        if is_verified.lower() == "true":
            is_verified = True
        else:
            is_verified = False
        shop = Shop(name=name,
                    address_id=address_id,
                    is_verified=is_verified,)
        db.session.add(shop)
        db.session.commit()
        return redirect(url_for('index'))
    
    return render_template('create_shop.html')





# Routes for front-end
@application.route('/get-all-shops', methods=['GET'])
def get_all_shops():

    # MANUALLY ADDING SHOPS
    response = jsonify(ALL_SHOPS)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

    # USING AN ACTUAL DATABASE
    '''
    shops = Shop.query.all()
    full_shop_data = []
    for shop in shops:
        address = Address.query.get(shop.address_id)
        state = State.query.get(address.state_id)
        full_shop = {
            "id": shop.id,
            "name": shop.name,
            "address": {
                "id": address.id,
                "address_1": address.address_1,
                "address_2": address.address_2,
                "address_3": address.address_3,
                "city": address.city,
                "state": state.name,
                "postal_code": address.postal_code,
            },
            "is_verified": shop.is_verified,
        }
        full_shop_data.append(full_shop)
    return jsonify(full_shop_data)
    '''

# helper function for parsing the response from listing api
def format_google_listing(google_response):
    name = google_response['name']
    is_open_now = google_response['opening_hours']['open_now']
    opening_hours = google_response['opening_hours']['weekday_text']
    formatted_address = google_response['formatted_address']
    formatted_phone_number = google_response['formatted_phone_number']
    rating = google_response['rating']

    formatted_listing = {
        'name': name, 
        'is_open_now': is_open_now,
        'opening_hours': opening_hours,
        'formatted_address': formatted_address,
        'formatted_phone_number': formatted_phone_number,
        'rating': rating,
    }

    return formatted_listing

@application.route('/get-google-listing', methods=['GET'])
def get_google_listing():
    place_id = request.args.get('placeId')

    if not place_id:
        return jsonify({'error': 'placeId parameter is required'}), 400

    if not GOOGLE_PLACES_API_KEY:
        return jsonify({'error': 'Google Places API key is not configured'}), 500

    url = f'https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&key={GOOGLE_PLACES_API_KEY}'

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx and 5xx)
        data = response.json()
        data_trimmed = data['result']
        formatted_google_details = format_google_listing(data_trimmed)
        formatted_google_details = jsonify(formatted_google_details)
        formatted_google_details.headers.add('Access-Control-Allow-Origin', '*')
        return formatted_google_details
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Google listing: {e}")
        return jsonify({'error': 'Failed to fetch Google listing'}), 500

@application.route('/handle-contact-form', methods=['POST'])
def handle_contact_form():
    data = request.json

    name = data.get('name')
    email = data.get('email')
    message = data.get('message')

    # Create the email content
    subject = "New Contact Form Submission"
    body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"

    # Create a Message object
    msg = Message(subject=subject, recipients=[CONTACT_RECIPIENT], body=body)

    try:
        # Send the email
        mail.send(msg)
        return {"status": "success", "message": "Form data received and email sent"}, 200
    except Exception as e:
        # Handle errors during email sending
        print(f"Error sending email: {e}")
        return {"status": "error", "message": "Failed to send email"}, 500
