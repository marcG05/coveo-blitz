import random
from game_message import *


class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")
        self.exploration_targets = {}  # Track where each spore is heading
        self.spawner_created = False
        self.defenseSpore : Spore = None
        self.defense_spores : list[Spore] = []

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        Starter bot that moves spores across the map to explore and claim territory.
        """
        use_spores_list : list[Spore] = []
        
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        game_map = game_message.world.map
        
        # Strategy: Create one spawner, then produce spores and explore the map
        
        # Step 1: Create initial spawner if we don't have one
        if len(my_team.spawners) == 0 and len(my_team.spores) > 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
            self.spawner_created = True
            print(f"Tick {game_message.tick}: Creating spawner")
        elif game_message.tick % 200 == 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[-1].id))
        
        # Step 2: Produce new spores if we have nutrients and few spores
        elif len(my_team.spawners) > 0:
            # Only produce if we have enough nutrients
            if my_team.nutrients >= 20 and game_message.tick % 25 == 0:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=20)
                    )
                    print(f"Tick {game_message.tick}: Producing spore from spawner")
                    break  # Produce one at a time
        
        # Step 3: Move all spores to explore the map
        if len(my_team.spores) > 4 and self.defenseSpore != None:
            use_spores_list = my_team.spores
            multipler = 0.3
            actions.append(
                SporeSplitAction(self.defenseSpore.id, int(self.defenseSpore.biomass*multipler), Position(0,1))
            )
            if my_team.spores[-1] not in self.defense_spores:
                self.defense_spores.append(my_team.spores[-1])

        else:
            use_spores_list = my_team.spores

        #bouger spore
        highSpore = 0
        for spore in use_spores_list:
            if spore == self.defenseSpore:
                print("HIGHEST SPORE : IGNORED")
                continue
            if spore in self.defense_spores:
                print("DEFENSE SPORE : IGNORED")
                continue

            if spore.biomass > highSpore:
                highSpore = spore.biomass
                self.defenseSpore = spore
            # Check if spore reached its target or doesn't have one
            if spore.id not in self.exploration_targets:
                # Assign a new exploration target
                target = self._get_exploration_target(spore, game_map, game_message.world)
                self.exploration_targets[spore.id] = target
            else:
                target = self.exploration_targets[spore.id]
                # Check if we reached the target (within 1 tile)
                if abs(spore.position.x - target.x) <= 1 and abs(spore.position.y - target.y) <= 1:
                    # Get a new target
                    target = self._get_exploration_target(spore, game_map, game_message.world)
                    self.exploration_targets[spore.id] = target
            
            # Move towards target
            actions.append(
                SporeMoveToAction(
                    sporeId=spore.id,
                    position=target
                )
            )
            print(f"Tick {game_message.tick}: Moving spore {spore.id} to ({target.x}, {target.y})")

        

        
        return actions
    
    def _get_exploration_target(self, spore: Spore, game_map: GameMap, world: GameWorld) -> Position:
        """
        Get a strategic exploration target for the spore.
        Prioritizes high-nutrient tiles and unexplored areas.
        """
        # Strategy: Look for high-nutrient tiles that are not owned by us
        best_score = -1
        best_position = Position(
            x=random.randint(0, game_map.width - 1),
            y=random.randint(0, game_map.height - 1)
        )
        
        # Sample random positions and pick the best one
        for _ in range(10):
            x = random.randint(0, game_map.width - 1)
            y = random.randint(0, game_map.height - 1)
            
            # Calculate score based on:
            # 1. Nutrient value of the tile
            # 2. Distance from spore (prefer closer tiles)
            # 3. Whether it's owned by another team (prefer neutral/enemy tiles)
            
            nutrients = game_map.nutrientGrid[y][x]
            distance = abs(spore.position.x - x) + abs(spore.position.y - y)
            owner = world.ownershipGrid[y][x]
            
            # Score calculation
            score = nutrients * 2  # Nutrients are important
            score -= distance * 0.5  # Prefer closer tiles
            
            # Prefer tiles not owned by us
            if owner != spore.teamId:
                score += 5
            
            if score > best_score:
                best_score = score
                best_position = Position(x=x, y=y)
        
        return best_position
