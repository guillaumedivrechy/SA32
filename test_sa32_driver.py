#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests unitaires pour le driver SA32.

Ce module contient des tests pytest complets pour valider toutes les fonctionnalités
du driver SA32, incluant les modes mock et réel.

Pour exécuter les tests:
    pytest test_sa32_driver.py -v
    pytest test_sa32_driver.py -v --cov=sa32_driver --cov-report=html

Auteur: Équipe SOLINOV
Date: 2025-11-16
"""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
from typing import List

from sa32_driver import (
    SA32Driver,
    SA32Exception,
    SA32ConnectionError,
    SA32CommunicationError,
    SA32ConfigurationError,
    EquipmentError,
    ModbusProtocol,
    RegisterType,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_driver():
    """Fournit un driver en mode mock pour les tests."""
    driver = SA32Driver(mock_mode=True)
    yield driver
    if driver.is_connected():
        driver.disconnect()


@pytest.fixture
def mock_driver_connected():
    """Fournit un driver en mode mock déjà connecté."""
    driver = SA32Driver(mock_mode=True)
    driver.connect()
    yield driver
    if driver.is_connected():
        driver.disconnect()


@pytest.fixture
def tcp_driver_config():
    """Configuration pour driver Modbus TCP."""
    return {
        'protocol': 'TCP',
        'host': '192.168.1.100',
        'port': 502,
        'slave_id': 1,
        'timeout': 5.0
    }


@pytest.fixture
def rtu_driver_config():
    """Configuration pour driver Modbus RTU."""
    return {
        'protocol': 'RTU',
        'port': 'COM3',
        'baudrate': 9600,
        'slave_id': 1,
        'timeout': 5.0
    }


# ============================================================================
# TESTS D'INITIALISATION ET CONFIGURATION
# ============================================================================

class TestInitialization:
    """Tests d'initialisation du driver."""

    def test_default_initialization(self):
        """Test l'initialisation avec paramètres par défaut."""
        driver = SA32Driver(mock_mode=True)
        assert driver.protocol == ModbusProtocol.TCP
        assert driver.slave_id == 1
        assert driver.timeout == 10.0
        assert driver.mock_mode is True
        assert not driver.is_connected()

    def test_tcp_initialization(self, tcp_driver_config):
        """Test l'initialisation en mode TCP."""
        driver = SA32Driver(**tcp_driver_config, mock_mode=True)
        assert driver.protocol == ModbusProtocol.TCP
        assert driver.host == '192.168.1.100'
        assert driver.port == 502
        assert driver.slave_id == 1

    def test_rtu_initialization(self, rtu_driver_config):
        """Test l'initialisation en mode RTU."""
        driver = SA32Driver(**rtu_driver_config, mock_mode=True)
        assert driver.protocol == ModbusProtocol.RTU
        assert driver.port == 'COM3'
        assert driver.baudrate == 9600

    def test_invalid_protocol(self):
        """Test la détection de protocole invalide."""
        with pytest.raises(SA32ConfigurationError, match="Protocole invalide"):
            SA32Driver(protocol='INVALID', mock_mode=True)

    def test_invalid_slave_id(self):
        """Test la détection de slave ID invalide."""
        with pytest.raises(SA32ConfigurationError, match="Slave ID invalide"):
            SA32Driver(slave_id=0, mock_mode=True)

        with pytest.raises(SA32ConfigurationError, match="Slave ID invalide"):
            SA32Driver(slave_id=300, mock_mode=True)

    def test_invalid_baudrate(self):
        """Test la détection de baudrate invalide."""
        with pytest.raises(SA32ConfigurationError, match="Baudrate invalide"):
            SA32Driver(protocol='RTU', baudrate=1111, mock_mode=True)

    def test_invalid_bytesize(self):
        """Test la détection de bytesize invalide."""
        with pytest.raises(SA32ConfigurationError, match="Bytesize invalide"):
            SA32Driver(protocol='RTU', bytesize=9, mock_mode=True)

    def test_invalid_parity(self):
        """Test la détection de parité invalide."""
        with pytest.raises(SA32ConfigurationError, match="Parité invalide"):
            SA32Driver(protocol='RTU', parity='X', mock_mode=True)

    def test_invalid_stopbits(self):
        """Test la détection de stop bits invalide."""
        with pytest.raises(SA32ConfigurationError, match="Stop bits invalide"):
            SA32Driver(protocol='RTU', stopbits=3, mock_mode=True)


