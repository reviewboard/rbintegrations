"""Integration for chat integrations"""

from __future__ import annotations

import logging
from typing import (ClassVar, Optional, Sequence, TYPE_CHECKING, Tuple,
                    TypedDict)

from djblets.db.query import get_object_or_none
from djblets.util.templatetags.djblets_utils import user_displayname
from housekeeping.functions import deprecate_non_keyword_only_args
from reviewboard.accounts.models import Trophy
from reviewboard.admin.server import build_server_url
from reviewboard.extensions.hooks import SignalHook
from reviewboard.integrations.base import Integration
from reviewboard.reviews.models import (BaseComment, Comment,
                                        FileAttachmentComment,
                                        GeneralComment,
                                        ReviewRequest,
                                        ScreenshotComment)
from reviewboard.reviews.signals import (review_request_closed,
                                         review_request_published,
                                         review_request_reopened,
                                         review_published,
                                         reply_published)
from reviewboard.site.urlresolvers import local_site_reverse

from rbintegrations.basechat.forms import BaseChatIntegrationConfigForm
from rbintegrations.deprecation import RemovedInRBIntegrations50Warning

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from djblets.integrations.forms import IntegrationConfigForm
    from reviewboard.changedescs.models import ChangeDescription
    from reviewboard.reviews.models import Review
    from reviewboard.site.models import LocalSite


logger = logging.getLogger(__name__)


class FieldsDict(TypedDict):
    """The fields comprising the information to display in a chat message.

    Version Added:
        4.0
    """

    #: Whether the field is short.
    #:
    #: This should be ``True`` if the field is short enough to be displayed
    #: side by side with other fields.
    #:
    #: This may not be relevant for some chat integrations.
    short: Optional[bool]

    #: The title for the field.
    title: str

    #: The value for the field.
    value: str


