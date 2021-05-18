Review Board Integrations
=========================

This extends `Review Board`_ 3.0+ with support for integrating with
third-party services, like Slack or automated code review services.

The latest supported version is automatically installed as part of Review
Board 3.0+, but maintained and released separately, allowing administrators to
get the latest and greatest integration support without having to update
Review Board.

.. _`Review Board`: https://www.reviewboard.org/


Integrations
============

Several integrations are provided out of the box, with more planned for future
releases. See the links below for a description of each integration and
instructions.


Chat
----

* `Mattermost <https://www.reviewboard.org/integrations/mattermost/>`_
* `Slack <https://www.reviewboard.org/integrations/slack/>`_


Continuous Integration
----------------------

* `CircleCI <https://www.reviewboard.org/integrations/circleci/>`_
* `Travis CI <https://www.reviewboard.org/integrations/travis-ci/>`_
* `Jenkins <https://www.reviewboard.org/integrations/jenkins/>`_


Task Tracking
-------------

* `Asana <https://www.reviewboard.org/integrations/asana/>`_
* `Trello <https://www.reviewboard.org/integrations/trello/>`_


Status Tracking
---------------

* `I Done This <https://www.reviewboard.org/integrations/idonethis/>`_


Getting Support
===============

We can help you get going with Review Board, and diagnose any issues that may
come up. There are two levels of support: Public community support, and
private premium support.

The public community support is available on our main `discussion list`_. We
generally respond to requests within a couple of days. This support works well
for general, non-urgent questions that don't need to expose confidential
information.

We can also provide more
`dedicated, private support <https://www.beanbaginc.com/support/contracts/>`_
for your organization through a support contract. We offer same-day responses
(generally within a few hours, if not sooner), confidential communications,
installation/upgrade assistance, emergency database repair, phone/chat (by
appointment), priority fixes for urgent bugs, and backports of urgent fixes to
older releases (when possible).

.. _`discussion list`: https://groups.google.com/group/reviewboard/


Our Happy Users
===============

There are thousands of companies and organizations using Review Board today.
We respect the privacy of our users, but some of them have asked to feature them
on the `Happy Users page`_.

If you're using Review Board, and you're a happy user,
`let us know! <https://groups.google.com/group/reviewboard/>`_.


.. _`Happy Users page`: https://www.reviewboard.org/users/


Reporting Bugs
==============

Hit a bug? Let us know by
`filing a bug report <https://www.reviewboard.org/bugs/new/>`_.

You can also look through the
`existing bug reports <https://www.reviewboard.org/bugs/>`_ to see if anyone
else has already filed the bug.


Contributing
============

Are you a developer? Do you want to add new integrations or improve our
existing integrations? Great! Let's help you get started.

First off, we have some handy guides:

* `Extending Review Board`_
* `Contributor Guide`_

We accept patches to the integrations, Review Board, RBTools, and other
related projects on `reviews.reviewboard.org
<https://reviews.reviewboard.org/>`_. (Please note that we do not accept pull
requests.)

Got any questions about anything related to Review Board and development? Head
on over to our `development discussion list`_.

.. _`Extending Review Board`:
   https://www.reviewboard.org/docs/manual/latest/webapi
.. _`Contributor Guide`: https://www.reviewboard.org/docs/codebase/dev/
.. _`development discussion list`:
   https://groups.google.com/group/reviewboard-dev/


Related Projects
================

* `Review Board`_ -
  Our powerful, open source code review tool.
* Djblets_ -
  Our pack of Django utilities for datagrids, API, extensions, integrations,
  and more. Used by Review Board.
* ReviewBot_ -
  Pluggable, automated code review for Review Board.

.. _Djblets: https://github.com/djblets/djblets/
.. _ReviewBot: https://github.com/reviewboard/ReviewBot/
