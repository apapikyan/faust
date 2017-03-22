"""Abstract types for static typing."""
import abc
import asyncio
from typing import (
    Any, AsyncIterable, Awaitable, Callable, FrozenSet, Generator,
    Iterable, List, Mapping, MutableMapping, MutableSequence,
    NamedTuple, Optional, Pattern, Sequence, Tuple, Type, Union,
)

__all__ = [
    'K', 'V', 'SerializerT', 'SerializerArg',
    'Topic', 'Message', 'Request', 'ConsumerCallback',
    'KeyDecodeErrorCallback', 'ValueDecodeErrorCallback',
    'ServiceT', 'AppT',
]

#: Shorthand for the type of a key (Any for now).
K = Any

#: Shorthand for the type of a value (Any for now).
V = Any


class SerializerT(metaclass=abc.ABCMeta):
    """Abstract type for Serializer.

    See Also:
        :class:`faust.utils.serialization.Serializer`.
    """

    @abc.abstractmethod
    def dumps(self, obj: Any) -> bytes:
        ...

    @abc.abstractmethod
    def loads(self, s: bytes) -> Any:
        ...

    @abc.abstractmethod
    def clone(self, *children: 'SerializerT') -> 'SerializerT':
        ...

    @abc.abstractmethod
    def __or__(self, other: Any) -> Any:
        ...


# `serializer` argument can be str or serializer instance.
SerializerArg = Union[SerializerT, str]


class Topic(NamedTuple):
    topics: Sequence[str]
    pattern: Pattern
    type: Type
    key_serializer: SerializerArg


class Message(NamedTuple):
    topic: str
    partition: int
    offset: int
    timestamp: float
    timestamp_type: str
    key: bytes
    value: bytes
    checksum: bytes
    serialized_key_size: int
    serialized_value_size: int


class Request(NamedTuple):
    app: 'AppT'
    key: K
    message: Message


#: Callback called by :class:`faust.transport.base.Consumer` whenever
#: a message is received.
ConsumerCallback = Callable[[Topic, K, V], Awaitable]

#: Callback called by :class:`faust.transport.base.Consumer` whenever
#: a message key cannot be decoded/deserialized.
KeyDecodeErrorCallback = Callable[[Exception, Message], Awaitable]

#: Callback called by :class:`faust.transport.base.Consumer` whenever
#: a message value cannot be decoded/deserialized.
ValueDecodeErrorCallback = Callable[[Exception, Message], Awaitable]


class ServiceT(metaclass=abc.ABCMeta):
    """Abstract type for an asynchronous service that can be started/stopped.

    See Also:
        :class:`faust.utils.service.Service`.
    """

    shutdown_timeout: float
    loop: asyncio.AbstractEventLoop = None

    @abc.abstractmethod
    async def __aenter__(self) -> 'ServiceT':
        ...

    @abc.abstractmethod
    async def __aexit__(*exc_info) -> None:
        ...

    @abc.abstractmethod
    def on_init(self) -> None:
        ...

    @abc.abstractmethod
    async def on_start(self) -> None:
        ...

    @abc.abstractmethod
    async def on_stop(self) -> None:
        ...

    @abc.abstractmethod
    async def on_shutdown(self) -> None:
        ...

    @abc.abstractmethod
    async def start(self) -> None:
        ...

    @abc.abstractmethod
    async def maybe_start(self) -> None:
        ...

    @abc.abstractmethod
    async def stop(self) -> None:
        ...

    @abc.abstractmethod
    def add_poller(self, callback: Callable) -> None:
        ...

    @property
    @abc.abstractmethod
    def state(self) -> str:
        ...


class EventOptions:
    serializer: SerializerArg
    namespace: str

    # Index: Flattened view of __annotations__ in MRO order.
    fields: Mapping[str, Type]

    # Index: Set of required field names, for fast argument checking.
    fieldset: FrozenSet[str]

    # Index: Set of optional field names, for fast argument checking.
    optionalset: FrozenSet[str]


class EventT:
    # uses __init_subclass__ so cannot use ABCMeta

    req: Request

    _options: EventOptions

    @classmethod
    def as_schema(cls) -> Mapping:
        ...

    @classmethod
    def loads(cls, s: bytes,
              *,
              default_serializer: SerializerArg = None,
              **kwargs) -> 'EventT':
        ...

    def from_message(cls, key: K, message: Message, app: 'AppT',
                     *,
                     default_serializer: SerializerArg = None) -> 'EventT':
        ...

    def dumps(self) -> bytes:
        ...

    def derive(self, *events: 'EventT', **fields) -> 'EventT':
        ...

    async def forward(self, topic: Union[str, Topic]) -> None:
        ...


class FieldDescriptorT:
    field: str
    type: Type
    event: Type
    required: bool = True
    default: Any = None  # noqa: E704


class InputStreamT(Iterable, AsyncIterable):
    queue: asyncio.Queue

    @abc.abstractmethod
    async def put(self, value: V) -> None:
        ...

    @abc.abstractmethod
    async def next(self) -> Any:
        ...

    @abc.abstractmethod
    async def join(self, timeout: float = None):
        ...


