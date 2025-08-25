import pytest

from src.core.di.container import DIContainer
from src.core.di.interfaces import DataLoaderInterface


class MockDataLoader(DataLoaderInterface):
    """Mock implementation of DataLoaderInterface for testing."""

    def load_processed_data(self):
        return [{"id": 1, "content": "test"}]

    def load_prompt_template(self):
        return "Test prompt template"


class AnotherMockDataLoader(DataLoaderInterface):
    """Another mock implementation of DataLoaderInterface for testing."""

    def load_processed_data(self):
        return [{"id": 2, "content": "another test"}]

    def load_prompt_template(self):
        return "Another test prompt template"


def test_register_and_resolve_singleton():
    """Test registering and resolving a singleton service."""
    container = DIContainer()

    # Register a singleton service
    container.register_singleton(DataLoaderInterface, MockDataLoader)

    # Resolve the service twice
    instance1 = container.resolve(DataLoaderInterface)
    instance2 = container.resolve(DataLoaderInterface)

    # Verify that both instances are the same (singleton behavior)
    assert isinstance(instance1, MockDataLoader)
    assert isinstance(instance2, MockDataLoader)
    assert instance1 is instance2


def test_register_and_resolve_transient():
    """Test registering and resolving a transient service."""
    container = DIContainer()

    # Register a transient service
    container.register_transient(DataLoaderInterface, MockDataLoader)

    # Resolve the service twice
    instance1 = container.resolve(DataLoaderInterface)
    instance2 = container.resolve(DataLoaderInterface)

    # Verify that both instances are different (transient behavior)
    assert isinstance(instance1, MockDataLoader)
    assert isinstance(instance2, MockDataLoader)
    assert instance1 is not instance2


def test_register_singleton_instance():
    """Test registering a singleton instance."""
    container = DIContainer()

    # Create an instance and register it as a singleton
    mock_instance = MockDataLoader()
    container.register_singleton_instance(DataLoaderInterface, mock_instance)

    # Resolve the service
    resolved_instance = container.resolve(DataLoaderInterface)

    # Verify that the resolved instance is the same as the registered instance
    assert resolved_instance is mock_instance


def test_register_transient_factory():
    """Test registering a transient factory."""
    container = DIContainer()

    # Register a factory function
    factory_called_count = 0

    def factory():
        nonlocal factory_called_count
        factory_called_count += 1
        return MockDataLoader()

    container.register_transient_factory(DataLoaderInterface, factory)

    # Resolve the service twice
    instance1 = container.resolve(DataLoaderInterface)
    instance2 = container.resolve(DataLoaderInterface)

    # Verify that the factory was called twice (transient behavior)
    assert factory_called_count == 2
    assert isinstance(instance1, MockDataLoader)
    assert isinstance(instance2, MockDataLoader)
    assert instance1 is not instance2


def test_resolve_unregistered_service():
    """Test that resolving an unregistered service raises an error."""
    container = DIContainer()

    # Try to resolve an unregistered service
    with pytest.raises(ValueError, match="No service registered for"):
        container.resolve(DataLoaderInterface)


def test_clear_container():
    """Test clearing the container."""
    container = DIContainer()

    # Register a service
    container.register_singleton(DataLoaderInterface, MockDataLoader)

    # Verify the service can be resolved
    instance = container.resolve(DataLoaderInterface)
    assert isinstance(instance, MockDataLoader)

    # Clear the container
    container.clear()

    # Verify that resolving the service now raises an error
    with pytest.raises(ValueError, match="No service registered for"):
        container.resolve(DataLoaderInterface)


def test_multiple_service_registrations():
    """Test registering multiple different services."""
    container = DIContainer()

    # Register multiple services
    container.register_singleton(DataLoaderInterface, MockDataLoader)

    # Resolve the service
    data_loader = container.resolve(DataLoaderInterface)

    # Verify the correct service was resolved
    assert isinstance(data_loader, MockDataLoader)
    assert data_loader.load_processed_data() == [{"id": 1, "content": "test"}]


if __name__ == "__main__":
    pytest.main([__file__])