# ============================================================================
# TESTS DE CONNEXION/DÉCONNEXION
# ============================================================================

class TestConnection:
    """Tests de connexion et déconnexion."""

    def test_connect_mock_mode(self, mock_driver):
        """Test la connexion en mode mock."""
        assert not mock_driver.is_connected()
        result = mock_driver.connect()
        assert result is True
        assert mock_driver.is_connected()

    def test_disconnect_mock_mode(self, mock_driver_connected):
        """Test la déconnexion en mode mock."""
        assert mock_driver_connected.is_connected()
        mock_driver_connected.disconnect()
        assert not mock_driver_connected.is_connected()

    def test_connect_already_connected(self, mock_driver_connected):
        """Test la connexion quand déjà connecté."""
        assert mock_driver_connected.is_connected()
        result = mock_driver_connected.connect()
        assert result is True
        assert mock_driver_connected.is_connected()

    def test_disconnect_not_connected(self, mock_driver):
        """Test la déconnexion quand pas connecté."""
        assert not mock_driver.is_connected()
        mock_driver.disconnect()  # Ne doit pas lever d'exception
        assert not mock_driver.is_connected()

    def test_context_manager(self):
        """Test l'utilisation du context manager."""
        driver = SA32Driver(mock_mode=True)
        assert not driver.is_connected()

        with driver:
            assert driver.is_connected()

        assert not driver.is_connected()

    def test_context_manager_with_exception(self):
        """Test que le context manager ferme la connexion même avec exception."""
        driver = SA32Driver(mock_mode=True)

        try:
            with driver:
                assert driver.is_connected()
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert not driver.is_connected()


# ============================================================================
# TESTS DE LECTURE DE REGISTRES
# ============================================================================

class TestReadOperations:
    """Tests des opérations de lecture."""

    def test_read_holding_register_mock(self, mock_driver_connected):
        """Test la lecture d'un registre Holding en mode mock."""
        # Définir une valeur mock
        mock_driver_connected.set_mock_register(1000, 12345)

        # Lire le registre
        value = mock_driver_connected.read_holding_register(1000)
        assert value == 12345

    def test_read_holding_registers_multiple_mock(self, mock_driver_connected):
        """Test la lecture de plusieurs registres Holding."""
        # Définir des valeurs mock
        mock_driver_connected.set_mock_register(1000, 100)
        mock_driver_connected.set_mock_register(1001, 200)
        mock_driver_connected.set_mock_register(1002, 300)

        # Lire les registres
        values = mock_driver_connected.read_holding_registers(1000, 3)
        assert len(values) == 3
        assert values == [100, 200, 300]

    def test_read_input_register_mock(self, mock_driver_connected):
        """Test la lecture d'un registre Input en mode mock."""
        mock_driver_connected.set_mock_register(2000, 54321)
        value = mock_driver_connected.read_input_register(2000)
        assert value == 54321

    def test_read_input_registers_multiple_mock(self, mock_driver_connected):
        """Test la lecture de plusieurs registres Input."""
        values = mock_driver_connected.read_input_registers(3000, 5)
        assert len(values) == 5
        assert all(isinstance(v, int) for v in values)

    def test_read_not_connected(self, mock_driver):
        """Test la lecture sans connexion active."""
        with pytest.raises(SA32ConnectionError, match="Aucune connexion active"):
            mock_driver.read_holding_register(1000)

    def test_read_float_mock(self, mock_driver_connected):
        """Test la lecture d'un float (2 registres)."""
        # Note: Cette fonction nécessite pymodbus pour la conversion
        # En mode mock, elle retournera une valeur basée sur les registres simulés
        value = mock_driver_connected.read_float(4000)
        assert value is not None
        assert isinstance(value, float)


# ============================================================================
# TESTS D'ÉCRITURE DE REGISTRES
# ============================================================================

