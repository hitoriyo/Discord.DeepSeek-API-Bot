import discord
from discord.ext import commands
import requests
import json
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Bot setup with correct intents
intents = discord.Intents.default()
intents.message_content = True  # This is the privileged intent
intents.members = True          # This might also be needed

bot = commands.Bot(
    command_prefix='!', 
    intents=intents,
    help_command=None  # Optional: removes default help command
)

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')

async def call_deepseek_api(message_content, conversation_history=None):
    """
    Call DeepSeek API with the given message and conversation history
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Prepare messages array
    messages = []
    
    # Add conversation history if provided
    if conversation_history:
        messages.extend(conversation_history)
    
    # Add current message
    messages.append({"role": "user", "content": message_content})
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        return "Sorry, I encountered an error while contacting DeepSeek API."
    except (KeyError, IndexError) as e:
        print(f"API Response Parsing Error: {e}")
        return "Sorry, I had trouble understanding the response from DeepSeek."

# Store conversation history per channel
conversation_histories = {}

def update_conversation_history(channel_id, user_message, assistant_response):
    """
    Update conversation history for a channel
    """
    if channel_id not in conversation_histories:
        conversation_histories[channel_id] = []
    
    # Add user message and assistant response to history
    conversation_histories[channel_id].extend([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_response}
    ])
    
    # Keep only last 10 messages (5 exchanges) to manage token usage
    if len(conversation_histories[channel_id]) > 20:
        conversation_histories[channel_id] = conversation_histories[channel_id][-20:]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

@bot.command(name='ask')
async def ask_deepseek(ctx, *, question):
    """
    Ask DeepSeek a question
    """
    # Show typing indicator
    async with ctx.typing():
        # Get conversation history for this channel
        history = conversation_histories.get(ctx.channel.id, [])
        
        # Call DeepSeek API
        response = await call_deepseek_api(question, history)
        
        # Update conversation history
        update_conversation_history(ctx.channel.id, question, response)
        
        # Split response if it's too long for Discord
        if len(response) > 2000:
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for chunk in chunks:
                await ctx.send(chunk)
        else:
            await ctx.send(response)

@bot.command(name='clear')
async def clear_history(ctx):
    """
    Clear conversation history for this channel
    """
    if ctx.channel.id in conversation_histories:
        del conversation_histories[ctx.channel.id]
        await ctx.send("Conversation history cleared!")
    else:
        await ctx.send("No conversation history to clear.")

@bot.command(name='model')
async def set_model(ctx, model_name):
    """
    Set the DeepSeek model to use
    """
    global DEEPSEEK_MODEL
    DEEPSEEK_MODEL = model_name
    await ctx.send(f"Model set to: {model_name}")

@bot.command(name='help')
async def bot_help(ctx):
    """
    Show bot help information
    """
    help_text = """
**DeepSeek Discord Bot Commands:**
`!ask <question>` - Ask DeepSeek a question
`!clear` - Clear conversation history for this channel
`!model <model_name>` - Change the DeepSeek model
`!help` - Show this help message

**Example:** `!ask What is artificial intelligence?`
"""
    await ctx.send(help_text)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please provide a question after the command. Example: `!ask What is AI?`")
    else:
        await ctx.send(f"An error occurred: {error}")

# Run the bot
if __name__ == "__main__":
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    if not bot_token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables")
    else:
        bot.run(bot_token)