# Environment Variables for Production Deployment

## Required Environment Variables

Set these environment variables in your Vercel dashboard under Project Settings > Environment Variables:

### Security
- `SECRET_KEY`: A random secret key for Flask sessions (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)
- `JWT_SECRET_KEY`: A random secret key for JWT tokens (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)

### Database
- `DATABASE_URL`: Your PostgreSQL connection string (Vercel Postgres recommended)
  - Format: `postgresql://username:password@host:port/database`
  - For Vercel Postgres: Use the connection string provided in your Vercel dashboard

### CORS Configuration
- `CORS_ORIGINS`: Comma-separated list of allowed origins
  - Example: `https://your-frontend-domain.vercel.app,https://your-custom-domain.com`
  - Include your frontend deployment URL

## Optional Environment Variables

### Flask Configuration
- `FLASK_ENV`: Set to `production` (already configured in vercel.json)
- `FLASK_DEBUG`: Set to `False` for production

## Database Setup

### Option 1: Vercel Postgres (Recommended)
1. In your Vercel dashboard, go to Storage
2. Create a new Postgres database
3. Copy the connection string and set it as `DATABASE_URL`

### Option 2: External Database
- Use services like Supabase, Railway, or PlanetScale
- Set the connection string as `DATABASE_URL`

## Database Initialization

After setting up the database and environment variables, initialize the database schema:

### Option 1: Using the initialization script (Recommended)
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database tables
python init_db.py
```

### Option 2: Using Flask-Migrate (if migrations are set up)
```bash
# Install dependencies
pip install -r requirements.txt

# Initialize migrations (first time only)
flask db init

# Create migration
flask db migrate -m "Initial migration"

# Apply migration
flask db upgrade
```

## Deployment Steps

1. **Push to GitHub**: Upload your backend code to a GitHub repository
2. **Connect to Vercel**: 
   - Go to [vercel.com](https://vercel.com)
   - Import your GitHub repository
   - Select the `backend` folder as the root directory
3. **Set Environment Variables**: Add all required environment variables in Vercel dashboard
4. **Deploy**: Vercel will automatically build and deploy your application
5. **Initialize Database**: Run the database initialization script after first deployment

## Post-Deployment

After successful deployment:
1. Your API will be available at `https://your-project-name.vercel.app`
2. Test the health endpoint: `https://your-project-name.vercel.app/api/health`
3. Update your frontend's API base URL to point to the new backend URL

## API Endpoints

All API endpoints are prefixed with `/api/`:

- **Authentication**: `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, `/api/auth/profile`
- **Leagues**: `/api/leagues/user`, `/api/leagues/create`, `/api/leagues/join`, `/api/leagues/{id}`, `/api/leagues/{id}/standings`, `/api/leagues/{id}/schedule`
- **Bets**: `/api/bets/...` (see bets.py for specific endpoints)
- **Results**: `/api/results/...` (see results.py for specific endpoints)
- **Health Check**: `/api/health`
