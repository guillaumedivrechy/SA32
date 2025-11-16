#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Driver pour équipement SA32 - Système d'Acquisition thermique.

Ce module fournit une interface Python complète pour communiquer avec l'équipement
SA32 de SOLINOV via les protocoles Modbus TCP et Modbus RTU.

Le SA32 est un système d'acquisition et de mesure thermique/thermodynamique utilisé
dans les bancs de test pour mesurer des paramètres comme les températures, débits,
puissance thermique, et calculer des nombres adimensionnels (Nusselt, Reynolds, etc.).

Examples:
    Utilisation basique avec Modbus TCP:

    >>> from sa32_driver import SA32Driver
    >>>
    >>> # Connexion à l'équipement
    >>> with SA32Driver(host='192.168.1.100', port=502, slave_id=1) as sa32:
    ...     # Lecture d'un registre
    ...     value = sa32.read_holding_register(1000)
    ...     print(f"Valeur du registre 1000: {value}")
    ...
    ...     # Écriture d'un registre
    ...     sa32.write_holding_register(2000, 42)

    Utilisation avec Modbus RTU:

    >>> sa32 = SA32Driver(
    ...     protocol='RTU',
    ...     port='COM3',
    ...     baudrate=9600,
    ...     slave_id=1
    ... )
    >>> sa32.connect()
    >>> temperature = sa32.read_holding_register(1000)
    >>> sa32.disconnect()

    Mode mock pour les tests:

    >>> sa32_mock = SA32Driver(mock_mode=True)
    >>> sa32_mock.connect()
    >>> value = sa32_mock.read_holding_register(1000)  # Retourne une valeur simulée

Auteur: Équipe SOLINOV
Version: 1.0.0
Date: 2025-11-16
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Union, Dict, List, Callable, Any
from enum import Enum

try:
    # Essayer d'importer pymodbus (compatible avec versions 3.0.x et 3.x)
    try:
        # pymodbus 3.0.x
        from pymodbus.client import ModbusTcpClient, ModbusSerialClient
    except ImportError:
        # pymodbus 3.x (nouveau format)
        from pymodbus.client.tcp import ModbusTcpClient
        from pymodbus.client.serial import ModbusSerialClient

    from pymodbus.exceptions import ModbusException, ConnectionException

    # Pour Endian et payload, gérer les différences de versions
    try:
        from pymodbus.constants import Endian
    except ImportError:
        # pymodbus 3.x n'a pas Endian dans constants
        # Utiliser int directement (Big Endian = '>', Little Endian = '<')
        class Endian:
            BIG = '>'
            LITTLE = '<'

    try:
        from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
    except ImportError:
        # pymodbus 3.x n'a plus le module payload
        # Utiliser struct pour conversion (implémentation simplifiée)
        import struct

        class BinaryPayloadDecoder:
            def __init__(self, payload, byteorder='>', wordorder='>'):
                self.payload = payload
                self.byteorder = byteorder

            @classmethod
            def fromRegisters(cls, registers, byteorder='>', wordorder='>'):
                # Convertir registres en bytes
                payload = b''.join(reg.to_bytes(2, byteorder='big') for reg in registers)
                return cls(payload, byteorder, wordorder)

            def decode_32bit_float(self):
                # Décoder 4 bytes en float
                if self.byteorder == '>':
                    return struct.unpack('>f', self.payload[:4])[0]
                else:
                    return struct.unpack('<f', self.payload[:4])[0]

        class BinaryPayloadBuilder:
            def __init__(self, byteorder='>', wordorder='>'):
                self.byteorder = byteorder
                self.payload = bytearray()

            def add_32bit_float(self, value):
                if self.byteorder == '>':
                    self.payload.extend(struct.pack('>f', value))
                else:
                    self.payload.extend(struct.pack('<f', value))

            def to_registers(self):
                # Convertir bytes en registres 16-bit
                registers = []
                for i in range(0, len(self.payload), 2):
                    reg = int.from_bytes(self.payload[i:i+2], byteorder='big')
                    registers.append(reg)
                return registers

    PYMODBUS_AVAILABLE = True
    # Valeurs par défaut pour Endian
    DEFAULT_BYTE_ORDER = Endian.BIG
    DEFAULT_WORD_ORDER = Endian.BIG

except ImportError:
    PYMODBUS_AVAILABLE = False
    # Définir des placeholders si pymodbus n'est pas disponible
    ModbusTcpClient = None
    ModbusSerialClient = None
    ModbusException = Exception
    ConnectionException = Exception
    Endian = None
    BinaryPayloadDecoder = None
    BinaryPayloadBuilder = None
    DEFAULT_BYTE_ORDER = None
    DEFAULT_WORD_ORDER = None


