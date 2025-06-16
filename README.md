[![Join Telegram](https://img.shields.io/badge/Telegram-Join%20Channel-blue?logo=telegram)](https://t.me/NxMirror) 

<details>
<summary> Features</summary>

---

### User Commands
- `/start` — Start the bot  
- `/help` — Get help and usage guide  
- `/buy` — Browse available services/products  
- `/alive` — Check if the bot is active  
- `/ping` — Measure bot response time  
- `/system` — Show system resource usage  
- `/id` — Get user ID and chat info  
- `/info` — Fetch user profile details  
- `/img` — Upload an image to cloud  
- `/ocr` — Extract text from image or text file  
- `/telegraphtxt` — Upload plain text to Telegraph  
- `/telegraph` — Upload images to Telegraph  
- `/stickerid` — Retrieve sticker file ID  
- `/getsticker` — Get detailed info about a sticker  
- `/wiki` — Search any topic on Wikipedia  
- `/news` — Get trending news headlines  

---

### Admin Commands
- `/addservice` — Add a new product to the selling list  
- `/editservice` — Edit existing product details  
- `/removeservice` — Remove a product from the list  
- `/listservices` — View all available products  
- `/cleanservices` — Delete all products from the database  
- `/users` — Get total registered users  
- `/send` — Send a direct message to a user  
- `/broadcast` — Send a message to all users  
- `/logs` — Fetch recent bot logs  
- `/commands` — Update bot command list  
- `/getcmds` — View current command list  
- `/keyword` — Add keyword-triggered auto-reply  
- `/keywords` — View all active keywords  
- `/delkeyword` — Delete a specific keyword  
- `/clearkeywords` — Remove all keywords  
- `/save` — Save callback data and response  
- `/listcallbacks` — List all stored callbacks  
- `/delcallback` — Delete a specific callback  
- `/clearcallbacks` — Clear all saved callbacks  

---

### Note:
For instance, with `/addservice`, admins can introduce new items or services for users to purchase, while `/editservice` allows them to update existing product details such as price or description. If a product is outdated, it can be removed using `/removeservice`, or the entire list can be wiped clean with `/cleanservices`. 

</details>

# Deploy To Heroku
<a href="https://heroku.com/deploy?template=https://github.com/Krshnasys/FeedbackBot">
  <img src="https://www.herokucdn.com/deploy/button.svg" alt="<b>Deploy To Heroku</b>">
</a>

# Other Ways
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
## 1. Deploy to Heroku (Dashboard GUI)
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

Your bot will run as a worker process.

---
## 2. Deploy to Heroku using CLI

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
 Your bot will now be running inside a Docker container.

---

## 5. Deploy using Docker Compose

### Prerequisites:

- Install [Docker Compose](https://docs.docker.com/compose/install/)

### Steps:

1. Ensure `docker-compose.yml` and `config.env` are in the same directory
2. Run:

```bash
docker-compose up --build -d
```

 Docker Compose will handle everything: building, environment setup, and running the bot.

---

## Restart / Stop Commands (Docker & Compose)

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

## License & Copyright

© 2025 FtKrishna. All rights reserved.  
This project, FeedbackBoy, is released under the [MIT License](LICENSE).  
You are free to use, modify, and distribute it — just remember to give credit.
