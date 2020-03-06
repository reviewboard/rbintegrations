"""Forms for I Done This integration."""

from __future__ import unicode_literals

import logging

from django import forms
from django.utils.six.moves.urllib.error import HTTPError, URLError
from django.utils.six.moves.urllib.request import urlopen
from django.utils.translation import ugettext, ugettext_lazy as _
from djblets.forms.fields import ConditionsField
from reviewboard.accounts.forms.pages import AccountPageForm
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.reviews.conditions import ReviewRequestConditionChoices
from reviewboard.scmtools.crypto_utils import encrypt_password

from rbintegrations.idonethis.utils import (create_idonethis_request,
                                            delete_cached_user_team_ids,
                                            get_user_api_token)


class IDoneThisIntegrationConfigForm(IntegrationConfigForm):
    """Admin configuration form for I Done This.

    This allows an administrator to set up a configuration for posting 'done'
    entries to a given I Done This team based on the specified conditions.
    """

    conditions = ConditionsField(ReviewRequestConditionChoices,
                                 label=_('Conditions'))

    team_id = forms.CharField(
        label=_('Team ID'),
        required=True,
        help_text=_('The identifier of the team to receive posts. This can '
                    'be found at the end of the team URL, e.g. '
                    '<code>https://beta.idonethis.com/t/'
                    '<strong>123456abcdef</strong></code>'),
        widget=forms.TextInput(attrs={
            'size': 15,
        }))

    def clean_team_id(self):
        """Clean and validate the 'team_id' field.

        Returns:
            unicode:
            Team ID with leading and trailing whitespace removed.

        Raises:
            django.core.exceptions.ValidationError:
                Raised if the team ID contains any slashes.
        """
        team_id = self.cleaned_data['team_id'].strip()

        if '/' in team_id:
            raise forms.ValidationError(
                ugettext('Team ID cannot contain slashes.'))

        return team_id

    class Meta:
        fieldsets = (
            (_('What to Post'), {
                'description': _(
                    'You can choose which review request activity would be '
                    'posted by selecting the conditions to match.'
                ),
                'fields': ('conditions',),
            }),
            (_('Where to Post'), {
                'description': _(
                    'Posts are made to the specified I Done This team on '
                    'behalf of individual users who belong to that team. '
                    'A separate configuration is required for each team, '
                    'and multiple configurations may use the same team to '
                    'specify alternative sets of conditions.\n'
                    'To enable posting, each user has to provide their '
                    'personal I Done This API Token on their Review Board '
                    'account page.'
                ),
                'fields': ('team_id',),
                'classes': ('wide',)
            }),
        )


class IDoneThisIntegrationAccountPageForm(AccountPageForm):
    """User account page form for I Done This.

    This allows a user to specify their I Done This API Token and choose
    which actions result in posting of 'done' entries to I Done This.
    """

    form_id = 'idonethis_account_page_form'
    form_title = _('I Done This')
    template_name = 'rbintegrations/idonethis/account_page_form.html'

    idonethis_api_token = forms.CharField(
        label=_('API Token'),
        required=False,
        widget=forms.TextInput(attrs={
            'size': 45,
        }))

    def clean_idonethis_api_token(self):
        """Clean and validate the 'idonethis_api_token' field.

        This performs a test against the I Done This authentication test
        endpoint to ensure that the provided API token is valid. We only care
        if the request is successful, so we ignore the returned user data.

        Returns:
            unicode:
            Validated API token with leading and trailing whitespace removed,
            or an empty string if the API token is empty.

        Raises:
            django.core.exceptions.ValidationError:
                Raised if the API token validation fails.
        """
        api_token = self.cleaned_data['idonethis_api_token'].strip()

        if not api_token:
            return ''

        request = create_idonethis_request('noop', api_token)
        logging.debug('IDoneThis: Validating API token for user "%s", '
                      'request "%s %s"',
                      self.user.username,
                      request.get_method(),
                      request.get_full_url())

        try:
            urlopen(request)
        except (HTTPError, URLError) as e:
            if isinstance(e, HTTPError):
                error_info = '%s, error data: %s' % (e, e.read())
            else:
                error_info = e.reason

            logging.error('IDoneThis: Failed to validate API token for user '
                          '"%s", request "%s %s": %s',
                          self.user.username,
                          request.get_method(),
                          request.get_full_url(),
                          error_info)

            raise forms.ValidationError(
                ugettext('Error validating the API Token. Make sure the token '
                         'matches your I Done This Account Settings.'))

        return api_token

    def load(self):
        """Load the account page form."""
        self.set_initial({
            'idonethis_api_token': get_user_api_token(self.user),
        })

    def save(self):
        """Save the account page form.

        Stores an encrypted version of the API token.
        """
        api_token = self.cleaned_data['idonethis_api_token']
        profile = self.user.get_profile()
        settings = profile.settings.setdefault('idonethis', {})

        if api_token:
            logging.debug('IDoneThis: Saving API token for user "%s"',
                          self.user.username)
            settings['api_token'] = encrypt_password(api_token)
        elif 'api_token' in settings:
            logging.debug('IDoneThis: Deleting API token for user "%s"',
                          self.user.username)
            del settings['api_token']

        profile.save()

        delete_cached_user_team_ids(self.user)
