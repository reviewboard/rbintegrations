"""Integration for Discord"""

from __future__ import annotations

import json
import logging
from typing import MutableMapping, Optional, Sequence, TYPE_CHECKING
from urllib.request import Request, urlopen
from uuid import uuid4

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from rbintegrations.basechat.integration import BaseChatIntegration
from rbintegrations.discord.forms import DiscordIntegrationConfigForm
from rbintegrations.slack.integration import format_link, build_slack_message

if TYPE_CHECKING:
    from djblets.util.typing import JSONDict
    from rbintegrations.basechat.integration import FieldsDict
    from reviewboard.reviews.models import ReviewRequest
    from reviewboard.site.models import LocalSite


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

    assets_base_url = (
        'https://static.reviewboard.org/integration-assets/discord'
    )

    def notify(
        self,
        *,
        title: str,
        title_link: str,
        fallback_text: str,
        local_site: Optional[LocalSite],
        review_request: ReviewRequest,
        event_name: Optional[str] = None,
        fields: Sequence[FieldsDict] = [],
        pre_text: Optional[str] = None,
        body: Optional[str] = None,
        color: Optional[str] = None,
        thumb_url: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> None:
        """Send a WebHook notification to Discord.

        This will post the given message to any Discord channels configured to
        receive it.

        Args:
            title (str):
                The title for the message.

            title_link (str):
                The link for the title of the message.

            fallback_text (str):
                The non-rich fallback text to display in the chat, for use in
                IRC and other services.

            local_site (reviewboard.site.models.LocalSite):
                The Local Site for the review request or review emitting
                the message. Only integration configurations matching this
                Local Site will be processed.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request the notification is bound to.

            event_name (str, optional):
                The name of the event triggering this notification.

            fields (list of rbintegrations.basechat.integration.FieldsDict,
                    optional):
                The fields comprising the rich message to display in chat.

            pre_text (str, optional):
                Text to display before the rest of the message.

            body (str, optional):
                The body of the message.

            color (str, optional):
                A color string or RGB hex value for the message.

            thumb_url (str, optional):
                URL of an image to show on the side of the message.

            image_url (str, optional):
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

            payload: JSONDict = dict({
                'username': config.get('notify_username'),
            }, **common_payload)

            # Tell Discord to use Slack formatted message.
            webhook_url = '%s/slack' % config.get('webhook_url')

            logger.debug('Sending notification for event "%s", '
                         'review_request ID %d, '
                         'WebHook URL %s',
                         event_name, review_request.pk, webhook_url)

            try:
                data = json.dumps(payload).encode('utf-8')

                # Must include 'User-Agent' to avoid being blocked by Discord.
                headers: MutableMapping[str, str] = {
                    'Content-Length': str(len(data)),
                    'Content-Type': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)',
                }
                urlopen(Request(webhook_url, data, headers))
            except Exception as e:
                error_id = str(uuid4())
                fp = getattr(e, 'fp', None)

                logger.exception('[%s] Failed to send notification: %s',
                                 error_id, e)
                logger.debug('[%s] Discord message payload = %r',
                             error_id, payload)

                if fp is not None:
                    logger.debug('[%s] Discord error response = %r',
                                 error_id, fp.read())

    def format_link(
        self,
        *,
        path: str,
        text: str,
    ) -> str:
        """Format the given URL and text to be shown in a Slack message.

        This uses SlackIntegration's format_link function and Discord will
        handle the translation of Slack URL to Discord URL

        Args:
            path (str):
                The path on the Review Board server.

            text (str):
                The text for the link.

        Returns:
            str:
            The link for use in Slack.
        """
        return format_link(path=path, text=text)

    def format_field_text(
        self,
        text: str,
    ) -> str:
        """Format the field text, providing any normalization required.

        This will limit the text of any Discord field to 1024 characters.
        Failing to do so results in errors posting messages.

        Version Added:
            4.0

        Args:
            text (str):
                The text for the field.

        Returns:
            str:
            The formatted or normalized text.
        """
        if len(text) > 1024:
            text = '%s...' % text[:1021]

        return text

    # NOTE: It's technically type-unsafe to replace an attribute with a
    #       property, but this works for us practically.
    @cached_property
    def icon_static_urls(self) -> dict[str, str]:  # type: ignore
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for Discord.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        assert extension is not None

        return {
            '1x': extension.get_static_url('images/discord/icon.png'),
            '2x': extension.get_static_url('images/discord/icon@2x.png'),
        }
