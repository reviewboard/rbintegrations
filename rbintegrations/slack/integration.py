"""Integration for Slack."""

from __future__ import annotations

import json
import logging
from typing import (MutableMapping, Optional, Sequence, TYPE_CHECKING, Union,
                    cast)
from urllib.request import Request, urlopen

from django.utils.functional import cached_property
from djblets.util.typing import JSONListImmutable
from housekeeping.functions import deprecate_non_keyword_only_args
from reviewboard.admin.server import build_server_url

from rbintegrations.basechat.integration import BaseChatIntegration
from rbintegrations.deprecation import RemovedInRBIntegrations50Warning

if TYPE_CHECKING:
    from djblets.util.typing import JSONDict, JSONValue
    from rbintegrations.basechat.integration import FieldsDict
    from reviewboard.reviews.models import ReviewRequest
    from reviewboard.site.models import LocalSite


logger = logging.getLogger(__name__)


@deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
def build_slack_message(
    *,
    integration: BaseChatIntegration,
    title: str,
    title_link: str,
    fallback_text: str,
    fields: Sequence[FieldsDict] = [],
    pre_text: Optional[str] = None,
    body: Optional[str] = None,
    color: Optional[str] = None,
    thumb_url: Optional[str] = None,
    image_url: Optional[str] = None,
) -> JSONDict:
    """Build message using Slack WebHook format.

    This will build the payload data for HTTP requests to services such as
    Slack, Mattermost and Discord.

    Version Changed:
        4.0:
        * Made all arguments keyword-only.

    Args:
        integration (BaseChatIntegration):
            The Integration.

        title (str):
            The title for the message.

        title_link (str):
            The link for the title of the message.

        fallback_text (str):
            The non-rich fallback text to display in the chat, for use in
            IRC and other services.

        fields (list of rbintegrations.basechat.integration.FieldsDict,
                optional):
            The fields comprising the rich message to display in chat.

        pre_text (str, optional):
            Text to display before the rest of the message.

        body (str, optional):
            The body of the message.

        color (str, optional):
            A Slack color string or RGB hex value for the message.

        thumb_url (str, optional):
            URL of an image to show on the side of the message.

        image_url (str, optional):
            URL of an image to show in the message.

    Returns:
        djblets.util.typing.JSONDict:
        The payload of the Slack message request.
    """
    if not color:
        color = integration.default_color

    attachment: dict[str, Union[JSONValue, Sequence[FieldsDict]]] = {
        'color': color or integration.default_color,
        'fallback': fallback_text,
        'title': title,
        'title_link': title_link,
        'text': body,
        'pretext': pre_text,
    }

    if fields:
        attachment['fields'] = fields

    if thumb_url:
        attachment['thumb_url'] = thumb_url

    if image_url:
        attachment['image_url'] = image_url

    return {
        'attachments': cast(JSONListImmutable, [attachment]),
        'icon_url': integration.logo_url,
    }


@deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
def notify(
    *,
    integration: BaseChatIntegration,
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
    """Send a WebHook notification.

    This will post the given message to any Slacks/Mattermost channels
    configured to receive it. This is oriented towards Slack, however is
    broken out of the SlackIntegration because other services (like
    Mattermost) duplicate Slack APIs.

    Version Changed:
        4.0:
        * Made all arguments keyword-only.

    Args:
        integration (BaseChatIntegration):
            The Integration.

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

        event_name (str):
            The name of the event triggering this notification.

        fields (list of rbintegrations.basechat.integration.FieldsDict,
                optional):
            The fields comprising the rich message to display in chat.

        pre_text (str, optional):
            Text to display before the rest of the message.

        body (str, optional):
            The body of the message.

        color (str, optional):
            A Slack color string or RGB hex value for the message.

        thumb_url (str, optional):
            URL of an image to show on the side of the message.

        image_url (str, optional):
            URL of an image to show in the message.
    """
    common_payload = build_slack_message(integration=integration,
                                         title=title,
                                         title_link=title_link,
                                         fallback_text=fallback_text,
                                         fields=fields,
                                         pre_text=pre_text,
                                         body=body,
                                         color=color,
                                         thumb_url=thumb_url,
                                         image_url=image_url)

    # Send a notification to any configured channels.
    for config in integration.get_configs(local_site):
        if not config.match_conditions(form_cls=integration.config_form_cls,
                                       review_request=review_request):
            continue

        payload = dict({
            'username': config.get('notify_username'),
        }, **common_payload)

        channel = config.get('channel')

        if channel:
            payload['channel'] = channel

        webhook_url = config.get('webhook_url')

        logger.debug('Sending notification for event "%s", '
                     'review_request ID %d to channel "%s", '
                     'WebHook URL %s',
                     event_name, review_request.pk, channel, webhook_url)

        try:
            if not webhook_url:
                raise Exception('WebHook URL has not been configured.')

            data = json.dumps(payload).encode('utf-8')
            headers: MutableMapping[str, str] = {
                'Content-Type': 'application/json',
                'Content-Length': str(len(data)),
            }
            urlopen(Request(webhook_url, data, headers))
        except Exception as e:
            logger.error('Failed to send notification: %s',
                         e, exc_info=True)


@deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
def format_link(
    *,
    path: str,
    text: str,
) -> str:
    """Format the given URL and text to be shown in a message.

    This will combine together the parts of the URL (method, domain, path)
    and format it using Slack/Mattermost's URL syntax. This is oriented
    towards Slack, however is broken out of the SlackIntegration because
    other services (like Mattermost) duplicate Slack APIs.

    Version Changed:
        4.0:
        * Made all arguments keyword-only.

    Args:
        path (str):
            The path on the Review Board server.

        text (str):
            The text for the link.

    Returns:
        str:
        The link for use in Slack.
    """
    # Slack/Mattermost only want these three entities replaced, rather than
    # all the entities that Django's escape() would attempt to replace.
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    return '<%s|%s>' % (build_server_url(path), text)


class SlackIntegration(BaseChatIntegration):
    """Integrates Review Board with Slack.

    This will handle updating Slack channels when review requests are posted,
    changed, or closed, and when there's new activity on the review request.
    """

    name = 'Slack'
    description = (
        'Notifies channels in Slack when review requests are created, '
        'updated, and reviewed.'
    )

    default_settings = {
        'webhook_url': '',
        'channel': '',
        'notify_username': 'Review Board',
    }

    assets_base_url = (
        'https://static.reviewboard.org/integration-assets/slack'
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
        """Send a WebHook notification to Slack.

        This will post the given message to any Slack channels configured to
        receive it.

        Args:
            title (str):
                The title for the message.

            title_link (str):
                The link for the title of the message.

            fallback_text (str):
                The non-rich fallback text to display in the chat, for use in
                IRC and other services.

            fields (list of rbintegrations.basechat.integration.FieldsDict,
                    optional):
                The fields comprising the rich message to display in chat.

            local_site (reviewboard.site.models.LocalSite):
                The Local Site for the review request or review emitting
                the message. Only integration configurations matching this
                Local Site will be processed.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request the notification is bound to.

            event_name (str):
                The name of the event triggering this notification.

            pre_text (str, optional):
                Text to display before the rest of the message.

            body (str, optional):
                The body of the message.

            color (str, optional):
                A Slack color string or RGB hex value for the message.

            thumb_url (str, optional):
                URL of an image to show on the side of the message.

            image_url (str, optional):
                URL of an image to show in the message.
        """
        notify(integration=self,
               title=title,
               title_link=title_link,
               fallback_text=fallback_text,
               local_site=local_site,
               review_request=review_request,
               event_name=event_name,
               fields=fields,
               pre_text=pre_text,
               body=body,
               color=color,
               thumb_url=thumb_url,
               image_url=image_url)

    def format_link(
        self,
        *,
        path: str,
        text: str,
    ) -> str:
        """Format the given URL and text to be shown in a Slack message.

        This will combine together the parts of the URL (method, domain, path)
        and format it using Slack's URL syntax.

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

    # NOTE: It's technically type-unsafe to replace an attribute with a
    #       property, but this works for us practically.
    @cached_property
    def icon_static_urls(self) -> dict[str, str]:  # type: ignore
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for Slack.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        assert extension is not None

        return {
            '1x': extension.get_static_url('images/slack/icon.png'),
            '2x': extension.get_static_url('images/slack/icon@2x.png'),
        }
