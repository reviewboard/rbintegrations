"""Integration for building changes on Jenkins CI."""

from __future__ import unicode_literals

import logging
from datetime import datetime

from django.utils.six.moves.urllib.error import HTTPError
from djblets.util.decorators import cached_property
from reviewboard.admin.server import get_server_url
from reviewboard.diffviewer.models import DiffSet
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

        try:
            from reviewboard.reviews.signals import status_update_request_run
            SignalHook(self, status_update_request_run,
                       self._on_status_update_request_run)
        except ImportError:
            # Running on Review Board 3.0.18 or older.
            pass

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
        # This integration will work with all repository types that rbtools
        # supports.
        repository = review_request.repository

        # Don't build any review request that don't have matching configs.
        matching_configs = [
            config
            for config in self.get_configs(review_request.local_site)
            if config.match_conditions(form_cls=self.config_form_cls,
                                       review_request=review_request)
        ]

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
            status_update.extra_data['can_retry'] = True

            if config.get('run_manually'):
                status_update.description = 'waiting to run.'
                status_update.state = StatusUpdate.NOT_YET_RUN
                status_update.save()
            else:
                patch_info['status_update_id'] = status_update.pk
                patch_info['reviewboard_server'] = get_server_url(
                    local_site=config.local_site)

                job_name = self._replace_job_variables(
                    config.get('jenkins_job_name'), repository, review_request)

                # Time to kick off the build!
                logger.info('Triggering Jenkins CI build for review request '
                            '%s (diffset revision %d)',
                            review_request.get_absolute_url(),
                            diffset.revision)
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
                        status_update.description = ('failed, job does not '
                                                     'exist.')

                    status_update.state = StatusUpdate.ERROR
                status_update.save()

    def _on_status_update_request_run(self, sender, status_update, **kwargs):
        """Handle a request to run or rerun a Jenkins build.

        Args:
            sender (object):
                The sender of the signal.

            status_update (reviewboard.reviews.models.StatusUpdate):
                The status update.

            **kwargs (dict):
                Any additional keyword arguments.
        """
        service_id = status_update.service_id

        if not service_id.startswith('jenkins-ci'):
            # Ignore anything that's not Jenkins.
            return

        review_request = status_update.review_request

        # This integration will work with all repository types that rbtools
        # supports.
        repository = review_request.repository

        matching_configs = [
            config
            for config in self.get_configs(review_request.local_site)
            if config.match_conditions(form_cls=self.config_form_cls,
                                       review_request=review_request)
        ]

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
                          'JenkinsCI for status update %d',
                          status_update.pk)
            return

        assert len(matching_configs) == 1
        config = matching_configs[0]

        patch_info = {
            'review_id': review_request.display_id,
            'diff_revision': diffset.revision,
            'status_update_id': status_update.pk,
            'reviewboard_server': get_server_url(
                local_site=config.local_site)
        }

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
            status_update.description = 'starting...'
            status_update.state = StatusUpdate.PENDING
            status_update.timestamp = datetime.now()
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
