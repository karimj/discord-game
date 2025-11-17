"""Main Discord bot file with event handlers."""

import os
import asyncio
import discord
from discord.ext import commands
from discord import utils
from dotenv import load_dotenv
from game import Game
from config_manager import ConfigManager

# Load environment variables
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration manager
config_manager = ConfigManager()

# Store active games: {message_id: Game}
active_games: dict[int, Game] = {}

# Store user to message mapping: {user_id: message_id}
user_games: dict[int, int] = {}

# Store user levels: {user_id: level}
user_levels: dict[int, int] = {}

# Store server configs in memory: {guild_id: emoji_config}
server_configs: dict[int, dict] = {}


@bot.event
async def on_ready():
    """Called when the bot is ready."""
    print(f"{bot.user} has logged in!")
    
    # Load server configurations
    for guild in bot.guilds:
        # Store full config (emojis + settings)
        server_configs[guild.id] = config_manager.load_config(guild.id)
        print(f"Loaded config for server: {guild.name} ({guild.id})")
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when the bot joins a new guild."""
    # Load configuration for the new guild
    server_configs[guild.id] = config_manager.load_config(guild.id)
    print(f"Loaded config for new server: {guild.name} ({guild.id})")


def create_game_embed(game: Game, title: str = "🎮 Game", emojis: dict = None, item_types: dict = None) -> discord.Embed:
    """Create a game embed with field, inventory, and level info."""
    # Check if using custom emojis (they don't render in code blocks)
    field_render = game.render()
    if emojis is None:
        emojis = {}
    if item_types is None:
        item_types = {}
    
    # Get UI emojis (heart and skull)
    heart_emoji = emojis.get("heart", "❤️")
    skull_emoji = emojis.get("skull", "💀")
    
    all_emojis = list(emojis.values()) if emojis else []
    all_emojis.extend(item_types.values() if item_types else [])
    uses_custom_emoji = any(
        emoji.startswith("<:") or emoji.startswith("<a:") 
        for emoji in all_emojis
    )
    
    # Use code block for Unicode emojis, plain text for custom emojis
    if uses_custom_emoji:
        description = field_render
    else:
        description = f"```\n{field_render}\n```"
    
    # Discord embed description limit is 4096 characters
    # If the field is too large, truncate and add a warning
    MAX_DESCRIPTION_LENGTH = 4096
    if len(description) > MAX_DESCRIPTION_LENGTH:
        # Calculate how much we can show (leave room for warning message)
        warning_msg = "\n\n⚠️ Field too large to display fully. Consider reducing field size in settings."
        max_field_length = MAX_DESCRIPTION_LENGTH - len(warning_msg)
        
        if uses_custom_emoji:
            # Truncate the field render
            truncated_field = field_render[:max_field_length]
            description = truncated_field + warning_msg
        else:
            # For code blocks, we need to account for the ``` markers
            code_block_overhead = 7  # ```\n and \n```
            max_field_length = MAX_DESCRIPTION_LENGTH - len(warning_msg) - code_block_overhead
            truncated_field = field_render[:max_field_length]
            description = f"```\n{truncated_field}\n```{warning_msg}"
    
    # Set embed color based on game state
    if game.game_over:
        embed_color = discord.Color.red()
    elif game.is_level_complete():
        embed_color = discord.Color.gold()
    else:
        embed_color = discord.Color.green()
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=embed_color
    )
    
    # Add game over message if applicable
    if game.game_over:
        embed.add_field(
            name=f"{skull_emoji} Game Over",
            value="You ran out of lives! Use `/play` to start a new game.",
            inline=False
        )
    
    # Add level info
    embed.add_field(
        name="Level",
        value=f"Level {game.level}",
        inline=True
    )
    
    # Add lives info
    lives_emoji = heart_emoji * game.player_lives if game.player_lives > 0 else skull_emoji
    embed.add_field(
        name="Lives",
        value=f"{lives_emoji} {game.player_lives}",
        inline=True
    )
    
    # Add progress info
    total_collected = game.get_total_collected()
    progress = f"{total_collected}/{game.required_items_count}"
    embed.add_field(
        name="Progress",
        value=progress,
        inline=True
    )
    
    # Add inventory
    inventory = game.get_inventory()
    inventory_text = ""
    for item_type, count in inventory.items():
        if count > 0:
            emoji = item_types.get(item_type, "❓") if item_types else "❓"
            inventory_text += f"{emoji} {item_type.capitalize()}: {count}\n"
    
    if inventory_text:
        embed.add_field(
            name="Inventory",
            value=inventory_text.strip(),
            inline=False
        )
    else:
        embed.add_field(
            name="Inventory",
            value="Empty",
            inline=False
        )
    
    if game.game_over:
        embed.set_footer(text="Game Over - Use /play to restart!")
    else:
        embed.set_footer(text="Click the arrows below to move!")
    
    return embed


@bot.tree.command(name="play", description="Start a new game!")
async def play_command(interaction: discord.Interaction):
    """Handle the /play slash command."""
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else None
    
    # If user already has an active game, end it first
    if user_id in user_games:
        old_message_id = user_games[user_id]
        if old_message_id in active_games:
            del active_games[old_message_id]
        del user_games[user_id]
    
    # Reset level to 1 for new game
    user_levels[user_id] = 1
    
    # Get server-specific emojis and settings
    if guild_id and guild_id in server_configs:
        server_emojis = config_manager.get_emojis(guild_id)
        item_types = config_manager.get_item_types(guild_id)
        game_settings = config_manager.get_game_settings(guild_id)
    else:
        server_emojis = config_manager.get_default_emojis()
        item_types = config_manager.get_default_item_types()
        game_settings = config_manager.get_game_settings(0) if guild_id else config_manager.get_game_settings(0)
    
    # Create emoji dict for Game class
    game_emojis = {
        "wall": server_emojis["wall"],
        "obstacle": server_emojis["obstacle"],
        "empty": server_emojis["empty"],
        "player": server_emojis["player"],
        "portal": server_emojis["portal"],
        "zombie": server_emojis["zombie"],
    }
    
    # Get player lives from server settings
    player_lives = game_settings.get("player_lives", 3)
    
    # Create new game at level 1 with server-specific emojis and settings
    game = Game(level=1, player_lives=player_lives, emojis=game_emojis, item_types=item_types)
    
    # Create embed
    embed = create_game_embed(game, "🎮 Game Started!", emojis=server_emojis, item_types=item_types)
    
    # Send message
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    # Add reaction emojis
    movement_emojis = [server_emojis["up"], server_emojis["down"], server_emojis["left"], server_emojis["right"]]
    for emoji in movement_emojis:
        await message.add_reaction(emoji)
    
    # Store game state
    active_games[message.id] = game
    user_games[user_id] = message.id


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle reaction additions for movement."""
    # Ignore bot's own reactions
    if user.bot:
        return
    
    # Check if this is a game message
    message_id = reaction.message.id
    if message_id not in active_games:
        return
    
    # Check if this is the game owner
    game = active_games[message_id]
    if user.id not in user_games or user_games[user.id] != message_id:
        return
    
    # Get guild ID for server-specific emojis
    guild_id = reaction.message.guild.id if reaction.message.guild else None
    
    # Get emoji to direction mapping for this server
    if guild_id and guild_id in server_configs:
        emoji_to_direction = config_manager.get_emoji_to_direction(guild_id)
        server_emojis = server_configs[guild_id]
        item_types = config_manager.get_item_types(guild_id)
    else:
        emoji_to_direction = config_manager.get_emoji_to_direction(0)  # Use defaults
        server_emojis = config_manager.get_default_emojis()
        item_types = config_manager.get_default_item_types()
    
    # Get direction from emoji
    # Handle both Unicode and custom emojis
    # str(reaction.emoji) returns Unicode for standard emojis or "<:name:id>" for custom emojis
    emoji_str = str(reaction.emoji)
    
    if emoji_str not in emoji_to_direction:
        return
    
    # Get UI emojis
    skull_emoji = server_emojis.get("skull", "💀")
    
    # Check if game is over
    if game.game_over:
        # Show game over embed
        embed = create_game_embed(game, f"{skull_emoji} Game Over", emojis=server_emojis, item_types=item_types)
        await reaction.message.edit(embed=embed)
        # Remove user's reaction
        try:
            await reaction.message.remove_reaction(reaction.emoji, user)
        except discord.errors.Forbidden:
            pass
        return
    
    direction = emoji_to_direction[emoji_str]
    
    # Try to move
    moved = game.move(direction[0], direction[1])
    
    # Check if game over after move (collision might have occurred)
    if game.game_over:
        embed = create_game_embed(game, f"{skull_emoji} Game Over", emojis=server_emojis, item_types=item_types)
        await reaction.message.edit(embed=embed)
        # Remove user's reaction
        try:
            await reaction.message.remove_reaction(reaction.emoji, user)
        except discord.errors.Forbidden:
            pass
        return
    
    # Check if level is complete
    if game.is_level_complete():
        # Level completed!
        current_level = game.level
        next_level = current_level + 1
        
        # Create completion embed
        embed = create_game_embed(game, f"🎉 Level {current_level} Complete!", emojis=server_emojis, item_types=item_types)
        embed.color = discord.Color.gold()
        embed.add_field(
            name="Status",
            value=f"✅ You collected {game.get_total_collected()} items and reached the portal!",
            inline=False
        )
        
        # Create emoji dict for new Game instance
        game_emojis = {
            "wall": server_emojis["wall"],
            "obstacle": server_emojis["obstacle"],
            "empty": server_emojis["empty"],
            "player": server_emojis["player"],
            "portal": server_emojis["portal"],
            "zombie": server_emojis["zombie"],
        }
        
        # Advance to next level (preserve lives from current game)
        user_levels[user.id] = next_level
        new_game = Game(level=next_level, player_lives=game.player_lives, emojis=game_emojis, item_types=item_types)
        active_games[message_id] = new_game
        
        # Add next level info
        embed.add_field(
            name="Next Level",
            value=f"Starting Level {next_level}!",
            inline=False
        )
        
        await reaction.message.edit(embed=embed)
        
        # Wait a moment, then update to new level
        await asyncio.sleep(2)
        
        # Create new level embed
        new_embed = create_game_embed(new_game, f"🎮 Level {next_level}", emojis=server_emojis, item_types=item_types)
        await reaction.message.edit(embed=new_embed)
    else:
        # Update embed with current game state
        embed = create_game_embed(game, emojis=server_emojis, item_types=item_types)
        await reaction.message.edit(embed=embed)
    
    # Remove user's reaction to allow repeated moves
    try:
        await reaction.message.remove_reaction(reaction.emoji, user)
    except discord.errors.Forbidden:
        pass  # Ignore if we can't remove the reaction


