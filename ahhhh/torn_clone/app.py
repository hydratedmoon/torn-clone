import os
import random
import time
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///torn_clone.db'
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

# ---------------------------------------------------------------------------
# Config constants - tweak these to balance the game
# ---------------------------------------------------------------------------
MAX_ENERGY = 100
MAX_NERVE = 50
ENERGY_REGEN_PER_SEC = 1 / 30   # 1 energy every 30 seconds
NERVE_REGEN_PER_SEC = 1 / 120  # 1 nerve every 2 minutes

GYM_ENERGY_COST = 10
GYM_GAIN_MIN = 1
GYM_GAIN_MAX = 5

CRIMES = [
    {"id": "pickpocket", "name": "Pickpocket a stranger", "nerve_cost": 3,
     "difficulty": 0.75, "money_min": 10, "money_max": 80, "jail_seconds": 30},
    {"id": "shoplift", "name": "Shoplift from a store", "nerve_cost": 5,
     "difficulty": 0.60, "money_min": 30, "money_max": 150, "jail_seconds": 60},
    {"id": "burglary", "name": "Burgle a house", "nerve_cost": 8,
     "difficulty": 0.45, "money_min": 80, "money_max": 400, "jail_seconds": 120},
    {"id": "armed_robbery", "name": "Armed robbery", "nerve_cost": 12,
     "difficulty": 0.30, "money_min": 200, "money_max": 1000, "jail_seconds": 240},
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    money = db.Column(db.Integer, default=500)

    strength = db.Column(db.Integer, default=10)
    speed = db.Column(db.Integer, default=10)
    dexterity = db.Column(db.Integer, default=10)
    defense = db.Column(db.Integer, default=10)

    energy = db.Column(db.Float, default=MAX_ENERGY)
    nerve = db.Column(db.Float, default=MAX_NERVE)

    jail_until = db.Column(db.Float, default=0)  # unix timestamp
    last_update = db.Column(db.Float, default=lambda: time.time())

    def regen(self):
        """Lazily regenerate energy/nerve based on elapsed time."""
        now = time.time()
        elapsed = max(0, now - self.last_update)

        self.energy = min(MAX_ENERGY, self.energy + elapsed * ENERGY_REGEN_PER_SEC)
        self.nerve = min(MAX_NERVE, self.nerve + elapsed * NERVE_REGEN_PER_SEC)
        self.last_update = now

    def in_jail(self):
        return time.time() < self.jail_until

    def jail_remaining(self):
        return max(0, int(self.jail_until - time.time()))

    def total_battle_stats(self):
        return self.strength + self.speed + self.dexterity + self.defense


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def current_player():
    if 'player_id' not in session:
        return None
    player = Player.query.get(session['player_id'])
    if player:
        player.regen()
        db.session.commit()
    return player


def login_required(view):
    def wrapped(*args, **kwargs):
        if current_player() is None:
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('register'))

        if Player.query.filter_by(username=username).first():
            flash('That username is already taken.')
            return redirect(url_for('register'))

        player = Player(username=username, password_hash=generate_password_hash(password))
        db.session.add(player)
        db.session.commit()

        session['player_id'] = player.id
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        player = Player.query.filter_by(username=username).first()
        if player is None or not check_password_hash(player.password_hash, password):
            flash('Invalid username or password.')
            return redirect(url_for('login'))

        session['player_id'] = player.id
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('player_id', None)
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Game routes
# ---------------------------------------------------------------------------
@app.route('/')
@login_required
def dashboard():
    player = current_player()
    return render_template('dashboard.html', player=player, max_energy=MAX_ENERGY, max_nerve=MAX_NERVE)


@app.route('/gym', methods=['GET', 'POST'])
@login_required
def gym():
    player = current_player()

    if request.method == 'POST':
        stat = request.form.get('stat')
        if stat not in ('strength', 'speed', 'dexterity', 'defense'):
            flash('Invalid stat selected.')
            return redirect(url_for('gym'))

        if player.in_jail():
            flash(f"You're in jail for {player.jail_remaining()}s and can't train.")
            return redirect(url_for('gym'))

        if player.energy < GYM_ENERGY_COST:
            flash('Not enough energy to train.')
            return redirect(url_for('gym'))

        gain = random.randint(GYM_GAIN_MIN, GYM_GAIN_MAX)
        setattr(player, stat, getattr(player, stat) + gain)
        player.energy -= GYM_ENERGY_COST

        db.session.commit()
        flash(f'Training complete! {stat.capitalize()} +{gain}.')
        return redirect(url_for('gym'))

    return render_template('gym.html', player=player, energy_cost=GYM_ENERGY_COST)


@app.route('/crimes', methods=['GET', 'POST'])
@login_required
def crimes():
    player = current_player()
    result = None

    if request.method == 'POST':
        crime_id = request.form.get('crime_id')
        crime = next((c for c in CRIMES if c['id'] == crime_id), None)

        if crime is None:
            flash('Unknown crime.')
            return redirect(url_for('crimes'))

        if player.in_jail():
            flash(f"You're in jail for {player.jail_remaining()}s and can't commit crimes.")
            return redirect(url_for('crimes'))

        if player.nerve < crime['nerve_cost']:
            flash('Not enough nerve for that crime.')
            return redirect(url_for('crimes'))

        player.nerve -= crime['nerve_cost']

        # Skill bonus: dexterity nudges success chance a little
        success_chance = min(0.95, crime['difficulty'] + (player.dexterity * 0.002))
        success = random.random() < success_chance

        if success:
            payout = random.randint(crime['money_min'], crime['money_max'])
            player.money += payout
            result = {'success': True, 'message': f"Success! You earned ${payout}.", 'crime': crime['name']}
        else:
            player.jail_until = time.time() + crime['jail_seconds']
            result = {
                'success': False,
                'message': f"You got caught and sent to jail for {crime['jail_seconds']}s.",
                'crime': crime['name'],
            }

        db.session.commit()

    return render_template('crimes.html', player=player, crimes=CRIMES, result=result)


@app.route('/players')
@login_required
def players():
    player = current_player()
    all_players = Player.query.filter(Player.id != player.id).all()
    return render_template('players.html', player=player, all_players=all_players)


@app.route('/fight/<int:opponent_id>', methods=['POST'])
@login_required
def fight(opponent_id):
    player = current_player()
    opponent = Player.query.get_or_404(opponent_id)
    opponent.regen()

    if player.in_jail():
        flash(f"You're in jail for {player.jail_remaining()}s and can't fight.")
        return redirect(url_for('players'))

    # Simple weighted-random outcome based on total stats, with some randomness
    player_power = player.total_battle_stats() * random.uniform(0.8, 1.2)
    opponent_power = opponent.total_battle_stats() * random.uniform(0.8, 1.2)

    if player_power > opponent_power:
        winnings = max(10, int(opponent.money * 0.05))
        winnings = min(winnings, opponent.money)
        player.money += winnings
        opponent.money -= winnings
        flash(f'You defeated {opponent.username} and looted ${winnings}!')
    else:
        loss = max(5, int(player.money * 0.05))
        loss = min(loss, player.money)
        player.money -= loss
        opponent.money += loss
        flash(f'{opponent.username} beat you. You lost ${loss}.')

    db.session.commit()
    return redirect(url_for('players'))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
