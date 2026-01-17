import random
from game_message import *


class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")
        self.exploration_targets = {}  # Track where each spore is heading
        self.spawner_created = False
        self.stationed_spores = set()  # Track spores that reached 10+ biomass and should stay put

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        NEW STRATEGY:
        1. Spread spores across map to accumulate biomass
        2. When spore reaches 300+ biomass, convert it to spawner
        3. Find spawner with most biomass at its tile
        4. Use that spawner to produce 10-biomass spores
        """
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        game_map = game_message.world.map
        
        # Step 1: Create initial spawner if we don't have one
        if len(my_team.spawners) == 0 and len(my_team.spores) > 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
            self.spawner_created = True
            return actions
        
        # Step 2: Convert spores with 100+ biomass into spawners (lowered from 300)
        spawner_positions = {(s.position.x, s.position.y) for s in my_team.spawners}
        for spore in my_team.spores:
            if spore.biomass >= 100:
                # Check if spawner already exists at this position
                if (spore.position.x, spore.position.y) not in spawner_positions:
                    # Game requires STRICTLY MORE than nextSpawnerCost (not equal)
                    if spore.biomass > my_team.nextSpawnerCost:
                        actions.append(SporeCreateSpawnerAction(sporeId=spore.id))
                        print(f"Converting spore with {spore.biomass} biomass into spawner #{len(my_team.spawners)+1} at ({spore.position.x}, {spore.position.y})")
                        return actions  # Return immediately after creating spawner
        
        # Step 3: ALL spawners produce one 10-biomass spore per tick
        # Prioritize spawners with more biomass at their tile (they're better defended)
        if len(my_team.spawners) > 0:
            # Sort spawners by biomass at their tile location (most biomass first)
            spawners_with_biomass = []
            for spawner in my_team.spawners:
                tile_biomass = game_message.world.biomassGrid[spawner.position.y][spawner.position.x]
                spawners_with_biomass.append((spawner, tile_biomass))
            
            # Sort by biomass (descending)
            spawners_with_biomass.sort(key=lambda x: x[1], reverse=True)
            
            # Track spawners used to avoid multiple actions
            spawners_used = set()
            
            # Each spawner produces ONE spore per tick (game rule: one action per entity)
            for spawner, tile_biomass in spawners_with_biomass:
                if spawner.id in spawners_used:
                    continue
                    
                # Only produce spores if tile has less than 100 biomass AND we have enough nutrients
                if tile_biomass < 100:
                    # Calculate how much biomass we can afford (use 50% of available nutrients, min 5)
                    desired_biomass = int(max(my_team.nutrients * 0.5, 5))
                    
                    # CRITICAL: Only produce if we have enough nutrients!
                    if my_team.nutrients >= desired_biomass:
                        actions.append(
                            SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=desired_biomass)
                        )
                        spawners_used.add(spawner.id)
                        my_team.nutrients -= desired_biomass  # Deduct the actual cost
                        print(f"Tick {game_message.tick}: Spawner at ({spawner.position.x}, {spawner.position.y}) producing spore with {desired_biomass} biomass (tile biomass: {tile_biomass}, nutrients left: {my_team.nutrients})")
                    else:
                        print(f"Tick {game_message.tick}: Spawner at ({spawner.position.x}, {spawner.position.y}) skipped - not enough nutrients ({my_team.nutrients} < {desired_biomass})")
                elif tile_biomass >= 100:
                    print(f"Tick {game_message.tick}: Spawner at ({spawner.position.x}, {spawner.position.y}) skipped - tile has {tile_biomass} biomass (>= 100)")
        
        # Step 4: Split large spores (500+ biomass) into two smaller spores
        spores_used = set()  # Track spores that have been used for actions
        for spore in my_team.spores:
            if spore.id in spores_used:
                continue
            
            # Split spores with 500+ biomass to spread resources better
            if spore.biomass >= 500:
                split_amount = spore.biomass // 2  # Split in half
                # Pick a random direction for the moving spore
                directions = [
                    Position(x=0, y=-1),  # up
                    Position(x=0, y=1),   # down
                    Position(x=-1, y=0),  # left
                    Position(x=1, y=0)    # right
                ]
                direction = random.choice(directions)
                actions.append(SporeSplitAction(
                    sporeId=spore.id, 
                    biomassForMovingSpore=split_amount,
                    direction=direction
                ))
                spores_used.add(spore.id)
                
                # CRITICAL: Clear the exploration target for this spore so it gets a new target next tick
                # The split will create a new spore at the original position and move the original spore
                if spore.id in self.exploration_targets:
                    del self.exploration_targets[spore.id]
                
                print(f"Tick {game_message.tick}: Splitting spore {spore.id} with {spore.biomass} biomass into two ({split_amount} each)")
                # Return immediately - one action per tick per entity
                # The split spores will get new movement targets on next tick
        
        # Step 5: Move ALL spores aggressively - don't station them, keep spreading!
        spawner_positions = {(s.position.x, s.position.y) for s in my_team.spawners}
        
        # ATTACK MODE: At tick 250+, focus on attacking enemies with biggest spores (MUCH earlier!)
        attack_mode = game_message.tick >= 250
        if attack_mode and len(my_team.spores) > 0:
            # Find our biggest spore
            biggest_spore = max(my_team.spores, key=lambda s: s.biomass)
            print(f"Tick {game_message.tick}: ATTACK MODE! Biggest spore has {biggest_spore.biomass} biomass - HUNTING ENEMIES!")
        
        for spore in my_team.spores:
            if spore.id in spores_used:
                continue
            
            # Keep all spores moving to spread across the map
            # Only stop spores that have 100+ biomass (they'll become spawners) BEFORE tick 250
            if spore.biomass >= 100 and not attack_mode:
                # These will become spawners in the next tick, so don't move them
                spores_used.add(spore.id)
                continue
            
            # CRITICAL: If spore is ON or very close to a spawner, force it to move away immediately!
            on_spawner = (spore.position.x, spore.position.y) in spawner_positions
            near_spawner = any(
                abs(spore.position.x - sx) <= 2 and abs(spore.position.y - sy) <= 2
                for sx, sy in spawner_positions
            )
            
            # Force new target if on/near spawner OR reached current target
            needs_new_target = (
                spore.id not in self.exploration_targets or
                on_spawner or
                near_spawner or
                (abs(spore.position.x - self.exploration_targets[spore.id].x) <= 1 and
                 abs(spore.position.y - self.exploration_targets[spore.id].y) <= 1)
            )
            
            if needs_new_target:
                target = self._get_spread_target(spore, game_map, game_message.world, my_team, attack_mode)
                self.exploration_targets[spore.id] = target
            else:
                target = self.exploration_targets[spore.id]
            
            actions.append(
                SporeMoveToAction(
                    sporeId=spore.id,
                    position=target
                )
            )
            spores_used.add(spore.id)
        
        return actions
    
    def _get_spread_target(self, spore: Spore, game_map: GameMap, world: GameWorld, my_team: TeamInfo, attack_mode: bool = False) -> Position:
        """
        Get a target position with AGGRESSIVE strategy.
        Goal: Attack enemy tiles and expand territory.
        """
        best_score = -1
        best_position = Position(
            x=random.randint(0, game_map.width - 1),
            y=random.randint(0, game_map.height - 1)
        )
        
        # Get our spawner positions to avoid sending spores there
        our_spawner_positions = {(spawner.position.x, spawner.position.y) for spawner in my_team.spawners}
        
        # Get ENEMY spawner positions - these are HIGH PRIORITY targets!
        enemy_spawner_positions = set()
        for spawner in world.spawners:
            if spawner.teamId != spore.teamId:
                enemy_spawner_positions.add((spawner.position.x, spawner.position.y))
        
        # IN ATTACK MODE: First, actively scan for ALL enemy tiles!
        enemy_tiles = []
        if attack_mode:
            for y in range(game_map.height):
                for x in range(game_map.width):
                    owner = world.ownershipGrid[y][x]
                    # Found an enemy tile!
                    if owner != spore.teamId and owner != "":
                        enemy_tiles.append((x, y, world.biomassGrid[y][x]))
            
            # If we found enemies, prioritize them!
            if len(enemy_tiles) > 0:
                print(f"ATTACK MODE: Found {len(enemy_tiles)} enemy tiles! Targeting them...")
                # In attack mode, check MORE enemy positions and include spawners!
                sample_size = min(50, len(enemy_tiles))  # Increased from 30 to 50
                enemy_sample = random.sample(enemy_tiles, sample_size)
                
                # ALWAYS include enemy spawners in the sample!
                for spawner_pos in enemy_spawner_positions:
                    if spawner_pos not in [(t[0], t[1]) for t in enemy_sample]:
                        enemy_sample.append((spawner_pos[0], spawner_pos[1], world.biomassGrid[spawner_pos[1]][spawner_pos[0]]))
        else:
            # Even in NORMAL mode, check for nearby enemies!
            enemy_sample = []
            for y in range(game_map.height):
                for x in range(game_map.width):
                    owner = world.ownershipGrid[y][x]
                    distance = abs(spore.position.x - x) + abs(spore.position.y - y)
                    # Found a nearby enemy tile!
                    if owner != spore.teamId and owner != "" and distance <= 15:
                        enemy_tiles.append((x, y, world.biomassGrid[y][x]))
            if len(enemy_tiles) > 0:
                sample_size = min(20, len(enemy_tiles))
                enemy_sample = random.sample(enemy_tiles, sample_size)
        
        # Determine what positions to check
        if len(enemy_tiles) > 0:
            # When enemies exist, check enemy positions + some random
            positions_to_check = enemy_sample + [
                (random.randint(0, game_map.width - 1), 
                 random.randint(0, game_map.height - 1),
                 0)  # dummy biomass for random positions
                for _ in range(10)
            ]
        else:
            # Normal mode or no enemies: random sampling
            positions_to_check = [
                (random.randint(0, game_map.width - 1), 
                 random.randint(0, game_map.height - 1),
                 0)
                for _ in range(20)
            ]
        
        for pos_data in positions_to_check:
            x, y = pos_data[0], pos_data[1]
            
            # CRITICAL: Skip tiles with our spawners - don't send biomass there!
            if (x, y) in our_spawner_positions:
                continue
            
            # Also heavily penalize tiles NEAR our spawners (within 3 tiles)
            near_our_spawner = any(
                abs(x - sx) <= 3 and abs(y - sy) <= 3
                for sx, sy in our_spawner_positions
            )
            
            nutrients = game_map.nutrientGrid[y][x]
            distance = abs(spore.position.x - x) + abs(spore.position.y - y)
            owner = world.ownershipGrid[y][x]
            tile_biomass = world.biomassGrid[y][x]
            
            # CRITICAL: Skip tiles with 0 nutrients - these are likely walls or impassable!
            if nutrients == 0 and owner == "" and tile_biomass == 0:
                continue  # This is a wall or blocked tile
            
            # Score calculation - AGGRESSIVE strategy
            score = 0
            
            # CRITICAL: Heavily penalize positions near our spawners (unless in attack mode)
            if near_our_spawner and not attack_mode:
                score -= 500  # Make these positions very unattractive
            
            # PRIORITY 0: Distance penalties - REDUCED in attack mode!
            if attack_mode:
                # In attack mode, much smaller distance penalty so we reach distant enemies
                if distance > 20:
                    score -= (distance - 20) * 2  # Only -2 per tile (was -10!)
            else:
                # Normal mode: heavy penalties to avoid walls
                if distance > 20:
                    score -= (distance - 20) * 10  # Big penalty for very far tiles
                elif distance > 10:
                    score -= (distance - 10) * 5  # Moderate penalty for far tiles
            
            # PRIORITY 1: Attack enemy tiles (not neutral, not ours)
            if owner != spore.teamId and owner != "":
                # SUPER CRITICAL: If this is an ENEMY SPAWNER, ULTRA HIGH PRIORITY!
                is_enemy_spawner = (x, y) in enemy_spawner_positions
                if is_enemy_spawner:
                    score += 3000  # ENEMY SPAWNER - DESTROY IT!!!
                    print(f"ENEMY SPAWNER DETECTED at ({x},{y}) with {tile_biomass} biomass - PRIORITY ATTACK!")
                    # If we can beat it, MASSIVE bonus
                    if tile_biomass < spore.biomass:
                        score += 2000  # We can destroy their spawner!
                
                # CRITICAL: If enemy is VERY close AND we can destroy it, MASSIVE priority!
                if distance <= 5 and tile_biomass < spore.biomass:
                    score += 2000  # INSTANT ATTACK! Close enemy we can destroy!
                    print(f"PRIORITY TARGET: Enemy at ({x},{y}) with {tile_biomass} biomass, distance {distance} - WE CAN DESTROY IT!")
                
                # AGGRESSIVE: Even if we can't FULLY destroy it, attack if we're stronger!
                if distance <= 8 and tile_biomass < spore.biomass * 0.8:
                    score += 1500  # We're much stronger - easy win!
                
                # In attack mode, MASSIVELY prioritize enemy attacks
                if attack_mode:
                    score += 1000  # EXTREMELY HIGH priority for enemy tiles in attack mode!
                    
                    # Prefer ANY enemy tile we can beat
                    if tile_biomass < spore.biomass:
                        score += 500  # We can definitely win this fight!
                        # Extra bonus for VERY close enemies
                        if distance <= 3:
                            score += 300  # Very close and winnable!
                    elif tile_biomass < spore.biomass * 1.5:
                        score += 400  # Good chance to win
                    elif tile_biomass < spore.biomass * 2:
                        score += 300  # Close fight, but worth trying
                    else:
                        score += 200  # Even tough fights are worth it in attack mode
                else:
                    score += 200  # Normal priority for enemy tiles
                    
                    # MUCH MORE AGGRESSIVE in normal mode too!
                    if tile_biomass < spore.biomass:
                        score += 300  # We can win this fight! (boosted from 150)
                        # Extra bonus for VERY close enemies in normal mode too
                        if distance <= 3:
                            score += 400  # Very close and winnable - take it! (boosted from 200)
                        elif distance <= 6:
                            score += 250  # Close and winnable
                    elif tile_biomass < spore.biomass * 1.5:
                        score += 200  # Close fight, but winnable (boosted from 100)
                    elif tile_biomass < spore.biomass * 2:
                        score += 100  # Worth trying even if tough
                    else:
                        score += 50  # Tough fight, but still worth attacking
            
            # PRIORITY 2: Claim neutral territory (lower priority in attack mode)
            elif owner != spore.teamId:
                if attack_mode:
                    score += 10  # Very low priority in attack mode - FOCUS ON ENEMIES!
                else:
                    score += 80  # Normal expansion mode
            
            # Prefer close, accessible tiles over far nutrient-rich tiles
            # This prevents going through walls
            if attack_mode:
                # In attack mode, distance to enemies matters more than nutrients
                if owner != spore.teamId and owner != "":
                    score += max(0, 50 - distance)  # Closer enemies = better
                score += nutrients * 0.3  # Nutrients matter much less in attack mode
            else:
                # In expansion mode, prefer CLOSE nutrient-rich tiles
                # Boost score for tiles that are both close AND have nutrients
                if distance < 10:
                    score += nutrients * 3  # Triple bonus for close nutrient tiles!
                elif distance < 20:
                    score += nutrients * 1.5  # Good bonus for medium distance
                else:
                    score += nutrients * 0.5  # Low bonus for far tiles (likely blocked)
            
            if score > best_score:
                best_score = score
                best_position = Position(x=x, y=y)
        
        return best_position