# ============================================================================
# CONSTANTES
# ============================================================================

# Paramètres de communication série par défaut (basés sur la documentation)
DEFAULT_BAUDRATE = 9600
DEFAULT_DATA_BITS = 8
DEFAULT_PARITY = 'N'  # None
DEFAULT_STOP_BITS = 1
DEFAULT_TIMEOUT = 10.0  # secondes

# Paramètres Modbus TCP
DEFAULT_TCP_PORT = 502
DEFAULT_TCP_TIMEOUT = 10.0

# Codes fonction Modbus
MODBUS_FUNC_READ_HOLDING_REGISTERS = 0x03
MODBUS_FUNC_READ_INPUT_REGISTERS = 0x04
MODBUS_FUNC_WRITE_SINGLE_REGISTER = 0x06
MODBUS_FUNC_WRITE_MULTIPLE_REGISTERS = 0x10


# ============================================================================
# CLASSES D'ERREUR
# ============================================================================

@dataclass
class EquipmentError:
    """
    Structure d'erreur standardisée pour compatibilité avec les autres drivers.

    Attributes:
        status (bool): True si une erreur est présente, False sinon.
        code (int): Code numérique de l'erreur (0 = pas d'erreur).
        source (str): Description de la source/nature de l'erreur.
    """
    status: bool = False
    code: int = 0
    source: str = ""

    def __bool__(self) -> bool:
        """Permet d'utiliser l'objet dans un contexte booléen."""
        return self.status

    def __str__(self) -> str:
        """Représentation textuelle de l'erreur."""
        if self.status:
            return f"Error {self.code}: {self.source}"
        return "No error"


class SA32Exception(Exception):
    """Exception de base pour le driver SA32."""
    pass


class SA32ConnectionError(SA32Exception):
    """Exception levée lors d'erreurs de connexion."""
    pass


class SA32CommunicationError(SA32Exception):
    """Exception levée lors d'erreurs de communication Modbus."""
    pass


class SA32ConfigurationError(SA32Exception):
    """Exception levée lors d'erreurs de configuration."""
    pass


class SA32TimeoutError(SA32Exception):
    """Exception levée lors de dépassement de timeout."""
    pass


# ============================================================================
# ÉNUMÉRATIONS
# ============================================================================

class ModbusProtocol(Enum):
    """Protocoles Modbus supportés."""
    TCP = "TCP"
    RTU = "RTU"


class RegisterType(Enum):
    """Types de registres Modbus."""
    HOLDING = "holding"
    INPUT = "input"


# ============================================================================
# CLASSE PRINCIPALE
# ============================================================================

