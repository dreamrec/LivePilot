from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AuthType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SPLICE: _ClassVar[AuthType]
    AUTH0: _ClassVar[AuthType]

class SampleType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    All: _ClassVar[SampleType]
    Loop: _ClassVar[SampleType]
    OneShot: _ClassVar[SampleType]

class CollectionAccess(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AccessNotSpecified: _ClassVar[CollectionAccess]
    AccessPrivate: _ClassVar[CollectionAccess]
    AccessPublic: _ClassVar[CollectionAccess]

class FlagValueType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    Boolean: _ClassVar[FlagValueType]
    String: _ClassVar[FlagValueType]
SPLICE: AuthType
AUTH0: AuthType
All: SampleType
Loop: SampleType
OneShot: SampleType
AccessNotSpecified: CollectionAccess
AccessPrivate: CollectionAccess
AccessPublic: CollectionAccess
Boolean: FlagValueType
String: FlagValueType

class LogoutRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LogoutResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ValidateLoginRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ValidateLoginResponse(_message.Message):
    __slots__ = ("User",)
    USER_FIELD_NUMBER: _ClassVar[int]
    User: User
    def __init__(self, User: _Optional[_Union[User, _Mapping]] = ...) -> None: ...

class GetSessionRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetSessionResponse(_message.Message):
    __slots__ = ("Auth",)
    AUTH_FIELD_NUMBER: _ClassVar[int]
    Auth: Auth
    def __init__(self, Auth: _Optional[_Union[Auth, _Mapping]] = ...) -> None: ...

class Auth(_message.Message):
    __slots__ = ("Token", "SubKey", "SubChannel", "AuthType")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    SUBKEY_FIELD_NUMBER: _ClassVar[int]
    SUBCHANNEL_FIELD_NUMBER: _ClassVar[int]
    AUTHTYPE_FIELD_NUMBER: _ClassVar[int]
    Token: str
    SubKey: str
    SubChannel: str
    AuthType: AuthType
    def __init__(self, Token: _Optional[str] = ..., SubKey: _Optional[str] = ..., SubChannel: _Optional[str] = ..., AuthType: _Optional[_Union[AuthType, str]] = ...) -> None: ...

class User(_message.Message):
    __slots__ = ("ID", "Username", "Bio", "AvatarURL", "Location", "Email", "SoundsStatus", "Credits", "Features", "SoundsPlan", "UUID")
    class FeaturesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: bool
        def __init__(self, key: _Optional[str] = ..., value: bool = ...) -> None: ...
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    BIO_FIELD_NUMBER: _ClassVar[int]
    AVATARURL_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    SOUNDSSTATUS_FIELD_NUMBER: _ClassVar[int]
    CREDITS_FIELD_NUMBER: _ClassVar[int]
    FEATURES_FIELD_NUMBER: _ClassVar[int]
    SOUNDSPLAN_FIELD_NUMBER: _ClassVar[int]
    UUID_FIELD_NUMBER: _ClassVar[int]
    ID: int
    Username: str
    Bio: str
    AvatarURL: str
    Location: str
    Email: str
    SoundsStatus: str
    Credits: int
    Features: _containers.ScalarMap[str, bool]
    SoundsPlan: int
    UUID: str
    def __init__(self, ID: _Optional[int] = ..., Username: _Optional[str] = ..., Bio: _Optional[str] = ..., AvatarURL: _Optional[str] = ..., Location: _Optional[str] = ..., Email: _Optional[str] = ..., SoundsStatus: _Optional[str] = ..., Credits: _Optional[int] = ..., Features: _Optional[_Mapping[str, bool]] = ..., SoundsPlan: _Optional[int] = ..., UUID: _Optional[str] = ...) -> None: ...

class LoggedInRequest(_message.Message):
    __slots__ = ("Auth", "User")
    AUTH_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    Auth: Auth
    User: User
    def __init__(self, Auth: _Optional[_Union[Auth, _Mapping]] = ..., User: _Optional[_Union[User, _Mapping]] = ...) -> None: ...

class LoggedInResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UpdatedSessionRequest(_message.Message):
    __slots__ = ("auth", "user")
    AUTH_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    auth: Auth
    user: User
    def __init__(self, auth: _Optional[_Union[Auth, _Mapping]] = ..., user: _Optional[_Union[User, _Mapping]] = ...) -> None: ...

class UpdatedSessionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListSamplesRequest(_message.Message):
    __slots__ = ("NextToken",)
    NEXTTOKEN_FIELD_NUMBER: _ClassVar[int]
    NextToken: int
    def __init__(self, NextToken: _Optional[int] = ...) -> None: ...

class ListSamplesResponse(_message.Message):
    __slots__ = ("NextToken", "Samples")
    NEXTTOKEN_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    NextToken: int
    Samples: _containers.RepeatedCompositeFieldContainer[Sample]
    def __init__(self, NextToken: _Optional[int] = ..., Samples: _Optional[_Iterable[_Union[Sample, _Mapping]]] = ...) -> None: ...

class SampleInfoRequest(_message.Message):
    __slots__ = ("LocalPath", "FileHash", "AudioHash")
    LOCALPATH_FIELD_NUMBER: _ClassVar[int]
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    AUDIOHASH_FIELD_NUMBER: _ClassVar[int]
    LocalPath: str
    FileHash: str
    AudioHash: str
    def __init__(self, LocalPath: _Optional[str] = ..., FileHash: _Optional[str] = ..., AudioHash: _Optional[str] = ...) -> None: ...

class SampleInfoResponse(_message.Message):
    __slots__ = ("Sample",)
    SAMPLE_FIELD_NUMBER: _ClassVar[int]
    Sample: Sample
    def __init__(self, Sample: _Optional[_Union[Sample, _Mapping]] = ...) -> None: ...

class ImportedSampleInfoResponse(_message.Message):
    __slots__ = ("Sample",)
    SAMPLE_FIELD_NUMBER: _ClassVar[int]
    Sample: ImportedSample
    def __init__(self, Sample: _Optional[_Union[ImportedSample, _Mapping]] = ...) -> None: ...

class ListSamplePacksRequest(_message.Message):
    __slots__ = ("NextToken",)
    NEXTTOKEN_FIELD_NUMBER: _ClassVar[int]
    NextToken: int
    def __init__(self, NextToken: _Optional[int] = ...) -> None: ...

class ListSamplePacksResponse(_message.Message):
    __slots__ = ("NextToken", "SamplePacks")
    NEXTTOKEN_FIELD_NUMBER: _ClassVar[int]
    SAMPLEPACKS_FIELD_NUMBER: _ClassVar[int]
    NextToken: int
    SamplePacks: _containers.RepeatedCompositeFieldContainer[SamplePack]
    def __init__(self, NextToken: _Optional[int] = ..., SamplePacks: _Optional[_Iterable[_Union[SamplePack, _Mapping]]] = ...) -> None: ...

class DownloadSampleRequest(_message.Message):
    __slots__ = ("FileHash",)
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    FileHash: str
    def __init__(self, FileHash: _Optional[str] = ...) -> None: ...

class DownloadSampleResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SyncSoundsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SyncSoundsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelSampleDownloadRequest(_message.Message):
    __slots__ = ("FileHash",)
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    FileHash: str
    def __init__(self, FileHash: _Optional[str] = ...) -> None: ...

class CancelSampleDownloadResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SearchSampleRequest(_message.Message):
    __slots__ = ("Liked", "Purchased", "MatchingTagsAndPacks", "SearchTerm", "CollectionUUID", "SortFn", "BPMMin", "BPMMax", "Tags", "FileHash", "Genre", "Instrument", "Key", "SampleType", "PackUUID", "ChordType", "PerPage", "Page", "RandomSeed")
    class PurchasedTypes(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        All: _ClassVar[SearchSampleRequest.PurchasedTypes]
        OnlyPurchased: _ClassVar[SearchSampleRequest.PurchasedTypes]
        NotPurchased: _ClassVar[SearchSampleRequest.PurchasedTypes]
    All: SearchSampleRequest.PurchasedTypes
    OnlyPurchased: SearchSampleRequest.PurchasedTypes
    NotPurchased: SearchSampleRequest.PurchasedTypes
    LIKED_FIELD_NUMBER: _ClassVar[int]
    PURCHASED_FIELD_NUMBER: _ClassVar[int]
    MATCHINGTAGSANDPACKS_FIELD_NUMBER: _ClassVar[int]
    SEARCHTERM_FIELD_NUMBER: _ClassVar[int]
    COLLECTIONUUID_FIELD_NUMBER: _ClassVar[int]
    SORTFN_FIELD_NUMBER: _ClassVar[int]
    BPMMIN_FIELD_NUMBER: _ClassVar[int]
    BPMMAX_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    GENRE_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    SAMPLETYPE_FIELD_NUMBER: _ClassVar[int]
    PACKUUID_FIELD_NUMBER: _ClassVar[int]
    CHORDTYPE_FIELD_NUMBER: _ClassVar[int]
    PERPAGE_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    RANDOMSEED_FIELD_NUMBER: _ClassVar[int]
    Liked: bool
    Purchased: SearchSampleRequest.PurchasedTypes
    MatchingTagsAndPacks: bool
    SearchTerm: str
    CollectionUUID: str
    SortFn: str
    BPMMin: int
    BPMMax: int
    Tags: _containers.RepeatedScalarFieldContainer[str]
    FileHash: str
    Genre: str
    Instrument: str
    Key: str
    SampleType: str
    PackUUID: str
    ChordType: str
    PerPage: int
    Page: int
    RandomSeed: str
    def __init__(self, Liked: bool = ..., Purchased: _Optional[_Union[SearchSampleRequest.PurchasedTypes, str]] = ..., MatchingTagsAndPacks: bool = ..., SearchTerm: _Optional[str] = ..., CollectionUUID: _Optional[str] = ..., SortFn: _Optional[str] = ..., BPMMin: _Optional[int] = ..., BPMMax: _Optional[int] = ..., Tags: _Optional[_Iterable[str]] = ..., FileHash: _Optional[str] = ..., Genre: _Optional[str] = ..., Instrument: _Optional[str] = ..., Key: _Optional[str] = ..., SampleType: _Optional[str] = ..., PackUUID: _Optional[str] = ..., ChordType: _Optional[str] = ..., PerPage: _Optional[int] = ..., Page: _Optional[int] = ..., RandomSeed: _Optional[str] = ...) -> None: ...

class SearchSampleResponse(_message.Message):
    __slots__ = ("TotalHits", "Samples", "MatchingPacks", "MatchingTags")
    class MatchingTagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    TOTALHITS_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    MATCHINGPACKS_FIELD_NUMBER: _ClassVar[int]
    MATCHINGTAGS_FIELD_NUMBER: _ClassVar[int]
    TotalHits: int
    Samples: _containers.RepeatedCompositeFieldContainer[Sample]
    MatchingPacks: _containers.RepeatedCompositeFieldContainer[SamplePack]
    MatchingTags: _containers.ScalarMap[str, int]
    def __init__(self, TotalHits: _Optional[int] = ..., Samples: _Optional[_Iterable[_Union[Sample, _Mapping]]] = ..., MatchingPacks: _Optional[_Iterable[_Union[SamplePack, _Mapping]]] = ..., MatchingTags: _Optional[_Mapping[str, int]] = ...) -> None: ...

class Sample(_message.Message):
    __slots__ = ("LocalPath", "FileHash", "Filename", "AudioHash", "ModifiedTime", "IsPremium", "AudioKey", "BPM", "ChordType", "Dir", "Duration", "Genre", "PreviewURL", "Price", "ProviderName", "ProviderUuid", "ProviderPermalink", "SampleType", "Tags", "WaveformURL", "Published", "Popularity", "PublishedAt", "PurchasedAt", "PackUUID")
    LOCALPATH_FIELD_NUMBER: _ClassVar[int]
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    AUDIOHASH_FIELD_NUMBER: _ClassVar[int]
    MODIFIEDTIME_FIELD_NUMBER: _ClassVar[int]
    ISPREMIUM_FIELD_NUMBER: _ClassVar[int]
    AUDIOKEY_FIELD_NUMBER: _ClassVar[int]
    BPM_FIELD_NUMBER: _ClassVar[int]
    CHORDTYPE_FIELD_NUMBER: _ClassVar[int]
    DIR_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    GENRE_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURL_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    PROVIDERNAME_FIELD_NUMBER: _ClassVar[int]
    PROVIDERUUID_FIELD_NUMBER: _ClassVar[int]
    PROVIDERPERMALINK_FIELD_NUMBER: _ClassVar[int]
    SAMPLETYPE_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    WAVEFORMURL_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_FIELD_NUMBER: _ClassVar[int]
    POPULARITY_FIELD_NUMBER: _ClassVar[int]
    PUBLISHEDAT_FIELD_NUMBER: _ClassVar[int]
    PURCHASEDAT_FIELD_NUMBER: _ClassVar[int]
    PACKUUID_FIELD_NUMBER: _ClassVar[int]
    LocalPath: str
    FileHash: str
    Filename: str
    AudioHash: str
    ModifiedTime: int
    IsPremium: bool
    AudioKey: str
    BPM: int
    ChordType: str
    Dir: str
    Duration: int
    Genre: str
    PreviewURL: str
    Price: int
    ProviderName: str
    ProviderUuid: str
    ProviderPermalink: str
    SampleType: str
    Tags: _containers.RepeatedScalarFieldContainer[str]
    WaveformURL: str
    Published: bool
    Popularity: int
    PublishedAt: int
    PurchasedAt: int
    PackUUID: str
    def __init__(self, LocalPath: _Optional[str] = ..., FileHash: _Optional[str] = ..., Filename: _Optional[str] = ..., AudioHash: _Optional[str] = ..., ModifiedTime: _Optional[int] = ..., IsPremium: bool = ..., AudioKey: _Optional[str] = ..., BPM: _Optional[int] = ..., ChordType: _Optional[str] = ..., Dir: _Optional[str] = ..., Duration: _Optional[int] = ..., Genre: _Optional[str] = ..., PreviewURL: _Optional[str] = ..., Price: _Optional[int] = ..., ProviderName: _Optional[str] = ..., ProviderUuid: _Optional[str] = ..., ProviderPermalink: _Optional[str] = ..., SampleType: _Optional[str] = ..., Tags: _Optional[_Iterable[str]] = ..., WaveformURL: _Optional[str] = ..., Published: bool = ..., Popularity: _Optional[int] = ..., PublishedAt: _Optional[int] = ..., PurchasedAt: _Optional[int] = ..., PackUUID: _Optional[str] = ...) -> None: ...

class ImportedSample(_message.Message):
    __slots__ = ("LocalPath", "Filename", "AudioHash", "IsPremium", "AudioKey", "BPM", "ChordType", "Dir", "Duration", "Genre", "SampleType", "Tags", "PackUUID", "FileExists")
    LOCALPATH_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    AUDIOHASH_FIELD_NUMBER: _ClassVar[int]
    ISPREMIUM_FIELD_NUMBER: _ClassVar[int]
    AUDIOKEY_FIELD_NUMBER: _ClassVar[int]
    BPM_FIELD_NUMBER: _ClassVar[int]
    CHORDTYPE_FIELD_NUMBER: _ClassVar[int]
    DIR_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    GENRE_FIELD_NUMBER: _ClassVar[int]
    SAMPLETYPE_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    PACKUUID_FIELD_NUMBER: _ClassVar[int]
    FILEEXISTS_FIELD_NUMBER: _ClassVar[int]
    LocalPath: str
    Filename: str
    AudioHash: str
    IsPremium: bool
    AudioKey: str
    BPM: int
    ChordType: str
    Dir: str
    Duration: int
    Genre: str
    SampleType: str
    Tags: _containers.RepeatedScalarFieldContainer[str]
    PackUUID: str
    FileExists: bool
    def __init__(self, LocalPath: _Optional[str] = ..., Filename: _Optional[str] = ..., AudioHash: _Optional[str] = ..., IsPremium: bool = ..., AudioKey: _Optional[str] = ..., BPM: _Optional[int] = ..., ChordType: _Optional[str] = ..., Dir: _Optional[str] = ..., Duration: _Optional[int] = ..., Genre: _Optional[str] = ..., SampleType: _Optional[str] = ..., Tags: _Optional[_Iterable[str]] = ..., PackUUID: _Optional[str] = ..., FileExists: bool = ...) -> None: ...

class SamplePack(_message.Message):
    __slots__ = ("UUID", "Name", "CoverURL", "Genre", "Permalink", "ProviderName")
    UUID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    COVERURL_FIELD_NUMBER: _ClassVar[int]
    GENRE_FIELD_NUMBER: _ClassVar[int]
    PERMALINK_FIELD_NUMBER: _ClassVar[int]
    PROVIDERNAME_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Name: str
    CoverURL: str
    Genre: str
    Permalink: str
    ProviderName: str
    def __init__(self, UUID: _Optional[str] = ..., Name: _Optional[str] = ..., CoverURL: _Optional[str] = ..., Genre: _Optional[str] = ..., Permalink: _Optional[str] = ..., ProviderName: _Optional[str] = ...) -> None: ...

class PCMWavFile(_message.Message):
    __slots__ = ("Path", "Channels", "SampleRate", "BitDepth")
    PATH_FIELD_NUMBER: _ClassVar[int]
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    SAMPLERATE_FIELD_NUMBER: _ClassVar[int]
    BITDEPTH_FIELD_NUMBER: _ClassVar[int]
    Path: str
    Channels: int
    SampleRate: int
    BitDepth: int
    def __init__(self, Path: _Optional[str] = ..., Channels: _Optional[int] = ..., SampleRate: _Optional[int] = ..., BitDepth: _Optional[int] = ...) -> None: ...

class ConvertToWavRequest(_message.Message):
    __slots__ = ("Path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    Path: str
    def __init__(self, Path: _Optional[str] = ...) -> None: ...

class ConvertToWavResponse(_message.Message):
    __slots__ = ("WavFile",)
    WAVFILE_FIELD_NUMBER: _ClassVar[int]
    WavFile: PCMWavFile
    def __init__(self, WavFile: _Optional[_Union[PCMWavFile, _Mapping]] = ...) -> None: ...

class ListPluginsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListPluginsResponse(_message.Message):
    __slots__ = ("Plugins",)
    PLUGINS_FIELD_NUMBER: _ClassVar[int]
    Plugins: _containers.RepeatedCompositeFieldContainer[Plugin]
    def __init__(self, Plugins: _Optional[_Iterable[_Union[Plugin, _Mapping]]] = ...) -> None: ...

class RefreshPluginsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RefreshPluginsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InstallPluginRequest(_message.Message):
    __slots__ = ("UUID", "Name")
    UUID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Name: str
    def __init__(self, UUID: _Optional[str] = ..., Name: _Optional[str] = ...) -> None: ...

class InstallPluginResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UpdatePluginRequest(_message.Message):
    __slots__ = ("UUID", "Name", "Version")
    UUID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Name: str
    Version: str
    def __init__(self, UUID: _Optional[str] = ..., Name: _Optional[str] = ..., Version: _Optional[str] = ...) -> None: ...

class UpdatePluginResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelPluginDownloadRequest(_message.Message):
    __slots__ = ("UUID",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    def __init__(self, UUID: _Optional[str] = ...) -> None: ...

class CancelPluginDownloadResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Plugin(_message.Message):
    __slots__ = ("UUID", "Name", "Author", "Version", "Image", "PlanStatus", "IsInstalled", "InstallationPath", "InstallURL", "UpdateURL", "UpdateVersion", "IsSplice")
    UUID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    PLANSTATUS_FIELD_NUMBER: _ClassVar[int]
    ISINSTALLED_FIELD_NUMBER: _ClassVar[int]
    INSTALLATIONPATH_FIELD_NUMBER: _ClassVar[int]
    INSTALLURL_FIELD_NUMBER: _ClassVar[int]
    UPDATEURL_FIELD_NUMBER: _ClassVar[int]
    UPDATEVERSION_FIELD_NUMBER: _ClassVar[int]
    ISSPLICE_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Name: str
    Author: str
    Version: str
    Image: str
    PlanStatus: str
    IsInstalled: bool
    InstallationPath: str
    InstallURL: str
    UpdateURL: str
    UpdateVersion: str
    IsSplice: bool
    def __init__(self, UUID: _Optional[str] = ..., Name: _Optional[str] = ..., Author: _Optional[str] = ..., Version: _Optional[str] = ..., Image: _Optional[str] = ..., PlanStatus: _Optional[str] = ..., IsInstalled: bool = ..., InstallationPath: _Optional[str] = ..., InstallURL: _Optional[str] = ..., UpdateURL: _Optional[str] = ..., UpdateVersion: _Optional[str] = ..., IsSplice: bool = ...) -> None: ...

class UserPreferences(_message.Message):
    __slots__ = ("SpliceFolderPath", "SaveOutsideSpliceFolder", "SampleImportDirectories", "Presets")
    class PresetsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: PresetConfigEntry
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[PresetConfigEntry, _Mapping]] = ...) -> None: ...
    SPLICEFOLDERPATH_FIELD_NUMBER: _ClassVar[int]
    SAVEOUTSIDESPLICEFOLDER_FIELD_NUMBER: _ClassVar[int]
    SAMPLEIMPORTDIRECTORIES_FIELD_NUMBER: _ClassVar[int]
    PRESETS_FIELD_NUMBER: _ClassVar[int]
    SpliceFolderPath: str
    SaveOutsideSpliceFolder: bool
    SampleImportDirectories: _containers.RepeatedScalarFieldContainer[str]
    Presets: _containers.MessageMap[str, PresetConfigEntry]
    def __init__(self, SpliceFolderPath: _Optional[str] = ..., SaveOutsideSpliceFolder: bool = ..., SampleImportDirectories: _Optional[_Iterable[str]] = ..., Presets: _Optional[_Mapping[str, PresetConfigEntry]] = ...) -> None: ...

class PresetConfigEntry(_message.Message):
    __slots__ = ("Path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    Path: str
    def __init__(self, Path: _Optional[str] = ...) -> None: ...

class UserPreferencesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UserPreferencesResponse(_message.Message):
    __slots__ = ("Preferences",)
    PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    Preferences: UserPreferences
    def __init__(self, Preferences: _Optional[_Union[UserPreferences, _Mapping]] = ...) -> None: ...

class UpdateUserPreferencesRequest(_message.Message):
    __slots__ = ("Preferences",)
    PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    Preferences: UserPreferences
    def __init__(self, Preferences: _Optional[_Union[UserPreferences, _Mapping]] = ...) -> None: ...

class UpdateUserPreferencesResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DownloadLogsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DownloadLogsResponse(_message.Message):
    __slots__ = ("Filename",)
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    Filename: str
    def __init__(self, Filename: _Optional[str] = ...) -> None: ...

class CopyFileToClipboardRequest(_message.Message):
    __slots__ = ("Filename",)
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    Filename: str
    def __init__(self, Filename: _Optional[str] = ...) -> None: ...

class CopyFileToClipboardResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ProjectDiskScanRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ProjectDiskScanResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelProjectDiskScanRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CancelProjectDiskScanResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ShutdownRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ShutdownResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ConvertSoundsTrialRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ConvertSoundsTrialResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SendFeedbackRequest(_message.Message):
    __slots__ = ("Text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    Text: str
    def __init__(self, Text: _Optional[str] = ...) -> None: ...

class SendFeedbackResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class InstallAppFromChannelRequest(_message.Message):
    __slots__ = ("Channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    Channel: str
    def __init__(self, Channel: _Optional[str] = ...) -> None: ...

class InstallAppFromChannelResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class Event(_message.Message):
    __slots__ = ("Name", "Data")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    Name: str
    Data: str
    def __init__(self, Name: _Optional[str] = ..., Data: _Optional[str] = ...) -> None: ...

class ImportedAddDirectoryRequest(_message.Message):
    __slots__ = ("Path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    Path: str
    def __init__(self, Path: _Optional[str] = ...) -> None: ...

class ImportedAddDirectoryResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ImportedSearchSamplesRequest(_message.Message):
    __slots__ = ("Text", "Tags", "AudioKey", "ChordType", "Loop", "MinBPM", "MaxBPM", "From", "Size")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    AUDIOKEY_FIELD_NUMBER: _ClassVar[int]
    CHORDTYPE_FIELD_NUMBER: _ClassVar[int]
    LOOP_FIELD_NUMBER: _ClassVar[int]
    MINBPM_FIELD_NUMBER: _ClassVar[int]
    MAXBPM_FIELD_NUMBER: _ClassVar[int]
    FROM_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    Text: str
    Tags: _containers.RepeatedScalarFieldContainer[str]
    AudioKey: str
    ChordType: str
    Loop: SampleType
    MinBPM: int
    MaxBPM: int
    From: int
    Size: int
    def __init__(self, Text: _Optional[str] = ..., Tags: _Optional[_Iterable[str]] = ..., AudioKey: _Optional[str] = ..., ChordType: _Optional[str] = ..., Loop: _Optional[_Union[SampleType, str]] = ..., MinBPM: _Optional[int] = ..., MaxBPM: _Optional[int] = ..., From: _Optional[int] = ..., Size: _Optional[int] = ...) -> None: ...

class ImportedListSamplesResponse(_message.Message):
    __slots__ = ("Results", "Tags", "TotalResults", "NextToken")
    class TagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    TOTALRESULTS_FIELD_NUMBER: _ClassVar[int]
    NEXTTOKEN_FIELD_NUMBER: _ClassVar[int]
    Results: _containers.RepeatedCompositeFieldContainer[ImportedSample]
    Tags: _containers.ScalarMap[str, int]
    TotalResults: int
    NextToken: int
    def __init__(self, Results: _Optional[_Iterable[_Union[ImportedSample, _Mapping]]] = ..., Tags: _Optional[_Mapping[str, int]] = ..., TotalResults: _Optional[int] = ..., NextToken: _Optional[int] = ...) -> None: ...

class ImportedListSamplesRequest(_message.Message):
    __slots__ = ("From", "Size")
    FROM_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    From: int
    Size: int
    def __init__(self, From: _Optional[int] = ..., Size: _Optional[int] = ...) -> None: ...

class ImportedCancelAddDirectoryRequest(_message.Message):
    __slots__ = ("Directory",)
    DIRECTORY_FIELD_NUMBER: _ClassVar[int]
    Directory: str
    def __init__(self, Directory: _Optional[str] = ...) -> None: ...

class ImportedCancelAddDirectoryResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ImportedDeleteSampleMetadataRequest(_message.Message):
    __slots__ = ("LocalPath",)
    LOCALPATH_FIELD_NUMBER: _ClassVar[int]
    LocalPath: str
    def __init__(self, LocalPath: _Optional[str] = ...) -> None: ...

class ImportedDeleteSampleMetadataResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ImportedListTagsRequest(_message.Message):
    __slots__ = ("From", "Size")
    FROM_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    From: int
    Size: int
    def __init__(self, From: _Optional[int] = ..., Size: _Optional[int] = ...) -> None: ...

class ImportedListTagsResponse(_message.Message):
    __slots__ = ("Tags", "NextToken")
    class TagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    TAGS_FIELD_NUMBER: _ClassVar[int]
    NEXTTOKEN_FIELD_NUMBER: _ClassVar[int]
    Tags: _containers.ScalarMap[str, int]
    NextToken: int
    def __init__(self, Tags: _Optional[_Mapping[str, int]] = ..., NextToken: _Optional[int] = ...) -> None: ...

class SamplePackInfoRequest(_message.Message):
    __slots__ = ("UUID",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    def __init__(self, UUID: _Optional[str] = ...) -> None: ...

class SamplePackInfoResponse(_message.Message):
    __slots__ = ("Pack",)
    PACK_FIELD_NUMBER: _ClassVar[int]
    Pack: SamplePack
    def __init__(self, Pack: _Optional[_Union[SamplePack, _Mapping]] = ...) -> None: ...

class ImportedMatchSetPausedStatusRequest(_message.Message):
    __slots__ = ("Paused",)
    PAUSED_FIELD_NUMBER: _ClassVar[int]
    Paused: bool
    def __init__(self, Paused: bool = ...) -> None: ...

class ImportedMatchSetPausedStatusResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ImportedMatchGetProgressRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ImportedMatchGetProgressResponse(_message.Message):
    __slots__ = ("total", "current", "status")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    CURRENT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    total: int
    current: int
    status: str
    def __init__(self, total: _Optional[int] = ..., current: _Optional[int] = ..., status: _Optional[str] = ...) -> None: ...

class ImportedRescanRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ImportedRescanResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CollectionAddRequest(_message.Message):
    __slots__ = ("Name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    Name: str
    def __init__(self, Name: _Optional[str] = ...) -> None: ...

class CollectionAddResponse(_message.Message):
    __slots__ = ("Collection",)
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    Collection: Collection
    def __init__(self, Collection: _Optional[_Union[Collection, _Mapping]] = ...) -> None: ...

class CollectionsListRequest(_message.Message):
    __slots__ = ("Page", "PerPage")
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PERPAGE_FIELD_NUMBER: _ClassVar[int]
    Page: int
    PerPage: int
    def __init__(self, Page: _Optional[int] = ..., PerPage: _Optional[int] = ...) -> None: ...

class CollectionsListResponse(_message.Message):
    __slots__ = ("TotalCount", "Collections")
    TOTALCOUNT_FIELD_NUMBER: _ClassVar[int]
    COLLECTIONS_FIELD_NUMBER: _ClassVar[int]
    TotalCount: int
    Collections: _containers.RepeatedCompositeFieldContainer[Collection]
    def __init__(self, TotalCount: _Optional[int] = ..., Collections: _Optional[_Iterable[_Union[Collection, _Mapping]]] = ...) -> None: ...

class CollectionAddItemsRequest(_message.Message):
    __slots__ = ("UUID", "Samples")
    UUID_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Samples: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, UUID: _Optional[str] = ..., Samples: _Optional[_Iterable[str]] = ...) -> None: ...

class CollectionAddItemsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CollectionDeleteItemsRequest(_message.Message):
    __slots__ = ("UUID", "Samples")
    UUID_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Samples: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, UUID: _Optional[str] = ..., Samples: _Optional[_Iterable[str]] = ...) -> None: ...

class CollectionDeleteItemsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CollectionUpdateRequest(_message.Message):
    __slots__ = ("UUID", "Name", "Description", "Access")
    UUID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Name: str
    Description: str
    Access: CollectionAccess
    def __init__(self, UUID: _Optional[str] = ..., Name: _Optional[str] = ..., Description: _Optional[str] = ..., Access: _Optional[_Union[CollectionAccess, str]] = ...) -> None: ...

class CollectionUpdateResponse(_message.Message):
    __slots__ = ("Collection",)
    COLLECTION_FIELD_NUMBER: _ClassVar[int]
    Collection: Collection
    def __init__(self, Collection: _Optional[_Union[Collection, _Mapping]] = ...) -> None: ...

class CollectionDeleteRequest(_message.Message):
    __slots__ = ("UUID",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    def __init__(self, UUID: _Optional[str] = ...) -> None: ...

class CollectionDeleteResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CollectionCreator(_message.Message):
    __slots__ = ("ID", "Username", "AvatarURL")
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    AVATARURL_FIELD_NUMBER: _ClassVar[int]
    ID: int
    Username: str
    AvatarURL: str
    def __init__(self, ID: _Optional[int] = ..., Username: _Optional[str] = ..., AvatarURL: _Optional[str] = ...) -> None: ...

class Collection(_message.Message):
    __slots__ = ("UUID", "Name", "Description", "Access", "Permalink", "CoverURL", "SampleCount", "PresetCount", "PackCount", "SubscriptionCount", "CreatedByCurrentUser", "Creator", "CreatedAt", "UpdatedAt")
    UUID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    PERMALINK_FIELD_NUMBER: _ClassVar[int]
    COVERURL_FIELD_NUMBER: _ClassVar[int]
    SAMPLECOUNT_FIELD_NUMBER: _ClassVar[int]
    PRESETCOUNT_FIELD_NUMBER: _ClassVar[int]
    PACKCOUNT_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIPTIONCOUNT_FIELD_NUMBER: _ClassVar[int]
    CREATEDBYCURRENTUSER_FIELD_NUMBER: _ClassVar[int]
    CREATOR_FIELD_NUMBER: _ClassVar[int]
    CREATEDAT_FIELD_NUMBER: _ClassVar[int]
    UPDATEDAT_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Name: str
    Description: str
    Access: CollectionAccess
    Permalink: str
    CoverURL: str
    SampleCount: int
    PresetCount: int
    PackCount: int
    SubscriptionCount: int
    CreatedByCurrentUser: bool
    Creator: CollectionCreator
    CreatedAt: str
    UpdatedAt: str
    def __init__(self, UUID: _Optional[str] = ..., Name: _Optional[str] = ..., Description: _Optional[str] = ..., Access: _Optional[_Union[CollectionAccess, str]] = ..., Permalink: _Optional[str] = ..., CoverURL: _Optional[str] = ..., SampleCount: _Optional[int] = ..., PresetCount: _Optional[int] = ..., PackCount: _Optional[int] = ..., SubscriptionCount: _Optional[int] = ..., CreatedByCurrentUser: bool = ..., Creator: _Optional[_Union[CollectionCreator, _Mapping]] = ..., CreatedAt: _Optional[str] = ..., UpdatedAt: _Optional[str] = ...) -> None: ...

class CollectionListSamplesRequest(_message.Message):
    __slots__ = ("UUID", "Page", "PerPage")
    UUID_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PERPAGE_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    Page: int
    PerPage: int
    def __init__(self, UUID: _Optional[str] = ..., Page: _Optional[int] = ..., PerPage: _Optional[int] = ...) -> None: ...

class CollectionSample(_message.Message):
    __slots__ = ("LocalPath", "FileHash", "Filename", "AudioHash", "ModifiedTime", "IsPremium", "AudioKey", "BPM", "ChordType", "Dir", "Duration", "Genre", "PreviewURL", "Price", "ProviderName", "ProviderUuid", "ProviderPermalink", "SampleType", "Tags", "WaveformURL", "Published", "Popularity", "PublishedAt", "PurchasedAt", "Pack")
    LOCALPATH_FIELD_NUMBER: _ClassVar[int]
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    AUDIOHASH_FIELD_NUMBER: _ClassVar[int]
    MODIFIEDTIME_FIELD_NUMBER: _ClassVar[int]
    ISPREMIUM_FIELD_NUMBER: _ClassVar[int]
    AUDIOKEY_FIELD_NUMBER: _ClassVar[int]
    BPM_FIELD_NUMBER: _ClassVar[int]
    CHORDTYPE_FIELD_NUMBER: _ClassVar[int]
    DIR_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    GENRE_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURL_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    PROVIDERNAME_FIELD_NUMBER: _ClassVar[int]
    PROVIDERUUID_FIELD_NUMBER: _ClassVar[int]
    PROVIDERPERMALINK_FIELD_NUMBER: _ClassVar[int]
    SAMPLETYPE_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    WAVEFORMURL_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_FIELD_NUMBER: _ClassVar[int]
    POPULARITY_FIELD_NUMBER: _ClassVar[int]
    PUBLISHEDAT_FIELD_NUMBER: _ClassVar[int]
    PURCHASEDAT_FIELD_NUMBER: _ClassVar[int]
    PACK_FIELD_NUMBER: _ClassVar[int]
    LocalPath: str
    FileHash: str
    Filename: str
    AudioHash: str
    ModifiedTime: int
    IsPremium: bool
    AudioKey: str
    BPM: int
    ChordType: str
    Dir: str
    Duration: int
    Genre: str
    PreviewURL: str
    Price: int
    ProviderName: str
    ProviderUuid: str
    ProviderPermalink: str
    SampleType: str
    Tags: _containers.RepeatedScalarFieldContainer[str]
    WaveformURL: str
    Published: bool
    Popularity: int
    PublishedAt: int
    PurchasedAt: int
    Pack: SamplePack
    def __init__(self, LocalPath: _Optional[str] = ..., FileHash: _Optional[str] = ..., Filename: _Optional[str] = ..., AudioHash: _Optional[str] = ..., ModifiedTime: _Optional[int] = ..., IsPremium: bool = ..., AudioKey: _Optional[str] = ..., BPM: _Optional[int] = ..., ChordType: _Optional[str] = ..., Dir: _Optional[str] = ..., Duration: _Optional[int] = ..., Genre: _Optional[str] = ..., PreviewURL: _Optional[str] = ..., Price: _Optional[int] = ..., ProviderName: _Optional[str] = ..., ProviderUuid: _Optional[str] = ..., ProviderPermalink: _Optional[str] = ..., SampleType: _Optional[str] = ..., Tags: _Optional[_Iterable[str]] = ..., WaveformURL: _Optional[str] = ..., Published: bool = ..., Popularity: _Optional[int] = ..., PublishedAt: _Optional[int] = ..., PurchasedAt: _Optional[int] = ..., Pack: _Optional[_Union[SamplePack, _Mapping]] = ...) -> None: ...

class CollectionListSamplesResponse(_message.Message):
    __slots__ = ("TotalHits", "Samples")
    TOTALHITS_FIELD_NUMBER: _ClassVar[int]
    SAMPLES_FIELD_NUMBER: _ClassVar[int]
    TotalHits: int
    Samples: _containers.RepeatedCompositeFieldContainer[CollectionSample]
    def __init__(self, TotalHits: _Optional[int] = ..., Samples: _Optional[_Iterable[_Union[CollectionSample, _Mapping]]] = ...) -> None: ...

class Preset(_message.Message):
    __slots__ = ("UUID", "FileHash", "Filename", "LocalPath", "Tags", "Price", "IsDefault", "PluginDescriptionID", "PluginName", "PluginVersion", "Published", "PublishedAt", "ProviderName", "Trending", "ProviderUuid", "ProviderPermalink", "Pack", "PreviewURL", "PreviewURLMonoG1", "PreviewURLMonoG3", "PreviewURLMonoG5", "PreviewURLPolyG1", "PreviewURLPolyG3", "PreviewURLPolyG5", "PurchasedAt")
    UUID_FIELD_NUMBER: _ClassVar[int]
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    LOCALPATH_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    ISDEFAULT_FIELD_NUMBER: _ClassVar[int]
    PLUGINDESCRIPTIONID_FIELD_NUMBER: _ClassVar[int]
    PLUGINNAME_FIELD_NUMBER: _ClassVar[int]
    PLUGINVERSION_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_FIELD_NUMBER: _ClassVar[int]
    PUBLISHEDAT_FIELD_NUMBER: _ClassVar[int]
    PROVIDERNAME_FIELD_NUMBER: _ClassVar[int]
    TRENDING_FIELD_NUMBER: _ClassVar[int]
    PROVIDERUUID_FIELD_NUMBER: _ClassVar[int]
    PROVIDERPERMALINK_FIELD_NUMBER: _ClassVar[int]
    PACK_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURL_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURLMONOG1_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURLMONOG3_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURLMONOG5_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURLPOLYG1_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURLPOLYG3_FIELD_NUMBER: _ClassVar[int]
    PREVIEWURLPOLYG5_FIELD_NUMBER: _ClassVar[int]
    PURCHASEDAT_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    FileHash: str
    Filename: str
    LocalPath: str
    Tags: _containers.RepeatedScalarFieldContainer[str]
    Price: int
    IsDefault: bool
    PluginDescriptionID: int
    PluginName: str
    PluginVersion: str
    Published: bool
    PublishedAt: int
    ProviderName: str
    Trending: float
    ProviderUuid: str
    ProviderPermalink: str
    Pack: SamplePack
    PreviewURL: str
    PreviewURLMonoG1: str
    PreviewURLMonoG3: str
    PreviewURLMonoG5: str
    PreviewURLPolyG1: str
    PreviewURLPolyG3: str
    PreviewURLPolyG5: str
    PurchasedAt: int
    def __init__(self, UUID: _Optional[str] = ..., FileHash: _Optional[str] = ..., Filename: _Optional[str] = ..., LocalPath: _Optional[str] = ..., Tags: _Optional[_Iterable[str]] = ..., Price: _Optional[int] = ..., IsDefault: bool = ..., PluginDescriptionID: _Optional[int] = ..., PluginName: _Optional[str] = ..., PluginVersion: _Optional[str] = ..., Published: bool = ..., PublishedAt: _Optional[int] = ..., ProviderName: _Optional[str] = ..., Trending: _Optional[float] = ..., ProviderUuid: _Optional[str] = ..., ProviderPermalink: _Optional[str] = ..., Pack: _Optional[_Union[SamplePack, _Mapping]] = ..., PreviewURL: _Optional[str] = ..., PreviewURLMonoG1: _Optional[str] = ..., PreviewURLMonoG3: _Optional[str] = ..., PreviewURLMonoG5: _Optional[str] = ..., PreviewURLPolyG1: _Optional[str] = ..., PreviewURLPolyG3: _Optional[str] = ..., PreviewURLPolyG5: _Optional[str] = ..., PurchasedAt: _Optional[int] = ...) -> None: ...

class PresetsListPurchasedRequest(_message.Message):
    __slots__ = ("SortFn", "SortOrder", "PerPage", "Page")
    SORTFN_FIELD_NUMBER: _ClassVar[int]
    SORTORDER_FIELD_NUMBER: _ClassVar[int]
    PERPAGE_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    SortFn: str
    SortOrder: str
    PerPage: int
    Page: int
    def __init__(self, SortFn: _Optional[str] = ..., SortOrder: _Optional[str] = ..., PerPage: _Optional[int] = ..., Page: _Optional[int] = ...) -> None: ...

class PresetsListPurchasedResponse(_message.Message):
    __slots__ = ("TotalHits", "Presets")
    TOTALHITS_FIELD_NUMBER: _ClassVar[int]
    PRESETS_FIELD_NUMBER: _ClassVar[int]
    TotalHits: int
    Presets: _containers.RepeatedCompositeFieldContainer[Preset]
    def __init__(self, TotalHits: _Optional[int] = ..., Presets: _Optional[_Iterable[_Union[Preset, _Mapping]]] = ...) -> None: ...

class PresetDownloadRequest(_message.Message):
    __slots__ = ("UUID",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    def __init__(self, UUID: _Optional[str] = ...) -> None: ...

class PresetDownloadResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PresetsDownloadCancelRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PresetsDownloadCancelResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UnlicensedPresetDownloadRequest(_message.Message):
    __slots__ = ("UUID", "UnlicensedSignedS3Url", "Temporary", "PluginName")
    UUID_FIELD_NUMBER: _ClassVar[int]
    UNLICENSEDSIGNEDS3URL_FIELD_NUMBER: _ClassVar[int]
    TEMPORARY_FIELD_NUMBER: _ClassVar[int]
    PLUGINNAME_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    UnlicensedSignedS3Url: str
    Temporary: bool
    PluginName: str
    def __init__(self, UUID: _Optional[str] = ..., UnlicensedSignedS3Url: _Optional[str] = ..., Temporary: bool = ..., PluginName: _Optional[str] = ...) -> None: ...

class UnlicensedPresetDownloadResponse(_message.Message):
    __slots__ = ("Path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    Path: str
    def __init__(self, Path: _Optional[str] = ...) -> None: ...

class PresetPurchaseRequest(_message.Message):
    __slots__ = ("UUID",)
    UUID_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    def __init__(self, UUID: _Optional[str] = ...) -> None: ...

class PresetPurchaseResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PresetInfoRequest(_message.Message):
    __slots__ = ("UUID", "FileHash", "PluginName")
    UUID_FIELD_NUMBER: _ClassVar[int]
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    PLUGINNAME_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    FileHash: str
    PluginName: str
    def __init__(self, UUID: _Optional[str] = ..., FileHash: _Optional[str] = ..., PluginName: _Optional[str] = ...) -> None: ...

class PresetInfo(_message.Message):
    __slots__ = ("UUID", "FileHash", "LocalPath")
    UUID_FIELD_NUMBER: _ClassVar[int]
    FILEHASH_FIELD_NUMBER: _ClassVar[int]
    LOCALPATH_FIELD_NUMBER: _ClassVar[int]
    UUID: str
    FileHash: str
    LocalPath: str
    def __init__(self, UUID: _Optional[str] = ..., FileHash: _Optional[str] = ..., LocalPath: _Optional[str] = ...) -> None: ...

class PresetInfoResponse(_message.Message):
    __slots__ = ("Preset",)
    PRESET_FIELD_NUMBER: _ClassVar[int]
    Preset: PresetInfo
    def __init__(self, Preset: _Optional[_Union[PresetInfo, _Mapping]] = ...) -> None: ...

class FlagValue(_message.Message):
    __slots__ = ("name", "type", "boolValue", "stringValue")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    BOOLVALUE_FIELD_NUMBER: _ClassVar[int]
    STRINGVALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: FlagValueType
    boolValue: bool
    stringValue: str
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[FlagValueType, str]] = ..., boolValue: bool = ..., stringValue: _Optional[str] = ...) -> None: ...

class UpdatedFlagsRequest(_message.Message):
    __slots__ = ("flags",)
    FLAGS_FIELD_NUMBER: _ClassVar[int]
    flags: _containers.RepeatedCompositeFieldContainer[FlagValue]
    def __init__(self, flags: _Optional[_Iterable[_Union[FlagValue, _Mapping]]] = ...) -> None: ...

class UpdatedFlagsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CountPresetsToCleanRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CountPresetsToCleanResponse(_message.Message):
    __slots__ = ("count",)
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: int
    def __init__(self, count: _Optional[int] = ...) -> None: ...

class CleanPresetsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class CleanPresetsResponse(_message.Message):
    __slots__ = ("path",)
    PATH_FIELD_NUMBER: _ClassVar[int]
    path: str
    def __init__(self, path: _Optional[str] = ...) -> None: ...

class SyncPresetsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SyncPresetsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
