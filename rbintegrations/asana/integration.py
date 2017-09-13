"""Integration for associating review requests with Asana tasks."""

from __future__ import unicode_literals

from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from reviewboard.extensions.hooks import ReviewRequestFieldsHook
from reviewboard.integrations import Integration

from rbintegrations.asana.fields import AsanaField
from rbintegrations.asana.forms import AsanaIntegrationConfigForm


class AsanaIntegration(Integration):
    """Integrates Review Board with Asana."""

    name = 'Asana'
    description = _('Associate Asana tasks with your review requests.')
    config_form_cls = AsanaIntegrationConfigForm

    def initialize(self):
        """Initialize the integration hooks."""
        ReviewRequestFieldsHook(self, 'main', [AsanaField])

    @cached_property
    def icon_static_urls(self):
        """The icons used for the integration."""
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/asana/icon.png'),
            '2x': extension.get_static_url('images/asana/icon@2x.png'),
        }
