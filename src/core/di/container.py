"""
Simple dependency injection container.

This module provides a basic dependency injection container that can register
and resolve services. It supports both singleton and transient services.
"""

from typing import Any, Callable, Dict, Type, TypeVar

T = TypeVar("T")
U = TypeVar("U")


class DIContainer:
    """
    A simple dependency injection container.
    """

    def __init__(self):
        """Initialize the DI container."""
        self._services: Dict[Type, Callable] = {}
        self._singletons: Dict[Type, Any] = {}
        self._instances: Dict[Type, Any] = {}

    def register_singleton(self, interface: Type[T], implementation: Type[U]) -> None:
        """Register a singleton service."""
        self._services[interface] = implementation
        self._singletons[interface] = None

    def register_singleton_instance(self, interface: Type[T], instance: T) -> None:
        """
        Register a singleton service instance.

        Args:
            interface: The interface type
            instance: The instance to register
        """
        self._services[interface] = lambda: instance
        self._singletons[interface] = instance

    def register_transient(self, interface: Type[T], implementation: Type[T]) -> None:
        """
        Register a transient service.

        Args:
            interface: The interface type
            implementation: The implementation type
        """
        self._services[interface] = implementation

    def register_transient_factory(
        self, interface: Type[T], factory: Callable[[], T]
    ) -> None:
        """
        Register a transient service factory.

        Args:
            interface: The interface type
            factory: The factory function
        """
        self._services[interface] = factory

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a service instance.

        Args:
            interface: The interface type to resolve

        Returns:
            An instance of the requested service
        """
        if interface not in self._services:
            raise ValueError(f"No service registered for {interface}")

        # Check if it's a singleton that's already been created
        if interface in self._singletons:
            if self._singletons[interface] is None:
                # Create the singleton instance
                implementation = self._services[interface]
                if isinstance(implementation, type):
                    self._singletons[interface] = implementation()
                else:
                    self._singletons[interface] = implementation()
            return self._singletons[interface]

        # For transient services, create a new instance
        implementation = self._services[interface]
        if isinstance(implementation, type):
            return implementation()
        else:
            return implementation()

    def clear(self):
        """Clear all registered services and instances."""
        self._services.clear()
        self._singletons.clear()
        self._instances.clear()


# Global container instance
container = DIContainer()
