"""Integration for building changes on Travis CI."""

from __future__ import unicode_literals

import base64
import logging

import yaml
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.db import IntegrityError, transaction
from django.utils.functional import cached_property
from djblets.avatars.services import URLAvatarService
from djblets.siteconfig.models import SiteConfiguration
from reviewboard.admin.server import build_server_url
from reviewboard.avatars import avatar_services
from reviewboard.extensions.hooks import SignalHook
from reviewboard.integrations import Integration
from reviewboard.reviews.models.status_update import StatusUpdate
from reviewboard.reviews.signals import review_request_published

from rbintegrations.travisci.api import TravisAPI
from rbintegrations.travisci.forms import TravisCIIntegrationConfigForm


logger = logging.getLogger(__name__)


class TravisCIIntegration(Integration):
    """Integrates Review Board with Travis CI."""

    name = 'Travis CI'
    description = 'Builds diffs posted to Review Board using Travis CI.'
    config_form_cls = TravisCIIntegrationConfigForm

    def initialize(self):
        """Initialize the integration hooks."""
        SignalHook(self, review_request_published,
                   self._on_review_request_published)

    @cached_property
    def icon_static_urls(self):
        """Return the icons used for the integration.

        Returns:
            dict:
            The icons for Travis CI.
        """
        from rbintegrations.extension import RBIntegrationsExtension

        extension = RBIntegrationsExtension.instance

        return {
            '1x': extension.get_static_url('images/travisci/icon.png'),
            '2x': extension.get_static_url('images/travisci/icon@2x.png'),
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
                The change description associated with the publish.

            **kwargs (dict):
                Additional keyword arguments.
        """
        repository = review_request.repository

        # Only build changes against GitHub repositories.
        if not (repository and
                repository.hosting_account and
                repository.hosting_account.service_name == 'github'):
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

        user = self._get_or_create_user()

        scmtool = repository.get_scmtool()
        diff_data = base64.b64encode(scmtool.get_parser(b'').raw_diff(diffset))

        commit_message = '%s\n\n%s' % (review_request.summary,
                                       review_request.description)
        webhook_url = build_server_url(reverse('travis-ci-webhook'))

        for config in matching_configs:
            status_update = StatusUpdate.objects.create(
                service_id='travis-ci',
                user=user,
                summary='Travis CI',
                description='starting build...',
                state=StatusUpdate.PENDING,
                review_request=review_request,
                change_description=changedesc)

            travis_config = yaml.load(config.get('travis_yml'),
                                      Loader=yaml.SafeLoader)

            # Add set-up and patching to the start of the "before_install"
            # section of the config.
            before_install = []

            if travis_config.get('git', {}).get('depth', True) is not False:
                before_install.append('git fetch --unshallow origin')

            before_install.append('git checkout %s' % diffset.base_commit_id)

            # Add parent diff if necessary
            parent_diff_data = self._get_parent_diff(diffset)

            if parent_diff_data:
                parent_diff_data = base64.b64encode(parent_diff_data)
                before_install.append('echo %s | base64 --decode | patch -p1' %
                                      parent_diff_data.decode('utf-8'))

            before_install.append('echo %s | base64 --decode | patch -p1' %
                              diff_data.decode('utf-8'))

            old_install = travis_config.get('before_install', [])

            if not isinstance(old_install, list):
                old_install = [old_install]

            travis_config['before_install'] = before_install + old_install

            # Set up webhook notifications.
            notifications = travis_config.get('notifications') or {}
            webhooks = notifications.get('webhooks') or {}

            urls = webhooks.get('urls', [])

            if not isinstance(urls, list):
                urls = [urls]

            urls.append(webhook_url)

            webhooks['urls'] = urls
            webhooks['on_start'] = 'always'

            notifications['webhooks'] = webhooks
            notifications['email'] = False
            travis_config['notifications'] = notifications

            # Add some special data in the environment so that when the
            # webhooks come in, we can find the right status update to update.
            env = travis_config.setdefault('env', {})

            if not isinstance(env, dict):
                env = {
                    'matrix': env,
                }

            global_ = env.setdefault('global', [])

            if not isinstance(global_, list):
                global_ = [global_]

            global_ += [
                'REVIEWBOARD_STATUS_UPDATE_ID=%d' % status_update.pk,
                'REVIEWBOARD_TRAVIS_INTEGRATION_CONFIG_ID=%d' % config.pk,
            ]

            env['global'] = global_

            travis_config['env'] = env

            # Time to kick off the build!
            logger.info('Triggering Travis CI build for review request %s '
                        '(diffset revision %d)',
                        review_request.get_absolute_url(), diffset.revision)
            api = TravisAPI(config)
            repo_slug = self._get_github_repository_slug(repository)
            api.start_build(repo_slug, travis_config, commit_message,
                            config.get('branch_name') or 'master')

    def _get_github_repository_slug(self, repository):
        """Return the "slug" for a GitHub repository.

        Args:
            repository (reviewboard.scmtools.models.Repository):
                The repository.

        Returns:
            unicode:
            The slug for use with the Travis CI API.
        """
        extra_data = repository.extra_data
        plan = extra_data['repository_plan']

        if plan == 'public':
            return '%s/%s' % (repository.hosting_account.username,
                              extra_data['github_public_repo_name'])
        elif plan == 'public-org':
            return '%s/%s' % (extra_data['github_public_org_name'],
                              extra_data['github_public_org_repo_name'])
        elif plan == 'private':
            return '%s/%s' % (extra_data['hosting_account_username'],
                              extra_data['github_private_repo_name'])
        elif plan == 'private-org':
            return '%s/%s' % (extra_data['github_private_org_name'],
                              extra_data['github_private_org_repo_name'])
        else:
            raise ValueError('Unexpected plan for GitHub repository %d: %s'
                             % (repository.pk, plan))

    def _get_or_create_user(self):
        """Return a user to use for Travis CI.

        Returns:
            django.contrib.auth.models.User:
            A user instance.
        """
        try:
            return User.objects.get(username='travis-ci')
        except User.DoesNotExist:
            logger.info('Creating new user for Travis CI')
            siteconfig = SiteConfiguration.objects.get_current()
            noreply_email = siteconfig.get('mail_default_from')

            with transaction.atomic():
                try:
                    user = User.objects.create(username='travis-ci',
                                               email=noreply_email,
                                               first_name='Travis',
                                               last_name='CI')
                except IntegrityError:
                    # Another process/thread beat us to it.
                    return User.objects.get(username='travis-ci')

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

    def _get_parent_diff(self, diffset):
        """Return the raw parent diff.

        Args:
            diffset (reviewboard.diffviewer.models.DiffSet):
                The diffset to get the parent data for.

        Returns:
            bytes:
            The raw parent diff data, if available. None if not.
        """
        data = []

        for filediff in diffset.files.all():
            parent_diff = filediff.parent_diff

            if parent_diff:
                data.append(parent_diff)

        if data:
            return b''.join(data)
        else:
            return None
