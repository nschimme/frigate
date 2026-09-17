"""FAAC audio encoding utilities for Frigate."""

import logging
import os
import shutil
import subprocess as sp

logger = logging.getLogger(__name__)


def resolve_faac_path(path: str = "default") -> str:
    """Resolve the FAAC binary path.

    Args:
        path: Custom binary path or 'default' to search system PATH.

    Returns:
        The resolved FAAC binary path.
    """
    if path and path != "default":
        return path

    which_faac = shutil.which("faac")
    if which_faac:
        return which_faac

    for common_path in ("/usr/local/bin/faac", "/usr/bin/faac"):
        if os.path.isfile(common_path) and os.access(common_path, os.X_OK):
            return common_path

    return "faac"


def build_faac_cmd(
    faac_path: str = "default",
    bitrate: int | None = 64,
    object_type: str = "auto",
    adts: bool = True,
    output_file: str = "-",
    input_file: str = "-",
    sample_rate: int = 44100,
    channels: int = 2,
    bits_per_sample: int = 16,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build command line arguments for the FAAC encoder.

    Args:
        faac_path: Path to FAAC binary or 'default'.
        bitrate: Average bitrate (ABR) in kbps (e.g. 32, 64, 128). None to omit -b.
        object_type: AAC object type ('auto', 'he-aac-v1', 'lc').
        adts: Whether to output ADTS stream format (-a).
        output_file: Output file path or '-' for stdout.
        input_file: Input file path or '-' for stdin.
        sample_rate: Sample rate for raw PCM input.
        channels: Number of channels for raw PCM input.
        bits_per_sample: Bits per sample for raw PCM input (16, 24, 32).
        extra_args: Additional command line arguments to pass to FAAC.

    Returns:
        List of command line tokens for subprocess execution.
    """
    cmd = [resolve_faac_path(faac_path)]

    # Raw PCM input settings if stdin/pipe
    if input_file == "-":
        cmd.extend(
            [
                "-P",
                "-R",
                str(sample_rate),
                "-B",
                str(bits_per_sample),
                "-C",
                str(channels),
            ]
        )

    if adts:
        cmd.append("-a")

    if object_type and object_type in ("auto", "he-aac-v1", "lc"):
        cmd.extend(["--object-type", object_type])

    if bitrate is not None and bitrate > 0:
        cmd.extend(["-b", str(bitrate)])

    if extra_args:
        cmd.extend(extra_args)

    cmd.extend(["-o", output_file, input_file])
    return cmd


def encode_audio_with_faac(
    audio_data: bytes,
    bitrate: int = 64,
    object_type: str = "auto",
    faac_path: str = "default",
) -> bytes | None:
    """Encode WAV/PCM audio bytes to AAC using FAAC.

    Args:
        audio_data: WAV or headered PCM audio bytes.
        bitrate: Target average bitrate in kbps.
        object_type: AAC object type ('auto', 'he-aac-v1', 'lc').
        faac_path: Path to FAAC binary or 'default'.

    Returns:
        Bytes of encoded AAC audio, or None if encoding failed.
    """
    if not audio_data:
        logger.warning("Empty audio data passed to FAAC encoder")
        return None

    cmd = build_faac_cmd(
        faac_path=faac_path,
        bitrate=bitrate,
        object_type=object_type,
        adts=True,
        output_file="-",
        input_file="-",
    )

    try:
        process = sp.run(
            cmd,
            input=audio_data,
            capture_output=True,
        )

        if process.returncode == 0:
            return process.stdout

        logger.error(
            "FAAC process exited with code %d: %s",
            process.returncode,
            process.stderr.decode(errors="replace"),
        )
        return None
    except Exception as err:
        logger.error("Failed to run FAAC process: %s", err)
        return None


def pipe_ffmpeg_to_faac(
    ffmpeg_cmd: list[str],
    faac_cmd: list[str],
) -> bytes | None:
    """Pipe uncompressed audio directly from FFmpeg into FAAC encoder.

    Args:
        ffmpeg_cmd: FFmpeg command outputting raw audio to stdout (-f wav - or -f s16le -).
        faac_cmd: FAAC command taking stdin input and outputting ADTS to stdout.

    Returns:
        Bytes of encoded AAC audio output, or None on failure.
    """
    try:
        ffmpeg_proc = sp.Popen(
            ffmpeg_cmd,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        faac_proc = sp.Popen(
            faac_cmd,
            stdin=ffmpeg_proc.stdout,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )

        # Allow ffmpeg_proc to receive a SIGPIPE if faac_proc exits early
        if ffmpeg_proc.stdout is not None:
            ffmpeg_proc.stdout.close()

        faac_out, faac_err = faac_proc.communicate()
        if ffmpeg_proc.stderr:
            ffmpeg_proc.stderr.read()
        ffmpeg_proc.wait()

        if faac_proc.returncode == 0 and ffmpeg_proc.returncode == 0:
            return faac_out

        logger.error(
            "FFmpeg/FAAC pipeline error. FFmpeg exit: %d, FAAC exit: %d. FAAC stderr: %s",
            ffmpeg_proc.returncode,
            faac_proc.returncode,
            faac_err.decode(errors="replace"),
        )
        return None
    except Exception as err:
        logger.error("Failed to execute FFmpeg to FAAC pipeline: %s", err)
        return None
