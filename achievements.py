"""Achievement definitions and checking logic."""

from typing import Dict, Callable, List, Tuple


# Achievement structure: {"name": str, "xp_reward": int, "check": Callable[[Dict], bool]}
ACHIEVEMENTS: Dict[str, Dict] = {
    # Collection achievements
    "first_item": {
        "name": "First Collection",
        "xp_reward": 50,
        "description": "Collect your first item",
        "category": "Collection",
        "check": lambda stats: stats.get("items_collected", 0) >= 1
    },
    "collect_10": {
        "name": "Item Collector",
        "xp_reward": 100,
        "description": "Collect 10 items",
        "category": "Collection",
        "check": lambda stats: stats.get("items_collected", 0) >= 10
    },
    "collect_50": {
        "name": "Item Hoarder",
        "xp_reward": 250,
        "description": "Collect 50 items",
        "category": "Collection",
        "check": lambda stats: stats.get("items_collected", 0) >= 50
    },
    "collect_100": {
        "name": "Master Collector",
        "xp_reward": 500,
        "description": "Collect 100 items",
        "category": "Collection",
        "check": lambda stats: stats.get("items_collected", 0) >= 100
    },
    
    # Level progression achievements
    "level_3": {
        "name": "Level Explorer",
        "xp_reward": 150,
        "description": "Reach level 3",
        "category": "Level Progression",
        "check": lambda stats: stats.get("highest_level", 0) >= 3
    },
    "level_5": {
        "name": "Level Master",
        "xp_reward": 200,
        "description": "Reach level 5",
        "category": "Level Progression",
        "check": lambda stats: stats.get("highest_level", 0) >= 5
    },
    "level_10": {
        "name": "Level Champion",
        "xp_reward": 400,
        "description": "Reach level 10",
        "category": "Level Progression",
        "check": lambda stats: stats.get("highest_level", 0) >= 10
    },
    
    # Survival achievements
    "zombie_survivor": {
        "name": "Zombie Survivor",
        "xp_reward": 150,
        "description": "Complete a game without dying",
        "category": "Survival",
        "check": lambda stats: stats.get("deaths", 0) == 0 and stats.get("games_completed", 0) >= 1
    },
    "perfect_game": {
        "name": "Perfect Game",
        "xp_reward": 300,
        "description": "Complete 3 games without dying",
        "category": "Survival",
        "check": lambda stats: stats.get("deaths", 0) == 0 and stats.get("games_completed", 0) >= 3
    },
    
    # Completion achievements
    "first_win": {
        "name": "First Victory",
        "xp_reward": 100,
        "description": "Win your first level",
        "category": "Completion",
        "check": lambda stats: stats.get("wins", 0) >= 1
    },
    "win_10": {
        "name": "Victory Master",
        "xp_reward": 300,
        "description": "Win 10 levels",
        "category": "Completion",
        "check": lambda stats: stats.get("wins", 0) >= 10
    },
    "complete_5_levels": {
        "name": "Level Completer",
        "xp_reward": 200,
        "description": "Complete 5 levels",
        "category": "Completion",
        "check": lambda stats: stats.get("levels_completed", 0) >= 5
    },
    "complete_20_levels": {
        "name": "Level Expert",
        "xp_reward": 400,
        "description": "Complete 20 levels",
        "category": "Completion",
        "check": lambda stats: stats.get("levels_completed", 0) >= 20
    },
    
    # Activity achievements
    "play_5_games": {
        "name": "Dedicated Player",
        "xp_reward": 100,
        "description": "Play 5 games",
        "category": "Activity",
        "check": lambda stats: stats.get("games_played", 0) >= 5
    },
    "play_20_games": {
        "name": "Veteran Player",
        "xp_reward": 300,
        "description": "Play 20 games",
        "category": "Activity",
        "check": lambda stats: stats.get("games_played", 0) >= 20
    },
}


def check_achievements(stats: Dict[str, int], unlocked_achievements: List[str]) -> List[Tuple[str, int]]:
    """Check which achievements should be unlocked based on current stats.
    
    Args:
        stats: Current player stats dictionary
        unlocked_achievements: List of already unlocked achievement IDs
        
    Returns:
        List of (achievement_id, xp_reward) tuples for newly unlocked achievements
    """
    newly_unlocked = []
    
    for achievement_id, achievement_data in ACHIEVEMENTS.items():
        # Skip if already unlocked
        if achievement_id in unlocked_achievements:
            continue
        
        # Check if achievement condition is met
        if achievement_data["check"](stats):
            xp_reward = achievement_data.get("xp_reward", 0)
            newly_unlocked.append((achievement_id, xp_reward))
    
    return newly_unlocked


def get_achievement_info(achievement_id: str) -> Dict:
    """Get achievement information by ID.
    
    Args:
        achievement_id: ID of the achievement
        
    Returns:
        Achievement data dictionary or None if not found
    """
    return ACHIEVEMENTS.get(achievement_id)


def get_achievements_by_category() -> Dict[str, List[str]]:
    """Get all achievement IDs grouped by category.
    
    Returns:
        Dictionary mapping category names to lists of achievement IDs
    """
    categories = {}
    for achievement_id, achievement_data in ACHIEVEMENTS.items():
        category = achievement_data.get("category", "Other")
        if category not in categories:
            categories[category] = []
        categories[category].append(achievement_id)
    return categories

