"""Unit tests for the Microsoft Teams integration.

Version Added:
    4.0
"""

from __future__ import annotations

import json
from typing import List, Optional, TYPE_CHECKING
from urllib.request import urlopen

import kgb
from django.contrib.auth.models import User
from djblets.conditions import ConditionSet, Condition
from djblets.testing.decorators import add_fixtures
from reviewboard.accounts.trophies import TrophyType, trophies_registry
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.models import ReviewRequestDraft

from rbintegrations.msteams.integration import MSTeamsIntegration
from rbintegrations.testing.testcases import IntegrationTestCase

if TYPE_CHECKING:
    from djblets.integrations.models import BaseIntegrationConfig
    from djblets.util.typing import JSONDict


class MSTeamsIntegrationTests(IntegrationTestCase):
    """Tests Review Board integration with Microsoft Teams.

    Version Added:
        4.0
    """

    integration_cls = MSTeamsIntegration
    fixtures = ['test_scmtools', 'test_users']

    def setUp(self) -> None:
        super(MSTeamsIntegrationTests, self).setUp()

        self.user = User.objects.create(username='test',
                                        first_name='Test',
                                        last_name='User')

        self.spy_on(urlopen, call_original=False)
        self.spy_on(self.integration.notify)

    def test_notify_new_review_request(self) -> None:
        """Testing MSIntegration notifies on new review request"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=False)

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    @add_fixtures(['test_site'])
    def test_notify_new_review_request_with_local_site(self) -> None:
        """Testing MSTeamsIntegration notifies on new review request
        with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            target_people=[self.user],
            publish=False)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from [Test User]'
                     '(http://example.com/s/local-site-1/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/s/local-site-1/r/1/)',
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_new_review_request_with_diff(self) -> None:
        """Testing MSTeamsIntegration notifies on new review request
        with diff
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)
        self.create_diffset(review_request)

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Diff',
                    'value': '[Revision 1](http://example.com/r/1/diff/1/)',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    @add_fixtures(['test_site'])
    def test_notify_new_review_request_with_local_site_and_diff(self) -> None:
        """Testing MSTeamsIntegration notifies on new review request
        with local site and diff
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            publish=False)
        self.create_diffset(review_request)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from [Test User]'
                     '(http://example.com/s/local-site-1/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/s/local-site-1/r/1/)',
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Diff',
                    'value': '[Revision 1]'
                             '(http://example.com/s/local-site-1/r/1/diff/1/)',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_new_review_request_with_image_file_attachment(
        self,
    ) -> None:
        """Testing MSTeamsIntegration notifies on new review request
        with image file attachment
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=False)
        attachment = self.create_file_attachment(review_request)

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
            image_url=attachment.get_absolute_url(),
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_new_review_request_with_invalid_file_attachment(
        self,
    ) -> None:
        """Testing MSTeamsIntegration doesn't include an image url
        for a review request that has a file attachment with an invalid
        file extension
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=False)
        self.create_file_attachment(
            review_request,
            mimetype='text/plain',
            orig_filename='foo.txt')

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_new_review_request_with_fish_trophy(self) -> None:
        """Testing MSTeamsIntegration notifies on new review request
        with fish trophy
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=False,
            id=12321)

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#12321: Test Review Request]'
                  '(http://example.com/r/12321/)',
            thumb_url=self.integration.trophy_urls['fish'],
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_new_review_request_with_milestone_trophy(self) -> None:
        """Testing MSTeamsIntegration notifies on new review request
        with milestone trophy
        """
        review_request = self.create_review_request(
            create_repository=True,
            id=10000,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#10000: Test Review Request]'
                  '(http://example.com/r/10000/)',
            thumb_url=self.integration.trophy_urls['milestone'],
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_new_review_request_with_custom_trophy(self) -> None:
        """Testing MSTeamsIntegration notifies on new review request
        with ignored custom trophy
        """
        class MyTrophy(TrophyType):
            category = 'test'

            def __init__(self) -> None:
                super(MyTrophy, self).__init__(title='My Trophy',
                                               image_url='blahblah')

            def qualifies(self, review_request):
                return True

        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)

        self._create_config()
        self.integration.enable_integration()

        trophies_registry.register(MyTrophy)

        try:
            review_request.publish(self.user)
        finally:
            trophies_registry.unregister(MyTrophy)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_updated_review_request(self) -> None:
        """Testing MSTeamsIntegration notifies on updated review
        request"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=True)

        draft = ReviewRequestDraft.create(review_request)
        draft.summary = 'My new summary'
        draft.description = 'My new description'
        draft.save()

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New update from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: My new summary](http://example.com/r/1/)',
            fields=[
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_updated_review_request_with_change_description(
        self,
    ) -> None:
        """Testing MSTeamsIntegration notifies on updated review request
        with change description
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=True)

        draft = ReviewRequestDraft.create(review_request)
        draft.summary = 'My new summary'
        draft.description = 'My new description'
        draft.save()

        changedesc = draft.changedesc
        changedesc.text = 'These are my changes.'
        changedesc.save()

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New update from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: My new summary](http://example.com/r/1/)',
            body='These are my changes.',
            fields=[
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_updated_review_request_with_new_image_attachments(
        self,
    ) -> None:
        """Testing MSTeamsIntegration notifies on updated review
        request with new image attachments
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            target_people=[self.user],
            publish=False)
        self.create_file_attachment(review_request)
        review_request.publish(self.user)

        attachment = self.create_file_attachment(review_request,
                                                 caption='My new attachment',
                                                 draft=True)

        self._create_config()
        self.integration.enable_integration()

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New update from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
            image_url=attachment.get_absolute_url(),
            fields=[
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def test_notify_closed_review_request_as_submitted(self) -> None:
        """Testing MSTeamsIntegration notifies on closing review
        request as submitted
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=True)

        self._create_config()
        self.integration.enable_integration()

        review_request.close(review_request.SUBMITTED)

        self._check_notify_request(
            pre_text='Closed as completed by '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
        )

    def test_notify_closed_review_request_as_discarded(self) -> None:
        """Testing MSTeamsIntegration notifies on closing review
        request as discarded
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=True)

        self._create_config()
        self.integration.enable_integration()

        review_request.close(review_request.DISCARDED)

        self._check_notify_request(
            pre_text='Discarded by '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
        )

    @add_fixtures(['test_site'])
    def test_notify_closed_review_request_with_local_site(self) -> None:
        """Testing MSTeamsIntegration notifies on closing review
        request with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            publish=True)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        review_request.close(review_request.SUBMITTED)

        self._check_notify_request(
            pre_text='Closed as completed by [Test User]'
                     '(http://example.com/s/local-site-1/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/s/local-site-1/r/1/)',
        )

    def test_notify_reopened_review_request(self) -> None:
        """Testing MSTeamsIntegration notifies on reopened review
        request
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=True)
        review_request.close(review_request.SUBMITTED)

        self._create_config()
        self.integration.enable_integration()

        review_request.reopen(self.user)

        self._check_notify_request(
            pre_text='Reopened by '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request](http://example.com/r/1/)',
            body='My description.',
        )

    @add_fixtures(['test_site'])
    def test_notify_reopened_review_request_with_local_site(self) -> None:
        """Testing MSTeamsIntegration notifies on reopened review
        request with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            with_local_site=True,
            local_id=1,
            publish=True)
        review_request.close(review_request.SUBMITTED)

        review_request.local_site.users.add(self.user)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        review_request.reopen(self.user)

        self._check_notify_request(
            pre_text='Reopened by [Test User]'
                     '(http://example.com/s/local-site-1/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/s/local-site-1/r/1/)',
            body='My description.',
        )

    def test_notify_new_review_with_body_top(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with
        body_top
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    body_top='This is my review.')
        self.create_general_comment(review)

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='This is my review.'
        )

    @add_fixtures(['test_site'])
    def test_notify_new_review_with_local_site(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with local
        site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)

        review_request.local_site.users.add(self.user)

        review = self.create_review(review_request,
                                    user=self.user,
                                    body_top='This is my review.')
        self.create_general_comment(review)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from [Test User]'
                     '(http://example.com/s/local-site-1/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/s/local-site-1/r/1/#review1)',
            body='This is my review.'
        )

    def test_notify_new_review_with_comments(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with only
        comments
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request, user=self.user,
                                    body_top='')
        self.create_general_comment(review, text='My general comment.')

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='My general comment.'
        )

    def test_notify_new_review_with_one_open_issue(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with 1 open
        issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request, user=self.user,
                                    body_top='')
        self.create_general_comment(review, text='My general comment.',
                                    issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='My general comment.',
            fields=[
                {
                    'title': 'Open Issues',
                    'value': '⚠ 1 issue',
                },
            ],
        )

    def test_notify_new_review_with_open_issues(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with > 1
        open issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request, user=self.user,
                                    body_top='')
        self.create_general_comment(review, text='My general comment 1.',
                                    issue_opened=True)
        self.create_general_comment(review, text='My general comment 2.',
                                    issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='My general comment 1.',
            fields=[
                {
                    'title': 'Open Issues',
                    'value': '⚠ 2 issues',
                },
            ],
        )

    def test_notify_new_review_with_ship_it(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with
        Ship It!
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='Ship It!')

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='Test Body Bottom',
            fields=[
                {
                    'title': 'Ship it!',
                    'value': '✅',
                },
            ],
        )

    def test_notify_new_review_with_ship_it_and_custom_body_top(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with Ship
        It and custom body_top
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='This is body_top.')
        self.create_general_comment(review)

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='This is body_top.',
            fields=[
                {
                    'title': 'Ship it!',
                    'value': '✅',
                },
            ],
        )

    def test_notify_new_review_with_ship_it_and_one_open_issue(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with Ship
        It! and 1 open issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='Ship It!')
        self.create_general_comment(review, issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='My comment',
            fields=[
                {
                    'title': 'Fix it, then Ship it!',
                    'value': '⚠ 1 issue',
                },
            ],
        )

    def test_notify_new_review_with_ship_it_and_open_issues(self) -> None:
        """Testing MSTeamsIntegration notifies on new review with Ship
        It! and > 1 open issues
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True,
                                    body_top='Ship It!')
        self.create_general_comment(review, text='My general comment 1.',
                                    issue_opened=True)
        self.create_general_comment(review, text='My general comment 2.',
                                    issue_opened=True)

        self._create_config()
        self.integration.enable_integration()

        review.publish()

        self._check_notify_request(
            pre_text='New review from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review1)',
            body='My general comment 1.',
            fields=[
                {
                    'title': 'Fix it, then Ship it!',
                    'value': '⚠ 2 issues',
                },
            ],
        )

    def test_notify_new_reply_with_body_top(self) -> None:
        """Testing MSTeamsIntegration notifies on new reply with
        body_top
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review,
                                  user=self.user,
                                  body_top='This is body_top.')
        self.create_general_comment(reply,
                                    text='This is a comment.',
                                    reply_to=comment)

        self._create_config()
        self.integration.enable_integration()

        reply.publish()

        self._check_notify_request(
            pre_text='New reply from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review2)',
            body='This is body_top.',
        )

    @add_fixtures(['test_site'])
    def test_notify_new_reply_with_local_site(self) -> None:
        """Testing MSTeamsIntegration notifies on new reply with local
        site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)

        review_request.local_site.users.add(self.user)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review,
                                  user=self.user,
                                  body_top='This is body_top.')
        self.create_general_comment(reply,
                                    text='This is a comment.',
                                    reply_to=comment)

        self._create_config(with_local_site=True)
        self.integration.enable_integration()

        reply.publish()

        self._check_notify_request(
            pre_text='New reply from [Test User]'
                     '(http://example.com/s/local-site-1/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/s/local-site-1/r/1/#review2)',
            body='This is body_top.',
        )

    def test_notify_new_reply_with_comment(self) -> None:
        """Testing MSTeamsIntegration notifies on new reply with
        comment
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review, user=self.user, body_top='')
        self.create_general_comment(reply,
                                    text='This is a comment.',
                                    reply_to=comment)

        self._create_config()
        self.integration.enable_integration()

        reply.publish()

        self._check_notify_request(
            pre_text='New reply from '
                     '[Test User](http://example.com/users/test/)',
            title='[\\#1: Test Review Request]'
                  '(http://example.com/r/1/#review2)',
            body='This is a comment.',
        )

    def test_notify_with_no_webhook_url(self) -> None:
        """Testing MSTeamsIntegration logs an error when attempting to send
        a notification when no webhook URL is configured
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            description='My description.',
            publish=False)

        config = self._create_config()
        config.set('webhook_url', None)
        config.save()
        self.integration.enable_integration()

        with self.assertLogs() as logs:
            review_request.publish(self.user)

            self.assertEqual(
                logs.records[0].getMessage(),
                'Failed to send notification: '
                'WebHook URL has not been configured.')

    def test_notify_new_review_request_escaped_markdown(self) -> None:
        """Testing MSIntegration escapes markdown characters in its
        notification
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            # This would break a Markdown link.
            summary='Test](Foo)',
            description='My description.',
            target_people=[self.user],
            publish=False)

        self._create_config()
        self.integration.enable_integration()

        # This would break a Markdown link.
        self.spy_on(
            self.integration.get_user_text_url,
            op=kgb.SpyOpReturn('http://example.com/users/test?val=)&foo=(1)'))

        review_request.publish(self.user)

        self._check_notify_request(
            pre_text='New review request from '
                     '[Test User](http://example.com/users/test?'
                     'val=%29&foo=%281%29)',
            title='[\\#1: Test\\](Foo)](http://example.com/r/1/)',
            fields=[
                {
                    'title': 'Description',
                    'value': 'My description.',
                },
                {
                    'title': 'Repository',
                    'value': 'Test Repo',
                },
                {
                    'title': 'Branch',
                    'value': 'my-branch',
                },
            ],
        )

    def _create_config(
        self,
        with_local_site: bool = False
    ) -> BaseIntegrationConfig:
        """Set configuration values for MSTeamsIntegration.

        Args:
            with_local_site (bool, optional):
                Whether the configuration should be for a local site.

        Returns:
            djblets.integrations.models.BaseIntegrationConfig:
            The configuration for the integration.
        """
        choice = ReviewRequestRepositoriesChoice()

        condition_set = ConditionSet(conditions=[
            Condition(choice=choice,
                      operator=choice.get_operator('any')),
        ])

        if with_local_site:
            local_site = self.get_local_site(name=self.local_site_name)
        else:
            local_site = None

        config = self.integration.create_config(name='Config 1',
                                                enabled=True,
                                                local_site=local_site)
        config.set('notify_username', 'RB User')
        config.set('webhook_url', 'http://example.com/msteams-url/')
        config.set('conditions', condition_set.serialize())
        config.save()

        return config

    def _check_notify_request(
        self,
        *,
        pre_text,
        title,
        body: str = '',
        fields: Optional[List[JSONDict]] = None,
        thumb_url: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> None:
        """Check that a notify and HTTP request meets expected criteria.

        This will ensure that only a single request was invoked, and that the
        request information contains the appropriate headers, string types,
        and payload message content.

        Args:
            pre_text (str):
                The expected text to display before the rest of the message.

            title (str):
                The expected title of the message.

            body (str, optional):
                The expected body of the message.

            fields (list of djblets.util.typing.JSONDict):
                The expected fields to display in the message.

            thumb_url (str, optional):
                Expected URL of an image to show on the side of the message.

            image_url (str, optional):
                Expected URL of an image to show in the message.

        Raises:
            AssertionError:
                One or more of the checks failed.
        """
        pre_text_card = {
            'type': 'ColumnSet',
            'columns': [
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
        }

        if thumb_url:
            pre_text_card['columns'].append({
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

        activity_card = {
            'type': 'ColumnSet',
            'columns': [
                {
                    'type': 'Column',
                    'width': 'Auto',
                    'items': [
                        {
                            'type': 'Image',
                            'url': self.integration.logo_url,
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
                            'text': title,
                            'weight': 'Bolder',
                            'wrap': True,
                        },
                        {
                            'type': 'TextBlock',
                            'text': body,
                            'isSubtle': True,
                            'spacing': 'Small',
                            'wrap': True,
                        },
                    ]
                },
            ]
        }

        main_body = [
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

        request = urlopen.last_call.args[0]
        request_body = request.data
        headers = request.headers

        self.assertSpyCallCount(self.integration.notify, 1)
        self.assertSpyCallCount(urlopen, 1)
        self.assertIsInstance(request_body, bytes)
        self.assertEqual(headers['Content-length'], str(len(request_body)))
        self.assertEqual(headers['Content-type'], str('application/json'))
        self.assertEqual(
            json.loads(request_body.decode('utf-8')),
            {
                'type': 'message',
                'attachments': [
                    {
                        'contentType':
                            'application/vnd.microsoft.card.adaptive',
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
            })
