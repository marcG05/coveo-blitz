import random
from game_message import *


CONVERING = 0
ATTACK = 1
DEFEND = 2
LISTSPORE = 3

class Bot:
    def __init__(self):
        print("Initializing your super mega duper bot")
        self.exploration_targets = {}  # Track where each spore is heading
        self.spawner_created = False
        self.defense_list : list[Spore] = []
        self.defense_list_id : list[str] = []
        self.highestSpore : Spore = None
        self.newDefensePosition : Position = None
        self.tenHighest : list[str] = []
        self.state = CONVERING
        self.last_positions = {} # {spore_id: Position_objet}

    def get_next_move(self, game_message: TeamGameState) -> list[Action]:
        """
        Starter bot that moves spores across the map to explore and claim territory.
        """
        use_spores_list : list[Spore] = []
        
        actions = []
        my_team: TeamInfo = game_message.world.teamInfos[game_message.yourTeamId]
        game_map = game_message.world.map
        alreadyPlayed_id : list[str] = []
        
        for s in self.defense_list:
            print(f"DEFENCE : {s.id}")

        
        # Strategy: Create one spawner, then produce spores and explore the map
        
        # Step 1: Create initial spawner if we don't have one
        if len(my_team.spawners) == 0 and len(my_team.spores) > 0:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[0].id))
            self.spawner_created = True
            print(f"Tick {game_message.tick}: Creating spawner")   
        elif game_message.tick % 300 == 0 and len(my_team.spawners) < 5:
            actions.append(SporeCreateSpawnerAction(sporeId=my_team.spores[-2].id))
        
        # Step 2: Produce new spores if we have nutrients and few spores
        elif len(my_team.spawners) > 0:
            # Only produce if we have enough nutrients
            if my_team.nutrients >= 10:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=10)
                    )
                    print(f"Tick {game_message.tick}: Producing spore from spawner")
                    break  # Produce one at a time
        
        # Step 3: Move all spores to explore the map
        """if len(my_team.spores) - len(self.defense_list_id) > 4 and self.highestSpore != None:
            use_spores_list = my_team.spores
            print(self.highestSpore)
            actions.append(
                SporeSplitAction(self.highestSpore.id, int(self.highestSpore.biomass*0.3), Position(0,1))
            )
            self.defense_list_id.append(self.highestSpore.id)
        else:
            use_spores_list = my_team.spores"""

        if game_message.tick > 200 and len(my_team.spores) > 10:
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
        
        if len(my_team.spores) > 12:
            self.state = LISTSPORE

        highBio = 0
        for index, spore in enumerate(my_team.spores):

            if game_map.nutrientGrid[spore.position.y][spore.position.x] > 0 and not self.spawner_exists_at(spore.position.y, spore.position.x, game_message.world):
                actions.append(SporeCreateSpawnerAction(spore.id))

            if spore.id in alreadyPlayed_id:
                continue

            if spore.biomass >  20:
                valid_dir = self.get_valid_direction(spore, game_map)
                actions.append(SporeSplitAction(spore.id, 10, valid_dir))
                #self.defense_list_id.append(spore.id)                
                continue

            if spore.biomass > highBio:
                highBio = spore.biomass
                self.highestSpore = spore

            if self.state in [CONVERING, LISTSPORE]: 
                for index, spore in enumerate(my_team.spores):
                    if spore.id in alreadyPlayed_id or spore.id in self.defense_list_id:
                        continue

                    # 1. Gestion du Split (Expansion)
                    if spore.biomass > 20:
                        valid_dir = self.get_valid_direction(spore, game_map)
                        actions.append(SporeSplitAction(spore.id, 10, valid_dir))
                        continue

                    # 2. Attribution du rôle (0: Nutriments, 1: Attaque, 2: Spread)
                    role = index % 3 

                    # 3. Mise à jour ou création de la cible
                    if spore.id not in self.exploration_targets:
                        target = self._get_exploration_target(spore, game_map, game_message.world, self.exploration_targets, mode=role)
                        self.exploration_targets[spore.id] = target
                    else:
                        target = self.exploration_targets[spore.id]
                        # Si cible atteinte ou presque, on change
                        if abs(spore.position.x - target.x) <= 1 and abs(spore.position.y - target.y) <= 1:
                            target = self._get_exploration_target(spore, game_map, game_message.world, self.exploration_targets, mode=role)
                            self.exploration_targets[spore.id] = target

                    # 4. Calcul du mouvement "Anti-Retour" et "Faible Coût"
                    options = [Position(x=1, y=0), Position(x=-1, y=0), Position(x=0, y=1), Position(x=0, y=-1)]
                    best_step = None
                    min_step_score = float('inf')
                    last_pos = self.last_positions.get(spore.id)

                    for opt in options:
                        nx, ny = spore.position.x + opt.x, spore.position.y + opt.y
                        
                        if not (0 <= nx < game_map.width and 0 <= ny < game_map.height):
                            continue

                        # Sécurité Anti-Retour
                        if last_pos and nx == last_pos.x and ny == last_pos.y:
                            continue 

                        cell_biomass = game_message.world.biomassGrid[ny][nx]
                        cell_owner = game_message.world.ownershipGrid[ny][nx]
                        
                        # On favorise les cases qui nous appartiennent ou les cases neutres vides
                        step_cost = cell_biomass if cell_owner != game_message.yourTeamId else 0
                        dist_to_target = abs(nx - target.x) + abs(ny - target.y)

                        # Score du pas : Priorité énorme à éviter les grosses biomasses
                        # (step_cost * 100) assure qu'on contourne un mur plutôt que de le traverser
                        current_score = (step_cost * 100) + dist_to_target

                        if current_score < min_step_score:
                            min_step_score = current_score
                            best_step = opt

                    # 5. Exécution du mouvement
                    if best_step:
                        self.last_positions[spore.id] = Position(x=spore.position.x, y=spore.position.y)
                        actions.append(SporeMoveAction(sporeId=spore.id, direction=best_step))

        

        print(f"STATE {self.state}")
        return actions
    
    def is_direction_safe(self, current_pos: Position, direction: Position, world: GameWorld, my_team_id: int) -> bool:
        target_x = current_pos.x + direction.x
        target_y = current_pos.y + direction.y
        
        # Vérifier les limites de la carte
        if not (0 <= target_x < world.map.width and 0 <= target_y < world.map.height):
            return False
            
        # Vérifier la biomasse et le propriétaire
        # On évite si : Biomasse > 20 ET ce n'est pas à nous
        cell_biomass = world.biomassGrid[target_y][target_x]
        cell_owner = world.ownershipGrid[target_y][target_x]
        
        if cell_biomass > 20 and cell_owner != my_team_id:
            return False
            
        return True
    
    def _get_exploration_target(self, spore: Spore, game_map: GameMap, world: GameWorld, current_targets: dict, mode: int = 0) -> Position:
        best_score = -float('inf')
        best_position = spore.position 
        taken_positions = [(p.x, p.y) for p in current_targets.values()]

        for _ in range(200):
            x = random.randint(0, game_map.width - 1)
            y = random.randint(0, game_map.height - 1)
            if (x, y) in taken_positions: continue

            target_biomass = world.biomassGrid[y][x]
            target_owner = world.ownershipGrid[y][x]
            nutrients = game_map.nutrientGrid[y][x]
            distance = abs(spore.position.x - x) + abs(spore.position.y - y)
            
            is_enemy = (target_owner != -1 and target_owner != spore.teamId)
            is_neutral = (target_owner == -1)

            # --- LOGIQUE DE COÛT ---
            # Si c'est à nous, coût = 0. Si c'est vide, coût = 1. Si ennemi, coût = biomasse + 1.
            cost = 0 if target_owner == spore.teamId else (target_biomass + 1)

            # --- MODE ATTAQUE OPTIMISÉ (Cibles faibles) ---
            if mode == 1: # Mode Attaque
                if not is_enemy: continue
                
                # Priorité : Nutriments élevés / Coût faible
                # On ajoute +1 au coût pour éviter la division par zéro
                score = (nutrients * 1000) / (cost + 1)
                
                # Bonus pour les "petites" proies (on veut spread sur ses traces faibles)
                if target_biomass <= 2:
                    score += 500
                    
                score -= (distance * 5)

            # --- MODE SPREAD (Terrain Neutre) ---
            elif mode == 2:
                if not is_neutral: continue
                # On cherche les cases vides les moins chères (biomasse neutre 0)
                score = 2000 - (cost * 100) - (distance * 10)

            # --- MODE NUTRIMENTS (Classique) ---
            else:
                # On cherche le meilleur rendement
                score = (nutrients * 1000) - (cost * 200) - (distance * 10)

            # SÉCURITÉ : Ne jamais cibler ce qu'on ne peut pas détruire
            if target_owner != spore.teamId and target_biomass >= spore.biomass:
                continue

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

    def spawner_exists_at(self, y: int, x: int, world: GameWorld) -> bool:
        for spawner in world.spawners:
            if spawner.position.y == y and spawner.position.x == x:
                return True
        return False