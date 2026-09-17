import unittest
from unittest.mock import MagicMock, patch

from frigate.util.faac import (
    build_faac_cmd,
    encode_audio_with_faac,
    pipe_ffmpeg_to_faac,
    resolve_faac_path,
)


class TestFaac(unittest.TestCase):
    def test_resolve_faac_path_custom(self):
        self.assertEqual(resolve_faac_path("/custom/bin/faac"), "/custom/bin/faac")

    @patch("shutil.which")
    def test_resolve_faac_path_default(self, mock_which):
        mock_which.returncode = 0
        mock_which.return_value = "/usr/bin/faac"
        self.assertEqual(resolve_faac_path("default"), "/usr/bin/faac")

    def test_build_faac_cmd_default(self):
        cmd = build_faac_cmd(
            faac_path="/bin/faac",
            bitrate=64,
            object_type="auto",
            input_file="input.wav",
        )
        self.assertEqual(
            cmd,
            ["/bin/faac", "-a", "--object-type", "auto", "-b", "64", "-o", "-", "input.wav"],
        )

    def test_build_faac_cmd_raw_stdin(self):
        cmd = build_faac_cmd(
            faac_path="/bin/faac",
            bitrate=64,
            object_type="auto",
            input_file="-",
            sample_rate=44100,
            channels=2,
            bits_per_sample=16,
        )
        self.assertEqual(
            cmd,
            [
                "/bin/faac",
                "-P",
                "-R",
                "44100",
                "-B",
                "16",
                "-C",
                "2",
                "-a",
                "--object-type",
                "auto",
                "-b",
                "64",
                "-o",
                "-",
                "-",
            ],
        )

    def test_build_faac_cmd_he_aac(self):
        cmd = build_faac_cmd(
            faac_path="/bin/faac",
            bitrate=32,
            object_type="he-aac-v1",
            adts=True,
            output_file="/tmp/out.aac",
            input_file="input.wav",
        )
        self.assertEqual(
            cmd,
            [
                "/bin/faac",
                "-a",
                "--object-type",
                "he-aac-v1",
                "-b",
                "32",
                "-o",
                "/tmp/out.aac",
                "input.wav",
            ],
        )

    def test_build_faac_cmd_lc_aac(self):
        cmd = build_faac_cmd(
            faac_path="/bin/faac",
            bitrate=128,
            object_type="lc",
            extra_args=["-c", "18000"],
            input_file="input.wav",
        )
        self.assertEqual(
            cmd,
            [
                "/bin/faac",
                "-a",
                "--object-type",
                "lc",
                "-b",
                "128",
                "-c",
                "18000",
                "-o",
                "-",
                "input.wav",
            ],
        )

    @patch("subprocess.run")
    def test_encode_audio_with_faac_success(self, mock_run):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"encoded_aac_bytes"
        mock_run.return_value = mock_proc

        result = encode_audio_with_faac(
            b"fake_wav_bytes",
            bitrate=64,
            object_type="auto",
            faac_path="/bin/faac",
        )
        self.assertEqual(result, b"encoded_aac_bytes")

    def test_encode_audio_with_faac_empty_input(self):
        result = encode_audio_with_faac(b"")
        self.assertIsNone(result)

    @patch("subprocess.Popen")
    def test_pipe_ffmpeg_to_faac_success(self, mock_popen):
        mock_ffmpeg_proc = MagicMock()
        mock_ffmpeg_proc.returncode = 0
        mock_ffmpeg_proc.stdout = MagicMock()

        mock_faac_proc = MagicMock()
        mock_faac_proc.returncode = 0
        mock_faac_proc.communicate.return_value = (b"aac_stream_bytes", b"")

        mock_popen.side_effect = [mock_ffmpeg_proc, mock_faac_proc]

        res = pipe_ffmpeg_to_faac(["ffmpeg", "-i", "in.mp4"], ["faac", "-"])
        self.assertEqual(res, b"aac_stream_bytes")
