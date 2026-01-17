import random
from game_message import *


class Bot:
    def __init__(self):
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
            return actions  # Return immediately to create the spawner
        
        # Initialize spawner line positions on first run
        if not self.spawner_line_created:
            self._create_spawner_line_plan(game_map)
            self.spawner_line_created = True
        
        # Step 1: Identify the most protected spawners and produce more spores from them
        protected_spawners = self._get_protected_spawners(my_team, game_message.world)
        
        # Early game (first 100 ticks): DEFENSE mode - create small defensive spores
        early_game = game_message.tick < 100
        # Mid game (100-500): Build and explore
        mid_game = game_message.tick >= 100 and game_message.tick < 500
        # Late game (500+): ATTACK mode
        attack_mode = game_message.tick >= 500
        
        # Produce spores with different strategies per phase
        for spawner in my_team.spawners:
            # Check if this spawner is well-protected
            is_protected = spawner.id in [s.id for s in protected_spawners]
            
            # EARLY GAME (0-100): Create MANY small defensive spores (15-20 biomass)
            if early_game:
                if my_team.nutrients >= 15:
                    # Create small defensive spores
                    defensive_biomass = 15 if my_team.nutrients < 25 else 20
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=defensive_biomass)
                    )
                    my_team.nutrients -= defensive_biomass
                    
                    # Protected spawners create 2 defensive spores
                    if is_protected and my_team.nutrients >= 15:
                        actions.append(
                            SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=15)
                        )
                        print(f"Tick {game_message.tick}: Protected spawner creating DEFENSIVE spore!")
                        my_team.nutrients -= 15
            
            # MID GAME (100-500): Normal exploration and building
            elif mid_game:
                if is_protected and my_team.nutrients >= 50:
                    # Protected spawners: double production
                    biomass = 30 if my_team.nutrients >= 30 else 25
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=biomass)
                    )
                    my_team.nutrients -= biomass
                    
                    # Second spore
                    if my_team.nutrients >= 30:
                        actions.append(
                            SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=30)
                        )
                        my_team.nutrients -= 30
                else:
                    # Regular production
                    if my_team.nutrients >= 25:
                        biomass = 30 if my_team.nutrients >= 30 else 25
                        actions.append(
                            SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=biomass)
                        )
                        my_team.nutrients -= biomass
                
                # Builder spores - MORE aggressive spawner creation!
                if my_team.nutrients >= 70 and len(my_team.spawners) < 15:
                    spawner_biomass = min(80, my_team.nutrients)
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=spawner_biomass)
                    )
                    my_team.nutrients -= spawner_biomass
            
            # LATE GAME (500+): ATTACK mode
            elif attack_mode:
                if is_protected and my_team.nutrients >= 50:
                    # Protected spawners create attack spores
                    if my_team.nutrients >= 150:
                        attack_biomass = min(200, my_team.nutrients)
                        actions.append(
                            SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=attack_biomass)
                        )
                        print(f"Tick {game_message.tick}: PROTECTED spawner producing ATTACK spore ({attack_biomass} biomass)!")
                        my_team.nutrients -= attack_biomass
                        continue
                    
                    # Regular production
                    biomass = 30
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=biomass)
                    )
                    my_team.nutrients -= biomass
                else:
                    # Regular spawners create attack spores
                    if my_team.nutrients >= 150 and len(my_team.spores) < 20:
                        attack_biomass = min(200, my_team.nutrients)
                        if attack_biomass >= 150:
                            actions.append(
                                SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=attack_biomass)
                            )
                            my_team.nutrients -= attack_biomass
                            continue
                    
                    # Regular production
                    if my_team.nutrients >= 25:
                        biomass = 30 if my_team.nutrients >= 30 else 25
                        actions.append(
                            SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=biomass)
                        )
                        my_team.nutrients -= biomass
        
        target_spawner_count = min(15, len(self.spawner_line_positions))  # Increased to 15 spawners
        
        for spore in my_team.spores[:]:  # Use slice to avoid modifying list during iteration
            if len(my_team.spawners) >= target_spawner_count:
                break  # We have enough spawners - focus on exploration!
            
            # Create spawners from spores with 70+ biomass (lowered threshold)
            if spore.biomass >= 70 and spore.biomass >= my_team.nextSpawnerCost:
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
                if near_planned_position or len(my_team.spawners) < 8:
                    actions.append(SporeCreateSpawnerAction(sporeId=spore.id))
                    self.spores_assigned_to_spawners.add(spore.id)
                    continue  # Skip movement for this spore
        
        # Step 3: Move spores - Phase-based strategy!
        early_game = game_message.tick < 100
        mid_game = game_message.tick >= 100 and game_message.tick < 500
        attack_mode = game_message.tick >= 500
        
        for spore in my_team.spores:
            if spore.id in self.spores_assigned_to_spawners:
                continue  # This spore is becoming a spawner
            
            # EARLY GAME (0-100): Small defensive spores stay near spawners, but attack nearby threats!
            if early_game and spore.biomass <= 25:
                # Find nearest spawner
                nearest_spawner = None
                nearest_dist = float('inf')
                for spawner in my_team.spawners:
                    dist = abs(spore.position.x - spawner.position.x) + abs(spore.position.y - spawner.position.y)
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest_spawner = spawner
                
                # Check for nearby enemies to attack (priority targets)
                nearby_enemy = None
                for team in game_message.world.teamInfos.values():
                    if team.teamId == my_team.teamId or team.teamId == game_message.constants.neutralTeamId:
                        continue
                    
                    # Check enemy spores
                    for enemy_spore in team.spores:
                        dist = abs(spore.position.x - enemy_spore.position.x) + abs(spore.position.y - enemy_spore.position.y)
                        if dist <= 8:  # Within 8 tiles
                            nearby_enemy = enemy_spore.position
                            break
                    
                    if nearby_enemy:
                        break
                
                # Attack nearby enemies OR patrol near spawner
                if nearby_enemy and spore.biomass >= 15:
                    # Attack nearby enemy!
                    actions.append(
                        SporeMoveToAction(
                            sporeId=spore.id,
                            position=nearby_enemy
                        )
                    )
                elif nearest_spawner and nearest_dist > 8:
                    # Too far from spawner, move back to defensive position
                    actions.append(
                        SporeMoveToAction(
                            sporeId=spore.id,
                            position=nearest_spawner.position
                        )
                    )
                else:
                    # Patrol near spawner (explore a bit but stay close)
                    patrol_x = nearest_spawner.position.x + random.randint(-6, 6) if nearest_spawner else spore.position.x + random.randint(-3, 3)
                    patrol_y = nearest_spawner.position.y + random.randint(-6, 6) if nearest_spawner else spore.position.y + random.randint(-3, 3)
                    patrol_x = max(0, min(game_map.width - 1, patrol_x))
                    patrol_y = max(0, min(game_map.height - 1, patrol_y))
                    
                    actions.append(
                        SporeMoveToAction(
                            sporeId=spore.id,
                            position=Position(x=patrol_x, y=patrol_y)
                        )
                    )
            
            # MID GAME (100-500): Heavy spores build spawners, light spores explore
            elif mid_game:
                if spore.biomass >= 70 and len(my_team.spawners) < target_spawner_count:
                    # Heavy spore - move to spawner positions
                    target = self._find_best_spawner_position(spore, my_team, game_map, game_message.world)
                    
                    actions.append(
                        SporeMoveToAction(
                            sporeId=spore.id,
                            position=target
                        )
                    )
                else:
                    # ALL other spores - EXPLORE AND CONQUER!
                    target = self._find_exploration_target(spore, game_map, game_message.world, my_team, game_message)
                    
                    actions.append(
                        SporeMoveToAction(
                            sporeId=spore.id,
                            position=target
                        )
                    )
            
            # LATE GAME (500+): ATTACK MODE - all spores become aggressive!
            elif attack_mode:
                # Heavy spores (150+ biomass) specifically target enemy SPAWNERS
                if spore.biomass >= 150:
                    target = self._find_enemy_spawner_target(spore, game_message.world, my_team, game_message)
                    
                    actions.append(
                        SporeMoveToAction(
                            sporeId=spore.id,
                            position=target
                        )
                    )
                else:
                    # Light spores attack enemy TERRITORY and spores
                    target = self._find_enemy_target(spore, game_message.world, my_team, game_message)
                    
                    actions.append(
                        SporeMoveToAction(
                            sporeId=spore.id,
                            position=target
                        )
                    )

        
        return actions
    
    def _create_spawner_line_plan(self, game_map: GameMap):
        """
        Plan spawner positions in a DEFENSIVE LINE - close together for mutual protection!
        Creates a tight cluster in the center for maximum defense.
        """
        print("Creating DEFENSIVE spawner line...")
        
        # Create a defensive cluster in the center of the map
        center_x = game_map.width // 2
        center_y = game_map.height // 2
        
        # Create spawners in a TIGHT formation (3-4 tiles apart)
        defensive_spacing = 3  # Close together for defense!
        
        # Create a defensive line horizontally across the center
        for offset in range(-9, 10, defensive_spacing):
            x = max(2, min(game_map.width - 3, center_x + offset))
            self.spawner_line_positions.append(Position(x=x, y=center_y))
        
        # Add a second defensive line above
        for offset in range(-9, 10, defensive_spacing):
            x = max(2, min(game_map.width - 3, center_x + offset))
            y = max(2, center_y - 4)
            self.spawner_line_positions.append(Position(x=x, y=y))
        
        # Add a third defensive line below
        for offset in range(-9, 10, defensive_spacing):
            x = max(2, min(game_map.width - 3, center_x + offset))
            y = min(game_map.height - 3, center_y + 4)
            self.spawner_line_positions.append(Position(x=x, y=y))
        
        print(f"Planned {len(self.spawner_line_positions)} spawner positions in DEFENSIVE formation!")
    
    def _get_protected_spawners(self, my_team: TeamInfo, world: GameWorld) -> list[Spawner]:
        """
        Identify spawners that are well-protected (have other spawners nearby).
        These spawners should produce MORE spores!
        """
        protected = []
        
        for spawner in my_team.spawners:
            nearby_spawner_count = 0
            
            # Count how many friendly spawners are nearby (within 5 tiles)
            for other_spawner in my_team.spawners:
                if spawner.id == other_spawner.id:
                    continue
                
                distance = abs(spawner.position.x - other_spawner.position.x) + abs(spawner.position.y - other_spawner.position.y)
                
                if distance <= 5:
                    nearby_spawner_count += 1
            
            # If spawner has 2+ nearby spawners, it's well-protected!
            if nearby_spawner_count >= 2:
                protected.append(spawner)
        
        return protected
    
    
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
    
    def _find_enemy_spawner_target(self, spore: Spore, world: GameWorld, my_team: TeamInfo, game_message: TeamGameState) -> Position:
        """
        Find enemy spawners to attack and destroy! (After tick 500)
        Only send spores with 150-200 biomass to attack.
        """
        best_score = -999999
        best_target = Position(x=spore.position.x, y=spore.position.y)
        
        # Look for all enemy spawners
        enemy_spawners = []
        for spawner in world.spawners:
            if spawner.teamId != my_team.teamId and spawner.teamId != game_message.constants.neutralTeamId:
                enemy_spawners.append(spawner)
        
        if len(enemy_spawners) == 0:
            # No enemy spawners found - just explore
            return self._find_exploration_target(spore, world.map, world, my_team, game_message)
        
        # Evaluate each enemy spawner
        for enemy_spawner in enemy_spawners:
            distance = abs(spore.position.x - enemy_spawner.position.x) + abs(spore.position.y - enemy_spawner.position.y)
            
            # Check the biomass at the spawner position
            spawner_biomass = world.biomassGrid[enemy_spawner.position.y][enemy_spawner.position.x]
            
            # Score calculation
            score = 0
            
            # HUGE bonus for enemy spawners - this is our target!
            score += 500
            
            # Prefer closer spawners
            score -= distance * 2
            
            # Only attack if we have enough biomass (don't send more than 200)
            if spore.biomass >= spawner_biomass:
                score += 200  # We can win this fight!
            elif spore.biomass >= spawner_biomass * 0.8:
                score += 100  # Close fight, but worth it
            else:
                score -= 300  # Too risky
            
            # Prefer spawners with less biomass (easier to conquer)
            score -= spawner_biomass * 0.5
            
            if score > best_score:
                best_score = score
                best_target = enemy_spawner.position
        
        return best_target
    
    def _find_enemy_target(self, spore: Spore, world: GameWorld, my_team: TeamInfo, game_message: TeamGameState) -> Position:
        """
        Find enemy territory, spores, or any enemy assets to attack!
        Used by light spores after tick 500.
        """
        best_score = -999999
        best_target = Position(x=spore.position.x, y=spore.position.y)
        
        # First, look for enemy SPORES nearby
        enemy_spores = []
        for enemy_spore in world.spores:
            if enemy_spore.teamId != my_team.teamId and enemy_spore.teamId != game_message.constants.neutralTeamId:
                enemy_spores.append(enemy_spore)
        
        # Target enemy spores if we can beat them
        for enemy_spore in enemy_spores:
            distance = abs(spore.position.x - enemy_spore.position.x) + abs(spore.position.y - enemy_spore.position.y)
            
            # Only consider nearby enemies (within 15 tiles)
            if distance > 15:
                continue
            
            score = 0
            
            # Bonus for targeting enemy spores
            score += 300
            
            # Prefer closer enemies
            score -= distance * 3
            
            # Only attack if we can win
            if spore.biomass > enemy_spore.biomass:
                score += 250  # We can destroy them!
            elif spore.biomass >= enemy_spore.biomass * 0.9:
                score += 100  # Close fight
            else:
                score -= 500  # Don't attack, we'll lose
            
            if score > best_score:
                best_score = score
                best_target = enemy_spore.position
        
        # If no good spore targets, look for enemy TERRITORY with high biomass
        if best_score < 100:
            # Sample enemy territory positions
            for _ in range(25):
                x = random.randint(0, world.map.width - 1)
                y = random.randint(0, world.map.height - 1)
                
                owner = world.ownershipGrid[y][x]
                
                # Only target enemy-owned tiles
                if owner == my_team.teamId or owner == game_message.constants.neutralTeamId:
                    continue
                
                biomass = world.biomassGrid[y][x]
                nutrients = world.map.nutrientGrid[y][x]
                distance = abs(spore.position.x - x) + abs(spore.position.y - y)
                
                score = 0
                
                # ATTACK enemy territory!
                score += 200
                
                # Prefer high-value enemy tiles
                score += biomass * 2  # More biomass = more valuable
                score += nutrients * 10  # High nutrient tiles
                
                # Prefer closer tiles
                score -= distance * 1.5
                
                # Prefer tiles we can conquer
                if spore.biomass > biomass:
                    score += 150
                
                if score > best_score:
                    best_score = score
                    best_target = Position(x=x, y=y)
        
        # If still no good target, fall back to exploration
        if best_score < 0:
            return self._find_exploration_target(spore, world.map, world, my_team, game_message)
        
        return best_target
