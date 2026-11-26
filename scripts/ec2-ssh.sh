#!/usr/bin/env bash
# Open a shell on the EC2 server, or run one command there, in /opt/whitespace.
#
#   make ec2-ssh                                    interactive shell
#   scripts/ec2-ssh.sh docker compose ps            run a command
#   scripts/ec2-ssh.sh docker compose logs -f api   follow the API logs
#
# Host and key come from deploy/ec2/.env.deploy.
set -euo pipefail
cd "$(dirname "$0")/.."

CONF=deploy/ec2/.env.deploy
[ -f "$CONF" ] || { echo "Missing $CONF" >&2; exit 1; }
# shellcheck disable=SC1090
source "$CONF"
: "${EC2_HOST:?set EC2_HOST in $CONF}"
EC2_KEY="${EC2_KEY:-$HOME/.ssh/whitespace-ec2.pem}"
EC2_KEY="${EC2_KEY/#\~/$HOME}"

if [ $# -eq 0 ]; then
  exec ssh -t -i "$EC2_KEY" -o StrictHostKeyChecking=accept-new "ubuntu@$EC2_HOST" \
    'cd /opt/whitespace && exec bash -l'
fi
exec ssh -i "$EC2_KEY" -o StrictHostKeyChecking=accept-new "ubuntu@$EC2_HOST" \
  "cd /opt/whitespace && $*"
