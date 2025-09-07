# Fantasy Betting League Backend

A Flask-based backend API for a fantasy betting league application with JWT authentication, PostgreSQL database, and sports odds integration.

## Features

- **Authentication**: JWT-based user registration and login
- **League Management**: Create leagues, join via invite codes, manage members
- **Betting System**: Place bets on NFL games with weekly $100 balance
- **Results & Scoring**: Automatic result calculation and league standings
- **Sports Odds Integration**: Real-time NFL moneyline odds from external APIs

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: PostgreSQL (via Supabase)
- **ORM**: SQLAlchemy
- **Authentication**: JWT (Flask-JWT-Extended)
- **External API**: The Odds API (or similar sports odds provider)
- **Deployment**: Ready for Vercel, Railway, or Heroku

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and update with your values:

```bash
cp env.example .env
```

Update the following variables in `.env`:

```env
# Database (Supabase)
DATABASE_URL=postgresql://username:password@db.supabase.co:5432/postgres

# Security
SECRET_KEY=your-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production

# External API
ODDS_API_KEY=your-odds-api-key-here

# CORS (for frontend)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 3. Database Setup

The application will automatically create tables on first run. For production, consider using Flask-Migrate:

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 4. Run the Application

```bash
python app.py
```

The API will be available at `http://localhost:5000`

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info

### League Management
- `POST /leagues` - Create new league
- `POST /leagues/join` - Join league via invite code
- `GET /leagues/:id` - Get league details
- `GET /leagues/:id/standings` - Get league standings
- `POST /leagues/:id/schedule` - Generate weekly schedule

### Betting
- `GET /bets/odds/week/:week` - Get NFL odds for week
- `POST /bets` - Place a bet
- `GET /bets/user/:week` - Get user's bets for week
- `GET /bets/matchup/:id` - Get matchup bets

### Results
- `POST /results/update` - Update game results
- `GET /results/week/:week` - Get weekly results

## Database Schema

### Core Tables
- **Users**: User accounts with authentication
- **Leagues**: Fantasy leagues with invite codes
- **LeagueMembers**: User membership in leagues
- **Matchups**: Weekly head-to-head matchups
- **Bets**: Individual bets placed by users
- **Games**: NFL games with odds and results

## Core Logic

### Weekly Betting System
1. Each user starts with $100 fake money every week
2. Users place bets on NFL moneyline odds
3. Bets are tied to specific matchups
4. After games finish, results are calculated
5. Matchup winners determined by final balance
6. League standings updated automatically

### Betting Rules
- Maximum $100 per week per user
- Bets must be placed before game start time
- Moneyline bets only (Phase 1)
- Automatic payout calculation based on odds

## External API Integration

The application integrates with sports odds APIs (The Odds API, OddsJam, etc.) to:
- Fetch NFL moneyline odds
- Get game results and scores
- Update bet outcomes automatically

For development, mock data is provided when no API key is configured.

## Deployment

### Vercel
1. Install Vercel CLI: `npm i -g vercel`
2. Run: `vercel --prod`
3. Set environment variables in Vercel dashboard

### Railway
1. Connect GitHub repository
2. Set environment variables
3. Deploy automatically

### Heroku
1. Create Heroku app
2. Add PostgreSQL addon
3. Set environment variables
4. Deploy via Git

## Development Notes

- Mock data is enabled by default for testing
- Set `mock_data = False` in `OddsService` to use real API
- CORS is configured for frontend development
- JWT tokens don't expire for simplicity (configure for production)

## Future Enhancements

- Support for spreads, totals, parlays
- Real-time odds updates via WebSockets
- Public leagues with auto-fill
- In-league chat
- Advanced statistics dashboard
- Playoff bracket system