# Configuration UI Components
class SettingInputModal(discord.ui.Modal):
    """Modal for inputting numeric setting values."""
    
    def __init__(self, setting_key: str, setting_name: str, current_value: int, config_manager: ConfigManager, guild_id: int, min_value: int = 1, max_value: int = 100):
        super().__init__(title=f"Set {setting_name}")
        self.setting_key = setting_key
        self.setting_name = setting_name
        self.current_value = current_value
        self.config_manager = config_manager
        self.guild_id = guild_id
        self.min_value = min_value
        self.max_value = max_value
    
    setting_input = discord.ui.TextInput(
        label="Value",
        placeholder="Enter a number",
        default="",
        max_length=10,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = int(self.setting_input.value.strip())
            
            # Validate range
            if value < self.min_value or value > self.max_value:
                await interaction.response.send_message(
                    f"❌ Value must be between {self.min_value} and {self.max_value}.",
                    ephemeral=True
                )
                return
            
            # Update configuration
            success = self.config_manager.update_setting(self.guild_id, self.setting_key, value)
            
            if success:
                # Update in-memory config if it exists
                if self.guild_id in server_configs:
                    server_configs[self.guild_id][self.setting_key] = value
                
                await interaction.response.send_message(
                    f"✅ Updated **{self.setting_name}** to: {value}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Failed to save configuration. Please try again.",
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message(
                f"❌ Invalid number. Please enter a valid integer.",
                ephemeral=True
            )


class EmojiInputModal(discord.ui.Modal, title="Set Emoji"):
    """Modal for inputting emoji value."""
    
    def __init__(self, emoji_key: str, emoji_name: str, current_value: str, config_manager: ConfigManager, guild_id: int):
        super().__init__()
        self.emoji_key = emoji_key
        self.emoji_name = emoji_name
        self.current_value = current_value
        self.config_manager = config_manager
        self.guild_id = guild_id
    
    emoji_input = discord.ui.TextInput(
        label="Emoji",
        placeholder="Enter emoji (:name:, <:name:id>, or Unicode)",
        default="",
        max_length=100,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        emoji_value = self.emoji_input.value.strip()
        original_value = emoji_value
        
        # Check if input is in :name: format (without ID)
        if emoji_value.startswith(":") and emoji_value.endswith(":") and len(emoji_value) > 2:
            emoji_name = emoji_value[1:-1]  # Remove the colons
            
            # Try to find the emoji in the guild
            if interaction.guild:
                # Search for custom emoji by name
                custom_emoji = utils.get(interaction.guild.emojis, name=emoji_name)
                if custom_emoji:
                    # Convert to proper format
                    if custom_emoji.animated:
                        emoji_value = f"<a:{emoji_name}:{custom_emoji.id}>"
                    else:
                        emoji_value = f"<:{emoji_name}:{custom_emoji.id}>"
                else:
                    # Emoji not found in guild
                    await interaction.response.send_message(
                        f"❌ Custom emoji `{emoji_value}` not found in this server.\n\n"
                        f"Please use:\n"
                        f"- Unicode emoji (e.g., 🟢)\n"
                        f"- Custom emoji name: `:name:` (must exist in this server)\n"
                        f"- Full custom emoji format: `<:name:id>`\n"
                        f"- Animated emoji: `<a:name:id>`",
                        ephemeral=True
                    )
                    return
            else:
                # No guild context
                await interaction.response.send_message(
                    f"❌ Cannot resolve emoji name `{emoji_value}` outside of a server context.",
                    ephemeral=True
                )
                return
        
        # Basic validation - check if it looks like a valid emoji or custom emoji
        # Custom emoji format: <:name:id> or <a:name:id>
        # Unicode emojis can be 1-10 characters (including modifiers)
        is_custom = (emoji_value.startswith("<:") or emoji_value.startswith("<a:")) and emoji_value.endswith(">")
        is_unicode = len(emoji_value) > 0 and len(emoji_value) <= 10  # Allow longer unicode sequences
        is_valid = is_custom or is_unicode
        
        if not is_valid:
            await interaction.response.send_message(
                f"❌ Invalid emoji format. Please use:\n"
                f"- Unicode emoji (e.g., 🟢)\n"
                f"- Custom emoji name: `:name:` (must exist in this server)\n"
                f"- Full custom emoji format: `<:name:id>`\n"
                f"- Animated emoji: `<a:name:id>`",
                ephemeral=True
            )
            return
        
        # Update configuration
        success = self.config_manager.update_emoji(self.guild_id, self.emoji_key, emoji_value)
        
        if success:
            # Update in-memory config
            if self.guild_id in server_configs:
                server_configs[self.guild_id][self.emoji_key] = emoji_value
            else:
                server_configs[self.guild_id] = self.config_manager.get_emojis(self.guild_id)
            
            # Show original input if it was converted
            display_value = original_value if original_value != emoji_value else emoji_value
            await interaction.response.send_message(
                f"✅ Updated **{self.emoji_name}** emoji to: {emoji_value}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Failed to save configuration. Please try again.",
                ephemeral=True
            )


def create_emoji_button(emoji_key: str, emoji_name: str, current_value: str, config_manager: ConfigManager, guild_id: int, row: int = None):
    """Helper function to create a button for setting an emoji."""
    # Truncate long emoji values for button label
    display_value = current_value[:20] if len(current_value) > 20 else current_value
    
    # Create a closure to capture the values properly
    def make_callback(key, name):
        async def button_callback(interaction: discord.Interaction):
            # Reload emojis to get latest values
            current_emojis = config_manager.get_emojis(guild_id)
            current = current_emojis.get(key, "❓")
            modal = EmojiInputModal(key, name, current, config_manager, guild_id)
            modal.emoji_input.default = current
            await interaction.response.send_modal(modal)
        return button_callback
    
    button = discord.ui.Button(
        label=f"{emoji_name}: {display_value}",
        style=discord.ButtonStyle.primary,
        row=row
    )
    button.callback = make_callback(emoji_key, emoji_name)
    return button


def create_setting_button(setting_key: str, setting_name: str, current_value: int, config_manager: ConfigManager, guild_id: int, min_value: int = 1, max_value: int = 100, row: int = None):
    """Helper function to create a button for setting a numeric game setting."""
    def make_callback(key, name, min_val, max_val):
        async def button_callback(interaction: discord.Interaction):
            # Reload settings to get latest values
            current_settings = config_manager.get_game_settings(guild_id)
            current = current_settings.get(key, current_value)
            modal = SettingInputModal(key, name, current, config_manager, guild_id, min_val, max_val)
            modal.setting_input.default = str(current)
            await interaction.response.send_modal(modal)
        return button_callback
    
    button = discord.ui.Button(
        label=f"{setting_name}: {current_value}",
        style=discord.ButtonStyle.primary,
        row=row
    )
    button.callback = make_callback(setting_key, setting_name, min_value, max_value)
    return button


class CategoryView(discord.ui.View):
    """View with buttons for emoji categories."""
    
    def __init__(self, config_manager: ConfigManager, guild_id: int, emojis: dict):
        super().__init__(timeout=300)  # 5 minute timeout
        self.config_manager = config_manager
        self.guild_id = guild_id
        self.emojis = emojis
    
    @discord.ui.button(label="Field Objects", style=discord.ButtonStyle.secondary, row=0)
    async def field_objects_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show field object emoji configuration."""
        # Reload emojis to get latest values
        current_emojis = self.config_manager.get_emojis(self.guild_id)
        view = discord.ui.View(timeout=300)  # Plain view, no category buttons
        
        view.add_item(create_emoji_button("wall", "Wall", current_emojis.get("wall", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("obstacle", "Obstacle", current_emojis.get("obstacle", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("empty", "Empty", current_emojis.get("empty", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("player", "Player", current_emojis.get("player", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("portal", "Portal", current_emojis.get("portal", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("zombie", "Zombie", current_emojis.get("zombie", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("heart", "Heart", current_emojis.get("heart", "❓"), self.config_manager, self.guild_id, 2))
        view.add_item(create_emoji_button("skull", "Skull", current_emojis.get("skull", "❓"), self.config_manager, self.guild_id, 2))
        
        embed = discord.Embed(
            title="Configure Field Object & UI Emojis",
            description="Click a button to set the emoji for that object.",
            color=discord.Color.blue()
        )
        for key in ["wall", "obstacle", "empty", "player", "portal", "zombie", "heart", "skull"]:
            current = current_emojis.get(key, "❓")
            embed.add_field(name=key.capitalize(), value=f"Current: {current}", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Items", style=discord.ButtonStyle.secondary, row=0)
    async def items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show item emoji configuration."""
        # Reload emojis to get latest values
        current_emojis = self.config_manager.get_emojis(self.guild_id)
        view = discord.ui.View(timeout=300)  # Plain view, no category buttons
        
        view.add_item(create_emoji_button("diamond", "Diamond", current_emojis.get("diamond", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("wood", "Wood", current_emojis.get("wood", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("stone", "Stone", current_emojis.get("stone", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("coal", "Coal", current_emojis.get("coal", "❓"), self.config_manager, self.guild_id, 1))
        
        embed = discord.Embed(
            title="Configure Item Emojis",
            description="Click a button to set the emoji for that item.",
            color=discord.Color.green()
        )
        for key in ["diamond", "wood", "stone", "coal"]:
            current = current_emojis.get(key, "❓")
            embed.add_field(name=key.capitalize(), value=f"Current: {current}", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Movement", style=discord.ButtonStyle.secondary, row=0)
    async def movement_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show movement emoji configuration."""
        # Reload emojis to get latest values
        current_emojis = self.config_manager.get_emojis(self.guild_id)
        view = discord.ui.View(timeout=300)  # Plain view, no category buttons
        
        view.add_item(create_emoji_button("up", "Up", current_emojis.get("up", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("down", "Down", current_emojis.get("down", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("left", "Left", current_emojis.get("left", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("right", "Right", current_emojis.get("right", "❓"), self.config_manager, self.guild_id, 1))
        
        embed = discord.Embed(
            title="Configure Movement Emojis",
            description="Click a button to set the emoji for that direction.",
            color=discord.Color.orange()
        )
        for key in ["up", "down", "left", "right"]:
            current = current_emojis.get(key, "❓")
            embed.add_field(name=key.capitalize(), value=f"Current: {current}", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Game Settings", style=discord.ButtonStyle.secondary, row=1)
    async def game_settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show game settings configuration."""
        # Reload settings to get latest values
        current_settings = self.config_manager.get_game_settings(self.guild_id)
        view = discord.ui.View(timeout=300)  # Plain view, no category buttons
        
        view.add_item(create_setting_button("player_lives", "Player Lives", current_settings.get("player_lives", 3), self.config_manager, self.guild_id, min_value=1, max_value=10, row=0))
        
        embed = discord.Embed(
            title="Configure Game Settings",
            description="Click a button to set the value for that setting.",
            color=discord.Color.red()
        )
        embed.add_field(name="Player Lives", value=f"Current: {current_settings.get('player_lives', 3)}", inline=True)
        embed.set_footer(text="Note: Field size is automatically capped based on emoji length to prevent message size limits.")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="View All", style=discord.ButtonStyle.success, row=1)
    async def view_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show all current configurations."""
        # Reload emojis and settings to get latest values
        current_emojis = self.config_manager.get_emojis(self.guild_id)
        current_settings = self.config_manager.get_game_settings(self.guild_id)
        
        embed = discord.Embed(
            title="Current Configuration",
            description="All configured settings for this server:",
            color=discord.Color.purple()
        )
        
        # Field objects
        field_text = "\n".join([
            f"**{key.capitalize()}**: {current_emojis.get(key, '❓')}"
            for key in ["wall", "obstacle", "empty", "player", "portal", "zombie", "heart", "skull"]
        ])
        embed.add_field(name="Field Objects & UI", value=field_text, inline=False)
        
        # Items
        items_text = "\n".join([
            f"**{key.capitalize()}**: {current_emojis.get(key, '❓')}"
            for key in ["diamond", "wood", "stone", "coal"]
        ])
        embed.add_field(name="Items", value=items_text, inline=False)
        
        # Movement
        movement_text = "\n".join([
            f"**{key.capitalize()}**: {current_emojis.get(key, '❓')}"
            for key in ["up", "down", "left", "right"]
        ])
        embed.add_field(name="Movement", value=movement_text, inline=False)
        
        # Game Settings
        settings_text = f"**Player Lives**: {current_settings.get('player_lives', 3)}"
        embed.add_field(name="Game Settings", value=settings_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="configure", description="Configure emojis for game objects (Admin only)")
async def configure_command(interaction: discord.Interaction):
    """Handle the /configure slash command."""
    # Check if user is administrator
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You need administrator permissions to use this command.",
            ephemeral=True
        )
        return
    
    guild_id = interaction.guild.id if interaction.guild else None
    if not guild_id:
        await interaction.response.send_message(
            "❌ This command can only be used in a server.",
            ephemeral=True
        )
        return
    
    # Get current emojis for this server
    if guild_id in server_configs:
        emojis = config_manager.get_emojis(guild_id)
    else:
        emojis = config_manager.get_emojis(guild_id)
        server_configs[guild_id] = config_manager.load_config(guild_id)
    
    # Create embed
    embed = discord.Embed(
        title="⚙️ Emoji Configuration",
        description="Configure emojis for different game objects. Click a category button to get started!",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Categories",
        value="• **Field Objects**: Wall, Obstacle, Empty, Player, Portal, Zombie, Heart, Skull\n"
              "• **Items**: Diamond, Wood, Stone, Coal\n"
              "• **Movement**: Up, Down, Left, Right\n"
              "• **Game Settings**: Player Lives",
        inline=False
    )
    embed.set_footer(text="Changes are saved automatically and persist across bot restarts.")
    
    # Create view with category buttons
    view = CategoryView(config_manager, guild_id, emojis)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please create a .env file with your bot token.")
        exit(1)
    
    bot.run(token)

