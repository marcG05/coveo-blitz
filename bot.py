import random
from game_message import *


class Bot:
    def __init__(self):
        print("Initializing SPAWNER LINE STRATEGY bot")
        self.spawner_line_positions = []  # Track target positions for spawners
        self.spawner_line_created = False
        self.spores_assigned_to_spawners = set()  # Track which spores are going to create spawners

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        SPAWNER LINE STRATEGY: Create a line of spawners across the map and pump massive nutrients into them.
        Focus on spawner production over spore movement.
        """
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        game_map = game_message.world.map
        
        print(f"Tick {game_message.tick}: Nutrients: {my_team.nutrients}, Spores: {len(my_team.spores)}, Spawners: {len(my_team.spawners)}, Next Spawner Cost: {my_team.nextSpawnerCost}")
        
        # CRITICAL: Create initial spawner if we have zero spawners!
        if len(my_team.spawners) == 0 and len(my_team.spores) > 0:
            # Create spawner from the first spore immediately
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
            print(f"Tick {game_message.tick}: CREATING INITIAL SPAWNER!")
            return actions  # Return immediately to create the spawner
        
        # Initialize spawner line positions on first run
        if not self.spawner_line_created:
            self._create_spawner_line_plan(game_map)
            self.spawner_line_created = True
        
        # Step 1: Produce spores from ALL spawners
        # Focus on quantity over quality - more spores = more map control
        max_biomass = 100 if game_message.tick < 500 else 150  # Even after tick 500, keep it reasonable
        
        # Prioritize creating MANY spores rather than few heavy ones
        for spawner in my_team.spawners:
            # Always try to produce at least one spore per spawner if we have nutrients
            if my_team.nutrients >= 25:
                # Light spores for exploration and combat (25-40 biomass)
                if my_team.nutrients >= 100:
                    # We're rich - create multiple spores
                    biomass = 30  # Light and fast
                elif my_team.nutrients >= 50:
                    biomass = 30
                elif my_team.nutrients >= 25:
                    biomass = 25
                else:
                    continue
                
                actions.append(
                    SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=biomass)
                )
                print(f"Tick {game_message.tick}: Spawner producing spore with {biomass} biomass")
                my_team.nutrients -= biomass
            
            # If we still have lots of nutrients, produce another spore for spawner building
            if my_team.nutrients >= 80 and len(my_team.spawners) < 10:
                spawner_biomass = min(80, my_team.nutrients)
                actions.append(
                    SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=spawner_biomass)
                )
                print(f"Tick {game_message.tick}: Spawner producing BUILDER spore with {spawner_biomass} biomass")
                my_team.nutrients -= spawner_biomass
        
        # Step 2: Convert spores to spawners ONLY if we really need more spawners
        target_spawner_count = min(8, len(self.spawner_line_positions))  # Reduced from 15 to 8 spawners max
        
        for spore in my_team.spores[:]:  # Use slice to avoid modifying list during iteration
            if len(my_team.spawners) >= target_spawner_count:
                break  # We have enough spawners - focus on exploration!
            
            # Only create spawners from spores with 80+ biomass
            if spore.biomass >= 80 and spore.biomass >= my_team.nextSpawnerCost:
                # Check if there's already a spawner at this exact position
                spawner_at_position = False
                for spawner in my_team.spawners:
                    if spawner.position.x == spore.position.x and spawner.position.y == spore.position.y:
                        spawner_at_position = True
                        break
                
                if spawner_at_position:
                    # This spore is at a spawner, don't try to create another one
                    continue
                
                # Find if spore is near a planned spawner position
                near_planned_position = False
                for planned_pos in self.spawner_line_positions:
                    if abs(spore.position.x - planned_pos.x) <= 3 and abs(spore.position.y - planned_pos.y) <= 3:
                        near_planned_position = True
                        break
                
                # Create spawner if near a good position or if we have very few spawners
                if near_planned_position or len(my_team.spawners) < 5:
                    actions.append(SporeCreateSpawnerAction(sporeId=spore.id))
                    print(f"Tick {game_message.tick}: Converting spore {spore.id} to SPAWNER (cost: {my_team.nextSpawnerCost})")
                    self.spores_assigned_to_spawners.add(spore.id)
                    continue  # Skip movement for this spore
        
        # Step 3: Move spores - MOST spores explore and conquer, only heavy ones build spawners
        for spore in my_team.spores:
            if spore.id in self.spores_assigned_to_spawners:
                continue  # This spore is becoming a spawner
            
            # Decide role based on biomass - most spores should explore!
            if spore.biomass >= 70 and len(my_team.spawners) < target_spawner_count:
                # Heavy spore - move to spawner positions (only if we need more spawners)
                target = self._find_best_spawner_position(spore, my_team, game_map, game_message.world)
                
                actions.append(
                    SporeMoveToAction(
                        sporeId=spore.id,
                        position=target
                    )
                )
                
                if game_message.tick % 20 == 0:
                    print(f"Tick {game_message.tick}: Heavy spore moving to spawner position ({target.x}, {target.y})")
            else:
                # ALL other spores - EXPLORE AND CONQUER!
                target = self._find_exploration_target(spore, game_map, game_message.world, my_team, game_message)
                
                actions.append(
                    SporeMoveToAction(
                        sporeId=spore.id,
                        position=target
                    )
                )
                
                if game_message.tick % 20 == 0:
                    print(f"Tick {game_message.tick}: Spore exploring/conquering to ({target.x}, {target.y})")
        
        return actions
    
    def _create_spawner_line_plan(self, game_map: GameMap):
        """
        Plan spawner positions in a line across the map.
        Creates positions on both sides (left and right edges).
        """
        print("Creating spawner line plan...")
        
        # Create spawners along the left edge (x = 10% of map width)
        left_x = max(2, game_map.width // 10)
        # Create spawners along the right edge (x = 90% of map width)
        right_x = min(game_map.width - 3, (game_map.width * 9) // 10)
        # Create spawners along the middle
        middle_x = game_map.width // 2
        
        # Space spawners evenly along Y axis
        spacing = max(3, game_map.height // 8)  # About 8 spawners per line
        
        for y in range(spacing // 2, game_map.height, spacing):
            # Left side spawner
            self.spawner_line_positions.append(Position(x=left_x, y=y))
            # Middle spawner
            self.spawner_line_positions.append(Position(x=middle_x, y=y))
            # Right side spawner
            self.spawner_line_positions.append(Position(x=right_x, y=y))
        
        print(f"Planned {len(self.spawner_line_positions)} spawner positions across the map")
    
    def _find_best_spawner_position(self, spore: Spore, my_team: TeamInfo, game_map: GameMap, world: GameWorld) -> Position:
        """
        Find the best position for a spore to move toward to eventually create a spawner.
        Prioritizes high-nutrient areas along the spawner line.
        """
        best_score = -999999
        best_position = self.spawner_line_positions[0] if self.spawner_line_positions else Position(x=game_map.width // 2, y=game_map.height // 2)
        
        # Check each planned spawner position
        for pos in self.spawner_line_positions:
            # Skip if there's already a spawner very close
            too_close_to_existing = False
            for spawner in my_team.spawners:
                if abs(spawner.position.x - pos.x) <= 2 and abs(spawner.position.y - pos.y) <= 2:
                    too_close_to_existing = True
                    break
            
            if too_close_to_existing:
                continue
            
            # Calculate score based on:
            # 1. Distance from spore (prefer closer)
            # 2. Nutrient value at that position
            # 3. Whether it's not owned by us yet
            
            distance = abs(spore.position.x - pos.x) + abs(spore.position.y - pos.y)
            
            # Ensure position is within bounds
            safe_x = max(0, min(pos.x, game_map.width - 1))
            safe_y = max(0, min(pos.y, game_map.height - 1))
            
            nutrients = game_map.nutrientGrid[safe_y][safe_x]
            owner = world.ownershipGrid[safe_y][safe_x]
            
            score = -distance * 2  # Prefer closer positions
            score += nutrients * 10  # HEAVILY prioritize high-nutrient tiles
            
            # Bonus for unowned territory
            if owner != spore.teamId:
                score += 50
            
            if score > best_score:
                best_score = score
                best_position = Position(x=safe_x, y=safe_y)
        
        return best_position
    
    def _find_exploration_target(self, spore: Spore, game_map: GameMap, world: GameWorld, my_team: TeamInfo, game_message: TeamGameState) -> Position:
        """
        Find exploration targets for spores to claim territory and CONQUER ENEMIES!
        Prioritizes enemy territory and high-nutrient tiles.
        """
        best_score = -999999
        best_position = Position(
            x=random.randint(0, game_map.width - 1),
            y=random.randint(0, game_map.height - 1)
        )
        
        # Sample MORE positions to find better targets (20 instead of 15)
        for _ in range(20):
            x = random.randint(0, game_map.width - 1)
            y = random.randint(0, game_map.height - 1)
            
            nutrients = game_map.nutrientGrid[y][x]
            distance = abs(spore.position.x - x) + abs(spore.position.y - y)
            owner = world.ownershipGrid[y][x]
            current_biomass = world.biomassGrid[y][x]
            
            # Score calculation - AGGRESSIVE!
            score = nutrients * 8  # Nutrients are very valuable
            score -= distance * 1.0  # Prefer closer tiles but willing to travel far
            
            # HEAVILY prefer enemy territory over neutral
            if owner != spore.teamId and owner != game_message.constants.neutralTeamId:
                score += 100  # HUGE bonus for enemy tiles - ATTACK!
            elif owner == game_message.constants.neutralTeamId:
                score += 50  # Still good bonus for neutral tiles
            
            # Prefer tiles we can conquer (low biomass or we have more)
            if current_biomass < spore.biomass:
                score += 40  # We can win this fight!
            
            # Bonus for high-value targets
            if nutrients >= 3:
                score += 30  # High nutrient tiles are worth fighting for
            
            # Don't waste time too close to our spawners (let them handle local area)
            too_close_to_spawner = False
            for spawner in my_team.spawners:
                if abs(spawner.position.x - x) <= 3 and abs(spawner.position.y - y) <= 3:
                    too_close_to_spawner = True
                    break
            
            if too_close_to_spawner:
                score -= 30  # Small penalty, not huge
            
            if score > best_score:
                best_score = score
                best_position = Position(x=x, y=y)
        
        return best_position
