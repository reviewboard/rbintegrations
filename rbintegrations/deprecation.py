"""Internal support for handling deprecations.

The version-specific objects in this module are not considered stable between
releases, and may be removed at any point. The base objects are considered
stable.

Version Added:
    4.0
"""

from housekeeping import BasePendingRemovalWarning, BaseRemovedInWarning


class PendingRemovalInRBIntegrationsWarning(BasePendingRemovalWarning):
    project = 'Review Board Integrations'


class BaseRemovedInRBIntegrationsWarning(BaseRemovedInWarning):
    project = 'Review Board Integrations'


class RemovedInRBIntegrations50Warning(BaseRemovedInRBIntegrationsWarning):
    version = '5.0'
