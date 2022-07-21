"""Integration for building changes on CircleCI."""

import json
import logging
from datetime import datetime
from urllib.parse import quote_plus
from urllib.request import urlopen

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils.functional import cached_property
from djblets.avatars.services import URLAvatarService
from djblets.siteconfig.models import SiteConfiguration
from reviewboard.admin.server import get_server_url
from reviewboard.avatars import avatar_services
from reviewboard.diffviewer.models import DiffSet
from reviewboard.extensions.hooks import SignalHook
from reviewboard.integrations.base import Integration
from reviewboard.reviews.models.status_update import StatusUpdate
from reviewboard.reviews.signals import (review_request_published,
                                         status_update_request_run)
from reviewboard.webapi.models import WebAPIToken

from rbintegrations.circleci.forms import CircleCIIntegrationConfigForm
from rbintegrations.util.urlrequest import URLRequest


logger = logging.getLogger(__name__)


class CircleCIIntegration(Integration):
    """Integrates Review Board with CircleCI."""

    name = 'CircleCI'
    description = 'Builds diffs posted to Review Board using CircleCI.'
    config_form_cls = CircleCIIntegrationConfigForm

    def initialize(self):
        """Initialize the integration hooks."""
        SignalHook(self, review_request_published,
                   self._on_review_request_published)

        SignalHook(self, status_update_request_run,
                   self._on_status_update_request_run)

    @cached_property
    def icon_static_urls(self):
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for CircleCI.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/circleci/icon.png'),
            '2x': extension.get_static_url('images/circleci/icon@2x.png'),
        }

    def _on_review_request_published(self, sender, review_request,
                                     changedesc=None, **kwargs):
        """Handle when a review request is published.

        Args:
            sender (object):
                The sender of the signal.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request which was published.

            changedesc (reviewboard.changedescs.models.ChangeDescription,
                        optional):
                The change description associated with this publish.

            **kwargs (dict):
                Additional keyword arguments.
        """
        repository, vcs_type, matching_configs = \
            self._prepare_for_build(review_request)

        if not bool(matching_configs):
            return

        # Don't build any review requests that don't include diffs.
        diffset = review_request.get_latest_diffset()

        if not diffset:
            return

        # If this was an update to a review request, make sure that there was a
        # diff update in it.
        if changedesc is not None:
            fields_changed = changedesc.fields_changed

            if ('diff' not in fields_changed or
                'added' not in fields_changed['diff']):
                return

        user = self._get_or_create_user()

        for config in matching_configs:
            status_update = StatusUpdate.objects.create(
                service_id='circle-ci',
                user=user,
                summary='CircleCI',
                description='starting build...',
                state=StatusUpdate.PENDING,
                review_request=review_request,
                change_description=changedesc)
            status_update.extra_data['can_retry'] = True

            if config.get('run_manually'):
                status_update.description = 'waiting to run.'
                status_update.state = StatusUpdate.NOT_YET_RUN
                status_update.save()
            else:
                try:
                    data = self._send_circleci_request(config, repository,
                                                       vcs_type, diffset,
                                                       review_request,
                                                       status_update)

                    status_update.url = data['build_url']
                    status_update.url_text = 'View Build'
                except Exception as e:
                    status_update.state = StatusUpdate.ERROR
                    status_update.description = str(e)

                status_update.save()

    def _on_status_update_request_run(self, sender, status_update, **kwargs):
        """Handle a request to run or rerun a CircleCI build.

        Args:
            sender (object):
                The sender of the signal.

            status_update (reviewboard.reviews.models.StatusUpdate):
                The status update.

            **kwargs (dict):
                Any additional keyword arguments.
        """
        service_id = status_update.service_id

        if not service_id.startswith('circle-ci'):
            # Ignore anything that's not CircleCI.
            return

        review_request = status_update.review_request

        repository, vcs_type, matching_configs = \
            self._prepare_for_build(review_request)

        diffset = None
        changedesc = status_update.change_description

        # If there's a change description associated with the status
        # update, then use the diff from that. Otherwise, choose the first
        # diffset on the review request.
        try:
            if changedesc and 'diff' in changedesc.fields_changed:
                new_diff = changedesc.fields_changed['diff']['added'][0]
                diffset = DiffSet.objects.get(pk=new_diff[2])
            else:
                diffset = DiffSet.objects.filter(
                    history=review_request.diffset_history_id).earliest()
        except DiffSet.DoesNotExist:
            logging.error('Unable to determine diffset when running '
                          'CircleCI tool for status update %d',
                          status_update.pk)
            return

        assert len(matching_configs) == 1
        config = matching_configs[0]

        try:
            data = self._send_circleci_request(config, repository,
                                               vcs_type, diffset,
                                               review_request, status_update)

            status_update.description = 'starting...'
            status_update.state = StatusUpdate.PENDING
            status_update.timestamp = datetime.now()
            status_update.url = data['build_url']
            status_update.url_text = 'View Build'
        except Exception as e:
            status_update.state = StatusUpdate.ERROR
            status_update.description = str(e)

        status_update.save()

    def _prepare_for_build(self, review_request):
        """Returns the required variables for the next step.

        Args:
            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request which was published.

        Returns:
            tuple of object, unicode and list.
            A three-tuple consisting of the repository, the service name and
            the matching configurations.
        """
        repository = None
        vcs_type = None
        matching_configs = None

        # Only build changes against GitHub or Bitbucket repositories.
        repository = review_request.repository

        if not repository or not repository.hosting_account:
            return (repository, vcs_type, matching_configs)

        service_name = repository.hosting_account.service_name

        # This may look weird, but it's here for defensive purposes.
        # Currently, the possible values for CircleCI's "vcs-type" field in
        # their API happens to match up perfectly with our service names,
        # but that's not necessarily always going to be the case.
        if service_name == 'github':
            vcs_type = 'github'
        elif service_name == 'bitbucket':
            vcs_type = 'bitbucket'
        else:
            raise ValueError('Unexpected hosting service type got through '
                             'to CircleCI invocation: %s'
                             % service_name)

        # Don't build any review requests that don't have matching configs.
        matching_configs = [
            config
            for config in self.get_configs(review_request.local_site)
            if config.match_conditions(form_cls=self.config_form_cls,
                                       review_request=review_request)
        ]

        return (repository, vcs_type, matching_configs)

    def _get_repo_ids(self, service_name, repository):
        """Return the organization and repo name for the given repository.

        Args:
            service_name (unicode):
                The version control service name.

            repository (reviewboard.scmtools.models.Repository):
                The repository.

        Returns:
            tuple of unicode:
            A two-tuple consisting of the organization (or user) and repository
            names.
        """
        extra_data = repository.extra_data
        plan = extra_data['repository_plan']

        if service_name == 'github':
            if plan == 'public':
                return (repository.hosting_account.username,
                        extra_data['github_public_repo_name'])
            elif plan == 'public-org':
                return (extra_data['github_public_org_name'],
                        extra_data['github_public_org_repo_name'])
            elif plan == 'private':
                return (repository.hosting_account.username,
                        extra_data['github_private_repo_name'])
            elif plan == 'private-org':
                return (extra_data['github_private_org_name'],
                        extra_data['github_private_org_repo_name'])
            else:
                raise ValueError('Unexpected plan for GitHub repository %d: %s'
                                 % (repository.pk, plan))
        elif service_name == 'bitbucket':
            if plan == 'personal':
                return (extra_data['bitbucket_account_username'],
                        extra_data['bitbucket_repo_name'])
            elif plan == 'other-user':
                return (extra_data['bitbucket_other_user_username'],
                        extra_data['bitbucket_other_user_repo_name'])
            elif plan == 'team':
                return (extra_data['bitbucket_team_name'],
                        extra_data['bitbucket_team_repo_name'])
            else:
                raise ValueError('Unexpected plan for Bitbucket repository '
                                 '%d: %s'
                                 % (repository.pk, plan))
        else:
            raise ValueError('Unexpected service_name %s' % service_name)

    def _get_or_create_user(self):
        """Return a user to use for CircleCI.

        Returns:
            django.contrib.auth.models.User:
            A user instance.
        """
        try:
            return User.objects.get(username='circle-ci')
        except User.DoesNotExist:
            logger.info('Creating new user for CircleCI')
            siteconfig = SiteConfiguration.objects.get_current()
            noreply_email = siteconfig.get('mail_default_from')

            with transaction.atomic():
                try:
                    user = User.objects.create(username='circle-ci',
                                               email=noreply_email,
                                               first_name='Circle',
                                               last_name='CI')
                except IntegrityError:
                    # Another process/thread beat us to it.
                    return User.objects.get(username='circle-ci')

                profile = user.get_profile()
                profile.should_send_email = False
                profile.save()

                if avatar_services.is_enabled(
                    URLAvatarService.avatar_service_id):
                    avatar_service = avatar_services.get_avatar_service(
                        URLAvatarService.avatar_service_id)
                    # TODO: make somewhat higher-res versions for the main
                    # avatar.
                    avatar_service.setup(user, self.icon_static_urls)

                return user

    def _send_circleci_request(self, config, repository, vcs_type,
                               diffset, review_request, status_update):
        """Build and send CircleCI request.

        Args:
            config (reviewboard.integrations.models.IntegrationConfig):
                Enabled integration configurations matching the query.

            repository (reviewboard.scmtools.models):
                The repository.

            vcs_type (unicode):
                The version control system type.

            diffset (reviewboard.diffviewer.models.DiffSet):
                The diffset.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request which was published.

            status_update (reviewboard.reviews.models.StatusUpdate):
                The status update for the tool that should be run.

        Returns:
            dict:
            Response from CircleCI.
        """
        org_name, repo_name = self._get_repo_ids(vcs_type, repository)
        api_token = config.get('circle_api_token')

        if not api_token:
            logger.error('Unable to make CircleCI API request for '
                         'integration config %d: api_token is missing.',
                         config.pk)
            raise ValueError('missing API token.')

        url = ('https://circleci.com/api/v1.1/project/%s/%s/%s/tree/%s'
               '?circle-token=%s'
               % (vcs_type, org_name, repo_name,
                  config.get('branch_name') or 'master',
                  quote_plus(api_token.encode('utf-8'))))

        logger.info('Making CircleCI API request: %s', url)

        local_site = config.local_site

        user = self._get_or_create_user()

        try:
            token = user.webapi_tokens.filter(local_site=local_site)[0]
        except IndexError:
            token = WebAPIToken.objects.generate_token(
                user, local_site=local_site, auto_generated=True)

        body = {
            'revision': diffset.base_commit_id,
            'build_parameters': {
                'CIRCLE_JOB': 'reviewboard',
                'REVIEWBOARD_SERVER':
                    get_server_url(local_site=config.local_site),
                'REVIEWBOARD_REVIEW_REQUEST': review_request.display_id,
                'REVIEWBOARD_DIFF_REVISION': diffset.revision,
                'REVIEWBOARD_API_TOKEN': token.token,
                'REVIEWBOARD_STATUS_UPDATE_ID': status_update.pk,
            },
        }

        if config.local_site:
            body['build_parameters']['REVIEWBOARD_LOCAL_SITE'] = \
                config.local_site.name

        request = URLRequest(
            url,
            body=json.dumps(body),
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            method='POST')

        u = urlopen(request)

        return json.loads(u.read())
