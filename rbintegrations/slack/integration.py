from __future__ import unicode_literals

import json
import logging

from django.utils.functional import cached_property
from django.utils.six.moves.urllib.request import Request, urlopen
from reviewboard.admin.server import build_server_url

from rbintegrations.basechat.forms import BaseChatIntegrationConfigForm
from rbintegrations.basechat.integration import BaseChatIntegration


def build_slack_message(integration, title, title_link, fallback_text, fields,
                        pre_text, body, color, thumb_url, image_url):
    """Build message using Slack webhook format.

    This will build the payload data for HTTP requests to services such as
    Slack, Mattermost and Discord.

    Args:
        integration (BaseChatIntegration):
            The Integration.

        title (unicode):
            The title for the message.

        title_link (unicode):
            The link for the title of the message.

        fallback_text (unicode):
            The non-rich fallback text to display in the chat, for use in
            IRC and other services.

        fields (dict):
            The fields comprising the rich message to display in chat.

        pre_text (unicode):
            Text to display before the rest of the message.

        body (unicode):
            The body of the message.

        color (unicode):
            A Slack color string or RGB hex value for the message.

        thumb_url (unicode):
            URL of an image to show on the side of the message.

        image_url (unicode):
            URL of an image to show in the message.

    Returns:
        dict:
        The payload of the Slack message request.
    """
    if not color:
        color = integration.DEFAULT_COLOR

    attachment = {
        'color': color or integration.DEFAULT_COLOR,
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
        'attachments': [attachment],
        'icon_url': integration.LOGO_URL,
    }


def notify(integration, title, title_link, fallback_text, local_site,
           review_request, event_name, fields, pre_text, body, color,
           thumb_url, image_url):
    """Send a webhook notification.

    This will post the given message to any Slacks/Mattermost channels
    configured to receive it. This is oriented towards Slack, however is
    broken out of the SlackIntegration because other services (like
    Mattermost) duplicate Slack APIs.

    Args:
        integration (BaseChatIntegration):
            The Integration.

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

        event_name (unicode):
            The name of the event triggering this notification.

        fields (dict):
            The fields comprising the rich message to display in chat.

        pre_text (unicode):
            Text to display before the rest of the message.

        body (unicode):
            The body of the message.

        color (unicode):
            A Slack color string or RGB hex value for the message.

        thumb_url (unicode):
            URL of an image to show on the side of the message.

        image_url (unicode):
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

        logging.debug('Sending notification for event "%s", '
                      'review_request ID %d to channel "%s", '
                      'webhook URL %s',
                      event_name, review_request.pk, channel, webhook_url)

        try:
            data = json.dumps(payload)
            headers = {
                'Content-Type': 'application/json',
                'Content-Length': len(data),
            }
            urlopen(Request(webhook_url, data, headers))
        except Exception as e:
            logging.error('Failed to send notification: %s',
                          e, exc_info=True)


def format_link(path, text):
    """Format the given URL and text to be shown in a message.

    This will combine together the parts of the URL (method, domain, path)
    and format it using Slack/Mattermost's URL syntax. This is oriented
    towards Slack, however is broken out of the SlackIntegration because
    other services (like Mattermost) duplicate Slack APIs.

    Args:
        path (unicode):
            The path on the Review Board server.

        text (unicode):
            The text for the link.

    Returns:
        unicode:
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

    config_form_cls = BaseChatIntegrationConfigForm

    DEFAULT_COLOR = '#efcc96'
    ASSETS_BASE_URL = 'https://static.reviewboard.org/integration-assets/slack'
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
        """Send a webhook notification to Slack.

        This will post the given message to any Slack channels configured to
        receive it.

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
                A Slack color string or RGB hex value for the message.

            thumb_url (unicode, optional):
                URL of an image to show on the side of the message.

            image_url (unicode, optional):
                URL of an image to show in the message.
        """
        notify(self, title, title_link, fallback_text, local_site,
               review_request, event_name, fields, pre_text, body, color,
               thumb_url, image_url)

    def format_link(self, path, text):
        """Format the given URL and text to be shown in a Slack message.

        This will combine together the parts of the URL (method, domain, path)
        and format it using Slack's URL syntax.

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
            The icons for Slack.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/slack/icon.png'),
            '2x': extension.get_static_url('images/slack/icon@2x.png'),
        }