class BaseChatIntegration(Integration):
    """Integrates Review Board with chat applications.

    This will handle updating chat channels when review requests are posted,
    changed, or closed, and when there's new activity on the review request.
    """

    #: The base URL to use for static assets to use in chat messages.
    #:
    #: The static assets will usually just be the Review Board logo and
    #: trophy icons.
    #:
    #: Type:
    #:     str
    assets_base_url: ClassVar[str] = (
        'https://static.reviewboard.org/integration-assets/chat-common'
    )

    #: The timestamp to use for static assets.
    #:
    #: Type:
    #:     str
    assets_timestamp: ClassVar[str] = '?20240418-1205'

    #: The default color to style the chat message.
    #:
    #: Type:
    #:     str
    default_color: ClassVar[str] = '#efcc96'

    #: The URL of the Review Board logo to use in chat messages.
    #:
    #: Type:
    #:     str
    logo_url: ClassVar[str] = (
        f'{assets_base_url}/reviewboard.png{assets_timestamp}'
    )

    #: URLs of trophy icons to use in chat messages.
    #:
    #: Type:
    #:     dict
    trophy_urls: ClassVar[dict[str, str]] = {
        'fish': f'{assets_base_url}/fish-trophy.png{assets_timestamp}',
        'milestone':
            f'{assets_base_url}/milestone-trophy.png{assets_timestamp}',
    }

    #: Whether to use shortcodes to represent emojis instead of unicode blocks.
    #:
    #: Version Added:
    #:     4.0
    #:
    #: Type:
    #:     bool
    use_emoji_shortcode: ClassVar[bool] = True

    #: Extensions of images that can appear in chat messages.
    #:
    #: Type:
    #:     tuple of str
    valid_image_url_exts: ClassVar[Tuple[str, ...]] = (
        '.png',
        '.bmp',
        '.gif',
        '.jpg',
        '.jpeg',
    )

    #: The form class for handling integration configuration.
    #:
    #: Type:
    #:     djblets.integrations.forms.IntegrationConfigForm
    config_form_cls: ClassVar[type[IntegrationConfigForm]] = \
        BaseChatIntegrationConfigForm

    def initialize(self) -> None:
        """Initialize the integration hooks."""
        hooks = (
            (review_request_closed, self._on_review_request_closed),
            (review_request_published, self._on_review_request_published),
            (review_request_reopened, self._on_review_request_reopened),
            (review_published, self._on_review_published),
            (reply_published, self._on_reply_published),
        )

        for signal, handler in hooks:
            SignalHook(self, signal, handler)

    @deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
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
        """Send a WebHook notification to chat application.

        This will post the given message to any channels configured to
        receive it.

        Version Changed:
            4.0:
            * Made all arguments keyword-only.

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
        raise NotImplementedError(
            '%s must implement notify' % type(self).__name__)

    @deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
    def notify_review_or_reply(
        self,
        *,
        user: User,
        review: Review,
        pre_text: Optional[str] = None,
        fallback_text: Optional[str] = None,
        event_name: Optional[str] = None,
        first_comment: Optional[BaseComment] = None,
        **kwargs,
    ) -> None:
        """Notify chat application for any new posted reviews or replies.

        This performs the common work of notifying configured channels
        when there's a review or a reply.

        Version Changed:
            4.0:
            * Made all arguments keyword-only.

        Args:
            user (django.contrib.auth.models.User):
                The user who posted the review or reply.

            review (reviewboard.reviews.models.Review):
                The review or reply that was posted.

            pre_text (str, optional):
                Text to show before the message attachments.

            fallback_text (str, optional):
                Text to show in the fallback text, before the review URL and
                after the review request ID.

            event_name (str, optional):
                The name of the event triggering this notification.

            first_comment (reviewboard.reviews.models.BaseComment, optional):
                The first comment in a review, to generate the body message
                from. This is optional, and will be computed if needed.

            **kwargs (dict):
                Other keyword arguments to pass to :py:meth:`notify`.
        """
        review_request = review.review_request
        review_url = build_server_url(review.get_absolute_url())
        fallback_text = '#%s: %s: %s' % (review_request.display_id,
                                         fallback_text, review_url)
        body = ''
        review_body_top = review.body_top

        # Prefer showing the body, unless it's just a repeat of a "Ship It!".
        # Otherwise, we'll aim for a comment, or body_bottom.
        if (review_body_top and
            (not review.ship_it or review_body_top != 'Ship It!')):
            body = review_body_top
        else:
            if not first_comment:
                for comment_cls in (Comment, FileAttachmentComment,
                                    ScreenshotComment, GeneralComment):
                    try:
                        first_comment = (
                            comment_cls.objects
                            .filter(review=review)
                            .only('text')
                        )[0]
                        break
                    except IndexError:
                        pass

            if first_comment:
                body = first_comment.text
            else:
                body = review.body_bottom

        self.notify(title=self.get_review_request_title(review_request),
                    title_link=review_url,
                    fallback_text=fallback_text,
                    pre_text=pre_text,
                    body=body,
                    local_site=review.review_request.local_site,
                    review_request=review_request,
                    event_name=event_name,
                    **kwargs)

    @deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
    def notify_review_request(
        self,
        review_request: ReviewRequest,
        *,
        fallback_text: Optional[str],
        event_name: Optional[str],
        **kwargs,
    ) -> None:
        """Notify chat application for a review request update.

        This performs the common work of notifying configured channels
        when there's a new review request or update to a review request.

        Version Changed:
            4.0:
            * Made all arguments other than ``review_request`` keyword-only.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request.

            fallback_text (str):
                Text to show in the fallback text, before the review URL and
                after the review request ID.

            event_name (str):
                The name of the event triggering this notification.

            **kwargs (dict):
                Other keyword arguments to pass to :py:meth:`notify`.
        """
        review_request_url = self.get_review_request_url(review_request)
        fallback_text = '#%s: %s: %s' % (review_request.display_id,
                                         fallback_text,
                                         review_request_url)

        self.notify(title=self.get_review_request_title(review_request),
                    title_link=review_request_url,
                    fallback_text=fallback_text,
                    review_request=review_request,
                    event_name=event_name,
                    **kwargs)

    @deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
    def format_link(
        self,
        *,
        path: str,
        text: str,
    ) -> str:
        """Format the given URL and text to be shown in a Slack message.

        This will combine together the parts of the URL (method, domain, path)
        and format it using Slack's URL syntax.

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
        raise NotImplementedError(
            '%s must implement format_link' % type(self).__name__)

    @deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
    def get_user_text_url(
        self,
        *,
        user: User,
        local_site: Optional[LocalSite],
    ) -> str:
        """Return the URL to a user page.

        Version Changed:
            4.0:
            * Made all arguments keyword-only.

        Args:
            user (django.contrib.auth.models.User):
                The user being linked to.

            local_site (reviewboard.site.models.LocalSite):
                The local site for the link, if any.

        Returns:
            str:
            The URL to the user page.
        """
        # This doesn't use user.get_absolute_url because that won't include
        # site roots or local site names.
        return local_site_reverse(
            'user',
            local_site=local_site,
            kwargs={'username': user.username})

    @deprecate_non_keyword_only_args(RemovedInRBIntegrations50Warning)
    def get_user_text_link(
        self,
        *,
        user: User,
        local_site: Optional[LocalSite],
    ) -> str:
        """Return the chat application-formatted link to a user page.

        Version Changed:
            4.0:
            * Made all arguments keyword-only.

        Args:
            user (django.contrib.auth.models.User):
                The user being linked to.

            local_site (reviewboard.site.models.LocalSite):
                The local site for the link, if any.

        Returns:
            str:
            The formatted link to the user page.
        """
        return self.format_link(
            path=self.get_user_text_url(user=user, local_site=local_site),
            text=user.get_full_name() or user.username)

    def get_review_request_title(
        self,
        review_request: ReviewRequest,
    ) -> str:
        """Return the title for a review request message.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request.

        Returns:
            str:
            The title for the message.
        """
        return f'#{review_request.display_id}: {review_request.summary}'

    def get_review_request_text_link(
        self,
        review_request: ReviewRequest,
    ) -> str:
        """Return the chat application-formatted link to a review request.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request being linked to.

        Returns:
            str:
            The formatted link to the review request.
        """
        return self.format_link(
            path=review_request.get_absolute_url(),
            text=review_request.summary)

    def get_review_request_url(
        self,
        review_request: ReviewRequest,
    ) -> str:
        """Return the absolute URL to a review request.

        Returns:
            str:
            The absolute URL to the review request.
        """
        return build_server_url(review_request.get_absolute_url())

    def _on_review_request_closed(
        self,
        user: User,
        review_request: ReviewRequest,
        close_type: str,
        description: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Handler for when review requests are closed.

        This will send a notification to any configured channels when
        a review request is closed.

        Args:
            user (django.contrib.auth.models.User):
                The user who closed the review request.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that was closed.

            close_type (str):
                The close type.

            description (str, optional):
                The close message,

            **kwargs (dict, unused):
                Additional keyword arguments passed to the handler.
        """
        if not user:
            user = review_request.submitter

        user_link = self.get_user_text_link(
            user=user,
            local_site=review_request.local_site)

        if close_type == ReviewRequest.DISCARDED:
            pre_text = f'Discarded by {user_link}'
            fallback_text = f'Discarded by {user_displayname(user)}'
        elif close_type == ReviewRequest.SUBMITTED:
            pre_text = f'Closed as completed by {user_link}'
            fallback_text = f'Closed as completed by {user_displayname(user)}'
        else:
            logger.error('Tried to notify on review_request_closed for '
                         'review request pk=%d with unknown close type "%s"',
                         review_request.pk, close_type)
            return

        self.notify_review_request(review_request,
                                   fallback_text=fallback_text,
                                   body=description,
                                   pre_text=pre_text,
                                   local_site=review_request.local_site,
                                   event_name='review_request_closed')

    def _on_review_request_published(
        self,
        user: User,
        review_request: ReviewRequest,
        changedesc: ChangeDescription,
        **kwargs,
    ) -> None:
        """Handler for when review requests are published.

        This will send a notification to any configured channels when
        a review request is published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the review request.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that was published.

            changedesc (reviewboard.changedescs.models.ChangeDescription):
                The change description for the update, if any.

            **kwargs (dict, unused):
                Additional keyword arguments passed to the handler.
        """
        user_link = self.get_user_text_link(
            user=user,
            local_site=review_request.local_site)
        fields: list[FieldsDict] = []

        if changedesc:
            fallback_text = f'New update from {user_displayname(user)}'
            pre_text = f'New update from {user_link}'

            # This might be empty, which is fine. We won't show an update
            # at that point.
            body = changedesc.text
        else:
            fallback_text = f'New review request from {user_displayname(user)}'
            pre_text = f'New review request from {user_link}'
            body = None

            fields.append({
                'short': False,
                'title': 'Description',
                'value': review_request.description,
            })

        # Link to the diff in the update, if any.
        diffset = review_request.get_latest_diffset()

        if diffset:
            diff_url = local_site_reverse(
                'view-diff-revision',
                local_site=review_request.local_site,
                kwargs={
                    'review_request_id': review_request.display_id,
                    'revision': diffset.revision,
                })

            fields.append({
                'short': True,
                'title': 'Diff',
                'value': self.format_link(path=diff_url,
                                          text=f'Revision {diffset.revision}'),
            })

        if review_request.repository:
            fields.append({
                'short': True,
                'title': 'Repository',
                'value': review_request.repository.name,
            })

        if review_request.branch:
            fields.append({
                'short': True,
                'title': 'Branch',
                'value': review_request.branch,
            })

        # See if there are any new interesting file attachments to show.
        # These will only show up if the file is accessible.
        attachment = None
        valid_image_url_exts = self.valid_image_url_exts

        if changedesc:
            # Only show new files added in this change.
            try:
                new_files_pks = [
                    file[2]
                    for file in changedesc.fields_changed['files']['added']
                    if len(file) >= 3
                ]
            except KeyError:
                new_files_pks = []

            file_attachments = review_request.file_attachments.filter(
                pk__in=new_files_pks)
        else:
            # This is a new review request, so show any valid image.
            file_attachments = review_request.file_attachments.all()

        for attachment in file_attachments:
            if attachment.filename.endswith(valid_image_url_exts):
                # This one wins. Show it.
                break
        else:
            attachment = None

        if attachment:
            image_url = attachment.get_absolute_url()
        else:
            image_url = None

        # Find any trophies we may want to show in the update.
        trophies = Trophy.objects.get_trophies(review_request)
        trophy_url = None

        if trophies:
            # For now, due to the need to look up resources from a stable
            # location, we're only supporting certain trophies. First one
            # wins.
            for trophy in trophies:
                try:
                    trophy_url = self.trophy_urls[trophy.category]
                    break
                except KeyError:
                    pass

        self.notify_review_request(review_request,
                                   fallback_text=fallback_text,
                                   body=body,
                                   pre_text=pre_text,
                                   fields=fields,
                                   thumb_url=trophy_url,
                                   image_url=image_url,
                                   local_site=review_request.local_site,
                                   event_name='review_request_published')

    def _on_review_request_reopened(
        self,
        user: User,
        review_request: ReviewRequest,
        **kwargs,
    ) -> None:
        """Handler for when review requests are reopened.

        This will send a notification to any configured channels when
        a review request is reopened.

        Args:
            user (django.contrib.auth.models.User):
                The user who reopened the review request.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that was published.

            **kwargs (dict, unused):
                Additional keyword arguments passed to the handler.
        """
        if not user:
            user = review_request.submitter

        user_link = self.get_user_text_link(
            user=user,
            local_site=review_request.local_site)
        pre_text = f'Reopened by {user_link}'
        fallback_text = f'Reopened by {user_displayname(user)}'

        self.notify_review_request(review_request,
                                   fallback_text=fallback_text,
                                   pre_text=pre_text,
                                   body=review_request.description,
                                   local_site=review_request.local_site,
                                   event_name='review_request_reopened')

    def _on_review_published(
        self,
        user: User,
        review: Review,
        **kwargs,
    ) -> None:
        """Handler for when a review is published.

        This will send a notification to any configured channels when
        a review is published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the review.

            review (reviewboard.reviews.models.Review):
                The review that was published.

            **kwargs (dict, unused):
                Additional keyword arguments passed to the handler.
        """
        fields: list[FieldsDict]
        open_issues = 0
        first_comment = None

        for comment in review.get_all_comments():
            if not first_comment:
                first_comment = comment

            if (comment.issue_opened and
                comment.issue_status == BaseComment.OPEN):
                open_issues += 1

        if open_issues == 1:
            issue_text = '1 issue'
        else:
            issue_text = f'{open_issues} issues'

        user_link = self.get_user_text_link(
            user=user,
            local_site=review.review_request.local_site)
        pre_text = f'New review from {user_link}'

        warning_emoji = '⚠'
        checkmark_emoji = '✅'

        if self.use_emoji_shortcode:
            warning_emoji = ':warning:'
            checkmark_emoji = ':white_check_mark:'

        if review.ship_it:
            if open_issues:
                fields = [{
                    'title': 'Fix it, then Ship it!',
                    'value': f'{warning_emoji} {issue_text}',
                    'short': True,
                }]
                extra_text = ' (Fix it, then Ship it!)'
                color = 'warning'
            else:
                fields = [{
                    'title': 'Ship it!',
                    'value': checkmark_emoji,
                    'short': True,
                }]
                extra_text = ' (Ship it!)'
                color = 'good'
        elif open_issues:
            fields = [{
                'title': 'Open Issues',
                'value': f'{warning_emoji} {issue_text}',
                'short': True,
            }]
            extra_text = f' ({issue_text})'
            color = 'warning'
        else:
            fields = []
            extra_text = ''
            color = None

        fallback_text = f'New review from {user_displayname(user)}{extra_text}'

        self.notify_review_or_reply(user=user,
                                    review=review,
                                    pre_text=pre_text,
                                    fallback_text=fallback_text,
                                    first_comment=first_comment,
                                    fields=fields,
                                    color=color,
                                    event_name='review_published')

    def _on_reply_published(
        self,
        user: User,
        reply: Review,
        **kwargs,
    ) -> None:
        """Handler for when a reply to a review is published.

        This will send a notification to any configured channels when
        a reply to a review is published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the reply.

            reply (reviewboard.reviews.models.Review):
                The reply that was published.

            **kwargs (dict, unused):
                Additional keyword arguments passed to the handler.
        """
        user_link = self.get_user_text_link(
            user=user,
            local_site=reply.review_request.local_site)
        pre_text = f'New reply from {user_link}'
        fallback_text = f'New reply from {user_displayname(user)}'

        self.notify_review_or_reply(user=user,
                                    review=reply,
                                    fallback_text=fallback_text,
                                    pre_text=pre_text,
                                    event_name='reply_published')
