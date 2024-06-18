import os
import discord
from discord.ext import commands, tasks
import pymongo
import openai
from datetime import datetime, timedelta
import re
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer

# Configuration
openai.api_key = os.environ["OPENAI_API_KEY"]
discord_token = os.environ["DISCORD_BOT_TOKEN"]
discord_channel_id = int(os.environ["DISCORD_CHANNEL_ID"])

# MongoDB setup
mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
db = mongo_client["social_media_posts"]
collection = db["posts"]

# Discord Bot setup
bot = commands.Bot(command_prefix='!')

# NLP Setup
stop_words = set(stopwords.words("english"))
stemmer = PorterStemmer()

def clean_text(text):
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    tokens = word_tokenize(text.lower())
    filtered_tokens = [stemmer.stem(word) for word in tokens if word not in stop_words]
    return " ".join(filtered_tokens)

@tasks.loop(hours=1)
async def fetch_and_process_posts():
    print("Fetching and processing posts...")
    last_hour = datetime.now() - timedelta(hours=1)
    posts = collection.find({"timestamp": {"$gte": last_hour}})

    important_posts = [post for post in posts if "update" in post["text"].lower() or "announcement" in post["text"].lower()]

    if important_posts:
        responses = await generate_summaries([post['text'] for post in important_posts])

        channel = bot.get_channel(discord_channel_id)
        for post, summary in zip(important_posts, responses):
            # Store summary in MongoDB
            post["summary"] = summary
            collection.update_one({"_id": post["_id"]}, {"$set": {"summary": summary}})
            
            # Post summary to Discord
            await channel.send(f"**Summary of Important Post:**\n{summary}")

async def generate_summaries(texts):
    summaries = []
    for text in texts:
        chat = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": f"Summarize this important post: {text}"}],
            max_tokens=150
        )
        summaries.append(chat.choices[0].message['content'])
    return summaries

@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    fetch_and_process_posts.start()

bot.run(discord_token)
