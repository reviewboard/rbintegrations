"""The form for configuring the Asana integration."""

from __future__ import unicode_literals

from django import forms
from django.utils.translation import ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices


class AsanaIntegrationConfigForm(IntegrationConfigForm):
    """Form for configuring Asana."""

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    asana_access_token = forms.CharField(
        label=_('Asana Personal Access Token'),
        help_text=_('A personal access token for authenticating to the Asana '
                    'API. To create this, open Asana and select "My Profile '
                    'Settings" in the upper right. From the resulting dialog, '
                    'choose "Apps", then "Manage Developer Apps". Finally, '
                    'select "Create New Personal Access Token".'),
        min_length=34,
        max_length=34,
        widget=forms.widgets.TextInput(attrs={
            'size': 40,
        }))

    asana_workspace = forms.ChoiceField(label=_('Asana Workspace'),
                                        choices=[])

    asana_workspace_name = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        """Initialize the form.

        Args:
            *args (tuple):
                Positional arguments for the form.

            **kwargs (dict):
                Keyword arguments for the form.
        """
        super(AsanaIntegrationConfigForm, self).__init__(*args, **kwargs)

        from rbintegrations.extension import RBIntegrationsExtension
        extension = RBIntegrationsExtension.instance

        asana_integration_config_bundle = \
            extension.get_bundle_id('asana-integration-config')
        self.css_bundle_names = [asana_integration_config_bundle]
        self.js_bundle_names = [asana_integration_config_bundle]

        if (self.data and
            'asana_workspace' in self.data and
            'asana_workspace_name' in self.data):
            # Saving case: If the provided form data contains the workspace
            # ID and name, set those as valid choices so that the
            # asana_workspace field will validate properly.

            self.fields['asana_workspace'].choices = [
                (self.data['asana_workspace'],
                 self.data['asana_workspace_name']),
            ]
        elif (self.instance and
              'asana_workspace' in self.instance.settings and
              'asana_workspace_name' in self.instance.settings):
            # Loading case: If the saved settings contain the workspace ID and
            # name, set those as valid choices for the asana_workspace field so
            # that it shows the initial value correctly.

            self.fields['asana_workspace'].choices = [
                (self.instance.settings['asana_workspace'],
                 self.instance.settings['asana_workspace_name']),
            ]
