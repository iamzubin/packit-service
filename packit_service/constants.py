FAQ_URL = "https://packit.dev/packit-as-a-service/#faq"
SANDCASTLE_WORK_DIR = "/sandcastle"
SANDCASTLE_IMAGE = "docker.io/usercont/sandcastle"
SANDCASTLE_DEFAULT_PROJECT = "myproject"
SANDCASTLE_PVC = "SANDCASTLE_PVC"

CONFIG_FILE_NAME = "packit-service.yaml"

TESTING_FARM_TRIGGER_URL = (
    "https://scheduler-testing-farm.apps.ci.centos.org/v0/trigger"
)

MSG_RETRIGGER = (
    "You can re-trigger build by adding a comment (`/packit {build}`) "
    "into this pull request."
)

PERMISSIONS_ERROR_WRITE_OR_ADMIN = (
    "Only users with write or admin permissions to the repository "
    "can trigger Packit-as-a-Service"
)

COPR_SUCC_STATE = "succeeded"
COPR_FAILED_STATE = "failed"
COPR_API_SUCC_STATE = 1
COPR_API_FAIL_STATE = 2

PG_COPR_BUILD_STATUS_FAILURE = "failure"
PG_COPR_BUILD_STATUS_SUCCESS = "success"

WHITELIST_CONSTANTS = {
    "approved_automatically": "approved_automatically",
    "waiting": "waiting",
    "approved_manually": "approved_manually",
}
