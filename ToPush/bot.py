import random
from game_message import *

COVERING = 0
ATTACK = 1
DEFEND = 2

class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")
        self.exploration_targets = {}  # Track where each spore is heading
        self.spawner_created = False
        self.defense_list : list[Spore] = []
        self.highestSpore : Spore = None
        self.newDefensePosition : Position = None
        self.tenHighest : list[str] = []
        self.state = COVERING

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        Starter bot that moves spores across the map to explore and claim territory.
        """
        
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        game_map = game_message.world.map
        alreadyPlayed_id : list[str] = []
        
        # Step 1: Create new spawners
        if len(my_team.spawners) == 0 and len(my_team.spores) > 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
            self.spawner_created = True
            print(f"Tick {game_message.tick}: Creating spawner")
        elif game_message.tick % 100 == 0 and len(my_team.spawners) < 2:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[-2].id))
        elif game_message.tick % 400 == 0 and len(my_team.spawners) < 3:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[-2].id))
        
        # Step 2: Produce new spores if we have nutrients
        elif len(my_team.spawners) > 0:
            if my_team.nutrients >= 10:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=10)
                    )
                    print(f"Tick {game_message.tick}: Producing spore from spawner")
                    break  # Produce one at a time
        
        # Step 3: Start the attack phase
        if game_message.tick > 100 and len(my_team.spores) > 10:
            self.state = ATTACK
            temp_list = list(my_team.spores) # Work on a copy
            result = []
            for _ in range(4):
                current_max = temp_list[0]
                for val in temp_list:
                    if val.biomass > current_max.biomass:
                        current_max = val
                result.append(current_max)
                temp_list.remove(current_max)
                spawn = None
                for g in game_message.world.spawners:
                    if g.teamId != my_team.teamId:
                        spawn = g.position
                        break
                if spawn == None:
                    for g in game_message.world.spores:
                        if g.teamId != my_team.teamId:
                            spawn = g.position
                            break
                
                print(f"ATTACK AT POS {spawn}")
                for r in result:
                    actions.append(
                    SporeMoveToAction(
                        sporeId=r.id,
                        position=spawn
                    )
                    )
                    alreadyPlayed_id.append(r.id)

        highBio = 0
        for spore in my_team.spores:

            if spore.id in alreadyPlayed_id:
                continue

            if spore.biomass >  20:
                valid_dir = self.get_valid_direction(spore, game_map)
                actions.append(SporeSplitAction(spore.id, 10, valid_dir))
                #self.defense_list.append(spore.id)          
                continue

            if spore.biomass > highBio:
                highBio = spore.biomass
                self.highestSpore = spore

            if self.state == COVERING:
                if spore.id in self.defense_list:
                    continue
                # Check if spore reached its target or doesn't have one
                if spore.id not in self.exploration_targets:
                    # Assign a new exploration target
                    target = self._get_exploration_target(spore, game_map, game_message.world, self.exploration_targets)
                    self.exploration_targets[spore.id] = target
                else:
                    target = self.exploration_targets[spore.id]
                    # Check if we reached the target (within 1 tile)
                    if abs(spore.position.x - target.x) <= 1 and abs(spore.position.y - target.y) <= 1:
                        # Get a new target
                        target = self._get_exploration_target(spore, game_map, game_message.world, self.exploration_targets)
                        self.exploration_targets[spore.id] = target
                
                # Move towards target
                actions.append(

                    SporeMoveToAction(
                        sporeId=spore.id,
                        position=target
                    )
                )

        print(f"STATE {self.state}")
        return actions
    
    def _get_exploration_target(self, spore: Spore, game_map: GameMap, world: GameWorld, current_targets: dict) -> Position:
        best_score = -float('inf')
        best_position = Position(x=random.randint(0, game_map.width - 1), y=random.randint(0, game_map.height - 1))
        taken_positions = [(p.x, p.y) for p in current_targets.values()]

        for _ in range(80):
            x = random.randint(0, game_map.width - 1)
            y = random.randint(0, game_map.height - 1)
            
            if (x, y) in taken_positions: continue

            target_biomass = world.biomassGrid[y][x]
            target_owner = world.ownershipGrid[y][x]
            nutrients = game_map.nutrientGrid[y][x]
            distance = abs(spore.position.x - x) + abs(spore.position.y - y)

            # --- DÉTECTION DE MUR / DANGER ---
            # On regarde la biomasse autour de la cible (rayon de 1)
            proximity_danger = 0
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < game_map.width and 0 <= ny < game_map.height:
                        # Si c'est un ennemi ou neutre, on ajoute sa biomasse au danger
                        if world.ownershipGrid[ny][nx] != spore.teamId:
                            proximity_danger += world.biomassGrid[ny][nx]

            # --- CALCUL DU SCORE FINAL ---
            # 1. Priorité massive aux nutriments
            score = nutrients * 30 
            
            # 2. On pénalise le "Mur" : Si le danger total autour est > 20, on fuit
            if proximity_danger > 20:
                score -= (proximity_danger * 50) # Grosse pénalité pour les zones denses

            # 3. On pénalise la biomasse directe sur la tuile
            if target_owner != spore.teamId:
                score -= (target_biomass * 40)
                if target_biomass >= spore.biomass: continue # Sécurité survie
            
            # 4. Pénalité de distance légère
            score -= distance * 1.5

            if score > best_score:
                best_score = score
                best_position = Position(x=x, y=y)
                
        return best_position
    
    def get_valid_direction(self, spore: Spore, game_map: GameMap) -> Position:
        # 1. Définir les 4 directions possibles (CARDINALES uniquement)
        # x et y ne peuvent être que -1, 0 ou 1
        possible_dirs = [
            Position(0, -1), # Haut
            Position(0, 1),  # Bas
            Position(-1, 0), # Gauche
            Position(1, 0)   # Droite
        ]
        
        # Mélanger pour varier l'expansion
        random.shuffle(possible_dirs)

        for d in possible_dirs:
            # 2. Calculer la position théorique
            target_x = spore.position.x + d.x
            target_y = spore.position.y + d.y
            
            # 3. Vérifier si on reste à l'intérieur de la grille
            if 0 <= target_x < game_map.width and 0 <= target_y < game_map.height:
                return d  # Retourne la première direction valide trouvée
                
        return Position(0, 0) # Sécurité : ne bouge pas si aucune option