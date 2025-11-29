"""Score manager for tracking player statistics per server."""

import os
import json
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
        else:
            # Ensure all stats exist
            for stat_name in self.STAT_NAMES:
                if stat_name not in scores[user_id_str]:
                    scores[user_id_str][stat_name] = 0
        
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

