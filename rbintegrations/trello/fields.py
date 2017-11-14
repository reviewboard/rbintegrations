"""Review Request field definitions for Trello integration."""

from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from reviewboard.integrations.base import get_integration_manager
from reviewboard.reviews.fields import BaseEditableField


class TrelloField(BaseEditableField):
    """A review request field for selecting Trello cards."""

    field_id = 'rbintegrations_trello'
    label = _('Trello Cards')

    #: The class name for the JavaScript view representing this field.
    js_view_class = 'RB.ReviewRequestFields.TrelloFieldView'

    #: The HTML tag to be used when rendering the field.
    tag_name = 'div'

    @property
    def should_render(self):
        """Whether the field should render or not.

        The Trello Cards field renders when there are any matching
        integration configs for the current review request.
        """
        from rbintegrations.trello.integration import TrelloIntegration

        integration_manager = get_integration_manager()
        integration = integration_manager.get_integration(
            TrelloIntegration.integration_id)
        review_request = self.review_request_details.get_review_request()

        for config in integration.get_configs(review_request.local_site):
            if config.match_conditions(form_cls=integration.config_form_cls,
                                       review_request=review_request):
                return True

        return False

    def render_value(self, value):
        """Render the value in the field.

        This always returns the empty string, because the field value is
        rendered in JavaScript.

        Args:
            value (object):
                The value to render.

        Returns:
            unicode:
            The rendered value.
        """
        return ''

    def get_data_attributes(self):
        """Return any data attributes to include in the element.

        Returns:
            dict:
            The data attributes to include in the element.
        """
        attrs = super(TrelloField, self).get_data_attributes()

        if self.value is not None:
            attrs['raw-value'] = self.value

        return attrs
