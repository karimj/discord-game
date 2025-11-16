"""Game logic for the text-based movement game."""

import random
from typing import Tuple, Set, Dict, Optional, List
from config import (
    FIELD_WIDTH,
    FIELD_HEIGHT,
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


class Game:
    """Manages a single game instance for a player."""
    
    def __init__(self, level: int = 1, player_lives: Optional[int] = None, emojis: Optional[Dict[str, str]] = None, item_types: Optional[Dict[str, str]] = None):
        """Initialize a new game for the specified level.
        
        Args:
            level: The level number
            player_lives: Optional number of lives (defaults to PLAYER_LIVES)
            emojis: Optional dict of emoji names to emoji strings (defaults to config.py values)
            item_types: Optional dict of item type names to emoji strings (defaults to config.py values)
        """
        self.level = level
        
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
        
        self.width = width
        self.height = height
        self.obstacle_count = obstacle_count
        self.required_items_count = random.randint(min_items, max_items)
        
        # Generate obstacles
        self.obstacles: Set[Tuple[int, int]] = self._generate_obstacles()
        
        # Place player at a random starting position (not on obstacle)
        self.player_pos = self._generate_start_position()
        
        # Generate collectible items
        self.items: Dict[Tuple[int, int], str] = self._generate_items()
        
        # Generate portal (crafting table)
        self.portal_pos: Optional[Tuple[int, int]] = self._generate_portal()
        
        # Track collected items
        self.collected_items: Dict[str, int] = {item_type: 0 for item_type in self.item_types.keys()}
        
        # Track if level is complete
        self.level_complete = False
        
        # Player lives (use provided value or default)
        self.player_lives = player_lives if player_lives is not None else PLAYER_LIVES
        
        # Zombie tracking
        self.zombies: List[Tuple[int, int]] = []
        self.zombie_move_counter = 0
        
        # Game over flag
        self.game_over = False
        
        # Generate zombies
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
    
    def _generate_start_position(self) -> Tuple[int, int]:
        """Generate a starting position that's not on an obstacle."""
        while True:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if (x, y) not in self.obstacles:
                return (x, y)
    
    def _generate_items(self) -> Dict[Tuple[int, int], str]:
        """Generate collectible items randomly on the field."""
        items = {}
        item_types_list = list(self.item_types.keys())
        max_attempts = 200
        
        # Generate more items than required to give player choice
        items_to_generate = self.required_items_count + random.randint(2, 4)
        
        attempts = 0
        while len(items) < items_to_generate and attempts < max_attempts:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            pos = (x, y)
            
            # Don't place on obstacles or player start
            if pos not in self.obstacles and pos != self.player_pos:
                # Randomly select an item type
                item_type = random.choice(item_types_list)
                items[pos] = item_type
            attempts += 1
        
        return items
    
    def _generate_portal(self) -> Optional[Tuple[int, int]]:
        """Generate portal position that's not on obstacles, player start, or items."""
        # First try random positions
        max_attempts = 100
        attempts = 0
        
        while attempts < max_attempts:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            pos = (x, y)
            
            # Don't place on obstacles, player start, or items
            if (pos not in self.obstacles and 
                pos != self.player_pos and 
                pos not in self.items):
                return pos
            attempts += 1
        
        # If random failed, try all positions systematically
        for y in range(self.height):
            for x in range(self.width):
                pos = (x, y)
                if (pos not in self.obstacles and 
                    pos != self.player_pos and 
                    pos not in self.items):
                    return pos
        
        # If still no position found, return None (shouldn't happen in normal cases)
        return None
    
    def _generate_zombies(self) -> List[Tuple[int, int]]:
        """Generate zombies randomly on the field, avoiding obstacles, player start, items, and portal."""
        zombies = []
        
        # Get zombie count for this level
        if self.level in ZOMBIE_COUNT_BY_LEVEL:
            min_zombies, max_zombies = ZOMBIE_COUNT_BY_LEVEL[self.level]
        else:
            min_zombies, max_zombies = DEFAULT_ZOMBIE_COUNT
        
        zombie_count = random.randint(min_zombies, max_zombies)
        
        # Collect all blocked positions
        blocked_positions = set(self.obstacles)
        blocked_positions.add(self.player_pos)
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
        """Move all zombies using weighted random movement toward the player."""
        from config import DIRECTION_UP, DIRECTION_DOWN, DIRECTION_LEFT, DIRECTION_RIGHT
        
        new_zombie_positions = []
        
        for zombie_pos in self.zombies:
            # Calculate distance to player
            dx_to_player = self.player_pos[0] - zombie_pos[0]
            dy_to_player = self.player_pos[1] - zombie_pos[1]
            
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
                    # Calculate new distance to player
                    new_dx = self.player_pos[0] - new_pos[0]
                    new_dy = self.player_pos[1] - new_pos[1]
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
        """Check if player collides with any zombie and handle life loss/game over."""
        # Check if player is at a zombie position
        if self.player_pos in self.zombies:
            # Collision detected - reduce lives
            self.player_lives -= 1
            
            # Remove all zombies at player's position to prevent immediate re-kill
            self.zombies = [z for z in self.zombies if z != self.player_pos]
            
            # Check if game over
            if self.player_lives <= 0:
                self.game_over = True
    
    def can_move(self, dx: int, dy: int) -> bool:
        """Check if the player can move in the given direction."""
        new_x = self.player_pos[0] + dx
        new_y = self.player_pos[1] + dy
        
        # Check boundaries
        if new_x < 0 or new_x >= self.width or new_y < 0 or new_y >= self.height:
            return False
        
        # Check obstacles
        if (new_x, new_y) in self.obstacles:
            return False
        
        return True
    
    def move(self, dx: int, dy: int) -> bool:
        """Move the player in the given direction. Returns True if move was successful."""
        # Don't allow moves if game is over
        if self.game_over:
            return False
        
        if self.can_move(dx, dy):
            new_pos = (self.player_pos[0] + dx, self.player_pos[1] + dy)
            self.player_pos = new_pos
            
            # Check if player collected an item
            if new_pos in self.items:
                item_type = self.items[new_pos]
                self.collected_items[item_type] += 1
                del self.items[new_pos]
            
            # Check if player reached portal (and has required items)
            if self.portal_pos is not None and new_pos == self.portal_pos and self.can_reach_portal():
                self.level_complete = True
            
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
    
    def collect_item(self, item_type: str) -> None:
        """Manually collect an item (used when player steps on it)."""
        self.collected_items[item_type] += 1
    
    def can_reach_portal(self) -> bool:
        """Check if player has collected enough items to use the portal."""
        total_collected = sum(self.collected_items.values())
        return total_collected >= self.required_items_count
    
    def is_level_complete(self) -> bool:
        """Check if the level is complete."""
        return self.level_complete
    
    def get_inventory(self) -> Dict[str, int]:
        """Get current inventory."""
        return self.collected_items.copy()
    
    def get_total_collected(self) -> int:
        """Get total number of items collected."""
        return sum(self.collected_items.values())
    
    def render(self) -> str:
        """Render the game field as a string using emojis."""
        lines = []
        
        # Convert zombies list to set for faster membership checking
        zombie_positions = set(self.zombies)
        
        # Top wall
        lines.append(self.emojis["wall"] * (self.width + 2))
        
        # Game field
        for y in range(self.height):
            line = self.emojis["wall"]  # Left wall
            for x in range(self.width):
                pos = (x, y)
                # Rendering priority: player > portal > zombies > items > obstacles > empty
                if pos == self.player_pos:
                    line += self.emojis["player"]
                elif self.portal_pos is not None and pos == self.portal_pos:
                    # Show portal only if player can reach it
                    if self.can_reach_portal():
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

