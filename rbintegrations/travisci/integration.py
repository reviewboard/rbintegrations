"""Integration for building changes on Travis CI."""

from __future__ import annotations

import base64
import logging
from typing import List, TYPE_CHECKING

import yaml
from django.urls import reverse
from django.utils.functional import cached_property
from reviewboard.admin.server import build_server_url

from rbintegrations.baseci.integration import (BaseCIIntegration,
                                               BuildPrepData)
from rbintegrations.travisci.api import TravisAPI
from rbintegrations.travisci.forms import TravisCIIntegrationConfigForm

if TYPE_CHECKING:
    from reviewboard.integrations.models import IntegrationConfig
    from reviewboard.reviews.models import StatusUpdate


logger = logging.getLogger(__name__)


class TravisCIIntegration(BaseCIIntegration):
    """Integrates Review Board with Travis CI."""

    name = 'Travis CI'
    description = 'Builds diffs posted to Review Board using Travis CI.'
    config_form_cls = TravisCIIntegrationConfigForm

    status_update_service_id = 'travis-ci'

    bot_username = 'travis-ci'
    bot_user_first_name = 'Travis'
    bot_user_last_name = 'CI'

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

    def prepare_builds(
        self,
        prep_data: BuildPrepData,
    ) -> bool:
        """Prepare for builds.

        This will check if the change is on a supported hosting service
        (GitHub), and only permit the build if it is.

        Version Added:
            3.1

        Args:
            prep_data (BuildPrepData):
                The builds preparation data to modify.

        Returns:
            bool:
            ``True`` if the builds should proceed. ``False`` if builds should
            be skipped.
        """
        # Only build changes against GitHub repositories.
        repository = prep_data.repository

        if not (repository and
                repository.hosting_account and
                repository.hosting_account.service_name == 'github'):
            return False

        scmtool = repository.get_scmtool()
        review_request = prep_data.review_request

        prep_data.extra_state.update({
            'commit_message': '%s\n\n%s' % (review_request.summary,
                                            review_request.description),
            'diff_data': (
                base64.b64encode(
                    scmtool.get_parser(b'').raw_diff(prep_data.diffset))
                .decode('utf-8')
            ),
            'webhook_url': build_server_url(reverse('travis-ci-webhook')),
        })

        return True

    def start_build(
        self,
        *,
        prep_data: BuildPrepData,
        config: IntegrationConfig,
        status_update: StatusUpdate,
    ) -> None:
        """Start a new build.

        This will trigger a Travis-CI build for the given review request and
        configuration.

        Version Added:
            3.1

        Args:
            prep_data (BuildPrepData):
                The builds preparation data containing information for the
                build.

            config (reviewboard.integrations.models.IntegrationConfig):
                The configuration for the integration triggering this build.

            status_update (reviewboard.reviews.models.status_update.
                           StatusUpdate):
                The status update indicating the status of this build.

        Raises:
            rbintegrations.baseci.errors.CIBuildError:
                There was an error invoking the build.
        """
        diffset = prep_data.diffset

        travis_config = yaml.load(config.get('travis_yml'),
                                  Loader=yaml.SafeLoader)

        # Add set-up and patching to the start of the "before_install"
        # section of the config.
        before_install: List[str] = []

        if travis_config.get('git', {}).get('depth', True) is not False:
            before_install.append('git fetch --unshallow origin || true')

        before_install.append('git checkout %s' % diffset.base_commit_id)

        # Add parent diff if necessary
        parent_diff_data = self._get_parent_diff(diffset)

        if parent_diff_data:
            parent_diff_data = base64.b64encode(parent_diff_data)
            before_install.append('echo %s | base64 --decode | patch -p1' %
                                  parent_diff_data.decode('utf-8'))

        before_install.append('echo %s | base64 --decode | patch -p1' %
                              prep_data.extra_state['diff_data'])

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

        urls.append(prep_data.extra_state['webhook_url'])

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
                    prep_data.review_request.get_absolute_url(),
                    diffset.revision)
        repo_slug = self._get_github_repository_slug(prep_data.repository)

        api = TravisAPI(config)
        api.start_build(repo_slug=repo_slug,
                        travis_config=travis_config,
                        commit_message=prep_data.extra_state['commit_message'],
                        branch=config.get('branch_name') or 'master')

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
            return '%s/%s' % (repository.hosting_account.username,
                              extra_data['github_private_repo_name'])
        elif plan == 'private-org':
            return '%s/%s' % (extra_data['github_private_org_name'],
                              extra_data['github_private_org_repo_name'])
        else:
            raise ValueError('Unexpected plan for GitHub repository %d: %s'
                             % (repository.pk, plan))

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
