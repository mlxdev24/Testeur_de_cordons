# Testeur de cordons

Application graphique pour tester et valider des câbles électroniques via interface série UART.

## Description

Cette application permet de :
- Se connecter à un testeur de câbles via port série (UART)
- Identifier automatiquement les testeurs compatibles (TTL-232R-5V-WE)
- Enregistrer des brochages de câbles au format JSON
- Charger des références de câblage
- Tester la conformité d'un câble par rapport à une référence
- Gérer un dossier de références pour stocker les configurations

## Prérequis

### Dépendances Python

```bash
pip install customtkinter pyserial
```

### Matériel requis

- Testeur de câbles compatible (ex: TTL-232R-5V-WE avec VID:PID 0403:6001)
- Câble USB vers série
- Port série disponible sur le système

## Installation

1. Cloner le dépôt
2. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

## Utilisation

### Lancement de l'application

```bash
python main.py
```

### Configuration UART

1. **Scanner les ports** : Utiliser le bouton "🔄 Re-scanner" pour détecter les ports série disponibles
2. **Connexion automatique** : Si un testeur compatible est détecté, une popup proposera de se connecter automatiquement
3. **Connexion manuelle** : Sélectionner un port et cliquer sur "🔌 Connecter"
4. **Paramètres** :
   - Baudrate par défaut : 38400
   - Timeout : 2.0 secondes

### Gestion des références

- **Charger une référence** : Cliquer sur "📁 Charger une référence" et sélectionner un fichier JSON
- **Effacer** : Supprimer la référence active (option de suppression du fichier physique disponible)
- Les références sont stockées dans le dossier `Références/` créé automatiquement

### Enregistrer un nouveau câble

1. Connecter le testeur
2. Cliquer sur "💾 Enregistrer un nouveau câble"
3. Le testeur envoie les données de brochage au format JSON
4. Sauvegarder le fichier (il peut être chargé comme référence)

### Tester la conformité

1. Charger une référence JSON
2. Connecter le câble à tester
3. Cliquer sur "✓ Tester la conformité"
4. Le résultat s'affiche en popup colorée :
   - **CONFORME** (vert) : Le câble correspond à la référence
   - **NON-CONFORME** (rouge) : Le câble diffère de la référence

## Format des fichiers JSON

Les fichiers de référence sont au format JSON avec une structure de type dictionnaire :

```json
{
  "Pin_1": ["connection1", "connection2"],
  "Pin_2": ["connection3"],
  ...
}
```

## Fonctionnalités

### Détection automatique
- Scan automatique des ports série au démarrage
- Identification du testeur TTL-232R-5V-WE (VID:PID 0403:6001)
- Proposition de connexion automatique

### Interface utilisateur
- Interface moderne avec CustomTkinter
- Thème système adaptatif
- Journal d'activité en temps réel
- Popups de confirmation avec options

### Connexion persistante
- Le port série reste ouvert après l'identification
- Optimisation des performances pour les tests multiples
- Déconnexion propre à la fermeture de l'application

## Structure du projet

```
Testeur_de_cordons/
├── main.py           # Application principale
├── README.md         # Documentation
└── Références/       # Dossier des fichiers de référence JSON (créé automatiquement)
```

## Commandes du testeur

- `IDN\n` : Identification du testeur (retourne "Testeur de cordon")
- `TEST\n` : Lance un test et retourne le brochage JSON

## Dépannage

### Le testeur n'est pas détecté
- Vérifier que le câble USB est bien branché
- Vérifier les drivers FTDI (pour TTL-232R-5V-WE)
- Essayer de re-scanner les ports

### Erreur d'accès au port
- Vérifier que le port n'est pas utilisé par une autre application
- Sous Linux : vérifier les permissions (`sudo usermod -a -G dialout $USER`)
- Redémarrer l'application

### Timeout lors du test
- Augmenter la valeur du timeout
- Vérifier la connexion physique au testeur
- Vérifier le baudrate (doit correspondre au testeur)

## Licence

Ce projet est développé pour tester des câbles électroniques via interface série.
