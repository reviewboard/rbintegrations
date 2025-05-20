"""Base test cases for rbintegrations."""

from __future__ import annotations

from typing import Generic, Optional, Type, TypeVar

from kgb import SpyAgency
from reviewboard.extensions.testing import ExtensionTestCase
from reviewboard.integrations.base import (Integration,
                                           get_integration_manager)

from rbintegrations.extension import RBIntegrationsExtension


_IntegrationT = TypeVar('_IntegrationT', bound=Integration)


class RBIntegrationsExtensionTestCase(SpyAgency, ExtensionTestCase):
    """Base class for unit tests for rbintegrations."""

    extension_class = RBIntegrationsExtension


class IntegrationTestCase(RBIntegrationsExtensionTestCase,
                          Generic[_IntegrationT]):
    """Base class for unit tests for individual integrations."""

    #: The integration class to test.
    integration_cls: Optional[Type[_IntegrationT]] = None

    ######################
    # Instance variables #
    ######################

    integration: _IntegrationT

    def setUp(self):
        super(IntegrationTestCase, self).setUp()

        integration_mgr = get_integration_manager()

        integration_cls = self.integration_cls
        assert integration_cls is not None, (
            '%s.integration_cls must be set'
            % type(self).__name__)

        self.integration = integration_mgr.get_integration(
            integration_cls.integration_id)

        integration_mgr.clear_all_configs_cache()
