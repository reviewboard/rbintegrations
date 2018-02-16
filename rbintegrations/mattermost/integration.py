"""Integration for Mattermost"""
from __future__ import unicode_literals

from django.utils.functional import cached_property

from rbintegrations.basechat.forms import BaseChatIntegrationConfigForm
from rbintegrations.basechat.integration import BaseChatIntegration
from rbintegrations.slack.integration import format_link, notify


class MattermostIntegration(BaseChatIntegration):
    """Integrates Review Board with Mattermost.

    This will handle updating Mattermost channels when review requests are
    posted, changed, or closed, and when there's new activity on the review
    request.
    """

    name = 'Mattermost'
    description = (
        'Notifies channels in Mattermost when review requests are created, '
        'updated, and reviewed.'
    )

    default_settings = {
        'webhook_url': '',
        'channel': '',
        'notify_username': 'Review Board',
    }

    config_form_cls = BaseChatIntegrationConfigForm

    DEFAULT_COLOR = '#efcc96'
    ASSETS_BASE_URL = 'https://static.reviewboard.org/integration-assets' \
                      '/mattermost'
    ASSETS_TIMESTAMP = '?20160830-2346'
    LOGO_URL = '%s/reviewboard.png?%s' % (ASSETS_BASE_URL, ASSETS_TIMESTAMP)
    VALID_IMAGE_URL_EXTS = ('.png', '.bmp', '.gif', '.jpg', '.jpeg')

    TROPHY_URLS = {
        'fish': '%s/fish-trophy.png?%s' % (ASSETS_BASE_URL, ASSETS_TIMESTAMP),
        'milestone': '%s/milestone-trophy.png?%s' % (ASSETS_BASE_URL,
                                                     ASSETS_TIMESTAMP),
    }

    def notify(self, title, title_link, fallback_text, local_site,
               review_request, event_name=None, fields={}, pre_text=None,
               body=None, color=None, thumb_url=None, image_url=None):
        """Send a webhook notification to Mattermost.

        This will post the given message to any Mattermost channels
        configured to receive it.

        Args:
            title (unicode):
                The title for the message.

            title_link (unicode):
                The link for the title of the message.

            fallback_text (unicode):
                The non-rich fallback text to display in the chat, for use in
                IRC and other services.

            fields (dict):
                The fields comprising the rich message to display in chat.

            local_site (reviewboard.site.models.LocalSite):
                The Local Site for the review request or review emitting
                the message. Only integration configurations matching this
                Local Site will be processed.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request the notification is bound to.

            event_name (unicode):
                The name of the event triggering this notification.

            pre_text (unicode, optional):
                Text to display before the rest of the message.

            body (unicode, optional):
                The body of the message.

            color (unicode, optional):
                A Mattermost color string or RGB hex value for the message.

            thumb_url (unicode, optional):
                URL of an image to show on the side of the message.

            image_url (unicode, optional):
                URL of an image to show in the message.
        """
        notify(self, title, title_link, fallback_text, local_site,
               review_request, event_name, fields, pre_text, body, color,
               thumb_url, image_url)

    def format_link(self, path, text):
        """Format the given URL and text to be shown in a Mattermost message.

        This will combine together the parts of the URL (method, domain, path)
        and format it using Mattermost's URL syntax.

        Args:
            path (unicode):
                The path on the Review Board server.

            text (unicode):
                The text for the link.

        Returns:
            unicode:
            The link for use in Slack.
        """
        return format_link(path, text)

    @cached_property
    def icon_static_urls(self):
        """The icons used for the integration.

        Returns:
            dict:
            The icons for Mattermost.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/mattermost/icon.png'),
            '2x': extension.get_static_url('images/mattermost/icon@2x.png'),
        }
