#!/usr/bin/bash

set -x

source /src-packit-service/files/setup_env_in_openshift.sh

id

cat $HOME/.config/packit-service.yaml

alembic upgrade head

python3 -m pytest -vv tests_requre/
