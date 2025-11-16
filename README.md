# Discord Text-Based Game Bot

A Discord bot that allows multiple players to play a text-based movement game. Each player has their own game field where they can move around using emoji reactions.

## Features

- 🎮 Multi-player support - Each player has their own independent game
- 🎯 Reaction-based movement - Click arrow emojis to move
- 🔄 Real-time updates - Game field updates in the same message
- 🚧 Obstacle avoidance - Random obstacles prevent movement
- 📦 Boundary checking - Players can't move outside the game field
- 🎨 Customizable emojis - Configure emojis per server using `/configure`
- ⚙️ Server-specific settings - Field size and player lives configurable per server
- 🎁 Item collection - Collect items and reach the portal to advance levels
- 🧟 Zombie enemies - Avoid zombies that move toward you
- 💾 Persistent configuration - Server settings saved and loaded on restart

## Setup Instructions

### 1. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name (e.g., "Text Game Bot")
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot" and confirm
5. Under "Privileged Gateway Intents", enable:
   - ✅ Message Content Intent
   - ✅ Server Members Intent (if needed)
6. Copy the bot token (click "Reset Token" if needed) - **Keep this secret!**

### 2. Invite Bot to Your Server

1. In the Developer Portal, go to the "OAuth2" → "URL Generator" section
2. Under "Scopes", select:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Under "Bot Permissions", select:
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Read Message History
   - ✅ Add Reactions
   - ✅ Manage Messages (for removing reactions)
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### 3. Install Dependencies

Make sure you have Python 3.8 or higher installed, then:

```bash
pip install -r requirements.txt
```

### 4. Configure Bot Token

1. Copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your bot token:
   ```
   DISCORD_BOT_TOKEN=your_actual_bot_token_here
   ```

### 5. Run the Bot

```bash
python bot.py
```

You should see a message like:
```
BotName#1234 has logged in!
Loaded config for server: Your Server Name (123456789)
Synced 2 command(s)
```

Note: The bot will automatically load server configurations on startup.

## How to Play

1. In any channel where the bot has permissions, type `/play`
2. The bot will create a game field and add arrow reaction emojis (⬆️⬇️⬅️➡️)
3. Click the arrow emojis to move your player (🟢) around the field
4. Collect items (💎🪵🪨⚫) scattered across the field
5. Avoid obstacles (🟥) and zombies (🧟) - zombies move toward you!
6. Reach the portal (🛠️) after collecting enough items to advance to the next level
7. Each click moves you one space in that direction
8. The game field updates automatically after each move
9. You have limited lives - avoid zombies or you'll lose a life!

## Configuration

### Server-Specific Configuration

Server administrators can configure emojis and game settings using the `/configure` command:

1. Type `/configure` in any channel
2. Click a category button (Field Objects, Items, Movement, or Game Settings)
3. Click a button for the specific emoji or setting you want to change
4. Enter the new value in the modal that appears
5. Settings are saved automatically and persist across bot restarts

#### Configurable Settings:

**Emojis:**
- Field Objects: Wall, Obstacle, Empty space, Player, Portal, Zombie
- Items: Diamond, Wood, Stone, Coal
- Movement: Up, Down, Left, Right arrows

**Game Settings:**
- Field Width: 5-50 (default: 10)
- Field Height: 3-30 (default: 5)
- Player Lives: 1-10 (default: 3)

#### Using Custom Discord Emojis

You can use custom Discord emojis from your server in two ways:

1. **Using emoji name** (easiest):
   - Type `:emoji_name:` (e.g., `:stone:`)
   - The bot will automatically find and use the emoji from your server

2. **Using full emoji format**:
   - Enable Developer Mode: User Settings → Advanced → Enable Developer Mode
   - Right-click the emoji → Copy ID
   - Enter: `<:emoji_name:emoji_id>` (e.g., `<:stone:123456789012345678>`)
   - For animated emojis: `<a:emoji_name:emoji_id>`

**Important Notes:**
- Custom emojis must exist in the server where you're configuring
- Custom emojis work great for reactions (movement arrows)
- Custom emojis in the game field won't render inside code blocks, so the bot automatically removes code block formatting when custom emojis are detected
- Configuration files are stored in `configs/{server_id}.json` and persist across restarts

### Default Configuration

The `config.py` file contains default values used when server-specific configs don't exist. These use standard Unicode emojis and can be overridden per-server using `/configure`. You generally don't need to edit `config.py` unless you want to change the defaults for new servers.

## Troubleshooting

**Bot doesn't respond to `/play` or `/configure`:**
- Make sure the bot has the `applications.commands` scope when invited
- Wait a few minutes for slash commands to sync globally
- Try restarting the bot

**Bot can't add reactions:**
- Check that the bot has "Add Reactions" permission in the server
- Make sure the bot has "Manage Messages" permission to remove reactions

**Bot doesn't update messages:**
- Ensure the bot has "Send Messages" and "Embed Links" permissions
- Check that the bot has "Read Message History" permission

**Can't use `/configure`:**
- Only server administrators can use `/configure`
- Make sure you have administrator permissions in the server

**Custom emoji not found:**
- The emoji must exist in the server where you're configuring
- Try using the full format: `<:emoji_name:emoji_id>` instead of `:emoji_name:`
- Make sure the bot has access to the emoji's server

## Technical Details

- Built with Python 3.8+ and discord.py
- Uses slash commands (`/play`, `/configure`) for game control
- Uses reaction events for movement input
- Game state stored in memory (resets when bot restarts)
- Server configurations stored in JSON files (`configs/{server_id}.json`) and persist across restarts
- Each player can have one active game at a time
- Supports multiple levels with increasing difficulty
- Zombies use weighted pathfinding to move toward the player

