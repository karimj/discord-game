"""Main Discord bot file with event handlers."""

import os
import asyncio
import logging
import discord
from discord.ext import commands
from discord import utils
from dotenv import load_dotenv
from typing import Optional
from game import Game
from config_manager import ConfigManager
from score_manager import ScoreManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration manager
config_manager = ConfigManager()

# Score manager
score_manager = ScoreManager()

# Store active games: {message_id: Game}
active_games: dict[int, Game] = {}

# Store game players: {message_id: set of user_ids}
game_players: dict[int, set[int]] = {}

# Store game owners: {message_id: user_id} (who created the game)
game_owners: dict[int, int] = {}

# Store user levels: {user_id: level} (for tracking level progression)
user_levels: dict[int, int] = {}

# Store server configs in memory: {guild_id: emoji_config}
server_configs: dict[int, dict] = {}

# Store previous death counts per game: {message_id: {user_id: death_count}}
previous_death_counts: dict[int, dict[int, int]] = {}


@bot.event
async def on_ready():
    """Called when the bot is ready."""
    logger.info(f"{bot.user} has logged in!")
    
    # Load server configurations
    for guild in bot.guilds:
        try:
            # Store full config (emojis + settings)
            server_configs[guild.id] = config_manager.load_config(guild.id)
            logger.info(f"Loaded config for server: {guild.name} ({guild.id})")
        except Exception as e:
            logger.error(f"Error loading config for server {guild.id}: {e}", exc_info=True)
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}", exc_info=True)


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when the bot joins a new guild."""
    try:
        # Load configuration for the new guild
        server_configs[guild.id] = config_manager.load_config(guild.id)
        logger.info(f"Loaded config for new server: {guild.name} ({guild.id})")
    except Exception as e:
        logger.error(f"Error loading config for new server {guild.id}: {e}", exc_info=True)


@bot.event
async def on_message_delete(message: discord.Message):
    """Clean up games when messages are deleted."""
    message_id = message.id
    if message_id in active_games:
        logger.info(f"Cleaning up game for deleted message {message_id}")
        if message_id in active_games:
            del active_games[message_id]
        if message_id in game_players:
            del game_players[message_id]
        if message_id in game_owners:
            del game_owners[message_id]
        if message_id in previous_death_counts:
            del previous_death_counts[message_id]


def create_game_embed(game: Game, title: str = "🎮 Game", emojis: dict = None, item_types: dict = None, user_id: Optional[int] = None) -> discord.Embed:
    """Create a game embed with field, inventory, and level info for all players."""
    # Check if using custom emojis (they don't render in code blocks)
    field_render = game.render()
    if emojis is None:
        emojis = {}
    if item_types is None:
        item_types = {}
    
    # Get UI emojis (heart, skull, and join)
    heart_emoji = emojis.get("heart", "❤️")
    skull_emoji = emojis.get("skull", "💀")
    join_emoji = emojis.get("join", "✅")
    
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
    if game.game_over and game.winner is None:
        embed.add_field(
            name=f"{skull_emoji} Game Over",
            value="All players ran out of lives! Use `/play` to start a new game.",
            inline=False
        )
    
    # Add level info
    embed.add_field(
        name="Level",
        value=f"Level {game.level}",
        inline=True
    )
    
    # Add players info
    if game.player_positions:
        players_text = ""
        for player_id in game.players:
            player_emoji = game.get_player_emoji(player_id)
            lives = game.player_lives.get(player_id, 0)
            lives_display = heart_emoji * lives if lives > 0 else skull_emoji
            total_collected = game.get_total_collected(player_id)
            progress = f"{total_collected}/{game.required_items_count}"
            wins = game.get_player_wins(player_id)
            win_text = f", {wins} win{'s' if wins != 1 else ''}" if wins > 0 else ""
            players_text += f"{player_emoji} Player: {lives_display} {lives} lives, {progress} items{win_text}\n"
        
        embed.add_field(
            name="Players",
            value=players_text.strip(),
            inline=False
        )
    
    # Add inventories for all players
    inventories_text = ""
    for player_id in game.players:
        player_emoji = game.get_player_emoji(player_id)
        inventory = game.get_inventory(player_id)
        if inventory:
            inv_items = []
            for item_type, count in inventory.items():
                if count > 0:
                    emoji = item_types.get(item_type, "❓") if item_types else "❓"
                    inv_items.append(f"{emoji} {item_type.capitalize()}: {count}")
            if inv_items:
                inventories_text += f"{player_emoji} {' | '.join(inv_items)}\n"
    
    if inventories_text:
        embed.add_field(
            name="Inventories",
            value=inventories_text.strip(),
            inline=False
        )
    else:
        embed.add_field(
            name="Inventories",
            value="All empty",
            inline=False
        )
    
    if game.game_over:
        embed.set_footer(text="Game Over - Use /play to restart!")
    else:
        embed.set_footer(text=f"Click {join_emoji} to join, then use arrows to move!")
    
    return embed


@bot.tree.command(name="play", description="Start a new game!")
async def play_command(interaction: discord.Interaction):
    """Handle the /play slash command."""
    try:
        user_id = interaction.user.id
        guild_id = interaction.guild.id if interaction.guild else None
        
        # If user already has an active game, end it first
        for message_id, players in list(game_players.items()):
            if user_id in players:
                # Remove user from that game
                players.discard(user_id)
                # If no players left, clean up the game
                if not players:
                    if message_id in active_games:
                        del active_games[message_id]
                    if message_id in game_owners:
                        del game_owners[message_id]
                    del game_players[message_id]
        
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
        
        # Get player emojis for this server
        player_emojis = config_manager.get_player_emojis(guild_id) if guild_id else config_manager.get_player_emojis(0)
        
        # Create new game at level 1 with server-specific emojis and settings
        # Pass first_player_id to add the creator as the first player
        game = Game(level=1, player_lives=player_lives, emojis=game_emojis, item_types=item_types, first_player_id=user_id, player_emojis=player_emojis)
        
        # Create embed
        embed = create_game_embed(game, "🎮 Game Started!", emojis=server_emojis, item_types=item_types)
        
        # Send message
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        
        # Add join reaction first, then movement reactions
        join_emoji = server_emojis.get("join", "✅")
        await message.add_reaction(join_emoji)
        
        movement_emojis = [server_emojis["up"], server_emojis["down"], server_emojis["left"], server_emojis["right"]]
        for emoji in movement_emojis:
            await message.add_reaction(emoji)
        
        # Store game state
        active_games[message.id] = game
        game_players[message.id] = {user_id}  # Creator is automatically joined
        game_owners[message.id] = user_id
        
        # Initialize death tracking for this game
        previous_death_counts[message.id] = {}
        
        # Track game start
        if guild_id:
            score_manager.increment_player_score(guild_id, user_id, "games_played")
    
    except Exception as e:
        logger.error(f"Error in play_command: {e}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred while starting the game. Please try again.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ An error occurred while starting the game. Please try again.",
                ephemeral=True
            )


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle reaction additions for joining and movement."""
    try:
        # Ignore bot's own reactions
        if user.bot:
            return
        
        # Check if this is a game message
        message_id = reaction.message.id
        if message_id not in active_games:
            return
        
        game = active_games[message_id]
        
        # Validate game still exists
        if game is None:
            # Clean up invalid game
            if message_id in active_games:
                del active_games[message_id]
            if message_id in game_players:
                del game_players[message_id]
            if message_id in game_owners:
                del game_owners[message_id]
            return
        
        # Get guild ID for server-specific emojis
        guild_id = reaction.message.guild.id if reaction.message.guild else None
    
        # Get server emojis
        if guild_id and guild_id in server_configs:
            server_emojis = config_manager.get_emojis(guild_id)
            item_types = config_manager.get_item_types(guild_id)
            emoji_to_direction = config_manager.get_emoji_to_direction(guild_id)
        else:
            server_emojis = config_manager.get_default_emojis()
            item_types = config_manager.get_default_item_types()
            emoji_to_direction = config_manager.get_emoji_to_direction(0)  # Use defaults
        
        # Get UI emojis
        skull_emoji = server_emojis.get("skull", "💀")
        join_emoji = server_emojis.get("join", "✅")
        
        # Handle both Unicode and custom emojis
        emoji_str = str(reaction.emoji)
        
        # Check if this is a join reaction
        if emoji_str == join_emoji:
            # Check if user is already in the game
            user_in_game = message_id in game_players and user.id in game_players[message_id]
            
            if user_in_game:
                # User already joined, remove reaction
                try:
                    await reaction.message.remove_reaction(reaction.emoji, user)
                except discord.errors.Forbidden:
                    pass
                return
            
            # Check if game is over
            if game.game_over:
                try:
                    await reaction.message.remove_reaction(reaction.emoji, user)
                except discord.errors.Forbidden:
                    pass
                return
            
            # Get player lives from server settings
            game_settings = config_manager.get_game_settings(guild_id) if guild_id else config_manager.get_game_settings(0)
            player_lives = game_settings.get("player_lives", 3)
            
            # Add player to game
            if game.add_player(user.id, player_lives):
                # Add to game_players tracking
                if message_id not in game_players:
                    game_players[message_id] = set()
                game_players[message_id].add(user.id)
                
                # Get player emoji
                player_emoji = game.get_player_emoji(user.id)
                
                # Create join message embed
                embed = create_game_embed(game, "🎮 Game", emojis=server_emojis, item_types=item_types)
                embed.add_field(
                    name="Player Joined",
                    value=f"{player_emoji} {user.display_name} joined the game!",
                    inline=False
                )
                await reaction.message.edit(embed=embed)
                
                # Remove user's reaction
                try:
                    await reaction.message.remove_reaction(reaction.emoji, user)
                except discord.errors.Forbidden:
                    pass
            return
        
        # Check if this is a movement reaction
        if emoji_str not in emoji_to_direction:
            return  # Not a movement emoji, ignore
        
        # Check if user is in the game (must join first)
        user_in_game = message_id in game_players and user.id in game_players[message_id]
        
        if not user_in_game:
            # User hasn't joined yet, remove reaction and ignore
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.errors.Forbidden:
                pass
            return
        
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
        
        # Track items collected before move
        items_before = game.get_total_collected(user.id) if user.id in game.player_positions else 0
        
        # Try to move the specific player
        moved = game.move(user.id, direction[0], direction[1])
        
        # Track item collection
        if moved and guild_id:
            items_after = game.get_total_collected(user.id) if user.id in game.player_positions else 0
            items_collected = items_after - items_before
            if items_collected > 0:
                score_manager.increment_player_score(guild_id, user.id, "items_collected", items_collected)
        
        # Track deaths - check if any players died
        if guild_id:
            # Initialize previous death counts for this game if not exists
            if message_id not in previous_death_counts:
                previous_death_counts[message_id] = {}
            
            # Check all players who were in the game (including those who might have been removed)
            # We check game_players to include all players who joined, not just active ones
            all_player_ids = set(game_players.get(message_id, set()))
            all_player_ids.update(game.players)  # Also include current players
            
            for player_id in all_player_ids:
                current_deaths = game.get_player_deaths(player_id)
                previous_deaths = previous_death_counts[message_id].get(player_id, 0)
                
                if current_deaths > previous_deaths:
                    # Player died - track it
                    deaths_to_add = current_deaths - previous_deaths
                    score_manager.increment_player_score(guild_id, player_id, "deaths", deaths_to_add)
                    previous_death_counts[message_id][player_id] = current_deaths
        
        # Check if level completed (player won)
        if game.is_level_complete() and game.winner is not None:
            # Track level completion scores
            if guild_id:
                # Update highest level for all players who participated
                for player_id in game.players:
                    current_highest = score_manager.get_player_stats(guild_id, player_id).get("highest_level", 0)
                    if game.level > current_highest:
                        score_manager.update_player_score(guild_id, player_id, "highest_level", game.level)
                    # Increment levels completed
                    score_manager.increment_player_score(guild_id, player_id, "levels_completed")
                
                # Increment wins for winner
                score_manager.increment_player_score(guild_id, game.winner, "wins")
            
            # Winner announcement
            winner_user_id = game.winner
            try:
                winner_user = await bot.fetch_user(winner_user_id)
                winner_name = winner_user.display_name
            except:
                winner_name = f"User {winner_user_id}"
            
            winner_emoji = game.get_player_emoji(winner_user_id)
            winner_wins = game.get_player_wins(winner_user_id)
            
            # Show completion message
            embed = create_game_embed(game, f"🎉 Level {game.level} Complete!", emojis=server_emojis, item_types=item_types)
            embed.color = discord.Color.gold()
            embed.add_field(
                name="Winner",
                value=f"{winner_emoji} **{winner_name}** won Level {game.level}! (Total wins: {winner_wins})",
                inline=False
            )
            embed.add_field(
                name="Next Level",
                value=f"Advancing to Level {game.level + 1}...",
                inline=False
            )
            await reaction.message.edit(embed=embed)
            
            # Wait a moment before advancing
            await asyncio.sleep(2)
            
            # Create new game for next level, preserving player data
            new_game = Game.create_next_level(game)
            active_games[message_id] = new_game
            
            # Preserve previous death counts for the new game
            if message_id in previous_death_counts:
                previous_death_counts[message_id] = {pid: game.get_player_deaths(pid) for pid in game.players}
            
            # Update embed for new level
            new_embed = create_game_embed(new_game, f"🎮 Level {new_game.level}", emojis=server_emojis, item_types=item_types)
            await reaction.message.edit(embed=new_embed)
            
            # Remove user's reaction
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.errors.Forbidden:
                pass
            return
        
        # Check if game over (all players lost)
        if game.game_over:
            # Track game completion for all players
            if guild_id:
                for player_id in list(game_players.get(message_id, set())):
                    score_manager.increment_player_score(guild_id, player_id, "games_completed")
            
            # Clean up death tracking for this game
            if message_id in previous_death_counts:
                del previous_death_counts[message_id]
            
            embed = create_game_embed(game, f"{skull_emoji} Game Over", emojis=server_emojis, item_types=item_types)
            await reaction.message.edit(embed=embed)
            # Remove user's reaction
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except discord.errors.Forbidden:
                pass
            return
        
        # Update embed with current game state
        embed = create_game_embed(game, "🎮 Game", emojis=server_emojis, item_types=item_types)
        await reaction.message.edit(embed=embed)
        
        # Remove user's reaction to allow repeated moves
        try:
            await reaction.message.remove_reaction(reaction.emoji, user)
        except discord.errors.Forbidden:
            pass  # Ignore if we can't remove the reaction
        except Exception as e:
            logger.error(f"Error removing reaction: {e}", exc_info=True)
    
    except discord.errors.NotFound:
        # Message was deleted, clean up game
        try:
            message_id = reaction.message.id if hasattr(reaction, 'message') and reaction.message else None
            if message_id:
                logger.info(f"Game message {message_id} was deleted, cleaning up game")
                if message_id in active_games:
                    del active_games[message_id]
                if message_id in game_players:
                    del game_players[message_id]
                if message_id in game_owners:
                    del game_owners[message_id]
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}", exc_info=True)
    except discord.errors.Forbidden:
        # Bot doesn't have permission
        try:
            message_id = reaction.message.id if hasattr(reaction, 'message') and reaction.message else None
            if message_id:
                logger.warning(f"Bot lacks permission for message {message_id}")
        except:
            pass
    except Exception as e:
        try:
            message_id = reaction.message.id if hasattr(reaction, 'message') and reaction.message else None
            logger.error(f"Error handling reaction on message {message_id}: {e}", exc_info=True)
            # Try to clean up if game is in bad state
            if message_id and message_id in active_games:
                # Don't delete immediately, but log the error
                logger.warning(f"Game {message_id} may be in bad state after error")
        except Exception as log_error:
            logger.error(f"Error in error handler: {log_error}", exc_info=True)


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
    
    @discord.ui.button(label="Player Emojis", style=discord.ButtonStyle.secondary, row=0)
    async def player_emojis_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show player emoji configuration."""
        # Reload emojis to get latest values
        current_emojis = self.config_manager.get_emojis(self.guild_id)
        view = discord.ui.View(timeout=300)  # Plain view, no category buttons
        
        view.add_item(create_emoji_button("player1", "Player 1", current_emojis.get("player1", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("player2", "Player 2", current_emojis.get("player2", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("player3", "Player 3", current_emojis.get("player3", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("player4", "Player 4", current_emojis.get("player4", "❓"), self.config_manager, self.guild_id, 1))
        
        embed = discord.Embed(
            title="Configure Player Emojis",
            description="Click a button to set the emoji for that player position. These emojis are assigned to players 1-4 based on join order.",
            color=discord.Color.purple()
        )
        for key in ["player1", "player2", "player3", "player4"]:
            current = current_emojis.get(key, "❓")
            embed.add_field(name=key.capitalize().replace("player", "Player "), value=f"Current: {current}", inline=True)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @discord.ui.button(label="Movement", style=discord.ButtonStyle.secondary, row=0)
    async def movement_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show movement emoji configuration."""
        # Reload emojis to get latest values
        current_emojis = self.config_manager.get_emojis(self.guild_id)
        view = discord.ui.View(timeout=300)  # Plain view, no category buttons
        
        view.add_item(create_emoji_button("join", "Join", current_emojis.get("join", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("up", "Up", current_emojis.get("up", "❓"), self.config_manager, self.guild_id, 0))
        view.add_item(create_emoji_button("down", "Down", current_emojis.get("down", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("left", "Left", current_emojis.get("left", "❓"), self.config_manager, self.guild_id, 1))
        view.add_item(create_emoji_button("right", "Right", current_emojis.get("right", "❓"), self.config_manager, self.guild_id, 2))
        
        embed = discord.Embed(
            title="Configure Movement & Join Emojis",
            description="Click a button to set the emoji for that action.",
            color=discord.Color.orange()
        )
        for key in ["join", "up", "down", "left", "right"]:
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
        
        # Player Emojis
        player_text = "\n".join([
            f"**{key.capitalize().replace('player', 'Player ')}**: {current_emojis.get(key, '❓')}"
            for key in ["player1", "player2", "player3", "player4"]
        ])
        embed.add_field(name="Player Emojis", value=player_text, inline=False)
        
        # Movement
        movement_text = "\n".join([
            f"**{key.capitalize()}**: {current_emojis.get(key, '❓')}"
            for key in ["join", "up", "down", "left", "right"]
        ])
        embed.add_field(name="Movement & Join", value=movement_text, inline=False)
        
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
              "• **Player Emojis**: Player 1, Player 2, Player 3, Player 4\n"
              "• **Movement**: Join, Up, Down, Left, Right\n"
              "• **Game Settings**: Player Lives",
        inline=False
    )
    embed.set_footer(text="Changes are saved automatically and persist across bot restarts.")
    
    # Create view with category buttons
    view = CategoryView(config_manager, guild_id, emojis)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# Leaderboard UI Components
class LeaderboardView(discord.ui.View):
    """View with buttons for selecting leaderboard stat type."""
    
    STAT_DISPLAY_NAMES = {
        "wins": "Wins",
        "highest_level": "Highest Level",
        "items_collected": "Items Collected",
        "games_played": "Games Played",
        "levels_completed": "Levels Completed",
        "games_completed": "Games Completed",
        "deaths": "Deaths"
    }
    
    def __init__(self, score_manager: ScoreManager, guild_id: int, current_stat: str = "wins"):
        super().__init__(timeout=300)  # 5 minute timeout
        self.score_manager = score_manager
        self.guild_id = guild_id
        self.current_stat = current_stat
    
    def format_stat_value(self, stat_name: str, value: int) -> str:
        """Format a stat value for display."""
        if stat_name == "highest_level":
            return f"Level {value}"
        elif stat_name == "items_collected":
            return f"{value:,} items"
        elif stat_name == "deaths":
            return f"{value:,} deaths"
        else:
            return f"{value:,}"
    
    async def create_leaderboard_embed(self, stat_name: str, user_id: int, client: discord.Client = None, guild: discord.Guild = None) -> discord.Embed:
        """Create a leaderboard embed for the given stat."""
        # Get top 10 players
        leaderboard = self.score_manager.get_leaderboard(self.guild_id, stat_name, limit=10)
        
        # Get current player's rank and stats
        player_rank = self.score_manager.get_player_rank(self.guild_id, user_id, stat_name)
        player_stats = self.score_manager.get_player_stats(self.guild_id, user_id)
        player_value = player_stats.get(stat_name, 0)
        
        # Check if player is in top 10
        player_in_top_10 = any(uid == user_id for uid, _ in leaderboard)
        
        # Create embed
        stat_display = self.STAT_DISPLAY_NAMES.get(stat_name, stat_name.replace("_", " ").title())
        embed = discord.Embed(
            title=f"Leaderboard: {stat_display}",
            color=discord.Color.gold()
        )
        
        # Build leaderboard text
        leaderboard_text = ""
        
        for rank, (uid, value) in enumerate(leaderboard, start=1):
            try:
                # Try to get user from guild first (faster)
                member = None
                if guild:
                    member = guild.get_member(uid)
                
                if member:
                    # Use mention for guild members
                    username = member.mention
                else:
                    # Use user ID format for mentions (Discord will resolve it)
                    username = f"<@{uid}>"
            except:
                # Fallback to user ID format
                username = f"<@{uid}>"
            
            # Use number for rank
            rank_display = f"{rank}."
            
            # Format: rank. @mention - value
            leaderboard_text += f"{rank_display} {username} - {self.format_stat_value(stat_name, value)}\n"
        
        # Add current player if not in top 10
        if not player_in_top_10 and player_rank is not None:
            leaderboard_text += "\n" + "─" * 30 + "\n"
            try:
                # Try to get user from guild first (faster)
                member = None
                if guild:
                    member = guild.get_member(user_id)
                
                if member:
                    # Use mention for guild members
                    username = member.mention
                else:
                    # Use user ID format for mentions (Discord will resolve it)
                    username = f"<@{user_id}>"
            except:
                # Fallback to user ID format
                username = f"<@{user_id}>"
            leaderboard_text += f"{player_rank}. {username} - {self.format_stat_value(stat_name, player_value)}\n"
        
        if leaderboard_text:
            embed.description = leaderboard_text
        else:
            embed.description = "No players have stats yet. Play a game to get on the leaderboard!"
        
        embed.set_footer(text="Click a button below to view different stats")
        
        return embed
    
    @discord.ui.button(label="Wins", style=discord.ButtonStyle.success, row=0)
    async def wins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show wins leaderboard."""
        self.current_stat = "wins"
        embed = await self.create_leaderboard_embed("wins", interaction.user.id, interaction.client, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Highest Level", style=discord.ButtonStyle.secondary, row=0)
    async def highest_level_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show highest level leaderboard."""
        self.current_stat = "highest_level"
        embed = await self.create_leaderboard_embed("highest_level", interaction.user.id, interaction.client, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Items", style=discord.ButtonStyle.primary, row=0)
    async def items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show items collected leaderboard."""
        self.current_stat = "items_collected"
        embed = await self.create_leaderboard_embed("items_collected", interaction.user.id, interaction.client, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Games Played", style=discord.ButtonStyle.secondary, row=1)
    async def games_played_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show games played leaderboard."""
        self.current_stat = "games_played"
        embed = await self.create_leaderboard_embed("games_played", interaction.user.id, interaction.client, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Levels Completed", style=discord.ButtonStyle.secondary, row=1)
    async def levels_completed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show levels completed leaderboard."""
        self.current_stat = "levels_completed"
        embed = await self.create_leaderboard_embed("levels_completed", interaction.user.id, interaction.client, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Games Completed", style=discord.ButtonStyle.secondary, row=1)
    async def games_completed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show games completed leaderboard."""
        self.current_stat = "games_completed"
        embed = await self.create_leaderboard_embed("games_completed", interaction.user.id, interaction.client, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Deaths", style=discord.ButtonStyle.danger, row=2)
    async def deaths_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show deaths leaderboard."""
        self.current_stat = "deaths"
        embed = await self.create_leaderboard_embed("deaths", interaction.user.id, interaction.client, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)


@bot.tree.command(name="leaderboard", description="View the leaderboard for various stats")
async def leaderboard_command(interaction: discord.Interaction):
    """Handle the /leaderboard slash command."""
    try:
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True
            )
            return
        
        # Create leaderboard view with default stat (wins)
        view = LeaderboardView(score_manager, guild_id, current_stat="wins")
        embed = await view.create_leaderboard_embed("wins", interaction.user.id, interaction.client, interaction.guild)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    except Exception as e:
        logger.error(f"Error in leaderboard_command: {e}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred while loading the leaderboard. Please try again.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ An error occurred while loading the leaderboard. Please try again.",
                ephemeral=True
            )


@bot.tree.command(name="stats", description="View your stats or another player's stats")
async def stats_command(interaction: discord.Interaction, user: Optional[discord.User] = None):
    """Handle the /stats slash command."""
    try:
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.",
                ephemeral=True
            )
            return
        
        # Use provided user or default to command user
        target_user = user if user else interaction.user
        user_id = target_user.id
        
        # Get player stats
        stats = score_manager.get_player_stats(guild_id, user_id)
        
        # Calculate win rate
        games_played = stats.get("games_played", 0)
        wins = stats.get("wins", 0)
        win_rate = (wins / games_played * 100) if games_played > 0 else 0.0
        
        # Create embed
        embed = discord.Embed(
            title=f"Stats for {target_user.display_name}",
            color=discord.Color.blue()
        )
        
        # Build stats text with name and value on same line
        stats_text = ""
        stats_text += f"Wins: {stats.get('wins', 0):,}\n"
        stats_text += f"Highest Level: Level {stats.get('highest_level', 0)}\n"
        stats_text += f"Items Collected: {stats.get('items_collected', 0):,}\n"
        stats_text += f"Games Played: {stats.get('games_played', 0):,}\n"
        stats_text += f"Levels Completed: {stats.get('levels_completed', 0):,}\n"
        stats_text += f"Games Completed: {stats.get('games_completed', 0):,}\n"
        stats_text += f"Deaths: {stats.get('deaths', 0):,}\n"
        stats_text += f"Win Rate: {win_rate:.1f}%\n" if games_played > 0 else "Win Rate: N/A\n"
        
        embed.description = stats_text
        
        # Add rank information
        rank_text = ""
        for stat_name, display_name in LeaderboardView.STAT_DISPLAY_NAMES.items():
            rank = score_manager.get_player_rank(guild_id, user_id, stat_name)
            if rank is not None:
                rank_text += f"**{display_name}**: #{rank}\n"
        
        if rank_text:
            embed.add_field(
                name="Ranks",
                value=rank_text,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    except Exception as e:
        logger.error(f"Error in stats_command: {e}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred while loading stats. Please try again.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ An error occurred while loading stats. Please try again.",
                ephemeral=True
            )


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables!")
        print("Please create a .env file with your bot token.")
        exit(1)
    
    bot.run(token)

