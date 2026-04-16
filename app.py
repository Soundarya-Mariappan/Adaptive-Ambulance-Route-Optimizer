import os
import random
import math
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests
import openrouteservice

# Load environment variables
load_dotenv()

# Create Flask application instance
app = Flask(__name__)

# Configure the application
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///ambulance_tracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'signin'

# Helper functions
def calculate_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two points in kilometers"""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lng / 2) * math.sin(delta_lng / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def simulate_traffic_conditions():
    """Simulate traffic conditions for demo purposes"""
    conditions = ['light', 'moderate', 'heavy']
    weights = [0.4, 0.4, 0.2]  # 40% light, 40% moderate, 20% heavy
    return random.choices(conditions, weights=weights)[0]

def generate_alternative_routes(origin_coords, dest_coords, primary_route):
    """Generate alternative routes using nearby waypoints when only 1 route is found"""
    import random
    
    alternative_routes = []
    
    try:
        # Extract basic info from primary route
        primary_distance = float(primary_route['distance'].replace(' km', ''))
        primary_duration = int(primary_route['duration'].replace(' mins', ''))
        
        # Generate 2 alternative routes with different waypoints
        for alt_index in range(2):
            print(f"Generating alternative route {alt_index + 1}...")
            
            # Create waypoints by offsetting from the direct path
            mid_lat = (origin_coords[1] + dest_coords[1]) / 2
            mid_lng = (origin_coords[0] + dest_coords[0]) / 2
            
            # Add random offset to create different paths
            if alt_index == 0:
                # Route via slightly north
                waypoint_lat = mid_lat + 0.01 + random.uniform(0, 0.005)
                waypoint_lng = mid_lng + random.uniform(-0.005, 0.005)
                route_name = "Northern Route"
            else:
                # Route via slightly south  
                waypoint_lat = mid_lat - 0.01 - random.uniform(0, 0.005)
                waypoint_lng = mid_lng + random.uniform(-0.005, 0.005)
                route_name = "Southern Route"
            
            # Try to get actual route via waypoint from OSRM
            try:
                osrm_url = f"http://router.project-osrm.org/route/v1/driving/{origin_coords[0]},{origin_coords[1]};{waypoint_lng},{waypoint_lat};{dest_coords[0]},{dest_coords[1]}"
                params = {
                    'overview': 'full',
                    'geometries': 'geojson',
                    'steps': 'true'
                }
                headers = {'User-Agent': 'AmbulanceTracker/1.0'}
                
                response = requests.get(osrm_url, params=params, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    waypoint_data = response.json()
                    
                    if waypoint_data.get('routes'):
                        route = waypoint_data['routes'][0]
                        
                        # Get route details
                        base_duration = route.get('duration', primary_duration * 60 * 1.2)  # 20% longer
                        base_distance = route.get('distance', primary_distance * 1000 * 1.2)  # 20% longer
                        coordinates = route.get('geometry', {}).get('coordinates', [])
                        
                        # Simulate different traffic conditions for alternatives
                        traffic_conditions = ['moderate', 'light', 'heavy']
                        traffic_condition = traffic_conditions[alt_index % len(traffic_conditions)]
                        
                        if traffic_condition == 'light':
                            traffic_multiplier = 1.0
                            traffic_status = "Light Traffic"
                            traffic_color = "green"
                            delay_minutes = 0
                        elif traffic_condition == 'moderate':
                            traffic_multiplier = 1.3
                            traffic_status = "Moderate Traffic"
                            traffic_color = "orange"
                            delay_minutes = round((base_duration * 0.3) / 60)
                        else:
                            traffic_multiplier = 1.6
                            traffic_status = "Heavy Traffic"
                            traffic_color = "red"
                            delay_minutes = round((base_duration * 0.6) / 60)
                        
                        duration_with_traffic = base_duration * traffic_multiplier
                        
                        # Get turn-by-turn instructions
                        steps = []
                        if 'legs' in route:
                            for leg in route['legs']:
                                if 'steps' in leg:
                                    for step in leg['steps']:
                                        if 'maneuver' in step and 'instruction' in step['maneuver']:
                                            steps.append(step['maneuver']['instruction'])
                        
                        alternative_routes.append({
                            'route_index': alt_index + 1,
                            'distance': f"{round(base_distance / 1000, 1)} km",
                            'duration': f"{round(duration_with_traffic / 60)} mins",
                            'normal_duration': f"{round(base_duration / 60)} mins",
                            'traffic_delay_minutes': delay_minutes,
                            'traffic_status': traffic_status,
                            'traffic_color': traffic_color,
                            'coordinates': coordinates,
                            'steps': steps if steps else [f'Head towards {route_name}', 'Continue on alternative route', 'Arrive at destination'],
                            'route_type': route_name
                        })
                        
                        print(f"Generated {route_name}: {round(base_distance / 1000, 1)} km, {round(duration_with_traffic / 60)} mins")
                        continue
                        
            except Exception as waypoint_error:
                print(f"Waypoint routing error for alternative {alt_index + 1}: {waypoint_error}")
            
            # Fallback: Create simulated alternative route
            print(f"Creating simulated alternative route {alt_index + 1}")
            
            # Simulate alternative route characteristics
            distance_factor = 1.1 + (alt_index * 0.15)  # 10-25% longer
            time_factor = 1.05 + (alt_index * 0.1)      # 5-15% longer
            
            alt_distance = primary_distance * distance_factor
            alt_duration = primary_duration * time_factor
            
            # Generate coordinates for simulated route
            alt_coordinates = generate_alternative_coordinates(origin_coords, dest_coords, alt_index)
            
            # Different traffic conditions
            traffic_conditions = ['light', 'moderate', 'heavy']
            traffic_condition = traffic_conditions[alt_index % len(traffic_conditions)]
            
            if traffic_condition == 'light':
                traffic_multiplier = 1.0
                traffic_status = "Light Traffic"
                traffic_color = "green"
                delay_minutes = 0
            elif traffic_condition == 'moderate':
                traffic_multiplier = 1.3
                traffic_status = "Moderate Traffic"
                traffic_color = "orange"
                delay_minutes = round((alt_duration * 0.3))
            else:
                traffic_multiplier = 1.6
                traffic_status = "Heavy Traffic"
                traffic_color = "red"
                delay_minutes = round((alt_duration * 0.6))
            
            final_duration = alt_duration * traffic_multiplier
            
            alternative_routes.append({
                'route_index': alt_index + 1,
                'distance': f"{round(alt_distance, 1)} km",
                'duration': f"{round(final_duration)} mins",
                'normal_duration': f"{round(alt_duration)} mins",
                'traffic_delay_minutes': delay_minutes,
                'traffic_status': traffic_status,
                'traffic_color': traffic_color,
                'coordinates': alt_coordinates,
                'steps': [f'Head towards alternative route {alt_index + 1}', 'Continue on alternative path', 'Arrive at destination'],
                'route_type': f'Alternative {alt_index + 1}'
            })
            
            print(f"Created simulated alternative {alt_index + 1}: {round(alt_distance, 1)} km, {round(final_duration)} mins")
    
    except Exception as e:
        print(f"Error generating alternative routes: {e}")
    
    return alternative_routes

def generate_alternative_coordinates(origin_coords, dest_coords, route_index):
    """Generate coordinates for alternative route paths"""
    import random
    
    # Create a path that deviates from the direct route
    coordinates = []
    
    # Start point
    coordinates.append([origin_coords[0], origin_coords[1]])
    
    # Create waypoints that deviate from direct path
    steps = 8  # Number of intermediate points
    
    for i in range(1, steps):
        progress = i / steps
        
        # Linear interpolation between start and end
        base_lng = origin_coords[0] + (dest_coords[0] - origin_coords[0]) * progress
        base_lat = origin_coords[1] + (dest_coords[1] - origin_coords[1]) * progress
        
        # Add deviation based on route index
        if route_index == 0:
            # Route 1: Deviate north
            deviation_lat = 0.003 * random.uniform(0.5, 1.5) * (1 - abs(progress - 0.5) * 2)
            deviation_lng = random.uniform(-0.002, 0.002)
        else:
            # Route 2: Deviate south
            deviation_lat = -0.003 * random.uniform(0.5, 1.5) * (1 - abs(progress - 0.5) * 2)
            deviation_lng = random.uniform(-0.002, 0.002)
        
        coordinates.append([base_lng + deviation_lng, base_lat + deviation_lat])
    
    # End point
    coordinates.append([dest_coords[0], dest_coords[1]])
    
    return coordinates

def parse_coordinates(coord_str):
    """Parse coordinates from string format"""
    try:
        if ',' in coord_str:
            # Format: "lat,lng"
            parts = coord_str.strip().split(',')
            if len(parts) == 2:
                lat, lng = map(float, parts)
                return [lng, lat]  # OpenRouteService uses [lng, lat] format
        
        # Try to geocode address using Nominatim (free)
        return geocode_address(coord_str)
    except Exception as e:
        print(f"Coordinate parsing error: {e}")
        return None

def geocode_address(address):
    """Geocode address using Nominatim (free OpenStreetMap service) with improved detection"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        headers = {'User-Agent': 'AmbulanceTracker/1.0'}
        
        print(f"Geocoding address: '{address}'")
        
        # Strategy 1: Try with Coimbatore context first
        params = {
            'q': f"{address}, Coimbatore, Tamil Nadu, India",
            'format': 'json',
            'limit': 10,  # Get more results to choose from
            'countrycodes': 'in',
            'addressdetails': 1
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data:
                print(f"Found {len(data)} results with Coimbatore context")
                
                # Look for results in extended Coimbatore area (more flexible bounds)
                for result in data:
                    lat = float(result['lat'])
                    lng = float(result['lon'])
                    display_name = result.get('display_name', '')
                    
                    # Extended Coimbatore area bounds (more flexible)
                    if 10.7 <= lat <= 11.3 and 76.6 <= lng <= 77.3:
                        print(f"Found Coimbatore area result: {lat}, {lng} - {display_name}")
                        return [lng, lat]
                
                # If no Coimbatore results, take the first Tamil Nadu result
                for result in data:
                    lat = float(result['lat'])
                    lng = float(result['lon'])
                    display_name = result.get('display_name', '')
                    
                    if 'Tamil Nadu' in display_name or 'TN' in display_name:
                        print(f"Found Tamil Nadu result: {lat}, {lng} - {display_name}")
                        return [lng, lat]
        
        # Strategy 2: Try with just Tamil Nadu context
        print(f"Trying with Tamil Nadu context for '{address}'")
        params = {
            'q': f"{address}, Tamil Nadu, India",
            'format': 'json',
            'limit': 10,
            'countrycodes': 'in',
            'addressdetails': 1
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data:
                print(f"Found {len(data)} results with Tamil Nadu context")
                
                # Prefer results in Tamil Nadu
                for result in data:
                    lat = float(result['lat'])
                    lng = float(result['lon'])
                    display_name = result.get('display_name', '')
                    
                    # Tamil Nadu bounds (approximate)
                    if 8.0 <= lat <= 13.5 and 76.0 <= lng <= 80.5:
                        print(f"Found Tamil Nadu result: {lat}, {lng} - {display_name}")
                        return [lng, lat]
        
        # Strategy 3: Try without any location context
        print(f"Trying broad search for '{address}'")
        params = {
            'q': address,
            'format': 'json',
            'limit': 10,
            'countrycodes': 'in',
            'addressdetails': 1
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data:
                print(f"Found {len(data)} results in broad search")
                
                # Take the first Indian result
                for result in data:
                    lat = float(result['lat'])
                    lng = float(result['lon'])
                    display_name = result.get('display_name', '')
                    
                    # India bounds
                    if 6.0 <= lat <= 37.0 and 68.0 <= lng <= 97.0:
                        print(f"Found India result: {lat}, {lng} - {display_name}")
                        return [lng, lat]



        # Strategy 4: Try fuzzy matching for common Coimbatore locations
        coimbatore_locations = {
            'rs puram': [76.9558, 11.0168],
            'gandhipuram': [76.9558, 11.0168], 
            'peelamedu': [77.0082, 11.0296],
            'saibaba colony': [76.9365, 11.0183],
            'race course': [76.9647, 11.0015],
            'town hall': [76.9558, 11.0168],
            'railway station': [76.9647, 11.0015],
            'airport': [77.0434, 11.0297],
            'perur': [76.9142, 10.9764],
            'singanallur': [77.0082, 10.9296],
            'vadavalli': [76.9000, 11.0500],
            'coimbatore': [76.9558, 11.0168]
        }
        
        address_lower = address.lower().strip()
        for location, coords in coimbatore_locations.items():
            if location in address_lower or address_lower in location:
                print(f"Found fuzzy match for '{address}' -> {location}: {coords[1]}, {coords[0]}")
                return [coords[0], coords[1]]  # [lng, lat] format
        
        print(f"No geocoding results found for '{address}' after all strategies")
        return None
        
    except Exception as e:
        print(f"Geocoding error for '{address}': {e}")
        return None

def generate_route_coordinates(origin, dest):
    """Generate realistic road-following route coordinates for demo"""
    coords = []
    steps = 25  # More points for smoother, more realistic route
    
    # origin and dest are in [lng, lat] format
    start_lng, start_lat = origin
    end_lng, end_lat = dest
    
    # Calculate total distance for scaling variations
    total_distance = calculate_distance(start_lat, start_lng, end_lat, end_lng)
    
    # Create waypoints that simulate following roads
    waypoints = []
    
    # Add some intermediate waypoints to simulate road network
    if total_distance > 2:  # For longer routes, add more waypoints
        # Add waypoint roughly 1/3 of the way
        mid1_lat = start_lat + (end_lat - start_lat) * 0.33
        mid1_lng = start_lng + (end_lng - start_lng) * 0.33
        # Offset to simulate following roads instead of straight line
        mid1_lat += random.uniform(-0.003, 0.003)
        mid1_lng += random.uniform(-0.003, 0.003)
        waypoints.append([mid1_lng, mid1_lat])
        
        # Add waypoint roughly 2/3 of the way
        mid2_lat = start_lat + (end_lat - start_lat) * 0.67
        mid2_lng = start_lng + (end_lng - start_lng) * 0.67
        # Offset to simulate following roads
        mid2_lat += random.uniform(-0.003, 0.003)
        mid2_lng += random.uniform(-0.003, 0.003)
        waypoints.append([mid2_lng, mid2_lat])
    
    # Create route segments
    route_points = [origin] + waypoints + [dest]
    
    # Generate smooth path between all points
    for segment_idx in range(len(route_points) - 1):
        segment_start = route_points[segment_idx]
        segment_end = route_points[segment_idx + 1]
        
        segment_steps = steps // (len(route_points) - 1)
        
        for i in range(segment_steps + 1):
            if segment_idx > 0 and i == 0:  # Skip first point of non-first segments
                continue
                
            ratio = i / segment_steps
            
            # Interpolate between segment points
            lat = segment_start[1] + (segment_end[1] - segment_start[1]) * ratio
            lng = segment_start[0] + (segment_end[0] - segment_start[0]) * ratio
            
            # Add road-like variations
            if i > 0 and i < segment_steps:
                # Create curves that simulate following actual roads
                curve_intensity = 0.001 if total_distance < 5 else 0.002
                curve_factor = math.sin(ratio * math.pi * 4) * curve_intensity
                
                # Add some randomness to simulate road network
                lat += curve_factor + random.uniform(-curve_intensity * 0.5, curve_intensity * 0.5)
                lng += curve_factor * 0.8 + random.uniform(-curve_intensity * 0.5, curve_intensity * 0.5)
            
            coords.append([lng, lat])
    
    return coords

# Initialize OpenRouteService client (free tier)
try:
    ors_api_key = os.getenv('OPENROUTE_API_KEY')
    if ors_api_key:
        ors_client = openrouteservice.Client(key=ors_api_key)
    else:
        ors_client = None  # Use free tier without API key
except:
    ors_client = None

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Forms
class SignUpForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Sign Up')

class SignInForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

# Routes
@app.route('/')
def index():
    """Landing page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Sign up page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = SignUpForm()
    if form.validate_on_submit():
        # Check if user already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered. Please sign in instead.', 'error')
            return redirect(url_for('signin'))
        
        # Create new user
        user = User(
            name=form.name.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash('Account created successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('signup.html', form=form)

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    """Sign in page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = SignInForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Signed in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('signin.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Driver dashboard with OpenStreetMap"""
    return render_template('dashboard_osm.html', user=current_user)

@app.route('/api/hospitals')
@login_required
def get_hospitals():
    """Get nearby hospitals using Overpass API (OpenStreetMap)"""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    
    if not lat or not lng:
        return jsonify({'error': 'Latitude and longitude required'}), 400
    
    try:
        # Use Overpass API to find hospitals from OpenStreetMap
        radius = 10000  # 10km radius
        overpass_url = "http://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json][timeout:25];
        (
          node["amenity"="hospital"](around:{radius},{lat},{lng});
          way["amenity"="hospital"](around:{radius},{lat},{lng});
          relation["amenity"="hospital"](around:{radius},{lat},{lng});
        );
        out center meta;
        """
        
        response = requests.post(overpass_url, data=overpass_query, timeout=30)
        data = response.json()
        
        hospitals = []
        for element in data.get('elements', []):
            # Get coordinates
            if element['type'] == 'node':
                hospital_lat = element['lat']
                hospital_lng = element['lon']
            elif 'center' in element:
                hospital_lat = element['center']['lat']
                hospital_lng = element['center']['lon']
            else:
                continue
            
            # Get hospital info
            tags = element.get('tags', {})
            name = tags.get('name', 'Hospital')
            
            # Calculate distance
            distance = calculate_distance(lat, lng, hospital_lat, hospital_lng)
            
            hospitals.append({
                'name': name,
                'id': element['id'],
                'location': {'lat': hospital_lat, 'lng': hospital_lng},
                'distance_km': round(distance, 1),
                'address': tags.get('addr:full', tags.get('addr:street', 'Address not available')),
                'phone': tags.get('phone', ''),
                'website': tags.get('website', '')
            })
        
        # Sort by distance
        hospitals.sort(key=lambda x: x['distance_km'])
        
        return jsonify({'hospitals': hospitals[:20]})  # Return top 20 closest
    
    except Exception as e:
        # Return empty list if API fails - let user manually select locations
        print(f"Hospital search error: {e}")
        return jsonify({'hospitals': [], 'message': 'No hospitals found. You can click on the map to set a destination.'})

@app.route('/api/route')
@login_required
def get_route():
    """Get optimized route using OpenRouteService"""
    origin_str = request.args.get('origin')
    destination_str = request.args.get('destination')
    
    print(f"Route request - Origin: {origin_str}, Destination: {destination_str}")
    
    if not origin_str or not destination_str:
        return jsonify({'error': 'Origin and destination required'}), 400
    
    try:
        # Parse coordinates from strings
        origin_coords = parse_coordinates(origin_str)
        dest_coords = parse_coordinates(destination_str)
        
        print(f"Parsed coordinates - Origin: {origin_coords}, Destination: {dest_coords}")
        
        if not origin_coords or not dest_coords:
            return jsonify({'error': 'Could not parse coordinates. Please check your input.'}), 400
        
        # Use OpenRouteService for routing (free tier)
        routes = []
        
        # Try to get real routes from OpenRouteService (free public API)
        try:
            # Use OpenRouteService public API without authentication for basic routing
            ors_url = "https://api.openrouteservice.org/v2/directions/driving-car"
            
            # Prepare request data
            request_data = {
                "coordinates": [origin_coords, dest_coords],
                "format": "geojson",
                "instructions": True,
                "alternative_routes": {
                    "target_count": 3,
                    "weight_factor": 1.4
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'AmbulanceTracker/1.0'
            }
            
            # Try with API key if available
            if ors_api_key:
                headers['Authorization'] = ors_api_key
            
            response = requests.post(ors_url, json=request_data, headers=headers, timeout=15)
            
            if response.status_code == 200:
                ors_data = response.json()
                print(f"OpenRouteService returned {len(ors_data.get('features', []))} routes")
                
                for i, feature in enumerate(ors_data.get('features', [])):
                    props = feature['properties']
                    segments = props.get('segments', [{}])
                    if segments:
                        segment = segments[0]
                        
                        # Simulate traffic conditions
                        traffic_condition = simulate_traffic_conditions()
                        base_duration = segment.get('duration', 0)
                        base_distance = segment.get('distance', 0)
                        
                        if traffic_condition == 'light':
                            traffic_multiplier = 1.0
                            traffic_status = "Light Traffic"
                            traffic_color = "green"
                            delay_minutes = 0
                        elif traffic_condition == 'moderate':
                            traffic_multiplier = 1.3
                            traffic_status = "Moderate Traffic"
                            traffic_color = "orange"
                            delay_minutes = round((base_duration * 0.3) / 60)
                        else:
                            traffic_multiplier = 1.6
                            traffic_status = "Heavy Traffic"
                            traffic_color = "red"
                            delay_minutes = round((base_duration * 0.6) / 60)
                        
                        duration_with_traffic = base_duration * traffic_multiplier
                        
                        # Get turn-by-turn instructions
                        steps = []
                        if 'steps' in segment:
                            steps = [step.get('instruction', 'Continue') for step in segment['steps']]
                        
                        routes.append({
                            'route_index': i,
                            'distance': f"{round(base_distance / 1000, 1)} km",
                            'duration': f"{round(duration_with_traffic / 60)} mins",
                            'normal_duration': f"{round(base_duration / 60)} mins",
                            'traffic_delay_minutes': delay_minutes,
                            'traffic_status': traffic_status,
                            'traffic_color': traffic_color,
                            'coordinates': feature['geometry']['coordinates'],
                            'steps': steps
                        })
            else:
                print(f"OpenRouteService API error: {response.status_code} - {response.text}")
            
        except Exception as ors_error:
            print(f"OpenRouteService error: {ors_error}")
        
        # Try GraphHopper as backup (also free)
        if not routes:
            try:
                print("Trying GraphHopper as backup routing service")
                graphhopper_url = "https://graphhopper.com/api/1/route"
                
                params = {
                    'point': [f"{origin_coords[1]},{origin_coords[0]}", f"{dest_coords[1]},{dest_coords[0]}"],
                    'vehicle': 'car',
                    'locale': 'en',
                    'instructions': 'true',
                    'calc_points': 'true',
                    'debug': 'false',
                    'elevation': 'false',
                    'points_encoded': 'false'
                }
                
                headers = {'User-Agent': 'AmbulanceTracker/1.0'}
                
                response = requests.get(graphhopper_url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    gh_data = response.json()
                    print(f"GraphHopper returned data: {len(gh_data.get('paths', []))} paths")
                    
                    for i, path in enumerate(gh_data.get('paths', [])):
                        # Simulate traffic conditions
                        traffic_condition = simulate_traffic_conditions()
                        base_duration = path.get('time', 0) / 1000  # Convert from ms to seconds
                        base_distance = path.get('distance', 0)
                        
                        if traffic_condition == 'light':
                            traffic_multiplier = 1.0
                            traffic_status = "Light Traffic"
                            traffic_color = "green"
                            delay_minutes = 0
                        elif traffic_condition == 'moderate':
                            traffic_multiplier = 1.3
                            traffic_status = "Moderate Traffic"
                            traffic_color = "orange"
                            delay_minutes = round((base_duration * 0.3) / 60)
                        else:
                            traffic_multiplier = 1.6
                            traffic_status = "Heavy Traffic"
                            traffic_color = "red"
                            delay_minutes = round((base_duration * 0.6) / 60)
                        
                        duration_with_traffic = base_duration * traffic_multiplier
                        
                        # Get coordinates from points
                        coordinates = []
                        if 'points' in path and 'coordinates' in path['points']:
                            coordinates = path['points']['coordinates']
                        
                        # Get turn-by-turn instructions
                        steps = []
                        if 'instructions' in path:
                            steps = [instr.get('text', 'Continue') for instr in path['instructions']]
                        
                        routes.append({
                            'route_index': i,
                            'distance': f"{round(base_distance / 1000, 1)} km",
                            'duration': f"{round(duration_with_traffic / 60)} mins",
                            'normal_duration': f"{round(base_duration / 60)} mins",
                            'traffic_delay_minutes': delay_minutes,
                            'traffic_status': traffic_status,
                            'traffic_color': traffic_color,
                            'coordinates': coordinates,
                            'steps': steps
                        })
                else:
                    print(f"GraphHopper API error: {response.status_code}")
                    
            except Exception as gh_error:
                print(f"GraphHopper error: {gh_error}")
        
        # Try OSRM as final backup (completely free, no API key needed)
        if not routes:
            try:
                print("Trying OSRM as final backup routing service")
                osrm_url = f"http://router.project-osrm.org/route/v1/driving/{origin_coords[0]},{origin_coords[1]};{dest_coords[0]},{dest_coords[1]}"
                
                params = {
                    'overview': 'full',
                    'geometries': 'geojson',
                    'steps': 'true',
                    'alternatives': 'true'
                }
                
                headers = {'User-Agent': 'AmbulanceTracker/1.0'}
                
                response = requests.get(osrm_url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    osrm_data = response.json()
                    print(f"OSRM returned {len(osrm_data.get('routes', []))} routes")
                    
                    for i, route in enumerate(osrm_data.get('routes', [])):
                        # Simulate traffic conditions
                        traffic_condition = simulate_traffic_conditions()
                        base_duration = route.get('duration', 0)  # Already in seconds
                        base_distance = route.get('distance', 0)  # Already in meters
                        
                        if traffic_condition == 'light':
                            traffic_multiplier = 1.0
                            traffic_status = "Light Traffic"
                            traffic_color = "green"
                            delay_minutes = 0
                        elif traffic_condition == 'moderate':
                            traffic_multiplier = 1.3
                            traffic_status = "Moderate Traffic"
                            traffic_color = "orange"
                            delay_minutes = round((base_duration * 0.3) / 60)
                        else:
                            traffic_multiplier = 1.6
                            traffic_status = "Heavy Traffic"
                            traffic_color = "red"
                            delay_minutes = round((base_duration * 0.6) / 60)
                        
                        duration_with_traffic = base_duration * traffic_multiplier
                        
                        # Get coordinates from geometry
                        coordinates = []
                        if 'geometry' in route and 'coordinates' in route['geometry']:
                            coordinates = route['geometry']['coordinates']
                        
                        # Get turn-by-turn instructions
                        steps = []
                        if 'legs' in route:
                            for leg in route['legs']:
                                if 'steps' in leg:
                                    for step in leg['steps']:
                                        if 'maneuver' in step and 'instruction' in step['maneuver']:
                                            steps.append(step['maneuver']['instruction'])
                        
                        routes.append({
                            'route_index': i,
                            'distance': f"{round(base_distance / 1000, 1)} km",
                            'duration': f"{round(duration_with_traffic / 60)} mins",
                            'normal_duration': f"{round(base_duration / 60)} mins",
                            'traffic_delay_minutes': delay_minutes,
                            'traffic_status': traffic_status,
                            'traffic_color': traffic_color,
                            'coordinates': coordinates,
                            'steps': steps if steps else ['Head towards destination', 'Continue on route', 'Arrive at destination']
                        })
                    
                    # If we only got 1 route, generate 2 more alternative routes
                    if len(routes) == 1:
                        print("Only 1 route found, generating alternatives using nearby waypoints...")
                        alternative_routes = generate_alternative_routes(origin_coords, dest_coords, routes[0])
                        routes.extend(alternative_routes)
                        
                else:
                    print(f"OSRM API error: {response.status_code}")
                    
            except Exception as osrm_error:
                print(f"OSRM error: {osrm_error}")
        
        # Fallback to simulated routes if all routing services fail
        if not routes:
            print("Using fallback route generation")
            # Calculate distance between points (origin_coords and dest_coords are [lng, lat])
            distance = calculate_distance(origin_coords[1], origin_coords[0], dest_coords[1], dest_coords[0])
            
            # Generate 3 alternative routes with different characteristics
            for i in range(3):
                traffic_condition = simulate_traffic_conditions()
                base_time = max(5, distance * 3 + random.randint(-3, 8))  # More realistic time estimate
                
                if traffic_condition == 'light':
                    duration = base_time
                    traffic_status = "Light Traffic"
                    traffic_color = "green"
                    delay_minutes = 0
                elif traffic_condition == 'moderate':
                    duration = base_time * 1.3
                    traffic_status = "Moderate Traffic"
                    traffic_color = "orange"
                    delay_minutes = round(base_time * 0.3)
                else:
                    duration = base_time * 1.6
                    traffic_status = "Heavy Traffic"
                    traffic_color = "red"
                    delay_minutes = round(base_time * 0.6)
                
                # Add some variation to distance for different routes
                route_distance = distance + random.uniform(-0.3, 0.8)
                if route_distance < 0.1:
                    route_distance = 0.1
                
                routes.append({
                    'route_index': i,
                    'distance': f"{round(route_distance, 1)} km",
                    'duration': f"{round(duration)} mins",
                    'normal_duration': f"{round(base_time)} mins",
                    'traffic_delay_minutes': delay_minutes,
                    'traffic_status': traffic_status,
                    'traffic_color': traffic_color,
                    'coordinates': generate_route_coordinates(origin_coords, dest_coords),
                    'steps': [
                        f"Head towards destination from current location",
                        f"Continue for {round(route_distance * 0.6, 1)} km",
                        f"Approach destination area",
                        f"Arrive at destination ({round(route_distance, 1)} km total)"
                    ]
                })
        
        # Sort routes by duration (fastest first)
        routes.sort(key=lambda x: float(x['duration'].split()[0]))
        
        return jsonify({'routes': routes})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/geocode')
@login_required
def geocode():
    """Geocode address to coordinates"""
    address = request.args.get('address')
    if not address:
        return jsonify({'error': 'Address required'}), 400
    
    coords = geocode_address(address)
    if coords:
        return jsonify({
            'lat': coords[1], 
            'lng': coords[0],
            'address': address
        })
    else:
        return jsonify({'error': 'Address not found'}), 404

@app.route('/api/traffic')
@login_required
def get_traffic_data():
    """Get real-time traffic data for map area"""
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    zoom = request.args.get('zoom', type=int, default=12)
    
    if not lat or not lng:
        return jsonify({'error': 'Latitude and longitude required'}), 400
    
    try:
        # Calculate bounding box based on zoom level
        bbox_size = 0.1 / (zoom / 10)  # Adjust based on zoom
        bbox = {
            'north': lat + bbox_size,
            'south': lat - bbox_size,
            'east': lng + bbox_size,
            'west': lng - bbox_size
        }
        
        # Get traffic incidents and road conditions
        print(f"Getting traffic data for bbox: {bbox}")
        traffic_data = get_traffic_incidents(bbox)
        road_conditions = get_road_conditions(bbox)
        
        print(f"Returning {len(traffic_data)} incidents and {len(road_conditions)} road conditions")
        
        return jsonify({
            'traffic_incidents': traffic_data,
            'road_conditions': road_conditions,
            'bbox': bbox,
            'timestamp': int(time.time())
        })
    
    except Exception as e:
        print(f"Traffic data error: {e}")
        return jsonify({'error': 'Could not fetch traffic data'}), 500

def get_traffic_incidents(bbox):
    """Get real traffic incidents from multiple sources"""
    incidents = []
    
    try:
        # Try completely free sources first
        free_incidents = get_free_traffic_incidents(bbox)
        incidents.extend(free_incidents)
        
        # Always try OpenStreetMap traffic data (don't skip if we have some incidents)
        osm_incidents = get_osm_traffic_incidents(bbox)
        incidents.extend(osm_incidents)
        
        # Try traffic data from government sources
        gov_incidents = get_government_traffic_data(bbox)
        incidents.extend(gov_incidents)
        
        # If we still don't have enough incidents, try paid APIs
        if len(incidents) < 3:
            here_incidents = get_here_traffic_incidents(bbox)
            incidents.extend(here_incidents)
        
        if len(incidents) < 3:
            tomtom_incidents = get_tomtom_traffic_incidents(bbox)
            incidents.extend(tomtom_incidents)
        
        # If still no incidents, generate some simulated ones for demo
        if len(incidents) == 0:
            print("No real incidents found, generating simulated traffic incidents...")
            simulated_incidents = simulate_traffic_incidents(bbox)
            incidents.extend(simulated_incidents)
            
        print(f"Found {len(incidents)} traffic incidents from various sources")
        
    except Exception as e:
        print(f"Traffic incidents error: {e}")
    
    return incidents

def get_road_conditions(bbox):
    """Get real road conditions and congestion levels"""
    conditions = []
    
    try:
        # Always try free sources first
        free_conditions = get_free_traffic_flow_data(bbox)
        conditions.extend(free_conditions)
        
        # If we don't have enough road conditions, try paid APIs
        if len(conditions) < 10:
            here_conditions = get_here_traffic_flow(bbox)
            conditions.extend(here_conditions)
        
        if len(conditions) < 10:
            tomtom_conditions = get_tomtom_traffic_flow(bbox)
            conditions.extend(tomtom_conditions)
            
        if len(conditions) < 10:
            mapbox_conditions = get_mapbox_traffic_flow(bbox)
            conditions.extend(mapbox_conditions)
        
        # If still no conditions, generate simulated ones
        if len(conditions) == 0:
            print("No real road conditions found, generating simulated traffic flow...")
            simulated_conditions = simulate_road_conditions(bbox)
            conditions.extend(simulated_conditions)
        
        # Ensure we always have some traffic data for route analysis
        if len(conditions) < 5:
            print(f"Only {len(conditions)} conditions found, adding more simulated data...")
            additional_conditions = simulate_road_conditions(bbox)
            conditions.extend(additional_conditions[:10])  # Add up to 10 more
            
        print(f"Found {len(conditions)} traffic conditions from various sources")
        
    except Exception as e:
        print(f"Road conditions error: {e}")
    
    return conditions

# Completely Free Traffic Data Sources (No API Keys Required)

def get_free_traffic_incidents(bbox):
    """Get traffic incidents from completely free sources"""
    incidents = []
    
    try:
        # Try Waze traffic data (public feeds)
        waze_incidents = get_waze_traffic_data(bbox)
        incidents.extend(waze_incidents)
        
        # Try traffic data from social media and news feeds
        social_incidents = get_social_traffic_data(bbox)
        incidents.extend(social_incidents)
        
        print(f"Found {len(incidents)} incidents from free sources")
        
    except Exception as e:
        print(f"Free traffic sources error: {e}")
    
    return incidents

def get_waze_traffic_data(bbox):
    """Get traffic data from Waze public feeds"""
    incidents = []
    
    try:
        # Waze has some public traffic data feeds
        # Note: This is a simplified implementation
        # In practice, you'd need to find current Waze public APIs or feeds
        
        # For now, we'll try to get data from traffic aggregators
        print("Attempting to get Waze traffic data...")
        
        # This would need actual Waze API endpoints or public feeds
        # Waze doesn't have a completely open API, but some data is available
        
    except Exception as e:
        print(f"Waze traffic data error: {e}")
    
    return incidents

def get_social_traffic_data(bbox):
    """Get traffic incidents from social media and news sources"""
    incidents = []
    
    try:
        # This could aggregate traffic reports from:
        # - Twitter traffic accounts
        # - Local news traffic reports
        # - Government traffic feeds
        # - Radio station traffic reports
        
        print("Checking social media and news for traffic reports...")
        
        # Example: Check for traffic-related tweets in the area
        # This would require Twitter API or web scraping
        
    except Exception as e:
        print(f"Social traffic data error: {e}")
    
    return incidents

def get_osm_traffic_incidents(bbox):
    """Get traffic data from OpenStreetMap and related sources"""
    incidents = []
    
    try:
        # OpenStreetMap has some traffic-related data
        # Check for construction zones, road closures, etc.
        
        overpass_url = "http://overpass-api.de/api/interpreter"
        
        # Query for construction zones and road works
        overpass_query = f"""
        [out:json][timeout:25];
        (
          way["highway"]["construction"](bbox:{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
          way["highway"]["construction:highway"](bbox:{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
          node["highway"="construction"](bbox:{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
          way["barrier"="temporary"](bbox:{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
        );
        out center meta;
        """
        
        response = requests.post(overpass_url, data=overpass_query, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            for element in data.get('elements', []):
                # Get coordinates
                if element['type'] == 'node':
                    lat = element['lat']
                    lng = element['lon']
                elif 'center' in element:
                    lat = element['center']['lat']
                    lng = element['center']['lon']
                else:
                    continue
                
                # Determine incident type
                tags = element.get('tags', {})
                
                if 'construction' in tags:
                    incident_type = 'construction'
                    description = f"Construction work: {tags.get('construction', 'Road work in progress')}"
                    severity = 'medium'
                elif tags.get('barrier') == 'temporary':
                    incident_type = 'road_closure'
                    description = "Temporary road closure or barrier"
                    severity = 'high'
                else:
                    incident_type='construction'
                    description="Road construction or maintenance"
                    incident_type = 'construction'
                    description = "Road construction or maintenance"
                    severity = 'medium'
                
                incidents.append({
                    'id': f"osm_{element.get('id', '')}",
                    'type': incident_type,
                    'severity': severity,
                    'icon': get_incident_icon(incident_type),
                    'location': {'lat': lat, 'lng': lng},
                    'description': description,
                    'delay': estimate_delay_from_severity(severity),
                    'timestamp': int(time.time()),
                    'active': True,
                    'source': 'OpenStreetMap'
                })
        
        print(f"Found {len(incidents)} incidents from OpenStreetMap")
        
    except Exception as e:
        print(f"OSM traffic data error: {e}")
    
    return incidents

def get_government_traffic_data(bbox):
    """Get traffic data from government and public sources"""
    incidents = []
    
    try:
        # For India (since you're using Coimbatore), try government traffic sources
        
        # Try Indian government traffic APIs (if available)
        # Many cities have public traffic data feeds
        
        # Example: Try to get data from local traffic management systems
        print("Checking government traffic data sources...")
        
        # This would be specific to your region
        # For Tamil Nadu/Coimbatore, you might check:
        # - Tamil Nadu Police traffic updates
        # - Local municipal corporation traffic data
        # - Highway authority incident reports
        
        # Example implementation for Indian government data
        incidents.extend(get_indian_traffic_data(bbox))
        
    except Exception as e:
        print(f"Government traffic data error: {e}")
    
    return incidents

def get_indian_traffic_data(bbox):
    """Get traffic data from Indian government sources"""
    incidents = []
    
    try:
        # Try to get data from various Indian government sources
        
        # 1. Try National Highway Authority of India (NHAI) if they have public APIs
        # 2. Try state government traffic departments
        # 3. Try local police traffic updates
        
        # For demonstration, we'll create realistic incidents based on common patterns
        # In a real implementation, you'd connect to actual government APIs
        
        print("Checking Indian government traffic sources...")
        
        # This is where you'd implement actual government API calls
        # For now, we'll return empty to avoid simulation
        
    except Exception as e:
        print(f"Indian traffic data error: {e}")
    
    return incidents

def get_free_traffic_flow_data(bbox):
    """Get traffic flow data from free sources"""
    conditions = []
    
    try:
        # Try to get traffic flow from completely free sources
        
        # 1. OpenStreetMap-based traffic estimation
        osm_flow = get_osm_traffic_flow(bbox)
        conditions.extend(osm_flow)
        
        # 2. Public transportation delay data (can indicate traffic)
        transit_data = get_transit_delay_indicators(bbox)
        conditions.extend(transit_data)
        
        print(f"Found {len(conditions)} traffic flow conditions from free sources")
        
    except Exception as e:
        print(f"Free traffic flow error: {e}")
    
    return conditions

def get_osm_traffic_flow(bbox):
    """Estimate traffic flow using OpenStreetMap road data"""
    conditions = []
    
    try:
        # Get road network from OpenStreetMap
        overpass_url = "http://overpass-api.de/api/interpreter"
        
        # Query for major roads
        overpass_query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"^(motorway|trunk|primary|secondary)$"](bbox:{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
        );
        out geom meta;
        """
        
        response = requests.post(overpass_url, data=overpass_query, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            for element in data.get('elements', []):
                if element['type'] == 'way' and 'geometry' in element:
                    # Convert geometry to coordinate pairs
                    coordinates = []
                    for point in element['geometry']:
                        coordinates.append([point['lon'], point['lat']])
                    
                    if len(coordinates) >= 2:
                        # Estimate traffic based on road type and time
                        highway_type = element.get('tags', {}).get('highway', '')
                        
                        # Estimate congestion based on road importance and current time
                        current_hour = time.localtime().tm_hour
                        
                        # Rush hour logic
                        if 7 <= current_hour <= 9 or 17 <= current_hour <= 19:
                            if highway_type in ['motorway', 'trunk']:
                                congestion = 'heavy'
                                color = '#ef4444'
                                speed_factor = 0.4
                            elif highway_type in ['primary']:
                                congestion = 'moderate'
                                color = '#f59e0b'
                                speed_factor = 0.6
                            else:
                                congestion = 'light'
                                color = '#22c55e'
                                speed_factor = 0.8
                        else:
                            # Normal hours - less traffic
                            if highway_type in ['motorway', 'trunk']:
                                congestion = 'moderate'
                                color = '#f59e0b'
                                speed_factor = 0.7
                            else:
                                congestion = 'light'
                                color = '#22c55e'
                                speed_factor = 0.9
                        
                        conditions.append({
                            'id': f"osm_flow_{element.get('id', '')}",
                            'coordinates': coordinates,
                            'congestion': congestion,
                            'color': color,
                            'speed_factor': speed_factor,
                            'road_type': highway_type,
                            'timestamp': int(time.time()),
                            'source': 'OpenStreetMap'
                        })
        
        print(f"Generated {len(conditions)} traffic flow estimates from OSM roads")
        
    except Exception as e:
        print(f"OSM traffic flow error: {e}")
    
    return conditions

def get_transit_delay_indicators(bbox):
    """Use public transit delays as traffic indicators"""
    conditions = []
    
    try:
        # Public transit delays often correlate with traffic congestion
        # If buses are delayed, roads are likely congested
        
        # This would require access to public transit APIs
        # Many cities provide real-time transit data for free
        
        print("Checking public transit delays as traffic indicators...")
        
        # For Indian cities, you might check:
        # - Local bus service APIs
        # - Metro/railway delay information
        # - Government transport department data
        
    except Exception as e:
        print(f"Transit delay indicator error: {e}")
    
    return conditions

# Real Traffic API Implementations

def get_here_traffic_incidents(bbox):
    """Get real traffic incidents from HERE API"""
    incidents = []
    
    try:
        # HERE Traffic API (free tier: 1000 requests/month)
        here_api_key = os.getenv('HERE_API_KEY')  # You need to get this from developer.here.com
        
        if not here_api_key:
            print("HERE API key not found, trying without key...")
            return []
        
        url = "https://traffic.ls.hereapi.com/traffic/6.3/incidents.json"
        params = {
            'bbox': f"{bbox['north']},{bbox['west']};{bbox['south']},{bbox['east']}",
            'apikey': here_api_key,
            'criticality': 'major,minor'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            for item in data.get('TRAFFIC_ITEMS', {}).get('TRAFFIC_ITEM', []):
                location = item.get('LOCATION', {})
                if 'GEOLOC' in location:
                    geoloc = location['GEOLOC']
                    lat = float(geoloc.get('ORIGIN', {}).get('LATITUDE', 0))
                    lng = float(geoloc.get('ORIGIN', {}).get('LONGITUDE', 0))
                    
                    incident_type = item.get('TRAFFIC_ITEM_TYPE_DESC', 'incident').lower()
                    severity = 'high' if item.get('CRITICALITY', 0) > 2 else 'medium'
                    
                    incidents.append({
                        'id': f"here_{item.get('TRAFFIC_ITEM_ID', '')}",
                        'type': incident_type,
                        'severity': severity,
                        'icon': get_incident_icon(incident_type),
                        'location': {'lat': lat, 'lng': lng},
                        'description': item.get('TRAFFIC_ITEM_DESCRIPTION', [{}])[0].get('content', 'Traffic incident'),
                        'delay': estimate_delay_from_severity(severity),
                        'timestamp': int(time.time()),
                        'active': True,
                        'source': 'HERE'
                    })
        
    except Exception as e:
        print(f"HERE Traffic API error: {e}")
    
    return incidents

def get_tomtom_traffic_incidents(bbox):
    """Get real traffic incidents from TomTom API"""
    incidents = []
    
    try:
        # TomTom Traffic API (free tier: 2500 requests/day)
        tomtom_api_key = os.getenv('TOMTOM_API_KEY')  # Get from developer.tomtom.com
        
        if not tomtom_api_key:
            print("TomTom API key not found")
            return []
        
        url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
        params = {
            'key': tomtom_api_key,
            'bbox': f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
            'fields': '{incidents{type,geometry{type,coordinates},properties{iconCategory,magnitudeOfDelay,events{description,code,iconCategory}}}}'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            for incident in data.get('incidents', []):
                props = incident.get('properties', {})
                coords = incident.get('geometry', {}).get('coordinates', [])
                
                if coords:
                    lng, lat = coords[0], coords[1]
                    
                    icon_category = props.get('iconCategory', 0)
                    incident_type = get_tomtom_incident_type(icon_category)
                    severity = get_severity_from_delay(props.get('magnitudeOfDelay', 0))
                    
                    description = 'Traffic incident'
                    events = props.get('events', [])
                    if events:
                        description = events[0].get('description', description)
                    
                    incidents.append({
                        'id': f"tomtom_{incident.get('id', '')}",
                        'type': incident_type,
                        'severity': severity,
                        'icon': get_incident_icon(incident_type),
                        'location': {'lat': lat, 'lng': lng},
                        'description': description,
                        'delay': estimate_delay_from_severity(severity),
                        'timestamp': int(time.time()),
                        'active': True,
                        'source': 'TomTom'
                    })
        
    except Exception as e:
        print(f"TomTom Traffic API error: {e}")
    
    return incidents

def get_mapbox_traffic_incidents(bbox):
    """Get traffic incidents from MapBox API"""
    incidents = []
    
    try:
        # MapBox doesn't have a direct incidents API, but we can use their traffic tiles
        # For now, return empty - you'd need to implement tile parsing
        print("MapBox incidents API not implemented yet")
        
    except Exception as e:
        print(f"MapBox Traffic API error: {e}")
    
    return incidents

def get_here_traffic_flow(bbox):
    """Get real traffic flow data from HERE API"""
    conditions = []
    
    try:
        here_api_key = os.getenv('HERE_API_KEY')
        
        if not here_api_key:
            return []
        
        url = "https://traffic.ls.hereapi.com/traffic/6.3/flow.json"
        params = {
            'bbox': f"{bbox['north']},{bbox['west']};{bbox['south']},{bbox['east']}",
            'apikey': here_api_key,
            'responseattributes': 'sh,fc'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            for item in data.get('RWS', [{}])[0].get('RW', []):
                for fis in item.get('FIS', []):
                    fi = fis.get('FI', [])
                    for flow_item in fi:
                        # Get shape points for the road segment
                        shp = flow_item.get('SHP', [])
                        if len(shp) >= 2:
                            coordinates = []
                            for point in shp:
                                lat, lng = map(float, point.split(','))
                                coordinates.append([lng, lat])
                            
                            # Get traffic flow data
                            cf = flow_item.get('CF', [{}])[0]
                            speed = cf.get('SP', 0)  # Current speed
                            free_flow = cf.get('FF', speed)  # Free flow speed
                            
                            # Calculate congestion level
                            if speed >= free_flow * 0.8:
                                congestion = 'light'
                                color = '#22c55e'
                            elif speed >= free_flow * 0.5:
                                congestion = 'moderate'
                                color = '#f59e0b'
                            else:
                                congestion = 'heavy'
                                color = '#ef4444'
                            
                            conditions.append({
                                'id': f"here_flow_{int(time.time())}_{len(conditions)}",
                                'coordinates': coordinates,
                                'congestion': congestion,
                                'color': color,
                                'speed_factor': speed / free_flow if free_flow > 0 else 0.5,
                                'current_speed': speed,
                                'free_flow_speed': free_flow,
                                'timestamp': int(time.time()),
                                'source': 'HERE'
                            })
        
    except Exception as e:
        print(f"HERE Traffic Flow API error: {e}")
    
    return conditions

def get_tomtom_traffic_flow(bbox):
    """Get real traffic flow data from TomTom API"""
    conditions = []
    
    try:
        tomtom_api_key = os.getenv('TOMTOM_API_KEY')
        
        if not tomtom_api_key:
            return []
        
        # TomTom Traffic Flow API
        url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        
        # Sample multiple points in the bounding box
        lat_step = (bbox['north'] - bbox['south']) / 5
        lng_step = (bbox['east'] - bbox['west']) / 5
        
        for i in range(5):
            for j in range(5):
                lat = bbox['south'] + i * lat_step
                lng = bbox['west'] + j * lng_step
                
                params = {
                    'key': tomtom_api_key,
                    'point': f"{lat},{lng}",
                    'unit': 'KMPH'
                }
                
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    flow_data = data.get('flowSegmentData', {})
                    
                    current_speed = flow_data.get('currentSpeed', 0)
                    free_flow_speed = flow_data.get('freeFlowSpeed', current_speed)
                    
                    # Calculate congestion
                    if current_speed >= free_flow_speed * 0.8:
                        congestion = 'light'
                        color = '#22c55e'
                    elif current_speed >= free_flow_speed * 0.5:
                        congestion = 'moderate'
                        color = '#f59e0b'
                    else:
                        congestion = 'heavy'
                        color = '#ef4444'
                    
                    # Create a small road segment around the point
                    coordinates = [
                        [lng - 0.002, lat - 0.002],
                        [lng + 0.002, lat + 0.002]
                    ]
                    
                    conditions.append({
                        'id': f"tomtom_flow_{int(time.time())}_{i}_{j}",
                        'coordinates': coordinates,
                        'congestion': congestion,
                        'color': color,
                        'speed_factor': current_speed / free_flow_speed if free_flow_speed > 0 else 0.5,
                        'current_speed': current_speed,
                        'free_flow_speed': free_flow_speed,
                        'timestamp': int(time.time()),
                        'source': 'TomTom'
                    })
        
    except Exception as e:
        print(f"TomTom Traffic Flow API error: {e}")
    
    return conditions

def get_mapbox_traffic_flow(bbox):
    """Get traffic flow data from MapBox"""
    conditions = []
    
    try:
        # MapBox traffic would require parsing their vector tiles
        # This is more complex and requires additional libraries
        print("MapBox traffic flow not implemented yet")
        
    except Exception as e:
        print(f"MapBox Traffic Flow API error: {e}")
    
    return conditions

# Helper functions for traffic data processing

def get_incident_icon(incident_type):
    """Get appropriate icon for incident type"""
    icons = {
        'accident': '🚗💥',
        'construction': '🚧',
        'congestion': '🚦',
        'road_closure': '🚫',
        'weather': '🌧️',
        'incident': '⚠️'
    }
    
    for key in icons:
        if key in incident_type.lower():
            return icons[key]
    
    return '⚠️'

def get_tomtom_incident_type(icon_category):
    """Convert TomTom icon category to incident type"""
    mapping = {
        0: 'incident',
        1: 'accident',
        2: 'fog',
        3: 'dangerous_conditions',
        4: 'rain',
        5: 'ice',
        6: 'jam',
        7: 'lane_closed',
        8: 'road_closed',
        9: 'road_works',
        10: 'wind',
        14: 'broken_down_vehicle'
    }
    
    return mapping.get(icon_category, 'incident')

def get_severity_from_delay(delay_magnitude):
    """Convert delay magnitude to severity"""
    if delay_magnitude >= 4:
        return 'high'
    elif delay_magnitude >= 2:
        return 'medium'
    else:
        return 'low'

def estimate_delay_from_severity(severity):
    """Estimate delay time from severity"""
    delays = {
        'high': '20-45 min',
        'medium': '10-20 min',
        'low': '5-10 min'
    }
    return delays.get(severity, '5-10 min')

def simulate_traffic_incidents(bbox):
    """Simulate realistic traffic incidents for demo"""
    import time
    from datetime import datetime
    
    incidents = []
    current_hour = datetime.now().hour
    
    # More incidents during rush hours (7-9 AM, 5-7 PM)
    if 7 <= current_hour <= 9 or 17 <= current_hour <= 19:
        incident_count = random.randint(3, 8)
    else:
        incident_count = random.randint(0, 3)
    
    incident_types = [
        {'type': 'accident', 'severity': 'high', 'icon': '🚗💥', 'delay': '15-30 min'},
        {'type': 'construction', 'severity': 'medium', 'icon': '🚧', 'delay': '5-15 min'},
        {'type': 'congestion', 'severity': 'medium', 'icon': '🚦', 'delay': '10-20 min'},
        {'type': 'road_closure', 'severity': 'high', 'icon': '🚫', 'delay': '30+ min'},
        {'type': 'weather', 'severity': 'low', 'icon': '🌧️', 'delay': '5-10 min'}
    ]
    
    for i in range(incident_count):
        incident_type = random.choice(incident_types)
        
        # Random location within bounding box
        lat = random.uniform(bbox['south'], bbox['north'])
        lng = random.uniform(bbox['west'], bbox['east'])
        
        incidents.append({
            'id': f"incident_{i}_{int(time.time())}",
            'type': incident_type['type'],
            'severity': incident_type['severity'],
            'icon': incident_type['icon'],
            'location': {'lat': lat, 'lng': lng},
            'description': f"{incident_type['type'].replace('_', ' ').title()} causing delays",
            'delay': incident_type['delay'],
            'timestamp': int(time.time()),
            'active': True
        })
    
    return incidents

def simulate_road_conditions(bbox):
    """Simulate road congestion levels"""
    import time
    from datetime import datetime
    
    conditions = []
    current_hour = datetime.now().hour
    
    # Generate road segments with different congestion levels
    segments_count = random.randint(10, 25)
    
    for i in range(segments_count):
        # Create road segment coordinates
        start_lat = random.uniform(bbox['south'], bbox['north'])
        start_lng = random.uniform(bbox['west'], bbox['east'])
        
        # Create a short road segment
        end_lat = start_lat + random.uniform(-0.005, 0.005)
        end_lng = start_lng + random.uniform(-0.005, 0.005)
        
        # Determine congestion level based on time
        if 7 <= current_hour <= 9 or 17 <= current_hour <= 19:
            # Rush hour - more congestion
            congestion_levels = ['heavy', 'moderate', 'light']
            weights = [0.4, 0.4, 0.2]
        elif 22 <= current_hour or current_hour <= 6:
            # Night time - less congestion
            congestion_levels = ['light', 'moderate', 'heavy']
            weights = [0.7, 0.2, 0.1]
        else:
            # Normal hours
            congestion_levels = ['light', 'moderate', 'heavy']
            weights = [0.5, 0.3, 0.2]
        
        congestion = random.choices(congestion_levels, weights=weights)[0]
        
        # Set colors based on congestion
        if congestion == 'light':
            color = '#22c55e'  # Green
            speed_factor = 1.0
        elif congestion == 'moderate':
            color = '#f59e0b'  # Orange
            speed_factor = 0.7
        else:
            color = '#ef4444'  # Red
            speed_factor = 0.4

         conditions.append({
             soundaryamariappan data analyst lpa of 10

            'id': f"road_{i}_{int(time.time())}",
            'coordinates': [[start_lng, start_lat], [end_lng, end_lat]],
            'congestion': congestion,
            'color': color,
            'speed_factor': speed_factor,
            'timestamp': int(time.time())
        })
    
    return conditions

if __name__ == '__main__':
    with app.app_context():iu
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
    Binary search tree
    {\
        if(root==null)
    return;
    System.out.print(root.data+" ")
    }