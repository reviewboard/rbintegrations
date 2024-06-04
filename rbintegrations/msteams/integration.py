"""Integration for Microsoft Teams.

Version Added:
    4.0
"""

from __future__ import annotations

import json
import logging
import re
from typing import ClassVar, MutableMapping, Optional, Sequence, TYPE_CHECKING
from urllib.request import Request, urlopen

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from reviewboard.admin.server import build_server_url

from rbintegrations.basechat.integration import BaseChatIntegration
from rbintegrations.msteams.forms import MSTeamsIntegrationConfigForm

if TYPE_CHECKING:
    from djblets.util.typing import JSONDict, JSONList
    from rbintegrations.basechat.integration import FieldsDict
    from reviewboard.site.models import LocalSite
    from reviewboard.reviews.models import ReviewRequest


logger = logging.getLogger(__name__)


class MSTeamsIntegration(BaseChatIntegration):
    """Integrates Review Board with MS Teams.

    This will handle updating MS Teams channels when review requests
    are posted, changed, or closed, and when there's new activity on the
    review request.

    Version Added:
        4.0
    """

    name = 'Microsoft Teams'
    description = _(
        'Notifies channels in Microsoft Teams when review requests are '
        'created, updated, and reviewed.'
    )

    default_settings = {
        'notify_username': 'Review Board',
        'webhook_url': '',
    }

    config_form_cls = MSTeamsIntegrationConfigForm

    use_emoji_shortcode = False

    assets_base_url: ClassVar[str] = (
        'https://static.reviewboard.org/integration-assets/msteams'
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
        """Send a WebHook notification to MS Teams.

        This will post the given message to any MS Teams channels
        configured to receive it.

        The message JSON payload follows the Adaptive Card v1.5 schema.

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
                An RGB hex value for the message.

            thumb_url (str, optional):
                URL of an image to show on the side of the message.

            image_url (str, optional):
                URL of an image to show in the message.
        """
        pre_text_card_columns: JSONList = [
            {
                'type': 'Column',
                'width': 'Auto',
                'verticalContentAlignment': 'Center',
                'items': [
                    {
                        'type': 'TextBlock',
                        'text': pre_text,
                        'size': 'Medium',
                        'style': 'Heading',
                    },
                ]
            }
        ]

        if thumb_url:
            pre_text_card_columns.append({
                'type': 'Column',
                'width': 'auto',
                'spacing': 'None',
                'items': [
                    {
                        'type': 'Image',
                        'url': thumb_url,
                        'altText': 'A trophy earned on the review request.',
                        'width': '32px',
                        'height': '32px',
                    }
                ],
            })

        pre_text_card: JSONDict = {
            'type': 'ColumnSet',
            'columns': pre_text_card_columns
        }

        activity_card: JSONDict = {
            'type': 'ColumnSet',
            'columns': [
                {
                    'type': 'Column',
                    'width': 'Auto',
                    'items': [
                        {
                            'type': 'Image',
                            'url': self.logo_url,
                            'alt': 'Review Board notification',
                            'width': '45px',
                            'height': '45px',
                        },
                    ],
                },
                {
                    'type': 'Column',
                    'items': [
                        {
                            'type': 'TextBlock',
                            'text': self.format_link(path=title_link,
                                                     text=title),
                            'weight': 'Bolder',
                            'wrap': True,
                        },
                        {
                            'type': 'TextBlock',
                            'text': body or '',
                            'isSubtle': True,
                            'spacing': 'Small',
                            'wrap': True,
                        },
                    ]
                },
            ]
        }

        main_body: list[JSONDict] = [
            pre_text_card,
            activity_card,
        ]

        if fields:
            main_body.append({
                'type': 'FactSet',
                'facts': [
                    {
                        'title': field['title'],
                        'value': field['value'],
                    }
                    for field in fields
                ],
            })

        if image_url:
            main_body.append({
                'type': 'Image',
                'url': image_url,
                'altText': 'An image file attachment from the review request.',
            })

        payload: JSONDict = {
            'type': 'message',
            'attachments': [
                {
                    'contentType': 'application/vnd.microsoft.card.adaptive',
                    'contentUrl': None,
                    'content':
                        {
                            '$schema': 'http://adaptivecards.io/schemas/'
                                       'adaptive-card.json',
                            'type': 'AdaptiveCard',
                            'version': '1.5',
                            'body': main_body,
                        },
                },
            ],
        }

        # Send a notification to any configured channels.
        for config in self.get_configs(local_site):
            if not config.match_conditions(form_cls=self.config_form_cls,
                                           review_request=review_request):
                continue

            webhook_url = config.get('webhook_url')

            logger.debug('Sending notification for event "%s", '
                         'review_request ID %d, '
                         'WebHook URL %s',
                         event_name, review_request.pk, webhook_url)

            try:
                if not webhook_url:
                    raise Exception('WebHook URL has not been configured.')

                data = json.dumps(payload).encode('utf-8')
                headers: MutableMapping[str, str] = {
                    'Content-Length': str(len(data)),
                    'Content-Type': 'application/json',
                }
                urlopen(Request(webhook_url, data, headers))
            except Exception as e:
                logger.exception('Failed to send notification: %s', e)

    def format_link(
        self,
        *,
        path: str,
        text: str,
    ) -> str:
        """Format the given URL and text to be shown in a MS Teams message.

        This will combine together the parts of the URL (method, domain, path)
        and format it using MS Teams' URL syntax.

        Args:
            path (str):
                The path on the Review Board server.

            text (str):
                The text for the link.

        Returns:
            str:
            The link for use in MS Teams.
        """
        # We only care about escaping parentheses in the URL, since those are
        # the only things that can break the Markdown link.
        escape_map = {
            '(': '%28',
            ')': '%29',
        }

        path = re.sub(
            '[()]',
            lambda m: escape_map[m.group(0)],
            path)

        # We only care about escaping brackets in the text, since those
        # are the only things that can break the Markdown link.
        text = re.sub(r'([\[\]])', r'\\\1', text)

        return (
            f'[{text}]'
            f'({build_server_url(path)})'
        )

    # NOTE: It's technically type-unsafe to replace an attribute with a
    #       property, but this works for us practically.
    @cached_property
    def icon_static_urls(self) -> dict[str, str]:  # type: ignore
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for MS Teams.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        assert extension is not None

        return {
            '1x': extension.get_static_url('images/msteams/icon.png'),
            '2x': extension.get_static_url('images/msteams/icon@2x.png'),
        }
