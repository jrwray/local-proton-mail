#!/bin/bash
# Run to start local-proton-mail on Linux. Opens http://127.0.0.1:7861 in your browser.
# Press Ctrl+C to stop it. Agents can use "./pmail.sh start" / "./pmail.sh stop" instead.
"$(dirname "$0")/pmail.sh" serve
