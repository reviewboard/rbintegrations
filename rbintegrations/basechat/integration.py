"""Integration for chat integrations"""
from __future__ import unicode_literals

import logging

from djblets.db.query import get_object_or_none
from djblets.util.templatetags.djblets_utils import user_displayname
from reviewboard.accounts.models import Trophy
from reviewboard.admin.server import build_server_url
from reviewboard.extensions.hooks import SignalHook
from reviewboard.integrations import Integration
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


class BaseChatIntegration(Integration):
    """Integrates Review Board with chat applications.

    This will handle updating chat channels when review requests are posted,
    changed, or closed, and when there's new activity on the review request.
    """

    def initialize(self):
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

    def notify(self, title, title_link, fallback_text, local_site,
               review_request, event_name=None, fields={}, pre_text=None,
               body=None, color=None, thumb_url=None, image_url=None):
        """Send a webhook notification to chat application.

        This will post the given message to any channels configured to
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
                A color string or RGB hex value for the message.

            thumb_url (unicode, optional):
                URL of an image to show on the side of the message.

            image_url (unicode, optional):
                URL of an image to show in the message.
        """
        raise NotImplementedError(
            '%s must implement notify' % type(self).__name__)

    def notify_review_or_reply(self, user, review, pre_text, fallback_text,
                               event_name, first_comment=None, **kwargs):
        """Notify chat application for any new posted reviews or replies.

        This performs the common work of notifying configured channels
        when there's a review or a reply.

        Args:
            user (django.contrib.auth.models.User):
                The user who posted the review or reply.

            review (reviewboard.reviews.models.Review):
                The review or reply that was posted.

            pre_text (unicode, optional):
                Text to show before the message attachments.

            fallback_text (unicode, optional):
                Text to show in the fallback text, before the review URL and
                after the review request ID.

            event_name (unicode):
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

        if review.body_top:
            body = review.body_top

            # This is silly to show twice.
            if review.ship_it and body == 'Ship It!':
                body = ''
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

        self.notify(title=self.get_review_request_title(review_request),
                    title_link=review_url,
                    fallback_text=fallback_text,
                    pre_text=pre_text,
                    body=body,
                    local_site=review.review_request.local_site,
                    review_request=review_request,
                    event_name=event_name,
                    **kwargs)

    def notify_review_request(self, review_request, fallback_text, event_name,
                              **kwargs):
        """Notify chat application for a review request update.

        This performs the common work of notifying configured channels
        when there's a new review request or update to a review request.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request.

            fallback_text (unicode, optional):
                Text to show in the fallback text, before the review URL and
                after the review request ID.

            event_name (unicode):
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
        raise NotImplementedError(
            '%s must implement format_link' % type(self).__name__)

    def get_user_text_url(self, user, local_site):
        """Return the URL to a user page.

        Args:
            user (django.contrib.auth.models.User):
                The user being linked to.

            local_site (reviewboard.site.models.LocalSite):
                The local site for the link, if any.

        Returns:
            unicode:
            The URL to the user page.
        """
        # This doesn't use user.get_absolute_url because that won't include
        # site roots or local site names.
        return local_site_reverse(
            'user',
            local_site=local_site,
            kwargs={'username': user.username})

    def get_user_text_link(self, user, local_site):
        """Return the chat application-formatted link to a user page.

        Args:
            user (django.contrib.auth.models.User):
                The user being linked to.

            local_site (reviewboard.site.models.LocalSite):
                The local site for the link, if any.

        Returns:
            unicode:
            The formatted link to the user page.
        """
        return self.format_link(self.get_user_text_url(user, local_site),
                                user.get_full_name() or user.username)

    def get_review_request_title(self, review_request):
        """Return the title for a review request message.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request.

        Returns:
            unicode:
            The title for the message.
        """
        return '#%s: %s' % (review_request.display_id, review_request.summary)

    def get_review_request_text_link(self, review_request):
        """Return the chat application-formatted link to a review request.

        Args:
            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request being linked to.

        Returns:
            unicode:
            The formatted link to the review request.
        """
        return self.format_link(review_request.get_absolute_url(),
                                review_request.summary)

    def get_review_request_url(self, review_request):
        """Return the absolute URL to a review request.

        Returns:
            unicode:
            The absolute URL to the review request.
        """
        return build_server_url(review_request.get_absolute_url())

    def _on_review_request_closed(self, user, review_request, close_type,
                                  description=None, **kwargs):
        """Handler for when review requests are closed.

        This will send a notification to any configured channels when
        a review request is closed.

        Args:
            user (django.contrib.auth.models.User):
                The user who closed the review request.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that was closed.

            close_type (unicode):
                The close type.

            description (unicode):
                The close message,

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        if not user:
            user = review_request.submitter

        user_link = self.get_user_text_link(user, review_request.local_site)

        if close_type == ReviewRequest.DISCARDED:
            pre_text = 'Discarded by %s' % user_link
            fallback_text = 'Discarded by %s' % user_displayname(user)
        elif close_type == ReviewRequest.SUBMITTED:
            pre_text = 'Closed as completed by %s' % user_link
            fallback_text = 'Closed as completed by %s' % \
                user_displayname(user)
        else:
            logging.error('Tried to notify on review_request_closed for '
                          ' review request pk=%d with unknown close type "%s"',
                          review_request.pk, close_type)
            return

        if not user:
            user = review_request.submitter

        self.notify_review_request(review_request,
                                   fallback_text=fallback_text,
                                   body=description,
                                   pre_text=pre_text,
                                   local_site=review_request.local_site,
                                   event_name='review_request_closed')

    def _on_review_request_published(self, user, review_request, changedesc,
                                     **kwargs):
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

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        user_link = self.get_user_text_link(user, review_request.local_site)
        fields = []

        if changedesc:
            fallback_text = 'New update from %s' % user_displayname(user)
            pre_text = 'New update from %s' % user_link

            # This might be empty, which is fine. We won't show an update
            # at that point.
            body = changedesc.text
        else:
            fallback_text = 'New review request from %s' % \
                user_displayname(user)
            pre_text = 'New review request from %s' % user_link
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
                'value': self.format_link(diff_url,
                                          'Revision %s' % diffset.revision),
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

        if changedesc:
            # Only show new files added in this change.
            try:
                new_files = changedesc.fields_changed['files']['added']
            except KeyError:
                new_files = []

            for file_info in new_files:
                if (len(file_info) >= 3 and
                    file_info[1].endswith(self.VALID_IMAGE_URL_EXTS)):
                    # This one wins. Show it.
                    attachment = get_object_or_none(
                        review_request.file_attachments,
                        pk=file_info[2])
                    break
        else:
            # This is a new review request, so show the first valid image
            # we can find.
            for attachment in review_request.file_attachments.all():
                if attachment.filename.endswith(self.VALID_IMAGE_URL_EXTS):
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
                    trophy_url = self.TROPHY_URLS[trophy.category]
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

    def _on_review_request_reopened(self, user, review_request, **kwargs):
        """Handler for when review requests are reopened.

        This will send a notification to any configured channels when
        a review request is reopened.

        Args:
            user (django.contrib.auth.models.User):
                The user who reopened the review request.

            review_request (reviewboard.reviews.models.ReviewRequest):
                The review request that was published.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        if not user:
            user = review_request.submitter

        user_link = self.get_user_text_link(user, review_request.local_site)
        pre_text = 'Reopened by %s' % user_link
        fallback_text = 'Reopened by %s' % user_displayname(user)

        self.notify_review_request(review_request,
                                   fallback_text=fallback_text,
                                   pre_text=pre_text,
                                   body=review_request.description,
                                   local_site=review_request.local_site,
                                   event_name='review_request_reopened')

    def _on_review_published(self, user, review, **kwargs):
        """Handler for when a review is published.

        This will send a notification to any configured channels when
        a review is published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the review.

            review (reviewboard.reviews.models.Review):
                The review that was published.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
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
            issue_text = '%d issues' % open_issues

        user_link = self.get_user_text_link(user,
                                            review.review_request.local_site)
        pre_text = 'New review from %s' % user_link

        # There doesn't seem to be any image support inside the text fields,
        # but the :white_check_mark: emoji shows a green box with a check-mark
        # in it, and the :warning: emoji is a yellow exclamation point, which
        # are close enough.
        if review.ship_it:
            if open_issues:
                fields = [{
                    'title': 'Fix it, then Ship it!',
                    'value': ':warning: %s' % issue_text,
                    'short': True,
                }]
                extra_text = ' (Fix it, then Ship it!)'
                color = 'warning'
            else:
                fields = [{
                    'title': 'Ship it!',
                    'value': ':white_check_mark:',
                    'short': True,
                }]
                extra_text = ' (Ship it!)'
                color = 'good'
        elif open_issues:
            fields = [{
                'title': 'Open Issues',
                'value': ':warning: %s' % issue_text,
                'short': True,
            }]
            extra_text = ' (%s)' % issue_text
            color = 'warning'
        else:
            fields = []
            extra_text = ''
            color = None

        fallback_text = 'New review from %s%s' % (
            user_displayname(user), extra_text)

        self.notify_review_or_reply(user=user,
                                    review=review,
                                    pre_text=pre_text,
                                    fallback_text=fallback_text,
                                    first_comment=first_comment,
                                    fields=fields,
                                    color=color,
                                    event_name='review_published')

    def _on_reply_published(self, user, reply, **kwargs):
        """Handler for when a reply to a review is published.

        This will send a notification to any configured channels when
        a reply to a review is published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the reply.

            review (reviewboard.reviews.models.Review):
                The reply that was published.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        user_link = self.get_user_text_link(user,
                                            reply.review_request.local_site)
        pre_text = 'New reply from %s' % user_link
        fallback_text = 'New reply from %s' % user_displayname(user)

        self.notify_review_or_reply(user=user,
                                    review=reply,
                                    fallback_text=fallback_text,
                                    pre_text=pre_text,
                                    event_name='reply_published')
