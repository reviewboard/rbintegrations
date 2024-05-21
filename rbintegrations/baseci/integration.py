"""Base support for CI-based integrations.

This can be used by both internal and external integrations to more easily
integrate with CI solutions for Review Board.

Version Added:
    3.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING, Type

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.utils import timezone
from djblets.avatars.services import URLAvatarService
from djblets.secrets.token_generators import token_generator_registry
from djblets.siteconfig.models import SiteConfiguration
from reviewboard.admin.server import get_server_url
from reviewboard.avatars import avatar_services
from reviewboard.diffviewer.models import DiffSet
from reviewboard.extensions.hooks import SignalHook
from reviewboard.integrations.base import Integration
from reviewboard.integrations.models import IntegrationConfig
from reviewboard.reviews.models import StatusUpdate
from reviewboard.reviews.signals import (review_request_published,
                                         status_update_request_run)
from reviewboard.webapi.models import WebAPIToken

from rbintegrations.baseci.errors import CIBuildError

if TYPE_CHECKING:
    from reviewboard.changedescs.models import ChangeDescription
    from reviewboard.reviews.models import ReviewRequest
    from reviewboard.scmtools.models import Repository
    from reviewboard.site.models import LocalSite


logger = logging.getLogger(__name__)


@dataclass
class BuildPrepData:
    """Data used in the preparation for a build.

    This contains state calculated by the base class and by a particular
    integration for use in configuring and running a build. It's also used
    to help create and manage :term:`status updates`.

    Version Added:
        3.1
    """

    #: The list of matching configurations for the build.
    #:
    #: Integrations can modify this list to narrow down the configurations
    #: further, if needed.
    #:
    #: By default, it will contain all configurations that match the
    #: integration configuration's conditions and :term:`Local Site`.
    #:
    #: Type:
    #:     list of reviewboard.integrations.models.IntegrationConfig
    configs: List[IntegrationConfig]

    #: The DiffSet being applied and tested against.
    #:
    #: Type:
    #:     reviewboard.diffviewer.models.DiffSet
    diffset: DiffSet

    #: The review request being tested against.
    #:
    #: Type:
    #:     reviewboard.reviews.models.review_request.ReviewRequest
    review_request: ReviewRequest

    #: The user owning the StatusUpdate and any reviews.
    #:
    #: Type:
    #:     django.contrib.auth.models.User
    user: User

    #: The optional Change Description a StatusUpdate should associate with.
    #:
    #: Type:
    #:     reviewboard.changedescs.models.ChangeDescription
    changedesc: Optional[ChangeDescription] = None

    #: Extra state set by the integration.
    #:
    #: The integration can use this to store and access any custom state
    #: needed for the build steps.
    #:
    #: Type:
    #:     dict
    extra_state: Dict = field(default_factory=dict)

    @property
    def local_site(self) -> LocalSite:
        """The Local Site these builds will be performed on.

        Type:
            reviewboard.site.models.LocalSite
        """
        return self.review_request.local_site

    @property
    def repository(self) -> Repository:
        """The repository the diff applies to.

        Type:
            reviewboard.scmtools.models.Repository
        """
        return self.review_request.repository

    @property
    def server_url(self) -> str:
        """The URL to the root of the server or Local Site.

        Type:
            str
        """
        return get_server_url(local_site=self.local_site)

    @property
    def api_token(self) -> WebAPIToken:
        """The API token used to communicate with Review Board.

        If one doesn't already exist for the user, one will be generated
        and stored.

        Type:
            reviewboard.webapi.models.WebAPIToken
        """
        user = self.user
        local_site = self.local_site

        try:
            return user.webapi_tokens.filter(local_site=local_site)[0]
        except IndexError:
            token_generator = token_generator_registry.get_default()

            return WebAPIToken.objects.generate_token(
                user,
                local_site=local_site,
                auto_generated=True,
                token_generator_id=token_generator.token_generator_id,
                token_info={'token_type': 'rbp'})


class BaseCIIntegration(Integration):
    """Base class for CI integrations.

    This manages the process of listening for new review requests or manual
    requests to run a build, setting up the necessary state (including any
    :term:`status updates`), and performing the build.

    Subclasses only need to implemenet:

    * :py:meth:`start_build`
    * :py:meth:`prepare_builds` (optional)

    And set some attributes:

    * :py:attr:`status_update_service_id`
    * :py:attr:`bot_username`
    * :py:attr:`bot_user_first_name`
    * :py:attr:`bot_user_last_name`
    """

    #: The ID of the service used for any status updates.
    #:
    #: This must be set by subclasses.
    #:
    #: Type:
    #:     str
    status_update_service_id: Optional[str] = None

    #: The username for the bot user to create/use for any status updates.
    #:
    #: This must be set by subclasses.
    #:
    #: Type:
    #:     str
    bot_username: Optional[str] = None

    #: The first name for the bot user.
    #:
    #: This must be set by subclasses.
    #:
    #: Type:
    #:     str
    bot_user_first_name: Optional[str] = None

    #: The last name for the bot user.
    #:
    #: This must be set by subclasses.
    #:
    #: Type:
    #:     str
    bot_user_last_name: Optional[str] = None

    def initialize(self):
        """Initialize the integration.

        This will begin listening for any signals needed to trigger builds or
        build preparation.
        """
        for attr_name in ('name',
                          'status_update_service_id',
                          'bot_username',
                          'bot_user_first_name',
                          'bot_user_last_name'):
            if not getattr(self, attr_name, None):
                raise ImproperlyConfigured('%s must set the "%s" attribute.'
                                           % (type(self).__name__, attr_name))

        SignalHook(self,
                   review_request_published,
                   self._on_review_request_published)
        SignalHook(self,
                   status_update_request_run,
                   self._on_status_update_request_run)

    def prepare_builds(
        self,
        prep_data: BuildPrepData,
    ) -> bool:
        """Prepare for builds.

        Subclasses can set this to set or modify any state in ``prep_data``
        before builds using this state are conducted.

        This should also return a boolean indicating whether to proceed with
        builds.

        Args:
            prep_data (BuildPrepData):
                The builds preparation data to modify or use.

        Returns:
            bool:
            ``True`` if the builds should proceed. ``False`` if builds should
            be skipped.
        """
        return True

    def start_build(
        self,
        *,
        prep_data: BuildPrepData,
        config: IntegrationConfig,
        status_update: StatusUpdate,
    ) -> None:
        """Start a new build.

        This will be called any time a build is being automatically started
        through a new published diff, or manually run via a
        :term:`status update`.

        Subclasses must override this to trigger a build. This should be a
        fast operation, and the implementation must not wait around for the
        results of a build. Instead, builds should communicate their status
        with Review Board via the API.

        ``status_update`` will already be in the correct running state.
        Subclasses should set this to a failure state if triggering a build
        fails. If an unexpected exception is raised, it will be automatically
        placed in an error state.

        A subclass may also set any relevant information (such as a URL) on the
        ``status_update``.

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
                There was an error invoking a build.

                Subclasses can raise this to set information for the
                :py:class:`~reviewboard.reviews.models.status_update.
                StatusUpdate`.
        """
        raise NotImplementedError

    def get_or_create_api_token(
        self,
        user: User,
        local_site: Optional[LocalSite],
    ) -> WebAPIToken:
        """Return or create an API token used to communicate with Review Board.

        Args:
            user (django.contrib.auth.models.User):
                The user that will own the token.

            local_site (reviewboard.site.models.LocalSite):
                The Local Site that the token will be restricted to.

        Returns:
            reviewboard.webapi.models.WebAPIToken:
            The resulting API token.
        """
        try:
            return user.webapi_tokens.filter(local_site=local_site)[0]
        except IndexError:
            token_generator = token_generator_registry.get_default()

            return WebAPIToken.objects.generate_token(
                user,
                local_site=local_site,
                auto_generated=True,
                token_generator_id=token_generator.token_generator_id,
                token_info={'token_type': 'rbp'})

    def get_or_create_user(self) -> User:
        """Return or create a bot user for this integration.

        The bot user will be associated with any status updates and reviews
        for the builds. It should also be used for any communication between
        the service or program running the build, and Review Board's API.
        """
        username = self.bot_username

        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            logger.info('Creating new user "%s" for CI integration "%s"',
                        username, self.name)

            siteconfig = SiteConfiguration.objects.get_current()
            noreply_email = siteconfig.get('mail_default_from')

            with transaction.atomic():
                try:
                    user = User.objects.create(
                        username=username,
                        email=noreply_email,
                        first_name=self.bot_user_first_name,
                        last_name=self.bot_user_last_name)
                except IntegrityError:
                    # Another process/thread beat us to it.
                    return User.objects.get(username=username)

                profile = user.get_profile()
                profile.should_send_email = False
                profile.save(update_fields=('should_send_email',))

                # Set up an avatar for this user, using the integration's
                # icons.
                avatar_service_id = URLAvatarService.avatar_service_id

                if avatar_services.is_enabled(avatar_service_id):
                    avatar_service = avatar_services.get_avatar_service(
                        avatar_service_id)
                    avatar_service.setup(user, self.icon_static_urls)

                return user

    def get_matching_configs(
        self,
        review_request: ReviewRequest,
    ) -> List[IntegrationConfig]:
        """Return configurations that match the review request and integration.

        This will return all configurations found in the database that are
        a match for the review request and its :term:`Local Site`.

        Subclasses can override this to further filter configurations, or
        filter this in :py:meth:`prepare_builds`.

        Args:
            review_request (reviewboard.reviews.models.review_request.
                            ReviewRequest):
                The review request being matched.

        Returns:
            list of reviewboard.integrations.models.IntegrationConfig:
            The list of matched configurations.
        """
        config_form_cls = self.config_form_cls
        local_site = review_request.local_site

        return [
            config
            for config in self.get_configs(local_site=local_site)
            if config.match_conditions(form_cls=config_form_cls,
                                       review_request=review_request)
        ]

    def update_status(
        self,
        status_update: StatusUpdate,
        *,
        state: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        url_text: Optional[str] = None,
        save: bool = True,
    ) -> None:
        """Update fields on a StatusUpdate.

        This will update only the provided fields, along with the timestamp,
        and optionally saving them to the database.

        This should be used when subclasses need to modify a
        :py:class:`~reviewboard.reviews.models.status_update.StatusUpdate`.

        Args:
            status_update (reviewboard.reviews.models.status_update.
                           StatusUpdate):
                The status update to modify.

            state (str, optional):
                A new state string.

            description (str, optional):
                A new description.

            url (str, optional):
                A new URL for build information.

            url_text (str, optional):
                New text for a URL for build information.

            save (bool, optional):
                Whether to save the resulting
                :py:class:`~reviewboard.reviews.models.status_update.
                StatusUpdate`.
        """
        fields: List[str] = []

        if state is not None and state != status_update.state:
            status_update.state = state
            fields.append('state')

        if (description is not None and
            description != status_update.description):
            status_update.description = description
            fields.append('description')

        if url is not None and url != status_update.url:
            status_update.url = url
            fields.append('url')

        if url_text is not None and url_text != status_update.url_text:
            status_update.url_text = url_text
            fields.append('url_text')

        if fields:
            status_update.timestamp = timezone.now()
            fields.append('timestamp')

            if save:
                if status_update.pk:
                    status_update.save(update_fields=fields)
                else:
                    status_update.save()

    def set_waiting(
        self,
        status_update: StatusUpdate,
        *,
        description: Optional[str] = None,
        url: Optional[str] = None,
        url_text: Optional[str] = None,
        save: bool = True,
    ) -> None:
        """Set a status update to "waiting to run" mode.

        Args:
            status_update (reviewboard.reviews.models.status_update.
                           StatusUpdate):
                The status update to modify.

            description (str, optional):
                A new description. If not provided, this will default to
                "waiting to run."

            url (str, optional):
                A new URL for build information.

            url_text (str, optional):
                New text for a URL for build information.

            save (bool, optional):
                Whether to save the resulting
                :py:class:`~reviewboard.reviews.models.status_update.
                StatusUpdate`.
        """
        self.update_status(status_update,
                           state=status_update.NOT_YET_RUN,
                           description=description or 'waiting to run.',
                           url=url,
                           url_text=url_text,
                           save=save)

    def set_starting(
        self,
        status_update: StatusUpdate,
        *,
        description: Optional[str] = None,
        url: Optional[str] = None,
        url_text: Optional[str] = None,
        save: bool = True,
    ) -> None:
        """Set a status update to "starting build" mode.

        Args:
            status_update (reviewboard.reviews.models.status_update.
                           StatusUpdate):
                The status update to modify.

            description (str, optional):
                A new description. If not provided, this will default to
                "starting build..."

            url (str, optional):
                A new URL for build information.

            url_text (str, optional):
                New text for a URL for build information.

            save (bool, optional):
                Whether to save the resulting
                :py:class:`~reviewboard.reviews.models.status_update.
                StatusUpdate`.
        """
        self.update_status(status_update,
                           state=status_update.PENDING,
                           description=description or 'starting build...',
                           url=url,
                           url_text=url_text,
                           save=save)

    def set_error(
        self,
        status_update: StatusUpdate,
        *,
        description: Optional[str] = None,
        url: Optional[str] = None,
        url_text: Optional[str] = None,
        save: bool = True,
    ) -> None:
        """Set a status update to "internal error" mode.

        Args:
            status_update (reviewboard.reviews.models.status_update.
                           StatusUpdate):
                The status update to modify.

            description (str, optional):
                A new description. If not provided, this will default to
                "internal error."

            url (str, optional):
                A new URL for build information.

            url_text (str, optional):
                New text for a URL for build information.

            save (bool, optional):
                Whether to save the resulting
                :py:class:`~reviewboard.reviews.models.status_update.
                StatusUpdate`.
        """
        self.update_status(status_update,
                           state=status_update.ERROR,
                           description=description or 'internal error.',
                           url=url,
                           url_text=url_text,
                           save=save)

    def _on_review_request_published(
        self,
        sender: Type[ReviewRequest],
        review_request: ReviewRequest,
        changedesc: Optional[ChangeDescription] = None,
        **kwargs,
    ) -> None:
        """Handle when a review request is published.

        Args:
            sender (type):
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
        # Don't build any review request that don't have matching configs.
        matching_configs = self.get_matching_configs(review_request)

        if not matching_configs:
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

        # Build the preparation data and find out if the subclass wants to
        # perform this build.
        user = self.get_or_create_user()
        prep_data = BuildPrepData(
            changedesc=changedesc,
            configs=matching_configs,
            diffset=diffset,
            review_request=review_request,
            user=user)

        if not self.prepare_builds(prep_data):
            return

        # Create a StatusUpdate for each matching configuration, and start
        # a build.
        status_update_service_id = self.status_update_service_id
        status_update_name = self.name

        has_create_for_integration = hasattr(StatusUpdate.objects,
                                             'create_for_integration')

        for config in matching_configs:
            run_manually = config.get('run_manually')
            timeout_secs = config.get('timeout')

            if has_create_for_integration:
                # Review Board >= 5.0.3
                status_update = StatusUpdate.objects.create_for_integration(
                    self,
                    config=config,
                    service_id=status_update_service_id,
                    user=user,
                    summary=status_update_name,
                    review_request=review_request,
                    change_description=changedesc,
                    can_retry=True,
                    timeout=timeout_secs,
                    starting_description='starting build...')
            else:
                # Review Board <= 5.0.2
                status_update = StatusUpdate(
                    service_id=status_update_service_id,
                    user=user,
                    summary=status_update_name,
                    review_request=review_request,
                    change_description=changedesc,
                    extra_data={
                        '__integration_config_id': config.pk,
                        'can_retry': True,
                    })

                # These will both save the StatusUpdate.
                if run_manually:
                    self.set_waiting(status_update)
                else:
                    self.set_starting(status_update)

            if not run_manually:
                self._run_start_build(prep_data=prep_data,
                                      config=config,
                                      status_update=status_update)

    def _on_status_update_request_run(
        self,
        sender: Type[StatusUpdate],
        status_update: StatusUpdate,
        config: Optional[IntegrationConfig] = None,
        **kwargs,
    ) -> None:
        """Handle a request to run or rerun a build.

        Args:
            sender (type):
                The sender of the signal.

            status_update (reviewboard.reviews.models.StatusUpdate):
                The status update being run.

            **kwargs (dict):
                Any additional keyword arguments.
        """
        assert self.status_update_service_id

        service_id: str = status_update.service_id

        if not service_id.startswith(self.status_update_service_id):
            # Ignore anything that's not this CI integration.
            return

        review_request: ReviewRequest = status_update.review_request
        changedesc = status_update.change_description

        if config is None:
            # This is a StatusUpdate created with Review Board < 5.0.3 or
            # rbintegrations < 3.1.
            #
            # We may have an __integration_config_id. This will only be
            # present if running Review Board < 5.0.3 with an upgraded
            # rbintegrations >= 3.1. If so, we can try to filter it.
            matching_configs = self.get_matching_configs(review_request)
            config_id = status_update.extra_data.get('__integration_config_id')

            if config_id is not None:
                matching_configs = [
                    _config
                    for _config in matching_configs
                    if _config.pk == config_id
                ]

            if not matching_configs:
                return
        else:
            # This is a StatusUpdate created with Review Board >= 5.0.3.
            matching_configs = [config]

        # If there's a change description associated with the status
        # update, then use the diff from that. Otherwise, choose the first
        # diffset on the review request.
        diffset: Optional[DiffSet] = None

        try:
            if changedesc:
                if 'diff' in changedesc.fields_changed:
                    new_diff = changedesc.fields_changed['diff']['added'][0]
                    diffset = DiffSet.objects.get(pk=new_diff[2])
            else:
                diffset = (
                    DiffSet.objects
                    .filter(history=review_request.diffset_history_id)
                    .earliest()
                )
        except DiffSet.DoesNotExist:
            logger.error('Unable to determine diffset when running '
                         '%s for status update %d',
                         self.name, status_update.pk)
            return

        if diffset is None:
            return

        prep_data = BuildPrepData(
            changedesc=changedesc,
            configs=matching_configs,
            diffset=diffset,
            review_request=review_request,
            user=status_update.user)

        if not self.prepare_builds(prep_data):
            return

        if len(prep_data.configs) != 1:
            logger.error('Unable to determine the right configuration when '
                         'running %s for status update %d (%d configurations '
                         'found).',
                         self.name, status_update.pk, len(prep_data.configs))
            return

        config = prep_data.configs[0]

        self.set_starting(status_update)
        self._run_start_build(prep_data=prep_data,
                              config=config,
                              status_update=status_update)

    def _run_start_build(
        self,
        *,
        prep_data: BuildPrepData,
        config: IntegrationConfig,
        status_update: StatusUpdate,
    ) -> None:
        """Run start_build, handling exceptions.

        This wraps the subclass's :py:meth:`start_build`, catching any
        exceptions and updating the
        :py:class:`~reviewboard.reviews.models.status_update.StatusUpdate`
        accordingly.

        Args:
            prep_data (BuildPrepData):
                The builds preparation data containing information for the
                build.

            config (reviewboard.integrations.models.IntegrationConfig):
                The configuration for the integration triggering this build.

            status_update (reviewboard.reviews.models.status_update.
                           StatusUpdate):
                The status update indicating the status of this build.
        """
        try:
            self.start_build(config=config,
                             prep_data=prep_data,
                             status_update=status_update)
        except CIBuildError as e:
            self.set_error(status_update,
                           description=str(e),
                           url=e.url,
                           url_text=e.url_text)
        except Exception as e:
            logger.exception('Unexpected error running %s build for review '
                             'request %s and configuration %s: %s',
                             self.name, prep_data.review_request.pk,
                             config.pk, e)
            self.set_error(status_update,
                           description='internal error: %s' % e)
