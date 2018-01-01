"""Integration with I Done This."""

from __future__ import unicode_literals

import json
import logging

from django.utils.functional import cached_property
from django.utils.six.moves.urllib.error import HTTPError, URLError
from django.utils.six.moves.urllib.request import urlopen
from django.utils.translation import ugettext_lazy as _
from reviewboard.admin.server import build_server_url
from reviewboard.extensions.hooks import AccountPagesHook, SignalHook
from reviewboard.integrations import Integration
from reviewboard.reviews.models import BaseComment, ReviewRequest
from reviewboard.reviews.signals import (review_request_closed,
                                         review_request_published,
                                         review_request_reopened,
                                         review_published,
                                         reply_published)

from rbintegrations.idonethis import entries
from rbintegrations.idonethis.forms import IDoneThisIntegrationConfigForm
from rbintegrations.idonethis.pages import IDoneThisIntegrationAccountPage
from rbintegrations.idonethis.utils import (create_idonethis_request,
                                            get_user_api_token,
                                            get_user_team_ids)


class IDoneThisIntegration(Integration):
    """Integrates Review Board with I Done This.

    This integration allows posting 'done' entries to I Done This teams on
    behalf of users when they publish, change, or close a review request, and
    when they publish reviews or replies.

    I Done This entries are plain text, with #tags (used for group names)
    and @mentions (unused; only I Done This admins can configure them).
    URLs inside entries shown on the I Done This website are also
    automatically linked with truncated URL text.
    """

    name = _('I Done This')
    description = _(
        'Posts on behalf of users to I Done This teams when review requests '
        'are created, updated, and reviewed.'
    )

    default_settings = {
        'team_id': '',
    }

    config_form_cls = IDoneThisIntegrationConfigForm

    def initialize(self):
        """Initialize the integration hooks."""
        AccountPagesHook(self, [IDoneThisIntegrationAccountPage])

        hooks = (
            (review_request_closed, self._on_review_request_closed),
            (review_request_published, self._on_review_request_published),
            (review_request_reopened, self._on_review_request_reopened),
            (review_published, self._on_review_published),
            (reply_published, self._on_reply_published),
        )

        for signal, handler in hooks:
            SignalHook(self, signal, handler)

    @cached_property
    def icon_static_urls(self):
        """The icons used for the integration."""
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/idonethis/icon.png'),
            '2x': extension.get_static_url('images/idonethis/icon@2x.png'),
        }

    def post_entry(self, entry_type, user, review_request, signal_name,
                   url=None, num_issues=0):
        """Post a 'done' entry to I Done This teams.

        Posts the specified entry to any configured teams that the user
        belongs to.

        Args:
            entry_type (unicode):
                Entry type from :py:mod:`rbintegrations.idonethis.entries` to
                post.

            user (django.contrib.auth.models.User):
                The user who updated the review request. Entries are only
                posted if the user has specified an API token for I Done This,
                and is a member of the configured teams.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request the notification is bound to.

            signal_name (unicode):
                The name of the signal triggering this notification.

            url (unicode, optional):
                URL to show in the entry instead of the review request URL.

            num_issues (int, optional):
                Number of issues opened in a review.
        """
        if not (review_request.public and user and user.is_active):
            return

        api_token = get_user_api_token(user)

        if not api_token:
            return

        user_team_ids = None

        for config in self.get_configs(review_request.local_site):
            if not config.match_conditions(form_cls=self.config_form_cls,
                                           review_request=review_request):
                continue

            # Lazy load team IDs after the first matching configuration.
            if user_team_ids is None:
                user_team_ids = get_user_team_ids(user)

            if not user_team_ids:
                # We finished posting to all of the user's teams, the request
                # to get the teams failed, or the user is not in any team.
                return

            team_id = config.get('team_id')

            if not team_id or team_id not in user_team_ids:
                continue

            # Avoid posting duplicate entries to the same team from multiple
            # matching configurations.
            user_team_ids.remove(team_id)

            template_string = entries.default_template_strings[entry_type]

            entry_body = entries.format_template_string(
                template_string=template_string,
                num_issues=num_issues,
                review_request=review_request,
                url=url)

            json_payload = json.dumps({
                'body': entry_body,
                'team_id': team_id,
                'status': 'done',
                # Optional 'occurred_on' is automatically set by I Done This.
            })

            request = create_idonethis_request(request_path='entries',
                                               api_token=api_token,
                                               json_payload=json_payload)
            logging.debug('IDoneThis: Posting entry "%s" for signal "%s", '
                          'review_request ID %d, user "%s" to team "%s", '
                          'request "%s %s"',
                          entry_type,
                          signal_name,
                          review_request.pk,
                          user.username,
                          team_id,
                          request.get_method(),
                          request.get_full_url())

            try:
                urlopen(request)
            except (HTTPError, URLError) as e:
                # TODO: record failure in user settings and possibly notify the
                # user on the account page so that problems can be noticed.
                if isinstance(e, HTTPError):
                    error_info = '%s, error data: %s' % (e, e.read())
                else:
                    error_info = e.reason

                logging.error('IDoneThis: Failed to post entry for user "%s" '
                              'to team "%s", request "%s %s": %s',
                              user.username,
                              team_id,
                              request.get_method(),
                              request.get_full_url(),
                              error_info)

    def _on_review_request_closed(self, user, review_request, close_type,
                                  **kwargs):
        """Handler for when review requests are closed.

        Posts an entry to any configured I Done This teams when a review
        request is closed.

        Args:
            user (django.contrib.auth.models.User):
                The user who closed the review request.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request that was closed.

            close_type (unicode):
                The close type. Must be either ReviewRequest.DISCARDED or
                ReviewRequest.SUBMITTED.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        if close_type == ReviewRequest.DISCARDED:
            entry_type = entries.REVIEW_REQUEST_DISCARDED
        else:
            entry_type = entries.REVIEW_REQUEST_COMPLETED

        self.post_entry(entry_type=entry_type,
                        user=user,
                        review_request=review_request,
                        signal_name='review_request_closed')

    def _on_review_request_published(self, user, review_request, changedesc,
                                     **kwargs):
        """Handler for when review requests are published.

        Posts an entry to any configured I Done This teams when a review
        request is published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the review request.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request that was published.

            changedesc (reviewboard.changedescs.models.ChangeDescription):
                The change description for the update, if any.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        if not changedesc:
            entry_type = entries.REVIEW_REQUEST_PUBLISHED
        elif ('status' in changedesc.fields_changed and
              changedesc.fields_changed['status']['new'][0] ==
                ReviewRequest.PENDING_REVIEW):
            entry_type = entries.REVIEW_REQUEST_REOPENED
        else:
            entry_type = entries.REVIEW_REQUEST_UPDATED

        self.post_entry(entry_type=entry_type,
                        user=user,
                        review_request=review_request,
                        signal_name='review_request_published')

    def _on_review_request_reopened(self, user, review_request, **kwargs):
        """Handler for when review requests are reopened.

        Posts an entry to any configured I Done This teams when a review
        request is reopened.

        Args:
            user (django.contrib.auth.models.User):
                The user who reopened the review request.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request that was reopened.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        self.post_entry(entry_type=entries.REVIEW_REQUEST_REOPENED,
                        user=user,
                        review_request=review_request,
                        signal_name='review_request_reopened')

    def _on_review_published(self, user, review, to_owner_only, **kwargs):
        """Handler for when a review is published.

        Posts an entry to any configured I Done This teams when a review is
        published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the review.

            review (reviewboard.reviews.models.review.Review):
                The review that was published.

            to_owner_only (boolean):
                Whether the review should be sent only to the review request
                owner.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        if to_owner_only:
            return

        num_issues = 0

        for comment in review.get_all_comments():
            if (comment.issue_opened and
                comment.issue_status == BaseComment.OPEN):
                num_issues += 1

        if review.ship_it:
            if num_issues == 0:
                entry_type = entries.REVIEW_PUBLISHED_SHIPIT
            elif num_issues == 1:
                entry_type = entries.REVIEW_PUBLISHED_SHIPIT_ISSUE
            else:
                entry_type = entries.REVIEW_PUBLISHED_SHIPIT_ISSUES
        else:
            if num_issues == 0:
                entry_type = entries.REVIEW_PUBLISHED
            elif num_issues == 1:
                entry_type = entries.REVIEW_PUBLISHED_ISSUE
            else:
                entry_type = entries.REVIEW_PUBLISHED_ISSUES

        self.post_entry(entry_type=entry_type,
                        user=user,
                        review_request=review.review_request,
                        signal_name='review_published',
                        url=build_server_url(review.get_absolute_url()),
                        num_issues=num_issues)

    def _on_reply_published(self, user, reply, **kwargs):
        """Handler for when a reply to a review is published.

        Posts an entry to any configured I Done This teams when a reply to a
        review is published.

        Args:
            user (django.contrib.auth.models.User):
                The user who published the reply.

            reply (reviewboard.reviews.models.review.Review):
                The reply that was published.

            **kwargs (dict):
                Additional keyword arguments passed to the handler.
        """
        self.post_entry(entry_type=entries.REPLY_PUBLISHED,
                        user=user,
                        review_request=reply.review_request,
                        signal_name='reply_published',
                        url=build_server_url(reply.get_absolute_url()))