class SA32Driver:
    """
    Driver principal pour l'équipement SA32.

    Cette classe fournit une interface complète pour communiquer avec le système
    d'acquisition thermique SA32 via Modbus TCP ou RTU. Elle gère automatiquement
    les connexions, la conversion des données, la gestion d'erreurs, et le logging.

    Attributes:
        protocol (ModbusProtocol): Protocole Modbus utilisé (TCP ou RTU).
        host (str): Adresse IP pour Modbus TCP.
        port (Union[str, int]): Port COM (RTU) ou port TCP (TCP).
        slave_id (int): Adresse de l'esclave Modbus.
        baudrate (int): Vitesse de communication série (RTU uniquement).
        timeout (float): Timeout pour les opérations de communication.
        mock_mode (bool): Active le mode simulation (sans équipement réel).
        logger (logging.Logger): Logger pour tracer les opérations.

    Thread Safety:
        Cette classe est thread-safe grâce à l'utilisation d'un verrou (lock)
        pour protéger les opérations de communication. Elle peut être utilisée
        dans des applications multi-thread comme PyQt5.
    """

    def __init__(
        self,
        protocol: str = 'TCP',
        host: str = '127.0.0.1',
        port: Union[str, int] = DEFAULT_TCP_PORT,
        slave_id: int = 1,
        baudrate: int = DEFAULT_BAUDRATE,
        parity: str = DEFAULT_PARITY,
        stopbits: int = DEFAULT_STOP_BITS,
        bytesize: int = DEFAULT_DATA_BITS,
        timeout: float = DEFAULT_TIMEOUT,
        auto_reconnect: bool = False,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 3,
        mock_mode: bool = False,
        log_level: int = logging.INFO
    ):
        """
        Initialise le driver SA32.

        Args:
            protocol: Protocole Modbus ('TCP' ou 'RTU').
            host: Adresse IP de l'équipement (TCP uniquement).
            port: Port COM (ex: 'COM3', '/dev/ttyUSB0') pour RTU ou numéro de port pour TCP.
            slave_id: Adresse de l'esclave Modbus (1-247).
            baudrate: Vitesse de communication série en bps (RTU).
            parity: Parité ('N', 'E', 'O') (RTU).
            stopbits: Nombre de bits d'arrêt (1 ou 2) (RTU).
            bytesize: Nombre de bits de données (7 ou 8) (RTU).
            timeout: Timeout en secondes pour les opérations.
            auto_reconnect: Active la reconnexion automatique en cas de perte de connexion.
            reconnect_delay: Délai en secondes entre les tentatives de reconnexion.
            max_reconnect_attempts: Nombre maximum de tentatives de reconnexion.
            mock_mode: Active le mode simulation (pour tests sans équipement).
            log_level: Niveau de logging (ex: logging.DEBUG, logging.INFO).

        Raises:
            SA32ConfigurationError: Si la configuration est invalide.
            ImportError: Si pymodbus n'est pas installé et mock_mode=False.
        """
        # Configuration du logger
        self.logger = logging.getLogger(f'SA32Driver[{slave_id}]')
        self.logger.setLevel(log_level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # Vérification de pymodbus
        if not PYMODBUS_AVAILABLE and not mock_mode:
            raise ImportError(
                "Le module 'pymodbus' est requis. "
                "Installez-le avec: pip install pymodbus"
            )

        # Validation de la configuration
        self._validate_config(protocol, slave_id, baudrate, bytesize, parity, stopbits)

        # Paramètres de connexion
        self.protocol = ModbusProtocol[protocol.upper()]
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.timeout = timeout

        # Paramètres de reconnexion
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        # Mode simulation
        self.mock_mode = mock_mode

        # Client Modbus
        self._client: Optional[Union[ModbusTcpClient, ModbusSerialClient]] = None
        self._connected = False
        self._lock = threading.RLock()  # Verrou pour thread-safety

        # Callbacks pour notifications
        self._callbacks: Dict[str, List[Callable]] = {
            'on_connect': [],
            'on_disconnect': [],
            'on_error': [],
            'on_data_received': []
        }

        # Données simulées pour mode mock
        self._mock_registers: Dict[int, int] = {}

        # Dernière erreur
        self._last_error = EquipmentError()

        self.logger.info(
            f"Driver SA32 initialisé - Protocole: {self.protocol.value}, "
            f"Slave ID: {self.slave_id}, Mock: {self.mock_mode}"
        )

    def _validate_config(
        self,
        protocol: str,
        slave_id: int,
        baudrate: int,
        bytesize: int,
        parity: str,
        stopbits: int
    ) -> None:
        """
        Valide la configuration du driver.

        Args:
            protocol: Protocole Modbus.
            slave_id: Adresse de l'esclave.
            baudrate: Vitesse de communication.
            bytesize: Nombre de bits de données.
            parity: Parité.
            stopbits: Nombre de bits d'arrêt.

        Raises:
            SA32ConfigurationError: Si un paramètre est invalide.
        """
        if protocol.upper() not in ['TCP', 'RTU']:
            raise SA32ConfigurationError(
                f"Protocole invalide: {protocol}. Utilisez 'TCP' ou 'RTU'."
            )

        if not 1 <= slave_id <= 247:
            raise SA32ConfigurationError(
                f"Slave ID invalide: {slave_id}. Doit être entre 1 et 247."
            )

        valid_baudrates = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
        if baudrate not in valid_baudrates:
            raise SA32ConfigurationError(
                f"Baudrate invalide: {baudrate}. Valeurs valides: {valid_baudrates}"
            )

        if bytesize not in [7, 8]:
            raise SA32ConfigurationError(
                f"Bytesize invalide: {bytesize}. Doit être 7 ou 8."
            )

        if parity.upper() not in ['N', 'E', 'O']:
            raise SA32ConfigurationError(
                f"Parité invalide: {parity}. Utilisez 'N', 'E' ou 'O'."
            )

        if stopbits not in [1, 2]:
            raise SA32ConfigurationError(
                f"Stop bits invalide: {stopbits}. Doit être 1 ou 2."
            )

    # ========================================================================
    # GESTION DE LA CONNEXION
    # ========================================================================

    def connect(self) -> bool:
        """
        Établit la connexion avec l'équipement SA32.

        Returns:
            bool: True si la connexion est établie avec succès, False sinon.

        Raises:
            SA32ConnectionError: Si la connexion échoue après toutes les tentatives.
        """
        with self._lock:
            if self._connected:
                self.logger.warning("Déjà connecté à l'équipement SA32")
                return True

            if self.mock_mode:
                self._connected = True
                self.logger.info("Mode MOCK: Connexion simulée établie")
                self._trigger_callbacks('on_connect')
                return True

            try:
                # Création du client Modbus selon le protocole
                if self.protocol == ModbusProtocol.TCP:
                    self._client = ModbusTcpClient(
                        host=self.host,
                        port=self.port,
                        timeout=self.timeout
                    )
                    self.logger.info(
                        f"Connexion Modbus TCP à {self.host}:{self.port}..."
                    )
                else:  # RTU
                    self._client = ModbusSerialClient(
                        port=self.port,
                        baudrate=self.baudrate,
                        bytesize=self.bytesize,
                        parity=self.parity,
                        stopbits=self.stopbits,
                        timeout=self.timeout
                    )
                    self.logger.info(
                        f"Connexion Modbus RTU sur {self.port} "
                        f"à {self.baudrate} bps..."
                    )

                # Tentative de connexion
                if self._client.connect():
                    self._connected = True
                    self._last_error = EquipmentError()
                    self.logger.info("Connexion établie avec succès")
                    self._trigger_callbacks('on_connect')
                    return True
                else:
                    raise SA32ConnectionError(
                        "Impossible de se connecter à l'équipement SA32"
                    )

            except Exception as e:
                error_msg = f"Erreur lors de la connexion: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(
                    status=True,
                    code=-1,
                    source=error_msg
                )
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32ConnectionError(error_msg) from e

    def disconnect(self) -> None:
        """
        Ferme la connexion avec l'équipement SA32.

        Cette méthode libère proprement les ressources de communication.
        Elle est automatiquement appelée lors de l'utilisation du context manager.
        """
        with self._lock:
            if not self._connected:
                self.logger.warning("Aucune connexion active à fermer")
                return

            if self.mock_mode:
                self._connected = False
                self.logger.info("Mode MOCK: Connexion simulée fermée")
                self._trigger_callbacks('on_disconnect')
                return

            try:
                if self._client:
                    self._client.close()
                    self.logger.info("Connexion fermée avec succès")
                self._connected = False
                self._client = None
                self._trigger_callbacks('on_disconnect')

            except Exception as e:
                self.logger.error(f"Erreur lors de la fermeture: {str(e)}")
                # On force la déconnexion même en cas d'erreur
                self._connected = False
                self._client = None

    def is_connected(self) -> bool:
        """
        Vérifie si la connexion est active.

        Returns:
            bool: True si connecté, False sinon.
        """
        return self._connected

    def _ensure_connected(self) -> None:
        """
        Vérifie que la connexion est active, tente une reconnexion si nécessaire.

        Raises:
            SA32ConnectionError: Si aucune connexion n'est active et la reconnexion échoue.
        """
        if not self._connected:
            if self.auto_reconnect:
                self.logger.warning(
                    "Connexion perdue, tentative de reconnexion automatique..."
                )
                self._attempt_reconnect()
            else:
                error_msg = "Aucune connexion active. Appelez connect() d'abord."
                self._last_error = EquipmentError(
                    status=True,
                    code=-1,
                    source=error_msg
                )
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32ConnectionError(error_msg)

    def _attempt_reconnect(self) -> bool:
        """
        Tente de rétablir la connexion avec l'équipement.

        Returns:
            bool: True si la reconnexion réussit, False sinon.
        """
        for attempt in range(1, self.max_reconnect_attempts + 1):
            self.logger.info(
                f"Tentative de reconnexion {attempt}/{self.max_reconnect_attempts}..."
            )
            try:
                if self.connect():
                    self.logger.info("Reconnexion réussie")
                    return True
            except SA32ConnectionError:
                if attempt < self.max_reconnect_attempts:
                    time.sleep(self.reconnect_delay)

        self.logger.error(
            f"Échec de la reconnexion après {self.max_reconnect_attempts} tentatives"
        )
        return False

    # ========================================================================
    # OPÉRATIONS MODBUS DE BAS NIVEAU
    # ========================================================================

    def read_holding_registers(
        self,
        address: int,
        count: int = 1
    ) -> Optional[List[int]]:
        """
        Lit plusieurs registres Holding (fonction 0x03).

        Args:
            address: Adresse du premier registre à lire.
            count: Nombre de registres à lire.

        Returns:
            Liste des valeurs lues, ou None en cas d'erreur.

        Raises:
            SA32CommunicationError: Si la lecture échoue.
            SA32ConnectionError: Si aucune connexion n'est active.
        """
        self._ensure_connected()

        with self._lock:
            # Mode simulation
            if self.mock_mode:
                values = self._mock_read_registers(address, count)
                self._trigger_callbacks('on_data_received', {'address': address, 'values': values})
                return values

            try:
                self.logger.debug(
                    f"Lecture Holding Registers: addr={address}, count={count}"
                )

                response = self._client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=self.slave_id
                )

                if response.isError():
                    error_msg = f"Erreur Modbus lors de la lecture: {response}"
                    self.logger.error(error_msg)
                    self._last_error = EquipmentError(
                        status=True,
                        code=response.exception_code if hasattr(response, 'exception_code') else -1,
                        source=error_msg
                    )
                    raise SA32CommunicationError(error_msg)

                values = response.registers
                self.logger.debug(f"Valeurs lues: {values}")
                self._last_error = EquipmentError()
                self._trigger_callbacks('on_data_received', {'address': address, 'values': values})
                return values

            except ModbusException as e:
                error_msg = f"Exception Modbus: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-2, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e
            except Exception as e:
                error_msg = f"Erreur inattendue lors de la lecture: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-3, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e

    def read_holding_register(self, address: int) -> Optional[int]:
        """
        Lit un seul registre Holding.

        Args:
            address: Adresse du registre à lire.

        Returns:
            Valeur du registre, ou None en cas d'erreur.
        """
        result = self.read_holding_registers(address, 1)
        return result[0] if result else None

    def read_input_registers(
        self,
        address: int,
        count: int = 1
    ) -> Optional[List[int]]:
        """
        Lit plusieurs registres Input (fonction 0x04).

        Args:
            address: Adresse du premier registre à lire.
            count: Nombre de registres à lire.

        Returns:
            Liste des valeurs lues, ou None en cas d'erreur.

        Raises:
            SA32CommunicationError: Si la lecture échoue.
            SA32ConnectionError: Si aucune connexion n'est active.
        """
        self._ensure_connected()

        with self._lock:
            # Mode simulation
            if self.mock_mode:
                values = self._mock_read_registers(address, count)
                self._trigger_callbacks('on_data_received', {'address': address, 'values': values})
                return values

            try:
                self.logger.debug(
                    f"Lecture Input Registers: addr={address}, count={count}"
                )

                response = self._client.read_input_registers(
                    address=address,
                    count=count,
                    slave=self.slave_id
                )

                if response.isError():
                    error_msg = f"Erreur Modbus lors de la lecture: {response}"
                    self.logger.error(error_msg)
                    self._last_error = EquipmentError(
                        status=True,
                        code=response.exception_code if hasattr(response, 'exception_code') else -1,
                        source=error_msg
                    )
                    raise SA32CommunicationError(error_msg)

                values = response.registers
                self.logger.debug(f"Valeurs lues: {values}")
                self._last_error = EquipmentError()
                self._trigger_callbacks('on_data_received', {'address': address, 'values': values})
                return values

            except ModbusException as e:
                error_msg = f"Exception Modbus: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-2, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e
            except Exception as e:
                error_msg = f"Erreur inattendue lors de la lecture: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-3, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e

    def read_input_register(self, address: int) -> Optional[int]:
        """
        Lit un seul registre Input.

        Args:
            address: Adresse du registre à lire.

        Returns:
            Valeur du registre, ou None en cas d'erreur.
        """
        result = self.read_input_registers(address, 1)
        return result[0] if result else None

    def write_register(self, address: int, value: int) -> bool:
        """
        Écrit un seul registre Holding (fonction 0x06).

        Args:
            address: Adresse du registre à écrire.
            value: Valeur à écrire (0-65535).

        Returns:
            True si l'écriture réussit, False sinon.

        Raises:
            SA32CommunicationError: Si l'écriture échoue.
            SA32ConnectionError: Si aucune connexion n'est active.
        """
        self._ensure_connected()

        with self._lock:
            # Mode simulation
            if self.mock_mode:
                return self._mock_write_register(address, value)

            try:
                self.logger.debug(f"Écriture registre: addr={address}, value={value}")

                response = self._client.write_register(
                    address=address,
                    value=value,
                    slave=self.slave_id
                )

                if response.isError():
                    error_msg = f"Erreur Modbus lors de l'écriture: {response}"
                    self.logger.error(error_msg)
                    self._last_error = EquipmentError(
                        status=True,
                        code=response.exception_code if hasattr(response, 'exception_code') else -1,
                        source=error_msg
                    )
                    raise SA32CommunicationError(error_msg)

                self.logger.debug("Écriture réussie")
                self._last_error = EquipmentError()
                return True

            except ModbusException as e:
                error_msg = f"Exception Modbus: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-2, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e
            except Exception as e:
                error_msg = f"Erreur inattendue lors de l'écriture: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-3, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e

    def write_registers(self, address: int, values: List[int]) -> bool:
        """
        Écrit plusieurs registres Holding (fonction 0x10).

        Args:
            address: Adresse du premier registre à écrire.
            values: Liste des valeurs à écrire.

        Returns:
            True si l'écriture réussit, False sinon.

        Raises:
            SA32CommunicationError: Si l'écriture échoue.
            SA32ConnectionError: Si aucune connexion n'est active.
        """
        self._ensure_connected()

        with self._lock:
            # Mode simulation
            if self.mock_mode:
                for i, value in enumerate(values):
                    self._mock_write_register(address + i, value)
                return True

            try:
                self.logger.debug(
                    f"Écriture registres: addr={address}, count={len(values)}"
                )

                response = self._client.write_registers(
                    address=address,
                    values=values,
                    slave=self.slave_id
                )

                if response.isError():
                    error_msg = f"Erreur Modbus lors de l'écriture: {response}"
                    self.logger.error(error_msg)
                    self._last_error = EquipmentError(
                        status=True,
                        code=response.exception_code if hasattr(response, 'exception_code') else -1,
                        source=error_msg
                    )
                    raise SA32CommunicationError(error_msg)

                self.logger.debug("Écriture réussie")
                self._last_error = EquipmentError()
                return True

            except ModbusException as e:
                error_msg = f"Exception Modbus: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-2, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e
            except Exception as e:
                error_msg = f"Erreur inattendue lors de l'écriture: {str(e)}"
                self.logger.error(error_msg)
                self._last_error = EquipmentError(status=True, code=-3, source=error_msg)
                self._trigger_callbacks('on_error', self._last_error)
                raise SA32CommunicationError(error_msg) from e

    # ========================================================================
    # CONVERSION DE DONNÉES
    # ========================================================================

    def read_float(
        self,
        address: int,
        register_type: RegisterType = RegisterType.HOLDING,
        byte_order = None,
        word_order = None
    ) -> Optional[float]:
        """
        Lit un nombre flottant 32 bits (2 registres).

        Args:
            address: Adresse du premier registre.
            register_type: Type de registre (HOLDING ou INPUT).
            byte_order: Ordre des octets (BIG ou LITTLE endian). Par défaut: BIG.
            word_order: Ordre des mots (BIG ou LITTLE endian). Par défaut: BIG.

        Returns:
            Valeur flottante lue, ou None en cas d'erreur.
        """
        # Utiliser les valeurs par défaut si non spécifiées
        if byte_order is None:
            byte_order = DEFAULT_BYTE_ORDER
        if word_order is None:
            word_order = DEFAULT_WORD_ORDER

        if register_type == RegisterType.HOLDING:
            registers = self.read_holding_registers(address, 2)
        else:
            registers = self.read_input_registers(address, 2)

        if not registers:
            return None

        decoder = BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=byte_order,
            wordorder=word_order
        )
        return decoder.decode_32bit_float()

    def write_float(
        self,
        address: int,
        value: float,
        byte_order = None,
        word_order = None
    ) -> bool:
        """
        Écrit un nombre flottant 32 bits (2 registres).

        Args:
            address: Adresse du premier registre.
            value: Valeur flottante à écrire.
            byte_order: Ordre des octets (BIG ou LITTLE endian). Par défaut: BIG.
            word_order: Ordre des mots (BIG ou LITTLE endian). Par défaut: BIG.

        Returns:
            True si l'écriture réussit, False sinon.
        """
        # Utiliser les valeurs par défaut si non spécifiées
        if byte_order is None:
            byte_order = DEFAULT_BYTE_ORDER
        if word_order is None:
            word_order = DEFAULT_WORD_ORDER

        builder = BinaryPayloadBuilder(byteorder=byte_order, wordorder=word_order)
        builder.add_32bit_float(value)
        registers = builder.to_registers()
        return self.write_registers(address, registers)

    # ========================================================================
    # MÉTHODES DE HAUT NIVEAU SPÉCIFIQUES AU SA32
    # ========================================================================
    # NOTE: Les adresses de registres ci-dessous sont des EXEMPLES.
    # Elles doivent être mises à jour avec les vraies adresses de votre équipement.

    def read_temperature(
        self,
        channel: int,
        temp_type: str = 'Te'
    ) -> Optional[float]:
        """
        Lit une température sur un canal donné.

        Args:
            channel: Numéro du canal (voie).
            temp_type: Type de température ('Te', 'Ts', 'Tw', 'T_bulk').

        Returns:
            Température en °C, ou None en cas d'erreur.

        Note:
            Cette méthode est un EXEMPLE. Les adresses de registres doivent être
            configurées selon la documentation technique de votre équipement SA32.
        """
        # EXEMPLE: Les adresses doivent être configurées selon votre équipement
        # base_address = 1000 + (channel * 100)
        # temp_offsets = {'Te': 0, 'Ts': 2, 'Tw': 4, 'T_bulk': 6}
        # address = base_address + temp_offsets.get(temp_type, 0)
        # return self.read_float(address)

        self.logger.warning(
            "read_temperature() est une méthode exemple. "
            "Configurez les adresses de registres selon votre équipement."
        )
        return None

    def read_power(self) -> Optional[float]:
        """
        Lit la puissance thermique.

        Returns:
            Puissance en Watts, ou None en cas d'erreur.

        Note:
            Cette méthode est un EXEMPLE. L'adresse de registre doit être
            configurée selon la documentation technique de votre équipement SA32.
        """
        # EXEMPLE: address = 2000
        # return self.read_float(address)

        self.logger.warning(
            "read_power() est une méthode exemple. "
            "Configurez l'adresse de registre selon votre équipement."
        )
        return None

    def read_nusselt_number(self) -> Optional[float]:
        """
        Lit le nombre de Nusselt.

        Returns:
            Nombre de Nusselt (sans dimension), ou None en cas d'erreur.

        Note:
            Cette méthode est un EXEMPLE. L'adresse de registre doit être
            configurée selon la documentation technique de votre équipement SA32.
        """
        self.logger.warning(
            "read_nusselt_number() est une méthode exemple. "
            "Configurez l'adresse de registre selon votre équipement."
        )
        return None

    def read_reynolds_number(self) -> Optional[float]:
        """
        Lit le nombre de Reynolds.

        Returns:
            Nombre de Reynolds (sans dimension), ou None en cas d'erreur.

        Note:
            Cette méthode est un EXEMPLE. L'adresse de registre doit être
            configurée selon la documentation technique de votre équipement SA32.
        """
        self.logger.warning(
            "read_reynolds_number() est une méthode exemple. "
            "Configurez l'adresse de registre selon votre équipement."
        )
        return None

    def get_thermal_data(self) -> Dict[str, Any]:
        """
        Récupère un ensemble complet de données thermiques.

        Returns:
            Dictionnaire contenant toutes les mesures thermiques disponibles.

        Note:
            Cette méthode est un EXEMPLE qui doit être personnalisée selon
            les registres disponibles sur votre équipement SA32.
        """
        data = {
            'timestamp': time.time(),
            'power_w': self.read_power(),
            'nusselt': self.read_nusselt_number(),
            'reynolds': self.read_reynolds_number(),
            # Ajoutez d'autres mesures selon vos besoins
        }

        return data

    # ========================================================================
    # CALLBACKS ET NOTIFICATIONS
    # ========================================================================

    def register_callback(self, event: str, callback: Callable) -> None:
        """
        Enregistre une fonction de callback pour un événement.

        Args:
            event: Type d'événement ('on_connect', 'on_disconnect', 'on_error', 'on_data_received').
            callback: Fonction à appeler lors de l'événement.

        Example:
            >>> def on_error_handler(error):
            ...     print(f"Erreur détectée: {error}")
            >>> sa32.register_callback('on_error', on_error_handler)
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
            self.logger.debug(f"Callback enregistré pour l'événement: {event}")
        else:
            self.logger.warning(f"Événement inconnu: {event}")

    def unregister_callback(self, event: str, callback: Callable) -> None:
        """
        Désenregistre une fonction de callback.

        Args:
            event: Type d'événement.
            callback: Fonction à retirer.
        """
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)
            self.logger.debug(f"Callback désenregistré pour l'événement: {event}")

    def _trigger_callbacks(self, event: str, data: Any = None) -> None:
        """
        Déclenche tous les callbacks enregistrés pour un événement.

        Args:
            event: Type d'événement.
            data: Données à passer aux callbacks.
        """
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    if data is not None:
                        callback(data)
                    else:
                        callback()
                except Exception as e:
                    self.logger.error(f"Erreur dans le callback {event}: {str(e)}")

    # ========================================================================
    # GESTION D'ERREURS
    # ========================================================================

    def get_last_error(self) -> EquipmentError:
        """
        Retourne la dernière erreur survenue.

        Returns:
            Objet EquipmentError avec les détails de la dernière erreur.
        """
        return self._last_error

    def clear_error(self) -> None:
        """Efface la dernière erreur enregistrée."""
        self._last_error = EquipmentError()

    # ========================================================================
    # MODE MOCK (SIMULATION)
    # ========================================================================

    def _mock_read_registers(self, address: int, count: int) -> List[int]:
        """
        Simule la lecture de registres en mode mock.

        Args:
            address: Adresse de départ.
            count: Nombre de registres.

        Returns:
            Liste de valeurs simulées.
        """
        import random
        values = []
        for i in range(count):
            addr = address + i
            if addr not in self._mock_registers:
                # Génère une valeur aléatoire réaliste
                self._mock_registers[addr] = random.randint(0, 65535)
            values.append(self._mock_registers[addr])

        self.logger.debug(f"MOCK - Lecture: addr={address}, values={values}")
        return values

    def _mock_write_register(self, address: int, value: int) -> bool:
        """
        Simule l'écriture d'un registre en mode mock.

        Args:
            address: Adresse du registre.
            value: Valeur à écrire.

        Returns:
            True (toujours succès en mode mock).
        """
        self._mock_registers[address] = value
        self.logger.debug(f"MOCK - Écriture: addr={address}, value={value}")
        return True

    def set_mock_register(self, address: int, value: int) -> None:
        """
        Définit la valeur d'un registre en mode mock (pour tests).

        Args:
            address: Adresse du registre.
            value: Valeur à définir.
        """
        if self.mock_mode:
            self._mock_registers[address] = value
        else:
            self.logger.warning("set_mock_register() ne fonctionne qu'en mode mock")

    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================

    def __enter__(self):
        """Support du context manager (with statement)."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support du context manager (with statement)."""
        self.disconnect()
        return False  # Ne supprime pas les exceptions

    # ========================================================================
    # REPRÉSENTATION
    # ========================================================================

    def __repr__(self) -> str:
        """Représentation de l'objet."""
        status = "connecté" if self._connected else "déconnecté"
        return (
            f"SA32Driver(protocol={self.protocol.value}, "
            f"slave_id={self.slave_id}, status={status}, mock={self.mock_mode})"
        )


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    # Configuration du logging pour l'exemple
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("EXEMPLE D'UTILISATION DU DRIVER SA32")
    print("=" * 70)

    # ========================================================================
    # EXEMPLE 1: Mode MOCK (sans équipement réel)
    # ========================================================================
    print("\n### EXEMPLE 1: Mode MOCK ###\n")

    try:
        # Création du driver en mode simulation
        sa32_mock = SA32Driver(mock_mode=True, log_level=logging.DEBUG)

        # Utilisation du context manager
        with sa32_mock:
            # Définir une valeur simulée
            sa32_mock.set_mock_register(1000, 12345)

            # Lecture d'un registre
            value = sa32_mock.read_holding_register(1000)
            print(f"Valeur lue (mock): {value}")

            # Écriture d'un registre
            sa32_mock.write_register(2000, 9999)

            # Lecture multiple
            values = sa32_mock.read_holding_registers(1000, 5)
            print(f"Valeurs multiples: {values}")

        print("✓ Exemple 1 terminé avec succès\n")

    except SA32Exception as e:
        print(f"✗ Erreur dans l'exemple 1: {e}\n")

    # ========================================================================
    # EXEMPLE 2: Modbus TCP (nécessite un équipement réel ou simulateur)
    # ========================================================================
    print("\n### EXEMPLE 2: Modbus TCP (commenté - nécessite équipement) ###\n")

    example_tcp_code = '''
    try:
        # Connexion Modbus TCP
        sa32_tcp = SA32Driver(
            protocol='TCP',
            host='192.168.1.100',  # Adresse IP de votre équipement
            port=502,
            slave_id=1,
            timeout=5.0,
            auto_reconnect=True
        )

        # Enregistrer un callback d'erreur
        def on_error(error):
            print(f"Erreur détectée: {error}")

        sa32_tcp.register_callback('on_error', on_error)

        # Connexion
        sa32_tcp.connect()

        # Lecture d'un registre
        value = sa32_tcp.read_holding_register(1000)
        print(f"Registre 1000: {value}")

        # Lecture d'un float (2 registres)
        temperature = sa32_tcp.read_float(2000)
        print(f"Température: {temperature} °C")

        # Écriture d'un registre
        sa32_tcp.write_register(3000, 500)

        # Déconnexion
        sa32_tcp.disconnect()

    except SA32Exception as e:
        print(f"Erreur: {e}")
    '''

    print(example_tcp_code)

    # ========================================================================
    # EXEMPLE 3: Modbus RTU (nécessite un port série)
    # ========================================================================
    print("\n### EXEMPLE 3: Modbus RTU (commenté - nécessite port série) ###\n")

    example_rtu_code = '''
    try:
        # Connexion Modbus RTU
        sa32_rtu = SA32Driver(
            protocol='RTU',
            port='COM3',  # ou '/dev/ttyUSB0' sur Linux
            baudrate=9600,
            parity='N',
            stopbits=1,
            slave_id=1
        )

        # Utilisation avec context manager
        with sa32_rtu:
            # Lecture d'un registre
            value = sa32_rtu.read_input_register(5000)
            print(f"Registre input 5000: {value}")

            # Écriture multiple
            sa32_rtu.write_registers(1000, [100, 200, 300])

    except SA32Exception as e:
        print(f"Erreur: {e}")
    '''

    print(example_rtu_code)

    print("\n" + "=" * 70)
    print("FIN DES EXEMPLES")
    print("=" * 70)
