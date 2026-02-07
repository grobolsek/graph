from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")


class TaskWrapper:
    def __init__(self, graph: "Graph", func: Callable, name: str | None = None):
        self.graph = graph
        self.func = func
        self.name = name or func.__name__
        self._condition_func = lambda: True  # Default: always run

    def condition(self, predicate: Callable[[], bool]):
        """Sets a predicate that must return True for the task to execute."""
        self._condition_func = predicate
        return self  # Return self to allow further chaining

    def __call__(self, *args, **kwargs):
        """When the decorated function is called, create the node."""
        new_node = Node(self.func, args, kwargs, self.name)
        new_node.condition = self._condition_func  # Attach condition to node
        self.graph.vertices.add(new_node)
        return Future(new_node)


class Future[T]:
    def __init__(self, node: "Node") -> None:
        self.node = node


class Component(ABC):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name

    @classmethod
    @abstractmethod
    def execute(cls, results: dict["Node", Any]):
        pass

    @classmethod
    def _resolve_futures(cls, data: Any, results: dict["Node", Any]) -> Any:
        if isinstance(data, Future):
            return results[data.node]
        if isinstance(data, list):
            return [cls._resolve_futures(i, results) for i in data]
        if isinstance(data, tuple):
            return tuple(cls._resolve_futures(i, results) for i in data)
        if isinstance(data, dict):
            return {k: cls._resolve_futures(v, results) for k, v in data.items()}
        return data


class Node(Component):
    def __init__(self, name: str, func: Callable, args: tuple[Any, ...], kwargs: dict[str, Any], condition: Callable[..., bool]) -> None:
        super().__init__(name=name)
        self.func = func
        self.args = list(args)
        self.kwargs = kwargs
        self.condition = condition

    def execute(self, results: dict["Node", Any]) -> Any:
        real_args = self._resolve_futures(self.args, results)
        real_kwargs = self._resolve_futures(self.kwargs, results)

        return self.func(*real_args, **real_kwargs)


class Chain(Component):
    def __init__(self, name: str, nodes: list[Component]):
        super().__init__(name)
        self.nodes = nodes

    def execute(self, results: dict["Node", Any]):
        return self._run(results=results, nodes=self.nodes)

    def _run(self, results: dict["Node", Any], nodes: list[Component]):
        if len(nodes) == 1:
            return nodes[0].execute(results)

        return self._run(input_=nodes[0].execute, nodes=nodes[1:])


class Graph:
    def __init__(self):
        self.vertices: set[Component] = set()
        self.edges: dict[Component, set[Component]] = {}

    def task(self, name: str | None = None):
        def decorator(func: Callable[P, T]):
            # Return the wrapper object instead of a simple function
            return TaskWrapper(self, func, name)

        return decorator
