from abc import ABC, abstractmethod

from database.models import Deployment


class BaseDeploymentProvider(ABC):
    @abstractmethod
    def dispatch(self, deployment: Deployment) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_logs(self, deployment: Deployment, tail: int = 100) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def teardown(self, deployment: Deployment) -> None:
        raise NotImplementedError
