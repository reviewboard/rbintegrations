"""Form-related utilities.

Version Added:
    4.1
"""

from __future__ import annotations

from typing import TYPE_CHECKING


try:
    # Review Board >= 7.1
    from reviewboard.reviews.conditions import review_request_condition_choices
    from reviewboard.reviews.forms import ReviewRequestConditionsField
except ImportError:
    # Review Board < 7.1
    assert not TYPE_CHECKING

    from django.utils.translation import gettext_lazy as _
    from djblets.forms.fields import ConditionsField
    from djblets.util.typing import StrOrPromise
    from reviewboard.reviews.conditions import ReviewRequestConditionChoices

    if TYPE_CHECKING:
        from djblets.conditions.choices import ConditionChoices

    review_request_condition_choices = ReviewRequestConditionChoices()

    class ReviewRequestConditionsField(ConditionsField):
        """Compatibility field for selecting review request conditions.

        This can be removed once Review Board 7.1 or higher is required.

        Version Added:
            4.1
        """

        def __init__(
            self,
            *,
            choices: ConditionChoices = review_request_condition_choices,
            label: StrOrPromise = _('Conditions'),
            **kwargs,
        ) -> None:
            """Initialize the field.

            Args:
                choices (djblets.conditions.choices.ConditionChoices or type or
                         callable):
                    The registry of choices available for the conditions.

                    This defaults to the standard review request condition
                    choices. It can be overridden to provide a more
                    specialized list of conditions.

                label (str, optional):
                    A custom label to use for this field.

                **kwargs (dict):
                    Keyword arguments to pass to the parent class.
            """
            super().__init__(choices=review_request_condition_choices,
                             label=label,
                             **kwargs)


__all__ = (
    'ReviewRequestConditionsField',
    'review_request_condition_choices',
)
