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
        self.assertEqual(resolve_faac_path("/custom/faac"), "/custom/faac")

    @patch("shutil.which")
    def test_resolve_faac_path_default(self, mock_which):
        mock_which.return_value = "/usr/local/bin/faac"
        self.assertEqual(resolve_faac_path("default"), "/usr/local/bin/faac")

    def test_build_faac_cmd_default(self):
        cmd = build_faac_cmd(faac_path="/bin/faac", bitrate=64, object_type="auto")
        self.assertEqual(
            cmd,
            ["/bin/faac", "-a", "--object-type", "auto", "-b", "64", "-", "-o", "-"],
        )

    def test_build_faac_cmd_he_aac(self):
        cmd = build_faac_cmd(
            faac_path="/bin/faac",
            bitrate=32,
            object_type="he-aac-v1",
            adts=True,
            output_file="/tmp/out.aac",
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
                "-",
                "-o",
                "/tmp/out.aac",
            ],
        )

    def test_build_faac_cmd_lc_aac(self):
        cmd = build_faac_cmd(
            faac_path="/bin/faac",
            bitrate=128,
            object_type="lc",
            extra_args=["-c", "18000"],
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
                "-",
                "-o",
                "-",
            ],
        )

    @patch("subprocess.run")
    def test_encode_audio_with_faac_success(self, mock_run):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b"ENCODED_AAC_HEADER_AND_DATA"
        mock_run.return_value = mock_process

        input_wav = b"RIFF....WAVEfmt ...."
        result = encode_audio_with_faac(
            input_wav, bitrate=64, object_type="auto", faac_path="/bin/faac"
        )

        self.assertEqual(result, b"ENCODED_AAC_HEADER_AND_DATA")
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_encode_audio_with_faac_failure(self, mock_run):
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stderr = b"Encoding error"
        mock_run.return_value = mock_process

        result = encode_audio_with_faac(b"BAD_DATA", faac_path="/bin/faac")
        self.assertIsNone(result)

    def test_encode_audio_with_faac_empty_input(self):
        result = encode_audio_with_faac(b"")
        self.assertIsNone(result)

    @patch("subprocess.Popen")
    def test_pipe_ffmpeg_to_faac_success(self, mock_popen):
        ffmpeg_proc = MagicMock()
        ffmpeg_proc.returncode = 0
        ffmpeg_proc.stderr.read.return_value = b""

        faac_proc = MagicMock()
        faac_proc.returncode = 0
        faac_proc.communicate.return_value = (b"FAAC_OUTPUT_DATA", b"")

        mock_popen.side_effect = [ffmpeg_proc, faac_proc]

        result = pipe_ffmpeg_to_faac(
            ["ffmpeg", "-i", "input.mp4", "-f", "wav", "-"],
            ["faac", "-a", "-b", "64", "-", "-o", "-"],
        )

        self.assertEqual(result, b"FAAC_OUTPUT_DATA")


if __name__ == "__main__":
    unittest.main()
