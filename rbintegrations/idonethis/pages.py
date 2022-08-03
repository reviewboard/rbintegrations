"""Pages for I Done This integration."""

from django.utils.translation import gettext_lazy as _
from reviewboard.accounts.pages import AccountPage

from rbintegrations.idonethis.forms import IDoneThisIntegrationAccountPageForm


class IDoneThisIntegrationAccountPage(AccountPage):
    """User account page for I Done This."""

    page_id = 'idonethis_account_page'
    page_title = _('I Done This')
    form_classes = [IDoneThisIntegrationAccountPageForm]
