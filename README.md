[![Join Telegram](https://img.shields.io/badge/Telegram-Join%20Channel-blue?logo=telegram)](https://t.me/NxMirror)

# Deployment Guide
---
Create a `.env` or `config.env` file using this template (Check sample_config.env):

```env
TOKEN=your_bot_token_here
API=your_api_id_here
HASH=your_api_hash_here
ADMINS=your_admin_user_ids_comma_separated
LOG=your_log_channel_or_group_id
MONGO=your_mongodb_uri
DB_NAME=your_database_name
FAQ=True
IMG_CLOUD=True
IMGBB_API_KEY=your_imgbb_api_key_here
LOG_FILE=bot.log
WEB_RESPONSE=your_web_response_name
SOURCE_BUTTON=True
SOURCE=https://github.com/Krshnasys/FeedbackBot
PRODUCTS=True
```
---
##1. Deploy to Heroku (Dashboard GUI)
### Steps:

1. Go to [Heroku Dashboard](https://dashboard.heroku.com/)
2. Click **New → Create new app**
3. Name your app and choose a region
4. Under **Deploy**, choose **GitHub**
5. Connect your GitHub repo
6. Enable automatic deploys (optional)
7. Go to **Settings → Config Vars**, and add all required variables from `config.env`
8. In **Settings**, set the buildpack to Python (if not using Docker)
9. Click **Deploy Branch**
10. Scale up Dynos 

✅ Your bot will run as a worker process.

---
##2. Deploy to Heroku using CLI

- Install [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
- Login with `heroku login`
- Git must be initialized

### Steps:

```bash
heroku create your-app-name
heroku git:remote -a your-app-name
heroku stack:set container
heroku config:set $(cat config.env | xargs)
git add .
git commit -m "Initial commit"
git push heroku main -f
heroku ps:scale worker=1
heroku logs --tail
```
## 3. Deploy using Docker (Locally)

### Prerequisites:

- Install [Docker](https://www.docker.com/get-started)

### Steps:

```bash
docker build -t nxmirror-bot .
docker run --env-file=config.env --name=nxmirror nxmirror-bot
```
✅ Your bot will now be running inside a Docker container.

---

## 🧱 5. Deploy using Docker Compose

### Prerequisites:

- Install [Docker Compose](https://docs.docker.com/compose/install/)

### Steps:

1. Ensure `docker-compose.yml` and `config.env` are in the same directory
2. Run:

```bash
docker-compose up --build -d
```

✅ Docker Compose will handle everything: building, environment setup, and running the bot.

---

## 🔁 Restart / Stop Commands (Docker & Compose)

To restart:

```bash
docker restart nxmirror  # Or the name of your container
```

To stop:

```bash
docker stop nxmirror
```

To rebuild:

```bash
docker-compose up --build -d
```

Forking and editing this repo won’t make you a developer. Thanks!"