class TestWriteOperations:
    """Tests des opérations d'écriture."""

    def test_write_register_mock(self, mock_driver_connected):
        """Test l'écriture d'un registre en mode mock."""
        result = mock_driver_connected.write_register(1000, 9999)
        assert result is True

        # Vérifier que la valeur a été écrite
        value = mock_driver_connected.read_holding_register(1000)
        assert value == 9999

    def test_write_registers_multiple_mock(self, mock_driver_connected):
        """Test l'écriture de plusieurs registres."""
        values_to_write = [111, 222, 333, 444]
        result = mock_driver_connected.write_registers(2000, values_to_write)
        assert result is True

        # Vérifier que les valeurs ont été écrites
        values_read = mock_driver_connected.read_holding_registers(2000, 4)
        assert values_read == values_to_write

    def test_write_not_connected(self, mock_driver):
        """Test l'écriture sans connexion active."""
        with pytest.raises(SA32ConnectionError, match="Aucune connexion active"):
            mock_driver.write_register(1000, 100)

    def test_write_float_mock(self, mock_driver_connected):
        """Test l'écriture d'un float."""
        value_to_write = 123.456
        result = mock_driver_connected.write_float(3000, value_to_write)
        assert result is True

        # Lire et vérifier (approximation due à la conversion)
        value_read = mock_driver_connected.read_float(3000)
        assert value_read is not None
        assert abs(value_read - value_to_write) < 0.01  # Tolérance


# ============================================================================
# TESTS DE GESTION D'ERREURS
# ============================================================================

class TestErrorHandling:
    """Tests de la gestion d'erreurs."""

    def test_equipment_error_structure(self):
        """Test la structure EquipmentError."""
        # Pas d'erreur
        error = EquipmentError()
        assert error.status is False
        assert error.code == 0
        assert error.source == ""
        assert not error  # Doit être False en contexte booléen

        # Avec erreur
        error = EquipmentError(status=True, code=42, source="Test error")
        assert error.status is True
        assert error.code == 42
        assert error.source == "Test error"
        assert error  # Doit être True en contexte booléen
        assert "Error 42" in str(error)

    def test_get_last_error_no_error(self, mock_driver_connected):
        """Test get_last_error quand il n'y a pas d'erreur."""
        # Opération réussie
        mock_driver_connected.write_register(1000, 100)

        # Pas d'erreur
        error = mock_driver_connected.get_last_error()
        assert not error.status
        assert error.code == 0

    def test_clear_error(self, mock_driver):
        """Test l'effacement d'erreur."""
        # Simuler une erreur en forçant la lecture sans connexion
        try:
            mock_driver.read_holding_register(1000)
        except SA32ConnectionError:
            pass

        # Vérifier qu'une erreur est enregistrée
        error = mock_driver.get_last_error()
        assert error.status is True

        # Effacer l'erreur
        mock_driver.clear_error()
        error = mock_driver.get_last_error()
        assert not error.status


# ============================================================================
# TESTS DES CALLBACKS
# ============================================================================

class TestCallbacks:
    """Tests du système de callbacks."""

    def test_on_connect_callback(self, mock_driver):
        """Test le callback de connexion."""
        callback_called = []

        def on_connect():
            callback_called.append(True)

        mock_driver.register_callback('on_connect', on_connect)
        mock_driver.connect()

        assert len(callback_called) == 1

    def test_on_disconnect_callback(self, mock_driver_connected):
        """Test le callback de déconnexion."""
        callback_called = []

        def on_disconnect():
            callback_called.append(True)

        mock_driver_connected.register_callback('on_disconnect', on_disconnect)
        mock_driver_connected.disconnect()

        assert len(callback_called) == 1

    def test_on_error_callback(self, mock_driver):
        """Test le callback d'erreur."""
        errors_received = []

        def on_error(error):
            errors_received.append(error)

        mock_driver.register_callback('on_error', on_error)

        # Provoquer une erreur
        try:
            mock_driver.read_holding_register(1000)
        except SA32ConnectionError:
            pass

        assert len(errors_received) == 1
        assert errors_received[0].status is True

    def test_on_data_received_callback(self, mock_driver_connected):
        """Test le callback de réception de données."""
        data_received = []

        def on_data(data):
            data_received.append(data)

        mock_driver_connected.register_callback('on_data_received', on_data)
        mock_driver_connected.read_holding_register(1000)

        assert len(data_received) == 1
        assert 'address' in data_received[0]
        assert 'values' in data_received[0]

    def test_multiple_callbacks(self, mock_driver):
        """Test plusieurs callbacks pour le même événement."""
        counter = []

        def callback1():
            counter.append(1)

        def callback2():
            counter.append(2)

        mock_driver.register_callback('on_connect', callback1)
        mock_driver.register_callback('on_connect', callback2)
        mock_driver.connect()

        assert len(counter) == 2
        assert 1 in counter and 2 in counter

    def test_unregister_callback(self, mock_driver):
        """Test le désenregistrement de callback."""
        callback_called = []

        def on_connect():
            callback_called.append(True)

        mock_driver.register_callback('on_connect', on_connect)
        mock_driver.unregister_callback('on_connect', on_connect)
        mock_driver.connect()

        assert len(callback_called) == 0


