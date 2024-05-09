"""Integration for Mattermost"""

from __future__ import annotations

from typing import Optional, Sequence, TYPE_CHECKING

from django.utils.functional import cached_property

from rbintegrations.basechat.integration import BaseChatIntegration
from rbintegrations.slack.integration import format_link, notify

if TYPE_CHECKING:
    from rbintegrations.basechat.integration import FieldsDict
    from reviewboard.reviews.models import ReviewRequest
    from reviewboard.site.models import LocalSite


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

    assets_base_url = (
        'https://static.reviewboard.org/integration-assets/mattermost'
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
        """Send a WebHook notification to Mattermost.

        This will post the given message to any Mattermost channels
        configured to receive it.

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
        """Format the given URL and text to be shown in a Mattermost message.

        This will combine together the parts of the URL (method, domain, path)
        and format it using Mattermost's URL syntax.

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

    # NOTE: Python hasn't yet figured out how typing should work for things
    #       that can be a plain attribute or a property, so we ignore.
    @cached_property
    def icon_static_urls(self) -> dict[str, str]:  # type: ignore
        """The icons used for the integration.

        Returns:
            dict:
            The icons for Mattermost.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        assert extension is not None

        return {
            '1x': extension.get_static_url('images/mattermost/icon.png'),
            '2x': extension.get_static_url('images/mattermost/icon@2x.png'),
        }
