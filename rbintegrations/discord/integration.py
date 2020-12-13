"""Integration for Discord"""

from __future__ import unicode_literals

import json
import logging

from django.utils.functional import cached_property
from django.utils.six.moves.urllib.request import Request, urlopen
from django.utils.translation import ugettext_lazy as _

from rbintegrations.basechat.integration import BaseChatIntegration
from rbintegrations.discord.forms import DiscordIntegrationConfigForm
from rbintegrations.slack.integration import format_link, build_slack_message


logger = logging.getLogger(__name__)


class DiscordIntegration(BaseChatIntegration):
    """Integrates Review Board with Discord.

    This will handle updating Discord channels when review requests are
    posted, changed, or closed, and when there's new activity on the review
    request.
    """

    name = 'Discord'
    description = _(
        'Notifies channels in Discord when review requests are created, '
        'updated, and reviewed.'
    )

    default_settings = {
        'channel': '',
        'notify_username': 'Review Board',
        'webhook_url': '',
    }

    config_form_cls = DiscordIntegrationConfigForm

    DEFAULT_COLOR = '#efcc96'
    ASSETS_BASE_URL = (
        'https://static.reviewboard.org/integration-assets/discord'
    )
    ASSETS_TIMESTAMP = '?20201121-1015'
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
        """Send a webhook notification to Discord.

        This will post the given message to any Discord channels configured to
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
                A Slack color string or RGB hex value for the message.

            thumb_url (unicode, optional):
                URL of an image to show on the side of the message.

            image_url (unicode, optional):
                URL of an image to show in the message.
        """
        common_payload = build_slack_message(integration=self,
                                             title=title,
                                             title_link=title_link,
                                             fallback_text=fallback_text,
                                             fields=fields,
                                             pre_text=None,
                                             body=body,
                                             color=color,
                                             thumb_url=thumb_url,
                                             image_url=image_url)
        common_payload['text'] = pre_text

        # Send a notification to any configured channels.
        for config in self.get_configs(local_site):
            if not config.match_conditions(form_cls=self.config_form_cls,
                                           review_request=review_request):
                continue

            payload = dict({
                'username': config.get('notify_username'),
            }, **common_payload)

            # Tell Discord to use Slack formatted message.
            webhook_url = '%s/slack' % config.get('webhook_url')

            logger.debug('Sending notification for event "%s", '
                         'review_request ID %d, '
                         'webhook URL %s',
                         event_name, review_request.pk, webhook_url)

            try:
                data = json.dumps(payload).encode('utf-8')

                # Must include 'User-Agent' to avoid being blocked by Discord.
                headers = {
                    'Content-Length': len(data),
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)',
                }
                urlopen(Request(webhook_url, data, headers))
            except Exception as e:
                logger.exception('Failed to send notification: %s', e)

    def format_link(self, path, text):
        """Format the given URL and text to be shown in a Slack message.

        This uses SlackIntegration's format_link function and Discord will
        handle the translation of Slack URL to Discord URL

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
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for Discord.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/discord/icon.png'),
            '2x': extension.get_static_url('images/discord/icon@2x.png'),
        }
