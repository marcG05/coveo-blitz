import random
from game_message import *


class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")
        self.exploration_targets = {}  # Track where each spore is heading
        self.spawner_created = False

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        Starter bot that moves spores across the map to explore and claim territory.
        """
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        game_map = game_message.world.map
        
        # Step 1: Create initial spawner if we don't have one
        if len(my_team.spawners) == 0 and len(my_team.spores) > 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
            self.spawner_created = True
        
        # Step 2: Produce new spores if we have nutrients and few spores
        elif len(my_team.spawners) > 0 and len(my_team.spores) < 5:
            possiblites = 0
            if my_team.nutrients >= 20:
                possiblites = 1
            if my_team.nutrients >= 50:
                possiblites = 2
            if my_team.nutrients >= 100:
                possiblites = 3
            if my_team.nutrients >= 200:
                possiblites = 4
            # Only produce if we have enough nutrients
            if possiblites == 1:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=20)
                    )
                    break  # Produce one at a time
            if possiblites == 2:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=50)
                    )
                    break  # Produce one at a time
            if possiblites == 3:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=100)
                    )
                    break  # Produce one at a time
            if possiblites == 4:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=200)
                    )
                    break  # Produce one at a time
        
        # Step 3: Move all spores to explore the map
        for spore in my_team.spores:
            # Check if spore reached its target or doesn't have one
            if spore.id not in self.exploration_targets:
                target = self._get_exploration_target(spore, game_map, game_message.world)
                self.exploration_targets[spore.id] = target
            
            else:
                target = self.exploration_targets[spore.id]
                if abs(spore.position.x - target.x) <= 1 and abs(spore.position.y - target.y) <= 1:
                    target = self._get_exploration_target(spore, game_map, game_message.world)
                    self.exploration_targets[spore.id] = target
            
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
