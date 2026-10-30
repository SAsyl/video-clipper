"""Application specific exception hierarchy."""


class VideoClipperError(Exception):
    """Base class for every failure raised by this application."""


class InvalidIdentifierError(VideoClipperError):
    """Raised when a source or clip identifier is not filesystem safe."""


class InvalidTimecodeError(VideoClipperError):
    """Raised when a timecode cannot be parsed or is out of range."""


class DownloadError(VideoClipperError):
    """Raised when yt-dlp fails to retrieve the requested video."""


class ProbeError(VideoClipperError):
    """Raised when ffprobe cannot describe a media file."""


class CutError(VideoClipperError):
    """Raised when ffmpeg fails to produce the requested clip."""


class JobNotFoundError(VideoClipperError):
    """Raised when a job id is unknown to the registry."""


class MediaNotFoundError(VideoClipperError):
    """Raised when a requested media file is missing on disk."""


class UnsupportedMediaError(VideoClipperError):
    """Raised when an uploaded file is not an importable video."""
