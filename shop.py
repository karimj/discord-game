"""Shop system for purchasing power-ups with XP."""

import os
import json
from typing import Dict, Optional, Tuple


# Shop items definition
SHOP_ITEMS = {
    "shield": {
        "name": "Shield",
        "cost": 500,
        "emoji": "🛡️",
        "description": "Blocks one zombie hit",
        "max_stack": 10  # Maximum number that can be owned
    },
    "extra_heart": {
        "name": "Extra Heart",
        "cost": 750,
        "emoji": "💚",
        "description": "Adds +1 life to your current lives",
        "max_stack": 5
    },
    "speed_boost": {
        "name": "Speed Boost",
        "cost": 1000,
        "emoji": "⚡",
        "description": "Move twice per reaction for 5 moves",
        "max_stack": 5
    },
}


class ShopManager:
    """Manages shop purchases and player inventories."""
    
    INVENTORIES_DIR = "inventories"
    
    def __init__(self):
        """Initialize the shop manager."""
        # Ensure inventories directory exists
        os.makedirs(self.INVENTORIES_DIR, exist_ok=True)
    
    def _get_inventory_path(self, guild_id: int) -> str:
        """Get the path to the inventory file for a guild."""
        return os.path.join(self.INVENTORIES_DIR, f"{guild_id}.json")
    
    def load_inventory(self, guild_id: int) -> Dict[str, Dict[str, int]]:
        """Load inventory for a specific server.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary mapping user_id (as string) to their inventory dictionary
        """
        inventory_path = self._get_inventory_path(guild_id)
        
        if os.path.exists(inventory_path):
            try:
                with open(inventory_path, 'r', encoding='utf-8') as f:
                    inventory = json.load(f)
                return inventory
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading inventory for guild {guild_id}: {e}")
                return {}
        
        return {}
    
    def save_inventory(self, guild_id: int, inventory: Dict[str, Dict[str, int]]) -> bool:
        """Save inventory for a specific server.
        
        Args:
            guild_id: Discord guild ID
            inventory: Dictionary mapping user_id (as string) to their inventory dictionary
            
        Returns:
            True if successful, False otherwise
        """
        inventory_path = self._get_inventory_path(guild_id)
        
        try:
            with open(inventory_path, 'w', encoding='utf-8') as f:
                json.dump(inventory, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving inventory for guild {guild_id}: {e}")
            return False
    
    def get_shop_items(self) -> Dict[str, Dict]:
        """Get all available shop items.
        
        Returns:
            Dictionary of shop items
        """
        return SHOP_ITEMS.copy()
    
    def get_player_inventory(self, guild_id: int, user_id: int) -> Dict[str, int]:
        """Get purchased items count for a player.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            Dictionary mapping item_id to count
        """
        inventory = self.load_inventory(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str in inventory:
            return inventory[user_id_str].copy()
        return {}
    
    def purchase_item(self, guild_id: int, user_id: int, item_id: str, player_xp: int) -> Tuple[bool, str]:
        """Purchase an item from the shop.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            item_id: ID of the item to purchase
            player_xp: Current XP of the player
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Check if item exists
        if item_id not in SHOP_ITEMS:
            return False, "Item not found in shop."
        
        item_data = SHOP_ITEMS[item_id]
        cost = item_data["cost"]
        
        # Check if player has enough XP
        if player_xp < cost:
            return False, f"Insufficient XP. You need {cost} XP but only have {player_xp} XP."
        
        # Load inventory
        inventory = self.load_inventory(guild_id)
        user_id_str = str(user_id)
        
        # Initialize player inventory if needed
        if user_id_str not in inventory:
            inventory[user_id_str] = {}
        
        # Check max stack
        current_count = inventory[user_id_str].get(item_id, 0)
        max_stack = item_data.get("max_stack", 999)
        if current_count >= max_stack:
            return False, f"You already own the maximum number of {item_data['name']} ({max_stack})."
        
        # Add item to inventory
        inventory[user_id_str][item_id] = current_count + 1
        
        # Save inventory
        if self.save_inventory(guild_id, inventory):
            return True, f"Successfully purchased {item_data['name']} for {cost} XP!"
        else:
            return False, "Failed to save purchase. Please try again."
    
    def use_item(self, guild_id: int, user_id: int, item_id: str) -> bool:
        """Consume one item from player inventory.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            item_id: ID of the item to use
            
        Returns:
            True if item was consumed, False if player doesn't have the item
        """
        inventory = self.load_inventory(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str not in inventory:
            return False
        
        current_count = inventory[user_id_str].get(item_id, 0)
        if current_count <= 0:
            return False
        
        # Consume one item
        inventory[user_id_str][item_id] = current_count - 1
        
        # Remove key if count reaches 0
        if inventory[user_id_str][item_id] == 0:
            del inventory[user_id_str][item_id]
        
        return self.save_inventory(guild_id, inventory)
    
    def has_item(self, guild_id: int, user_id: int, item_id: str) -> bool:
        """Check if player has at least one of an item.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            item_id: ID of the item to check
            
        Returns:
            True if player has the item, False otherwise
        """
        inventory = self.get_player_inventory(guild_id, user_id)
        return inventory.get(item_id, 0) > 0

