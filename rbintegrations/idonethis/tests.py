"""Unit tests for I Done This integration."""

from __future__ import unicode_literals

import json
import logging

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory
from django.utils.six.moves import cStringIO as StringIO
from django.utils.six.moves.urllib.error import HTTPError, URLError
from django.utils.six.moves.urllib.request import urlopen
from djblets.cache.backend import cache_memoize, make_cache_key
from djblets.conditions import ConditionSet, Condition
from djblets.testing.decorators import add_fixtures
from reviewboard.reviews.conditions import ReviewRequestRepositoriesChoice
from reviewboard.reviews.models import ReviewRequestDraft
from reviewboard.scmtools.crypto_utils import (decrypt_password,
                                               encrypt_password)

from rbintegrations.idonethis.forms import (
    IDoneThisIntegrationAccountPageForm,
    IDoneThisIntegrationConfigForm)
from rbintegrations.idonethis.integration import IDoneThisIntegration
from rbintegrations.idonethis.utils import get_user_team_ids
from rbintegrations.testing.testcases import IntegrationTestCase


class IDoneThisIntegrationTests(IntegrationTestCase):
    """Test posting of I Done This entries with review request activity."""

    integration_cls = IDoneThisIntegration

    fixtures = ['test_scmtools', 'test_users']

    def setUp(self):
        """Set up this test case."""
        super(IDoneThisIntegrationTests, self).setUp()

        self.user = User.objects.create_user(username='testuser')
        self.team_ids_cache_key = make_cache_key('idonethis-team_ids-testuser')
        self.profile = self.user.get_profile()
        self.profile.settings['idonethis'] = {
            'api_token': encrypt_password('tok123'),
        }

    def test_post_review_request_closed_completed(self):
        """Testing IDoneThisIntegration posts on review request closed as
        completed
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        request = urlopen.spy.calls[0].args[0]
        self.assertEqual(request.get_full_url(),
                         'https://beta.idonethis.com/api/v2/entries')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Authorization'), 'Token tok123')

        self.assertEqual(
            json.loads(request.data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_request_closed_completed_with_local_site(self):
        """Testing IDoneThisIntegration posts on review request closed as
        completed with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)
        review_request.local_site.users.add(self.user)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)


        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/s/local-site-1/r/1/ #group',
            })

    def test_post_review_request_closed_discarded(self):
        """Testing IDoneThisIntegration posts on review request closed as
        discarded
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.DISCARDED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)


        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Discarded review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_request_closed_discarded_with_local_site(self):
        """Testing IDoneThisIntegration posts on review request closed as
        discarded with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)
        review_request.local_site.users.add(self.user)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.DISCARDED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)


        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Discarded review request 1: Test Review Request '
                        'http://example.com/s/local-site-1/r/1/ #group',
            })

    def test_post_review_request_published_normal(self):
        """Testing IDoneThisIntegration posts on review request published"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=False)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.publish(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Published review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_request_published_normal_with_local_site(self):
        """Testing IDoneThisIntegration posts on review request published with
        local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=False)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)
        review_request.local_site.users.add(self.user)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.publish(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)


        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Published review request 1: Test Review Request '
                        'http://example.com/s/local-site-1/r/1/ #group',
            })

    def test_post_review_request_published_reopen(self):
        """Testing IDoneThisIntegration posts on review request published after
        discard and reopen
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review_request.close(review_request.DISCARDED)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.reopen(self.user)

        # Reopened discarded review is not public until publish,
        # so post_entry should not post.
        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 0)

        review_request.publish(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 2)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Reopened review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_request_published_reopen_with_local_site(self):
        """Testing IDoneThisIntegration posts on review request published after
        discard and reopen with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)
        review_request.local_site.users.add(self.user)

        review_request.close(review_request.DISCARDED)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.reopen(self.user)

        # Reopened discarded review is not public until publish,
        # so post_entry should not post.
        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 0)

        review_request.publish(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 2)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Reopened review request 1: Test Review Request '
                        'http://example.com/s/local-site-1/r/1/ #group',
            })

    def test_post_review_request_published_update(self):
        """Testing IDoneThisIntegration posts on review request published after
        update
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        draft = ReviewRequestDraft.create(review_request)
        draft.summary = 'My new summary'
        draft.description = 'My new description'
        draft.save()

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.publish(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Updated review request 1: My new summary '
                        'http://example.com/r/1/ #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_request_published_update_with_local_site(self):
        """Testing IDoneThisIntegration posts on review request published after
        update with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)
        review_request.local_site.users.add(self.user)

        draft = ReviewRequestDraft.create(review_request)
        draft.summary = 'My new summary'
        draft.description = 'My new description'
        draft.save()

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.publish(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Updated review request 1: My new summary '
                        'http://example.com/s/local-site-1/r/1/ #group',
            })

    def test_post_review_request_reopened(self):
        """Testing IDoneThisIntegration posts on review request reopened after
        after submit
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review_request.close(review_request.SUBMITTED)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.reopen(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Reopened review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_request_reopened_with_local_site(self):
        """Testing IDoneThisIntegration posts on review request reopened after
        submit with local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)
        review_request.local_site.users.add(self.user)

        review_request.close(review_request.SUBMITTED)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.reopen(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Reopened review request 1: Test Review Request '
                        'http://example.com/s/local-site-1/r/1/ #group',
            })

    def test_post_review_published_with_0_issues(self):
        """Testing IDoneThisIntegration posts on review published with no open
        issues
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review = self.create_review(review_request, user=self.user)
        self.create_general_comment(review)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted review on review request 1: '
                        'Test Review Request '
                        'http://example.com/r/1/#review1 #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_published_with_0_issues_local_site(self):
        """Testing IDoneThisIntegration posts on review published with no open
        issues and local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)

        review = self.create_review(review_request, user=self.user)
        self.create_general_comment(review)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted review on review request 1: '
                        'Test Review Request '
                        'http://example.com/s/local-site-1/r/1/#review1 '
                        '#group',
            })

    def test_post_review_published_with_1_issue(self):
        """Testing IDoneThisIntegration posts on review published with 1 open
        issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review = self.create_review(review_request, user=self.user)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted review (1 issue) on review request 1: '
                        'Test Review Request '
                        'http://example.com/r/1/#review1 #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_published_with_1_issue_local_site(self):
        """Testing IDoneThisIntegration posts on review published with 1 open
        issue and local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)

        review = self.create_review(review_request, user=self.user)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted review (1 issue) on review request 1: '
                        'Test Review Request '
                        'http://example.com/s/local-site-1/r/1/#review1 '
                        '#group',
            })

    def test_post_review_published_with_2_issues(self):
        """Testing IDoneThisIntegration posts on review published with > 1 open
        issues
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review = self.create_review(review_request, user=self.user)
        self.create_general_comment(review, issue_opened=True)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted review (2 issues) on review request 1: '
                        'Test Review Request '
                        'http://example.com/r/1/#review1 #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_published_with_2_issues_local_site(self):
        """Testing IDoneThisIntegration posts on review published with > 1 open
        issues and local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)

        review = self.create_review(review_request, user=self.user)
        self.create_general_comment(review, issue_opened=True)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted review (2 issues) on review request 1: '
                        'Test Review Request '
                        'http://example.com/s/local-site-1/r/1/#review1 '
                        '#group',
            })

    def test_post_review_published_with_shipit_0_issues(self):
        """Testing IDoneThisIntegration posts on review published with Ship it!
        and no open issues
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True)
        self.create_general_comment(review)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted Ship it! on review request 1: '
                        'Test Review Request '
                        'http://example.com/r/1/#review1 #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_published_with_shipit_0_issues_local_site(self):
        """Testing IDoneThisIntegration posts on review published with Ship it!
        and no open issues and local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True)
        self.create_general_comment(review)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted Ship it! on review request 1: '
                        'Test Review Request '
                        'http://example.com/s/local-site-1/r/1/#review1 '
                        '#group',
            })

    def test_post_review_published_with_shipit_1_issue(self):
        """Testing IDoneThisIntegration posts on review published with Ship it!
        and 1 open issue
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted Ship it! (1 issue) on review request 1: '
                        'Test Review Request '
                        'http://example.com/r/1/#review1 #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_published_with_shipit_1_issue_local_site(self):
        """Testing IDoneThisIntegration posts on review published with Ship it!
        and 1 open issue and local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted Ship it! (1 issue) on review request 1: '
                        'Test Review Request '
                        'http://example.com/s/local-site-1/r/1/#review1 '
                        '#group',
            })

    def test_post_review_published_with_shipit_2_issues(self):
        """Testing IDoneThisIntegration posts on review published with Ship it!
        and > 1 open issues
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True)
        self.create_general_comment(review, issue_opened=True)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted Ship it! (2 issues) on review request 1: '
                        'Test Review Request '
                        'http://example.com/r/1/#review1 #group',
            })

    @add_fixtures(['test_site'])
    def test_post_review_published_with_shipit_2_issues_local_site(self):
        """Testing IDoneThisIntegration posts on review published with Ship it!
        and > 1 open issues and local site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    ship_it=True)
        self.create_general_comment(review, issue_opened=True)
        self.create_general_comment(review, issue_opened=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Posted Ship it! (2 issues) on review request 1: '
                        'Test Review Request '
                        'http://example.com/s/local-site-1/r/1/#review1 '
                        '#group',
            })

    def test_post_reply_published(self):
        """Testing IDoneThisIntegration posts on reply published"""
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review, user=self.user)
        self.create_general_comment(reply, reply_to=comment)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        reply.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Replied to review request 1: Test Review Request '
                        'http://example.com/r/1/#review2 #group',
            })

    @add_fixtures(['test_site'])
    def test_post_reply_published_with_local_site(self):
        """Testing IDoneThisIntegration posts on reply published with local
        site
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            with_local_site=True,
            local_id=1,
            publish=True)
        group = self.create_review_group(name='group', with_local_site=True)
        review_request.target_groups.add(group)

        review = self.create_review(review_request,
                                    user=self.user,
                                    publish=True)
        comment = self.create_general_comment(review, issue_opened=True)

        reply = self.create_reply(review, user=self.user)
        self.create_general_comment(reply, reply_to=comment)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', with_local_site=True)
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        reply.publish()

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Replied to review request 1: Test Review Request '
                        'http://example.com/s/local-site-1/r/1/#review2 '
                        '#group',
            })

    def test_no_post_review_published_to_owner_only(self):
        """Testing IDoneThisIntegration doesn't post on review published to
        owner only
        """
        review_request = self.create_review_request(
            create_repository=True,
            summary='Test Review Request',
            publish=True)

        review = self.create_review(review_request, user=self.user)
        self.create_general_comment(review)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review.publish(to_owner_only=True)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 0)
        self.assertEqual(len(urlopen.spy.calls), 0)

    def test_no_post_without_user(self):
        """Testing IDoneThisIntegration doesn't post without a user"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(self.integration.get_configs)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(self.integration.get_configs.spy.calls), 0)
        self.assertEqual(len(urlopen.spy.calls), 0)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

    def test_no_post_with_inactive_user(self):
        """Testing IDoneThisIntegration doesn't post with inactive user"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        self.user.is_active = False

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(self.integration.get_configs)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(self.integration.get_configs.spy.calls), 0)
        self.assertEqual(len(urlopen.spy.calls), 0)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

    def test_no_post_without_api_token(self):
        """Testing IDoneThisIntegration doesn't post without an API Token"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        self.profile.settings['idonethis'] = {}

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(self.integration.get_configs)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(self.integration.get_configs.spy.calls), 0)
        self.assertEqual(len(urlopen.spy.calls), 0)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

    def test_no_post_without_matching_condition(self):
        """Testing IDoneThisIntegration doesn't post without a matching
        condition
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123', repository_operator='none')
        self._create_config(team_id='teamABC', repository_operator='none')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(get_user_team_ids)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(get_user_team_ids.spy.calls), 0)
        self.assertEqual(len(urlopen.spy.calls), 0)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

    def test_no_post_without_matching_team_id(self):
        """Testing IDoneThisIntegration doesn't post without a matching
        team ID
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123x')
        self._create_config(team_id='teamABCx')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(get_user_team_ids)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(get_user_team_ids.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 0)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

    def test_no_post_with_team_ids_error(self):
        """Testing IDoneThisIntegration doesn't post after error while
        requesting the user team IDs
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.assertNotIn(self.team_ids_cache_key, cache)

        self.spy_on(self.integration.post_entry)
        self.spy_on(get_user_team_ids)
        self.spy_on(urlopen, call_fake=_urlopen_raise_httperror)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(get_user_team_ids.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)
        self.assertEqual(urlopen.spy.calls[0].args[0].get_full_url(),
                         'https://beta.idonethis.com/api/v2/teams')

    def test_try_post_with_httperror(self):
        """Testing IDoneThisIntegration tries to post to multiple teams with
        HTTPError
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self._create_config(team_id='teamABC')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_fake=_urlopen_raise_httperror)
        self.spy_on(logging.error)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 2)
        self.assertEqual(len(logging.error.spy.calls), 2)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

    def test_try_post_with_urlerror(self):
        """Testing IDoneThisIntegration tries to post to multiple teams with
        URLError
        """
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self._create_config(team_id='teamABC')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_fake=_urlopen_raise_urlerror)
        self.spy_on(logging.error)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 2)
        self.assertEqual(len(logging.error.spy.calls), 2)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

    def test_post_to_multiple_teams(self):
        """Testing IDoneThisIntegration posts to multiple matched teams"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self._create_config(team_id='teamABC')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(get_user_team_ids)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(get_user_team_ids.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 2)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

        self.assertEqual(
            json.loads(urlopen.spy.calls[1].args[0].data),
            {
                'team_id': 'teamABC',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

    def test_post_once_to_duplicate_teams(self):
        """Testing IDoneThisIntegration posts once to duplicate teams"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='group')
        review_request.target_groups.add(group)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self._create_config(team_id='teamABC')
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(get_user_team_ids)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(get_user_team_ids.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 2)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

        self.assertEqual(
            json.loads(urlopen.spy.calls[1].args[0].data),
            {
                'team_id': 'teamABC',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/ #group',
            })

    def test_post_with_multiple_target_groups(self):
        """Testing IDoneThisIntegration posts with multiple target groups"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)
        group = self.create_review_group(name='groupA')
        review_request.target_groups.add(group)
        group = self.create_review_group(name='new group-B')
        review_request.target_groups.add(group)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/ #groupA #new_group_B',
            })

    def test_post_without_target_groups(self):
        """Testing IDoneThisIntegration posts without target groups"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/',
            })

    def test_post_with_extra_whitespace_removed(self):
        """Testing IDoneThisIntegration posts with extra whitespace removed"""
        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='    Test    Review     Request    ',
            publish=True)

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})
        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.spy_on(self.integration.post_entry)
        self.spy_on(urlopen, call_original=False)

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)

        self.assertEqual(
            json.loads(urlopen.spy.calls[0].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/',
            })

    def test_post_multiple_events_with_single_team_ids_request(self):
        """Testing IDoneThisIntegration posts multiple events with a single
        request for the user team IDs
        """
        def _urlopen(request, **kwargs):
            if request.get_full_url().endswith('/teams'):
                return StringIO(json.dumps([
                    {
                        'hash_id': 'team123',
                    },
                ]))

            return StringIO('')

        review_request = self.create_review_request(
            create_repository=True,
            submitter=self.user,
            summary='Test Review Request',
            publish=False)

        self._create_config(team_id='team123')
        self.integration.enable_integration()

        self.assertNotIn(self.team_ids_cache_key, cache)

        self.spy_on(self.integration.post_entry)
        self.spy_on(get_user_team_ids)
        self.spy_on(urlopen, call_fake=_urlopen)

        review_request.publish(self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 1)
        self.assertEqual(len(get_user_team_ids.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 2)

        self.assertIsNone(self.integration.post_entry.spy.calls[0].exception)
        self.assertEqual(urlopen.spy.calls[0].args[0].get_full_url(),
                         'https://beta.idonethis.com/api/v2/teams')

        self.assertIn(self.team_ids_cache_key, cache)
        self.assertEqual(cache.get(self.team_ids_cache_key), {'team123'})

        self.assertEqual(urlopen.spy.calls[1].args[0].get_full_url(),
                         'https://beta.idonethis.com/api/v2/entries')

        self.assertEqual(
            json.loads(urlopen.spy.calls[1].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Published review request 1: Test Review Request '
                        'http://example.com/r/1/',
            })

        review_request.close(review_request.SUBMITTED, self.user)

        self.assertEqual(len(self.integration.post_entry.spy.calls), 2)
        self.assertEqual(len(get_user_team_ids.spy.calls), 2)
        self.assertEqual(len(urlopen.spy.calls), 3)

        self.assertEqual(urlopen.spy.calls[2].args[0].get_full_url(),
                         'https://beta.idonethis.com/api/v2/entries')
        self.assertEqual(
            json.loads(urlopen.spy.calls[2].args[0].data),
            {
                'team_id': 'team123',
                'status': 'done',
                'body': 'Completed review request 1: Test Review Request '
                        'http://example.com/r/1/',
            })

    def _create_config(self,
                       team_id,
                       with_local_site=False,
                       repository_operator='any'):
        """Create an integration config with the given parameters.

        Args:
            team_id (unicode):
                The team ID to post entries to.

            with_local_site (boolean, optional):
                Whether the configuration should be for a local site.

            repository_operator (unicode, optional):
                Operator for a repository choice to satisfy the condition.
        """
        choice = ReviewRequestRepositoriesChoice()

        condition_set = ConditionSet(conditions=[
            Condition(choice=choice,
                      operator=choice.get_operator(repository_operator)),
        ])

        if with_local_site:
            local_site = self.get_local_site(name=self.local_site_name)
        else:
            local_site = None

        config = self.integration.create_config(name='Config %s' % team_id,
                                                enabled=True,
                                                local_site=local_site)
        config.set('team_id', team_id)
        config.set('conditions', condition_set.serialize())
        config.save()


class IDoneThisIntegrationFormTests(IntegrationTestCase):
    """Test the admin configuration and user account page forms."""

    integration_cls = IDoneThisIntegration

    def setUp(self):
        """Initialize this test case."""
        super(IDoneThisIntegrationFormTests, self).setUp()

        self.request = RequestFactory().get('test')
        self.user = User.objects.create_user(username='testuser')
        self.team_ids_cache_key = make_cache_key('idonethis-team_ids-testuser')
        self.profile = self.user.get_profile()

    def test_admin_clean_team_id_whitespace(self):
        """Testing IDoneThisIntegration admin form, cleaning team ID strips
        whitespace
        """
        form = IDoneThisIntegrationConfigForm(
            integration=self.integration,
            request=self.request,
            data={
                'team_id': '  team123  ',
            })

        self.spy_on(form.clean_team_id)

        form.full_clean()

        self.assertEqual(len(form.clean_team_id.spy.calls), 1)
        self.assertEqual(form.cleaned_data['team_id'], 'team123')

    def test_admin_clean_team_id_validation(self):
        """Testing IDoneThisIntegration admin form, cleaning team ID containing
        slash raises validation error
        """
        form = IDoneThisIntegrationConfigForm(integration=self.integration,
                                              request=self.request)
        form.cleaned_data = {
            'team_id': 't/team123',
        }

        self.assertRaisesValidationError(
            'Team ID cannot contain slashes.',
            form.clean_team_id)

    def test_user_clean_token_empty(self):
        """Testing IDoneThisIntegration user form, cleaning empty API token
        skips validation
        """
        form = IDoneThisIntegrationAccountPageForm(
            page=None,
            request=self.request,
            user=self.user,
            data={
                'idonethis_api_token': '   ',
            })

        self.spy_on(urlopen)
        self.spy_on(form.clean_idonethis_api_token)

        form.full_clean()

        self.assertEqual(len(urlopen.spy.calls), 0)
        self.assertEqual(len(form.clean_idonethis_api_token.spy.calls), 1)

        self.assertEqual(form.cleaned_data['idonethis_api_token'], '')

    def test_user_clean_token_validation_request(self):
        """Testing IDoneThisIntegration user form, cleaning API token strips
        whitespace and performs validation API request
        """
        form = IDoneThisIntegrationAccountPageForm(
            page=None,
            request=self.request,
            user=self.user,
            data={
                'idonethis_api_token': '  tok123  ',
            })

        self.spy_on(urlopen, call_original=False)
        self.spy_on(logging.error)
        self.spy_on(form.clean_idonethis_api_token)

        form.full_clean()

        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 0)
        self.assertEqual(len(form.clean_idonethis_api_token.spy.calls), 1)

        request = urlopen.spy.calls[0].args[0]
        self.assertEqual(request.get_full_url(),
                         'https://beta.idonethis.com/api/v2/noop')
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Authorization'), 'Token tok123')
        self.assertIsNone(request.data)

        self.assertEqual(form.cleaned_data['idonethis_api_token'], 'tok123')

    def test_user_clean_token_validation_httperror(self):
        """Testing IDoneThisIntegration user form, cleaning API token with
        HTTPError raises validation error
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)
        form.cleaned_data = {
            'idonethis_api_token': 'tok123',
        }

        self.spy_on(urlopen, call_fake=_urlopen_raise_httperror)
        self.spy_on(logging.error)

        self.assertRaisesValidationError(
            'Error validating the API Token. Make sure the token matches your '
            'I Done This Account Settings.',
            form.clean_idonethis_api_token)

        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 1)

    def test_user_clean_token_validation_urlerror(self):
        """Testing IDoneThisIntegration user form, cleaning API token with
        URLError raises validation error
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)
        form.cleaned_data = {
            'idonethis_api_token': 'tok123',
        }

        self.spy_on(urlopen, call_fake=_urlopen_raise_urlerror)
        self.spy_on(logging.error)

        self.assertRaisesValidationError(
            'Error validating the API Token. Make sure the token matches your '
            'I Done This Account Settings.',
            form.clean_idonethis_api_token)

        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 1)

    def test_user_load_token_empty(self):
        """Testing IDoneThisIntegration user form, loading empty API token
        when not in settings
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)

        self.spy_on(decrypt_password)

        form.load()

        self.assertEqual(len(decrypt_password.spy.calls), 0)

        self.assertIsNone(form.fields['idonethis_api_token'].initial)

    def test_user_load_token_decrypted(self):
        """Testing IDoneThisIntegration user form, loading decrypted API token
        from settings
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)
        self.profile.settings['idonethis'] = {
            'api_token': encrypt_password('tok123'),
        }

        self.spy_on(decrypt_password)

        form.load()

        self.assertEqual(len(decrypt_password.spy.calls), 1)

        self.assertEqual(form.fields['idonethis_api_token'].initial, 'tok123')

    def test_user_save_token_empty(self):
        """Testing IDoneThisIntegration user form, saving empty API token
        creates empty settings
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)
        form.cleaned_data = {
            'idonethis_api_token': '',
        }

        self.spy_on(encrypt_password)
        self.spy_on(self.profile.save)

        form.save()

        self.assertEqual(len(encrypt_password.spy.calls), 0)
        self.assertEqual(len(self.profile.save.spy.calls), 1)

        self.assertEqual(self.profile.settings['idonethis'], {})

    def test_user_save_token_empty_removes_old_token(self):
        """Testing IDoneThisIntegration user form, saving empty API token
        removes old token from settings and deletes cached team IDs
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)
        form.cleaned_data = {
            'idonethis_api_token': '',
        }
        self.profile.settings['idonethis'] = {
            'api_token': encrypt_password('tok123'),
            'other_key': 'other value',
        }

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})

        self.spy_on(encrypt_password)
        self.spy_on(self.profile.save)

        form.save()

        self.assertEqual(len(encrypt_password.spy.calls), 0)
        self.assertEqual(len(self.profile.save.spy.calls), 1)

        self.assertEqual(
            self.profile.settings['idonethis'],
            {
                'other_key': 'other value',
            })
        self.assertNotIn(self.team_ids_cache_key, cache)

    def test_user_save_token_encrypted(self):
        """Testing IDoneThisIntegration user form, saving encrypted API token
        to settings
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)
        form.cleaned_data = {
            'idonethis_api_token': 'tok123',
        }

        self.spy_on(encrypt_password)
        self.spy_on(self.profile.save)

        form.save()

        self.assertEqual(len(encrypt_password.spy.calls), 1)
        self.assertEqual(len(self.profile.save.spy.calls), 1)

        self.assertEqual(
            decrypt_password(self.profile.settings['idonethis']['api_token']),
            'tok123')

    def test_user_save_token_encrypted_replaces_old_token(self):
        """Testing IDoneThisIntegration user form, saving encrypted API token
        replaces old token in settings and deletes cached team IDs
        """
        form = IDoneThisIntegrationAccountPageForm(page=None,
                                                   request=self.request,
                                                   user=self.user)
        form.cleaned_data = {
            'idonethis_api_token': 'tokABC',
        }
        self.profile.settings['idonethis'] = {
            'api_token': encrypt_password('tok123'),
            'other_key': 'other value',
        }

        cache.set(self.team_ids_cache_key, {'team123', 'teamABC'})

        self.spy_on(encrypt_password)
        self.spy_on(self.profile.save)

        form.save()

        self.assertEqual(len(encrypt_password.spy.calls), 1)
        self.assertEqual(len(self.profile.save.spy.calls), 1)

        self.assertEqual(
            decrypt_password(self.profile.settings['idonethis']['api_token']),
            'tokABC')
        self.assertEqual(self.profile.settings['idonethis']['other_key'],
                         'other value')
        self.assertNotIn(self.team_ids_cache_key, cache)


class IDoneThisIntegrationUtilTests(IntegrationTestCase):
    """Test utility methods which are not fully covered by other tests."""

    integration_cls = IDoneThisIntegration

    def setUp(self):
        """Initialize this test case."""
        super(IDoneThisIntegrationUtilTests, self).setUp()

        self.user = User.objects.create_user(username='testuser')
        self.team_ids_cache_key = make_cache_key('idonethis-team_ids-testuser')
        self.profile = self.user.get_profile()
        self.profile.settings['idonethis'] = {
            'api_token': encrypt_password('tok123'),
        }

    def test_get_user_team_ids_without_token(self):
        """Testing IDoneThisIntegration team IDs get None without an API
        token
        """
        self.profile.settings['idonethis'] = {}

        self.spy_on(cache_memoize)
        self.spy_on(urlopen)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 0)
        self.assertEqual(len(urlopen.spy.calls), 0)

        self.assertIsNone(team_ids)
        self.assertNotIn(self.team_ids_cache_key, cache)

    def test_get_user_team_ids_from_cache(self):
        """Testing IDoneThisIntegration team IDs get data from cache without
        API request
        """
        cached_team_ids = {'team123', 'teamABC'}
        cache.set(self.team_ids_cache_key, cached_team_ids)

        self.spy_on(cache_memoize)
        self.spy_on(urlopen)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 0)

        self.assertEqual(team_ids, cached_team_ids)

    def test_get_user_team_ids_request(self):
        """Testing IDoneThisIntegration team IDs get data from API request
        if not in cache
        """
        response = json.dumps([
            {
                'name': 'Example Team 1',
                'created_at': '2016-07-05T07:13:57.873Z',
                'updated_at': '2016-07-05T07:13:57.873Z',
                'hash_id': 'team123'
            }, {
                'name': 'Example Team 2',
                'created_at': '2016-07-05T07:13:57.875Z',
                'updated_at': '2016-07-05T07:13:57.875Z',
                'hash_id': 'teamABC'
            }, {
                'name': 'Duplicate Team 1',
                'created_at': '2016-07-05T07:13:57.877Z',
                'updated_at': '2016-07-05T07:13:57.877Z',
                'hash_id': 'team123'
            }])

        self.spy_on(cache_memoize)
        self.spy_on(urlopen,
                    call_fake=lambda request, **kwargs: StringIO(response))
        self.spy_on(logging.error)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 0)

        request = urlopen.spy.calls[0].args[0]
        self.assertEqual(request.get_full_url(),
                         'https://beta.idonethis.com/api/v2/teams')
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Authorization'), 'Token tok123')
        self.assertIsNone(request.data)

        self.assertEqual(team_ids, {'team123', 'teamABC'})
        self.assertEqual(team_ids, cache.get(self.team_ids_cache_key))

    def test_get_user_team_ids_request_empty_team_list(self):
        """Testing IDoneThisIntegration team IDs get empty set if API request
        gets empty list
        """
        self.spy_on(cache_memoize)
        self.spy_on(urlopen,
                    call_fake=lambda request, **kwargs: StringIO('[]'))
        self.spy_on(logging.error)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 0)

        self.assertEqual(team_ids, set())
        self.assertEqual(team_ids, cache.get(self.team_ids_cache_key))

    def test_get_user_team_ids_request_httperror(self):
        """Testing IDoneThisIntegration team IDs get None if API request gets
        HTTPError
        """
        self.spy_on(cache_memoize)
        self.spy_on(urlopen, call_fake=_urlopen_raise_httperror)
        self.spy_on(logging.error)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 2)

        self.assertIsNone(team_ids)
        self.assertNotIn(self.team_ids_cache_key, cache)

    def test_get_user_team_ids_request_urlerror(self):
        """Testing IDoneThisIntegration team IDs get None if API request gets
        URLError
        """
        self.spy_on(cache_memoize)
        self.spy_on(urlopen, call_fake=_urlopen_raise_urlerror)
        self.spy_on(logging.error)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 2)

        self.assertIsNone(team_ids)
        self.assertNotIn(self.team_ids_cache_key, cache)

    def test_get_user_team_ids_request_invalid_json(self):
        """Testing IDoneThisIntegration team IDs get None if API request gets
        invalid JSON
        """
        self.spy_on(cache_memoize)
        self.spy_on(urlopen,
                    call_fake=lambda request, **kwargs: StringIO('[invalid'))
        self.spy_on(logging.error)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 1)

        self.assertIsNone(team_ids)
        self.assertNotIn(self.team_ids_cache_key, cache)

    def test_get_user_team_ids_request_invalid_team_data(self):
        """Testing IDoneThisIntegration team IDs get None if API request gets
        invalid team data
        """
        self.spy_on(cache_memoize)
        self.spy_on(urlopen,
                    call_fake=lambda request, **kw: StringIO('[{"a":"b"}]'))
        self.spy_on(logging.error)

        team_ids = get_user_team_ids(self.user)

        self.assertEqual(len(cache_memoize.spy.calls), 1)
        self.assertEqual(len(urlopen.spy.calls), 1)
        self.assertEqual(len(logging.error.spy.calls), 1)

        self.assertIsNone(team_ids)
        self.assertNotIn(self.team_ids_cache_key, cache)


def _urlopen_raise_httperror(request, **kwargs):
    """Fake urlopen that raises an HTTPError for testing.

    Args:
        request (urllib2.Request):
            The request to open.

        **kwargs (dict):
            Additional keyword arguments passed to urlopen.

    Raises:
        urllib2.HTTPError:
            The error for testing.
    """
    raise HTTPError(request.get_full_url(), 401, '', {}, StringIO(''))


def _urlopen_raise_urlerror(request, **kwargs):
    """Fake urlopen that raises a URLError for testing.

    Args:
        request (urllib2.Request):
            The request to open.

        **kwargs (dict):
            Additional keyword arguments passed to urlopen.

    Raises:
        urllib2.URLError:
            The error for testing.
    """
    raise URLError('url error')
