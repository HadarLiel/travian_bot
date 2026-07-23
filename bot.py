import discord
import os
import re
import http.server
import socketserver
import threading
from discord.ext import commands
from discord.ui import Modal, TextInput, View, Button
from dotenv import load_dotenv

# --- טริק ל-Render: שרת ווב קטנטן ברקע כדי לספק את דרישת הפורטים בחינם ---
PORT = int(os.environ.get("PORT", 8080))

class SimpleHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Travian Bot is alive and running!")

def run_server():
    with socketserver.TCPServer(("", PORT), httpd=SimpleHandler) as httpd:
        httpd.serve_forever()

# מריצים את השרת בחוט נפרד (Background Thread) כדי שלא יפריע לבוט
threading.Thread(target=run_server, daemon=True).start()
# ------------------------------------------------------------------

# טעינת הטוקן מהקובץ המוסתר
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

active_requests = {}

# ==========================================
# טופס המגינים והלוגיקה המתמטית
# ==========================================
class TroopsModal(Modal, title='Def Call Update'):
    troops_input = TextInput(
        label='How many troops did you send?',
        placeholder='e.g., 2000',
        required=True,
        max_length=7
    )

    def __init__(self, message_id: int):
        super().__init__()
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        req = active_requests.get(self.message_id)
        if not req:
            await interaction.response.send_message("This request is already closed or not found.", ephemeral=True)
            return

        try:
            sent_troops = int(self.troops_input.value)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            return

        target = req['target']
        current = req['current']
        missing_troops = target - current

        if sent_troops > missing_troops:
            accepted_troops = missing_troops
            excess_troops = sent_troops - missing_troops
            req['current'] = target
        else:
            accepted_troops = sent_troops
            excess_troops = 0
            req['current'] += sent_troops

        msg = interaction.message 
        
        if req['current'] >= req['target']:
            embed = discord.Embed(
                title="✅ Def Call Completed!",
                description=f"**Coordinates:** {req['coords_formatted']}\n**Latest Landing:** {req['landing_time']}\n**Target Reached:** {req['current']} / {req['target']}\n\nThank you to everyone who defended!",
                color=discord.Color.green()
            )
            await msg.edit(embed=embed, view=None) 
            del active_requests[self.message_id]
            response_text = f"Received! You sent {sent_troops} troops. We only needed {accepted_troops}, so you can return {excess_troops} troops home! The call is now complete."
        else:
            embed = discord.Embed(
                title="⚔️ Active Def Call",
                description=f"**Coordinates:** {req['coords_formatted']}\n**Latest Landing:** {req['landing_time']}\n**Current:** {req['current']} / {req['target']}",
                color=discord.Color.orange()
            )
            await msg.edit(embed=embed)
            if excess_troops > 0:
                response_text = f"Received! We only needed {accepted_troops} more. Please call back {excess_troops} troops."
            else:
                response_text = f"Received! Added {accepted_troops} troops to the count."

        await interaction.response.send_message(response_text, ephemeral=True)

class DefView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="I sent troops!", style=discord.ButtonStyle.green, emoji="🛡️")
    async def send_def_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TroopsModal(interaction.message.id))


# ==========================================
# טופס יצירת קריאה ולוח הבקרה
# ==========================================
class CreateCallModal(Modal, title='Create New Def Call'):
    target_input = TextInput(
        label='Troops Needed',
        placeholder='e.g., 10000',
        required=True,
        max_length=7
    )
    time_input = TextInput(
        label='Latest Landing Time',
        placeholder='e.g., 18:00 Server Time',
        required=True,
        max_length=50
    )
    coords_input = TextInput(
        label='Coordinates or Link',
        placeholder='e.g., 45|-23 or https://...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = int(self.target_input.value)
        except ValueError:
            await interaction.response.send_message("Troops needed must be a valid number.", ephemeral=True)
            return
        
        landing_time = self.time_input.value
        coords_raw = self.coords_input.value

        match = re.search(r'x=(-?\d+)&y=(-?\d+)', coords_raw)
        if match:
            x, y = match.groups()
            coords_formatted = f"[{x}|{y}]({coords_raw})" 
        else:
            coords_formatted = coords_raw 

        embed = discord.Embed(
            title="⚔️ Active Def Call",
            description=f"**Coordinates:** {coords_formatted}\n**Latest Landing:** {landing_time}\n**Current:** 0 / {target}",
            color=discord.Color.orange()
        )
        
        call_msg = await interaction.channel.send(embed=embed, view=DefView())
        
        active_requests[call_msg.id] = {
            "target": target,
            "current": 0,
            "coords_formatted": coords_formatted,
            "landing_time": landing_time
        }

        await interaction.response.send_message("Def call created successfully!", ephemeral=True)

class DashboardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Def Call 📢", style=discord.ButtonStyle.blurple)
    async def create_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CreateCallModal())


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')

@bot.command()
async def setup(ctx):
    embed = discord.Embed(
        title="🛡️ Defense Command Center",
        description="Click the button below to request defense for your village.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=DashboardView())

bot.run(TOKEN)