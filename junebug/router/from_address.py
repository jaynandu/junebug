from confmodel import Config
from confmodel.config import ConfigField
from confmodel.errors import ConfigError
from confmodel.fields import ConfigBool
import re
from uuid import UUID

from junebug.channel import Channel
from junebug.router import (
    BaseRouterWorker, InvalidRouterConfig, InvalidRouterDestinationConfig)


class ConfigUUID(ConfigField):
    """
    Field for validating UUIDs
    """
    field_type = 'uuid'

    def clean(self, value):
        try:
            return UUID(value)
        except (ValueError, AttributeError, TypeError):
            self.raise_config_error('is not a valid UUID')


class ConfigRegularExpression(ConfigField):
    """
    Field for validation regular expressions
    """
    field_type = 'regex'

    def clean(self, value):
        try:
            return re.compile(value)
        except (ValueError, TypeError, re.error) as e:
            self.raise_config_error(
                'is not a valid regular expression: {}'.format(e.message))


class FromAddressRouterConfig(BaseRouterWorker.CONFIG_CLASS):
    """
    Config for the FromAddressRouter.
    """
    channel = ConfigUUID(
        "The UUID of the channel to route messages for. This channel may not "
        "have an ``amqp_queue`` or ``mo_url`` parameter specified.",
        required=True, static=True)


class FromAddressRouterDestinationConfig(Config):
    """
    Config for each destination of the FromAddressRouter.
    """
    regular_expression = ConfigRegularExpression(
        "The regular expression to match the from address on for this "
        "destination. Any inbound messages with a from address that matches "
        "this regular expression will be sent to this destination.",
        required=True, static=True)
    default = ConfigBool(
        "Whether or not this destination is a default destination. Any "
        "messages that don't match any the destination regular expressions "
        "will be sent to the default destination(s).",
        required=False, default=False, static=True)


class FromAddressRouter(BaseRouterWorker):
    """
    A router that routes inbound messages based on the from address of the
    message
    """
    CONFIG_CLASS = FromAddressRouterConfig
    DESTINATION_CONFIG_CLASS = FromAddressRouterDestinationConfig

    @classmethod
    def validate_router_config(cls, api, config):
        try:
            config = cls.CONFIG_CLASS(config)
        except ConfigError as e:
            raise InvalidRouterConfig(e.message)

        channel_id = str(config.channel)
        d = Channel.from_id(
            api.redis, api.config, channel_id, api.service, api.plugins)

        def handle_missing_channel(err):
            raise InvalidRouterConfig(
                "Channel {} does not exist".format(channel_id))

        def ensure_valid_channel(channel):
            if channel.has_destination:
                raise InvalidRouterConfig(
                    "Channel {} already has a destination specified".format(
                        channel_id))

        d.addErrback(handle_missing_channel)
        return d.addCallback(ensure_valid_channel)

    @classmethod
    def validate_router_destination_config(cls, api, config):
        try:
            cls.DESTINATION_CONFIG_CLASS(config)
        except ConfigError as e:
            raise InvalidRouterDestinationConfig(e.message)

    def setup_router(self):
        pass

    def teardown_router(self):
        pass
