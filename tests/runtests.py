#!/usr/bin/env python

import sys

import reviewboard
from reviewboard.cmdline.rbext import RBExt


def main(argv):
    print('Python %s.%s.%s' % (sys.version_info[:3]))
    print('Review Board %s' % reviewboard.get_version_string())

    # When we drop Review Board 3.x support, we can remove -s and -m and
    # switch to:
    #
    #     --app beanbag_licensing.tests
    #     -e rbpowerpack.extension.PowerPackExtension
    sys.exit(RBExt().run([
        'test',
        '-m', 'rbintegrations',
        '--',
    ] + argv))


if __name__ == '__main__':
    main(sys.argv[1:])
