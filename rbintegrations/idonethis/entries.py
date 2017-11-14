"""Entries that can be posted to I Done This on behalf of the user."""

import re
import string

from reviewboard.admin.server import build_server_url


# Entry types.
REPLY_PUBLISHED = 'reply_published'
REVIEW_REQUEST_COMPLETED = 'review_request_completed'
REVIEW_REQUEST_DISCARDED = 'review_request_discarded'
REVIEW_REQUEST_PUBLISHED = 'review_request_published'
REVIEW_REQUEST_REOPENED = 'review_request_reopened'
REVIEW_REQUEST_UPDATED = 'review_request_updated'
REVIEW_PUBLISHED = 'review_published'
REVIEW_PUBLISHED_ISSUE = 'review_published_issue'
REVIEW_PUBLISHED_ISSUES = 'review_published_issues'
REVIEW_PUBLISHED_SHIPIT = 'review_published_shipit'
REVIEW_PUBLISHED_SHIPIT_ISSUE = 'review_published_shipit_issue'
REVIEW_PUBLISHED_SHIPIT_ISSUES = 'review_published_shipit_issues'


# Default template strings for each entry type. Should not be translated.
default_template_strings = {
    REPLY_PUBLISHED:
        'Replied to review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_REQUEST_COMPLETED:
        'Completed review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_REQUEST_DISCARDED:
        'Discarded review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_REQUEST_PUBLISHED:
        'Published review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_REQUEST_REOPENED:
        'Reopened review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_REQUEST_UPDATED:
        'Updated review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_PUBLISHED:
        'Posted review on review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_PUBLISHED_ISSUE:
        'Posted review (1 issue) on review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_PUBLISHED_ISSUES:
        'Posted review (${num_issues} issues) on review request '
        '${review_request_id}: ${summary} ${url} ${group_tags}',
    REVIEW_PUBLISHED_SHIPIT:
        'Posted Ship it! on review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_PUBLISHED_SHIPIT_ISSUE:
        'Posted Ship it! (1 issue) on review request ${review_request_id}: '
        '${summary} ${url} ${group_tags}',
    REVIEW_PUBLISHED_SHIPIT_ISSUES:
        'Posted Ship it! (${num_issues} issues) on review request '
        '${review_request_id}: ${summary} ${url} ${group_tags}',
}


# Tags allow only alphanumeric characters and underscore.
INVALID_TAG_CHARS_RE = re.compile(r'\W')
MULTIPLE_WHITESPACE_RE = re.compile(r'\s+')


def format_template_string(template_string, num_issues=0, review_request=None,
                           review_request_id=None, summary=None,
                           group_tags=None, url=None):
    """Format a template string for an I Done This entry.

    Args:
        template_string (unicode):
            The template string to substitute arguments into.

        num_issues (int, optional):
            Number of issues opened in a review, used for ``${num_issues}``.

        review_request (reviewboard.reviews.models.review_request.
                        ReviewRequest, optional):
            Review request used for the remaining template string arguments.
            Any arguments provided separately will override the review request.

        review_request_id (int, optional):
            Review request ID, used for ``${review_request_id}``.

        summary (unicode, optional):
            Review request summary, used for ``${summary}``.

        group_tags (unicode, optional):
            Reviewer group names as #tags, used for ``${group_tags}``.

        url (unicode, optional):
            URL for the review request, review, or reply, used for ``${url}``.

    Returns:
        unicode:
        Template string with replaced arguments and cleaned whitespace.

    Raises:
        ValueError:
            Raised if the template string is invalid.

        KeyError:
            Raised if the template string contains unrecognized arguments.
    """
    if review_request:
        review_request_id = review_request_id or review_request.display_id
        summary = summary or review_request.summary
        url = url or build_server_url(review_request.get_absolute_url())

        if not group_tags:
            # Tags allow only alphanumeric characters and underscore.
            group_names = review_request.target_groups.values_list('name',
                                                                   flat=True)
            group_tags = ' '.join(
                '#%s' % INVALID_TAG_CHARS_RE.sub('_', group_name)
                for group_name in group_names)

    result = string.Template(template_string).substitute(
        num_issues=num_issues,
        review_request_id=review_request_id,
        summary=summary,
        group_tags=group_tags,
        url=url)

    return MULTIPLE_WHITESPACE_RE.sub(' ', result).strip()