class CoroCallbackT:

    def __init__(self, inbox: InputStreamT,
                 *,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        ...

    async def send(self, value: V, callback: Callable) -> None:
        ...

    async def join(self) -> None:
        ...

    async def drain(self, callback: Callable) -> None:
        ...


class EventRefT(metaclass=abc.ABCMeta):
    offset: int


class ConsumerT(ServiceT):

    id: int
    topic: Topic
    transport: 'TransportT'
    commit_interval: float

    @abc.abstractmethod
    async def _commit(self, offset: int) -> None:
        ...

    @abc.abstractmethod
    async def register_timers(self) -> None:
        ...

    @abc.abstractmethod
    async def on_message(self, message: Message) -> None:
        ...

    @abc.abstractmethod
    def to_KV(self, message: Message) -> Tuple[K, V]:
        ...

    @abc.abstractmethod
    def track_event(self, event: EventT, offset: int) -> None:
        ...

    @abc.abstractmethod
    def on_event_ready(self, ref: EventRefT) -> None:
        ...


class ProducerT(ServiceT):
    transport: 'TransportT'

    @abc.abstractmethod
    async def send(
            self,
            topic: str,
            key: Optional[bytes],
            value: bytes) -> Awaitable:
        ...

    @abc.abstractmethod
    async def send_and_wait(
            self,
            topic: str,
            key: Optional[bytes],
            value: bytes) -> Awaitable:
        ...


class TransportT(metaclass=abc.ABCMeta):
    Consumer: Type
    Producer: Type

    app: 'AppT'
    url: str
    loop: asyncio.AbstractEventLoop

    def create_consumer(self, topic: Topic, callback: ConsumerCallback,
                        **kwargs) -> ConsumerT:
        ...

    def create_producer(self, **kwargs) -> ProducerT:
        ...


class AppT(ServiceT):
    """Abstract type for the Faust application.

    See Also:
        :class:`faust.App`.
    """

    Stream: Type

    id: str
    url: str
    client_id: str
    commit_interval: float
    key_serializer: SerializerArg
    value_serializer: SerializerArg
    num_standby_replicas: int
    replication_factor: int

    @abc.abstractmethod
    def add_task(self, task: Union[Generator, Awaitable]) -> asyncio.Future:
        ...

    @abc.abstractmethod
    def stream(self, topic: Topic,
               coroutine: Callable = None,
               processors: Sequence[Callable] = None,
               **kwargs) -> 'StreamT':
        ...

    @abc.abstractmethod
    def add_source(self, stream: 'StreamT') -> None:
        ...

    @abc.abstractmethod
    def new_stream_name(self) -> str:
        ...

    @abc.abstractmethod
    async def send(
            self, topic: Union[Topic, str], key: K, event: EventT,
            *,
            wait: bool = True,
            key_serializer: SerializerArg = None) -> Awaitable:
        ...

    @property
    @abc.abstractmethod
    def transport(self) -> TransportT:
        ...


class StreamT(ServiceT):

    app: AppT = None
    topics: MutableSequence[Topic] = None
    name: str = None
    outbox: asyncio.Queue = None
    join_strategy: 'JoinT' = None

    children: List['StreamT'] = None

    @classmethod
    @abc.abstractmethod
    def from_topic(cls, topic: Topic,
                   *,
                   coroutine: Callable = None,
                   processors: Sequence[Callable] = None,
                   loop: asyncio.AbstractEventLoop = None,
                   **kwargs) -> 'StreamT':
        ...

    def __init__(self, name: str = None,
                 topics: Sequence[Topic] = None,
                 processors: MutableMapping[Topic, Sequence[Callable]] = None,
                 coroutines: MutableMapping[Topic, CoroCallbackT] = None,
                 children: List['StreamT'] = None,
                 join_strategy: 'JoinT' = None,
                 app: AppT = None,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        # need this to initialize Service.__init__ (!)
        super().__init__(loop=loop)  # type: ignore

    @abc.abstractmethod
    def bind(self, app: AppT) -> 'StreamT':
        ...

    @abc.abstractmethod
    def info(self) -> Mapping[str, Any]:
        ...

    @abc.abstractmethod
    def clone(self, **kwargs) -> 'StreamT':
        ...

    @abc.abstractmethod
    def combine(self, *nodes: 'StreamT', **kwargs):
        ...

    @abc.abstractmethod
    def join(self, *fields: FieldDescriptorT) -> 'StreamT':
        ...

    @abc.abstractmethod
    def left_join(self, *fields: FieldDescriptorT) -> 'StreamT':
        ...

    @abc.abstractmethod
    def inner_join(self, *fields: FieldDescriptorT) -> 'StreamT':
        ...

    @abc.abstractmethod
    def outer_join(self, *fields: FieldDescriptorT) -> 'StreamT':
        ...

    @abc.abstractmethod
    async def on_message(self, topic: Topic, key: K, value: V) -> None:
        ...

    @abc.abstractmethod
    async def process(self, key: K, value: V) -> V:
        ...

    @abc.abstractmethod
    async def on_done(self, value: V = None) -> None:
        ...

    @abc.abstractmethod
    async def subscribe(self, topic: Topic,
                        *,
                        processors: Sequence[Callable] = None,
                        coroutine: Callable = None) -> None:
        ...

    @abc.abstractmethod
    async def unsubscribe(self, topic: Topic) -> None:
        ...

    @abc.abstractmethod
    def on_key_decode_error(self, exc: Exception, message: Message) -> None:
        ...

    @abc.abstractmethod
    def on_value_decode_error(self, exc: Exception, message: Message) -> None:
        ...

    @abc.abstractmethod
    def __and__(self, other: 'StreamT') -> 'StreamT':
        ...

    @abc.abstractmethod
    def __copy__(self) -> 'StreamT':
        ...


class JoinT(metaclass=abc.ABCMeta):
    fields: MutableMapping[Type, FieldDescriptorT]
    stream: StreamT

    @abc.abstractmethod
    async def process(_self, event: EventT) -> Optional[EventT]:
        ...
