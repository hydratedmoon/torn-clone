# Torn Clone — Prototype

A minimal browser-based crime/RPG game inspired by Torn, built with Flask.

## Features included
- Account registration/login
- Stats: strength, speed, dexterity, defense
- Energy (for gym training) and nerve (for crimes), both regenerate over real time
- Gym: spend energy to randomly boost a stat
- Crimes: spend nerve, random success/fail, jail time on failure, money on success
- Player list + simple PvP fighting based on total stats

## Setup

```bash
cd torn_clone
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser. Register two accounts (e.g. in two different browser tabs/incognito windows) to test fighting.

The database (`torn_clone.db`) is created automatically on first run.

## Where to go from here
- **Factions**: a `Faction` model that players can join, with shared chat/bank
- **Items/Inventory**: weapons/armor that modify battle stats
- **Travel**: locations with location-specific crimes or items
- **Jail/hospital separation**: right now jail just blocks crimes; Torn also has a hospital state after losing fights
- **A real combat formula**: currently fights are just `sum(stats) * random factor` — Torn's real combat math is much deeper (weapon damage, chance to hit, etc.)
- **Background regen via APScheduler**: works fine for a prototype with lazy regen, but a real scheduler matters once you add more time-based systems (e.g. travel duration, faction wars)
- **WebSockets for live updates** (e.g. Flask-SocketIO) instead of full page reloads

## Notes
- `app.config['SECRET_KEY']` is set to a dev value — change it before deploying anywhere public.
- Passwords are hashed with werkzeug's `generate_password_hash`/`check_password_hash`.
