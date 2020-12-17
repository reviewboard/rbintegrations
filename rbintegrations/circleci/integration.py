"""Integration for building changes on CircleCI."""

from __future__ import unicode_literals

import json
import logging

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils.functional import cached_property
from django.utils.http import urlquote_plus
from django.utils.six.moves.urllib.request import urlopen
from djblets.avatars.services import URLAvatarService
from djblets.siteconfig.models import SiteConfiguration
from reviewboard.admin.server import get_server_url
from reviewboard.avatars import avatar_services
from reviewboard.extensions.hooks import SignalHook
from reviewboard.integrations import Integration
from reviewboard.reviews.models.status_update import StatusUpdate
from reviewboard.reviews.signals import review_request_published
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
        # Only build changes against GitHub or Bitbucket repositories.
        repository = review_request.repository

        if not repository or not repository.hosting_account:
            return

        service_name = repository.hosting_account.service_name

        if service_name not in ('github', 'bitbucket'):
            return

        diffset = review_request.get_latest_diffset()

        # Don't build any review requests that don't include diffs.
        if not diffset:
            return

        # If this was an update to a review request, make sure that there was a
        # diff update in it.
        if changedesc is not None:
            fields_changed = changedesc.fields_changed

            if ('diff' not in fields_changed or
                'added' not in fields_changed['diff']):
                return

        matching_configs = [
            config
            for config in self.get_configs(review_request.local_site)
            if config.match_conditions(form_cls=self.config_form_cls,
                                       review_request=review_request)
        ]

        if not matching_configs:
            return

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

        org_name, repo_name = self._get_repo_ids(service_name, repository)

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

            url = ('https://circleci.com/api/v1.1/project/%s/%s/%s/tree/%s'
                   '?circle-token=%s'
                   % (vcs_type, org_name, repo_name,
                      config.get('branch_name') or 'master',
                      urlquote_plus(config.get('circle_api_token'))))

            logger.info('Making CircleCI API request: %s', url)

            local_site = config.local_site

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

            data = json.loads(u.read())

            status_update.url = data['build_url']
            status_update.url_text = 'View Build'
            status_update.save()

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
