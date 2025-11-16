# Driver Python pour Équipement SA32

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-PEP8-orange.svg)](https://www.python.org/dev/peps/pep-0008/)

Driver Python professionnel pour le système d'acquisition et de mesure thermique **SA32** de SOLINOV.

## 📋 Table des Matières

- [Description](#description)
- [Caractéristiques](#caractéristiques)
- [Installation](#installation)
- [Guide de Démarrage Rapide](#guide-de-démarrage-rapide)
- [Documentation Complète](#documentation-complète)
  - [Architecture](#architecture)
  - [Protocoles Supportés](#protocoles-supportés)
  - [API Référence](#api-référence)
  - [Gestion d'Erreurs](#gestion-derreurs)
  - [Mode Mock](#mode-mock)
  - [Thread Safety](#thread-safety)
- [Exemples Avancés](#exemples-avancés)
- [Tests](#tests)
- [Dépannage](#dépannage)
- [Contribution](#contribution)
- [License](#license)

---

## 📖 Description

Le **SA32** est un système d'acquisition et de mesure thermique/thermodynamique utilisé dans les bancs de test pour :
- Mesurer des températures (Te, Ts, Tw, T_bulk)
- Calculer la puissance thermique
- Calculer des nombres adimensionnels (Nusselt, Reynolds, coefficient de frottement)
- Acquérir des propriétés physiques (conductivité thermique, capacité calorifique, viscosité)

Ce driver Python fournit une interface complète et professionnelle pour communiquer avec l'équipement SA32 via les protocoles **Modbus TCP** et **Modbus RTU**.

### Fabricant
**SOLINOV** - Solutions innovantes pour la thermodynamique

---

## ✨ Caractéristiques

### Architecture
- ✅ **Architecture modulaire** : Séparation claire entre communication, traitement et données
- ✅ **Design patterns** : Context manager (`with` statement), callbacks, singleton
- ✅ **PEP 8 compliant** : Code conforme aux standards Python
- ✅ **Type hints** : Typage statique pour meilleure maintenabilité

### Communication
- ✅ **Modbus TCP** : Communication réseau Ethernet
- ✅ **Modbus RTU** : Communication série RS-232/RS-485
- ✅ **Auto-reconnexion** : Gestion automatique des pertes de connexion
- ✅ **Timeouts configurables** : Contrôle fin des délais

### Gestion d'Erreurs
- ✅ **Exceptions personnalisées** : Hiérarchie d'exceptions spécifiques
- ✅ **Structure d'erreur standardisée** : Compatible avec les autres drivers SOLINOV
- ✅ **Logging intégré** : Traçabilité complète des opérations
- ✅ **Callbacks d'erreur** : Notifications en temps réel

### Testabilité
- ✅ **Mode Mock** : Simulation complète sans équipement réel
- ✅ **Tests unitaires** : Suite complète de tests pytest (95%+ couverture)
- ✅ **Thread-safe** : Utilisation sûre dans applications multi-thread
- ✅ **PyQt5 compatible** : Intégration facile dans interfaces graphiques

### Documentation
- ✅ **Docstrings Google Style** : Documentation complète de toutes les fonctions
- ✅ **Exemples d'utilisation** : Code prêt à l'emploi
- ✅ **Guide de dépannage** : Solutions aux problèmes courants

---

## 🔧 Installation

### Prérequis

- **Python 3.7+** (testé avec Python 3.8, 3.9, 3.10, 3.11)
- Système d'exploitation : Windows, Linux, macOS

### Installation des dépendances

```bash
# Installation depuis requirements.txt
pip install -r requirements.txt

# Ou installation manuelle des dépendances
pip install pymodbus>=3.0.0
pip install pytest pytest-cov  # Pour les tests (optionnel)
```

### Installation du driver

```bash
# Cloner le dépôt (ou copier les fichiers)
git clone https://github.com/SOLINOV/SA32.git
cd SA32

# Ou simplement copier les fichiers dans votre projet
cp sa32_driver.py /path/to/your/project/
```

### Vérification de l'installation

```bash
# Test rapide en mode mock
python3 -c "from sa32_driver import SA32Driver; d = SA32Driver(mock_mode=True); d.connect(); print('✓ Installation réussie')"
```

---

## 🚀 Guide de Démarrage Rapide

### Exemple 1 : Modbus TCP

```python
from sa32_driver import SA32Driver

# Création du driver
sa32 = SA32Driver(
    protocol='TCP',
    host='192.168.1.100',  # Adresse IP de votre SA32
    port=502,
    slave_id=1,
    timeout=5.0
)

# Connexion avec context manager (recommandé)
with sa32:
    # Lecture d'un registre
    value = sa32.read_holding_register(1000)
    print(f"Valeur du registre 1000: {value}")

    # Écriture d'un registre
    sa32.write_register(2000, 42)
    print("Registre 2000 écrit avec succès")
```

### Exemple 2 : Modbus RTU

```python
from sa32_driver import SA32Driver

# Création du driver RTU
sa32 = SA32Driver(
    protocol='RTU',
    port='COM3',           # Windows
    # port='/dev/ttyUSB0', # Linux
    baudrate=9600,
    parity='N',
    stopbits=1,
    slave_id=1
)

# Connexion manuelle
sa32.connect()

try:
    # Lecture de plusieurs registres
    values = sa32.read_holding_registers(1000, 10)
    print(f"Valeurs lues: {values}")

    # Lecture d'un float (2 registres)
    temperature = sa32.read_float(3000)
    print(f"Température: {temperature} °C")

finally:
    # Toujours fermer la connexion
    sa32.disconnect()
```

### Exemple 3 : Mode Mock (pour tests)

```python
from sa32_driver import SA32Driver

# Driver simulé (sans équipement réel)
sa32_mock = SA32Driver(mock_mode=True)

with sa32_mock:
    # Définir des valeurs de test
    sa32_mock.set_mock_register(1000, 12345)

    # Lire comme sur un vrai équipement
    value = sa32_mock.read_holding_register(1000)
    print(f"Valeur mock: {value}")  # Affiche: 12345
```

---

## 📚 Documentation Complète

### Architecture

Le driver SA32 suit une architecture en couches :

```
┌─────────────────────────────────────────┐
│   Application (PyQt5, scripts, etc.)    │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│  SA32Driver (API de haut niveau)        │
│  - read_temperature()                   │
│  - read_power()                         │
│  - get_thermal_data()                   │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│  Couche Modbus (opérations génériques)  │
│  - read_holding_registers()             │
│  - write_register()                     │
│  - read_float()                         │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│  PyModbus (communication bas niveau)    │
│  - ModbusTcpClient                      │
│  - ModbusSerialClient                   │
└─────────────────────────────────────────┘
```

### Protocoles Supportés

#### Modbus TCP

**Configuration par défaut :**
- Port : 502
- Timeout : 10 secondes

**Paramètres :**
```python
sa32 = SA32Driver(
    protocol='TCP',
    host='192.168.1.100',    # Adresse IP
    port=502,                # Port TCP
    slave_id=1,              # ID Modbus (1-247)
    timeout=10.0             # Timeout en secondes
)
```

#### Modbus RTU

**Configuration par défaut :**
- Baudrate : 9600 bps
- Data bits : 8
- Parity : None
- Stop bits : 1
- Timeout : 10 secondes

**Paramètres :**
```python
sa32 = SA32Driver(
    protocol='RTU',
    port='COM3',             # Port série
    baudrate=9600,           # 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200
    bytesize=8,              # 7 ou 8
    parity='N',              # 'N' (None), 'E' (Even), 'O' (Odd)
    stopbits=1,              # 1 ou 2
    slave_id=1
)
```

### API Référence

#### Classe SA32Driver

##### Méthodes de Connexion

###### `connect() -> bool`

Établit la connexion avec l'équipement SA32.

**Returns:**
- `bool`: True si connexion réussie, False sinon

**Raises:**
- `SA32ConnectionError`: Si la connexion échoue

**Exemple:**
```python
driver = SA32Driver(host='192.168.1.100')
if driver.connect():
    print("Connecté avec succès")
```

###### `disconnect() -> None`

Ferme la connexion avec l'équipement.

**Exemple:**
```python
driver.disconnect()
```

###### `is_connected() -> bool`

Vérifie si la connexion est active.

**Returns:**
- `bool`: True si connecté, False sinon

##### Méthodes de Lecture

###### `read_holding_register(address: int) -> Optional[int]`

Lit un registre Holding (fonction Modbus 0x03).

**Args:**
- `address` (int): Adresse du registre (0-65535)

**Returns:**
- `int`: Valeur du registre (0-65535), ou None en cas d'erreur

**Raises:**
- `SA32CommunicationError`: Si la lecture échoue
- `SA32ConnectionError`: Si non connecté

**Exemple:**
```python
value = driver.read_holding_register(1000)
print(f"Registre 1000 = {value}")
```

###### `read_holding_registers(address: int, count: int = 1) -> Optional[List[int]]`

Lit plusieurs registres Holding consécutifs.

**Args:**
- `address` (int): Adresse du premier registre
- `count` (int): Nombre de registres à lire

**Returns:**
- `List[int]`: Liste des valeurs lues

**Exemple:**
```python
values = driver.read_holding_registers(1000, 10)
for i, val in enumerate(values):
    print(f"Registre {1000+i} = {val}")
```

###### `read_input_register(address: int) -> Optional[int]`

Lit un registre Input (fonction Modbus 0x04).

**Args:**
- `address` (int): Adresse du registre

**Returns:**
- `int`: Valeur du registre, ou None en cas d'erreur

###### `read_input_registers(address: int, count: int = 1) -> Optional[List[int]]`

Lit plusieurs registres Input consécutifs.

###### `read_float(address: int, register_type: RegisterType = RegisterType.HOLDING, byte_order: Endian = Endian.BIG, word_order: Endian = Endian.BIG) -> Optional[float]`

Lit un nombre flottant 32 bits (occupe 2 registres).

**Args:**
- `address` (int): Adresse du premier registre
- `register_type` (RegisterType): Type de registre (HOLDING ou INPUT)
- `byte_order` (Endian): Ordre des octets (BIG ou LITTLE)
- `word_order` (Endian): Ordre des mots (BIG ou LITTLE)

**Returns:**
- `float`: Valeur flottante

**Exemple:**
```python
from pymodbus.constants import Endian
temperature = driver.read_float(2000, byte_order=Endian.BIG)
print(f"Température: {temperature} °C")
```

##### Méthodes d'Écriture

###### `write_register(address: int, value: int) -> bool`

Écrit un registre Holding (fonction Modbus 0x06).

**Args:**
- `address` (int): Adresse du registre
- `value` (int): Valeur à écrire (0-65535)

**Returns:**
- `bool`: True si succès

**Exemple:**
```python
driver.write_register(3000, 100)
```

###### `write_registers(address: int, values: List[int]) -> bool`

Écrit plusieurs registres Holding (fonction Modbus 0x10).

**Args:**
- `address` (int): Adresse du premier registre
- `values` (List[int]): Liste des valeurs à écrire

**Returns:**
- `bool`: True si succès

**Exemple:**
```python
driver.write_registers(4000, [100, 200, 300, 400])
```

###### `write_float(address: int, value: float, byte_order: Endian = Endian.BIG, word_order: Endian = Endian.BIG) -> bool`

Écrit un nombre flottant 32 bits (occupe 2 registres).

**Args:**
- `address` (int): Adresse du premier registre
- `value` (float): Valeur flottante à écrire
- `byte_order` (Endian): Ordre des octets
- `word_order` (Endian): Ordre des mots

**Returns:**
- `bool`: True si succès

**Exemple:**
```python
driver.write_float(5000, 25.5)  # Température de consigne
```

##### Méthodes Spécifiques SA32

> **Note:** Les méthodes ci-dessous sont des EXEMPLES. Les adresses de registres
> doivent être configurées selon la documentation technique de votre équipement SA32.

###### `read_temperature(channel: int, temp_type: str = 'Te') -> Optional[float]`

Lit une température sur un canal donné.

**Args:**
- `channel` (int): Numéro du canal (voie)
- `temp_type` (str): Type de température ('Te', 'Ts', 'Tw', 'T_bulk')

**Returns:**
- `float`: Température en °C

###### `read_power() -> Optional[float]`

Lit la puissance thermique.

**Returns:**
- `float`: Puissance en Watts

###### `read_nusselt_number() -> Optional[float]`

Lit le nombre de Nusselt.

**Returns:**
- `float`: Nombre de Nusselt (sans dimension)

###### `read_reynolds_number() -> Optional[float]`

Lit le nombre de Reynolds.

**Returns:**
- `float`: Nombre de Reynolds (sans dimension)

###### `get_thermal_data() -> Dict[str, Any]`

Récupère un ensemble complet de données thermiques.

**Returns:**
- `dict`: Dictionnaire contenant toutes les mesures

**Exemple:**
```python
data = driver.get_thermal_data()
print(f"Puissance: {data['power_w']} W")
print(f"Nusselt: {data['nusselt']}")
print(f"Reynolds: {data['reynolds']}")
```

##### Méthodes de Gestion d'Erreurs

###### `get_last_error() -> EquipmentError`

Retourne la dernière erreur survenue.

**Returns:**
- `EquipmentError`: Objet contenant status, code et source de l'erreur

**Exemple:**
```python
error = driver.get_last_error()
if error.status:
    print(f"Erreur {error.code}: {error.source}")
```

###### `clear_error() -> None`

Efface la dernière erreur enregistrée.

##### Méthodes de Callbacks

###### `register_callback(event: str, callback: Callable) -> None`

Enregistre une fonction de callback pour un événement.

**Args:**
- `event` (str): Type d'événement ('on_connect', 'on_disconnect', 'on_error', 'on_data_received')
- `callback` (Callable): Fonction à appeler

**Exemple:**
```python
def on_error_handler(error):
    print(f"Erreur: {error.source}")
    # Envoyer une notification, écrire dans un log, etc.

driver.register_callback('on_error', on_error_handler)
```

**Événements disponibles:**

| Événement | Paramètres callback | Description |
|-----------|---------------------|-------------|
| `on_connect` | Aucun | Déclenché après connexion réussie |
| `on_disconnect` | Aucun | Déclenché après déconnexion |
| `on_error` | `error: EquipmentError` | Déclenché lors d'une erreur |
| `on_data_received` | `data: dict` | Déclenché après lecture de données |

###### `unregister_callback(event: str, callback: Callable) -> None`

Désenregistre une fonction de callback.

### Gestion d'Erreurs

#### Hiérarchie d'Exceptions

```
Exception
└── SA32Exception (base)
    ├── SA32ConnectionError      # Erreurs de connexion
    ├── SA32CommunicationError   # Erreurs de communication Modbus
    ├── SA32ConfigurationError   # Erreurs de configuration
    └── SA32TimeoutError         # Erreurs de timeout
```

#### Structure EquipmentError

```python
@dataclass
class EquipmentError:
    status: bool = False  # True si erreur présente
    code: int = 0         # Code numérique de l'erreur
    source: str = ""      # Description de la source
```

**Utilisation:**
```python
try:
    value = driver.read_holding_register(1000)
except SA32CommunicationError as e:
    print(f"Erreur de communication: {e}")
    error = driver.get_last_error()
    print(f"Code: {error.code}, Source: {error.source}")
```

#### Codes d'Erreur

| Code | Signification |
|------|---------------|
| 0 | Pas d'erreur |
| -1 | Erreur de connexion |
| -2 | Exception Modbus |
| -3 | Erreur inattendue |
| 1-255 | Codes exception Modbus standard |

### Mode Mock

Le mode mock permet de tester votre application sans équipement réel.

**Activation:**
```python
driver = SA32Driver(mock_mode=True)
```

**Fonctionnalités:**
- ✅ Simulation complète de toutes les opérations Modbus
- ✅ Génération automatique de valeurs aléatoires réalistes
- ✅ Persistance des valeurs écrites
- ✅ Aucune dépendance matérielle

**Définir des valeurs de test:**
```python
driver = SA32Driver(mock_mode=True)
driver.connect()

# Définir des valeurs spécifiques pour les tests
driver.set_mock_register(1000, 12345)
driver.set_mock_register(1001, 67890)

# Lire comme sur un vrai équipement
value = driver.read_holding_register(1000)
assert value == 12345
```

### Thread Safety

Le driver SA32 est **thread-safe** grâce à l'utilisation d'un verrou réentrant (`threading.RLock`).

**Utilisation dans PyQt5:**
```python
from PyQt5.QtCore import QThread, pyqtSignal

class AcquisitionThread(QThread):
    data_ready = pyqtSignal(dict)

    def __init__(self, driver):
        super().__init__()
        self.driver = driver

    def run(self):
        while not self.isInterruptionRequested():
            try:
                # Lecture thread-safe
                data = self.driver.get_thermal_data()
                self.data_ready.emit(data)
            except Exception as e:
                print(f"Erreur: {e}")

            self.msleep(1000)  # 1 seconde

# Utilisation
driver = SA32Driver(host='192.168.1.100')
driver.connect()

thread = AcquisitionThread(driver)
thread.data_ready.connect(lambda data: print(f"Données: {data}"))
thread.start()
```

---

## 🔬 Exemples Avancés

### Exemple 1 : Auto-reconnexion

```python
from sa32_driver import SA32Driver, SA32ConnectionError

# Configuration avec auto-reconnexion
driver = SA32Driver(
    host='192.168.1.100',
    auto_reconnect=True,
    reconnect_delay=2.0,           # Délai entre tentatives
    max_reconnect_attempts=5       # Nombre de tentatives max
)

driver.connect()

# La reconnexion se fait automatiquement en cas de perte
while True:
    try:
        value = driver.read_holding_register(1000)
        print(f"Valeur: {value}")
    except SA32ConnectionError:
        print("Connexion perdue, reconnexion en cours...")
        # Le driver tentera automatiquement de se reconnecter

    time.sleep(1)
```

### Exemple 2 : Acquisition Continue avec Callbacks

```python
from sa32_driver import SA32Driver
import time

# Compteurs pour statistiques
stats = {
    'reads': 0,
    'errors': 0,
    'last_values': []
}

def on_data_received(data):
    """Callback appelé à chaque lecture de données."""
    stats['reads'] += 1
    stats['last_values'].append(data['values'])

    # Garder seulement les 100 dernières valeurs
    if len(stats['last_values']) > 100:
        stats['last_values'].pop(0)

    print(f"Données reçues: {data}")

def on_error(error):
    """Callback appelé en cas d'erreur."""
    stats['errors'] += 1
    print(f"Erreur #{stats['errors']}: {error.source}")

# Configuration du driver
driver = SA32Driver(host='192.168.1.100', mock_mode=True)
driver.register_callback('on_data_received', on_data_received)
driver.register_callback('on_error', on_error)

with driver:
    # Acquisition pendant 10 secondes
    start_time = time.time()
    while time.time() - start_time < 10:
        driver.read_holding_registers(1000, 5)
        time.sleep(0.1)

    print(f"\nStatistiques:")
    print(f"  Lectures: {stats['reads']}")
    print(f"  Erreurs: {stats['errors']}")
    print(f"  Taux de succès: {100 * (1 - stats['errors']/stats['reads']):.1f}%")
```

### Exemple 3 : Interface PyQt5 Complète

```python
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from sa32_driver import SA32Driver
import sys

class SA32MonitorThread(QThread):
    """Thread d'acquisition des données SA32."""
    data_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, driver):
        super().__init__()
        self.driver = driver
        self.running = True

    def run(self):
        while self.running:
            try:
                # Lecture des données thermiques
                data = {
                    'reg_1000': self.driver.read_holding_register(1000),
                    'reg_1001': self.driver.read_holding_register(1001),
                    'reg_1002': self.driver.read_holding_register(1002),
                }
                self.data_updated.emit(data)
            except Exception as e:
                self.error_occurred.emit(str(e))

            self.msleep(500)  # Acquisition toutes les 500ms

    def stop(self):
        self.running = False

class SA32MonitorWindow(QMainWindow):
    """Fenêtre principale de monitoring SA32."""

    def __init__(self):
        super().__init__()
        self.driver = SA32Driver(mock_mode=True)
        self.thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('SA32 Monitor')
        self.setGeometry(100, 100, 400, 300)

        # Widgets
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.status_label = QLabel('Déconnecté')
        self.data_label = QLabel('Aucune donnée')
        self.connect_btn = QPushButton('Connexion')
        self.disconnect_btn = QPushButton('Déconnexion')

        layout.addWidget(self.status_label)
        layout.addWidget(self.data_label)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.disconnect_btn)

        # Connexions de signaux
        self.connect_btn.clicked.connect(self.connect_device)
        self.disconnect_btn.clicked.connect(self.disconnect_device)

        self.disconnect_btn.setEnabled(False)

    def connect_device(self):
        """Connexion à l'équipement."""
        try:
            self.driver.connect()
            self.status_label.setText('✓ Connecté')
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)

            # Démarrer le thread d'acquisition
            self.thread = SA32MonitorThread(self.driver)
            self.thread.data_updated.connect(self.update_data)
            self.thread.error_occurred.connect(self.handle_error)
            self.thread.start()

        except Exception as e:
            self.status_label.setText(f'✗ Erreur: {e}')

    def disconnect_device(self):
        """Déconnexion de l'équipement."""
        if self.thread:
            self.thread.stop()
            self.thread.wait()

        self.driver.disconnect()
        self.status_label.setText('Déconnecté')
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

    def update_data(self, data):
        """Mise à jour de l'affichage des données."""
        text = "Données SA32:\n"
        for key, value in data.items():
            text += f"  {key}: {value}\n"
        self.data_label.setText(text)

    def handle_error(self, error_msg):
        """Gestion des erreurs."""
        self.status_label.setText(f'⚠ Erreur: {error_msg}')

    def closeEvent(self, event):
        """Fermeture propre de l'application."""
        self.disconnect_device()
        event.accept()

# Application
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SA32MonitorWindow()
    window.show()
    sys.exit(app.exec_())
```

### Exemple 4 : Logging Avancé

```python
import logging
from logging.handlers import RotatingFileHandler
from sa32_driver import SA32Driver

# Configuration du logging
logger = logging.getLogger('SA32Application')
logger.setLevel(logging.DEBUG)

# Handler fichier avec rotation
file_handler = RotatingFileHandler(
    'sa32_log.txt',
    maxBytes=1024*1024,  # 1 MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)

# Handler console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Format
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Driver avec logging détaillé
driver = SA32Driver(
    host='192.168.1.100',
    log_level=logging.DEBUG  # Logs détaillés
)

# Utilisation
logger.info("Démarrage de l'application")

try:
    driver.connect()
    logger.info("Connexion établie")

    value = driver.read_holding_register(1000)
    logger.info(f"Valeur lue: {value}")

except Exception as e:
    logger.exception("Erreur dans l'application")

finally:
    driver.disconnect()
    logger.info("Application terminée")
```

---

## 🧪 Tests

### Exécution des Tests

```bash
# Tous les tests
pytest test_sa32_driver.py -v

# Tests spécifiques
pytest test_sa32_driver.py::TestConnection -v

# Avec couverture de code
pytest test_sa32_driver.py --cov=sa32_driver --cov-report=html

# Exclure les tests lents
pytest test_sa32_driver.py -v -m "not slow"
```

### Structure des Tests

```
test_sa32_driver.py
├── TestInitialization          # Tests d'initialisation
├── TestConnection              # Tests de connexion/déconnexion
├── TestReadOperations          # Tests de lecture
├── TestWriteOperations         # Tests d'écriture
├── TestErrorHandling           # Tests de gestion d'erreurs
├── TestCallbacks               # Tests des callbacks
├── TestThreadSafety            # Tests de thread-safety
├── TestHighLevelMethods        # Tests méthodes spécifiques SA32
├── TestMockMode                # Tests du mode mock
├── TestRepresentation          # Tests de représentation
├── TestIntegration             # Tests d'intégration
└── TestPerformance             # Tests de performance (slow)
```

### Couverture de Code

Le driver SA32 vise une couverture de code de **95%+** :

```bash
# Générer le rapport de couverture
pytest test_sa32_driver.py --cov=sa32_driver --cov-report=term-missing

# Rapport HTML
pytest test_sa32_driver.py --cov=sa32_driver --cov-report=html
# Ouvrir htmlcov/index.html dans un navigateur
```

---

## 🔍 Dépannage

### Problème : Impossible de se connecter (Modbus TCP)

**Symptômes:**
```
SA32ConnectionError: Impossible de se connecter à l'équipement SA32
```

**Solutions:**
1. Vérifier que l'équipement est sous tension et connecté au réseau
2. Vérifier l'adresse IP et le port :
   ```bash
   ping 192.168.1.100
   ```
3. Vérifier le pare-feu (port 502 doit être ouvert)
4. Tester avec un outil Modbus tiers (Modbus Poll, qModMaster)
5. Vérifier le slave ID (doit correspondre à la configuration de l'équipement)

### Problème : Timeout lors des lectures

**Symptômes:**
```
SA32TimeoutError: Timeout lors de la lecture du registre
```

**Solutions:**
1. Augmenter le timeout :
   ```python
   driver = SA32Driver(host='192.168.1.100', timeout=20.0)
   ```
2. Vérifier la qualité de la connexion réseau/série
3. Réduire la fréquence d'acquisition
4. Vérifier que l'équipement n'est pas surchargé

### Problème : Valeurs aberrantes

**Symptômes:**
Les valeurs lues ne correspondent pas aux attentes.

**Solutions:**
1. Vérifier l'ordre des octets (byte order / word order) :
   ```python
   from pymodbus.constants import Endian

   # Essayer différentes combinaisons
   value = driver.read_float(1000, byte_order=Endian.LITTLE, word_order=Endian.BIG)
   ```
2. Vérifier le type de registre (Holding vs Input)
3. Vérifier les adresses de registres dans la documentation SA32
4. Utiliser le mode mock pour isoler le problème

### Problème : Erreur d'importation pymodbus

**Symptômes:**
```
ImportError: Le module 'pymodbus' est requis
```

**Solutions:**
```bash
# Installer pymodbus
pip install pymodbus>=3.0.0

# Ou utiliser le mode mock (pas besoin de pymodbus)
driver = SA32Driver(mock_mode=True)
```

### Problème : Port série déjà utilisé (RTU)

**Symptômes:**
```
SA32ConnectionError: Port COM3 déjà utilisé
```

**Solutions:**
1. Fermer les autres applications utilisant le port
2. Vérifier qu'une instance précédente du driver n'est pas encore active
3. Sur Linux, vérifier les permissions :
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   # Ou ajouter l'utilisateur au groupe dialout
   sudo usermod -a -G dialout $USER
   ```

### Problème : Thread-safety dans PyQt5

**Symptômes:**
Erreurs aléatoires ou crashes dans applications multi-thread.

**Solutions:**
1. Toujours créer le driver dans le thread principal
2. Passer le driver aux threads enfants (ne pas le recréer)
3. Utiliser les callbacks pour communiquer avec l'UI
4. Exemple correct :
   ```python
   # Dans le thread principal
   driver = SA32Driver(host='192.168.1.100')
   driver.connect()

   # Passer au thread enfant
   thread = AcquisitionThread(driver)  # Passe la référence
   thread.start()
   ```

### Logs de Débogage

Pour activer les logs détaillés :

```python
import logging

# Configurer le niveau de log
logging.basicConfig(level=logging.DEBUG)

# Créer le driver avec logs détaillés
driver = SA32Driver(
    host='192.168.1.100',
    log_level=logging.DEBUG
)
```

---

## 📝 Changelog

### Version 1.0.0 (2025-11-16)

**Fonctionnalités initiales:**
- ✅ Support Modbus TCP et RTU
- ✅ Lecture/écriture de registres (16 bits et float 32 bits)
- ✅ Mode mock pour tests
- ✅ Context manager
- ✅ Callbacks
- ✅ Thread-safety
- ✅ Auto-reconnexion
- ✅ Gestion d'erreurs robuste
- ✅ Logging complet
- ✅ Tests unitaires (95%+ couverture)
- ✅ Documentation complète

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Pour contribuer :

1. **Fork** le dépôt
2. Créer une **branche** pour votre fonctionnalité (`git checkout -b feature/ma-fonctionnalite`)
3. **Committer** vos changements (`git commit -m 'Ajout de ma fonctionnalité'`)
4. **Pousser** vers la branche (`git push origin feature/ma-fonctionnalite`)
5. Ouvrir une **Pull Request**

### Standards de Code

- Suivre **PEP 8**
- Ajouter des **docstrings Google Style** pour toutes les fonctions publiques
- Ajouter des **tests unitaires** pour les nouvelles fonctionnalités
- Maintenir la **couverture de code** à 95%+
- Utiliser les **type hints** Python

### Exécuter les Vérifications

```bash
# Style de code
pylint sa32_driver.py

# Type checking
mypy sa32_driver.py

# Tests
pytest test_sa32_driver.py --cov=sa32_driver
```

---

## 📄 License

Ce projet est sous licence **MIT**. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 👥 Auteurs

**Équipe SOLINOV**
- Guillaume Divrechy - Développement initial
- [Autres contributeurs](https://github.com/SOLINOV/SA32/contributors)

---

## 📧 Support

Pour toute question ou problème :

- **Documentation technique SA32** : Consulter le manuel utilisateur SOLINOV
- **Issues GitHub** : [https://github.com/SOLINOV/SA32/issues](https://github.com/SOLINOV/SA32/issues)
- **Email** : support@solinov.com

---

## 🙏 Remerciements

- **PyModbus** - Excellente bibliothèque Modbus Python
- **SOLINOV** - Spécifications et support technique
- Communauté Python pour les outils et bibliothèques

---

**Dernière mise à jour :** 2025-11-16
**Version du driver :** 1.0.0
**Compatibilité Python :** 3.7+
