# FriendifyBot

**FriendifyBot** is an advanced Discord bot designed to automate "Speed-Friending" sessions. It handles the entire lifecycle of a session: from pairing users based on history to moving them between voice channels automatically.

Built with **Python**, **Discord.py**, and **PostgreSQL**, it uses graph theory (`networkx`) to ensure optimal pairings, prioritizing people who haven't met yet or met the longest time ago.

## Key Features

* **Smart Matchmaking:** Uses a "Time-Weighted" algorithm. The bot prefers creating pairs that have never met. If repeats are necessary, it prioritizes the "oldest" connections.
* **Voice Automation:** Automatically creates temporary voice channels, moves participants, signals time limits (audio & text), and returns everyone to the lobby after the round.
* **Round Status Tracking:** Tracks the lifecycle of every round in the database (In Progress, Completed, Cancelled, Error) for better reliability and statistics.
* **Bulk Move Tools:** Admins can instantly move all users from one channel to another using `!moveto`.
* **Persistent History:** All meetings are stored in a PostgreSQL database.
* **Dockerized:** Fully containerized with Docker Compose for easy deployment.
* **Secure:** Commands are restricted by Roles and specific Text Channels.
* **User History:** Users can check their last 10 meetings via DM using `!history`.

## Tech Stack

* **Language:** Python 3.14
* **Framework:** Discord.py
* **Database:** PostgreSQL 17 (Async SQLAlchemy 2.0)
* **Migrations:** Alembic
* **Algorithms:** NetworkX (Max Weight Matching)
* **Deployment:** Docker & Docker Compose

## Installation & Setup

The recommended way to run the bot is via Docker.

### 1. Clone the repository
```bash
git clone https://github.com/Donkrzawayan/FriendifyBot.git
cd FriendifyBot
```

### 2. Configure Environment Variables
Create a .env file in the root directory.
```ini
# Discord Configuration
DISCORD_TOKEN=discord_bot_token
ALLOWED_ROLE_ID=123456789012345678       # ID of the role allowed to manage sessions
ALLOWED_CHANNEL_IDS=[123456789012345678] # List of Channel IDs where bot listens to commands

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=friendify_db
POSTGRES_HOST=db
POSTGRES_PORT=5432

# General
TIMEZONE=Europe/Warsaw
```

### 3. Run with Docker
Build and start the containers (Bot + Database).
```bash
docker-compose up -d --build
```

### 4. Apply Database Migrations
Once the database container is running, apply the Alembic migrations to create/update tables.
```bash
docker-compose run --rm bot alembic upgrade head
```
To stop it, use `docker-compose stop`.

## Usage

### Manager Commands

Requires the role defined in `ALLOWED_ROLE_ID`.

- `!start <minutes>`  
Starts a new speed friending round.
- `!stop`  
Immediately stops the current round, updates the round status to `CANCELLED`, deletes temporary channels, and moves everyone back to the lobby.
- `!moveto <Target_Channel>`  
Moves all users from the voice channel you are currently in to the `Target_Channel`.
  - Example: `!moveto "Lobby"` or `!moveto 1234567890`

### User Commands

- `!history`  
Sends a private message (DM) with a list of the user's last 10 meetings.

## Credit

Original Concept & Idea: [MariuszSochacki](https://github.com/MariuszSochacki)

## License

This project is licensed under the CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0 International).

You are free to:
- Share — copy and redistribute the material in any medium or format.
- Adapt — remix, transform, and build upon the material.

Under the following terms:
- Attribution — You must give appropriate credit.
- NonCommercial — You may not use the material for commercial purposes.
