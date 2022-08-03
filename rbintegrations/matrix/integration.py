"""Integration for Matrix chat."""

import json
import logging
import re
from urllib.request import Request, urlopen

from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django.utils.html import format_html
from reviewboard.admin.server import build_server_url

from rbintegrations.basechat.integration import BaseChatIntegration
from rbintegrations.matrix.forms import MatrixIntegrationConfigForm


logger = logging.getLogger(__name__)


class MatrixIntegration(BaseChatIntegration):
    """Integrates Review Board with Matrix.

    This will handle updating Matrix rooms when review requests are posted,
    changed, or closed, and when there's new activity on the review request.
    """

    name = 'Matrix'
    description = _(
        'Notifies rooms in Matrix when review requests are created, '
        'updated, and reviewed.'
    )

    default_settings = {
        'access_token': '',
        'notify_username': 'Review Board',
        'room': '',
    }

    config_form_cls = MatrixIntegrationConfigForm

    DEFAULT_COLOR = '#efcc96'
    ASSETS_BASE_URL = \
        'https://static.reviewboard.org/integration-assets/matrix'
    ASSETS_TIMESTAMP = '?20201203-2346'
    LOGO_URL = '%s/reviewboard.png?%s' % (ASSETS_BASE_URL, ASSETS_TIMESTAMP)
    VALID_IMAGE_URL_EXTS = ('.png', '.bmp', '.gif', '.jpg', '.jpeg')

    TROPHY_URLS = {
        'fish': '%s/fish-trophy.png?%s' % (ASSETS_BASE_URL, ASSETS_TIMESTAMP),
        'milestone': '%s/milestone-trophy.png?%s' % (ASSETS_BASE_URL,
                                                     ASSETS_TIMESTAMP),
    }

    def initialize(self):
        """Initialize the integration."""
        super(MatrixIntegration, self).initialize()

        self._SHORTCODE_PATTERN = re.compile(r':[a-z_]+:')

    def notify(self, title, title_link, fallback_text, local_site,
               review_request, event_name=None, fields={}, pre_text=None,
               body=None, color=None, thumb_url=None, image_url=None):
        """Send a notification to Matrix.

        This will post the given message to any Matrix rooms configured to
        receive it.

        Args:
            title (unicode):
                The title for the message.

            title_link (unicode):
                The link for the title of the message.

            fallback_text (unicode):
                The non-rich fallback text to display in the chat, for use in
                IRC and other services.

            local_site (reviewboard.site.models.LocalSite):
                The Local Site for the review request or review emitting
                the message. Only integration configurations matching this
                Local Site will be processed.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request the notification is bound to.

            event_name (unicode, optional):
                The name of the event triggering this notification.

            fields (dict, optional):
                The fields comprising the rich message to display in chat.

            pre_text (unicode, optional):
                Text to display before the rest of the message.

            body (unicode, optional):
                The body of the message.

            color (unicode, optional):
                A Matrix color string or RGB hex value for the message.

            thumb_url (unicode, optional):
                URL of an image to show on the side of the message.

            image_url (unicode, optional):
                URL of an image to show in the message.
        """
        message = []
        message.append(
            format_html('<strong>{}</strong><p>{}</p>',
                        fallback_text, title))

        if not color:
            color = self.DEFAULT_COLOR

        if fields:
            for field in fields:
                text = self.replace_shortcode(field['value'])
                message.append(format_html(
                    '<strong><font color="{}">{}</font></strong><p>{}</p>',
                    color, field['title'], text))

        if body:
            message.append(format_html('<blockquote>{}</blockquote>', body))

        payload = {
            'body': '',
            'msgtype': 'm.text',
            'formatted_body': ''.join(message),
            'format': 'org.matrix.custom.html',
        }

        # Send a notification to any configured rooms.
        for config in self.get_configs(local_site):
            if not config.match_conditions(form_cls=self.config_form_cls,
                                           review_request=review_request):
                continue

            room_id = config.get('room_id')
            access_token = config.get('access_token')
            server = config.get('server')

            logger.debug('Sending notification for event "%s", '
                         'review_request ID %d to room "%s", '
                         'access token %s',
                         event_name, review_request.pk, room_id, access_token)

            try:
                data = json.dumps(payload).encode('utf-8')
                url = (
                    '%s/_matrix/client/r0/rooms/%s/send/'
                    'm.room.message?access_token=%s'
                    % (server, room_id, access_token))
                headers = {
                    'Content-Length': len(data),
                    'Content-Type': 'application/json',
                }

                urlopen(Request(url, data, headers))
            except Exception as e:
                logger.exception('Failed to send notification: %s', e)

    def replace_shortcode(self, s):
        """Replaces supported shortcodes in a string with their unicodes.

        Args:
            s (unicode):
                The text that may contain shortcodes.

        Returns:
            unicode:
            The text with all supported shortcodes replaced by their
            equivalent Unicode characters.
        """
        emoji_unicode = {
            ':warning:': '\U000026A0',
            ':white_check_mark:': '\U00002705',
        }
        return self._SHORTCODE_PATTERN.sub(
            lambda x: emoji_unicode[x.group()], s)

    def format_link(self, path, text):
        """Format the given URL and text to be shown in a Matrix message.

        This will combine together the parts of the URL (method, domain, path)
        and format it using Matrix's URL syntax.

        Args:
            path (unicode):
                The path on the Review Board server.

            text (unicode):
                The text for the link.

        Returns:
            unicode:
            The link for use in Matrix.
        """
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')

        return '%s | %s' % (build_server_url(path), text)

    @cached_property
    def icon_static_urls(self):
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for Matrix.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/matrix/icon.png'),
            '2x': extension.get_static_url('images/matrix/icon@2x.png'),
        }
