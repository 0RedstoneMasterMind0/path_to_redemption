

requirements = ['pyautogui','pygame', 'threading','concurrent.futures', 'json',"numpy",'pathlib',"typing",'multiprocessing','perlin_noise']
import os, sys

for requirement in requirements:
    try:
        print(f"Attempting import of {requirement}")
        __import__(requirement)
    except ImportError:
        print(f"failed import of {requirement}")
        print(f'"{sys.executable}" -m pip install {requirement}')
        os.system(f'"{sys.executable}" -m pip install {requirement}')


import _data.login
from _data.player_data import OnlineDatabase
from numpy.f2py.auxfuncs import throw_error
import pyautogui
from perlin_noise import PerlinNoise
import time
import random
import pygame
import threading
import math, json
from enum import Enum
from numpy.matrixlib.defmatrix import *
from concurrent.futures import ThreadPoolExecutor


def error_quit(error, **args):
    """
    Saftely quit program
    Args:
        Error: int Gives diffrent error messages with this
        args: dict, More info
    """

    # diff messages
    error_messages = {
        0: "Safely quit!",
        1: "Missing files, Please try reinstalling and or running the installer again.",
        2: "Error with database"
    }

    # Print message + details
    if error in error_messages:
        message = error_messages[error]
        if args:
            # +details
            details = ", ".join(f"{k}: {v}" for k, v in args.items())
            message += f": {details}"
        print(message)
    else:
        # if i dont provide a code error handling
        print(f"Unknown error code: {error}")
        if args:
            details = ", ".join(f"{k}: {v}" for k, v in args.items())
            print(f"Additional info: {details}")

    # Attempt Shutdown saftley
    try:
        if 'game' in globals():
            game.running = False
        if 'cleanup' in globals():
            cleanup()
    except Exception as e:
        print(f"Error during cleanup: {e}")

    # Force quit if shutdown fails
    if 'pygame' in globals():
        pygame.quit()

    sys.exit(1 if error != 0 else 0)

def get_data(path):
    try:
        with open("_data/"+path,"r") as file:
            return json.loads(file.read())
    except FileNotFoundError:
        error_quit(1)

def set_data(path, info):
    try:
        with open("_data/" + path, "w") as file:
            return file.write(info)
    except FileNotFoundError:
        error_quit(1)

last_id = 0
firebase = ""
database = OnlineDatabase(firebase_config_path=firebase, collection_name="game_characters", database_path="_data/backup.db", encryption_key=
             None)
# This will try Firebase first, then fall back to local database

info_database = OnlineDatabase(firebase_config_path=firebase, collection_name="entity_data", encryption_key=None, database_path="_data/backup_entites.db")
info_database.use_firebase = False
database.use_firebase = False

def debug_database():
    result = 0
    # Test connection
    print("=" * 50)
    print("DATABASE DEBUG TEST")
    print("=" * 50)

    # Test 1: Check if database exists
    try:
        type(database)
        result+=1
    except NameError:
        print("1. ERROR: 'database' variable not found!")
        return False

    # Test 2: Check Firebase
    import os
    config_path = "_data/access.json"
    if not os.path.exists(config_path):
        print("   ERROR: Firebase config file missing!")
        print(f"   Looking for: {os.path.abspath(config_path)}")
        return False

    # Test 3: Check contents
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        result += 1
    except Exception as e:
        print(f"3. Config file error: {e}")
        return False

    # Test 4: Test connection
    print("4. Testing database connection...")
    try:
        # Simple test write
        test_data = {"test": True, "timestamp": "debug_test"}
        result = database.set("debug_test_123", test_data)
        result += 1
        if not result:
            print("   ERROR: Set operation failed!")
            return False

    except Exception as e:
        print(f"   Set operation error: {e}")
        return False

    # Test 5: Test database read
    print("5. Testing database read...")
    try:
        retrieved = database.get("debug_test_123")
        result += 1
        if retrieved is None:
            print("   ERROR: Could not retrieve data that was just saved!")
            return False

    except Exception as e:
        print(f"   Get operation error: {e}")
        return False

    # Test 6: Test list operation
    print("6. Testing list operation...")
    try:
        all_ids = database.list_ids()
        result += 1
        if "debug_test_123" not in all_ids:
            print("   WARNING: Test document not found in list!")

    except Exception as e:
        print(f"   List operation error: {e}")

    # Test 7: Check for starter data
    print("7. Checking for starter data...")
    try:
        starter = database.get("starter")
        result += 1
        if starter is None:
            default_starter = {
                "level": "Menu",
                "strength": 2,
                "speed": 2,
                "health": 20,
                "resistance": {"fire": 1, "water": 1, "earth": 1, "blade": 1},
                "Inventory": {
                    "armor": {"head": {}, "chest": {}, "legs": {}, "feet": {}, "charm": []},
                    "weapons": [],
                    "else": []
                }
            }
            success = database.set("starter", default_starter)

    except Exception as e:
        print(f"   Starter data error: {e}")
    print("9. Cleaning up test data...")
    try:
        database.delete("debug_test_123")
        result += 1
    except Exception as e:
        print(f"   Cleanup error: {e}")

    print("=" * 50)
    print("DATABASE DEBUG COMPLETE")
    print("=" * 50)

    return True if result == 6 else result

if not debug_database():
    #quit if database fails
    error_quit(2, error=ConnectionError)

from typing import Dict, List, Union, Any

