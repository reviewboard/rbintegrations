#!/bin/sh

# When we move to Review Board 4.0+, use:
#
#     rbext test -e rbintegrations.extension.RBIntegrationsExtension -- $*

rbext test -m rbintegrations -- $*
