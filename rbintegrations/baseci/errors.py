"""Errors for builds.

Version Added:
    3.1
"""

from typing import Optional


class CIBuildError(Exception):
    """An error invoking a build over CI.

    Version Added:
        3.1
    """

    ######################
    # Instance variables #
    ######################

    #: An optional URL containing information on the build.
    #:
    #: Type:
    #:     str
    url: Optional[str]

    #: The text for an optional URL containing information on the build.
    #:
    #: Type:
    #:     str
    url_text: Optional[str]

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        url: Optional[str] = None,
        url_text: Optional[str] = None,
    ) -> None:
        """Initialize the error.

        Args:
            message (str, optional):
                An explicit error message for the error. This will be shown
                on the status update, and should follow standard conventions
                (start as lowercase, end with a period).

                If not provided, a default is used instead.

            url (str, optional):
                An optional URL containing information on the build.

            url_text (str, optional):
                The text for an optional URL containing information on the
                build.
        """
        super().__init__(message or 'error starting the build.')

        self.url = url
        self.url_text = url_text
