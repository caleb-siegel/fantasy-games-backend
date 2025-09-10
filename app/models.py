from app import db
from datetime import datetime
import bcrypt
import secrets
import string

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    leagues_created = db.relationship('League', backref='commissioner', lazy='dynamic')
    league_memberships = db.relationship('LeagueMember', backref='user', lazy='dynamic')
    bets = db.relationship('Bet', backref='user', lazy='dynamic')
    matchups_as_user1 = db.relationship('Matchup', foreign_keys='Matchup.user1_id', backref='user1', lazy='dynamic')
    matchups_as_user2 = db.relationship('Matchup', foreign_keys='Matchup.user2_id', backref='user2', lazy='dynamic')
    matchups_won = db.relationship('Matchup', foreign_keys='Matchup.winner_id', backref='winner', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        """Check password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

class League(db.Model):
    __tablename__ = 'leagues'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    commissioner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invite_code = db.Column(db.String(8), unique=True, nullable=False)
    is_setup_complete = db.Column(db.Boolean, default=False, nullable=False)
    setup_completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('LeagueMember', backref='league', lazy='dynamic')
    matchups = db.relationship('Matchup', backref='league', lazy='dynamic')
    
    def __init__(self, **kwargs):
        super(League, self).__init__(**kwargs)
        if not self.invite_code:
            self.invite_code = self.generate_invite_code()
    
    def generate_invite_code(self):
        """Generate a unique 8-character invite code"""
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not League.query.filter_by(invite_code=code).first():
                return code
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'commissioner_id': self.commissioner_id,
            'invite_code': self.invite_code,
            'is_setup_complete': self.is_setup_complete,
            'setup_completed_at': self.setup_completed_at.isoformat() if self.setup_completed_at else None,
            'created_at': self.created_at.isoformat(),
            'member_count': self.members.count()
        }

class LeagueMember(db.Model):
    __tablename__ = 'league_members'
    
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('leagues.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    points_for = db.Column(db.Float, default=0.0)
    points_against = db.Column(db.Float, default=0.0)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ensure unique user per league
    __table_args__ = (db.UniqueConstraint('league_id', 'user_id'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'league_id': self.league_id,
            'user_id': self.user_id,
            'username': self.user.username,
            'wins': self.wins,
            'losses': self.losses,
            'points_for': self.points_for,
            'points_against': self.points_against,
            'joined_at': self.joined_at.isoformat()
        }

class Matchup(db.Model):
    __tablename__ = 'matchups'
    
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('leagues.id'), nullable=False)
    week = db.Column(db.Integer, nullable=False)
    user1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    bets = db.relationship('Bet', backref='matchup', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'league_id': self.league_id,
            'week': self.week,
            'user1_id': self.user1_id,
            'user2_id': self.user2_id,
            'user1_username': self.user1.username,
            'user2_username': self.user2.username,
            'winner_id': self.winner_id,
            'created_at': self.created_at.isoformat()
        }

class Bet(db.Model):
    __tablename__ = 'bets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    matchup_id = db.Column(db.Integer, db.ForeignKey('matchups.id'), nullable=False)
    betting_option_id = db.Column(db.Integer, db.ForeignKey('betting_options.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    potential_payout = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, locked, won, lost, cancelled
    week = db.Column(db.Integer, nullable=False)
    locked_at = db.Column(db.DateTime, nullable=True)
    odds_snapshot_decimal = db.Column(db.Float, nullable=True)
    odds_snapshot_american = db.Column(db.Integer, nullable=True)
    bookmaker_snapshot = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    betting_option = db.relationship('BettingOption', backref='bets')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'matchup_id': self.matchup_id,
            'betting_option_id': self.betting_option_id,
            'amount': self.amount,
            'potential_payout': self.potential_payout,
            'status': self.status,
            'week': self.week,
            'locked_at': self.locked_at.isoformat() if self.locked_at else None,
            'odds_snapshot_decimal': self.odds_snapshot_decimal,
            'odds_snapshot_american': self.odds_snapshot_american,
            'bookmaker_snapshot': self.bookmaker_snapshot,
            'created_at': self.created_at.isoformat(),
            'betting_option': self.betting_option.to_dict() if self.betting_option else None
        }

class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.String(50), primary_key=True)  # From odds API
    home_team = db.Column(db.String(50), nullable=False)
    away_team = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    week = db.Column(db.Integer, nullable=False)
    result = db.Column(db.String(20), nullable=True)  # home_win, away_win, null
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    betting_options = db.relationship('BettingOption', backref='game', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'start_time': self.start_time.isoformat(),
            'week': self.week,
            'result': self.result,
            'created_at': self.created_at.isoformat()
        }

class BettingOption(db.Model):
    __tablename__ = 'betting_options'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(50), db.ForeignKey('games.id'), nullable=False)
    market_type = db.Column(db.String(20), nullable=False)  # h2h, spreads, totals
    outcome_name = db.Column(db.String(100), nullable=False)  # Team name or "Over"/"Under"
    outcome_point = db.Column(db.Float, nullable=True)  # For spreads/totals
    bookmaker = db.Column(db.String(50), nullable=False)  # fanduel, draftkings, etc.
    american_odds = db.Column(db.Integer, nullable=False)  # -110, +150, etc.
    decimal_odds = db.Column(db.Float, nullable=False)  # 1.91, 2.50, etc.
    is_locked = db.Column(db.Boolean, default=False)
    locked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'game_id': self.game_id,
            'market_type': self.market_type,
            'outcome_name': self.outcome_name,
            'outcome_point': self.outcome_point,
            'bookmaker': self.bookmaker,
            'american_odds': self.american_odds,
            'decimal_odds': self.decimal_odds,
            'is_locked': self.is_locked,
            'locked_at': self.locked_at.isoformat() if self.locked_at else None,
            'created_at': self.created_at.isoformat(),
            'game': self.game.to_dict() if self.game else None
        }
