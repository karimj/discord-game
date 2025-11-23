"""Configuration constants for the Discord game bot.

These are DEFAULT values used when server-specific JSON configs don't exist.
Server admins can override emojis and some game settings using the /configure command,
which saves to configs/{guild_id}.json. Custom emojis should be configured per-server.
"""

# Number of obstacles to place randomly (few obstacles)
OBSTACLE_COUNT = 3

# Emoji mappings - DEFAULT values, can be overridden per-server via /configure
# These use standard Unicode emojis. Server-specific custom Discord emojis are stored in JSON configs.
# For custom emojis, use format: "<:emoji_name:emoji_id>" or ":emoji_name:" in /configure
# To get emoji ID: Right-click emoji in Discord → Copy ID (enable Developer Mode first)

EMOJI_WALL = "⬛"  # Default: black square
EMOJI_OBSTACLE = "🟥"  # Default: red square
EMOJI_EMPTY = "🟦"  # Default: blue square
EMOJI_PLAYER = "🟢"  # Default: green circle

# Collectible item emojis - DEFAULT values, can be overridden per-server
EMOJI_DIAMOND = "💎"
EMOJI_WOOD = "🪵"
EMOJI_STONE = "🪨"
EMOJI_COAL = "⚫"

# Portal emoji (crafting table) - DEFAULT value, can be overridden per-server
EMOJI_PORTAL = "🛠️"

# Zombie emoji - DEFAULT value, can be overridden per-server
EMOJI_ZOMBIE = "🧟"

# UI emojis - DEFAULT values, can be overridden per-server
EMOJI_HEART = "❤️"  # Used for displaying player lives
EMOJI_SKULL = "💀"  # Used for game over display

# Player lives configuration - DEFAULT value, can be overridden per-server
PLAYER_LIVES = 3

# Zombie movement configuration
ZOMBIE_MOVE_INTERVAL = 2  # Zombies move every N player moves (default: 2)

# Zombie count by level: (min_zombies, max_zombies)
# More zombies spawn in later levels
ZOMBIE_COUNT_BY_LEVEL = {
    1: (0, 1),   # Level 1: 0-1 zombies
    2: (1, 2),   # Level 2: 1-2 zombies
    3: (1, 3),   # Level 3: 1-3 zombies
    4: (2, 3),   # Level 4: 2-3 zombies
    5: (2, 4),   # Level 5: 2-4 zombies
}

# Default zombie count for levels beyond LEVEL_CONFIGS
DEFAULT_ZOMBIE_COUNT = (3, 5)  # 3-5 zombies for high levels

# Item types available for collection
ITEM_TYPES = {
    "diamond": EMOJI_DIAMOND,
    "wood": EMOJI_WOOD,
    "stone": EMOJI_STONE,
    "coal": EMOJI_COAL,
}

# Level configuration
# Each level has: (min_items, max_items, width, height, obstacle_count)
LEVEL_CONFIGS = {
    1: (2, 3, 8, 5, 2),   # Level 1: 2-3 items, small field
    2: (3, 4, 10, 6, 3),  # Level 2: 3-4 items, medium field
    3: (4, 5, 12, 7, 4),  # Level 3: 4-5 items, larger field
    4: (5, 6, 14, 8, 5),  # Level 4: 5-6 items, even larger
    5: (6, 7, 16, 9, 6),  # Level 5: 6-7 items, large field
}

# Default level (if level exceeds LEVEL_CONFIGS)
DEFAULT_LEVEL_CONFIG = (7, 8, 18, 10, 7)

# Join reaction emoji - DEFAULT value, can be overridden per-server
EMOJI_JOIN = "✅"

# Player emojis for multiplayer (up to 4 players) - DEFAULT values, can be overridden per-server
EMOJI_PLAYER1 = "🟢"
EMOJI_PLAYER2 = "🔵"
EMOJI_PLAYER3 = "🟡"
EMOJI_PLAYER4 = "🟣"

# Movement reaction emojis - DEFAULT values, can be overridden per-server
# Custom emojis work great for reactions!
EMOJI_UP = "⬆️"
EMOJI_DOWN = "⬇️"
EMOJI_LEFT = "⬅️"
EMOJI_RIGHT = "➡️"

# Movement directions
DIRECTION_UP = (0, -1)
DIRECTION_DOWN = (0, 1)
DIRECTION_LEFT = (-1, 0)
DIRECTION_RIGHT = (1, 0)

# Emoji to direction mapping
EMOJI_TO_DIRECTION = {
    EMOJI_UP: DIRECTION_UP,
    EMOJI_DOWN: DIRECTION_DOWN,
    EMOJI_LEFT: DIRECTION_LEFT,
    EMOJI_RIGHT: DIRECTION_RIGHT,
}

