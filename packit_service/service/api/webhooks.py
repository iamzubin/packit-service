# MIT License
#
# Copyright (c) 2019 Red Hat, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import hmac
from hashlib import sha1
from http import HTTPStatus
from logging import getLogger

from flask import request

try:
    from flask_restx import Namespace, Resource, fields
except ModuleNotFoundError:
    from flask_restplus import Namespace, Resource, fields

from packit_service.celerizer import celery_app
from packit_service.config import ServiceConfig
from packit_service.service.api.errors import ValidationFailed

logger = getLogger("packit_service")
config = ServiceConfig.get_service_config()

ns = Namespace("webhooks", description="Webhooks")

# Just to be able to specify some payload in Swagger UI
ping_payload = ns.model(
    "Github webhook ping",
    {
        "zen": fields.String(required=False),
        "hook_id": fields.String(required=False),
        "hook": fields.String(required=False),
    },
)

ping_payload_gitlab = ns.model(
    "Gitlab webhook ping",
    {
        "zen": fields.String(required=False),
        "hook_id": fields.String(required=False),
        "hook": fields.String(required=False),
    },
)


@ns.route("/github")
class GithubWebhook(Resource):
    @ns.response(HTTPStatus.OK, "Webhook accepted, returning reply")
    @ns.response(HTTPStatus.ACCEPTED, "Webhook accepted, request is being processed")
    @ns.response(HTTPStatus.BAD_REQUEST, "Bad request data")
    @ns.response(HTTPStatus.UNAUTHORIZED, "X-Hub-Signature validation failed")
    # Just to be able to specify some payload in Swagger UI
    @ns.expect(ping_payload)
    def post(self):
        """
        A webhook used by Packit-as-a-Service GitHub App.
        """
        msg = request.json

        if not msg:
            logger.debug("/webhooks/github: we haven't received any JSON data.")
            return "We haven't received any JSON data.", HTTPStatus.BAD_REQUEST

        if all([msg.get("zen"), msg.get("hook_id"), msg.get("hook")]):
            logger.debug(f"/webhooks/github received ping event: {msg['hook']}")
            return "Pong!", HTTPStatus.OK

        try:
            self.validate_signature()
        except ValidationFailed as exc:
            logger.info(f"/webhooks/github {exc}")
            return str(exc), HTTPStatus.UNAUTHORIZED

        if not self.interested():
            return "Thanks but we don't care about this event", HTTPStatus.ACCEPTED

        # TODO: define task names at one place
        celery_app.send_task(
            name="task.steve_jobs.process_message", kwargs={"event": msg}
        )

        return "Webhook accepted. We thank you, Github.", HTTPStatus.ACCEPTED

    @staticmethod
    def validate_signature():
        """
        https://developer.github.com/webhooks/securing/#validating-payloads-from-github
        https://developer.github.com/webhooks/#delivery-headers
        """
        if "X-Hub-Signature" not in request.headers:
            if config.validate_webhooks:
                msg = "X-Hub-Signature not in request.headers"
                logger.warning(msg)
                raise ValidationFailed(msg)
            else:
                # don't validate signatures when testing locally
                logger.debug("Ain't validating signatures.")
                return

        sig = request.headers["X-Hub-Signature"]
        if not sig.startswith("sha1="):
            msg = f"Digest mode in X-Hub-Signature {sig!r} is not sha1."
            logger.warning(msg)
            raise ValidationFailed(msg)

        webhook_secret = config.webhook_secret.encode()
        if not webhook_secret:
            msg = "'webhook_secret' not specified in the config."
            logger.error(msg)
            raise ValidationFailed(msg)

        signature = sig.split("=")[1]
        mac = hmac.new(webhook_secret, msg=request.get_data(), digestmod=sha1)
        digest_is_valid = hmac.compare_digest(signature, mac.hexdigest())
        if digest_is_valid:
            logger.debug("Payload signature OK.")
        else:
            msg = "Payload signature validation failed."
            logger.warning(msg)
            logger.debug(f"X-Hub-Signature: {sig!r} != computed: {mac.hexdigest()}")
            raise ValidationFailed(msg)

    @staticmethod
    def interested():
        """
        Check X-GitHub-Event header for events we know we give a f...
        ...finely prepared response to.
        :return: False if we are not interested in this kind of event
        """
        uninteresting_events = {
            "integration_installation",
            "integration_installation_repositories",
        }
        event_type = request.headers.get("X-GitHub-Event")
        uuid = request.headers.get("X-GitHub-Delivery")
        _interested = event_type not in uninteresting_events

        logger.debug(
            f"{event_type} {uuid}{' (not interested)' if not _interested else ''}"
        )
        return _interested


@ns.route("/gitlab")
class GitlabWebhook(Resource):
    @ns.response(HTTPStatus.OK, "Webhook accepted, returning reply")
    @ns.response(HTTPStatus.ACCEPTED, "Webhook accepted, request is being processed")
    @ns.response(HTTPStatus.BAD_REQUEST, "Bad request data")
    @ns.response(HTTPStatus.UNAUTHORIZED, "X-Gitlab-Token validation failed")
    # Just to be able to specify some payload in Swagger UI
    @ns.expect(ping_payload_gitlab)
    def post(self):
        """
        A webhook used by Packit-as-a-Service Gitlab hook.
        """
        msg = request.json

        if not msg:
            logger.debug("/webhooks/gitlab: we haven't received any JSON data.")
            return "We haven't received any JSON data.", HTTPStatus.BAD_REQUEST

        if all([msg.get("zen"), msg.get("hook_id"), msg.get("hook")]):
            logger.debug(f"/webhooks/gitlab received ping event: {msg['hook']}")
            return "Pong!", HTTPStatus.OK

        try:
            self.validate_token()
        except ValidationFailed as exc:
            logger.info(f"/webhooks/gitlab {exc}")
            return str(exc), HTTPStatus.UNAUTHORIZED

        if not self.interested():
            return "Thanks but we don't care about this event", HTTPStatus.ACCEPTED

        # TODO: define task names at one place
        celery_app.send_task(
            name="task.steve_jobs.process_message", kwargs={"event": msg}
        )

        return "Webhook accepted. We thank you, Gitlab.", HTTPStatus.ACCEPTED

    @staticmethod
    def validate_token():
        """
        https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#secret-token
        """
        if "X-Gitlab-Token" not in request.headers:
            if config.validate_webhooks:
                msg = "X-Gitlab-Token not in request.headers"
                logger.warning(msg)
                raise ValidationFailed(msg)
            else:
                # don't validate signatures when testing locally
                logger.debug("Ain't validating token.")
                return

        token = request.headers["X-Gitlab-Token"]

        # Find a better solution
        if token != config.gitlab_webhook_token:
            raise ValidationFailed("Payload token validation failed.")

        logger.debug("Payload token is OK.")

    @staticmethod
    def interested():
        """
        Check object_kind in request body for events we know we give a f...
        ...finely prepared response to.
        :return: False if we are not interested in this kind of event
        """

        interesting_events = {
            "Note Hook",
            "Merge Request Hook",
        }
        event_type = request.headers.get("X-Gitlab-Event")
        _interested = event_type in interesting_events

        logger.debug(f"{event_type} {' (not interested)' if not _interested else ''}")
        return _interested
