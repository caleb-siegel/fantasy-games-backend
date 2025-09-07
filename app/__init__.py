from flask import Flask, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///fantasy_betting.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-string')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # Tokens don't expire for simplicity
    
    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    
    # Import and register blueprints
    from app.routes.auth import auth_bp
    from app.routes.leagues import leagues_bp
    from app.routes.bets import bets_bp
    from app.routes.results import results_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(leagues_bp, url_prefix='/api/leagues')
    app.register_blueprint(bets_bp, url_prefix='/api/bets')
    app.register_blueprint(results_bp, url_prefix='/api/results')
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'Fantasy Betting API is running'}
    
    # Test CORS endpoint
    @app.route('/api/test-cors', methods=['GET', 'OPTIONS'])
    def test_cors():
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization")
            response.headers.add('Access-Control-Allow-Methods', "GET,OPTIONS")
            return response
        return {'message': 'CORS test successful'}
    
    # Explicit CORS handling for all routes
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With,Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,HEAD')
        response.headers.add('Access-Control-Expose-Headers', 'Authorization')
        return response
    
    # Handle preflight OPTIONS requests
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = make_response()
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization,X-Requested-With,Accept")
            response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS,HEAD")
            return response
    
    return app