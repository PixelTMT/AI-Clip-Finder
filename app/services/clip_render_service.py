import os
from typing import List
import ffmpeg
from app.api.models import ClipExportRequest, SubtitleWord


class ClipRenderService:
    def _hex_to_ass_color(self, hex_color: str) -> str:
        # #RRGGBB -> &HBBGGRR
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H00{b}{g}{r}"
        return "&H00FFFFFF"

    def _generate_ass_content(
        self, words: List[SubtitleWord], options: ClipExportRequest
    ) -> str:
        # Font size mapping
        font_sizes = {"Small": 40, "Medium": 60, "Large": 80}
        font_size = font_sizes.get(options.font_size, 60)

        # Color
        primary_color = self._hex_to_ass_color(options.font_color)

        # Position (Alignment)
        # 1: Bottom Left, 2: Bottom Center, 3: Bottom Right
        # 4: Mid Left, 5: Mid Center, 6: Mid Right
        # 7: Top Left, 8: Top Center, 9: Top Right
        align_map = {"Top": 8, "Center": 5, "Bottom": 2}
        alignment = align_map.get(options.subtitle_position, 2)

        # Margins (Vertical)
        margin_v = 100 if options.subtitle_position in ["Top", "Bottom"] else 0

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{options.font_family},{font_size},{primary_color},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,{alignment},50,50,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []

        def format_time(seconds):
            # h:mm:ss.cc
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            cs = int((seconds % 1) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        for w in words:
            start = format_time(w.start)
            end = format_time(w.end)
            text = w.word
            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        return header + "\n".join(events)

    def render_video(
        self, input_path: str, output_path: str, ass_path: str, start: float, end: float
    ):
        """
        Renders the video with cropping and burned-in subtitles using ffmpeg-python.
        """
        # Escape path for filter
        # Windows: "D:\foo\bar.ass" -> "D\:/foo/bar.ass" or use forward slashes for filter arg
        ass_path_filter = ass_path.replace("\\", "/").replace(":", "\\:")

        try:
            stream = ffmpeg.input(input_path, ss=start, to=end)

            # Crop to 9:16 aspect ratio (width based on height), center horizontally.
            # Burning subtitles after crop
            stream = stream.filter("crop", "ih*(9/16)", "ih", "(iw-ow)/2", 0)
            stream = stream.filter("subtitles", ass_path_filter)

            stream = ffmpeg.output(stream, output_path, vcodec="libx264", acodec="aac")

            ffmpeg.run(
                stream, overwrite_output=True, capture_stdout=True, capture_stderr=True
            )
        except ffmpeg.Error as e:
            err_msg = e.stderr.decode() if e.stderr else str(e)
            raise RuntimeError(f"FFmpeg render failed: {err_msg}")

    def generate_ass_file(
        self, words: List[SubtitleWord], options: ClipExportRequest, output_path: str
    ):
        content = self._generate_ass_content(words, options)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