# ============================================================================
# TESTS DE THREAD SAFETY
# ============================================================================

class TestThreadSafety:
    """Tests de la sécurité multi-thread."""

    def test_concurrent_reads(self, mock_driver_connected):
        """Test les lectures concurrentes depuis plusieurs threads."""
        results = []
        errors = []

        def read_worker(address, count):
            try:
                for _ in range(count):
                    value = mock_driver_connected.read_holding_register(address)
                    results.append(value)
            except Exception as e:
                errors.append(e)

        # Créer plusieurs threads qui lisent simultanément
        threads = []
        for i in range(5):
            thread = threading.Thread(target=read_worker, args=(1000 + i, 10))
            threads.append(thread)
            thread.start()

        # Attendre la fin de tous les threads
        for thread in threads:
            thread.join()

        # Vérifier qu'il n'y a pas eu d'erreurs
        assert len(errors) == 0
        assert len(results) == 50  # 5 threads × 10 lectures

    def test_concurrent_writes(self, mock_driver_connected):
        """Test les écritures concurrentes depuis plusieurs threads."""
        errors = []

        def write_worker(base_address, count):
            try:
                for i in range(count):
                    mock_driver_connected.write_register(base_address + i, i * 100)
            except Exception as e:
                errors.append(e)

        # Créer plusieurs threads qui écrivent simultanément
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=write_worker,
                args=(2000 + (i * 100), 10)
            )
            threads.append(thread)
            thread.start()

        # Attendre la fin de tous les threads
        for thread in threads:
            thread.join()

        # Vérifier qu'il n'y a pas eu d'erreurs
        assert len(errors) == 0


# ============================================================================
# TESTS DES MÉTHODES DE HAUT NIVEAU
# ============================================================================

class TestHighLevelMethods:
    """Tests des méthodes de haut niveau spécifiques au SA32."""

    def test_read_temperature(self, mock_driver_connected):
        """Test la lecture de température (méthode exemple)."""
        # Note: Cette méthode est un exemple et retourne None
        # car les adresses de registres ne sont pas configurées
        temp = mock_driver_connected.read_temperature(1, 'Te')
        # La méthode exemple retourne None avec un warning
        assert temp is None

    def test_read_power(self, mock_driver_connected):
        """Test la lecture de puissance (méthode exemple)."""
        power = mock_driver_connected.read_power()
        assert power is None

    def test_read_nusselt_number(self, mock_driver_connected):
        """Test la lecture du nombre de Nusselt (méthode exemple)."""
        nu = mock_driver_connected.read_nusselt_number()
        assert nu is None

    def test_read_reynolds_number(self, mock_driver_connected):
        """Test la lecture du nombre de Reynolds (méthode exemple)."""
        re = mock_driver_connected.read_reynolds_number()
        assert re is None

    def test_get_thermal_data(self, mock_driver_connected):
        """Test la récupération de données thermiques complètes."""
        data = mock_driver_connected.get_thermal_data()
        assert isinstance(data, dict)
        assert 'timestamp' in data
        assert 'power_w' in data
        assert 'nusselt' in data
        assert 'reynolds' in data


# ============================================================================
# TESTS DE MODE MOCK
# ============================================================================

class TestMockMode:
    """Tests spécifiques au mode mock."""

    def test_mock_mode_enabled(self):
        """Test que le mode mock est correctement activé."""
        driver = SA32Driver(mock_mode=True)
        assert driver.mock_mode is True

    def test_set_mock_register(self, mock_driver_connected):
        """Test la définition de valeurs mock."""
        mock_driver_connected.set_mock_register(5000, 99999)
        value = mock_driver_connected.read_holding_register(5000)
        assert value == 99999

    def test_set_mock_register_not_in_mock_mode(self):
        """Test que set_mock_register ne fonctionne que en mode mock."""
        driver = SA32Driver(mock_mode=False)
        driver.set_mock_register(1000, 100)  # Ne doit pas crasher
        # Mais ne fait rien car pas en mode mock

    def test_mock_random_values(self, mock_driver_connected):
        """Test que les registres non définis retournent des valeurs aléatoires."""
        value1 = mock_driver_connected.read_holding_register(9000)
        value2 = mock_driver_connected.read_holding_register(9001)

        assert value1 is not None
        assert value2 is not None
        assert 0 <= value1 <= 65535
        assert 0 <= value2 <= 65535

    def test_mock_persistence(self, mock_driver_connected):
        """Test que les valeurs mock persistent entre les lectures."""
        # Première lecture génère une valeur aléatoire
        value1 = mock_driver_connected.read_holding_register(8000)

        # Deuxième lecture doit retourner la même valeur
        value2 = mock_driver_connected.read_holding_register(8000)

        assert value1 == value2


