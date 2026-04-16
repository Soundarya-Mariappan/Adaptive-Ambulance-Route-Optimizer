# Ambulance Tracker

A smart emergency vehicle routing system with real-time traffic analysis and Google Maps integration. Helps ambulance drivers find the fastest routes to hospitals with live traffic updates.

## Features

- **Smart Routing**: AI-powered route optimization with real-time traffic data
- **Hospital Network**: Comprehensive database of nearby hospitals
- **Traffic Analysis**: Color-coded traffic alerts (Green/Orange/Red)
- **User Authentication**: Secure sign-up and sign-in system
- **Live Updates**: Real-time route updates and alternative suggestions
- **Mobile Responsive**: Works on all devices and screen sizes

## Project Structure

```
ambulancetracker/
├── app.py              # Main Flask application with Google Maps integration
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (API keys)
├── templates/          # HTML templates
│   ├── base.html      # Base template with emergency styling
│   ├── landing.html   # Landing page
│   ├── signup.html    # User registration
│   ├── signin.html    # User login
│   └── dashboard.html # Main dashboard with Google Maps
└── README.md          # This file
```

## Installation

1. **Clone or navigate to the project directory**
   ```bash
   cd ambulancetracker
   ```

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables**
   - The `.env` file is already created with your Google Maps API key
   - Make sure your API key has the following APIs enabled:
     - Maps JavaScript API
     - Places API
     - Directions API
     - Geocoding API

## Running the Application

1. **Start the Flask development server**
   ```bash
   python app.py
   ```

2. **Open your browser and navigate to**
   ```
   http://localhost:5000
   ```

The application will automatically create the SQLite database on first run.

## How to Use

### For Ambulance Drivers:

1. **Sign Up**: Create an account with your name, email, and password
2. **Sign In**: Access your dashboard
3. **Set Location**: Enter your current location or use GPS
4. **Select Hospital**: Choose from nearby hospitals or click map markers
5. **Get Route**: Click "Find Best Route" to see traffic analysis
6. **Follow Guidance**: Use the recommended route with least traffic

### Traffic Analysis Features:

- **🟢 Green**: Light traffic, minimal delays
- **🟠 Orange**: Moderate traffic, some delays expected
- **🔴 Red**: Heavy traffic, significant delays

## Available Routes

### Web Pages
- `/` - Landing page
- `/signup` - User registration
- `/signin` - User login
- `/dashboard` - Main driver dashboard with maps
- `/logout` - User logout

### API Endpoints
- `/api/hospitals` - Get nearby hospitals based on location
- `/api/route` - Get optimized routes with traffic analysis
- `/api/traffic-analysis` - Detailed traffic analysis for routes

## API Examples

### Get Nearby Hospitals
```bash
curl "http://localhost:5000/api/hospitals?lat=28.6139&lng=77.2090"
```

### Get Route with Traffic
```bash
curl "http://localhost:5000/api/route?origin=New+Delhi&destination=28.6139,77.2090"
```

## Key Features Explained

### Smart Routing Algorithm
- Analyzes multiple route alternatives
- Considers real-time traffic conditions
- Calculates traffic delays and provides recommendations
- Sorts routes by fastest travel time

### Hospital Integration
- Automatically finds hospitals within 10km radius
- Displays hospital ratings and locations
- Interactive map markers for easy selection

### Traffic Analysis
- Real-time traffic data from Google Maps
- Color-coded traffic status indicators
- Delay predictions in minutes
- Alternative route suggestions

## Dependencies

- **Flask 2.3.3**: Web framework
- **Flask-SQLAlchemy 3.0.5**: Database ORM
- **Flask-Login 0.6.3**: User session management
- **Flask-WTF 1.1.1**: Form handling and validation
- **googlemaps 4.10.0**: Google Maps API client
- **Bootstrap 5**: Frontend framework
- **Font Awesome 6**: Icons

## Security Features

- Password hashing with Werkzeug
- CSRF protection with Flask-WTF
- Secure session management
- Environment variable protection for API keys

## License

This project is open source and available under the MIT License.

