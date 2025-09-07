from app import create_app

# Create the Flask application instance
app = create_app()

# This is the WSGI application that Vercel will use
if __name__ == "__main__":
    app.run()
