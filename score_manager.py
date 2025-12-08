"""Score manager for tracking player statistics per server."""

import os
import json
import math
from typing import Dict, Optional, List, Tuple


class ScoreManager:
    """Manages player scores and statistics per server."""
    
    SCORES_DIR = "scores"
    
    # Valid stat names
    STAT_NAMES = [
        "wins",
        "highest_level",
        "items_collected",
        "games_played",
        "levels_completed",
        "games_completed",
        "deaths"
    ]
    
    def __init__(self):
        """Initialize the score manager."""
        # Ensure scores directory exists
        os.makedirs(self.SCORES_DIR, exist_ok=True)
    
    def _get_scores_path(self, guild_id: int) -> str:
        """Get the path to the scores file for a guild."""
        return os.path.join(self.SCORES_DIR, f"{guild_id}.json")
    
    def load_scores(self, guild_id: int) -> Dict[str, Dict[str, int]]:
        """Load scores for a specific server.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dictionary mapping user_id (as string) to their stats dictionary
        """
        scores_path = self._get_scores_path(guild_id)
        
        if os.path.exists(scores_path):
            try:
                with open(scores_path, 'r', encoding='utf-8') as f:
                    scores = json.load(f)
                # Ensure all stats exist for all players
                for user_id, stats in scores.items():
                    for stat_name in self.STAT_NAMES:
                        if stat_name not in stats:
                            stats[stat_name] = 0
                    # Ensure XP exists
                    if "xp" not in stats:
                        stats["xp"] = 0
                    # Ensure achievements_unlocked exists as list
                    if "achievements_unlocked" not in stats:
                        stats["achievements_unlocked"] = []
                    elif not isinstance(stats["achievements_unlocked"], list):
                        # Convert old format to list if needed
                        stats["achievements_unlocked"] = []
                return scores
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading scores for guild {guild_id}: {e}")
                return {}
        
        return {}
    
    def save_scores(self, guild_id: int, scores: Dict[str, Dict[str, int]]) -> bool:
        """Save scores for a specific server.
        
        Args:
            guild_id: Discord guild ID
            scores: Dictionary mapping user_id (as string) to their stats dictionary
            
        Returns:
            True if successful, False otherwise
        """
        scores_path = self._get_scores_path(guild_id)
        
        try:
            with open(scores_path, 'w', encoding='utf-8') as f:
                json.dump(scores, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error saving scores for guild {guild_id}: {e}")
            return False
    
    def _ensure_player_stats(self, guild_id: int, user_id: int) -> Dict[str, int]:
        """Ensure a player has all stats initialized. Returns the stats dict."""
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str not in scores:
            scores[user_id_str] = {stat: 0 for stat in self.STAT_NAMES}
            scores[user_id_str]["xp"] = 0
            scores[user_id_str]["achievements_unlocked"] = []
        else:
            # Ensure all stats exist
            for stat_name in self.STAT_NAMES:
                if stat_name not in scores[user_id_str]:
                    scores[user_id_str][stat_name] = 0
            if "xp" not in scores[user_id_str]:
                scores[user_id_str]["xp"] = 0
            if "achievements_unlocked" not in scores[user_id_str]:
                scores[user_id_str]["achievements_unlocked"] = []
            elif not isinstance(scores[user_id_str]["achievements_unlocked"], list):
                scores[user_id_str]["achievements_unlocked"] = []
        
        return scores[user_id_str]
    
    def update_player_score(self, guild_id: int, user_id: int, stat_name: str, value: int) -> bool:
        """Update a specific stat for a player.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            stat_name: Name of the stat to update
            value: New value for the stat
            
        Returns:
            True if successful, False otherwise
        """
        if stat_name not in self.STAT_NAMES:
            return False
        
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        # Ensure player exists in the scores dict
        if user_id_str not in scores:
            scores[user_id_str] = {stat: 0 for stat in self.STAT_NAMES}
        else:
            # Ensure all stats exist
            for stat in self.STAT_NAMES:
                if stat not in scores[user_id_str]:
                    scores[user_id_str][stat] = 0
        
        # Update the stat
        scores[user_id_str][stat_name] = value
        
        return self.save_scores(guild_id, scores)
    
    def increment_player_score(self, guild_id: int, user_id: int, stat_name: str, amount: int = 1) -> bool:
        """Increment a stat for a player.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            stat_name: Name of the stat to increment
            amount: Amount to increment by (default: 1)
            
        Returns:
            True if successful, False otherwise
        """
        if stat_name not in self.STAT_NAMES:
            return False
        
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        # Ensure player exists in the scores dict
        if user_id_str not in scores:
            scores[user_id_str] = {stat: 0 for stat in self.STAT_NAMES}
        else:
            # Ensure all stats exist
            for stat in self.STAT_NAMES:
                if stat not in scores[user_id_str]:
                    scores[user_id_str][stat] = 0
        
        # Increment the stat
        current_value = scores[user_id_str].get(stat_name, 0)
        scores[user_id_str][stat_name] = current_value + amount
        
        return self.save_scores(guild_id, scores)
    
    def get_player_stats(self, guild_id: int, user_id: int) -> Dict[str, int]:
        """Get all stats for a player.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            Dictionary of stat names to values
        """
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str in scores:
            return scores[user_id_str].copy()
        else:
            # Return default stats
            return {stat: 0 for stat in self.STAT_NAMES}
    
    def get_leaderboard(self, guild_id: int, stat_name: str, limit: int = 10) -> List[Tuple[int, int]]:
        """Get top N players for a stat.
        
        Args:
            guild_id: Discord guild ID
            stat_name: Name of the stat to rank by
            limit: Maximum number of players to return
            
        Returns:
            List of tuples (user_id, stat_value) sorted by stat_value descending
        """
        if stat_name not in self.STAT_NAMES:
            return []
        
        scores = self.load_scores(guild_id)
        
        # Build list of (user_id, stat_value) tuples
        leaderboard = []
        for user_id_str, stats in scores.items():
            user_id = int(user_id_str)
            stat_value = stats.get(stat_name, 0)
            leaderboard.append((user_id, stat_value))
        
        # Sort by stat value descending
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        
        # Return top N
        return leaderboard[:limit]
    
    def get_player_rank(self, guild_id: int, user_id: int, stat_name: str) -> Optional[int]:
        """Get a player's rank for a stat (1-based, None if not found).
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            stat_name: Name of the stat to rank by
            
        Returns:
            Rank (1-based) or None if player not found
        """
        if stat_name not in self.STAT_NAMES:
            return None
        
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str not in scores:
            return None
        
        # Get all players sorted by stat value
        leaderboard = self.get_leaderboard(guild_id, stat_name, limit=10000)  # Get all
        
        # Find player's rank
        for rank, (uid, _) in enumerate(leaderboard, start=1):
            if uid == user_id:
                return rank
        
        return None
    
    def award_xp(self, guild_id: int, user_id: int, amount: int) -> bool:
        """Award XP to a player and check for level ups.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            amount: Amount of XP to award
            
        Returns:
            True if successful, False otherwise
        """
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        # Ensure player exists
        if user_id_str not in scores:
            scores[user_id_str] = {stat: 0 for stat in self.STAT_NAMES}
            scores[user_id_str]["xp"] = 0
            scores[user_id_str]["achievements_unlocked"] = []
        else:
            # Ensure XP exists
            if "xp" not in scores[user_id_str]:
                scores[user_id_str]["xp"] = 0
        
        # Award XP
        old_level = self.get_player_level(guild_id, user_id)
        scores[user_id_str]["xp"] = scores[user_id_str].get("xp", 0) + amount
        new_level = self.get_player_level(guild_id, user_id)
        
        # Save scores
        success = self.save_scores(guild_id, scores)
        
        # Return True if level up occurred
        return success
    
    def get_player_level(self, guild_id: int, user_id: int) -> int:
        """Calculate player level from XP.
        
        Formula: level = int(sqrt(xp / 100)) + 1
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            Player level (minimum 1)
        """
        stats = self.get_player_stats(guild_id, user_id)
        xp = stats.get("xp", 0)
        if xp <= 0:
            return 1
        level = int(math.sqrt(xp / 100)) + 1
        return max(1, level)
    
    def get_achievements(self, guild_id: int, user_id: int) -> List[str]:
        """Get list of unlocked achievement IDs for a player.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            
        Returns:
            List of achievement IDs
        """
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str in scores:
            achievements = scores[user_id_str].get("achievements_unlocked", [])
            if isinstance(achievements, list):
                return achievements.copy()
            return []
        return []
    
    def unlock_achievement(self, guild_id: int, user_id: int, achievement_id: str, xp_reward: int = 0) -> bool:
        """Unlock an achievement for a player and award bonus XP.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            achievement_id: ID of the achievement to unlock
            xp_reward: XP reward for unlocking this achievement
            
        Returns:
            True if achievement was newly unlocked, False if already unlocked
        """
        scores = self.load_scores(guild_id)
        user_id_str = str(user_id)
        
        # Ensure player exists
        if user_id_str not in scores:
            scores[user_id_str] = {stat: 0 for stat in self.STAT_NAMES}
            scores[user_id_str]["xp"] = 0
            scores[user_id_str]["achievements_unlocked"] = []
        else:
            if "achievements_unlocked" not in scores[user_id_str]:
                scores[user_id_str]["achievements_unlocked"] = []
            elif not isinstance(scores[user_id_str]["achievements_unlocked"], list):
                scores[user_id_str]["achievements_unlocked"] = []
        
        # Check if already unlocked
        if achievement_id in scores[user_id_str]["achievements_unlocked"]:
            return False
        
        # Unlock achievement
        scores[user_id_str]["achievements_unlocked"].append(achievement_id)
        
        # Award XP reward
        if xp_reward > 0:
            if "xp" not in scores[user_id_str]:
                scores[user_id_str]["xp"] = 0
            scores[user_id_str]["xp"] += xp_reward
        
        return self.save_scores(guild_id, scores)
    
    def check_achievements(self, guild_id: int, user_id: int, stats: Dict[str, int]) -> List[Tuple[str, int]]:
        """Check if any achievements should be unlocked based on current stats.
        
        This method should be called with an achievements module that defines achievement checks.
        Returns list of (achievement_id, xp_reward) tuples for newly unlocked achievements.
        
        Args:
            guild_id: Discord guild ID
            user_id: Discord user ID
            stats: Current player stats dictionary
            
        Returns:
            List of (achievement_id, xp_reward) tuples for newly unlocked achievements
        """
        # This will be called from bot.py with the achievements module
        # For now, return empty list - actual checking happens in bot.py
        return []

