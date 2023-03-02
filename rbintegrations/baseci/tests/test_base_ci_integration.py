"""Unit tests for rbintegrations.baseci.BaseCIIntegration.

Version Added:
    3.1
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

import kgb
from django.db.models import Q
from djblets.conditions import ConditionSet, Condition
from djblets.forms.fields import ConditionsField
from djblets.testing.decorators import add_fixtures
from kgb.ops import BaseSpyOperation
from reviewboard.diffviewer.models import DiffSet
from reviewboard.integrations.base import get_integration_manager
from reviewboard.integrations.forms import IntegrationConfigForm
from reviewboard.integrations.models import IntegrationConfig
from reviewboard.reviews.conditions import (ReviewRequestConditionChoices,
                                            ReviewRequestRepositoriesChoice)
from reviewboard.reviews.models import StatusUpdate
from reviewboard.site.models import LocalSite
from typing_extensions import TypedDict

from rbintegrations.baseci.errors import CIBuildError
from rbintegrations.baseci.integration import BaseCIIntegration, BuildPrepData
from rbintegrations.testing.testcases import IntegrationTestCase
from rbintegrations.travisci.integration import TravisCIIntegration

if TYPE_CHECKING:
    from reviewboard.reviews.models import ReviewRequest


class SetupRunTestResults(TypedDict):
    """Results from setting up a run test for a build integration.

    Version Added:
        3.1
    """

    #: The configuration to use for the build.
    config: Optional[IntegrationConfig]

    #: The DiffSets created for the test.
    diffsets: List[DiffSet]

    #: The review request created for the test.
    review_request: ReviewRequest


class MyCIIntegrationConfigForm(IntegrationConfigForm):
    """Test form for BaseCIIntegration tests.

    Version Added:
        3.1
    """

    conditions = ConditionsField(ReviewRequestConditionChoices)


class MyCIIntegration(BaseCIIntegration):
    """Test integration for BaseCIIntegration tests.

    Version Added:
        3.1
    """

    name = 'My CI'
    integration_id = 'my-ci'
    config_form_cls = MyCIIntegrationConfigForm
    status_update_service_id = 'my-ci'
    bot_username = 'test-ci-user'
    bot_user_first_name = 'Test'
    bot_user_last_name = 'CI'

    def prepare_builds(
        self,
        prep_data: BuildPrepData,
    ) -> bool:
        prep_data.extra_state['my_state'] = 123

        return True

    def start_build(
        self,
        *,
        prep_data: BuildPrepData,
        config: IntegrationConfig,
        status_update: StatusUpdate,
    ) -> None:
        pass


class BaseCIIntegrationTests(IntegrationTestCase):
    """Unit tests for BaseCIIntegration.

    Version Added:
        3.1
    """

    integration_cls = MyCIIntegration
    fixtures = ['test_users']

    @classmethod
    def setUpClass(cls) -> None:
        get_integration_manager().register_integration_class(
            cls.integration_cls)

    @classmethod
    def tearDownClass(cls) -> None:
        get_integration_manager().unregister_integration_class(
            cls.integration_cls)

    def test_get_or_create_api_token_with_new(self) -> None:
        """Testing BaseCIIntegration.get_or_create_api_token with new token"""
        user = self.create_user()

        with self.assertNumQueries(2):
            token = self.integration.get_or_create_api_token(
                user=user,
                local_site=None)

        self.assertIsNotNone(token.pk)
        self.assertEqual(token.user, user)
        self.assertIsNone(token.local_site)

    def test_get_or_create_api_token_with_new_and_local_site(self) -> None:
        """Testing BaseCIIntegration.get_or_create_api_token with new token
        on LocalSite
        """
        user = self.create_user()
        local_site = self.create_local_site()

        with self.assertNumQueries(2):
            token = self.integration.get_or_create_api_token(
                user=user,
                local_site=local_site)

        self.assertIsNotNone(token.pk)
        self.assertEqual(token.user, user)
        self.assertEqual(token.local_site, local_site)

    def test_get_or_create_api_token_with_existing(self) -> None:
        """Testing BaseCIIntegration.get_or_create_api_token with existing
        token
        """
        user = self.create_user()

        with self.assertNumQueries(2):
            token1 = self.integration.get_or_create_api_token(
                user=user,
                local_site=None)

        with self.assertNumQueries(1):
            token2 = self.integration.get_or_create_api_token(
                user=user,
                local_site=None)

        self.assertEqual(token1, token2)

    def test_get_or_create_api_token_with_existing_and_local_site(
        self,
    ) -> None:
        """Testing BaseCIIntegration.get_or_create_api_token with existing
        token on LocalSite
        """
        user = self.create_user()
        local_site = self.create_local_site()

        with self.assertNumQueries(2):
            token1 = self.integration.get_or_create_api_token(
                user=user,
                local_site=local_site)

        with self.assertNumQueries(1):
            token2 = self.integration.get_or_create_api_token(
                user=user,
                local_site=local_site)

        self.assertEqual(token1, token2)

    def test_get_or_create_user_with_new(self) -> None:
        """Testing BaseCIIntegration.get_or_create_user with new user"""
        user = self.integration.get_or_create_user()

        self.assertIsNotNone(user.pk)
        self.assertAttrsEqual(
            user,
            {
                'email': 'noreply@example.com',
                'first_name': 'Test',
                'last_name': 'CI',
                'username': 'test-ci-user',
            })
        self.assertFalse(user.get_profile().should_send_email)

    def test_get_or_create_user_with_existing(self) -> None:
        """Testing BaseCIIntegration.get_or_create_user with existing user"""
        integration = self.integration
        user1 = integration.get_or_create_user()
        user2 = integration.get_or_create_user()

        self.assertEqual(user1, user2)

    @add_fixtures(['test_scmtools'])
    def test_get_matching_configs(self) -> None:
        """Testing BaseCIIntegration.get_matching_configs"""
        local_site = self.create_local_site()

        # These will match.
        config1 = self._create_config(name='config1')
        config2 = self._create_config(name='config2')

        # These will not match.
        self._create_config(name='config3',
                            integration_id=TravisCIIntegration.integration_id)
        self._create_config(name='config4',
                            enabled=False)
        self._create_config(name='config5',
                            with_condition_match=False)
        self._create_config(name='config6',
                            local_site=local_site)

        user = self.create_user()
        review_request = self.create_review_request(submitter=user,
                                                    create_repository=True)

        self.assertEqual(
            self.integration.get_matching_configs(
                review_request=review_request),
            [config1, config2])

    @add_fixtures(['test_scmtools', 'test_site'])
    def test_get_matching_configs_and_local_site(self) -> None:
        """Testing BaseCIIntegration.get_matching_configs and Local Site"""
        local_site1 = self.create_local_site(name='test-site-1')
        local_site2 = self.create_local_site(name='test-site-2')

        # These will match.
        config1 = self._create_config(name='config1',
                                      local_site=local_site1)
        config2 = self._create_config(name='config2',
                                      local_site=local_site1)

        # These will not match.
        self._create_config(name='config3',
                            integration_id=TravisCIIntegration.integration_id,
                            local_site=local_site1)
        self._create_config(name='config4',
                            enabled=False,
                            local_site=local_site1)
        self._create_config(name='config5',
                            with_condition_match=False,
                            local_site=local_site1)
        self._create_config(name='config6')
        self._create_config(name='config7',
                            local_site=local_site2)

        user = self.create_user()
        review_request = self.create_review_request(submitter=user,
                                                    create_repository=True,
                                                    local_site=local_site1)

        self.assertEqual(
            self.integration.get_matching_configs(
                review_request=review_request),
            [config1, config2])

    def test_update_status_with_no_new_data(self) -> None:
        """Testing BaseCIIntegration.update_status with no new data"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(review_request)
        old_timestamp = status_update.timestamp

        with self.assertNumQueries(0):
            self.integration.update_status(status_update)

        self.assertEqual(status_update.timestamp, old_timestamp)

    def test_update_status_with_noops(self) -> None:
        """Testing BaseCIIntegration.update_status with no no-op changes"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='My description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        with self.assertNumQueries(0):
            self.integration.update_status(
                status_update,
                state=StatusUpdate.PENDING,
                description='My description.',
                url='https://example.com',
                url_text='Link')

        self.assertEqual(status_update.timestamp, old_timestamp)

    def test_update_status_with_new_data(self) -> None:
        """Testing BaseCIIntegration.update_status with new data"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        queries = [
            {
                'model': StatusUpdate,
                'type': 'UPDATE',
                'where': Q(pk=status_update.pk),
            },
        ]

        with self.assertQueries(queries):
            self.integration.update_status(
                status_update,
                state=StatusUpdate.DONE_SUCCESS,
                description='new description.',
                url='https://example.com/new/',
                url_text='New link')

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.DONE_SUCCESS,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure this all saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.DONE_SUCCESS,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

    def test_update_status_with_save_false(self) -> None:
        """Testing BaseCIIntegration.update_status with save=False"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        with self.assertNumQueries(0):
            self.integration.update_status(
                status_update,
                state=StatusUpdate.DONE_SUCCESS,
                description='new description.',
                url='https://example.com/new/',
                url_text='New link',
                save=False)

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.DONE_SUCCESS,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure none of that saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'description.',
                'state': StatusUpdate.PENDING,
                'timestamp': old_timestamp,
                'url': 'https://example.com',
                'url_text': 'Link',
            })

    def test_set_waiting(self) -> None:
        """Testing BaseCIIntegration.set_waiting"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='My description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_waiting(status_update)

        attrs = {
            'description': 'waiting to run.',
            'state': StatusUpdate.NOT_YET_RUN,
            'url': 'https://example.com',
            'url_text': 'Link',
        }

        self.assertAttrsEqual(status_update, attrs)
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure this all saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(status_update, attrs)
        self.assertGreater(status_update.timestamp, old_timestamp)

    def test_set_waiting_with_state(self) -> None:
        """Testing BaseCIIntegration.set_waiting with new custom state"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_waiting(
            status_update,
            description='new description.',
            url='https://example.com/new/',
            url_text='New link')

        attrs = {
            'description': 'new description.',
            'state': StatusUpdate.NOT_YET_RUN,
            'url': 'https://example.com/new/',
            'url_text': 'New link',
        }

        self.assertAttrsEqual(status_update, attrs)
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure this all saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(status_update, attrs)
        self.assertGreater(status_update.timestamp, old_timestamp)

    def test_set_waiting_with_save_false(self) -> None:
        """Testing BaseCIIntegration.set_waiting with save=False"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_waiting(
            status_update,
            description='new description.',
            url='https://example.com/new/',
            url_text='New link',
            save=False)

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.NOT_YET_RUN,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure none of that saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'description.',
                'state': StatusUpdate.PENDING,
                'timestamp': old_timestamp,
                'url': 'https://example.com',
                'url_text': 'Link',
            })

    def test_set_starting(self) -> None:
        """Testing BaseCIIntegration.set_starting"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.ERROR,
            description='My description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_starting(status_update)

        attrs = {
            'description': 'starting build...',
            'state': StatusUpdate.PENDING,
            'url': 'https://example.com',
            'url_text': 'Link',
        }

        self.assertAttrsEqual(status_update, attrs)
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure this all saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(status_update, attrs)
        self.assertGreater(status_update.timestamp, old_timestamp)

    def test_set_starting_with_state(self) -> None:
        """Testing BaseCIIntegration.set_starting with new custom state"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.ERROR,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_starting(
            status_update,
            description='new description.',
            url='https://example.com/new/',
            url_text='New link')

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.PENDING,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure this all saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.PENDING,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

    def test_set_starting_with_save_false(self) -> None:
        """Testing BaseCIIntegration.set_starting with save=False"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.ERROR,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_starting(
            status_update,
            description='new description.',
            url='https://example.com/new/',
            url_text='New link',
            save=False)

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.PENDING,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure none of that saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'description.',
                'state': StatusUpdate.ERROR,
                'timestamp': old_timestamp,
                'url': 'https://example.com',
                'url_text': 'Link',
            })

    def test_set_error(self) -> None:
        """Testing BaseCIIntegration.set_error"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='My description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_error(status_update)

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'internal error.',
                'state': StatusUpdate.ERROR,
                'url': 'https://example.com',
                'url_text': 'Link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure this all saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'internal error.',
                'state': StatusUpdate.ERROR,
                'url': 'https://example.com',
                'url_text': 'Link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

    def test_set_error_with_state(self) -> None:
        """Testing BaseCIIntegration.set_error with new custom state"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_error(
            status_update,
            description='new description.',
            url='https://example.com/new/',
            url_text='New link')

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.ERROR,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure this all saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.ERROR,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

    def test_set_error_with_save_false(self) -> None:
        """Testing BaseCIIntegration.set_error with save=False"""
        review_request = self.create_review_request()
        status_update = self.create_status_update(
            review_request,
            state=StatusUpdate.PENDING,
            description='description.',
            url='https://example.com',
            url_text='Link')
        old_timestamp = status_update.timestamp

        self.integration.set_error(
            status_update,
            description='new description.',
            url='https://example.com/new/',
            url_text='New link',
            save=False)

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'new description.',
                'state': StatusUpdate.ERROR,
                'url': 'https://example.com/new/',
                'url_text': 'New link',
            })
        self.assertGreater(status_update.timestamp, old_timestamp)

        # Make sure none of that saved.
        status_update.refresh_from_db()

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'description.',
                'state': StatusUpdate.PENDING,
                'timestamp': old_timestamp,
                'url': 'https://example.com',
                'url_text': 'Link',
            })

    @add_fixtures(['test_scmtools'])
    def test_on_publish(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published"""
        integration = self.integration

        info = self._setup_run_test()
        config = info['config']
        diffsets = info['diffsets']
        review_request = info['review_request']

        assert config

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        prep_data = call_kwargs['prep_data']
        status_update = call_kwargs['status_update']

        self.assertEqual(call_kwargs['config'], config)

        self.assertAttrsEqual(
            prep_data,
            {
                'changedesc': None,
                'configs': [config],
                'diffset': diffsets[0],
                'extra_state': {
                    'my_state': 123,
                },
                'review_request': review_request,
            })
        self.assertEqual(prep_data.user.username, 'test-ci-user')

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': None,
                'description': 'starting build...',
                'extra_data': {
                    '__integration_config_id': config.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.PENDING,
                'summary': 'My CI',
                'user': prep_data.user,
            })

    @add_fixtures(['test_scmtools'])
    def test_on_publish_with_changedesc(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published with
        ChangeDescription
        """
        integration = self.integration

        info = self._setup_run_test(with_changedesc=True)
        config = info['config']
        diffsets = info['diffsets']
        review_request = info['review_request']

        assert config

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        build_config = call_kwargs['config']
        prep_data = call_kwargs['prep_data']
        status_update = call_kwargs['status_update']

        self.assertEqual(build_config, config)

        self.assertAttrsEqual(
            prep_data,
            {
                'configs': [config],
                'diffset': diffsets[1],
                'extra_state': {
                    'my_state': 123,
                },
                'review_request': review_request,
            })
        self.assertIsNotNone(prep_data.changedesc)
        self.assertEqual(prep_data.user.username, 'test-ci-user')

        self.assertAttrsEqual(
            status_update,
            {
                'change_description': prep_data.changedesc,
                'description': 'starting build...',
                'extra_data': {
                    '__integration_config_id': config.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.PENDING,
                'summary': 'My CI',
                'user': prep_data.user,
            })
        self.assertIsNotNone(status_update.pk)

    @add_fixtures(['test_scmtools'])
    def test_on_publish_with_build_error(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published with
        CIBuildError
        """
        integration = self.integration

        self._setup_run_test(spy_op=kgb.SpyOpRaise(CIBuildError(
            'some error.',
            url='https://example.com/error/',
            url_text='Error')))

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        status_update = call_kwargs['status_update']

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'some error.',
                'state': StatusUpdate.ERROR,
                'url': 'https://example.com/error/',
                'url_text': 'Error',
            })

    @add_fixtures(['test_scmtools'])
    def test_on_publish_with_exception(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published with
        exception
        """
        integration = self.integration

        self._setup_run_test(spy_op=kgb.SpyOpRaise(Exception('oh no.')))

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        status_update = call_kwargs['status_update']

        self.assertAttrsEqual(
            status_update,
            {
                'description': 'internal error: oh no.',
                'state': StatusUpdate.ERROR,
            })

    @add_fixtures(['test_scmtools'])
    def test_on_publish_without_matching_config(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published without
        matching configuration
        """
        self._setup_run_test(with_config=False)

        self.assertSpyNotCalled(self.integration.start_build)

    @add_fixtures(['test_scmtools'])
    def test_on_publish_without_diffset(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published without
        DiffSet
        """
        self._setup_run_test(with_diffset=False)

        self.assertSpyNotCalled(self.integration.start_build)

    @add_fixtures(['test_scmtools'])
    def test_on_publish_without_changedesc_diffset(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published without
        new diff in review request update
        """
        self._setup_run_test(with_changedesc=True,
                             with_diffset=False)

        self.assertSpyNotCalled(self.integration.start_build)

    @add_fixtures(['test_scmtools'])
    def test_on_publish_with_prepare_builds_false(self) -> None:
        """Testing BaseCIIntegration._on_review_request_published with
        prepare_builds() returning False
        """
        integration = self.integration

        self.spy_on(integration.prepare_builds,
                    op=kgb.SpyOpReturn(False))

        self._setup_run_test()

        self.assertSpyNotCalled(integration.start_build)

    @add_fixtures(['test_scmtools'])
    def test_manual_run(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run"""
        integration = self.integration

        info = self._setup_run_test(with_manual_run=True)
        config = info['config']
        diffsets = info['diffsets']
        review_request = info['review_request']

        assert config

        self.assertSpyNotCalled(integration.start_build)

        # Check the status update created on publish.
        status_update = StatusUpdate.objects.get()
        user = integration.get_or_create_user()

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': None,
                'description': 'waiting to run.',
                'extra_data': {
                    '__integration_config_id': config.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.NOT_YET_RUN,
                'summary': 'My CI',
                'user': user,
            })

        # Perform the manual run.
        status_update.run()

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        prep_data = call_kwargs['prep_data']

        self.assertEqual(call_kwargs['status_update'], status_update)
        self.assertEqual(call_kwargs['config'], config)

        status_update = call_kwargs['status_update']

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': None,
                'description': 'starting build...',
                'extra_data': {
                    '__integration_config_id': config.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.PENDING,
                'summary': 'My CI',
                'user': user,
            })

        self.assertAttrsEqual(
            prep_data,
            {
                'changedesc': None,
                'configs': [config],
                'diffset': diffsets[0],
                'extra_state': {
                    'my_state': 123,
                },
                'review_request': review_request,
            })
        self.assertEqual(prep_data.user.username, 'test-ci-user')

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': None,
                'description': 'starting build...',
                'extra_data': {
                    '__integration_config_id': config.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.PENDING,
                'summary': 'My CI',
                'user': prep_data.user,
            })

    @add_fixtures(['test_scmtools'])
    def test_manual_run_with_changedesc(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run"""
        integration = self.integration

        info = self._setup_run_test(with_changedesc=True,
                                    with_manual_run=True)
        config = info['config']
        diffsets = info['diffsets']
        review_request = info['review_request']

        assert config

        self.assertSpyNotCalled(integration.start_build)

        user = integration.get_or_create_user()

        # Check the status updates created on publish.
        status_updates = StatusUpdate.objects.all()
        self.assertEqual(len(status_updates), 2)

        status_update = status_updates[1]

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'description': 'waiting to run.',
                'extra_data': {
                    '__integration_config_id': config.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.NOT_YET_RUN,
                'summary': 'My CI',
                'user': user,
            })
        self.assertIsNotNone(status_update.change_description)

        changedesc = status_update.change_description

        # Perform the manual run.
        status_update.run()

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        prep_data = call_kwargs['prep_data']

        self.assertEqual(call_kwargs['status_update'], status_update)
        self.assertEqual(call_kwargs['config'], config)

        status_update = call_kwargs['status_update']

        self.assertAttrsEqual(
            prep_data,
            {
                'changedesc': changedesc,
                'configs': [config],
                'diffset': diffsets[1],
                'extra_state': {
                    'my_state': 123,
                },
                'review_request': review_request,
            })
        self.assertEqual(prep_data.user.username, 'test-ci-user')

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': changedesc,
                'description': 'starting build...',
                'extra_data': {
                    '__integration_config_id': config.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.PENDING,
                'summary': 'My CI',
                'user': prep_data.user,
            })

    @add_fixtures(['test_scmtools'])
    def test_manual_run_with_multiple_configs(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run with
        multiple matching configs in database
        """
        integration = self.integration
        integration_id = integration.integration_id

        config1 = self._create_config(name='bad-config-1',
                                      integration_id=integration_id,
                                      with_manual_run=True)

        info = self._setup_run_test(with_manual_run=True)
        config2 = info['config']
        diffsets = info['diffsets']
        review_request = info['review_request']

        assert config2

        self._create_config(name='bad-config-2',
                            integration_id=integration_id,
                            with_manual_run=True)

        self.assertSpyNotCalled(integration.start_build)

        # Check the status updates created on publish.
        #
        # There should be only 2, since we did a publish after config1 and
        # config2 were published but before config3.
        status_updates = list(StatusUpdate.objects.all())

        self.assertEqual(len(status_updates), 2)
        self.assertEqual(status_updates[0].integration_config, config1)
        self.assertEqual(status_updates[1].integration_config, config2)

        # We want to test against the middle status update (the "good" one).
        status_update = status_updates[1]

        user = integration.get_or_create_user()

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': None,
                'description': 'waiting to run.',
                'extra_data': {
                    '__integration_config_id': config2.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.NOT_YET_RUN,
                'summary': 'My CI',
                'user': user,
            })

        # Perform the manual run.
        status_update.run()

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        prep_data = call_kwargs['prep_data']

        self.assertEqual(call_kwargs['status_update'], status_update)
        self.assertEqual(call_kwargs['config'], config2)

        status_update = call_kwargs['status_update']

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': None,
                'description': 'starting build...',
                'extra_data': {
                    '__integration_config_id': config2.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.PENDING,
                'summary': 'My CI',
                'user': user,
            })

        self.assertAttrsEqual(
            prep_data,
            {
                'changedesc': None,
                'configs': [config2],
                'diffset': diffsets[0],
                'extra_state': {
                    'my_state': 123,
                },
                'review_request': review_request,
            })
        self.assertEqual(prep_data.user.username, 'test-ci-user')

        self.assertIsNotNone(status_update.pk)
        self.assertAttrsEqual(
            status_update,
            {
                'change_description': None,
                'description': 'starting build...',
                'extra_data': {
                    '__integration_config_id': config2.pk,
                    'can_retry': True,
                },
                'review_request': review_request,
                'service_id': 'my-ci',
                'state': StatusUpdate.PENDING,
                'summary': 'My CI',
                'user': prep_data.user,
            })

    @add_fixtures(['test_scmtools'])
    def test_manual_run_with_build_error(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run with
        CIBuildError
        """
        integration = self.integration

        self._setup_run_test(
            with_manual_run=True,
            spy_op=kgb.SpyOpRaise(CIBuildError(
                'some error.',
                url='https://example.com/error/',
                url_text='Error')))

        self.assertSpyNotCalled(integration.start_build)

        # Check the status update created on publish.
        status_updates = StatusUpdate.objects.all()
        self.assertEqual(len(status_updates), 1)

        status_updates[0].run()

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        status_update = call_kwargs['status_update']

        self.assertEqual(status_update, status_updates[0])
        self.assertAttrsEqual(
            status_update,
            {
                'description': 'some error.',
                'state': StatusUpdate.ERROR,
                'url': 'https://example.com/error/',
                'url_text': 'Error',
            })

    @add_fixtures(['test_scmtools'])
    def test_manual_run_with_exception(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run with
        exception
        """
        integration = self.integration

        self._setup_run_test(
            with_manual_run=True,
            spy_op=kgb.SpyOpRaise(Exception('oh no.')))

        self.assertSpyNotCalled(integration.start_build)

        # Check the status update created on publish.
        status_updates = StatusUpdate.objects.all()
        self.assertEqual(len(status_updates), 1)

        status_updates[0].run()

        self.assertSpyCalled(integration.start_build)
        call_kwargs = integration.start_build.last_call.kwargs
        status_update = call_kwargs['status_update']

        self.assertEqual(status_update, status_updates[0])
        self.assertAttrsEqual(
            status_update,
            {
                'description': 'internal error: oh no.',
                'state': StatusUpdate.ERROR,
            })

    @add_fixtures(['test_scmtools'])
    def test_manual_run_without_matching_configs(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run with
        matching configuration
        """
        integration = self.integration

        info = self._setup_run_test(
            with_manual_run=True,
            spy_op=kgb.SpyOpRaise(Exception('oh no.')))
        config = info['config']
        assert config

        self.assertSpyNotCalled(integration.start_build)

        # Check the status update created on publish.
        status_updates = StatusUpdate.objects.all()
        self.assertEqual(len(status_updates), 1)

        # Delete the old configuration.
        config.delete()
        get_integration_manager().clear_all_configs_cache()

        # Now attempt a manual run.
        status_updates[0].run()

        self.assertSpyNotCalled(integration.start_build)

    @add_fixtures(['test_scmtools'])
    def test_manual_run_without_diffset(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run without
        DiffSet
        """
        integration = self.integration

        # We'll create with a DiffSet, and then delete it, to simulate
        # the conditions we check for in the code.
        info = self._setup_run_test(
            with_manual_run=True,
            spy_op=kgb.SpyOpRaise(Exception('oh no.')))
        info['diffsets'][0].delete()

        self.assertSpyNotCalled(integration.start_build)

        # Check the status update created on publish.
        status_updates = StatusUpdate.objects.all()
        self.assertEqual(len(status_updates), 1)

        # Now attempt a manual run.
        status_updates[0].run()

        self.assertSpyNotCalled(integration.start_build)

    @add_fixtures(['test_scmtools'])
    def test_manual_run_without_changedesc_diffset(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run without
        new diff in review request update
        """
        integration = self.integration

        # We'll create with a DiffSet, and then delete the information in the
        # change description, to simulate the conditions we check for in the
        # code.
        #
        # This shouldn't be able to happen, but the code safe-guards against
        # this, so we're verifying those checks.
        info = self._setup_run_test(
            with_changedesc=True,
            with_manual_run=True,
            spy_op=kgb.SpyOpRaise(Exception('oh no.')))

        self.assertSpyNotCalled(integration.start_build)

        # Delete the 'diff' key.
        changedesc = info['review_request'].changedescs.all()[0]
        del changedesc.fields_changed['diff']
        changedesc.save(update_fields=('fields_changed',))

        # Check the status update created on publish.
        status_updates = StatusUpdate.objects.all()
        self.assertEqual(len(status_updates), 2)

        # Now attempt a manual run.
        status_updates[1].run()

        self.assertSpyNotCalled(integration.start_build)

    @add_fixtures(['test_scmtools'])
    def test_manual_run_without_service_id_match(self) -> None:
        """Testing BaseCIIntegration._on_status_update_request_run without
        service ID match
        """
        integration = self.integration

        self._setup_run_test(with_manual_run=True)

        self.assertSpyNotCalled(integration.start_build)

        # Check the status update created on publish.
        status_updates = StatusUpdate.objects.all()
        self.assertEqual(len(status_updates), 1)

        status_update = status_updates[0]

        # Set a new service ID and run it.
        status_update.service_id = 'other-service'
        status_update.run()

        self.assertSpyNotCalled(integration.start_build)

    def _setup_run_test(
        self,
        *,
        with_changedesc: bool = False,
        with_config: bool = True,
        with_diffset: bool = True,
        with_manual_run: bool = False,
        spy_op: Optional[BaseSpyOperation] = None,
    ) -> SetupRunTestResults:
        """Set up a test for a build run, and handle publishing.

        This will create a configuration, review request, diffset, and any
        other necessary objects for a test for a build run. It also takes care
        of the spying and the publishing.

        Args:
            with_changedesc (bool, optional):
                Whether to test a publish on a change description.

            with_config (bool, optional):
                Whether to create a configuration to test with.

            with_diffset (bool, optional):
                Whether to create diffsets on the review request or change
                description.

            with_manual_run (bool, optional):
                Whether to test with a manual run configuration.

            spy_op (kgb.ops.BaseSpyOperation, optional):
                An explicit spy operation to use for checking builds.

        Returns:
            dict:
            A dictionary of results. See :py:class:`SetupRunTestResults`.
        """
        diffsets: List[DiffSet] = []

        integration = self.integration
        integration.enable_integration()

        if not with_changedesc:
            # We're testing the initial publish, so spy on it here.
            self.spy_on(integration.start_build, op=spy_op)

        if with_config:
            config = self._create_config(name='config',
                                         with_manual_run=with_manual_run)
        else:
            config = None

        review_request = self.create_review_request(
            create_repository=True,
            target_people=[self.create_user()])

        if with_diffset:
            diffsets.append(self.create_diffset(
                review_request,
                revision=1,
                draft=True))

        review_request.publish(user=review_request.owner)

        if with_changedesc:
            # We haven't spied above. We want to spy now, before the next
            # publish.
            self.spy_on(integration.start_build, op=spy_op)

            draft = self.create_review_request_draft(review_request)
            draft.summary = 'New summary'
            draft.save(update_fields=('summary',))

            if with_diffset:
                diffsets.append(self.create_diffset(
                    review_request,
                    revision=2,
                    draft=True))

            review_request.publish(user=review_request.owner)

        return {
            'config': config,
            'diffsets': diffsets,
            'review_request': review_request,
        }

    def _create_config(
        self,
        *,
        name: str,
        integration_id: str = MyCIIntegration.integration_id,
        enabled: bool = True,
        local_site: Optional[LocalSite] = None,
        with_condition_match: bool = True,
        with_manual_run: bool = False,
    ) -> IntegrationConfig:
        """Create an integration config for testing.

        Args:
            name (str):
                The name of the configuration.

            integration_id (str, optional):
                The ID of the integration the configuration applies to.

            enabled (bool, optional):
                Whether this configuration is enabled.

            local_site (reviewboard.site.models.LocalSite, optional):
                The Local Site the configuration is bound to.

            with_condition_match (bool, optional):
                Whether the condition should match the test run.

            with_manual_run (bool, optional):
                Whether the configuration should be created in manual run mode.

        Returns:
            reviewboard.integrations.models.IntegrationConfig:
            The resulting integration configuration.
        """
        choice = ReviewRequestRepositoriesChoice()

        if with_condition_match:
            operator = choice.get_operator('any')
        else:
            operator = choice.get_operator('none')

        condition_set = ConditionSet(conditions=[
            Condition(choice=choice,
                      operator=operator)
        ])

        config_settings: Dict[str, Any] = {
            'conditions': condition_set.serialize(),
        }

        if with_manual_run:
            config_settings['run_manually'] = True

        return IntegrationConfig.objects.create(
            integration_id=integration_id,
            local_site=local_site,
            name=name,
            enabled=enabled,
            settings=config_settings)