# ============================================================================
# TESTS DE REPRÉSENTATION
# ============================================================================

class TestRepresentation:
    """Tests de la représentation de l'objet."""

    def test_repr_disconnected(self, mock_driver):
        """Test la représentation d'un driver déconnecté."""
        repr_str = repr(mock_driver)
        assert 'SA32Driver' in repr_str
        assert 'TCP' in repr_str
        assert 'déconnecté' in repr_str
        assert 'mock=True' in repr_str

    def test_repr_connected(self, mock_driver_connected):
        """Test la représentation d'un driver connecté."""
        repr_str = repr(mock_driver_connected)
        assert 'SA32Driver' in repr_str
        assert 'connecté' in repr_str


# ============================================================================
# TESTS D'INTÉGRATION
# ============================================================================

class TestIntegration:
    """Tests d'intégration simulant des scénarios réels."""

    def test_full_workflow_mock(self):
        """Test un workflow complet en mode mock."""
        # Création et connexion
        driver = SA32Driver(mock_mode=True, auto_reconnect=True)
        driver.connect()

        # Définir des valeurs de test
        driver.set_mock_register(1000, 100)
        driver.set_mock_register(1001, 200)

        # Lecture
        values = driver.read_holding_registers(1000, 2)
        assert values == [100, 200]

        # Écriture
        driver.write_register(2000, 300)

        # Vérification
        value = driver.read_holding_register(2000)
        assert value == 300

        # Déconnexion
        driver.disconnect()
        assert not driver.is_connected()

    def test_reconnection_scenario(self):
        """Test un scénario de reconnexion."""
        driver = SA32Driver(
            mock_mode=True,
            auto_reconnect=True,
            max_reconnect_attempts=3
        )

        # Connexion initiale
        driver.connect()
        assert driver.is_connected()

        # Simulation d'une déconnexion
        driver.disconnect()
        assert not driver.is_connected()

        # La reconnexion automatique devrait fonctionner
        # (en mode mock, connect() fonctionne toujours)
        driver.connect()
        assert driver.is_connected()

        driver.disconnect()

    def test_multiple_drivers(self):
        """Test l'utilisation de plusieurs drivers simultanément."""
        driver1 = SA32Driver(mock_mode=True, slave_id=1)
        driver2 = SA32Driver(mock_mode=True, slave_id=2)

        driver1.connect()
        driver2.connect()

        driver1.write_register(1000, 111)
        driver2.write_register(1000, 222)

        value1 = driver1.read_holding_register(1000)
        value2 = driver2.read_holding_register(1000)

        assert value1 == 111
        assert value2 == 222

        driver1.disconnect()
        driver2.disconnect()


# ============================================================================
# TESTS DE PERFORMANCE (optionnels)
# ============================================================================

@pytest.mark.slow
class TestPerformance:
    """Tests de performance (marqués comme lents)."""

    def test_read_performance(self, mock_driver_connected):
        """Test la performance de lecture."""
        start_time = time.time()
        iterations = 1000

        for i in range(iterations):
            mock_driver_connected.read_holding_register(1000)

        elapsed = time.time() - start_time
        rate = iterations / elapsed

        print(f"\nPerformance lecture: {rate:.0f} lectures/seconde")
        assert rate > 100  # Au moins 100 lectures par seconde

    def test_write_performance(self, mock_driver_connected):
        """Test la performance d'écriture."""
        start_time = time.time()
        iterations = 1000

        for i in range(iterations):
            mock_driver_connected.write_register(2000, i)

        elapsed = time.time() - start_time
        rate = iterations / elapsed

        print(f"\nPerformance écriture: {rate:.0f} écritures/seconde")
        assert rate > 100  # Au moins 100 écritures par seconde


# ============================================================================
# EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Exécuter les tests avec pytest
    pytest.main([__file__, '-v', '--tb=short'])
