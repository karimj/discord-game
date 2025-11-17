"""Configuration manager for server-specific emoji settings."""

import os
import json
from typing import Dict, Optional
from config import (
    EMOJI_WALL,
    EMOJI_OBSTACLE,
    EMOJI_EMPTY,
    EMOJI_PLAYER,
    EMOJI_PORTAL,
    EMOJI_ZOMBIE,
    EMOJI_DIAMOND,
    EMOJI_WOOD,
    EMOJI_STONE,
    EMOJI_COAL,
    EMOJI_UP,
    EMOJI_DOWN,
    EMOJI_LEFT,
    EMOJI_RIGHT,
    EMOJI_HEART,
    EMOJI_SKULL,
    ITEM_TYPES,
    PLAYER_LIVES,
)


class ConfigManager:
    """Manages server-specific emoji configurations."""
    
    CONFIGS_DIR = "configs"
    
    def __init__(self):
        """Initialize the config manager."""
        # Ensure configs directory exists
        os.makedirs(self.CONFIGS_DIR, exist_ok=True)
    
    def get_default_emojis(self) -> Dict[str, str]:
        """Get default emoji configuration from config.py."""
        return {
            "wall": EMOJI_WALL,
            "obstacle": EMOJI_OBSTACLE,
            "empty": EMOJI_EMPTY,
            "player": EMOJI_PLAYER,
            "portal": EMOJI_PORTAL,
            "zombie": EMOJI_ZOMBIE,
            "diamond": EMOJI_DIAMOND,
            "wood": EMOJI_WOOD,
            "stone": EMOJI_STONE,
            "coal": EMOJI_COAL,
            "up": EMOJI_UP,
            "down": EMOJI_DOWN,
            "left": EMOJI_LEFT,
            "right": EMOJI_RIGHT,
            "heart": EMOJI_HEART,
            "skull": EMOJI_SKULL,
        }
    
    def get_default_item_types(self) -> Dict[str, str]:
        """Get default item types mapping."""
        return ITEM_TYPES.copy()
    
    def get_default_config(self) -> Dict:
        """Get default configuration including emojis and game settings."""
        config = self.get_default_emojis()
        config.update({
            "player_lives": PLAYER_LIVES,
        })
        return config
    
    def load_config(self, guild_id: int) -> Dict:
        """Load configuration for a specific server, fallback to defaults."""
        config_path = os.path.join(self.CONFIGS_DIR, f"{guild_id}.json")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # Merge with defaults to ensure all keys exist
                default_config = self.get_default_config()
                default_config.update(config)
                return default_config
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config for guild {guild_id}: {e}")
                return self.get_default_config()
        
        return self.get_default_config()
    
    def save_config(self, guild_id: int, config: Dict[str, str]) -> bool:
        """Save configuration for a specific server."""
        config_path = os.path.join(self.CONFIGS_DIR, f"{guild_id}.json")
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving config for guild {guild_id}: {e}")
            return False
    
    def get_emojis(self, guild_id: int) -> Dict[str, str]:
        """Get emojis for a server (loads from file or returns defaults)."""
        config = self.load_config(guild_id)
        # Return only emoji keys
        emoji_keys = ["wall", "obstacle", "empty", "player", "portal", "zombie", 
                      "diamond", "wood", "stone", "coal", "up", "down", "left", "right",
                      "heart", "skull"]
        return {k: config.get(k, "") for k in emoji_keys if k in config}
    
    def get_game_settings(self, guild_id: int) -> Dict[str, int]:
        """Get game settings (player_lives) for a server."""
        config = self.load_config(guild_id)
        return {
            "player_lives": int(config.get("player_lives", PLAYER_LIVES)),
        }
    
    def update_emoji(self, guild_id: int, emoji_key: str, emoji_value: str) -> bool:
        """Update a single emoji for a server."""
        config = self.load_config(guild_id)
        config[emoji_key] = emoji_value
        return self.save_config(guild_id, config)
    
    def update_setting(self, guild_id: int, setting_key: str, setting_value) -> bool:
        """Update a game setting (player_lives) for a server."""
        config = self.load_config(guild_id)
        config[setting_key] = setting_value
        return self.save_config(guild_id, config)
    
    def get_item_types(self, guild_id: int) -> Dict[str, str]:
        """Get item types mapping for a server."""
        emojis = self.get_emojis(guild_id)
        return {
            "diamond": emojis["diamond"],
            "wood": emojis["wood"],
            "stone": emojis["stone"],
            "coal": emojis["coal"],
        }
    
    def get_emoji_to_direction(self, guild_id: int) -> Dict[str, tuple]:
        """Get emoji to direction mapping for a server."""
        from config import DIRECTION_UP, DIRECTION_DOWN, DIRECTION_LEFT, DIRECTION_RIGHT
        
        emojis = self.get_emojis(guild_id)
        return {
            emojis["up"]: DIRECTION_UP,
            emojis["down"]: DIRECTION_DOWN,
            emojis["left"]: DIRECTION_LEFT,
            emojis["right"]: DIRECTION_RIGHT,
        }

