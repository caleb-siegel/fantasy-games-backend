from flask import Flask, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
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
    
    # CORS configuration - allow all origins for now to test
    cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
    app.config['CORS_ORIGINS'] = cors_origins
    
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
    
    # CORS configuration with additional headers (after blueprints)
    CORS(app, 
         origins=cors_origins,
         supports_credentials=False,  # Set to False when using wildcard origins
         allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD'],
         expose_headers=['Authorization'])
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'Fantasy Betting API is running'}
    
    
    return app