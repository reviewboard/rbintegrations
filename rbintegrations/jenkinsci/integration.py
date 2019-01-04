"""Integration for building changes on Jenkins CI."""

from __future__ import unicode_literals

import logging

from django.utils.six.moves.urllib.error import HTTPError
from djblets.util.decorators import cached_property
from reviewboard.admin.server import get_server_url
from reviewboard.extensions.hooks import SignalHook
from reviewboard.integrations import Integration
from reviewboard.reviews.models.status_update import StatusUpdate
from reviewboard.reviews.signals import review_request_published

from rbintegrations.jenkinsci.api import JenkinsAPI
from rbintegrations.jenkinsci.common import (get_icon_static_urls,
                                             get_or_create_jenkins_user)
from rbintegrations.jenkinsci.forms import JenkinsCIIntegrationConfigForm


logger = logging.getLogger(__name__)


class JenkinsCIIntegration(Integration):
    """Integrates Review Board with Jenkins CI."""

    name = 'Jenkins CI'
    description = 'Builds diffs posted to Review Board using Jenkins CI.'
    config_form_cls = JenkinsCIIntegrationConfigForm

    def initialize(self):
        """Initialize the integration hooks."""
        SignalHook(self, review_request_published,
                   self._on_review_request_published)

    @cached_property
    def icon_static_urls(self):
        """The icons used for the integration."""
        return get_icon_static_urls()

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

        # This integration will work with all repository types that rbtools
        # supports.
        if not repository:
            return

        diffset = review_request.get_latest_diffset()

        # TODO: the following code is common to all CI integrations.
        # make a common class?

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

        user = get_or_create_jenkins_user()

        patch_info = {
            'review_id': review_request.display_id,
            'diff_revision': diffset.revision,
        }

        for config in matching_configs:
            status_update = StatusUpdate.objects.create(
                service_id='jenkins-ci',
                user=user,
                summary='Jenkins CI',
                description='starting build...',
                state=StatusUpdate.PENDING,
                review_request=review_request,
                change_description=changedesc)
            patch_info['status_update_id'] = status_update.pk
            patch_info['reviewboard_server'] = get_server_url(
                local_site=config.local_site)

            job_name = self._replace_job_variables(
                config.get('jenkins_job_name'), repository, review_request)

            # Time to kick off the build!
            logger.info('Triggering Jenkins CI build for review request %s '
                        '(diffset revision %d)',
                        review_request.get_absolute_url(), diffset.revision)
            api = JenkinsAPI(config.get('jenkins_endpoint'),
                             job_name,
                             config.get('jenkins_username'),
                             config.get('jenkins_password'))

            try:
                api.start_build(patch_info)
            except HTTPError as e:
                status_update.description = ('failed to communicate with '
                                             'Jenkins.')

                if e.code == 404:
                    status_update.description = 'failed, job does not exist.'

                status_update.state = StatusUpdate.ERROR
                status_update.save()

    def _replace_job_variables(self, job_name, repository, review_request):
        """Replace variables in the jenkins job name.

        Args:
            job_name (unicode):
                The template string for the Jenkins job name.

            repository (reviewboard.scmtools.models.Repository):
                The repository for the change being built.

            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request for the change being built.
        """
        job_name = job_name.replace('{repository}', repository.name)

        if repository.tool.name in ('Git',):
            job_name = job_name.replace('{branch}', review_request.branch)

        return job_name
