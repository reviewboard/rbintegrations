#!/usr/bin/env python3

import sys

import pytest
import reviewboard


if __name__ == '__main__':
    print('Python %s.%s.%s' % (sys.version_info[:3]))
    print('Review Board %s' % reviewboard.get_version_string())

    sys.exit(pytest.main(sys.argv[1:]))
