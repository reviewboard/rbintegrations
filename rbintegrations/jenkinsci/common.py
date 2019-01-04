"""Common functions used with the various Jenkins classes."""

from __future__ import unicode_literals

import logging

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from djblets.avatars.services import URLAvatarService
from djblets.siteconfig.models import SiteConfiguration
from reviewboard.avatars import avatar_services


logger = logging.getLogger(__name__)


def get_icon_static_urls():
    """Return the icons used for the integration.

    Returns:
        dict:
        A dictionary mapping icon sizes to URLs.
    """
    from rbintegrations.extension import RBIntegrationsExtension

    extension = RBIntegrationsExtension.instance

    return {
        '1x': extension.get_static_url('images/jenkinsci/icon.png'),
        '2x': extension.get_static_url('images/jenkinsci/icon@2x.png'),
    }


def get_or_create_jenkins_user():
    """Return a user to use for Jenkins CI.

    Returns:
        django.contrib.auth.models.User:
        A user instance.
    """
    try:
        return User.objects.get(username='jenkins-ci')
    except User.DoesNotExist:
        logger.info('Creating new user for Jenkins CI')
        siteconfig = SiteConfiguration.objects.get_current()
        noreply_email = siteconfig.get('mail_default_from')

        with transaction.atomic():
            try:
                user = User.objects.create(username='jenkins-ci',
                                           email=noreply_email,
                                           first_name='Jenkins',
                                           last_name='CI')
            except IntegrityError:
                # Another process/thread beat us to it.
                return User.objects.get(username='jenkins-ci')

            profile = user.get_profile()
            profile.should_send_email = False
            profile.save()

            if avatar_services.is_enabled(
                URLAvatarService.avatar_service_id):
                avatar_service = avatar_services.get_avatar_service(
                    URLAvatarService.avatar_service_id)
                # TODO: make somewhat higher-res versions for the main
                # avatar.
                avatar_service.setup(user, get_icon_static_urls())

            return user
