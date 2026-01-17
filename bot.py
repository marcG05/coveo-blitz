import random
from game_message import *

CONVERING = 0
ATTACK = 1
DEFEND = 2
LISTSPORE = 3

class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")
        self.exploration_targets = {}  
        self.spawner_created = False
        self.defense_list : list[Spore] = []
        self.defense_list_id : list[str] = []
        self.highestSpore : Spore = None
        self.newDefensePosition : Position = None
        self.tenHighest : list[str] = []
        self.state = CONVERING
        self.last_positions = {} 

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        game_map = game_message.world.map
        world = game_message.world
        
        # We use a set for O(1) lookup to ensure NO spore is called twice
        alreadyPlayed_id = set()
        
        # --- PHASE 1: SPAWNER PRODUCTION & INITIAL SETUP ---
        if len(my_team.spawners) == 0 and len(my_team.spores) > 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
            alreadyPlayed_id.add(my_team.spores[0].id)
            self.spawner_created = True
        elif game_message.tick % 300 == 0 and len(my_team.spawners) < 5 and len(my_team.spores) > 1:
            # Create extra spawners periodically
            spore_to_use = my_team.spores[-1]
            if spore_to_use.id not in alreadyPlayed_id:
                actions.append(SporeCreateSpawnerAction(sporeId=spore_to_use.id))
                alreadyPlayed_id.add(spore_to_use.id)
        
        if len(my_team.spawners) > 0 and my_team.nutrients >= 10:
            for spawner in my_team.spawners:
                actions.append(SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=10))
                break 

        # --- PHASE 2: ATTACK STATE SELECTION ---
        if game_message.tick > 200 and len(my_team.spores) > 10:
            self.state = ATTACK
            
            # Identify "Cible" (Enemy Spawner)
            spawn_pos = None
            for g in world.spawners:
                if g.teamId != my_team.teamId:
                    spawn_pos = g.position
                    break
            
            if spawn_pos:
                # Select top 4 strongest spores not yet used
                available = [s for s in my_team.spores if s.id not in alreadyPlayed_id]
                available.sort(key=lambda x: x.biomass, reverse=True)
                for r in available[:4]:
                    actions.append(SporeMoveToAction(sporeId=r.id, position=spawn_pos))
                    alreadyPlayed_id.add(r.id)
        
        if len(my_team.spores) > 12:
            self.state = LISTSPORE

        # --- PHASE 3: MAIN SPORE LOOP (CONVERGING / EXPLORATION) ---
        for index, spore in enumerate(my_team.spores):
            # CRITICAL: Check if spore was already called in Phase 1 or 2
            if spore.id in alreadyPlayed_id:
                continue

            # 1. Expand/Split if heavy
            if spore.biomass > 20:
                valid_dir = self.get_valid_direction(spore, game_map)
                actions.append(SporeSplitAction(spore.id, 10, valid_dir))
                alreadyPlayed_id.add(spore.id)
                continue

            # 2. Strategic Nutrient-Path Movement
            if self.state in [CONVERING, LISTSPORE]: 
                role = index % 3 

                # Target Management
                if spore.id not in self.exploration_targets:
                    self.exploration_targets[spore.id] = self._get_exploration_target(spore, game_map, world, self.exploration_targets, mode=role)
                
                target = self.exploration_targets[spore.id]
                
                # If target reached, pick a new one
                if abs(spore.position.x - target.x) <= 1 and abs(spore.position.y - target.y) <= 1:
                    target = self._get_exploration_target(spore, game_map, world, self.exploration_targets, mode=role)
                    self.exploration_targets[spore.id] = target

                # Path Calculation: Avoid high biomass, seek nutrients
                best_step = self._get_nutrient_path_step(spore, target, world)

                if best_step:
                    self.last_positions[spore.id] = Position(x=spore.position.x, y=spore.position.y)
                    actions.append(SporeMoveAction(sporeId=spore.id, direction=best_step))
                    alreadyPlayed_id.add(spore.id)

        print(f"STATE {self.state} | Spores Active: {len(alreadyPlayed_id)}")
        return actions

    def _get_nutrient_path_step(self, spore: Spore, target: Position, world: GameWorld) -> Position:
        """Finds the best 1-tile move that prioritizes nutrients and avoids biomass."""
        options = [Position(x=1, y=0), Position(x=-1, y=0), Position(x=0, y=1), Position(x=0, y=-1)]
        best_step = None
        min_score = float('inf')
        last_pos = self.last_positions.get(spore.id)

        for opt in options:
            nx, ny = spore.position.x + opt.x, spore.position.y + opt.y
            
            if not (0 <= nx < world.map.width and 0 <= ny < world.map.height):
                continue
            if last_pos and nx == last_pos.x and ny == last_pos.y:
                continue 

            cell_biomass = world.biomassGrid[ny][nx]
            cell_owner = world.ownershipGrid[ny][nx]
            nutrients = world.map.nutrientGrid[ny][nx]
            
            # SCORING: 
            # High Biomass = Huge penalty
            # Nutrients = Bonus (negative cost)
            # Distance = Standard cost
            step_cost = (cell_biomass * 100) if cell_owner != world.teamInfos[spore.teamId].teamId else 0
            nutrient_bonus = nutrients * 50
            dist_to_target = abs(nx - target.x) + abs(ny - target.y)

            current_score = step_cost - nutrient_bonus + dist_to_target

            if current_score < min_score:
                min_score = current_score
                best_step = opt
        return best_step

    def _get_exploration_target(self, spore: Spore, game_map: GameMap, world: GameWorld, current_targets: dict, mode: int = 0) -> Position:
        best_score = -float('inf')
        best_position = spore.position 
        taken_positions = [(p.x, p.y) for p in current_targets.values()]

        for _ in range(100):
            x = random.randint(0, game_map.width - 1)
            y = random.randint(0, game_map.height - 1)
            if (x, y) in taken_positions: continue

            target_biomass = world.biomassGrid[y][x]
            target_owner = world.ownershipGrid[y][x]
            nutrients = game_map.nutrientGrid[y][x]
            distance = abs(spore.position.x - x) + abs(spore.position.y - y)
            
            if target_owner != spore.teamId and target_biomass >= spore.biomass:
                continue

            # Standardized scoring for modes
            if mode == 1: # Attack
                score = (nutrients * 1000) / (target_biomass + 2) - (distance * 5)
            elif mode == 2: # Spread
                score = 1000 - (target_biomass * 50) - (distance * 10)
            else: # Nutrients
                score = (nutrients * 1000) - (target_biomass * 100) - (distance * 10)

            if score > best_score:
                best_score = score
                best_position = Position(x=x, y=y)
        return best_position

    def get_valid_direction(self, spore: Spore, game_map: GameMap) -> Position:
        possible_dirs = [Position(0, -1), Position(0, 1), Position(-1, 0), Position(1, 0)]
        random.shuffle(possible_dirs)
        for d in possible_dirs:
            target_x, target_y = spore.position.x + d.x, spore.position.y + d.y
            if 0 <= target_x < game_map.width and 0 <= target_y < game_map.height:
                return d
        return Position(0, 0)

    def spawner_exists_at(self, y: int, x: int, world: GameWorld) -> bool:
        for spawner in world.spawners:
            if spawner.position.y == y and spawner.position.x == x:
                return True
        return False