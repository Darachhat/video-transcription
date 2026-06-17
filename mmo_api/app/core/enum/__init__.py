from enum import Enum


class JobStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSLATING = "TRANSLATING"
    DUBBING = "DUBBING"
    DONE = "DONE"
    FAILED = "FAILED"


ACTIVE_STATUSES = {
    JobStatus.PENDING,
    JobStatus.DOWNLOADING,
    JobStatus.TRANSCRIBING,
    JobStatus.TRANSLATING,
    JobStatus.DUBBING,
}

TERMINAL_STATUSES = {JobStatus.DONE, JobStatus.FAILED}

STAGE_ORDER = [
    JobStatus.PENDING,
    JobStatus.DOWNLOADING,
    JobStatus.TRANSCRIBING,
    JobStatus.TRANSLATING,
    JobStatus.DUBBING,
    JobStatus.DONE,
]
