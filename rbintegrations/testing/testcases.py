"""Base test cases for rbintegrations."""

from __future__ import unicode_literals

from kgb import SpyAgency
from reviewboard.extensions.testing import ExtensionTestCase
from reviewboard.integrations.base import get_integration_manager

from rbintegrations.extension import RBIntegrationsExtension


class RBIntegrationsExtensionTestCase(SpyAgency, ExtensionTestCase):
    """Base class for unit tests for rbintegrations."""

    extension_class = RBIntegrationsExtension


class IntegrationTestCase(RBIntegrationsExtensionTestCase):
    """Base class for unit tests for individual integrations."""

    #: The integration class to test.
    integration_cls = None

    def setUp(self):
        super(IntegrationTestCase, self).setUp()

        integration_mgr = get_integration_manager()

        self.integration = integration_mgr.get_integration(
            self.integration_cls.integration_id)

        integration_mgr.clear_all_configs_cache()
