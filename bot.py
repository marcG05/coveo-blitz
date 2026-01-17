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
            if my_team.nutrients >= 10:
                for spawner in my_team.spawners:
                    actions.append(
                        SpawnerProduceSporeAction(spawnerId=spawner.id, biomass=10)
                    )
                    print(f"Tick {game_message.tick}: Producing spore from spawner")
                    break  # Produce one at a time
        
        # Step 3: Move all spores to explore the map
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
        
        # CORRECTION: Une seule boucle pour traiter chaque spore UNE FOIS
        for index, spore in enumerate(my_team.spores):
            if game_map.nutrientGrid[spore.position.y][spore.position.x] > 0 and not self.spawner_exists_at(spore.position.y, spore.position.x, game_message.world):
                actions.append(SporeCreateSpawnerAction(spore.id))

            # Skip si déjà traité
            if spore.id in alreadyPlayed_id or spore.id in self.defense_list_id:
                continue

            # 1. Gestion du Split (Expansion) - PRIORITÉ #1
            # Split plus agressif pour expansion rapide
            if spore.biomass > 25:
                valid_dir = self.get_valid_direction(spore, game_map)
                actions.append(SporeSplitAction(spore.id, 12, valid_dir))
                alreadyPlayed_id.append(spore.id)  # Marquer comme traité
                continue

            # Track la spore avec le plus de biomasse
            if spore.biomass > highBio:
                highBio = spore.biomass
                self.highestSpore = spore

            # 2. Comportement selon l'état
            if self.state in [CONVERING, LISTSPORE]:
                # 2. Attribution du rôle (0: Nutriments, 1: Attaque, 2: Spread)
                role = index % 3 

                # 3. Mise à jour ou création de la cible (AVEC VÉRIFICATION D'UNICITÉ)
                if spore.id not in self.exploration_targets:
                    target = self._get_exploration_target(spore, game_map, game_message.world, self.exploration_targets, mode=role)
                    self.exploration_targets[spore.id] = target
                else:
                    target = self.exploration_targets[spore.id]
                    
                    # Vérifier si une autre spore cible la même position
                    other_targeting_same = False
                    for other_id, other_target in self.exploration_targets.items():
                        if other_id != spore.id and other_target.x == target.x and other_target.y == target.y:
                            other_targeting_same = True
                            break
                    
                    # Si cible atteinte, dupliquée, ou position identique = on change
                    if (abs(spore.position.x - target.x) <= 1 and abs(spore.position.y - target.y) <= 1) or other_targeting_same or (spore.position.x == target.x and spore.position.y == target.y):
                        target = self._get_exploration_target(spore, game_map, game_message.world, self.exploration_targets, mode=role)
                        self.exploration_targets[spore.id] = target

                # 4. UTILISER LE PATHFINDING DU JEU - Il est meilleur!
                # On donne juste la cible, le jeu trouve le meilleur chemin
                actions.append(SporeMoveToAction(sporeId=spore.id, position=target))
                alreadyPlayed_id.append(spore.id)  # Marquer comme traité

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
        # Collecter TOUTES les positions déjà ciblées par d'autres spores
        taken_positions = [(p.x, p.y) for spore_id, p in current_targets.items() if spore_id != spore.id]

        # NOUVEAU: Scanner TOUTE la carte pour les nutriments proches
        for y in range(game_map.height):
            for x in range(game_map.width):
                # CRITIQUE: Skip si cette position est déjà ciblée par une autre spore
                if (x, y) in taken_positions: 
                    continue

                target_biomass = world.biomassGrid[y][x]
                target_owner = world.ownershipGrid[y][x]
                nutrients = game_map.nutrientGrid[y][x]
                distance = abs(spore.position.x - x) + abs(spore.position.y - y)
                
                # SKIP si pas de nutriments et on est en mode nutriments
                if mode == 0 and nutrients == 0:
                    continue
                
                is_enemy = (target_owner != -1 and target_owner != spore.teamId)
                is_neutral = (target_owner == -1)

                # --- ESTIMATION SIMPLE: Détecter si entouré de GROS murs ---
                wall_count = 0
                
                # Vérifier seulement les cases adjacentes directes (4 directions cardinales)
                for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    check_x, check_y = x + dx, y + dy
                    if 0 <= check_x < game_map.width and 0 <= check_y < game_map.height:
                        check_biomass = world.biomassGrid[check_y][check_x]
                        check_owner = world.ownershipGrid[check_y][check_x]
                        
                        # Mur = biomasse >= 60 qui n'est pas à nous
                        if check_owner != spore.teamId and check_biomass >= 60:
                            wall_count += 1
                
                # Si entouré de 3+ murs (sur 4 directions), c'est inaccessible
                if wall_count >= 3:
                    continue  # Skip cette cible complètement

                # --- LOGIQUE DE COÛT SIMPLIFIÉE ---
                cost = 0 if target_owner == spore.teamId else (target_biomass + 1)

                # --- MODE ATTAQUE OPTIMISÉ (Cibles faibles) ---
                if mode == 1: # Mode Attaque
                    if not is_enemy: continue
                    score = (nutrients * 5000) / (cost + 1) - (distance * 2)
                    if target_biomass <= 2:
                        score += 2000

                # --- MODE SPREAD (Terrain Neutre) ---
                elif mode == 2:
                    if not is_neutral: continue
                    score = 2000 - (cost * 50) - (distance * 10)

                # --- MODE NUTRIMENTS (PRIORITÉ SIMPLE) ---
                else:
                    if nutrients > 0:
                        # Plus c'est proche et moins ça coûte, mieux c'est
                        if distance <= 10:
                            # Très proche: prioriser fortement
                            score = (nutrients * 15000) / (distance + 1) - (cost * 3)
                        elif distance <= 20:
                            # Proche: bon équilibre
                            score = (nutrients * 8000) / (distance + 1) - (cost * 5)
                        else:
                            # Lointain: seulement si très rentable
                            score = (nutrients * 3000) / (distance + 1) - (cost * 15)
                    else:
                        # Pas de nutriments = basse priorité
                        score = 50 - (cost * 10) - (distance * 5)

                # SÉCURITÉ : Ne jamais cibler ce qu'on ne peut pas détruire facilement
                # Sauf si c'est vraiment proche et très rentable
                if target_owner != spore.teamId and target_biomass >= spore.biomass:
                    if distance > 5 or nutrients < 10:
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