def print_verification_report(data: Dict[str, Any], base_path: str = "") -> bool:
    """Generate and print a detailed verification report."""
    existing_files = []
    missing_files = []

    def check_file_path(file_path: str) -> None:
        """Check if a single file path exists and add to appropriate list."""
        full_path = os.path.join(base_path, file_path) if base_path else file_path
        if os.path.exists(full_path):
            existing_files.append(file_path)
        else:
            missing_files.append(file_path)

    def traverse_dict(obj: Any, path: str = "") -> None:
        """Recursively traverse the dictionary structure."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                traverse_dict(value, current_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                current_path = f"{path}[{i}]"
                traverse_dict(item, current_path)
        elif isinstance(obj, str):
            # Check if string looks like a file path (has extension or is a relative path)
            if '.' in obj and ('/' in obj or '\\' in obj or not obj.startswith('http')) and not "#action#" in obj:
                check_file_path(obj)
            elif "#action#" in obj:
                for i in ['Idle', 'Walk', "Death", "Attack01", "Attack02", "Hurt", "Death"]:
                    check_file_path(obj.replace("#action#", i))

    traverse_dict(data)

    total_files = len(existing_files) + len(missing_files)
    success_rate = len(existing_files) / total_files * 100 if total_files > 0 else 0
    print("=" * 60)
    print("FILE VERIFICATION REPORT")
    print("=" * 60)

    print(f"Total files checked: {total_files}")
    print(f"Files found: {len(existing_files)}")
    print(f"Files missing: {len(missing_files)}")
    print(f"Success rate: {success_rate:.1f}%")
    print()

    if existing_files:
        print("✅ EXISTING FILES:")
        for file_path in sorted(existing_files):
            print(f"   {file_path}")
        print()

    if missing_files:
        print("❌ MISSING FILES:")
        for file_path in sorted(missing_files):
            print(f"   {file_path}")
        print()

    if not missing_files:
        print("🎉 All files exist!")
    else:
        print(f"⚠️  {len(missing_files)} file(s) need attention.")
    return len(missing_files) == 0

# Global variables
arrows,temp = [],False # List to store active projectiles

pygame.init() #pygame start
screen_size = pyautogui.size()
screen = pygame.display.set_mode((500,500), pygame.NOFRAME)
pygame.display.set_caption("Path to redemption")

# ALL FPS based variables
clock,fps_font,show_fps,fps_history,fps_history_size,frame_time_history,frame_time_history_size = pygame.time.Clock(),pygame.font.Font(None, 36),True,[],60,[],60

# Thread pool for background tasks
thread_pool = ThreadPoolExecutor(max_workers=4)
all_data = json.loads(open('_data/data.json').read())
if not print_verification_report(all_data,"_data/"):
    error_quit(1)
os.system('cls')
display = 1

class DJ:
    def __init__(self):
        global all_data
        self.lobby = "_data/"+all_data["soundtrack"]["lobby"]
    def set_volume(self, volume):
        pygame.mixer.music.set_volume(volume)
    def set_track(self, track=1, volume=0.5):
        """
        Args:
            Int: Track
        1: lobby
        """
        if track==1:
            pygame.mixer.music.load(self.lobby)
        pygame.mixer.music.play(1, 0.0,10)
        pygame.mixer.music.set_volume(volume)

class SFX:
    def __init__(self):

        self.error = pygame.mixer.Sound('_data/sfx/error.mp3')
        self.attack_1 = pygame.mixer.Sound('_data/sfx/entities/attack1.mp3')
        self.attack_2 = pygame.mixer.Sound('_data/sfx/entities/attack2.mp3')
        self.step = pygame.mixer.Sound('_data/sfx/entities/step.mp3')
        self.alarm = pygame.mixer.Sound('_data/sfx/entities/alarm.mp3')
        self.death = pygame.mixer.Sound('_data/sfx/entities/death.mp3')


def load_tile(sprite_path, target_tile_size, pic =None):
    """Load sprite and scale to single tile size"""
    sprite = pygame.image.load("_data/"+sprite_path).convert_alpha() if pic is None else pic
    scaled_sprite = pygame.transform.scale(sprite, (target_tile_size, target_tile_size))
    return scaled_sprite


def extract_sprites_from_sheet(sprite_sheet_surface, json_config):
    """
    Extract all sprites from a sprite sheet and return as a flat 1D list

    Args:
        sprite_sheet_surface: pygame.Surface of the loaded sprite sheet
        json_config: Dictionary containing the sprite sheet layout info

    Returns:
        List of pygame.Surface objects (all sprites in order)
    """
    all_sprites = []

    for layer in json_config["layers"]:
        offset = layer["offset"]
        height = layer["height"]
        width = layer["width"]
        amount = layer["amount"]

        # Extract each sprite in this layer
        for sprite_index in range(amount):
            x_pos = sprite_index * width
            y_pos = offset

            # Create rectangle for this sprite
            sprite_rect = pygame.Rect(x_pos, y_pos, width, height)

            # Extract the sprite - Fix: Create surface with SRCALPHA flag separately
            sprite_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            sprite_surface.blit(sprite_sheet_surface, (0, 0), sprite_rect)
            sprite_surface = sprite_surface.convert_alpha()


            all_sprites.append(sprite_surface)

    return all_sprites



class OptimizedBackgroundMatrix:
    def __init__(self, target_tiles_x=18, target_tiles_y=12, matrix=None, layout=None):
        global all_data

        screen_info = pygame.display.Info()
        self.screen_width = screen_info.current_w
        self.screen_height = screen_info.current_h

        self.tile_size_x = self.screen_width // target_tiles_x
        self.tile_size_y = self.screen_height // target_tiles_y
        self.tile_size = min(self.tile_size_x, self.tile_size_y)

        self.width = math.ceil(self.screen_width / self.tile_size)
        self.height = math.ceil(self.screen_height / self.tile_size)

        # Load tile sprites
        self.tile_sprites = [load_tile(sprite_path=a, target_tile_size=min(self.tile_size_x, self.tile_size_y) if type(a) == str else None)
                             for a in all_data["background"]]

        list_of_dicts = all_data["background_json"]
        list_of_pics = [pygame.image.load("_data/"+item['pic']).convert_alpha() for item in list_of_dicts]
        list_of_jsons = [item['json'] for item in list_of_dicts]
        lists = []
        for b in range(len(list_of_pics)):
            lists.append([list_of_pics[b], get_data(list_of_jsons[b])])
        for pic,dicts in lists:
            for item in extract_sprites_from_sheet(pic,dicts):
                self.tile_sprites.append(load_tile(sprite_path="",pic=item, target_tile_size=min(self.tile_size_x, self.tile_size_y)))




        self.matrix = [[self.tile_sprites[x] for x in y] for y in matrix] if matrix else [
            [self.tile_sprites[0] for _ in range(self.width)] for _ in range(self.height)]
        self.layout = layout

        print(f"Screen: {self.screen_width}x{self.screen_height}")
        print(f"Tile size: {self.tile_size}x{self.tile_size}")
        print(f"Grid: {self.width}x{self.height} tiles")

        # PRE-RENDER THE ENTIRE BACKGROUND AS ONE SURFACE
        self.background_surface = self._create_background_surface()
        print("Background pre-rendered for optimal performance!")

    def update_background(self, matrix, layout):
        """Update the background surface with a new matrix-FIXED VERSION!"""
        # Update the matrix with new tile sprites
        self.matrix = [[self.tile_sprites[x] for x in y] for y in matrix]
        self.layout = layout
        self.background_surface = self._create_background_surface()

    def _create_background_surface(self):
        global display
        """Create a single surface containing the entire background"""
        print("Pre-rendering background surface...")

        # Create surface matching screen size
        background_surf = pygame.Surface((self.screen_width, self.screen_height))
        background_surf = background_surf.convert()  # Convert for faster blitting


        # Render all tiles onto the background surface
        if display==1:
            for y in range(self.height):
                for x in range(self.width):
                    if y < len(self.matrix) and x < len(self.matrix[y]):
                        tile = (self.matrix[y][x])
                        if tile:
                            background_surf.blit(tile, (x * self.tile_size, y * self.tile_size))
        else:
            print("Displying layout")
            for y in range(self.height):
                for x in range(self.width):
                    if y < len(self.matrix) and x < len(self.matrix[y]):
                        tile = self.matrix[y][x]
                        try:
                            if tile and self.layout[y][x]==1:
                                background_surf.blit(tile, (x * self.tile_size, y * self.tile_size))
                        except Exception as e:
                            while True:
                                exec(input(f"{e}> "))

        return background_surf

    def switch_tile_at_position(self, world_x, world_y, new_tile_type):
        """Switch a single tile at world position - for interactive tile switching"""
        tile_x, tile_y = self.get_tile_from_position(world_x, world_y)

        if 0 <= tile_y < len(self.matrix) and 0 <= tile_x < len(self.matrix[tile_y]):
            # Update the matrix
            if new_tile_type < len(self.tile_sprites):
                self.matrix[tile_y][tile_x] = self.tile_sprites[new_tile_type]

                # Update just that tile on the background surface for efficiency
                self.background_surface.blit(
                    self.tile_sprites[new_tile_type],
                    (tile_x * self.tile_size, tile_y * self.tile_size)
                )
                print(f"Switched tile at ({tile_x}, {tile_y}) to type {new_tile_type}")

    def randomize_background(self):
        """Randomize the entire background - useful for testing"""
        import random
        new_matrix = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                row.append(random.randint(0, len(self.tile_sprites) - 1))
            new_matrix.append(row)

        self.update_background(new_matrix,current_level.level_layout)

    def get_tile_from_position(self, x, y):
        """Get tile coordinates from world position"""
        tile_x = int(x // self.tile_size)
        tile_y = int(y // self.tile_size)
        tile_x = max(0, min(tile_x, self.width - 1))
        tile_y = max(0, min(tile_y, self.height - 1))
        return tile_x, tile_y

    def get_tile_index(self, tile_x, tile_y):
        """Convert 2D tile coordinates to 1D array index"""
        return tile_y * self.width + tile_x

    def get_player_tile(self):
        """Get the tile the player is currently in"""
        tile_x, tile_y = self.get_tile_from_position(player.x_pos, player.y_pos)
        tile_index = self.get_tile_index(tile_x, tile_y)
        return [
            tile_x,
            tile_y]

    def is_position_in_bounds(self, x, y):
        """Check if a position is within the grid bounds"""
        tile_x = int(x // self.tile_size)
        tile_y = int(y // self.tile_size)
        return 0 <= tile_x < self.width and 0 <= tile_y < self.height


class Action(Enum):
    IDLE = 0
    WALK = 1
    DEATH = 2
    ATTACK_1 = 3
    ATTACK_2 = 4
    ATTACK_3 = 5


class Level:
    def __init__(self, level_name, level_id, level_display, level_layout:  list, monsters: list):
        self.level_name = level_name
        self.level_id = level_id
        self.level_display = level_display
        self.level_layout = level_layout
        self.monsters = monsters
    def export(self):
        return {
            "name": self.level_name,
            "id": self.level_id,
            "display": self.level_display,
            "layout": self.level_layout,
            "monsters": self.monsters
        }


class SpriteSheet:
    def __init__(self, type, class_of, speed=1, x=400, y=300, is_displayed=True, health=10, data = {}):
        self.damage_taken = None
        self.alarm = SFX().alarm
        self.sheets = None
        self.cooldown = [0]
        self.is_displayed = is_displayed
        self.speed = speed
        self.target_x, self.target_y = x, y
        self.action = Action.IDLE.value
        self.frame = 0
        self.frame_time = 50
        self.x_pos = x
        self.y_pos = y
        self.facing_right = True
        self.health = health
        self.max_health = health
        if type!='player':
            self.resistance = info_database.get(str(type))['resistances'][class_of]
            self.type = type
            self._class = class_of
        else:
            self.type = 'player'
            self._class = class_of
            self.resistance = data["resistance"]
        self.attacker = None


    def get_player_distance(self,obj):
        dx = abs(obj.x_pos-self.x_pos)
        dy = abs(obj.y_pos-self.y_pos)
        return round(math.sqrt((dy**2)+(dx**2)))



    def get_frame(self, frame_rect, action=None, scale=1.0, image=None):
        if not image:
            image = self.sheets[action]

        current_frame = pygame.Surface((frame_rect[2], frame_rect[3]), pygame.SRCALPHA)
        current_frame.blit(image, (0, 0), frame_rect)
        scaled_size = (int(100 * scale), int(100 * scale))
        scaled_frame = pygame.transform.scale(current_frame, scaled_size)

        if self.facing_right is False:
            scaled_frame = pygame.transform.flip(scaled_frame, True, False)

        return scaled_frame

    # Alternative simple version if you have a consistent entity size
    def distance_to_entity_simple(self, other_entity, entity_size=32):
        """
        Simple version assuming all entities have the same square size.
        """
        dx = other_entity.x_pos - self.x_pos
        dy = other_entity.y_pos - self.y_pos
        center_distance = math.sqrt(dx * dx + dy * dy)

        # Subtract the size of both entities (assuming square entities)
        edge_distance = center_distance - entity_size

        return max(0, edge_distance)

    # For your NPE class, you'd replace the existing distance_to_entity method with one of these:
    # Add this to your NPE class:

    def distance_to_entity(self, other_entity):
        """
        Calculate distance between entity edges, accounting for size.
        """
        # Use the sprite's rect if available, otherwise use width/height or default
        if hasattr(self, 'rect') and hasattr(other_entity, 'rect'):
            self_rect = self.rect
            other_rect = other_entity.rect
        else:
            # Fallback to position and size attributes
            self_rect = pygame.Rect(
                self.x_pos,
                self.y_pos,
                getattr(self, 'width', 32),
                getattr(self, 'height', 32)
            )
            other_rect = pygame.Rect(
                other_entity.x_pos,
                other_entity.y_pos,
                getattr(other_entity, 'width', 32),
                getattr(other_entity, 'height', 32)
            )

        # Check if rectangles overlap
        if self_rect.colliderect(other_rect):
            return 0

        # Calculate minimum distance between rectangle edges
        dx = max(0, max(self_rect.left - other_rect.right, other_rect.left - self_rect.right))
        dy = max(0, max(self_rect.top - other_rect.bottom, other_rect.top - self_rect.bottom))

        return math.sqrt(dx * dx + dy * dy)

    def update_facing_direction(self, mouse_y=None):
        """Update which direction the character is facing based on mouse position"""
        self.facing_right = self.target_x if mouse_y is None else mouse_y > self.x_pos

    def move_away(self, speed=0,ovx = 0,ovy = 0):
        """Move the sprite towards target position at given speed"""
        movement_speed = self.speed if speed == 0 else speed
        self.action = Action.WALK.value
        dx = self.target_x - self.x_pos
        dy = self.target_y - self.y_pos
        distance = math.sqrt(dx ** 2 + dy ** 2)

        if distance <= movement_speed:
            self.x_pos = self.target_x
            self.y_pos = self.target_y
            self.action = Action.IDLE.value
            self.frame = 0
            return False
        if speed <0:
            self.x_pos = ovx
            self.y_pos = ovy
        move_x = (dx / distance) * movement_speed
        move_y = (dy / distance) * movement_speed

        self.x_pos -= move_x
        self.y_pos -= move_y
        return True


    def move_towards(self, speed=0,ovx = 0,ovy = 0):
        """Move the sprite towards target position at given speed"""
        movement_speed = self.speed if speed == 0 else speed
        self.action = Action.WALK.value if self.action !=6 else self.action

        dx = self.target_x - self.x_pos
        dy = self.target_y - self.y_pos
        distance = math.sqrt(dx ** 2 + dy ** 2)

        if distance <= movement_speed:
            self.x_pos = self.target_x
            self.y_pos = self.target_y
            self.action = Action.IDLE.value if self.action !=6 else self.action
            self.frame = 0
            return False
        if speed <0:
            self.x_pos = ovx
            self.y_pos = ovy
        move_x = (dx / distance) * movement_speed
        move_y = (dy / distance) * movement_speed

        self.x_pos += move_x
        self.y_pos += move_y
        return True

    def take_damage(self,by,type_of_damage='blade'):
        if self.action!=5:
            amount = by.damage * random.random()+0.4
            self.health-=amount*self.resistance[type_of_damage]
            self.attacker = by
            self.damage_taken = amount*self.resistance[type_of_damage]
            self.action = len(self.sheets)-1
            self.frame = 0
            print(f"{self.id if hasattr(self, 'id') else 'player'} took {self.damage_taken} damage, now has {self.health} health")

class PlayerEntity(SpriteSheet):
    def __init__(self, image_path=None, speed=1, x=400, y=300, is_displayed=True, image=None, p_id="1", maxframes=None):
        if maxframes is None:
            maxframes = [6, 8, 4, 6, 6, 9, 4]
        self.attacks = [5]

        current_player = database.get(str(p_id))
        if current_player is None:
            current_player = database.get("starter")
        self.data = current_player
        self.damage = self.data['strength']
        super().__init__('player', p_id, self.data['speed'], x, y, is_displayed, self.data['health'], self.data)
        self.max_frames = maxframes
        if not image_path is None:
            action_names = ['Idle', 'Walk', "Death", "Attack01", "Attack02", "Attack03", "Hurt"]
            self.sheets = []
            for action in action_names:
                try:
                    sheet_path = image_path.replace("#action#", action)
                    sheet = pygame.image.load("_data/"+sheet_path).convert_alpha()
                    self.sheets.append(sheet)
                except Exception as error:
                    print(error)
            self.info = self.sheets[0].get_rect(topleft=(100, 100))
        else:
            self.pic = image

class NPE(SpriteSheet):
    def __init__(self, image_path=None, x=400, y=300, is_displayed=True, image=None, type="orc",class_of="basic",target=None,can_summon=True):
        self.alarm = None
        self.goal_change_timer = 0
        global last_id
        info = {}
        try:
            print(f"Debug: Retrieving data for {type} ['data'] {class_of}")
            # Debug: Check if the data exists
            data = info_database.get(type)
            print(f"Debug: Retrieved data for {type}: {data}")

            if data is None:
                raise ValueError(f"Unable to retrieve data for type '{type}' even after re-setting")

            info = data["data"][class_of]
        except Exception as e:
            print(f"Error accessing database: {e}")
            print(f"Type: {type}, Class: {class_of}")
            error_quit(2, database=e, type=type)
        self.has_summoned = False
        self.attacks = [3, 4]
        self.damage = info["strength"]
        self.size = info["size"]
        self.class_of = class_of
        self.summon_lock = threading.Lock()
        super().__init__(type,class_of, info['speed'], x, y, is_displayed,info['health'])
        self.noise_seed_x = random.random() * 100
        self.noise_seed_y = random.random() * 100
        self.noise_step = 0  # increases over time
        if type=='orc':
            self.max_frames = [6,8,6,6,4,4]

        if not image_path is None:
            action_names = ['Idle', 'Walk', "Death", "Attack01", "Attack02", "Hurt"]
            self.sheets = []
            for action in action_names:
                try:
                    sheet_path = image_path.replace("#action#", action)
                    sheet = pygame.image.load("_data/"+sheet_path).convert_alpha()
                    self.sheets.append(sheet)
                except Exception as error:
                    input(f"{error} occured, press enter to continue")
                    error_quit(1)
            self.info = self.sheets[0].get_rect(topleft=(100, 100))
        else:
            self.pic = image
        """
            # === Goals === #
            Goal 0 = Wander
            Goal 1 = Fight
            Goal 2 = Search
            Goal 3 = Retreat
            Goal 4 = Follow
            Goal 5 = Lead
            Goal 6 = Alarm
            Goal 7 = Mate

            # == Weights == #
            Chance of doing such a thing, 
            a Orc with a weight of 0 will not do that action, for example
            [0,1,0.3,0.1,0.4,0.6,0.1]
            Has a 0% chance of wandering
            Has a 100% chance of fighting (if given the option)
            Has a 30% chance of Searching ( as it cant wander, it might lead to other activities)
            Has a 10% chance of Retreating if given the chance
            Has a 40% chance of following
            Has a 60% chance of Leading
            Has a 10% chance of calling for help
        """
        last_id+=1
        self.id = abs(last_id)
        self.damage_taken = self.health
        self.progress = 0
        self.goal = 0
        self.weights = [random.uniform(0.0, 1.0) for _ in range(8)]
        self.weights[6] = self.weights[6] if can_summon else 0
        self.damage_threshold = random.random()
        self.vision = random.randint(50, 120)
        self.attack_cd = random.randint(3, 10)  # Seconds
        self.target = [] if target is None else target
        self.search_timer = 0
        self.attack_time=0

    def attack(self,who,type):
        who.take_damage(self,type)
        self.action = 3
        self.frame = 0

    def ai(self):
        # === Goals === #
        # Goal 0 = Wander
        # Goal 1 = Fight
        # Goal 2 = Search
        # Goal 3 = Retreat
        # Goal 4 = Follow
        # Goal 5 = Lead
        # Goal 6 = Alarm
        # Goal 7 = Mate

        # == Weights == #
        # Chance of doing such a thing,
        # a Orc with a weight of 0 will not do that action, for example
        # [0,1,0.3,0.1,0.4,0.6,0.1,0.01]

        wander_weight = self.weights[0]
        fight_weight = self.weights[1]
        search_weight = self.weights[2]

        # Determine vision range based on current goal
        current_vision_range = self.vision * 2 if self.goal == 2 else self.vision

        # Check if entity has been hurt (damaged)
        is_hurt = self.damage_taken > 0 or self.health < self.max_health

        # Initialize goal change timer if it doesn't exist
        if not hasattr(self, 'goal_change_timer'):
            self.goal_change_timer = 0

        # Only allow goal changes if hurt OR enough time has passed
        goal_change_cooldown = 60  # Frames before allowing non-hurt goal changes (1 second at 60 FPS)
        can_change_goal = is_hurt or self.goal_change_timer >= goal_change_cooldown

        if len(self.target) > 0:
            target_in_range = False
            for target in self.target:
                if self.distance_to_entity(target) < current_vision_range:
                    target_in_range = True
                    break

            if target_in_range:
                # Always allow goal changes when targets are in range (combat situation)
                # Generate single random number for consistent probability logic
                rand_val = random.random()

                # Get relevant weights for target-in-range behavior
                fight_weight = self.weights[1]
                retreat_weight = self.weights[3]
                alarm_weight = self.weights[6]

                total_weight = fight_weight + retreat_weight + alarm_weight

                if total_weight > 0:
                    new_goal = None
                    if rand_val < fight_weight / total_weight:
                        new_goal = 1  # Fight
                    elif rand_val < (fight_weight + retreat_weight) / total_weight:
                        new_goal = 3  # Retreat
                        # In your ai() method, when setting goal to 6:
                    elif not self.has_summoned:
                        new_goal = 6
                    else:
                        new_goal = 0

                    # Only change goal if it's different and we can change
                    if new_goal != self.goal and (can_change_goal or new_goal in [1, 3, 6]):
                        self.goal = new_goal
                        self.goal_change_timer = 0
                else:
                    # If no weights set for combat responses, default to fight
                    if self.goal != 1 and (can_change_goal or True):  # Combat is always allowed
                        self.goal = 1
                        self.goal_change_timer = 0
            else:
                # No target in range - only change if we can change goals
                if can_change_goal:
                    if search_weight == 0 and wander_weight == 0:
                        if self.goal is not None:
                            self.goal = None
                            self.goal_change_timer = 0
                    else:
                        new_goal = 2 if random.random() < search_weight / (search_weight + wander_weight) else 0
                        if new_goal != self.goal:
                            self.goal = new_goal
                            self.goal_change_timer = 0
        else:
            # No targets at all - only change if we can change goals
            if can_change_goal:
                if search_weight == 0 and wander_weight == 0:
                    if self.goal is not None:
                        self.goal = None
                        self.goal_change_timer = 0
                else:
                    new_goal = 2 if random.random() < search_weight / (search_weight + wander_weight) else 0
                    if new_goal != self.goal:
                        self.goal = new_goal
                        self.goal_change_timer = 0

        # If damaged and not fighting or searching, allow immediate switch to search (hurt condition)
        if self.goal not in [1, 2] and self.damage_taken > getattr(self, 'damage_threshold', 0):
            if search_weight > 0 and random.random() < search_weight:
                self.goal = 2
                self.goal_change_timer = 0

        # Handle search behavior - idle for a bit, then return to wander if healed
        if self.goal == 2:
            # Initialize search timer if not exists
            if not hasattr(self, 'search_timer'):
                self.search_timer = 0

            self.search_timer += 1

            # After searching for a while (adjust time as needed)
            if self.search_timer > 600:  # About 2 seconds at 60 FPS
                # Check if healed back up
                if self.damage_taken <= 0 or self.health >= self.max_health * 0.8:  # 80% health threshold
                    self.goal = 0  # Return to wander
                    self.search_timer = 0  # Reset timer
                    self.goal_change_timer = 0
                else:
                    # Still damaged, continue searching but reset timer to avoid infinite search
                    self.search_timer = 0

        # Increment the goal change timer
        self.goal_change_timer += 1

    def act(self):
        self.attack_time = self.attack_time+1 if self.attack_time<=10 else 0
        with self.summon_lock:
            if self.goal ==6 and not self.has_summoned and self.class_of=='basic':
                time.sleep(2)
                summon('orc', 'basic', [self.y_pos, self.x_pos], target=self.target, can_summon=False)
                summon('orc', 'basic', [self.y_pos, self.x_pos], target=self.target, can_summon=False)
                summon('orc', 'elder', [self.y_pos, self.x_pos], target=self.target, can_summon=True)
                self.has_summoned = True
                self.weights[6] = 0
                self.goal = 5
                self.alarm.play()
                self.alarm.set_volume(0.4)
            elif self.goal ==6 and not self.has_summoned and self.class_of=='elder':
                time.sleep(2)
                summon('orc', 'boss', [self.y_pos, self.x_pos], target=self.target, can_summon=True)
                self.has_summoned = True
                self.weights[6] = 0
                self.goal = 5
                self.alarm.play(2)
                self.alarm.set_volume(0.2)
            elif self.goal ==6 and not self.has_summoned and self.class_of=='boss':
                time.sleep(2)
                summon('orc', 'basic', [self.y_pos, self.x_pos], target=self.target, can_summon=False)
                summon('orc', 'basic', [self.y_pos, self.x_pos], target=self.target, can_summon=False)
                self.weights[6] = 0.1
                self.goal = 1
                self.alarm.play()
                self.alarm.set_volume(0.4)
        if self.goal is None:
            self.action = 0
        if self.goal==5:
            self.goal = 1
        if self.goal == 0:  # Wander
            self.noise_step += 0.005

            # Create PerlinNoise instances if they don't exist
            if not hasattr(self, 'noise_x'):
                self.noise_x = PerlinNoise(octaves=1, seed=self.noise_seed_x)
            if not hasattr(self, 'noise_y'):
                self.noise_y = PerlinNoise(octaves=1, seed=self.noise_seed_y)

            # Generate noise values
            noise_x = self.noise_x(self.noise_step)
            noise_y = self.noise_y(self.noise_step)

            self.target_x = int((noise_x + 1) / 2 * screen.get_width())
            self.target_y = int((noise_y + 1) / 2 * screen.get_height())
        elif self.goal == 1 and self.target:
            # Move toward closest target
            closest = min(self.target, key=lambda t: self.distance_to_entity(t))
            self.target_x = closest.x_pos
            self.target_y = closest.y_pos
        for target in self.target:
            if self.distance_to_entity(target) < 25 and self.attack_time==1:
                self.attack(target, 'blade')



class Game:
    def __init__(self, target_fps, admin=True): # change admin -> False before release
        self.running = True
        self.target = target_fps
        self.admin = admin

game = Game(1000)
# Optimized cooldown system using thread pool
def cooldown_tick():
    """Background thread to handle cooldown timers"""
    while game.running:
        time.sleep(0.01)

        # Tick cooldowns
        player.cooldown = [max(player.cooldown[c] - 0.01, 0) for c in range(len(player.cooldown))]

        if player.health <= 0:
            while game.running:
                Sound.death.play()
                player.action = 2
                player.frame = 0
                time.sleep(0.5)
                player.frame+=1
                time.sleep(0.5)
                player.frame += 1
                time.sleep(0.5)
                player.frame += 1
                time.sleep(0.5)
                player.frame += 1
                time.sleep(1)
                game.running = False
                error_quit(0)


        # Update animation frame timing
        max_frames = player.max_frames[player.action]  # Get number of frames for the current action
        if player.action!=2:
            if player.frame_time == 0:
                player.frame += 1

                # Reset to idle after finishing an attack or special animation
                if player.frame >= max_frames:
                    player.frame = 0
                    if player.action >= 3:  # Attack01, Attack02, etc.
                        player.action = Action.IDLE.value
                        player.frame = 0

            # Frame timing logic
            player.frame_time = max(player.frame_time - 1, 0) if player.frame_time > 0 else 11



class Load(SpriteSheet):
    def __init__(self, speed=1, x=400, y=300, is_displayed=True, image=None, sections=5, size=48): # Ignore
        self.is_displayed = is_displayed
        self.sections = sections
        self.width = size
        self.percent_full = 0
        self.x_pos = x
        self.y_pos = y
        self.pic = image

    def get_cooldown_frame(self, cooldown_value, max_cooldown=2, scale=1.0):
        """Get the appropriate bar frame from sprite sheet based on cooldown percentage"""
        if not self.pic or cooldown_value <= 0:
            frame_rect = (self.sections * self.width, 0, self.width, 44)
            frame = pygame.Surface((self.width, 44), pygame.SRCALPHA)
            frame.blit(self.pic, (0, 0), frame_rect)
            scaled_size = (int(self.width * scale), int(44 * scale))
            scaled_frame = pygame.transform.scale(frame, scaled_size)
            return scaled_frame

        percentage = max(0, (max_cooldown - cooldown_value) / max_cooldown)
        frame_index = min(self.sections - 1, int(percentage * self.sections - 1))
        frame_rect = (frame_index * self.width, 0, self.width, 44)
        frame = pygame.Surface((self.width, 44), pygame.SRCALPHA)
        frame.blit(self.pic, (0, 0), frame_rect)

        scaled_size = (int(self.width * scale), int(44 * scale))
        scaled_frame = pygame.transform.scale(frame, scaled_size)
        return scaled_frame


class Sprite:
    def __init__(self, pic, speed=10, x=0, y=0, x_p=0, y_p=0, is_displayed=False):
        self.pic = pic.convert_alpha()  # Convert for faster blitting
        self.speed = speed
        self.info = pic.get_rect(topleft=(100, 100))
        self.is_displayed = is_displayed
        self.opacity = 255


class Projectile:
    def __init__(self, pic, target_x, target_y, start_x, start_y, damage = 1):
        self.target_x, self.target_y = target_x, target_y
        self.damage = damage
        self.x_pos = start_x
        self.y_pos = start_y
        self.pic = pic.convert_alpha()  # Convert for faster blitting
        self.angle = 0
        self.info = pic.get_rect(topleft=(100, 100))
        # Pre-calculate rotated images for common angles to reduce real-time rotation
        self.rotated_cache = {}

    def get_rotated_image(self, angle):
        """Get cached rotated image or create new one"""
        # Round angle to nearest 5 degrees for caching efficiency
        cache_angle = round(angle / 5) * 5
        if cache_angle not in self.rotated_cache:
            self.rotated_cache[cache_angle] = pygame.transform.rotate(self.pic, cache_angle)
        return self.rotated_cache[cache_angle]

    def move_towards(self, speed=10):
        """Move projectile towards target and calculate rotation angle"""
        dx = self.target_x - self.x_pos
        dy = self.target_y - self.y_pos
        distance = math.sqrt(dx ** 2 + dy ** 2)

        if distance <= speed:
            self.x_pos = self.target_x
            self.y_pos = self.target_y
            return False

        move_x = (dx / distance) * speed
        move_y = (dy / distance) * speed

        self.x_pos += move_x
        self.y_pos += move_y

        angle_rad = math.atan2(-dy, dx)
        self.angle = math.degrees(angle_rad)

        return True


# Optimized target opacity update using threading
def update_target_opacity():
    """Update target opacity based on distance to player (fade effect)"""
    if not target.is_displayed:
        return

    dx = target.info.centerx - player.x_pos
    dy = target.info.centery - player.y_pos
    distance = math.sqrt(dx ** 2 + dy ** 2)

    MIN_DISTANCE = 10
    MAX_DISTANCE = 700

    if distance <= MIN_DISTANCE:
        target.opacity = 0
    elif distance >= MAX_DISTANCE:
        target.opacity = 255
    else:
        opacity_ratio = (distance - MIN_DISTANCE) / (MAX_DISTANCE - MIN_DISTANCE)
        target.opacity = int(255 * opacity_ratio)

    if target.opacity <= 0:
        target.is_displayed = False


def calculate_advanced_fps():
    """Calculate advanced FPS metrics with averaging and frame time tracking"""
    global fps_history, frame_time_history

    current_fps = clock.get_fps()
    frame_time = clock.get_time()

    fps_history.append(current_fps)
    frame_time_history.append(frame_time)

    if len(fps_history) > 60:
        fps_history.pop(0)
    if len(frame_time_history) > 60:
        frame_time_history.pop(0)

    avg_fps = sum(fps_history) / len(fps_history) if fps_history else 0
    avg_frame_time = sum(frame_time_history) / len(frame_time_history) if frame_time_history else 0

    min_fps = min(fps_history) if fps_history else 0
    max_fps = max(fps_history) if fps_history else 0

    return {
        'current': current_fps,
        'average': avg_fps,
        'min': min_fps,
        'max': max_fps,
        'frame_time': avg_frame_time
    }


def get_fps_color(fps):
    """Return color based on FPS performance"""
    if fps >= 55:
        return (0, 255, 0)  # Green - Excellent
    elif fps >= 40:
        return (255, 255, 0)  # Yellow - Good
    elif fps >= 25:
        return (255, 165, 0)  # Orange - Poor
    else:
        return (255, 0, 0)  # Red - Very Poor


interrupt = False


def task(wait, command):
    global interrupt
    current = 0
    while current < wait:
        clock.tick(60)
        current += 0.02
        if interrupt:
            return None
    try:
        exec(command)
    except Exception as e:
        print(e)
    return None

def task_uninterrupted(wait, command):
    time.sleep(wait)
    try:
        exec(command)
    except Exception as e:
        print(e)
    return None


# Separate projectile update thread  for better performance
def update_projectiles():
    """Update projectiles in separate thread"""
    global arrows

    while game.running:
        if arrows:
            for i in range(len(arrows) - 1, -1, -1):
                for monster in current_level.monsters:
                    if monster.distance_to_entity(arrows[i])<=25:
                        monster.take_damage(arrows[i],'arrow')
                        arrows.pop(i)
                        break
                try:
                    if not arrows[i].move_towards(10):
                        arrows.pop(i)
                except IndexError:
                    continue

        clock.tick(60)  # ~60 FPS for projectile updates


def do_monsters(thread):
    thread -= 1
    collective_clock = 0

    # Pre-calculate modulo checks to avoid repeated calculations
    clock_mod_2 = 0
    clock_mod_6 = 0
    clock_mod_10 = 0
    clock_mod_20 = 0

    # Cache frequently accessed values
    player_action = player.action
    player_x = player.x_pos
    player_y = player.y_pos

    while game.running:
        clock.tick(600/4)w
        monsters = current_level.monsters
        monsters_len = len(monsters)

        # Increment collective_clock with efficient reset
        collective_clock = (collective_clock + 1) % 2001  # 0-200 cycle

        # Update modulo checks once per frame
        clock_mod_2 = collective_clock & 1  # Fast modulo 2 using bitwise AND
        clock_mod_6 = collective_clock % 6
        clock_mod_10 = collective_clock % 10
        clock_mod_20 = collective_clock % 20

        # Update player cache less frequently to reduce overhead
        if collective_clock % 4 == 0:
            player_action = player.action
            player_x = player.x_pos
            player_y = player.y_pos

        if monsters_len > 0:
            # Pre-filter monsters for this thread to avoid continue statements
            thread_monsters = []
            for i in range(monsters_len - 1, -1, -1):
                if i % 4 == thread:
                    thread_monsters.append((i, monsters[i]))

            # Process only relevant monsters
            for i, monster in thread_monsters:
                # Movement and action (every other frame)
                if clock_mod_2 == 0:
                    entity_move_towards(monster)
                    monster.act()

                # Combat check - cache distance calculation
                if (
                        player_action == 3 or player_action == 4) and monster.action != 5 and monster.action != 2 and clock_mod_20 != 0:
                    # Fast distance check using squared distance to avoid sqrt
                    dx = monster.x_pos - player_x
                    dy = monster.y_pos - player_y
                    if dx * dx + dy * dy < 2500:  # 50*50 = 2500
                        monster.take_damage(player)
                        monster.target.append(player)
                        monster.ai()

                # Death check
                if monster.health < 0 and monster.action != 6:
                    monster.action = 2
                    monster.ai()

                # Animation updates
                monster_action = monster.action
                if clock_mod_6 == 0 and monster_action != 5 and monster_action != 2:
                    max_frames = monster.max_frames[monster_action]
                    monster.frame += 1
                    if monster.frame >= max_frames:
                        monster.frame = 0
                elif clock_mod_10 == 0 and monster_action >= 2:
                    max_frames = monster.max_frames[monster_action]
                    monster.frame += 1
                    if monster.frame >= max_frames:
                        monster.frame = 0
                        if monster_action == 2:
                            current_level.monsters.pop(i)
                        else:
                            monster.action = 0
                            monster.frame = 0



def summon(type,class_of, coords=None, target=None,can_summon=True):
    if coords is None:
        coords = [300, 400]
    if 0 in current_level.monsters:
        current_level.monsters.pop(0)
    if type=='orc':
        current_level.monsters.append(NPE(all_data["enemies"]["orc"],coords[1],coords[0],True,None,type,class_of,target=target,can_summon=can_summon))



def frame():
    """Main rendering loop with advanced FPS counter - HEAVILY OPTIMIZED"""
    global arrows, interrupt

    player.info.size = (250, 250)
    goal_font = pygame.font.Font(None, 24)
    while game.running:
        fps_data = calculate_advanced_fps()
        if display!=1:
            screen.fill((0, 0, 0))

        # MAJOR OPTIMIZATION: Single blit for entire background!
        screen.blit(background.background_surface, (0, 0))

        # Update character facing direction based on mouse position
        mouse_x, mouse_y = pygame.mouse.get_pos()
        player.update_facing_direction(mouse_x)

        # Run target opacity update in thread pool to avoid blocking main thread
        update_target_opacity()

        player.info.center = (player.x_pos, player.y_pos)

        # Render projectiles with cached rotation
        for arrow in arrows:
            rotated_image = arrow.get_rotated_image(arrow.angle)
            rotated_rect = rotated_image.get_rect(center=(arrow.x_pos, arrow.y_pos))
            scaled_arrow = pygame.transform.scale(rotated_image, (200, 200))
            screen.blit(scaled_arrow, rotated_rect)

        # Render player sprite
        # Player
        frame_rect = (player.frame * 100, 0, 100, 100)
        player_surface = player.get_frame(frame_rect, player.action, 2.5)
        player_rect = player_surface.get_rect(center=(player.x_pos, player.y_pos))
        screen.blit(player_surface, player_rect)
        if not game.admin:
            for monster in current_level.monsters:
                frame_rect = (monster.frame * 100, 0, 100, 100)
                monster_surface = monster.get_frame(frame_rect, monster.action, 2.5 * monster.size)
                monster_rect = monster_surface.get_rect(center=(monster.x_pos, monster.y_pos))
                screen.blit(monster_surface, monster_rect)
        else:
            for i, monster in enumerate(current_level.monsters):
                frame_rect = (monster.frame * 100, 0, 100, 100)
                monster_surface = monster.get_frame(frame_rect, monster.action, 2.5)
                monster_rect = monster_surface.get_rect(center=(monster.x_pos, monster.y_pos))
                screen.blit(monster_surface, monster_rect)

                # Draw vision circle around monster
                if hasattr(monster, 'vision'):
                    base_radius = monster.vision
                    # Increase radius by 2 if monster's goal is 2
                    if hasattr(monster, 'goal') and monster.goal == 2:
                        circle_radius = base_radius + 2
                        circle_color = (255, 100, 100, 200)  # Red tint for goal 2 monsters with less transparency
                    else:
                        circle_radius = base_radius
                        circle_color = (100, 100, 255, 200)  # Blue for regular monsters with less transparency

                    # Create a surface for the translucent circle
                    circle_surface = pygame.Surface((circle_radius * 2, circle_radius * 2), pygame.SRCALPHA)
                    pygame.draw.circle(circle_surface, circle_color, (circle_radius, circle_radius), circle_radius)

                    # Blit the translucent circle to the screen
                    circle_rect = circle_surface.get_rect(center=(int(monster.x_pos), int(monster.y_pos)))
                    screen.blit(circle_surface, circle_rect)

                # Draw 25px wide square box at entity position
                square_size = 25
                square_surface = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
                square_color = (255, 255, 255, 200)  # White square with reduced transparency
                pygame.draw.rect(square_surface, square_color, (0, 0, square_size, square_size))

                # Center the square on the monster
                square_rect = square_surface.get_rect(center=(int(monster.x_pos), int(monster.y_pos)))
                screen.blit(square_surface, square_rect)

                # Display monster goal above head
                if hasattr(monster, 'goal') and monster.goal:
                    goal_text = goal_font.render(str(monster.goal) + " : " + str(monster.size), True, (255, 255, 255))  # White text
                    goal_rect = goal_text.get_rect()
                    # Position text above monster (adjust the -40 offset as needed)
                    goal_rect.centerx = monster.x_pos
                    goal_rect.centery = monster.y_pos - 40

                    # Optional: Add background rectangle for better readability
                    bg_rect = goal_rect.inflate(10, 4)  # Add padding
                    pygame.draw.rect(screen, (0, 0, 0, 128), bg_rect)  # Semi-transparent black background

                    screen.blit(goal_text, goal_rect)
        # Render target if visible
        if target.is_displayed:
            target.pic.set_alpha(target.opacity)
            screen.blit(target.pic, target.info)

        if bar.is_displayed:
            bar_frame = bar.get_cooldown_frame(player.cooldown[0], max_cooldown=2, scale=1.25)
            if bar_frame:
                bar_rect = bar_frame.get_rect()
                bar_rect.center = (mouse_x, mouse_y + 30)
                screen.blit(bar_frame, bar_rect)

        if player.cooldown[0] <= 0 and game.running:
            thread_pool.submit(task, 1.5, "bar.is_displayed=False")
            interrupt = False
        elif player.cooldown[0] > 0:
            bar.is_displayed = True
            interrupt = True

        # Advanced FPS Counter Display
        if show_fps:
            y_offset = 10

            fps_color = get_fps_color(fps_data['current'])
            current_fps_text = fps_font.render(f"FPS: {fps_data['current']:.1f}", True, fps_color)
            screen.blit(current_fps_text, (10, y_offset))
            y_offset += 35

            avg_fps_text = fps_font.render(f"Avg: {fps_data['average']:.1f}", True, (200, 200, 200))
            screen.blit(avg_fps_text, (10, y_offset))
            y_offset += 35

            minmax_text = fps_font.render(f"Min: {fps_data['min']:.1f} Max: {fps_data['max']:.1f}", True,
                                          (150, 150, 150))
            screen.blit(minmax_text, (10, y_offset))
            y_offset += 35

            frame_time_text = fps_font.render(f"Frame: {fps_data['frame_time']:.1f}ms", True, (100, 200, 255))
            screen.blit(frame_time_text, (10, y_offset))

        pygame.display.flip()
        clock.tick(game.target)

def entity_move_towards(entity: NPE):
        if (entity.x_pos != entity.target_x or entity.y_pos != entity.target_y) and entity.action != 5:

            # Store previous position before moving
            prev_x, prev_y = entity.x_pos, entity.y_pos

            # Attempt to move towards target
            temps = entity.move_towards()

            # Check collision after movement
            lx, ly = background.get_tile_from_position(entity.x_pos, entity.y_pos)

            # If player moved into a wall (layout value 1), revert to previous position
            if background.layout[int(ly)][int(lx)] == 1:
                entity.x_pos = prev_x
                entity.y_pos = prev_y
                entity.action = Action.IDLE.value  # Stop movement animation
                entity.frame = 0

def move_towards():
    """Player movement handler (runs in separate thread)"""
    global temp
    temp = True
    les = 0

    while temp:
        tile_y,tile_x = background.get_player_tile()
        current_tile =current_level.level_display[tile_x][tile_y]
        les+=1
        if les>10*(player.speed/1.95) and current_tile==3:

            les = 0
            Sound.step.play()
            Sound.step.set_volume(0.2)
        # Store previous position before moving
        prev_x, prev_y = player.x_pos, player.y_pos

        # Attempt to move towards target
        temp = player.move_towards()

        # Check collision after movement
        lx, ly = background.get_player_tile()

        # If player moved into a wall (layout value 1), revert to previous position
        if background.layout[int(ly)][int(lx)] == 1:
            player.x_pos = prev_x
            player.y_pos = prev_y
            player.action = Action.IDLE.value  # Stop movement animation
            player.frame = 0
            temp = False  # Stop the movement loop
            break

        clock.tick(60)


def menu(Mix):
    Mix.set_track(1)
    try:
        menu_image = pygame.image.load("_data/" + all_data["menu"]).convert()

        # Set up fonts
        title_font = pygame.font.Font(None, 64)
        prompt_font = pygame.font.Font(None, 32)

        prompt_text = prompt_font.render("Click to continue", True, (100, 50, 100))
        prompt_rect = prompt_text.get_rect(center=(250, 300))
        menu_image.blit(prompt_text, prompt_rect)
    except pygame.error:
        # Create a placeholder if image doesn't exist
        menu_image = pygame.Surface((500, 500))
        menu_image.fill((50, 50, 100))
        font = pygame.font.Font(None, 48)
        text = font.render("MENU", True, (255, 255, 255))
        text_rect = text.get_rect(center=(250, 250))
        menu_image.blit(text, text_rect)
        print("using alternative menu image")
    global screen, screen_size
    game.running = False

    # Display menu in 500x500 window
    screen.blit(menu_image, (0, 0))
    pygame.display.flip()

    # Menu loop - wait for user interaction
    menu_running = True
    while menu_running:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                menu_running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                menu_running = False

        # Keep displaying the menu
        screen.blit(menu_image, (0, 0))
        pygame.display.flip()
        clock.tick(60)


    answer, fps, remeber = _data.login.run_login_app()
    if answer is None:
        error_quit(0)
    screen = pygame.display.set_mode(screen_size, pygame.FULLSCREEN)
    game.running = True
    game.target = fps
    pygame.mixer.music.stop()
    game.admin = answer==1
    if remeber:
        database.sync_all_collections_to_local()
        info_database.sync_all_collections_to_local()
    return answer


# Main game execution
if __name__ == "__main__":
    Mixer = DJ()
    p_id = menu(Mixer)
    player = PlayerEntity(all_data["hero"], p_id=str(p_id))

    with open('_data/levels.json', 'r') as file:
        try:
            info = json.loads(file.read())
            current_id = info['levels'][p_id]
            current_level = Level(info['level'][current_id]['name'], info['level'][current_id]['id'], info['level'][current_id]['display'],info['level'][current_id]['layout'], [0])
        except Exception as e:
            throw_error(e)
            current_level = Level("Menu", 0,
                                 [[0 for _ in range(27)] for _ in range(15)], [
                [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
                [1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1]],[])

    last_used = None
    background = OptimizedBackgroundMatrix(20, 15, layout=current_level.level_layout)
    background.update_background(current_level.level_display,current_level.level_layout)

    target = Sprite(pygame.transform.scale(pygame.image.load("_data/" + all_data["target"]).convert_alpha(), (50, 50)))
    bar = Load(image=pygame.image.load("_data/" + all_data["load"][0]).convert_alpha(), is_displayed=True, sections=6, size=44)
    # Start optimized background threads
    refreshing_screen = threading.Thread(target=frame, daemon=True)
    refreshing_screen.start()

    Sound = SFX()

    cooldown_thread = threading.Thread(target=cooldown_tick, daemon=True)
    cooldown_thread.start()

    toggle = []
    display = 1

    monsters_thread_1 = threading.Thread(target=do_monsters, args=(1,), daemon=True)
    monsters_thread_1.start()
    monsters_thread_2 = threading.Thread(target=do_monsters, args=(2,), daemon=True)
    monsters_thread_2.start()
    monsters_thread_3 = threading.Thread(target=do_monsters, args=(3,), daemon=True)
    monsters_thread_3.start()
    monsters_thread_4 = threading.Thread(target=do_monsters, args=(4,), daemon=True)
    monsters_thread_4.start()

    # Start projectile update thread
    projectile_thread = threading.Thread(target=update_projectiles, daemon=True)
    projectile_thread.start()
    mode = 1 #attack
    # Main game loop - handle events
    def cleanup():
        """Clean up resources and save data before quitting"""
        print("Starting cleanup process...")
        # Save player data to database
        try:
            if 'player' in globals() and 'database' in globals() and 'p_id' in globals():
                print("Saving player data...")
                database.set(str(p_id), player.data)
                print("Player data saved successfully")
        except Exception as e:
            print(f"Database save error: {e}")

        # Shutdown thread pool with timeout
        try:
            if 'thread_pool' in globals():
                print("Shutting down thread pool...")
                thread_pool.shutdown(wait=False)  # Don't wait to avoid hanging
                print("Thread pool shutdown initiated")
        except Exception as e:
            print(f"Thread pool shutdown error: {e}")

        # Print performance statistics
        try:
            if 'fps_history' in globals() and fps_history:
                avg_fps = sum(fps_history) / len(fps_history)
                min_fps = min(fps_history)
                max_fps = max(fps_history)
                if 'current_level' in globals():
                    entity_count = len(current_level.monsters)
                    print(
                        f"Performance stats - Average FPS: {avg_fps:.1f} (min: {min_fps:.1f}, max: {max_fps:.1f}), entities: {entity_count}")
        except Exception as e:
            print(f"Stats error: {e}")

        # Quit pygame
        try:
            print("Quitting pygame...")
            pygame.quit()
            print("Pygame quit successfully")
            sys.exit()
        except Exception as e:
            print(f"Pygame quit error: {e}")
        print("Cleanup complete!")
        os.abort()
    while game.running:
        clock.tick(game.target)
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                error_quit(0)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_f:
                show_fps = not show_fps
                print(f"FPS display: {'ON' if show_fps else 'OFF'}")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                mode = 1 if mode==0 else 0
                print(f"Building mode: {'ON' if mode==0 else 'OFF'}")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_s:
                display = 1 if display == 0 else 0

                background.background_surface = background._create_background_surface()
                print(f"Display layout mode: {'ON' if display == 0 else 'OFF'}")

            # BACKGROUND SWITCHING CONTROLS
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_1:
                # Switch to wood floor background
                current_level.level_display = [[0 for _ in range(background.width)] for _ in range(background.height)]
                background.update_background(current_level.level_display, current_level.level_layout)
                print("Switched to wood floor background")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_2:
                # Switch to bamboo floor background
                current_level.level_display = [[1 for _ in range(background.width)] for _ in range(background.height)]
                background.update_background(current_level.level_display,current_level.level_layout)
                print("Switched to bamboo floor background")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_4:
                X,Y = pygame.mouse.get_pos()
                summon('orc','basic',coords=[X,Y])

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_3:
                level = current_level.export()
                with open("_data/levels.json", 'r') as file:
                    info = json.loads(file.read())
                    if not level['name'] in info['levels']:

                        info['levels'][level['name']] = len(info['level'])
                        info['level'].append(level)
                    else:

                        sec = info['levels'][level['name']]
                        info['level'][sec] = level

                with open('_data/levels.json', 'w') as file:
                    file.write(json.dumps(info,indent=4))
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r and mode ==1:
                # Randomize background
                background.randomize_background()
                print("Randomized background")

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                ct = background.get_tile_from_position(player.x_pos, player.y_pos)
                # Create matrix with the new background type
                current_level.level_display[ct[1]][ct[0]] += 1 if current_level.level_display[ct[1]][ct[0]]<len(background.tile_sprites)-1 else -1
                background.update_background(current_level.level_display,current_level.level_layout)

            # ORIGINAL GAME CONTROLS
            elif (event.type == pygame.MOUSEBUTTONDOWN and
                  event.button == 3 and
                  player.action != Action.ATTACK_3.value and mode==1):


                x,y = pygame.mouse.get_pos()
                lx,ly = background.get_tile_from_position(x,y)
                try:
                    if background.layout[int(ly)][int(lx)] != 1:
                        target.is_displayed = True
                        target.info = target.pic.get_rect(center=pygame.mouse.get_pos())
                        target.opacity = 255
                        player.target_x, player.target_y = (x,y)
                        if not temp:
                            threading.Thread(target=move_towards, daemon=True).start()
                    else:
                        print('Cant move there')
                        Sound.error.play()
                except Exception as e:
                    print(f"Found Execption: {e}")
                    e=e

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and mode==1:
                if player.action == Action.IDLE.value:
                    attack = random.randint(Action.ATTACK_1.value, Action.ATTACK_2.value)
                    player.action = attack
                    player.frame = 0
                    Sound.attack_1.stop()
                    Sound.attack_2.stop()
                    if attack == Action.ATTACK_1.value:
                        Sound.attack_1.play()
                    else:
                        Sound.attack_2.play()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and mode==0:
                mouse_pos = pygame.mouse.get_pos()
                ct = background.get_tile_from_position(mouse_pos[0],mouse_pos[1])
                # Create matrix with the new background type
                current_level.level_display[ct[1]][ct[0]] -= 1 if current_level.level_display[ct[1]][ct[0]] > 0 else -1
                last_used = current_level.level_display[ct[1]][ct[0]]
                background.update_background(current_level.level_display,current_level.level_layout)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r and mode==0:
                # Toggle between wood (0) and bamboo (1) backgrounds
                mouse_pos = pygame.mouse.get_pos()
                ct = background.get_tile_from_position(mouse_pos[0],mouse_pos[1])
                # Create matrix with the new background type
                current_level.tile_info[ct[1]][ct[0]][0] += 90
                background.update_background(current_level.level_display,current_level.level_layout)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and mode==0:
                mouse_pos = pygame.mouse.get_pos()
                ct = background.get_tile_from_position(mouse_pos[0],mouse_pos[1])
                # Create matrix with the new background type
                current_level.level_display[ct[1]][ct[0]] += 1 if current_level.level_display[ct[1]][ct[0]] < len(
                    background.tile_sprites) - 1 else -1
                last_used = current_level.level_display[ct[1]][ct[0]]
                background.update_background(current_level.level_display,current_level.level_layout)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 2 and mode==0:
                toggle.append("scrWheel")
                # Toggle between wood (0) and bamboo (1) backgrounds
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2 and mode==0:
                toggle.remove("scrWheel")
                # Toggle between wood (0) and bamboo (1) backgrounds
            elif 'scrWheel' in toggle:
                mouse_pos = pygame.mouse.get_pos()
                ct = background.get_tile_from_position(mouse_pos[0], mouse_pos[1])
                # Create matrix with the new background type
                current_level.level_display[ct[1]][ct[0]] = last_used if last_used else 0
                last_used = current_level.level_display[ct[1]][ct[0]]
                background.update_background(current_level.level_display,current_level.level_layout)
            elif (event.type == pygame.KEYDOWN and
                  event.key == pygame.K_e and
                  player.cooldown[0] == 0):

                player.cooldown[0] = 2
                target_x, target_y = pygame.mouse.get_pos()

                if player.action == Action.IDLE.value:
                    player.action = Action.ATTACK_3.value
                    player.frame = 0

                new_arrow = Projectile(
                    pygame.image.load("_data/" + all_data["arrow"]),
                    target_x-50, target_y-50,
                    player.x_pos - 50, player.y_pos - 50
                )
                arrows.append(new_arrow)

    # Cleanup
    cleanup()
