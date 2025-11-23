"""Game logic for the text-based movement game."""

import random
from typing import Tuple, Set, Dict, Optional, List
from config import (
    OBSTACLE_COUNT,
    EMOJI_WALL,
    EMOJI_OBSTACLE,
    EMOJI_EMPTY,
    EMOJI_PLAYER,
    EMOJI_PORTAL,
    EMOJI_ZOMBIE,
    ITEM_TYPES,
    LEVEL_CONFIGS,
    DEFAULT_LEVEL_CONFIG,
    PLAYER_LIVES,
    ZOMBIE_MOVE_INTERVAL,
    ZOMBIE_COUNT_BY_LEVEL,
    DEFAULT_ZOMBIE_COUNT,
)

# Default player emojis (fallback if not configured)
DEFAULT_PLAYER_EMOJIS = ["🟢", "🔵", "🟡", "🟣"]


class Game:
    """Manages a single game instance for multiple players."""
    
    def __init__(self, level: int = 1, player_lives: Optional[int] = None, emojis: Optional[Dict[str, str]] = None, item_types: Optional[Dict[str, str]] = None, first_player_id: Optional[int] = None, player_emojis: Optional[List[str]] = None):
        """Initialize a new game for the specified level.
        
        Args:
            level: The level number
            player_lives: Optional number of lives (defaults to PLAYER_LIVES)
            emojis: Optional dict of emoji names to emoji strings (defaults to config.py values)
            item_types: Optional dict of item type names to emoji strings (defaults to config.py values)
            first_player_id: Optional user_id of the first player (if None, game starts empty)
            player_emojis: Optional list of player emojis (defaults to DEFAULT_PLAYER_EMOJIS)
        """
        self.level = level
        
        # Set player emojis (use provided or defaults)
        if player_emojis is None:
            self.player_emojis_list = DEFAULT_PLAYER_EMOJIS.copy()
        else:
            self.player_emojis_list = player_emojis.copy() if len(player_emojis) > 0 else DEFAULT_PLAYER_EMOJIS.copy()
        
        # Set emojis (use provided or defaults)
        if emojis is None:
            self.emojis = {
                "wall": EMOJI_WALL,
                "obstacle": EMOJI_OBSTACLE,
                "empty": EMOJI_EMPTY,
                "player": EMOJI_PLAYER,
                "portal": EMOJI_PORTAL,
                "zombie": EMOJI_ZOMBIE,
            }
        else:
            self.emojis = emojis.copy()
        
        # Set item types (use provided or defaults)
        if item_types is None:
            self.item_types = ITEM_TYPES.copy()
        else:
            self.item_types = item_types.copy()
        
        # Get level configuration
        if level in LEVEL_CONFIGS:
            min_items, max_items, width, height, obstacle_count = LEVEL_CONFIGS[level]
        else:
            min_items, max_items, width, height, obstacle_count = DEFAULT_LEVEL_CONFIG
        
        # Dynamically cap field size based on emoji length to prevent exceeding Discord's 4096 char limit
        # Estimate average emoji length (custom emojis are ~22 chars, Unicode are ~2 chars)
        avg_emoji_length = 2  # Default to Unicode
        emoji_lengths = [len(e) for e in self.emojis.values()]
        emoji_lengths.extend([len(e) for e in self.item_types.values()])
        if emoji_lengths:
            avg_emoji_length = sum(emoji_lengths) / len(emoji_lengths)
        
        # Calculate max safe field size
        # Formula: (width + 2) * (height + 2) * avg_emoji_length + (height + 2) newlines < 4000
        # Leave ~500 chars for other embed content (title, fields, etc.)
        MAX_SAFE_LENGTH = 3500
        max_cells = int(MAX_SAFE_LENGTH / avg_emoji_length)
        
        # Calculate max dimensions (accounting for walls: width+2, height+2)
        # Approximate: (width+2) * (height+2) <= max_cells
        # For square-ish fields: max_dimension ≈ sqrt(max_cells) - 2
        max_dimension = int((max_cells ** 0.5) - 2)
        
        # Cap width and height if they exceed the limit
        if width > max_dimension:
            width = max_dimension
        if height > max_dimension:
            height = max_dimension
        
        # Ensure minimum size
        width = max(5, width)
        height = max(3, height)
        
        self.width = width
        self.height = height
        self.obstacle_count = obstacle_count
        self.required_items_count = random.randint(min_items, max_items)
        
        # Generate obstacles
        self.obstacles: Set[Tuple[int, int]] = self._generate_obstacles()
        
        # Multiplayer structures
        self.players: List[int] = []  # Track player order
        self.player_positions: Dict[int, Tuple[int, int]] = {}  # user_id -> position
        self.collected_items: Dict[int, Dict[str, int]] = {}  # user_id -> {item_type: count}
        self.player_lives: Dict[int, int] = {}  # user_id -> lives
        self.player_emojis: Dict[int, str] = {}  # user_id -> emoji
        self.player_wins: Dict[int, int] = {}  # user_id -> win count
        self.winner: Optional[int] = None  # user_id of winner
        
        # Generate collectible items (before placing players)
        self.items: Dict[Tuple[int, int], str] = {}
        
        # Generate portal (crafting table)
        self.portal_pos: Optional[Tuple[int, int]] = None
        
        # Track if level is complete
        self.level_complete = False
        
        # Zombie tracking
        self.zombies: List[Tuple[int, int]] = []
        self.zombie_move_counter = 0
        
        # Game over flag
        self.game_over = False
        
        # Generate items and portal first (before placing players)
        self.items = self._generate_items()
        self.portal_pos = self._generate_portal()
        
        # Add first player if provided
        if first_player_id is not None:
            self.add_player(first_player_id, player_lives if player_lives is not None else PLAYER_LIVES)
        
        # Generate zombies (after players are placed)
        self.zombies = self._generate_zombies()
    
    def _generate_obstacles(self) -> Set[Tuple[int, int]]:
        """Generate random obstacles, ensuring they don't overlap."""
        obstacles = set()
        max_attempts = 100
        
        while len(obstacles) < self.obstacle_count and max_attempts > 0:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            obstacles.add((x, y))
            max_attempts -= 1
        
        return obstacles
    
    def _generate_start_position(self, exclude_positions: Optional[Set[Tuple[int, int]]] = None) -> Optional[Tuple[int, int]]:
        """Generate a starting position that's not on an obstacle or excluded positions.
        
        Args:
            exclude_positions: Set of positions to exclude (other players, items, portal, etc.)
        
        Returns:
            Tuple of (x, y) position or None if no valid position found
        """
        if exclude_positions is None:
            exclude_positions = set()
        
        blocked = set(self.obstacles) | exclude_positions
        max_attempts = 200
        
        for _ in range(max_attempts):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            pos = (x, y)
            if pos not in blocked:
                return pos
        
        # If random failed, try all positions systematically
        for y in range(self.height):
            for x in range(self.width):
                pos = (x, y)
                if pos not in blocked:
                    return pos
        
        return None
    
    def _generate_items(self) -> Dict[Tuple[int, int], str]:
        """Generate collectible items randomly on the field."""
        items = {}
        item_types_list = list(self.item_types.keys())
        max_attempts = 200
        
        # Generate more items than required to give players choice
        items_to_generate = self.required_items_count + random.randint(2, 4)
        
        attempts = 0
        while len(items) < items_to_generate and attempts < max_attempts:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            pos = (x, y)
            
            # Don't place on obstacles or player positions
            blocked = set(self.obstacles) | set(self.player_positions.values())
            if pos not in blocked:
                # Randomly select an item type
                item_type = random.choice(item_types_list)
                items[pos] = item_type
            attempts += 1
        
        return items
    
    def _generate_portal(self) -> Optional[Tuple[int, int]]:
        """Generate portal position that's not on obstacles, player positions, or items."""
        # First try random positions
        max_attempts = 100
        attempts = 0
        
        blocked = set(self.obstacles) | set(self.player_positions.values()) | set(self.items.keys())
        
        while attempts < max_attempts:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            pos = (x, y)
            
            # Don't place on obstacles, player positions, or items
            if pos not in blocked:
                return pos
            attempts += 1
        
        # If random failed, try all positions systematically
        for y in range(self.height):
            for x in range(self.width):
                pos = (x, y)
                if pos not in blocked:
                    return pos
        
        # If still no position found, return None (shouldn't happen in normal cases)
        return None
    
    def _generate_zombies(self) -> List[Tuple[int, int]]:
        """Generate zombies randomly on the field, avoiding obstacles, player positions, items, and portal."""
        zombies = []
        
        # Get zombie count for this level
        if self.level in ZOMBIE_COUNT_BY_LEVEL:
            min_zombies, max_zombies = ZOMBIE_COUNT_BY_LEVEL[self.level]
        else:
            min_zombies, max_zombies = DEFAULT_ZOMBIE_COUNT
        
        zombie_count = random.randint(min_zombies, max_zombies)
        
        # Collect all blocked positions
        blocked_positions = set(self.obstacles)
        blocked_positions.update(self.player_positions.values())
        blocked_positions.update(self.items.keys())
        if self.portal_pos is not None:
            blocked_positions.add(self.portal_pos)
        
        max_attempts = 200
        attempts = 0
        
        while len(zombies) < zombie_count and attempts < max_attempts:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            pos = (x, y)
            
            # Don't place on blocked positions
            if pos not in blocked_positions:
                zombies.append(pos)
                blocked_positions.add(pos)  # Prevent multiple zombies on same spot initially
            attempts += 1
        
        return zombies
    
    def _can_zombie_move(self, zombie_pos: Tuple[int, int], dx: int, dy: int) -> bool:
        """Check if a zombie can move in the given direction."""
        new_x = zombie_pos[0] + dx
        new_y = zombie_pos[1] + dy
        
        # Check boundaries
        if new_x < 0 or new_x >= self.width or new_y < 0 or new_y >= self.height:
            return False
        
        # Check obstacles (zombies cannot move through obstacles)
        if (new_x, new_y) in self.obstacles:
            return False
        
        return True
    
    def _move_zombies(self) -> None:
        """Move all zombies using weighted random movement toward the nearest player."""
        from config import DIRECTION_UP, DIRECTION_DOWN, DIRECTION_LEFT, DIRECTION_RIGHT
        
        if not self.player_positions:
            return  # No players to target
        
        new_zombie_positions = []
        
        for zombie_pos in self.zombies:
            # Find nearest player
            nearest_player_pos = None
            min_distance = float('inf')
            
            for player_pos in self.player_positions.values():
                dx_to_player = player_pos[0] - zombie_pos[0]
                dy_to_player = player_pos[1] - zombie_pos[1]
                distance = abs(dx_to_player) + abs(dy_to_player)
                if distance < min_distance:
                    min_distance = distance
                    nearest_player_pos = player_pos
            
            if nearest_player_pos is None:
                # No players, stay in place
                new_zombie_positions.append(zombie_pos)
                continue
            
            # Calculate distance to nearest player
            dx_to_player = nearest_player_pos[0] - zombie_pos[0]
            dy_to_player = nearest_player_pos[1] - zombie_pos[1]
            
            # Get all possible moves
            possible_moves = []
            move_weights = []
            
            directions = [
                (DIRECTION_UP[0], DIRECTION_UP[1], "up"),
                (DIRECTION_DOWN[0], DIRECTION_DOWN[1], "down"),
                (DIRECTION_LEFT[0], DIRECTION_LEFT[1], "left"),
                (DIRECTION_RIGHT[0], DIRECTION_RIGHT[1], "right"),
            ]
            
            for dx, dy, name in directions:
                if self._can_zombie_move(zombie_pos, dx, dy):
                    new_pos = (zombie_pos[0] + dx, zombie_pos[1] + dy)
                    # Calculate new distance to nearest player
                    new_dx = nearest_player_pos[0] - new_pos[0]
                    new_dy = nearest_player_pos[1] - new_pos[1]
                    old_distance = abs(dx_to_player) + abs(dy_to_player)
                    new_distance = abs(new_dx) + abs(new_dy)
                    
                    # Weight: moves that reduce distance get higher weight
                    # Moves that increase distance get lower weight
                    # Moves that keep same distance get medium weight
                    if new_distance < old_distance:
                        weight = 3  # Prefer moves toward player
                    elif new_distance == old_distance:
                        weight = 1  # Neutral moves
                    else:
                        weight = 0.5  # Discourage moves away from player
                    
                    possible_moves.append((dx, dy))
                    move_weights.append(weight)
            
            # If no valid moves, stay in place
            if not possible_moves:
                new_zombie_positions.append(zombie_pos)
                continue
            
            # Weighted random selection
            if sum(move_weights) > 0:
                chosen_move = random.choices(possible_moves, weights=move_weights, k=1)[0]
            else:
                # Fallback to random if all weights are 0 (shouldn't happen)
                chosen_move = random.choice(possible_moves)
            
            # Apply the move
            new_pos = (zombie_pos[0] + chosen_move[0], zombie_pos[1] + chosen_move[1])
            new_zombie_positions.append(new_pos)
        
        self.zombies = new_zombie_positions
    
    def _check_zombie_collision(self) -> None:
        """Check if any player collides with any zombie and handle life loss/game over."""
        # Check each player for zombie collisions
        for user_id, player_pos in list(self.player_positions.items()):
            if player_pos in self.zombies:
                # Collision detected - reduce lives
                self.player_lives[user_id] -= 1
                
                # Remove all zombies at player's position to prevent immediate re-kill
                self.zombies = [z for z in self.zombies if z != player_pos]
                
                # Check if player is out of lives
                if self.player_lives[user_id] <= 0:
                    # Remove player from game
                    self.remove_player(user_id)
        
        # Game over if no players remain
        if not self.player_positions:
            self.game_over = True
    
    def can_move(self, user_id: int, dx: int, dy: int) -> bool:
        """Check if the player can move in the given direction."""
        if user_id not in self.player_positions:
            return False
        
        player_pos = self.player_positions[user_id]
        new_x = player_pos[0] + dx
        new_y = player_pos[1] + dy
        
        # Check boundaries
        if new_x < 0 or new_x >= self.width or new_y < 0 or new_y >= self.height:
            return False
        
        # Check obstacles
        if (new_x, new_y) in self.obstacles:
            return False
        
        # Check if position is occupied by another player
        new_pos = (new_x, new_y)
        for other_user_id, other_pos in self.player_positions.items():
            if other_user_id != user_id and other_pos == new_pos:
                return False
        
        return True
    
    def move(self, user_id: int, dx: int, dy: int) -> bool:
        """Move the player in the given direction. Returns True if move was successful."""
        # Don't allow moves if game is over or player doesn't exist
        if self.game_over or user_id not in self.player_positions:
            return False
        
        if self.can_move(user_id, dx, dy):
            player_pos = self.player_positions[user_id]
            new_pos = (player_pos[0] + dx, player_pos[1] + dy)
            self.player_positions[user_id] = new_pos
            
            # Check if player collected an item
            if new_pos in self.items:
                item_type = self.items[new_pos]
                if user_id not in self.collected_items:
                    self.collected_items[user_id] = {item_type: 0 for item_type in self.item_types.keys()}
                self.collected_items[user_id][item_type] += 1
                del self.items[new_pos]
            
            # Check if player reached portal (and has required items)
            if self.portal_pos is not None and new_pos == self.portal_pos and self.can_reach_portal(user_id):
                # First player to complete wins the level
                if self.winner is None:
                    self.winner = user_id
                    self.level_complete = True
                    # Increment win count for the winner
                    if user_id not in self.player_wins:
                        self.player_wins[user_id] = 0
                    self.player_wins[user_id] += 1
            
            # Check for zombie collisions after player move
            self._check_zombie_collision()
            
            # Increment zombie move counter
            self.zombie_move_counter += 1
            
            # Move zombies every ZOMBIE_MOVE_INTERVAL moves
            if self.zombie_move_counter >= ZOMBIE_MOVE_INTERVAL:
                self._move_zombies()
                self.zombie_move_counter = 0
                
                # Check for zombie collisions after zombie movement
                self._check_zombie_collision()
            
            return True
        return False
    
    def add_player(self, user_id: int, player_lives: Optional[int] = None) -> bool:
        """Add a new player to the game.
        
        Args:
            user_id: Discord user ID
            player_lives: Number of lives (defaults to PLAYER_LIVES)
        
        Returns:
            True if player was added successfully, False otherwise
        """
        if user_id in self.player_positions:
            return False  # Player already in game
        
        # Assign emoji based on join order (cycles through configured player emojis)
        emoji_index = len(self.players) % len(self.player_emojis_list)
        emoji = self.player_emojis_list[emoji_index]
        
        # Generate starting position (avoid obstacles, other players, items, portal)
        exclude_positions = set(self.player_positions.values()) | set(self.items.keys())
        if self.portal_pos is not None:
            exclude_positions.add(self.portal_pos)
        
        start_pos = self._generate_start_position(exclude_positions)
        if start_pos is None:
            return False  # Could not find valid starting position
        
        # Add player
        self.players.append(user_id)
        self.player_positions[user_id] = start_pos
        self.player_emojis[user_id] = emoji
        self.player_lives[user_id] = player_lives if player_lives is not None else PLAYER_LIVES
        self.collected_items[user_id] = {item_type: 0 for item_type in self.item_types.keys()}
        # Initialize wins if not already set (for new players)
        if user_id not in self.player_wins:
            self.player_wins[user_id] = 0
        
        return True
    
    def remove_player(self, user_id: int) -> None:
        """Remove a player from the game."""
        if user_id in self.player_positions:
            del self.player_positions[user_id]
            if user_id in self.collected_items:
                del self.collected_items[user_id]
            if user_id in self.player_lives:
                del self.player_lives[user_id]
            if user_id in self.player_emojis:
                del self.player_emojis[user_id]
            if user_id in self.players:
                self.players.remove(user_id)
            # Note: Keep player_wins even if player is removed (for stats)
    
    def get_player_wins(self, user_id: int) -> int:
        """Get win count for a player."""
        return self.player_wins.get(user_id, 0)
    
    @classmethod
    def create_next_level(cls, previous_game: 'Game') -> 'Game':
        """Create a new game instance for the next level, preserving player data.
        
        Args:
            previous_game: The previous game instance
        
        Returns:
            New Game instance for the next level
        """
        next_level = previous_game.level + 1
        
        # Create new game with same emojis and item types
        new_game = cls(
            level=next_level,
            player_lives=None,  # Will be set per player
            emojis=previous_game.emojis.copy(),
            item_types=previous_game.item_types.copy(),
            first_player_id=None,  # Will add all players manually
            player_emojis=previous_game.player_emojis_list.copy()  # Preserve player emoji configuration
        )
        
        # Preserve player data: emojis, lives, wins
        for user_id in previous_game.players:
            # Preserve emoji assignment
            new_game.player_emojis[user_id] = previous_game.player_emojis[user_id]
            # Preserve lives
            new_game.player_lives[user_id] = previous_game.player_lives[user_id]
            # Preserve wins
            new_game.player_wins[user_id] = previous_game.player_wins[user_id]
            # Reset inventory for new level
            new_game.collected_items[user_id] = {item_type: 0 for item_type in new_game.item_types.keys()}
            # Add to players list
            new_game.players.append(user_id)
        
        # Generate starting positions for all players
        exclude_positions = set(new_game.items.keys())
        if new_game.portal_pos is not None:
            exclude_positions.add(new_game.portal_pos)
        
        for user_id in new_game.players:
            start_pos = new_game._generate_start_position(exclude_positions)
            if start_pos is not None:
                new_game.player_positions[user_id] = start_pos
                exclude_positions.add(start_pos)  # Prevent other players from spawning here
        
        # Reset level completion state
        new_game.level_complete = False
        new_game.winner = None
        new_game.game_over = False
        new_game.zombie_move_counter = 0
        
        # Regenerate zombies for new level
        new_game.zombies = new_game._generate_zombies()
        
        return new_game
    
    def get_player_emoji(self, user_id: int) -> Optional[str]:
        """Get the emoji for a player."""
        return self.player_emojis.get(user_id)
    
    def can_reach_portal(self, user_id: int) -> bool:
        """Check if player has collected enough items to use the portal."""
        if user_id not in self.collected_items:
            return False
        total_collected = sum(self.collected_items[user_id].values())
        return total_collected >= self.required_items_count
    
    def is_level_complete(self) -> bool:
        """Check if the level is complete."""
        return self.level_complete
    
    def get_inventory(self, user_id: int) -> Dict[str, int]:
        """Get current inventory for a player."""
        if user_id not in self.collected_items:
            return {}
        return self.collected_items[user_id].copy()
    
    def get_total_collected(self, user_id: int) -> int:
        """Get total number of items collected by a player."""
        if user_id not in self.collected_items:
            return 0
        return sum(self.collected_items[user_id].values())
    
    def render(self) -> str:
        """Render the game field as a string using emojis."""
        lines = []
        
        # Convert zombies list to set for faster membership checking
        zombie_positions = set(self.zombies)
        
        # Create position to player emoji mapping
        position_to_player_emoji = {pos: emoji for pos, emoji in 
                                    zip(self.player_positions.values(), 
                                        [self.player_emojis[uid] for uid in self.player_positions.keys()])}
        
        # Top wall
        lines.append(self.emojis["wall"] * (self.width + 2))
        
        # Game field
        for y in range(self.height):
            line = self.emojis["wall"]  # Left wall
            for x in range(self.width):
                pos = (x, y)
                # Rendering priority: players > portal > zombies > items > obstacles > empty
                if pos in position_to_player_emoji:
                    # Show player with their emoji
                    line += position_to_player_emoji[pos]
                elif self.portal_pos is not None and pos == self.portal_pos:
                    # Show portal only if at least one player can reach it
                    can_any_reach = any(self.can_reach_portal(uid) for uid in self.player_positions.keys())
                    if can_any_reach:
                        line += self.emojis["portal"]
                    else:
                        # Show as empty if portal not active yet
                        line += self.emojis["empty"]
                elif pos in zombie_positions:
                    line += self.emojis["zombie"]
                elif pos in self.items:
                    # Show item emoji
                    item_type = self.items[pos]
                    line += self.item_types[item_type]
                elif pos in self.obstacles:
                    line += self.emojis["obstacle"]
                else:
                    line += self.emojis["empty"]
            line += self.emojis["wall"]  # Right wall
            lines.append(line)
        
        # Bottom wall
        lines.append(self.emojis["wall"] * (self.width + 2))
        
        return "\n".join(lines)

