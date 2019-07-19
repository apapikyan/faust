from contextlib import suppress
from typing import Any, Callable, Optional, Tuple, cast
from faust.types.app import AppT
from faust.types.core import K, OpenHeadersArg, V
from faust.types.codecs import CodecArg
from faust.types.models import ModelArg
from faust.types.serializers import KT, SchemaT, VT
from faust.types.tuples import Message

__all__ = ['Schema']


class Schema(SchemaT):

    def __init__(self, *,
                 key_type: ModelArg = None,
                 value_type: ModelArg = None,
                 key_serializer: CodecArg = None,
                 value_serializer: CodecArg = None) -> None:
        self.update(
            key_type=key_type,
            value_type=value_type,
            key_serializer=key_serializer,
            value_serializer=value_serializer,
        )

    def update(self, *,
               key_type: ModelArg = None,
               value_type: ModelArg = None,
               key_serializer: CodecArg = None,
               value_serializer: CodecArg = None) -> None:
        if key_type is not None:
            self.key_type = key_type
        if value_type is not None:
            self.value_type = value_type
        if key_serializer is not None:
            self.key_serializer = key_serializer
        if value_serializer is not None:
            self.value_serializer = value_serializer
        if self.key_serializer is None and key_type:
            self.key_serializer = _model_serializer(key_type)
        if self.value_serializer is None and value_type:
            self.value_serializer = _model_serializer(value_type)

    def loads_key(self, app: AppT, message: Message, *,
                  loads: Callable = None,
                  serializer: CodecArg = None) -> KT:
        if loads is None:
            loads = app.serializers.loads_key
        return cast(KT, loads(
            self.key_type, message.key,
            serializer=serializer or self.key_serializer,
        ))

    def loads_value(self, app: AppT, message: Message, *,
                    loads: Callable = None,
                    serializer: CodecArg = None) -> VT:
        if loads is None:
            loads = app.serializers.loads_value
        return loads(
            self.value_type, message.value,
            serializer=serializer or self.value_serializer,
        )

    def dumps_key(self, app: AppT, key: K, *,
                  serializer: CodecArg = None,
                  headers: OpenHeadersArg) -> Tuple[Any, OpenHeadersArg]:
        payload = app.serializers.dumps_key(
            self.key_type, key,
            serializer=serializer or self.key_serializer,
        )
        return payload, self.on_dumps_key_prepare_headers(key, headers)

    def dumps_value(self, app: AppT, value: V, *,
                    serializer: CodecArg = None,
                    headers: OpenHeadersArg) -> Tuple[Any, OpenHeadersArg]:
        payload = app.serializers.dumps_value(
            self.value_type, value,
            serializer=serializer or self.value_serializer,
        )
        return payload, self.on_dumps_value_prepare_headers(value, headers)

    def on_dumps_key_prepare_headers(
            self, key: V, headers: OpenHeadersArg) -> OpenHeadersArg:
        return headers

    def on_dumps_value_prepare_headers(
            self, value: V, headers: OpenHeadersArg) -> OpenHeadersArg:
        return headers

    def __repr__(self) -> str:
        KT = self.key_type if self.key_type else '*default*'
        VT = self.key_type if self.value_type else '*default*'
        ks = self.key_serializer if self.key_serializer else '*default*'
        vs = self.value_serializer if self.value_serializer else '*default*'
        return (f'<{type(self).__name__}: '
                f'KT={KT} ({ks}) '
                f'VT={VT} ({vs})'
                f'>')


def _model_serializer(typ: Any) -> Optional[CodecArg]:
    with suppress(AttributeError):
        return typ._options.serializer
